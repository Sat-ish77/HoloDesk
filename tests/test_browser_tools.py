"""Browser tools with Playwright mocked: a FakePage stands in for the Chrome
tab, so these check the tools' decisions and observations, not real sites."""

import pytest

from brain.policy import Risk
from brain.tools import browser as bt
from brain.tools import build_default_registry
from brain.tools.registry import ToolContext, ToolError
from browser import playwright_controller as pw
from helpers import call, make_engine, say

CTX = ToolContext()
BODY = ("label", "Message Body")
REPLY = ("role", "button", "Reply")
SEND = ("role", "button", "Send")
YOUTUBE = "https://www.youtube.com/results?search_query=x"


class FakeLocator:
    def __init__(self, page, key, items):
        self.page, self.key, self.items = page, key, items

    @property
    def first(self):
        return self.nth(0)

    def nth(self, i):
        return FakeLocator(self.page, self.key, self.items[i:i + 1])

    def count(self):
        return len(self.items)

    def _item(self):
        if not self.items:
            raise TimeoutError(f"no element for {self.key}")
        return self.items[0]

    def inner_text(self, timeout=None):
        return self._item().get("text", "")

    def is_visible(self):
        return bool(self.items)

    def bounding_box(self):
        return {"x": 0, "y": self._item().get("y", 100), "width": 10, "height": 10}

    def click(self, timeout=None):
        item = self._item()
        self.page.clicks.append(item.get("text") or self.key)
        self.page.on_click(self.key, item)

    def fill(self, text, timeout=None):
        self._item()["text"] = text

    def input_value(self):
        return self._item().get("text", "")

    def get_attribute(self, name):
        return self._item().get(name)


class FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def type(self, text):
        self.page.typed.append(text)

    def press(self, key):
        self.page.keys.append(key)
        if key == "k" and self.page.k_works:
            self.page.paused = not self.page.paused


class FakeContext:
    def __init__(self, first):
        self.pages = [first]

    def new_page(self):
        page = FakePage("about:blank")
        page.context = self
        self.pages.append(page)
        return page


class FakePage:
    def __init__(self, url=YOUTUBE, elements=None):
        if isinstance(url, dict):                       # FakePage({...}) = a YouTube page
            url, elements = YOUTUBE, url
        self.url, self.elements = url, dict(elements or {})
        self.clicks, self.keys, self.typed, self.history = [], [], [], []
        self.context, self.closed, self.visible, self.focus_is_password = FakeContext(self), False, True, False
        self.paused, self.k_works, self.body = None, True, "Hello page"
        self.keyboard = FakeKeyboard(self)
        self.on_click = lambda key, item: None

    def title(self):
        return "Fake title"

    def locator(self, selector):
        return FakeLocator(self, selector, self.elements.get(selector, []))

    def get_by_role(self, role, name=None, **_):
        return self.locator(("role", role, name))

    def get_by_label(self, label):
        return self.locator(("label", label))

    def get_by_text(self, text):
        return self.locator(("text", text))

    def get_by_placeholder(self, text):
        return self.locator(("placeholder", text))

    def goto(self, url, **_):
        self.history.append(self.url)
        self.url = url

    def go_back(self, **_):
        if self.history:
            self.url = self.history.pop()

    def close(self):
        self.closed = True
        self.context.pages.remove(self)

    def is_closed(self):
        return self.closed

    def bring_to_front(self):
        for other in self.context.pages:
            other.visible = other is self

    def evaluate(self, js, *args):
        if "visibilityState" in js:
            return "visible" if self.visible else "hidden"
        if "activeElement" in js:
            return self.focus_is_password
        if "innerHeight" in js:
            return 800
        if "v.play()" in js:
            if self.paused is not None:
                self.paused = not self.paused
            return self.paused
        if "v.paused" in js:
            return self.paused
        if "innerText" in js:
            return self.body
        return []

    def wait_for_timeout(self, ms):
        pass

    def wait_for_load_state(self, state, timeout=None):
        pass


