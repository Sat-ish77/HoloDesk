"""
MemoryAgent — Passive session logging and habit detection.

What this does:
  1. On session start: creates a session row, sets session_id
  2. Every 60 seconds (background thread): logs the currently active window
  3. On session end: closes the session with duration
  4. On demand: runs SQL queries to detect habits and unfinished work

This module is safe to import and run NOW — it writes to data/holodesk.db
and starts accumulating the 14 days of data needed for the morning briefing
to be genuinely personalized. Start it today.

Windows-only: uses win32gui + win32process to read the active window title.
psutil reads the process name from the PID.
"""

import threading
import logging
import json
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Windows API — gracefully disabled if not available
try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    logger.warning("pywin32 not installed — window title logging disabled")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not installed — process name logging disabled")

from storage.db import db


# Window titles containing these strings are NEVER logged.
# Privacy is not optional.
BLOCKED_TITLE_KEYWORDS = [
    "1password", "lastpass", "bitwarden", "dashlane",
    "banking", "chase", "wells fargo", "bank of america",
    "private -", "incognito",
    "social security", "tax return", "payroll",
    "password manager",
]


def _is_blocked(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in BLOCKED_TITLE_KEYWORDS)


def _get_active_window() -> tuple[str, str]:
    """
    Return (app_name, window_title) for the currently focused window.
    Returns ("unknown", "") if win32 or psutil are unavailable.
    """
    if not WIN32_AVAILABLE:
        return "unknown", ""

    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""

        if _is_blocked(title):
            return "", ""  # Empty string signals: skip this log entry

        if PSUTIL_AVAILABLE:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                app_name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                app_name = "unknown"
        else:
            app_name = "unknown"

        return app_name, title

    except Exception as e:
        logger.debug("Could not read active window: %s", e)
        return "unknown", ""


