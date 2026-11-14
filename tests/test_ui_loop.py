"""The whole loop on real pages: a scripted "model" reads the view the tools
return, acts on its refs, is held at dangerous steps, resumes on yes, and its
answer is checked against what the browser shows.

The model's choices are scripted, so this proves the loop's mechanics (fresh
views, holds, resume, the check), not that a real model chooses well. The
window-channel tests use fake UI Automation elements: that code has not run
on Windows.
"""

import json

import pytest

from brain.engine import _VIEW_MARK
from brain.policy import Risk
from brain.tools import browser as bt
from brain.tools import ui
from brain.tools.registry import ToolContext, ToolError
from helpers import call, make_engine, say

CTX = ToolContext()


def act(tool, name, **extra):
    """A model step: find the element called `name` in the newest view and act on it."""
    def step(messages, tools):
        newest = next(m["content"] for m in reversed(messages) if m["role"] == "tool" and _VIEW_MARK in m["content"])
        lines = newest.split(_VIEW_MARK)[1].splitlines()
        ref = next(line.split()[0] for line in lines if f'"{name}"' in line)
        return call(tool, ref=ref, **extra)
    return step


def verdict(evidence="", **fields):
    return say(json.dumps({"claims_done": True, "confirmed": True, "evidence": evidence, "missing": "", **fields}))


def loop(script, check=True):
    engine, backend, _ = make_engine(script, extra_tools=ui.build() + bt.build())
    engine.cfg.verify, engine.cfg.max_turns = check, 12
    return engine, backend


# ---------------------------------------------------------------- web
def test_like_this_post_one_question_then_verified_on_the_page(tab):
    tab["open"]("feed.html")
    engine, backend = loop([call("look"), act("click", "Like"), say("I liked Asha Rai's post."),
                            verdict('button "Remove Like"')])
    asked = engine.reply("like this post")
    assert asked.needs_confirmation and 'click button "Like"' in asked.text and "Post by Asha Rai" in asked.text
    assert tab["page"].locator("#p1 > .like").get_attribute("aria-label") == "Like"       # held
    done = engine.reply("yes")
    assert done.text == "I liked Asha Rai's post." and done.verified and done.evidence == 'button "Remove Like"'
    assert tab["page"].locator("#p1 > .like").get_attribute("aria-label") == "Remove Like"
    assert [c["name"] for c in done.tool_calls] == ["look", "click"]                      # two steps, one question


def test_a_like_that_did_not_take_cannot_be_reported_as_done(tab):
    tab["open"]("feed.html")
    tab["page"].evaluate("document.querySelector('#p1 > .like').dataset.broken = '1'")
    engine, _ = loop([call("look"), act("click", "Like"), say("Liked it."), verdict('button "Remove Like"'),
                      say("The Like did not register; the button still says Like."), verdict(claims_done=False)])
    engine.reply("like this post")
    done = engine.reply("yes")
    # The checker's quote is not on the page, so "Liked it." was sent back once.
    assert done.text == "The Like did not register; the button still says Like." and not done.verified


def test_comment_one_question_quoting_the_text_then_seen_under_the_post(tab):
    tab["open"]("feed.html")
    engine, _ = loop([call("look"), act("click", "Comment"),
                      act("type", "Write a comment…", text="congrats!", press_enter=True),
                      say("Your comment is posted."), verdict("You: congrats!")])
    asked = engine.reply("comment congrats on this post")
    assert asked.needs_confirmation and '"congrats!"' in asked.text and "may post or send" in asked.text
    assert "You:" not in tab["page"].locator("#p1 .comments").inner_text()                # nothing posted yet
    done = engine.reply("yes")
    assert done.verified and "You: congrats!" in tab["page"].locator("#p1 .comments").inner_text()


def test_changing_your_mind_at_the_question_changes_what_is_posted(tab):
    tab["open"]("feed.html")
    engine, _ = loop([call("look"), act("click", "Comment"),
                      act("type", "Write a comment…", text="congrats!", press_enter=True),
                      act("type", "Write a comment…", text="so proud of you", press_enter=True),
                      say("Posted."), verdict("You: so proud of you")])
    engine.reply("comment congrats on this post")
    asked = engine.reply("no wait, say so proud of you instead")
    assert asked.needs_confirmation and '"so proud of you"' in asked.text
    assert engine.reply("yes").verified
    posted = tab["page"].locator("#p1 .comments").inner_text()
    assert "You: so proud of you" in posted and "congrats" not in posted


