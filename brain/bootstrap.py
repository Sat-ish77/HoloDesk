"""
One place that assembles the brain, used by both entry points:

  app/main.py      the overlay (gestures + voice)        -> build_engine()
  run_daemon.py    the headless 24/7 service (phone)     -> build_engine()

Both share the same SQLite memory, so something said by voice at the desk can
be followed up from the phone.
"""

from __future__ import annotations

import logging
import os

from .config import BrainConfig, load_config
from .engine import ReplyEngine
from .tools import build_default_registry

logger = logging.getLogger(__name__)


def _lazy(factory):
    """Create the object on first use, remember it, never raise."""
    box: dict = {}

    def provider():
        if "value" not in box:
            try:
                box["value"] = factory()
            except Exception as e:
                logger.warning("optional agent unavailable: %s", e)
                box["value"] = None
        return box["value"]
    return provider


def _make_task_agent():
    from agents.task_agent import TaskAgent
    return TaskAgent()


def _make_screen_agent():
    from agents.screen_agent import screen_agent
    return screen_agent


def build_engine(task_agent=None, screen_agent=None,
                 cfg: BrainConfig | None = None) -> ReplyEngine | None:
    """Returns a ready engine, or None when the brain is disabled or has no
    LLM to talk to (the caller then keeps using the legacy regex router)."""
    cfg = cfg or load_config()
    if (os.getenv("HOLODESK_BRAIN") or "1").strip() != "1":
        logger.info("brain disabled by HOLODESK_BRAIN=0")
        return None
    if not cfg.llm_ready:
        logger.warning("brain disabled: no LLM key (set GROQ_API_KEY in .env)")
        return None

    registry = build_default_registry(
        task_agent_provider=(lambda: task_agent) if task_agent is not None else _lazy(_make_task_agent),
        screen_agent_provider=(lambda: screen_agent) if screen_agent is not None else _lazy(_make_screen_agent),
    )
    engine = ReplyEngine(registry=registry, cfg=cfg)

    # Send-only phone link, so "text me when it's done" works from the overlay
    # too. Receiving messages is the daemon's job (one poller per bot).
    if cfg.telegram_token and cfg.telegram_allowed_ids:
        try:
            from remote.telegram_bridge import TelegramSender
            sender = TelegramSender(cfg.telegram_token, cfg.telegram_allowed_ids)
            engine.notify = sender.notify
        except Exception as e:
            logger.warning("phone notifications unavailable: %s", e)
    logger.info("brain ready: %d tools, model %s", len(registry), cfg.chat_model or "auto")
    return engine
