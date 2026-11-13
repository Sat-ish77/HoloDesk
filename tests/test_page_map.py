"""Page map and act-by-ref tools against a REAL headless Chromium.

The pages are local fixtures that mimic a feed, a mail client, a chatbot and
a settings form. They prove the map, the refs and the verify step work in a
browser; they do not prove Facebook, Gmail or Claude.ai behave the same.
Skipped when Playwright has no browser to launch.
"""

from pathlib import Path

import pytest

from brain.policy import Risk
from brain.tools import browser as bt
from brain.tools import build_default_registry, pagemap
from brain.tools.registry import ToolContext, ToolError
from browser import playwright_controller as pw
from helpers import call, make_engine, say

FIXTURES = Path(__file__).parent / "fixtures"
CTX = ToolContext()


@pytest.fixture(scope="module")
def chromium():
    sync_api = pytest.importorskip("playwright.sync_api")
    driver = sync_api.sync_playwright().start()
    browser = None
    for options in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            browser = driver.chromium.launch(**options)
            break
        except Exception:
            continue
    if browser is None:
        driver.stop()
        pytest.skip("Playwright has no Chromium, Chrome or Edge to launch")
    yield browser
    browser.close()
    driver.stop()


@pytest.fixture()
def tab(chromium, monkeypatch):
    context = chromium.new_context(viewport={"width": 900, "height": 600})
    holder = {"page": context.new_page()}

    def with_page(fn, *args, **kwargs):
        kwargs.pop("call_timeout", None)
        page = holder["page"]
        result = fn(page, *args, **kwargs)
        result.setdefault("url", page.url)
        result.setdefault("title", page.title())
        return result
    monkeypatch.setattr(pw, "with_page", with_page)
    monkeypatch.setattr(pw.controller, "use_tab", lambda page: holder.__setitem__("page", page))
    monkeypatch.setattr(bt, "_on_gmail", lambda page: True)
    bt._MAP.update(elements={}, groups={})
    holder["open"] = lambda name: holder["page"].goto((FIXTURES / name).as_uri())
    yield holder
    context.close()


def ref_of(name, role=None):
    """Ref of the first mapped element with this exact name."""
    for ref, el in bt._MAP["elements"].items():
        if el["name"] == name and (role is None or el["role"] == role):
            return ref
    raise AssertionError(f"{name!r} is not in the map: {[e['name'] for e in bt._MAP['elements'].values()]}")


def snapshot():
    out = bt.browser_snapshot({}, CTX)
    assert out["ok"], out
    return out["map"]


# ---------------------------------------------------------------- the map
def test_map_lists_what_is_on_screen_grouped_by_post(tab):
    tab["open"]("feed.html")
    text = snapshot()
    lines = text.splitlines()
    assert lines[0] == "[post · ON SCREEN] Post by Asha Rai"          # the post in the middle comes first
    assert '  e3 button "Like"' in text and 'searchbox "Search the feed"' in text
    assert "Third post" not in text                                   # below the fold
    assert bt.browser_snapshot({}, CTX)["title"] == "Feed"

    tab["page"].evaluate("window.scrollTo(0, 430)")
    text = snapshot()
    assert text.splitlines()[0].startswith("[post · ON SCREEN] Second post")
    assert 'button "Post" [disabled]' in text


def test_map_skips_covered_and_offscreen_elements_and_sees_shadow_dom(tab):
    tab["open"]("form.html")
    text = snapshot()
    assert "Shadow OK" in text and "Save changes" in text
    assert "Covered button" not in text and "Far away" not in text
    assert 'combobox "Country" = "Nepal"' in text


def test_map_never_reads_password_values(tab):
    tab["open"]("form.html")
    assert "hunter2" not in snapshot()
    out = bt.browser_type_ref({"ref": ref_of("Password"), "text": "x"}, CTX)
    assert out["ok"] is False and "never type passwords" in out["error"]


def test_map_is_capped(tab):
    tab["page"].set_content("".join(f"<button>B{i}</button>" for i in range(400)))
    out = bt.browser_snapshot({}, CTX)
    assert out["elements"] == 150 and len(out["map"]) <= 4100 and "more elements not listed" in out["map"]
    assert len(pagemap.render({"groups": [], "total": 1, "elements": [
        {"ref": f"e{i}", "group": 0, "role": "button", "name": "x" * 70, "value": None, "state": []}
        for i in range(150)]})) <= 4100


