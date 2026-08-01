"""Instagram Direct Messages adapter for browser/playwright_controller.py.

Same shape as browser/sites/facebook.py (Instagram DMs share Meta's messaging
stack). Selectors are best-effort based on Instagram's current DM UI and are
the most likely of the three site adapters to need tuning — Instagram's web
UI churns faster and has tighter automation detection than Gmail/Messenger,
so this is intentionally the lowest-priority/last-validated adapter.

Every function returns a plain dict and never raises.
"""

from __future__ import annotations

from typing import Any

from browser import playwright_controller as pw

INSTAGRAM_DM_URL = "https://www.instagram.com/direct/inbox/"
COMPOSER_PLACEHOLDER = "Message..."


def open_inbox(page) -> dict[str, Any]:
    return pw.open_url(page, INSTAGRAM_DM_URL)


def find_contact(page, name: str) -> dict[str, Any]:
    search = pw.type_into(page, name, placeholder="Search")
    if not search["success"]:
        return search

    page.wait_for_timeout(800)
    return pw.click(page, text=name, timeout_ms=8000)


def compose(page, subject: str | None = None) -> dict[str, Any]:
    # No separate "compose" step — selecting a contact opens the thread
    # directly. Kept for adapter-shape parity with gmail.py/facebook.py.
    return {"success": True, "error": None}


def fill_message(page, body: str) -> dict[str, Any]:
    return pw.type_into(page, body, placeholder=COMPOSER_PLACEHOLDER)


def is_draft_ready(page) -> bool:
    return pw.is_visible(page, placeholder=COMPOSER_PLACEHOLDER)


def click_send(page) -> dict[str, Any]:
    result = pw.click(page, role="button", name="Send")
    if result["success"]:
        return result
    return pw.press_key(page, "Enter", placeholder=COMPOSER_PLACEHOLDER)
