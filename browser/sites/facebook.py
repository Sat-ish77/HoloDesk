"""Facebook Messenger adapter for browser/playwright_controller.py.

Selectors are best-effort based on Messenger's current UI (search box,
conversation rows, message composer, send button). Messenger's composer
famously uses "Aa" as its placeholder text — that's not a typo here.

If no explicit Send button is found (Messenger sometimes hides it until you
type), we fall back to pressing Enter in the composer, which is Messenger's
default send shortcut. Every function returns a plain dict and never raises.
"""

from __future__ import annotations

from typing import Any

from browser import playwright_controller as pw

MESSENGER_URL = "https://www.messenger.com/"
COMPOSER_PLACEHOLDER = "Aa"


def open_messenger(page) -> dict[str, Any]:
    return pw.open_url(page, MESSENGER_URL)


def find_contact(page, name: str) -> dict[str, Any]:
    search = pw.type_into(page, name, placeholder="Search Messenger")
    if not search["success"]:
        search = pw.type_into(page, name, role="combobox", name="Search Messenger")
    if not search["success"]:
        return search

    page.wait_for_timeout(800)
    return pw.click(page, text=name, timeout_ms=8000)


def compose(page, subject: str | None = None) -> dict[str, Any]:
    # No separate "compose" step in Messenger — selecting a contact opens
    # the thread directly. Kept for adapter-shape parity with gmail.py.
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