# ---------------------------------------------------------------- act by ref
def test_click_returns_what_the_element_reads_afterwards(tab):
    tab["open"]("form.html")
    snapshot()
    out = bt.browser_click_ref({"ref": ref_of("Save changes")}, CTX)
    assert out["ok"] and out["before"] == 'button "Save changes"' and out["after"].startswith('button "Saved"')
    assert "now reads" in out["message"] and out["element"]["name"] == "Save changes"

    snapshot()
    unchanged = bt.browser_click_ref({"ref": ref_of("Next")}, CTX)          # a click with no effect
    assert unchanged["ok"] and unchanged["changed"] is False and "Nothing changed" in unchanged["message"]

    snapshot()
    moved = bt.browser_click_ref({"ref": ref_of("Jump")}, CTX)
    assert moved["url"].endswith("#saved") and "went to" in moved["message"]


def test_stale_and_changed_refs_are_refused(tab):
    tab["open"]("form.html")
    snapshot()
    ref = ref_of("Next")
    tab["page"].evaluate("document.getElementById('swap').textContent = 'Delete everything'")
    out = bt.browser_click_ref({"ref": ref}, CTX)                           # its risk was judged as "Next"
    assert out["ok"] is False and out["stale"] and "page changed" in out["error"]
    assert tab["page"].locator("#swap").inner_text() == "Delete everything"

    snapshot()
    ref = ref_of("Save changes")
    tab["open"]("other.html")                                               # navigation wipes the refs
    out = bt.browser_click_ref({"ref": ref}, CTX)
    assert out["ok"] is False and "browser_snapshot" in out["error"]
    assert bt.browser_click_ref({"ref": "e99"}, CTX)["stale"]


def test_a_click_that_opens_a_tab_makes_it_the_current_tab(tab):
    tab["open"]("form.html")
    snapshot()
    out = bt.browser_click_ref({"ref": ref_of("Open help in a new tab")}, CTX)
    assert out["ok"] and out["new_tab"] and out["title"] == "Help"
    assert "Back to settings" in snapshot()                                 # tools now act on the new tab


def test_type_reads_the_value_back_and_picks_dropdown_options(tab):
    tab["open"]("form.html")
    snapshot()
    out = bt.browser_type_ref({"ref": ref_of("Search settings"), "text": "wifi", "press_enter": True}, CTX)
    assert out["ok"] and tab["page"].locator("#hits").inner_text() == "Results for wifi"
    snapshot()
    picked = bt.browser_type_ref({"ref": ref_of("Country"), "text": "United States"}, CTX)
    assert picked["ok"] and picked["value"] == "United States"
    assert bt.browser_type_ref({"ref": ref_of("Save changes"), "text": "x"}, CTX)["ok"] is False
    with pytest.raises(ToolError):
        bt.browser_type_ref({"ref": "e1", "text": ""}, CTX)


def test_risk_comes_from_the_element_the_ref_points_at(tab):
    tab["open"]("form.html")
    snapshot()
    r = build_default_registry()
    click, type_ = r.get("browser_click_ref"), r.get("browser_type_ref")
    assert click.risk_for({"ref": ref_of("Save changes")}) == Risk.ACT
    assert click.risk_for({"ref": ref_of("Delete account")}) == Risk.DANGER
    assert "Delete account" in click.summary_for({"ref": ref_of("Delete account")})
    search = ref_of("Search settings")
    assert type_.risk_for({"ref": search, "text": "x", "press_enter": True}) == Risk.ACT

    tab["open"]("feed.html")
    tab["page"].evaluate("window.scrollTo(0, 430)")
    snapshot()
    box = ref_of("Add a comment…")
    assert click.risk_for({"ref": ref_of("Like")}) == Risk.DANGER
    assert type_.risk_for({"ref": box, "text": "hi"}) == Risk.ACT                      # typed, not posted
    assert type_.risk_for({"ref": box, "text": "hi", "press_enter": True}) == Risk.DANGER
    assert "may post or send" in type_.summary_for({"ref": box, "text": "hi", "press_enter": True})


# ---------------------------------------------------------------- like
def test_like_acts_on_the_post_on_screen_and_verifies_it(tab):
    tab["open"]("feed.html")
    out = bt.social_react({}, CTX)
    assert out["ok"] and out["liked"] and out["post"] == "Post by Asha Rai"
    assert out["before"] == 'button "Like"' and out["after"].startswith('button "Remove Like"')
    page = tab["page"]
    assert page.locator("#p1 > .like").get_attribute("aria-label") == "Remove Like"
    assert page.locator("#p1 .clike").inner_text() == "Like"                # the comment's Like is untouched
    assert page.locator("#p3 .like").get_attribute("aria-label") == "Like"

    again = bt.social_react({}, CTX)                                        # never unlikes
    assert again["ok"] and "already liked" in again["message"]
    assert page.locator("#p1 > .like").get_attribute("aria-label") == "Remove Like"


