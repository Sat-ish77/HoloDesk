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
    if not result["success"]:
        return result
    # A typed name is not an address: pick Gmail's contact suggestion so a chip forms.
    try:
        page.get_by_role("option").first.wait_for(state="visible", timeout=5000)
    except Exception:
        return {"success": False, "error": f"Gmail suggested no contact for '{recipient}'."}
    page.keyboard.press("Enter")
    page.wait_for_timeout(500)
    # UNVERIFIED selector: recipient chips carry an email attribute in current Gmail.
    if not page.locator("[email]").count():
        return {"success": False, "error": f"No recipient chip formed for '{recipient}'."}
    return {"success": True, "error": None}


# Live test: get_by_label("Subject") resolved to an inbox row (its aria label
# holds the thread's subject), so compose looked open when it wasn't. These
# name the compose window's own fields.
SUBJECT = 'input[name="subjectbox"]'
BODY = 'div[role="textbox"][aria-label="Message Body"]'


def compose_open(page) -> bool:
    try:
        return page.locator(SUBJECT).first.is_visible()
    except Exception:
        return False


def _fill(page, selector: str, text: str) -> dict[str, Any]:
    try:
        page.locator(selector).first.fill(text, timeout=8000)
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e).splitlines()[0][:120]}"}


def fill_subject(page, subject: str) -> dict[str, Any]:
    return _fill(page, SUBJECT, subject)


def fill_message(page, body: str) -> dict[str, Any]:
    result = _fill(page, BODY, body)
    if not result["success"]:
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
