"""
HoloDesk daemon: the headless, always-on half.

No camera, no overlay, no microphone. It keeps the brain alive, listens for
you on Telegram, and reports what the laptop is doing. Run it at login with
scripts/install_autostart.ps1 and it restarts itself after crashes and reboots.

It must run inside your logged-in desktop session (a Scheduled Task "at log
on"), NOT as a Windows service: services live in session 0 and cannot see or
click your windows.
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
LOCK = DATA / "daemon.lock"
logger = logging.getLogger("holodesk.daemon")


def _setup_logging() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [RotatingFileHandler(
        DATA / "holodesk_daemon.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")]
    if sys.stderr is not None:           # pythonw.exe has no console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _acquire_lock() -> bool:
    """One daemon per machine: Telegram allows a single poller per bot."""
    try:
        import psutil
        if LOCK.exists():
            old = int(LOCK.read_text().strip() or 0)
            if old and old != os.getpid() and psutil.pid_exists(old):
                try:
                    if "python" in psutil.Process(old).name().lower():
                        return False
                except psutil.Error:
                    pass
    except Exception:
        pass
    LOCK.write_text(str(os.getpid()))
    atexit.register(lambda: LOCK.unlink(missing_ok=True))
    return True


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    for stream in (sys.stdout, sys.stderr):   # Nepali text must not crash logging
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    _setup_logging()

    if not _acquire_lock():
        logger.error("another HoloDesk daemon is already running; exiting")
        return 1

    from brain.bootstrap import build_engine
    from brain.config import load_config
    cfg = load_config()
    engine = build_engine(cfg=cfg)
    if engine is None:
        logger.error("no LLM configured: set GROQ_API_KEY in .env")
        return 2
    if not cfg.telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set; see docs/BRAIN.md, 'Phone setup'")
        return 2
    if not cfg.telegram_allowed_ids:
        logger.warning("TELEGRAM_ALLOWED_USER_IDS is empty: the bot will obey NOBODY. "
                       "Message it once to learn your ID, add it to .env, restart.")

    from remote.telegram_bridge import TelegramBridge
    from service.monitors import Monitors
    from speech.stt import CloudSTT

    bridge = TelegramBridge(engine, cfg.telegram_token, cfg.telegram_allowed_ids, stt=CloudSTT())
    bridge.start()
    monitors = Monitors(notify=bridge.notify, engine=engine)
    monitors.start()

    stop = threading.Event()

    def _shutdown(*_):
        stop.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError):
            pass

    bridge.notify("🟢 HoloDesk is online. /help shows what I can do.")
    logger.info("daemon running: %d tools, %d allowed user(s)",
                len(engine.registry), len(cfg.telegram_allowed_ids))
    try:
        while not stop.is_set():
            time.sleep(1)
    finally:
        monitors.stop()
        bridge.notify("🔴 HoloDesk is going offline.")
        bridge.stop()
        try:
            engine.write_diary(min_turns=2)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