def test_like_follows_the_scroll_and_reads_icon_only_buttons(tab):
    tab["open"]("feed.html")
    tab["page"].evaluate("window.scrollTo(0, 430)")
    out = bt.social_react({}, CTX)
    assert out["ok"] and out["post"].startswith("Second post") and 'button "Unlike"' in out["after"]
    assert tab["page"].locator("#p1 > .like").get_attribute("aria-label") == "Like"


def test_like_that_does_not_take_is_reported_as_a_failure(tab):
    tab["open"]("feed.html")
    tab["page"].evaluate("document.querySelector('#p1 > .like').dataset.broken = '1'")
    out = bt.social_react({}, CTX)
    assert out["ok"] is False and out["liked"] is False and "does not show as liked" in out["error"]

    tab["open"]("form.html")
    assert "can't see a Like button" in bt.social_react({}, CTX)["error"]


def test_click_text_like_and_click_ref_like_are_both_verified(tab):
    tab["open"]("feed.html")
    assert bt._click_risk({"text": "Like"}) == Risk.DANGER
    assert bt.browser_click_text({"text": "Like"}, CTX)["liked"]            # routed to the like logic

    tab["page"].evaluate("window.scrollTo(0, 430)")
    tab["page"].evaluate("document.querySelector('#p2 .like').dataset.broken = '1'")
    snapshot()
    out = bt.browser_click_ref({"ref": ref_of("Like")}, CTX)
    assert out["ok"] is False and "does not show as liked" in out["error"]


def test_like_confirmation_names_the_post(tab):
    tab["open"]("feed.html")
    engine, _, _ = make_engine([call("social_react")], extra_tools=bt.build())
    asked = engine.reply("like this post")
    assert asked.needs_confirmation and "Post by Asha Rai" in asked.text
    done = engine.reply("yes")
    assert done.ok and tab["page"].locator("#p1 > .like").get_attribute("aria-label") == "Remove Like"


# ---------------------------------------------------------------- comment
def test_comment_opens_the_box_posts_with_enter_and_checks_it_appeared(tab):
    tab["open"]("feed.html")
    out = bt.social_comment({"text": "congrats!"}, CTX)
    assert out["ok"] and out["posted"] and "Enter" in out["message"]
    assert "You: congrats!" in tab["page"].locator("#p1 .comments").inner_text()


def test_comment_uses_a_post_button_when_the_site_has_one(tab):
    tab["open"]("feed.html")
    tab["page"].evaluate("window.scrollTo(0, 430)")
    out = bt.social_comment({"text": "ramro cha"}, CTX)
    assert out["ok"] and "Post button" in out["message"] and out["post"].startswith("Second post")
    assert tab["page"].locator("#p2 .comments").inner_text() == "You: ramro cha"


def test_comment_reports_when_nothing_was_posted(tab):
    tab["open"]("feed.html")
    tab["page"].evaluate("window.scrollTo(0, 430)")
    tab["page"].evaluate("document.querySelector('#p2 .post').remove()")    # Enter does nothing in this box
    out = bt.social_comment({"text": "hello"}, CTX)
    assert out["ok"] is False and out["posted"] is False and "can't see it posted" in out["error"]
    tab["open"]("other.html")
    assert "can't find a comment box" in bt.social_comment({"text": "hello"}, CTX)["error"]


def test_comment_asks_once_quoting_the_text_and_the_post(tab):
    tab["open"]("feed.html")
    engine, _, _ = make_engine([call("social_comment", text="congrats!")], extra_tools=bt.build())
    asked = engine.reply("comment congrats on this post")
    assert asked.needs_confirmation and '"congrats!"' in asked.text and "Post by Asha Rai" in asked.text
    assert "You:" not in tab["page"].locator("#p1 .comments").inner_text()   # nothing posted before yes
    assert engine.reply("yes").ok
    assert "You: congrats!" in tab["page"].locator("#p1 .comments").inner_text()


# ---------------------------------------------------------------- gmail
def test_compose_resolves_a_contact_by_name_and_reads_the_draft_back(tab):
    tab["open"]("mail.html")
    out = bt.gmail_compose({"to": "Smarika Koirala", "subject": "Hello", "body": "Good morning."}, CTX)
    assert out["ok"] and out["sent"] is False
    assert out["to"] == ["smarika@example.com"] and out["subject"] == "Hello" and out["body"] == "Good morning."