def test_ask_a_chatbot_with_generic_tools_only(tab, monkeypatch):
    monkeypatch.setattr(bt, "CHAT_HOSTS", ("",))          # the fixture stands in for claude.ai
    tab["open"]("chat.html")
    engine, backend = loop([call("look"), act("type", "Write your prompt", text="what is MCP in one line", press_enter=True),
                            call("wait_for_page", seconds=20), say("Claude says MCP is an open protocol for tools and data."),
                            verdict("MCP is an open protocol that lets AI apps connect to tools and data.")])
    done = engine.reply("ask claude what MCP is in one line")
    assert not done.needs_confirmation and done.verified
    waited = backend.calls[3]["messages"][-1]["content"]
    assert "MCP is an open protocol that lets AI apps connect to tools and data." in waited


def test_an_email_with_look_click_type_alone(tab):
    tab["open"]("mail.html")
    engine, _ = loop([call("look"), act("click", "Compose"), act("type", "To recipients", text="Smarika"),
                      act("click", "Smarika Koirala smarika@example.com"), act("type", "Subject", text="Hello"),
                      act("type", "Message Body", text="Good morning."), act("click", "Send"),
                      say("Sent to Smarika Koirala."), verdict("Message sent")])
    asked = engine.reply("email Smarika, subject hello, say good morning, and send it")
    assert asked.needs_confirmation and 'click button "Send"' in asked.text and "New Message" in asked.text
    assert tab["page"].locator("[email]").get_attribute("email") == "smarika@example.com"
    assert tab["page"].locator("#toast").inner_text() == ""
    done = engine.reply("yes")
    assert done.verified and done.evidence == "Message sent"
    assert tab["page"].locator("#toast").inner_text() == "Message sent"


def test_the_gmail_skill_then_send_through_the_same_loop(tab):
    tab["open"]("mail.html")
    engine, _ = loop([call("gmail_compose", to="Smarika", subject="Hello", body="Good morning."), call("gmail_send"),
                      say("Sent."), verdict("Message sent")])
    asked = engine.reply("send Smarika an email: hello, good morning")
    for part in ("smarika@example.com", '"Hello"', "Good morning."):
        assert part in asked.text                                   # the one question quotes the real draft
    assert engine.reply("yes").verified and tab["page"].locator("#toast").inner_text() == "Message sent"


def test_only_one_view_is_in_context_however_many_steps(tab):
    tab["open"]("mail.html")
    engine, backend = loop([call("look"), act("click", "Compose"), act("type", "Subject", text="Hi"), say("Drafted.")],
                           check=False)
    engine.reply("start an email with subject hi")
    final = backend.calls[-1]["messages"]
    assert sum(_VIEW_MARK in m["content"] for m in final if m["role"] == "tool") == 1
    assert sum("older view removed" in m["content"] for m in final if m["role"] == "tool") == 2


# ---------------------------------------------------------------- app windows (fake UI Automation)
class FakeElement:
    def __init__(self, role, name, value=None, enabled=True, password=False):
        self.element_info = type("Info", (), {"control_type": role, "name": name,
                                              "element": type("Raw", (), {"CurrentIsPassword": password})()})()
        self.value, self.enabled, self.clicks = value, enabled, 0

    def is_visible(self):
        return True

    def is_enabled(self):
        return self.enabled

    def get_value(self):
        if self.value is None:
            raise AttributeError("no value pattern")
        return self.value

    def window_text(self):
        return self.value or ""

    def click_input(self):
        self.clicks += 1


