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
LIKE, LIKED = bt.LIKE_SELECTORS["facebook.com"]
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


class FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def press(self, key):
        self.page.keys.append(key)
        if key == "k" and self.page.k_works:
            self.page.paused = not self.page.paused


class FakePage:
    def __init__(self, url=YOUTUBE, elements=None):
        if isinstance(url, dict):                       # FakePage({...}) = a YouTube page
            url, elements = YOUTUBE, url
        self.url, self.elements = url, dict(elements or {})
        self.clicks, self.keys = [], []
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

    def evaluate(self, js, *args):
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
    assert r.get("social_react").risk_for({}) == Risk.DANGER
    assert r.get("gmail_send").risk_for({}) == Risk.DANGER


def test_router_finds_the_tools_in_three_languages():
    r = build_default_registry()
    pick = lambda q: {t.name for t in r.select(q, 8)}
    assert "browser_open_result" in pick("open the first video")
    assert "browser_open_result" in pick("पहिलो भिडियो खोल")
    assert "browser_open_result" in pick("pahilo video khol")
    assert "social_react" in pick("like this post")
    assert "social_react" in pick("yo post like gara")
    assert "gmail_send" in pick("इमेल पठाऊ")
    assert "gmail_draft_reply" in pick("reply to this email saying I'll be there")


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
def test_click_text_clicks_and_reports(tab):
    tab["page"] = FakePage({("role", "link", "Videos"): [{"text": "Videos"}]})
    out = bt.browser_click_text({"text": "Videos"}, CTX)
    assert out["ok"] and tab["page"].clicks == ["Videos"] and "Clicked" in out["message"]
    missing = bt.browser_click_text({"text": "Nope"}, CTX)
    assert missing["ok"] is False and "Nothing clickable" in missing["error"]


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
def facebook_page(elements):
    page = FakePage("https://www.facebook.com/", elements)

    def on_click(key, item):
        if key == LIKE:
            page.elements[LIKE].remove(item)
            page.elements.setdefault(LIKED, []).append(item)
    page.on_click = on_click
    return page


def test_like_clicks_the_post_on_screen_and_verifies(tab):
    above, on_screen = {"y": -300, "text": "old"}, {"y": 400, "text": "this"}
    tab["page"] = facebook_page({LIKE: [above, on_screen]})
    out = bt.social_react({}, CTX)
    assert out["ok"] and out["liked"] and tab["page"].clicks == ["this"]


def test_like_never_unlikes_and_reports_failures(tab):
    tab["page"] = facebook_page({LIKED: [{"y": 300}]})
    out = bt.social_react({}, CTX)
    assert out["ok"] and "already liked" in out["message"] and tab["page"].clicks == []

    tab["page"] = facebook_page({LIKE: [{"y": 5000}]})                 # far below the screen
    assert "Scroll" in bt.social_react({}, CTX)["error"]

    page = FakePage("https://www.facebook.com/", {LIKE: [{"y": 300}]})  # click has no effect
    tab["page"] = page
    assert bt.social_react({}, CTX)["ok"] is False

    tab["page"] = FakePage("https://www.youtube.com/watch?v=1", {LIKE: [{"y": 300}]})
    out = bt.social_react({}, CTX)
    assert out["ok"] is False and "Facebook and Instagram only" in out["error"]


def test_like_waits_for_yes_through_the_existing_policy(tab):
    tab["page"] = facebook_page({LIKE: [{"y": 300, "text": "post"}]})
    engine, _, _ = make_engine([call("social_react")], extra_tools=bt.build())
    asked = engine.reply("like this post")
    assert asked.needs_confirmation and "like the post" in asked.text
    assert tab["page"].clicks == []                                       # nothing happened yet
    done = engine.reply("yes")
    assert done.ok and tab["page"].clicks == ["post"]


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


def test_normal_browser_is_used_when_automation_is_off_or_fails(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    monkeypatch.delenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", raising=False)
    r = build_default_registry()
    r.get("search_in_browser").handler({"query": "x"}, CTX)
    monkeypatch.setenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", "1")
    monkeypatch.setattr(pw, "open_in_automation_browser", lambda url: {"success": False, "response": "Chrome not found"})
    r.get("open_website").handler({"target": "github.com"}, CTX)
    assert opened == ["https://www.google.com/search?q=x", "https://github.com"]