@pytest.fixture()
def tab(monkeypatch):
    """Point the tools at a FakePage instead of a real Chrome tab."""
    holder = {"page": FakePage()}

    def with_page(fn, *args, **kwargs):
        page = holder["page"]
        result = fn(page, *args, **kwargs)
        result.setdefault("url", page.url)
        result.setdefault("title", page.title())
        return result
    monkeypatch.setattr(pw, "with_page", with_page)
    monkeypatch.setattr(pw.controller, "_page", None)      # close_tab / new_tab move it
    return holder


def videos(*titles):
    return {"ytd-video-renderer a#video-title": [{"text": t} for t in titles]}


def gmail_page(elements=None):
    return FakePage("https://mail.google.com/mail/u/0/#inbox/abc", elements)


# ---------------------------------------------------------------- catalogue
def test_tools_are_registered_with_the_right_risk():
    r = build_default_registry()
    assert r.get("browser_read_page").risk_for({}) == Risk.SAFE
    assert r.get("browser_open_result").risk_for({}) == Risk.ACT
    assert r.get("browser_play_pause").risk_for({}) == Risk.ACT
    assert r.get("gmail_draft_reply").risk_for({"body": "hi"}) == Risk.ACT
    assert r.get("click").risk_for({"ref": "e1"}) == Risk.ACT            # unknown ref: the handler refuses it
    assert r.get("gmail_send").risk_for({}) == Risk.DANGER


def test_brain_starts_without_playwright_and_reports_it(monkeypatch):
    monkeypatch.setattr(pw, "with_page", lambda fn: {
        "success": False, "response": "Couldn't connect to the automation browser: No module named 'playwright'"})
    out = bt.browser_read_page({}, CTX)
    assert out["ok"] is False and "pip install playwright" in out["error"]


def test_everything_is_off_until_enabled(monkeypatch):
    monkeypatch.delenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", raising=False)
    assert bt.open_in_automation("https://youtube.com") is None       # caller uses the normal browser
    out = bt.browser_read_page({}, CTX)
    assert out["ok"] is False and "HOLODESK_BROWSER_AUTOMATION_ENABLED" in out["error"]


# ---------------------------------------------------------------- open result
def test_open_result_clicks_the_nth_video_and_reports_it(tab):
    tab["page"] = FakePage(videos("Kapil Sharma Show ep 1", "Second video", "Third"))
    out = bt.browser_open_result({"position": 2}, CTX)
    assert out["ok"] and out["opened"] == "Second video" and tab["page"].clicks == ["Second video"]
    assert out["url"] and out["title"] == "Fake title"
    assert bt.browser_open_result({}, CTX)["opened"] == "Kapil Sharma Show ep 1"     # default: first


def test_open_result_says_when_there_are_too_few_or_none(tab):
    tab["page"] = FakePage(videos("only one"))
    out = bt.browser_open_result({"position": 3}, CTX)
    assert out["ok"] is False and "only 1" in out["error"] and tab["page"].clicks == []
    tab["page"] = FakePage("https://example.com/")
    assert "can't find a list" in bt.browser_open_result({}, CTX)["error"]
    with pytest.raises(ToolError):
        bt.browser_open_result({"position": "first"}, CTX)


def test_open_result_falls_back_to_generic_results_on_other_sites(tab):
    tab["page"] = FakePage("https://duckduckgo.com/?q=x", {"a:has(h3)": [{"text": "A"}, {"text": "B"}]})
    assert bt.browser_open_result({"position": 2}, CTX)["opened"] == "B"


# ---------------------------------------------------------------- click / read


def test_clicks_that_send_post_or_buy_need_confirmation():
    for text in ["Send", "Post", "Buy now", "Place order", "Delete", "Submit application", "पठाउनुहोस्"]:
        assert bt._click_risk({"text": text}) == Risk.DANGER, text
    for text in ["Videos", "Next", "Show more", "Home", "About"]:
        assert bt._click_risk({"text": text}) == Risk.ACT, text


