"""Tests for the browser automation layer (browser/*) and its wiring into
agents/desktop_grounding_agent.py and agents/task_agent.py.

Everything here uses a FakePage/FakeLocator test double instead of a real
Playwright browser, matching the plan: the action primitives in
browser/playwright_controller.py operate on a `page` object passed in
directly, so they're trivially testable without launching Chrome.
"""

import os

import pytest

from browser import playwright_controller as pw
from browser.sites import facebook as site_facebook
from browser.sites import gmail as site_gmail
from browser.sites import instagram as site_instagram
from agents.desktop_grounding_agent import (
    ActionPlan,
    DesktopActionExecutor,
    _detect_browser_target,
)
from agents.task_agent import TaskAgent


class FakeLocator:
    def __init__(self, page, key, exists=True, text=""):
        self.page = page
        self.key = key
        self.exists = exists
        self.text = text

    @property
    def first(self):
        return self

    def click(self, timeout=None):
        if not self.exists:
            raise TimeoutError(f"no element for {self.key}")
        self.page.clicks.append(self.key)

    def fill(self, text, timeout=None):
        if not self.exists:
            raise TimeoutError(f"no element for {self.key}")
        self.page.filled[self.key] = text
        self.text = text

    def inner_text(self, timeout=None):
        if not self.exists:
            raise TimeoutError(f"no element for {self.key}")
        return self.text

    def is_visible(self):
        return self.exists

    def press(self, key, timeout=None):
        if not self.exists:
            raise TimeoutError(f"no element for {self.key}")
        self.page.presses.append((self.key, key))


class FakePage:
    def __init__(self, missing=None, texts=None):
        self.missing = set(missing or [])
        self.texts = dict(texts or {})
        self.urls = []
        self.clicks = []
        self.filled = {}
        self.presses = []
        self.screenshot_path = None

    def goto(self, url, wait_until=None, timeout=None):
        self.urls.append(url)

    def screenshot(self, path=None):
        self.screenshot_path = path

    def wait_for_timeout(self, ms):
        pass

    def _locator(self, key):
        return FakeLocator(self, key, exists=key not in self.missing, text=self.texts.get(key, ""))

    def get_by_role(self, role, name=None):
        return self._locator(("role", role, name))

    def get_by_label(self, label):
        return self._locator(("label", label))

    def get_by_placeholder(self, placeholder):
        return self._locator(("placeholder", placeholder))

    def get_by_text(self, text):
        return self._locator(("text", text))


# ---------------------------------------------------------------------------
# playwright_controller action primitives
# ---------------------------------------------------------------------------

def test_click_success_and_failure():
    page = FakePage()
    result = pw.click(page, role="button", name="Send")
    assert result["success"] is True
    assert ("role", "button", "Send") in page.clicks

    page2 = FakePage(missing={("role", "button", "Send")})
    result2 = pw.click(page2, role="button", name="Send")
    assert result2["success"] is False
    assert result2["error"]


def test_type_into_fills_field():
    page = FakePage()
    result = pw.type_into(page, "hello@example.com", label="To")
    assert result["success"] is True
    assert page.filled[("label", "To")] == "hello@example.com"


def test_read_text_returns_value():
    page = FakePage(texts={("label", "Message Body"): "hi there"})
    result = pw.read_text(page, label="Message Body")
    assert result["success"] is True
    assert result["text"] == "hi there"


def test_is_visible_true_and_false():
    page = FakePage(missing={("role", "button", "Send")})
    assert pw.is_visible(page, role="button", name="Compose") is True
    assert pw.is_visible(page, role="button", name="Send") is False


def test_screenshot_creates_parent_dir(tmp_path):
    page = FakePage()
    target = tmp_path / "nested" / "shot.png"
    result = pw.screenshot(page, str(target))
    assert result["success"] is True
    assert target.parent.is_dir()
    assert page.screenshot_path == str(target)


def test_open_url_navigates():
    page = FakePage()
    result = pw.open_url(page, "https://mail.google.com")
    assert result["success"] is True
    assert "https://mail.google.com" in page.urls


def test_ensure_page_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", raising=False)
    result = pw.PlaywrightController().ensure_page()
    assert result["success"] is False
    assert "disabled" in result["error"].lower()


# ---------------------------------------------------------------------------
# Site adapters
# ---------------------------------------------------------------------------

def test_gmail_is_draft_ready_true_when_body_and_send_present():
    page = FakePage(texts={("label", "Message Body"): "see you tomorrow"})
    assert site_gmail.is_draft_ready(page) is True