def test_compose_says_what_is_missing(tab):
    tab["open"]("mail.html")
    out = bt.gmail_compose({"to": "Nobody Known", "subject": "Hi", "body": "Text"}, CTX)
    assert out["ok"] is False and out["to"] == [] and "recipient" in out["error"]
    assert out["subject"] == "Hi"                                            # the rest is still drafted
    refused = bt.gmail_send({}, CTX)
    assert refused["ok"] is False and "no recipient" in refused["error"]
    with pytest.raises(ToolError):
        bt.gmail_compose({}, CTX)


def test_compose_takes_a_plain_address(tab):
    tab["open"]("mail.html")
    out = bt.gmail_compose({"to": "new.person@example.org", "body": "Hi"}, CTX)
    assert out["ok"] and out["to"] == ["new.person@example.org"]


def test_send_asks_once_quoting_recipient_subject_and_body(tab):
    tab["open"]("mail.html")
    bt.gmail_compose({"to": "Smarika", "subject": "Hello", "body": "Good morning."}, CTX)
    engine, _, _ = make_engine([call("gmail_send")], extra_tools=bt.build())
    asked = engine.reply("send it")
    assert asked.needs_confirmation
    for part in ("smarika@example.com", '"Hello"', "Good morning."):
        assert part in asked.text
    assert tab["page"].locator("#toast").inner_text() == ""
    assert engine.reply("yes").ok and tab["page"].locator("#toast").inner_text() == "Message sent"


# ---------------------------------------------------------------- chatbot
def test_ask_chatbot_waits_for_the_answer_to_finish_and_returns_it(tab, monkeypatch):
    monkeypatch.setitem(bt._CHAT_SITES, "claude", ("", (FIXTURES / "chat.html").as_uri()))
    tab["open"]("chat.html")
    out = bt.ask_chatbot({"prompt": "what is MCP in one line", "wait_sec": 20}, CTX)
    assert out["ok"] and out["complete"]
    assert out["answer"] == "MCP is an open protocol that lets AI apps connect to tools and data."
    assert "untrusted" in out["note"]


def test_ask_chatbot_opens_the_site_in_a_new_tab_when_needed(tab, monkeypatch):
    monkeypatch.setitem(bt._CHAT_SITES, "claude", ("claude.ai", (FIXTURES / "chat.html").as_uri()))
    tab["open"]("other.html")
    first = tab["page"]
    out = bt.ask_chatbot({"prompt": "hi there", "wait_sec": 20}, CTX)
    assert out["ok"] and out["title"] == "Chat" and tab["page"] is not first and first.title() == "Help"


def test_ask_chatbot_says_when_there_is_no_chat_box(tab, monkeypatch):
    monkeypatch.setitem(bt._CHAT_SITES, "claude", ("", "about:blank"))
    tab["open"]("other.html")
    out = bt.ask_chatbot({"prompt": "hi"}, CTX)
    assert out["ok"] is False and "log in once" in out["error"]
    with pytest.raises(ToolError):
        bt.ask_chatbot({"prompt": "hi", "site": "bing"}, CTX)


# ---------------------------------------------------------------- through the engine
def test_snapshot_then_click_by_ref_through_the_agent_loop(tab):
    tab["open"]("form.html")
    seen = {}

    def click_save(messages, tools):
        seen["tools"] = {t["function"]["name"] for t in tools}
        page_map = messages[-1]["content"]
        ref = next(line.split()[0] for line in page_map.replace("\\n", "\n").splitlines() if "Save changes" in line)
        return call("browser_click_ref", ref=ref)
    engine, backend, _ = make_engine([call("browser_snapshot"), click_save, say("Your settings are saved.")],
                                     extra_tools=bt.build())
    engine.registry.get("browser_snapshot").always = True   # as when browser automation is enabled
    engine.cfg.max_tools_per_request = 3                    # the ref tools are not offered at first
    reply = engine.reply("save my settings")
    assert "browser_click_ref" not in {t["function"]["name"] for t in backend.calls[0]["tools"]}
    assert "browser_click_ref" in seen["tools"]             # the snapshot made them available
    assert reply.text == "Your settings are saved." and tab["page"].locator("#save").inner_text() == "Saved"
    assert "now reads" in backend.calls[2]["messages"][-1]["content"]       # the model saw the verified result