def test_read_page_returns_text_and_marks_it_untrusted(tab):
    tab["page"].body = "Line one\n\n  Line two  \n" + "x" * 5000
    out = bt.browser_read_page({"max_chars": 300}, CTX)
    assert out["ok"] and out["text"].startswith("Line one\nLine two") and len(out["text"]) == 300
    assert out["title"] == "Fake title" and "untrusted" in out["note"]


# ---------------------------------------------------------------- play / pause
def test_play_pause_toggles_and_reports_the_real_state(tab):
    page = tab["page"]
    page.paused = False
    assert bt.browser_play_pause({}, CTX)["state"] == "paused" and page.keys == ["k"]
    assert bt.browser_play_pause({}, CTX)["state"] == "playing"


def test_play_pause_falls_back_when_the_key_does_nothing_and_off_youtube(tab):
    tab["page"].paused, tab["page"].k_works = True, False
    assert bt.browser_play_pause({}, CTX)["state"] == "playing"
    tab["page"] = FakePage("https://vimeo.com/1")
    tab["page"].paused = False
    out = bt.browser_play_pause({}, CTX)
    assert out["state"] == "paused" and tab["page"].keys == []
    tab["page"] = FakePage("https://example.com/")
    assert "no video" in bt.browser_play_pause({}, CTX)["error"]


# ---------------------------------------------------------------- like
# ---------------------------------------------------------------- gmail
def test_draft_reply_opens_reply_writes_and_does_not_send(tab):
    page = gmail_page({REPLY: [{"text": "Reply"}], SEND: [{"text": "Send"}]})

    def on_click(key, item):
        if key == REPLY:
            page.elements[BODY] = [{"text": ""}]
    page.on_click = on_click
    tab["page"] = page
    out = bt.gmail_draft_reply({"body": "I'll be there."}, CTX)
    assert out["ok"] and out["draft"] == "I'll be there." and out["sent"] is False
    assert "Send" not in page.clicks


def test_draft_reply_needs_gmail_and_an_open_email(tab):
    tab["page"] = FakePage("https://www.youtube.com/")
    assert "Gmail isn't the open tab" in bt.gmail_draft_reply({"body": "hi"}, CTX)["error"]
    tab["page"] = gmail_page()
    assert "Open the email first" in bt.gmail_draft_reply({"body": "hi"}, CTX)["error"]
    with pytest.raises(ToolError):
        bt.gmail_draft_reply({"body": " "}, CTX)


def sendable_page(confirms=True):
    page = gmail_page({BODY: [{"text": "I'll be there."}], SEND: [{"text": "Send"}]})

    def on_click(key, item):
        if key == SEND and confirms:
            page.elements[("text", "Message sent")] = [{"text": "Message sent"}]
    page.on_click = on_click
    return page


def test_send_reports_sent_only_when_gmail_confirms(tab):
    tab["page"] = sendable_page()
    assert bt.gmail_send({}, CTX)["sent"] is True
    tab["page"] = sendable_page(confirms=False)
    out = bt.gmail_send({}, CTX)
    assert out["ok"] is False and out["sent"] is False and "didn't confirm" in out["error"]
    tab["page"] = gmail_page({SEND: [{"text": "Send"}]})                # no draft text
    out = bt.gmail_send({}, CTX)
    assert out["ok"] is False and tab["page"].clicks == []


def test_send_shows_the_draft_and_waits_for_yes(tab):
    tab["page"] = sendable_page()
    engine, _, _ = make_engine([call("gmail_send")], extra_tools=bt.build())
    asked = engine.reply("send it")
    assert asked.needs_confirmation and "I'll be there." in asked.text
    assert tab["page"].clicks == []
    engine.reply("cancel")
    assert tab["page"].clicks == []
    engine.backend.script = [call("gmail_send"), say("unused")]
    engine.reply("send it")
    assert engine.reply("yes").ok and tab["page"].clicks == ["Send"]


