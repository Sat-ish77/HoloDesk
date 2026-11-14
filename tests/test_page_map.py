"""look / click / type on web pages, against a REAL headless Chromium.

The pages are local fixtures that mimic a feed, a mail client, a chatbot and
a settings form. They prove the map, the refs and the read-back work in a
browser; they do not prove Facebook, Gmail or Claude.ai behave the same.
"""

import pytest

from brain.policy import Risk
from brain.tools import browser as bt
from brain.tools import build_default_registry, pagemap, ui
from brain.tools.registry import ToolContext, ToolError

CTX = ToolContext()


def ref_of(name, role=None):
    """Ref of the first mapped element with this exact name."""
    for ref, el in bt._MAP["elements"].items():
        if el["name"] == name and (role is None or el["role"] == role):
            return ref
    raise AssertionError(f"{name!r} is not in the map: {[e['name'] for e in bt._MAP['elements'].values()]}")


def view(**args):
    out = ui.look(args, CTX)
    assert out["ok"], out
    return out["view"]


# ---------------------------------------------------------------- look
def test_look_lists_what_is_on_screen_grouped_by_post(tab):
    tab["open"]("feed.html")
    lines = view().splitlines()
    assert lines[0].startswith('web page "Feed" file://')
    assert lines[1] == "[post · ON SCREEN] Post by Asha Rai"          # the post in the middle comes first
    assert '  e3 button "Like"' in lines and any('searchbox "Search the feed"' in line for line in lines)
    assert not any("Third post" in line for line in lines)            # below the fold

    tab["page"].evaluate("window.scrollTo(0, 430)")
    text = view()
    assert text.splitlines()[1].startswith("[post · ON SCREEN] Second post")
    assert 'button "Post" [disabled]' in text


def test_look_skips_covered_and_offscreen_elements_and_sees_shadow_dom(tab):
    tab["open"]("form.html")
    text = view()
    assert "Shadow OK" in text and "Save changes" in text
    assert "Covered button" not in text and "Far away" not in text
    assert 'combobox "Country" = "Nepal"' in text


def test_look_can_include_the_words_on_the_page_and_shows_notices(tab):
    tab["open"]("other.html")
    assert "Help text." not in view() and "Help text." in view(text=True)
    tab["open"]("mail.html")
    tab["page"].evaluate("document.getElementById('toast').textContent = 'Message sent'")
    assert "[notice] Message sent" in view()


def test_look_never_reads_password_values(tab):
    tab["open"]("form.html")
    assert "hunter2" not in view(text=True)
    out = ui.type_({"ref": ref_of("Password"), "text": "x"}, CTX)
    assert out["ok"] is False and "never type passwords" in out["error"]


def test_the_map_is_capped(tab):
    tab["page"].set_content("".join(f"<button>B{i}</button>" for i in range(400)))
    text = view()
    assert len(bt._MAP["elements"]) == 150 and len(text) <= 4300 and "more elements not listed" in text
    assert len(pagemap.render({"groups": [], "total": 1, "elements": [
        {"ref": f"e{i}", "group": 0, "role": "button", "name": "x" * 70, "value": None, "state": []}
        for i in range(150)]})) <= 4100


# ---------------------------------------------------------------- click
def test_click_returns_what_changed_and_the_fresh_view(tab):
    tab["open"]("form.html")
    view()
    out = ui.click({"ref": ref_of("Save changes")}, CTX)
    assert out["ok"] and out["before"] == 'button "Save changes"' and out["after"].startswith('button "Saved"')
    assert 'button "Saved"' in out["view"] and "Save changes" not in out["view"]     # refs for the next step
    unchanged = ui.click({"ref": ref_of("Next")}, CTX)                               # ref taken from that view
    assert unchanged["ok"] and unchanged["changed"] is False and "Nothing changed" in unchanged["message"]
    moved = ui.click({"ref": ref_of("Jump")}, CTX)
    assert moved["url"].endswith("#saved") and "went to" in moved["message"]


def test_stale_and_changed_refs_are_refused_and_the_new_view_comes_back(tab):
    tab["open"]("form.html")
    view()
    ref = ref_of("Next")
    tab["page"].evaluate("document.getElementById('swap').textContent = 'Delete everything'")
    out = ui.click({"ref": ref}, CTX)                                       # its risk was judged as "Next"
    assert out["ok"] is False and out["stale"] and "page changed" in out["error"]
    assert tab["page"].locator("#swap").inner_text() == "Delete everything"
    assert 'button "Delete everything"' in out["view"]                      # so the model can go on at once

    ref = ref_of("Save changes")
    tab["open"]("other.html")                                               # navigation wipes the refs
    out = ui.click({"ref": ref}, CTX)
    assert out["ok"] is False and "Back to settings" in out["view"]
    assert ui.click({"ref": "e99"}, CTX)["stale"]
    with pytest.raises(ToolError):
        ui.click({}, CTX)


