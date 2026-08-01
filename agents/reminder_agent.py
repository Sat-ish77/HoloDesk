"""Reminder agent for HoloDesk.

Stores simple natural-language reminders in SQLite and reports pending/due
items. This is intentionally conservative: reminders are persisted, but the
app only speaks them at startup/on request until a stronger scheduler exists.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from storage.db import db


try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except Exception:
    dateparser = None
    DATEPARSER_AVAILABLE = False


class ReminderAgent:
    def execute(self, action: str, context: dict | None = None) -> dict:
        ctx = context or {}
        raw = ctx.get("raw", "") or ""
        if action == "set_reminder":
            return self.set_reminder(raw)
        if action in {"list_reminders", "due_reminders"}:
            return self.describe_pending(raw)
        return {"success": False, "response": "I do not know that reminder action yet."}

    def set_reminder(self, raw: str) -> dict:
        title = self._extract_title(raw)
        due_at = self._extract_due_at(raw)
        if due_at is None:
            return {"success": False, "response": "When should I remind you?"}
        if not title:
            title = "Reminder"

        db.insert(
            "reminders",
            {
                "title": title[:300],
                "due_at": due_at.isoformat(timespec="seconds"),
                "status": "pending",
                "source_text": raw[:500],
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        return {
            "success": True,
            "response": f"Okay. I will remind you {self._format_due(due_at)}: {title}.",
        }

    def describe_pending(self, raw: str = "") -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        rows = db.query(
            """
            SELECT id, title, due_at
            FROM reminders
            WHERE status = 'pending'
            ORDER BY due_at ASC
            LIMIT 8
            """
        )
        if not rows:
            return {"success": True, "response": "You do not have pending reminders."}

        due = [r for r in rows if r["due_at"] <= now]
        upcoming = due or rows[:5]
        prefix = "Due now: " if due else "Upcoming reminders: "
        parts = []
        for row in upcoming:
            try:
                due_dt = datetime.fromisoformat(row["due_at"])
                when = self._format_due(due_dt)
            except Exception:
                when = row["due_at"]
            parts.append(f"{row['title']} ({when})")
        return {"success": True, "response": prefix + "; ".join(parts) + "."}

    @staticmethod
    def _extract_title(raw: str) -> str:
        text = (raw or "").strip()
        lowered = text.lower()
        for marker in ("remind me to", "remind me", "set a reminder to", "set reminder to"):
            idx = lowered.find(marker)
            if idx >= 0:
                text = text[idx + len(marker):].strip(" .,:;")
                break
        text = re.split(r"\b(tomorrow|today|tonight|at|on|in \d+|next)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
        return text.strip(" .,:;") or (raw or "").strip(" .,:;")

    @staticmethod
    def _extract_due_at(raw: str) -> datetime | None:
        text = raw or ""
        if DATEPARSER_AVAILABLE:
            parsed = dateparser.parse(
                text,
                settings={
                    "PREFER_DATES_FROM": "future",
                    "RELATIVE_BASE": datetime.now(),
                },
            )
            if parsed:
                return parsed

        lowered = text.lower()
        m = re.search(r"\bin\s+(\d+)\s+(minute|minutes|hour|hours|day|days)\b", lowered)
        if m:
            amount = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("minute"):
                return datetime.now() + timedelta(minutes=amount)
            if unit.startswith("hour"):
                return datetime.now() + timedelta(hours=amount)
            return datetime.now() + timedelta(days=amount)

        if "tomorrow" in lowered:
            base = datetime.now() + timedelta(days=1)
            hm = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
            if hm:
                hour = int(hm.group(1))
                minute = int(hm.group(2) or 0)
                suffix = hm.group(3)
                if suffix == "pm" and hour < 12:
                    hour += 12
                if suffix == "am" and hour == 12:
                    hour = 0
                return base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return base.replace(hour=9, minute=0, second=0, microsecond=0)

        return None

    @staticmethod
    def _format_due(due_at: datetime) -> str:
        return due_at.strftime("on %b %d at %I:%M %p").replace(" 0", " ")