# ---------------------------------------------------------------- routing
def test_sites_and_searches_open_in_the_automation_tab_when_enabled(monkeypatch):
    opened = []
    monkeypatch.setenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", "1")
    monkeypatch.setattr(pw, "open_in_automation_browser", lambda url: opened.append(url) or {
        "success": True, "url": url, "title": "T"})
    monkeypatch.setattr("webbrowser.open", lambda url: pytest.fail("used the normal browser"))
    r = build_default_registry()
    out = r.get("search_in_browser").handler({"query": "Kapil Sharma", "engine": "youtube"}, CTX)
    assert out["ok"] and "browser_open_result" in out["message"]
    r.get("open_website").handler({"target": "facebook"}, CTX)
    assert opened == ["https://www.youtube.com/results?search_query=Kapil+Sharma", "https://www.facebook.com"]


def test_normal_browser_is_used_only_when_automation_is_off(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    monkeypatch.delenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", raising=False)
    build_default_registry().get("search_in_browser").handler({"query": "x"}, CTX)
    assert opened == ["https://www.google.com/search?q=x"]


def test_a_failed_open_is_an_error_and_never_a_second_chrome(monkeypatch):
    # Round-2 voice test: the silent fallback put the page in the user's normal
    # Chrome, where browser_open_result and browser_click_text could not see it.
    monkeypatch.setenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", "1")
    monkeypatch.setattr("webbrowser.open", lambda url: pytest.fail("fell back to the normal browser"))
    monkeypatch.setattr(pw, "open_in_automation_browser", lambda url: {"success": False, "response": "Chrome not found on this PC."})
    r = build_default_registry()
    for tool, args in (("open_website", {"target": "github.com"}), ("search_in_browser", {"query": "x"})):
        out = r.get(tool).handler(args, CTX)
        assert out["ok"] is False and "Chrome not found" in out["error"] and "normal browser" in out["error"]

    def crash(url):
        raise RuntimeError("driver died")
    monkeypatch.setattr(pw, "open_in_automation_browser", crash)
    assert "driver died" in r.get("open_website").handler({"target": "github.com"}, CTX)["error"]


# ---------------------------------------------------------------- controller
class FakeBrowser:
    def __init__(self, page=None, dead=False):
        self.page, self.dead, self.closed = page, dead, False

    def is_connected(self):
        return True                      # a killed Chrome still reports connected for a while

    @property
    def contexts(self):
        if self.dead:
            raise RuntimeError("Target page, context or browser has been closed")
        return [self.page.context]

    def new_browser_cdp_session(self):
        if self.dead:
            raise RuntimeError("Target page, context or browser has been closed")
        return type("Session", (), {"send": lambda self, method: {}, "detach": lambda self: None})()

    def close(self):
        self.closed = True


def connected_controller(monkeypatch, browsers):
    launches = []
    monkeypatch.setenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", "1")
    monkeypatch.setattr(pw, "_debug_port_open", lambda port: True)
    monkeypatch.setattr(pw, "_launch_automation_chrome", lambda port: launches.append(port) or {"success": True, "error": None})

    class Chromium:
        def connect_over_cdp(self, url):
            return browsers.pop(0)

    class Driver:
        chromium = Chromium()

        def stop(self):
            pass

    class Api:
        def sync_playwright(self):
            return type("Starter", (), {"start": lambda self: Driver()})()
    monkeypatch.setattr(pw, "playwright_api", Api())
    return pw.PlaywrightController(), launches


def test_controller_rebuilds_a_dead_connection_instead_of_failing(monkeypatch):
    page = FakePage()
    dead = FakeBrowser(dead=True)
    controller, _ = connected_controller(monkeypatch, [dead, FakeBrowser(page)])
    got = controller.ensure_page()
    assert got["success"] and got["page"] is page and dead.closed


def test_controller_reports_an_error_when_chrome_cannot_come_back(monkeypatch):
    controller, _ = connected_controller(monkeypatch, [FakeBrowser(dead=True), FakeBrowser(dead=True)])
    got = controller.ensure_page()
    assert got["success"] is False and "Couldn't connect" in got["error"]


def test_chrome_is_launched_with_notification_prompts_off(monkeypatch):
    seen = []
    monkeypatch.setattr(pw, "_find_chrome_executable", lambda: "chrome.exe")
    monkeypatch.setattr(pw.subprocess, "Popen", lambda cmd: seen.extend(cmd))
    monkeypatch.setattr(pw, "_debug_port_open", lambda port: True)
    assert pw._launch_automation_chrome(9222)["success"] and "--disable-notifications" in seen


# ---------------------------------------------------------------- round-2 tools
def test_back_goes_back_and_says_when_it_cannot(tab):
    page = tab["page"]
    page.goto("https://www.youtube.com/watch?v=1")
    out = bt.browser_back({}, CTX)
    assert out["ok"] and out["url"] == YOUTUBE
    assert "no earlier page" in bt.browser_back({}, CTX)["error"]


def test_new_tab_opens_in_the_same_window_and_close_tab_returns_to_the_old_one(tab):
    first = tab["page"]
    out = bt.browser_new_tab({"target": "mail.google.com"}, CTX)
    assert out["ok"] and "mail.google.com" in out["url"] and len(first.context.pages) == 2
    gmail = first.context.pages[1]
    assert gmail.visible and not first.visible and pw.controller._page is gmail

    tab["page"] = gmail
    out = bt.browser_close_tab({}, CTX)
    assert out["ok"] and out["url"] == YOUTUBE and first.context.pages == [first]
    assert first.visible and pw.controller._page is first


def test_controller_keeps_its_tab_unless_chrome_is_sure_the_user_moved(monkeypatch):
    # Round-3 voice test: a still-loading new tab looked "hidden" and the tools
    # jumped back to the old one.
    first = FakePage("https://www.google.com/search?q=mcp")
    controller, _ = connected_controller(monkeypatch, [FakeBrowser(first)])
    assert controller.ensure_page()["page"] is first
    second = first.context.new_page()
    controller.use_tab(second)                       # HoloDesk opened it: follow it
    second.evaluate = lambda js, *a: (_ for _ in ()).throw(RuntimeError("navigating"))
    assert controller.ensure_page()["page"] is second        # unknown is not hidden
    del second.evaluate
    first.visible = second.visible = False                   # covered by the overlay
    assert controller.ensure_page()["page"] is second
    first.visible = True                                     # the user clearly switched back
    assert controller.ensure_page()["page"] is first
    third = first.context.new_page()
    first.visible, second.visible, third.visible = False, True, True      # two candidates: stay
    assert controller.ensure_page()["page"] is first
    first.close()
    assert controller.ensure_page()["page"] in (second, third)


def test_back_counts_as_done_when_the_page_changed_despite_a_timeout(tab):
    page = tab["page"]
    page.goto("https://www.youtube.com/watch?v=1")

    def slow_back(**_):
        page.url = page.history.pop()
        raise TimeoutError("Timeout 15000ms exceeded")
    page.go_back = slow_back
    out = bt.browser_back({}, CTX)
    assert out["ok"] and out["url"] == YOUTUBE


def test_the_separate_chrome_profile_is_explained_once(monkeypatch, tmp_path):
    monkeypatch.setenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", "1")
    monkeypatch.setenv("HOLODESK_BROWSER_PROFILE_DIR", str(tmp_path / "chrome-profile"))
    (tmp_path / "chrome-profile").mkdir()
    monkeypatch.setattr(pw, "open_in_automation_browser", lambda url: {"success": True, "url": url, "title": "T"})
    assert "own Chrome profile" in bt.open_in_automation("https://x.test")["message"]
    assert "own Chrome profile" not in bt.open_in_automation("https://x.test")["message"]


def test_controller_notices_a_killed_chrome_that_still_looks_connected(monkeypatch):
    # Found against a real Chrome: is_connected() stayed True after a kill and the
    # next open failed with "Target page, context or browser has been closed".
    old, new = FakePage(), FakePage("https://example.com/")
    first = FakeBrowser(old)
    controller, _ = connected_controller(monkeypatch, [first, FakeBrowser(new)])
    assert controller.ensure_page()["page"] is old
    first.dead = True
    got = controller.ensure_page()
    assert got["success"] and got["page"] is new