def test_gmail_is_draft_ready_false_when_send_missing():
    page = FakePage(
        texts={("label", "Message Body"): "see you tomorrow"},
        missing={("role", "button", "Send")},
    )
    assert site_gmail.is_draft_ready(page) is False


def test_gmail_click_send():
    page = FakePage()
    result = site_gmail.click_send(page)
    assert result["success"] is True
    assert ("role", "button", "Send") in page.clicks


def test_facebook_click_send_falls_back_to_enter_key():
    page = FakePage(missing={("role", "button", "Send")})
    result = site_facebook.click_send(page)
    assert result["success"] is True
    assert (("placeholder", "Aa"), "Enter") in page.presses


def test_instagram_find_contact_searches_then_clicks_name():
    page = FakePage()
    result = site_instagram.find_contact(page, "Satish Wagle")
    assert result["success"] is True
    assert page.filled[("placeholder", "Search")] == "Satish Wagle"
    assert ("text", "Satish Wagle") in page.clicks


# ---------------------------------------------------------------------------
# desktop_grounding_agent wiring
# ---------------------------------------------------------------------------

def test_detect_browser_target():
    assert _detect_browser_target("search Satish Wagle in gmail and draft an email") == "gmail"
    assert _detect_browser_target("message John on facebook") == "facebook"
    assert _detect_browser_target("dm someone on instagram") == "instagram"
    assert _detect_browser_target("open notepad") is None


def test_browser_send_flow_returns_none_when_disabled(monkeypatch):
    monkeypatch.delenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", raising=False)
    executor = DesktopActionExecutor(parser=None) if False else DesktopActionExecutor.__new__(DesktopActionExecutor)
    plan = ActionPlan(command="search Satish Wagle in gmail and draft an email saying hi", safe=True, blocked_reason=None, steps=[])
    assert executor._try_browser_send_flow(plan, "artifacts/ui_grounding") is None


def test_browser_send_flow_returns_none_for_unrelated_command(monkeypatch):
    monkeypatch.setenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", "1")
    executor = DesktopActionExecutor.__new__(DesktopActionExecutor)
    plan = ActionPlan(command="open notepad", safe=True, blocked_reason=None, steps=[])
    assert executor._try_browser_send_flow(plan, "artifacts/ui_grounding") is None


# ---------------------------------------------------------------------------
# task_agent confirm-gated send wiring
# ---------------------------------------------------------------------------

class StubGroundingAgent:
    def __init__(self, execute_result):
        self._execute_result = execute_result

    def plan(self, raw):
        return {"safe": True, "requires_confirmation": False}

    def execute(self, action, context):
        return self._execute_result


def test_grounded_desktop_action_sets_pending_confirm_for_browser_draft():
    execute_result = {
        "success": True,
        "response": "Gmail draft ready. Say 'yes' to send it, or 'cancel' to leave it as a draft.",
        "data": {"requires_confirmation": True, "browser_site": "gmail"},
    }
    agent = TaskAgent(desktop_grounding_agent=StubGroundingAgent(execute_result))

    result = agent.grounded_desktop_action("search Satish Wagle in gmail and draft an email saying hi")

    assert result["success"] is True
    assert agent._pending_confirm is not None
    assert agent._pending_confirm["kind"] == "send"


def test_confirm_yes_sends_via_browser(monkeypatch):
    execute_result = {
        "success": True,
        "response": "Gmail draft ready.",
        "data": {"requires_confirmation": True, "browser_site": "gmail"},
    }
    agent = TaskAgent(desktop_grounding_agent=StubGroundingAgent(execute_result))
    agent.grounded_desktop_action("search Satish Wagle in gmail and draft an email saying hi")

    fake_page = FakePage()
    monkeypatch.setattr(
        pw.controller, "ensure_page", lambda url=None: {"success": True, "page": fake_page, "error": None}
    )
    monkeypatch.setattr(site_gmail, "click_send", lambda page: {"success": True, "error": None})

    result = agent._confirm_yes()
    assert result["success"] is True
    assert result["response"] == "Sent."


def test_confirm_cancel_does_not_send():
    execute_result = {
        "success": True,
        "response": "Gmail draft ready.",
        "data": {"requires_confirmation": True, "browser_site": "gmail"},
    }
    agent = TaskAgent(desktop_grounding_agent=StubGroundingAgent(execute_result))
    agent.grounded_desktop_action("search Satish Wagle in gmail and draft an email saying hi")

    result = agent._confirm_cancel()
    assert result["success"] is True
    assert agent._pending_confirm is None
