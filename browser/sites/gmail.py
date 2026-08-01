"""Gmail adapter for browser/playwright_controller.py.

Selectors are best-effort, based on Gmail's current accessible roles/labels
(Compose button, To/Subject/Message Body fields, Send button). Gmail's DOM
changes over time — if these stop matching, this is the only file that needs
updating; nothing else in HoloDesk depends on Gmail's internal structure.

Every function returns a plain dict ({"success": bool, ...}) and never
raises, matching the rest of the automation layer's contract.
"""

from __future__ import annotations

from typing import Any

from browser import playwright_controller as pw

GMAIL_URL = "https://mail.google.com/mail/u/0/#inbox"


def open_inbox(page) -> dict[str, Any]:
    return pw.open_url(page, GMAIL_URL)


def compose(page) -> dict[str, Any]:
    result = pw.click(page, role="button", name="Compose", timeout_ms=15000)
    if not result["success"]:
        return result
    # Wait for the compose window's To field to confirm it actually opened.
    if not pw.is_visible(page, label="To"):
        page.wait_for_timeout(1000)
    return result


def fill_recipient(page, recipient: str) -> dict[str, Any]:
    result = pw.type_into(page, recipient, label="To")
    if not result["success"]:
        result = pw.type_into(page, recipient, role="combobox", name="To")
    return result


def fill_subject(page, subject: str) -> dict[str, Any]:
    return pw.type_into(page, subject, label="Subject")


def fill_message(page, body: str) -> dict[str, Any]:
    result = pw.type_into(page, body, label="Message Body")
    if not result["success"]:
        result = pw.type_into(page, body, role="textbox", name="Message Body")
    return result


def is_draft_ready(page) -> bool:
    body = pw.read_text(page, label="Message Body")
    has_body = bool(body.get("text") and body["text"].strip())
    has_send = pw.is_visible(page, role="button", name="Send")
    return has_body and has_send


def click_send(page) -> dict[str, Any]:
    return pw.click(page, role="button", name="Send")