@pytest.fixture()
def notepad(monkeypatch):
    """A fake Notepad window in front, with a fake keyboard."""
    els = [FakeElement("MenuItem", "File"), FakeElement("Document", "Text editor", value=""),
           FakeElement("Button", "Delete"), FakeElement("Button", "Print", enabled=False),
           FakeElement("Edit", "File name:", value="old.txt"), FakeElement("Edit", "Password", value="hunter2", password=True),
           FakeElement("Text", "Ln 1, Col 1"), FakeElement("Pane", "ignored")]
    keys = []
    focused = {"el": None}
    monkeypatch.setattr(ui, "_work_window", lambda: (7, "Untitled - Notepad"))
    monkeypatch.setattr(ui, "_descendants", lambda hwnd: els)
    monkeypatch.setattr(ui.desktop, "_focus", lambda hwnd: keys.append("focus"))
    monkeypatch.setattr(ui.desktop, "_pyautogui", lambda: type("Keys", (), {
        "hotkey": lambda self, *k: keys.append("+".join(k)), "press": lambda self, k: keys.append(k)})())

    def paste(text):
        target = next(e for e in els if e.clicks and e.element_info.control_type in ("Edit", "Document"))
        target.value = text if "ctrl+a" in keys else (target.value or "") + text
    monkeypatch.setattr(ui, "_paste", paste)
    monkeypatch.setattr(ui.time, "sleep", lambda s: None)
    return {"els": els, "keys": keys}


def test_a_window_is_seen_as_a_map_with_u_refs(notepad):
    out = ui.look({"text": True}, CTX)
    lines = out["view"].splitlines()
    assert lines[0] == 'window "Untitled - Notepad"'
    assert '  u1 MenuItem "File"' in lines and '  u2 Document "Text editor" = ""' in lines
    assert '  u4 Button "Print" [disabled]' in lines and '  u5 Edit "File name:" = "old.txt"' in lines
    assert "ignored" not in out["view"] and "hunter2" not in out["view"]
    assert "Ln 1, Col 1" in out["view"]                                    # static text only when asked for
    assert "Ln 1, Col 1" not in ui.look({}, CTX)["view"]


def test_click_and_type_in_a_window_return_the_fresh_view(notepad):
    ui.look({}, CTX)
    out = ui.click({"ref": "u1"}, CTX)
    assert out["ok"] and notepad["els"][0].clicks == 1 and out["view"].startswith('window "Untitled - Notepad"')

    out = ui.type_({"ref": "u5", "text": "notes.txt", "press_enter": True}, CTX)
    assert out["ok"] and out["value"] == "notes.txt" and 'Edit "File name:" = "notes.txt"' in out["view"]
    assert notepad["keys"][-3:] == ["focus", "ctrl+a", "enter"]            # a field is replaced
    notepad["keys"].clear()
    out = ui.type_({"ref": "u2", "text": "hello"}, CTX)
    assert out["ok"] and notepad["keys"] == ["focus", "ctrl+end"]          # a document gets it at the end


def test_window_refs_are_checked_before_use(notepad):
    ui.look({}, CTX)
    assert "disabled" in ui.click({"ref": "u4"}, CTX)["error"]
    assert "never type passwords" in ui.type_({"ref": "u6", "text": "x"}, CTX)["error"]
    assert "not a text field" in ui.type_({"ref": "u3", "text": "x"}, CTX)["error"]
    notepad["els"][2].element_info.name = "Format disk"                    # the window changed under the ref
    out = ui.click({"ref": "u3"}, CTX)
    assert out["ok"] is False and notepad["els"][2].clicks == 0 and 'Button "Format disk"' in out["view"]
    assert ui.click({"ref": "u99"}, CTX)["ok"] is False


def test_window_risk_is_judged_on_the_element_name(notepad):
    ui.look({}, CTX)
    click, type_ = (t for t in ui.build() if t.name in ("click", "type"))
    assert click.risk_for({"ref": "u1"}) == Risk.ACT and click.risk_for({"ref": "u3"}) == Risk.DANGER
    assert 'click Button "Delete" in the window "Untitled - Notepad"' == click.summary_for({"ref": "u3"})
    assert type_.risk_for({"ref": "u5", "text": "a"}) == Risk.ACT
    assert type_.risk_for({"ref": "u5", "text": "a", "press_enter": True}) == Risk.DANGER


def test_private_windows_are_not_read(notepad, monkeypatch):
    monkeypatch.setattr(ui, "_work_window", lambda: (7, "Bitwarden - Password Manager"))
    with pytest.raises(ToolError):
        ui.look({}, CTX)


def test_a_window_with_no_controls_points_to_the_other_eyes(notepad, monkeypatch):
    monkeypatch.setattr(ui, "_descendants", lambda hwnd: [])
    assert "look_at_screen" in ui.look({}, CTX)["view"]