def test_a_click_that_opens_a_tab_makes_it_the_current_tab(tab):
    tab["open"]("form.html")
    view()
    out = ui.click({"ref": ref_of("Open help in a new tab")}, CTX)
    assert out["ok"] and out["new_tab"] and out["title"] == "Help"
    assert "Back to settings" in out["view"]                                # already looking at the new tab


def test_like_is_verified_by_the_button_itself_on_the_post_on_screen(tab):
    tab["open"]("feed.html")
    view()
    out = ui.click({"ref": ref_of("Like")}, CTX)                            # first Like in the ON SCREEN post
    assert out["ok"] and out["after"].startswith('button "Remove Like"')
    page = tab["page"]
    assert page.locator("#p1 .clike").inner_text() == "Like"                # the comment's Like is untouched
    assert page.locator("#p3 .like").get_attribute("aria-label") == "Like"

    page.evaluate("window.scrollTo(0, 430)")
    page.evaluate("document.querySelector('#p2 .like').dataset.broken = '1'")
    view()
    out = ui.click({"ref": ref_of("Like")}, CTX)                            # icon-only button, and it does not take
    assert out["ok"] is False and "does not show as liked" in out["error"]


# ---------------------------------------------------------------- type
def test_type_reads_the_value_back_and_picks_dropdown_options(tab):
    tab["open"]("form.html")
    view()
    out = ui.type_({"ref": ref_of("Search settings"), "text": "wifi", "press_enter": True}, CTX)
    assert out["ok"] and tab["page"].locator("#hits").inner_text() == "Results for wifi"
    picked = ui.type_({"ref": ref_of("Country"), "text": "United States"}, CTX)
    assert picked["ok"] and picked["value"] == "United States" and '= "United States"' in picked["view"]
    assert ui.type_({"ref": ref_of("Save changes"), "text": "x"}, CTX)["ok"] is False
    with pytest.raises(ToolError):
        ui.type_({"ref": "e1", "text": ""}, CTX)


# ---------------------------------------------------------------- risk
def test_risk_comes_from_the_element_the_ref_points_at(tab):
    tab["open"]("form.html")
    view()
    r = build_default_registry()
    click, type_ = r.get("click"), r.get("type")
    assert click.risk_for({"ref": ref_of("Save changes")}) == Risk.ACT
    assert click.risk_for({"ref": ref_of("Delete account")}) == Risk.DANGER
    assert "Delete account" in click.summary_for({"ref": ref_of("Delete account")})
    assert type_.risk_for({"ref": ref_of("Search settings"), "text": "x", "press_enter": True}) == Risk.ACT
    assert type_.risk_for({"text": "x", "press_enter": True}) == Risk.DANGER       # Enter into who knows what
    assert type_.risk_for({"text": "x"}) == Risk.ACT

    tab["open"]("feed.html")
    tab["page"].evaluate("window.scrollTo(0, 430)")
    view()
    box = ref_of("Add a comment…")
    assert click.risk_for({"ref": ref_of("Like")}) == Risk.DANGER
    assert type_.risk_for({"ref": box, "text": "hi"}) == Risk.ACT                      # typed, not posted
    assert type_.risk_for({"ref": box, "text": "hi", "press_enter": True}) == Risk.DANGER
    assert "may post or send" in type_.summary_for({"ref": box, "text": "hi", "press_enter": True})


def test_comment_button_only_opens_the_box_until_something_is_typed(tab):
    tab["open"]("feed.html")
    view()
    click = build_default_registry().get("click")
    assert click.risk_for({"ref": ref_of("Comment")}) == Risk.ACT          # one question per comment, not two
    ui.click({"ref": ref_of("Comment")}, CTX)
    ui.type_({"ref": ref_of("Write a comment…"), "text": "congrats"}, CTX)
    assert click.risk_for({"ref": ref_of("Comment")}) == Risk.DANGER       # now it could be the button that posts


def test_enter_on_an_assistants_own_site_is_not_held(tab, monkeypatch):
    tab["open"]("chat.html")
    view()
    type_ = build_default_registry().get("type")
    args = {"ref": ref_of("Write your prompt"), "text": "hi", "press_enter": True}
    assert type_.risk_for(args) == Risk.DANGER
    monkeypatch.setitem(ui._SEEN, "host", "claude.ai")
    assert type_.risk_for(args) == Risk.ACT


# ---------------------------------------------------------------- wait
def test_wait_for_page_returns_what_is_new_once_the_page_settles(tab):
    tab["open"]("chat.html")
    view()
    ui.type_({"ref": ref_of("Write your prompt"), "text": "what is MCP in one line", "press_enter": True}, CTX)
    out = ui.wait_for_page({"seconds": 20}, CTX)
    assert out["ok"] and out["settled"]
    assert "MCP is an open protocol that lets AI apps connect to tools and data." in out["new_text"]
    assert "untrusted" in out["note"] and "view" in out


# ---------------------------------------------------------------- gmail skills
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
