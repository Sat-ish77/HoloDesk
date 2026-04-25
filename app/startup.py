"""
Startup module - runs once before the Pygame overlay initialises.

Responsibilities:
  1. If --demo flag: seed 14 days of fake app_events into the DB (skipped
     if data already exists so re-runs don't duplicate rows).
  2. Call morning_briefing.generate_briefing() to build the spoken intro.
  3. Persist the briefing text via db.set_pref("pending_briefing", ...)
     so main.py can read and speak it after the overlay is visible.

The whole function is wrapped in try/except - a broken startup must NEVER
prevent the overlay from launching.
"""

import logging
import sys
import os

from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Ensure parent repo root is on the path when this file is imported from app/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ---------------------------------------------------------------------------
# Demo dataset definition
# ---------------------------------------------------------------------------
#
# 14 weekdays x 3 work apps + 14 days x spotify = 56 rows total.
# Every timestamp is a real past datetime so detect_habits()'s
# WHERE timestamp > datetime('now', '-14 days') filter passes.
# 10+ rows per app/hour slot exceeds the HAVING frequency >= 5 threshold.

_DEMO_APPS = [
    # (app_name, window_title, days_back_start, days_back_end, hour, weekdays_only)
    ("Cursor.exe", "Cursor - HoloDesk", 1, 14, 21, True),
    ("brave.exe", "New Tab - Brave", 1, 14, 9, True),
    ("Code.exe", "Visual Studio Code", 1, 14, 14, True),
    ("spotify.exe", "Spotify", 1, 14, 18, False),
]


def _insert_demo_data() -> None:
    """
    Insert fake app_events and a completed session if the DB looks empty.
    Guard: skips insertion if app_events already has > 100 rows.
    """
    from storage.db import db

    # Guard - don't double-insert
    count_row = db.query_one("SELECT COUNT(*) AS cnt FROM app_events")
    existing = count_row["cnt"] if count_row else 0
    if existing > 100:
        logger.info("[Startup] Demo data already present (%d rows) - skipping", existing)
        return

    logger.info("[Startup] Inserting demo data...")

    # Create one completed fake session so get_unfinished_context() has context
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    two_days_ago_end = (datetime.now() - timedelta(days=2, hours=-2)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    db.execute(
        "INSERT INTO sessions (start_time, end_time, total_duration_minutes) "
        "VALUES (?, ?, ?)",
        (two_days_ago, two_days_ago_end, 120),
    )
    session_row = db.query_one("SELECT last_insert_rowid() AS id")
    fake_session_id = session_row["id"] if session_row else None

    rows_inserted = 0
    now = datetime.now()

    for app_name, window_title, days_start, days_end, hour, weekdays_only in _DEMO_APPS:
        for days_back in range(days_start, days_end + 1):
            event_dt = now - timedelta(days=days_back)
            event_dt = event_dt.replace(hour=hour, minute=0, second=0, microsecond=0)

            if weekdays_only and event_dt.weekday() >= 5:
                continue  # Skip weekends for work apps

            timestamp_str = event_dt.strftime("%Y-%m-%d %H:%M:%S")
            db.insert(
                "app_events",
                {
                    "session_id": fake_session_id,
                    "app_name": app_name,
                    "window_title": window_title,
                    "timestamp": timestamp_str,
                    "day_of_week": event_dt.weekday(),
                    "hour_of_day": hour,
                },
            )
            rows_inserted += 1

    logger.info("[Startup] Demo data ready - %d rows inserted", rows_inserted)


def _wake_keypress_callback() -> bool:
    """Emit a synthetic SPACE key press so main.py reuses request_wake()."""
    try:
        import pygame
    except Exception:
        return False

    try:
        if not pygame.get_init():
            return False
        ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        pygame.event.post(ev)
        logger.info("[WAKE] Posted synthetic SPACE key event.")
        return True
    except Exception as exc:
        logger.warning("[WAKE] Could not post wake event: %s", exc)
        return False


def _start_optional_wake_word_listener() -> None:
    """Boot optional wake-word listener. Safe no-op if disabled/missing deps."""
    try:
        from agents.wake_word_agent import launch_wake_word_listener

        launch_wake_word_listener(_wake_keypress_callback)
    except Exception as exc:
        logger.warning("[WAKE] Wake-word listener unavailable: %s", exc)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def on_startup(demo_mode: bool = False) -> None:
    """
    Called once before pygame.init().

    Generates a morning briefing and stores it in preferences so the overlay
    can speak it on the first rendered frame.

    Args:
        demo_mode: If True, seed demo data first and skip the Day 1 check.
    """
    try:
        if demo_mode:
            _insert_demo_data()

        logger.info("[Startup] Calling morning briefing generator...")
        from agents.morning_briefing import generate_briefing

        briefing = generate_briefing(demo_mode=demo_mode)
        logger.info("[Startup] Briefing ready: %s", briefing[:80])

        from storage.db import db

        db.set_pref("pending_briefing", briefing)

        _start_optional_wake_word_listener()

    except Exception as e:
        logger.error("[Startup] Startup failed (non-fatal): %s", e)
        # Don't re-raise - overlay must still launch even if briefing fails