class MemoryAgent:
    """
    Passive logger + habit detector.
    One instance is shared across the application (imported from here).
    """

    LOG_INTERVAL_SECONDS = 60  # How often to log the active window

    def __init__(self):
        self.session_id: int | None = None
        self._stop_event = threading.Event()
        self._logger_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_session(self, user_id: int = 1) -> int:
        """
        Create a new session row and return its id.
        Call this once when HoloDesk launches.
        """
        # Ensure a default user exists (for solo use)
        existing = db.query_one("SELECT id FROM users WHERE id = ?", (user_id,))
        if not existing:
            user_id = db.insert("users", {
                "name": "default",
                "created_at": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            })

        self.session_id = db.insert("sessions", {
            "user_id": user_id,
            "start_time": datetime.now().isoformat(),
        })
        logger.info("Session started: id=%d", self.session_id)
        return self.session_id

    def end_session(self):
        """Close the current session. Call this on HoloDesk exit."""
        if self.session_id is None:
            return
        closing_session_id = self.session_id
        start_row = db.query_one(
            "SELECT start_time FROM sessions WHERE id = ?", (self.session_id,)
        )
        if start_row:
            start = datetime.fromisoformat(start_row["start_time"])
            duration = int((datetime.now() - start).total_seconds() / 60)
            db.update(
                "sessions",
                {"end_time": datetime.now().isoformat(), "total_duration_minutes": duration},
                "id = ?",
                (self.session_id,),
            )
        try:
            self.write_session_summary(closing_session_id)
        except Exception as exc:
            logger.debug("Could not write session summary: %s", exc)
        logger.info("Session ended: id=%d", self.session_id)
        self.session_id = None

    # ------------------------------------------------------------------
    # Background logging thread
    # ------------------------------------------------------------------

    def start_background_logging(self):
        """
        Start the 60-second background logger thread.
        Safe to call multiple times — only starts one thread.
        """
        if self._logger_thread and self._logger_thread.is_alive():
            return

        self._stop_event.clear()
        self._logger_thread = threading.Thread(
            target=self._logging_loop,
            name="MemoryLogger",
            daemon=True,  # Dies automatically when main thread exits
        )
        self._logger_thread.start()
        logger.info("Background memory logger started (every %ds)", self.LOG_INTERVAL_SECONDS)

    def stop_background_logging(self):
        """Signal the logger thread to stop gracefully."""
        self._stop_event.set()

    def _logging_loop(self):
        """
        Runs on the background thread.
        Logs the active window every LOG_INTERVAL_SECONDS seconds.
        Low priority — never blocks the UI.
        """
        while not self._stop_event.is_set():
            try:
                self.log_app_event()
            except Exception as e:
                logger.debug("Memory logger error (non-fatal): %s", e)

            # Sleep in 1-second chunks so we can respond to stop_event quickly
            for _ in range(self.LOG_INTERVAL_SECONDS):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def log_app_event(self):
        """
        Write one row to app_events for the currently active window.
        Called by _logging_loop every 60 seconds.
        Can also be called manually.
        """
        if self.session_id is None:
            return

        app_name, window_title = _get_active_window()

        # Empty string means the window was blocked — skip silently
        if not app_name:
            return

        now = datetime.now()
        db.insert("app_events", {
            "session_id": self.session_id,
            "app_name": app_name,
            "window_title": window_title[:200],  # Truncate long titles
            "timestamp": now.isoformat(),
            "day_of_week": now.weekday(),   # 0=Monday, 6=Sunday
            "hour_of_day": now.hour,        # 0-23
        })
        logger.debug("Logged: [%s] %s", app_name, window_title[:60])

    # ------------------------------------------------------------------
    # Habit detection (pure SQL — no ML)
    # ------------------------------------------------------------------

    def detect_habits(self) -> list[dict]:
        """
        Find apps that appear consistently at the same hour on the same weekday.
        Requires frequency >= 5 over the last 14 days to be considered a habit.
        Returns top 20 habits ordered by frequency.
        """
        return db.query("""
            SELECT
                app_name,
                hour_of_day,
                day_of_week,
                COUNT(*) AS frequency
            FROM app_events
            WHERE timestamp > datetime('now', '-14 days')
            GROUP BY app_name, hour_of_day, day_of_week
            HAVING frequency >= 5
            ORDER BY frequency DESC
            LIMIT 20
        """)

    def get_unfinished_context(self) -> list[dict]:
        """
        What was the user working on at the end of the PREVIOUS session?
        Returns the last 5 app events from the second-most-recent session.
        Used to generate the "you left X open yesterday" morning briefing.
        """
        return db.query("""
            SELECT app_name, window_title, timestamp
            FROM app_events
            WHERE session_id = (
                SELECT id FROM sessions
                WHERE end_time IS NOT NULL
                ORDER BY start_time DESC
                LIMIT 1
            )
            ORDER BY timestamp DESC
            LIMIT 5
        """)

    def get_todays_app_summary(self) -> list[dict]:
        """
        Which apps have been used today, and for how long (in 60-second slots)?
        Useful for mid-day status display.
        """
        return db.query("""
            SELECT
                app_name,
                COUNT(*) AS minutes_approx
            FROM app_events
            WHERE date(timestamp) = date('now')
            AND session_id = (
                SELECT id FROM sessions ORDER BY start_time DESC LIMIT 1
            )
            GROUP BY app_name
            ORDER BY minutes_approx DESC
            LIMIT 10
        """)

    def get_days_active(self) -> int:
        """How many distinct calendar days has HoloDesk been running?"""
        result = db.query_one(
            "SELECT COUNT(DISTINCT date(start_time)) AS days FROM sessions"
        )
        return result["days"] if result else 0

    def generate_morning_context(self) -> dict:
        """
        Aggregate all context needed to generate the morning briefing.
        Called by startup.py in parallel with CalendarAgent.
        """
        return {
            "habits": self.detect_habits(),
            "unfinished_work": self.get_unfinished_context(),
            "todays_apps": self.get_todays_app_summary(),
            "days_active": self.get_days_active(),
        }

    def log_voice_command(self, command_text: str, response_summary: str = "",
                          agent_used: str = "chat_agent"):
        """
        Persist a voice command to the database.
        Call this from main.py whenever a command is processed.
        """
        if self.session_id is None:
            return
        db.insert("voice_commands", {
            "session_id": self.session_id,
            "command_text": command_text[:500],
            "response_summary": response_summary[:200],
            "agent_used": agent_used,
            "timestamp": datetime.now().isoformat(),
        })

    def get_recent_voice_commands(self, limit: int = 10) -> list[dict]:
        return db.query(
            """
            SELECT command_text, response_summary, agent_used, timestamp
            FROM voice_commands
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (int(limit),),
        )

    def format_today_summary(self) -> str:
        apps = self.get_todays_app_summary()
        commands = self.get_recent_voice_commands(limit=5)

        if not apps and not commands:
            return "I do not have much logged for today yet."

        parts = []
        if apps:
            top_apps = ", ".join(f"{a['app_name']} about {a['minutes_approx']} min" for a in apps[:5])
            parts.append(f"Top apps today: {top_apps}.")
        if commands:
            top_commands = "; ".join(c["command_text"] for c in reversed(commands[-3:]))
            parts.append(f"Recent commands: {top_commands}.")
        return " ".join(parts)

    def write_session_summary(self, session_id: int | None = None) -> Path:
        sid = session_id or self.session_id
        now = datetime.now()
        out_dir = Path("data") / "memory" / now.strftime("%Y") / now.strftime("%m")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{now.strftime('%Y-%m-%d')}.md"

        apps = db.query(
            """
            SELECT app_name, COUNT(*) AS minutes_approx
            FROM app_events
            WHERE session_id = ?
            GROUP BY app_name
            ORDER BY minutes_approx DESC
            LIMIT 10
            """,
            (sid,),
        ) if sid is not None else []
        commands = db.query(
            """
            SELECT command_text, response_summary, agent_used, timestamp
            FROM voice_commands
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT 50
            """,
            (sid,),
        ) if sid is not None else []

        lines = [
            f"# HoloDesk Session - {now.strftime('%Y-%m-%d')}",
            "",
            f"- Session id: {sid}",
            f"- Updated: {now.isoformat(timespec='seconds')}",
            "",
            "## Apps",
        ]
        if apps:
            lines.extend(f"- {row['app_name']}: about {row['minutes_approx']} min" for row in apps)
        else:
            lines.append("- No app activity logged.")

        lines.extend(["", "## Voice Commands"])
        if commands:
            for row in commands:
                response = row.get("response_summary") or ""
                lines.append(f"- {row['timestamp']}: {row['command_text']} -> {response[:120]}")
        else:
            lines.append("- No voice commands logged.")

        with open(out_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n\n")
        return out_path

    def format_habits_for_prompt(self) -> str:
        """
        Convert habit data to a short human-readable string for LLM prompts.
        Example: "You usually use VS Code at 9am on weekdays. Chrome is heavy at 2pm."
        """
        habits = self.detect_habits()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        lines = []
        for h in habits[:5]:  # Top 5 only to keep prompt short
            day = days[h["day_of_week"]] if 0 <= h["day_of_week"] <= 6 else "weekdays"
            hour = h["hour_of_day"]
            period = "am" if hour < 12 else "pm"
            display_hour = hour if hour <= 12 else hour - 12
            lines.append(
                f"{h['app_name']} at {display_hour}{period} on {day} "
                f"(seen {h['frequency']} times)"
            )
        return "; ".join(lines) if lines else "No habits detected yet — need more sessions."

    def format_unfinished_for_prompt(self) -> str:
        """
        Format last-session context for the morning briefing LLM prompt.
        Example: "Last session: VS Code (main.py), Chrome (Stack Overflow)"
        """
        context = self.get_unfinished_context()
        if not context:
            return "No previous session data."
        parts = []
        seen_apps = set()
        for row in context:
            app = row["app_name"]
            title = row["window_title"] or ""
            if app not in seen_apps:
                seen_apps.add(app)
                parts.append(f"{app} ({title[:40]})" if title else app)
        return "Last session: " + ", ".join(parts)


# Module-level singleton — import this everywhere
memory_agent = MemoryAgent()
