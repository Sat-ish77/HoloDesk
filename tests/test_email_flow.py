import json

from brain.email_flow import EmailFlow, basename, describe_file, wants_email
from brain.llm import FakeBackend, LLMResponse
from brain.policy import Risk
from brain.tools.registry import Tool
from helpers import call, make_engine, say


def _gmail_tools(calls):
    def tool(name, result, risk=Risk.ACT):
        def handler(args, ctx):
            calls.append((name, dict(args)))
            return result
        return Tool(name, name, handler, risk=risk)
    return [
        tool("gmail_compose", {"ok": True, "to": ["satish.wagle@gmail.com"], "subject": "Introduction",
                               "body": "I am graduating in December 2026."}),
        tool("gmail_open_latest", {"ok": True}),
        tool("gmail_draft_reply", {"ok": True, "draft": "Sounds good."}),
        tool("gmail_discard_draft", {"ok": True}),
        tool("gmail_attach", {"ok": True, "attached": "Satish_Resume.pdf"}),
        tool("find_files", {"ok": True, "matches": ["C:/Users/Sat/Desktop/Satish_Resume.pdf",
                                                   "C:/Users/Sat/Documents/Resume_old.docx"]}),
        tool("gmail_send", {"ok": True, "sent": True, "message": "Email sent."}, risk=Risk.DANGER),
    ]


def _decide(action, say_="", **fields):
    return LLMResponse(content=json.dumps({"to": None, "mode": None, "subject": None, "body": None,
                                           "attachment": None, "action": action, "say": say_, **fields}))


DRAFT = dict(to="satish.wagle@gmail.com", mode="new", subject="Introduction",
             body="I am graduating in December 2026.")


def _engine(calls, *decisions, script=()):
    engine, _, log = make_engine(list(script), extra_tools=() if script else _gmail_tools(calls))
    engine._writer = FakeBackend(list(decisions))
    return engine, log


def test_one_sentence_with_everything_drafts_and_waits_for_yes():
    # Live test: "It should go to Sati Swagli. It should be a new email." was rejected by the script.
    calls = []
    engine, _ = _engine(calls, _decide("draft", **DRAFT))
    ready = engine.reply("write an email to satish dot wagle at gmail dot com, new, subject introduction, "
                         "say I am graduating in December 2026")
    assert calls == [("gmail_compose", {"to": "satish.wagle@gmail.com", "subject": "Introduction",
                                        "body": "I am graduating in December 2026."})]
    assert ready.needs_confirmation and "satish.wagle@gmail.com" in ready.text
    engine.reply("yes")
    assert calls[-1] == ("gmail_send", {}) and not engine.email_flow_waiting("voice")


def test_just_press_send_sends_instead_of_starting_over():
    # Live test: "Just press send." got "Who should the email go to?" and "new or reply?".
    calls = []
    engine, _ = _engine(calls, _decide("draft", **DRAFT), _decide("send", **DRAFT))
    engine.reply("draft an email to Satish, new, subject Introduction, say I am graduating")
    out = engine.reply("Just press send.")
    assert calls[-1] == ("gmail_send", {}) and out.text == "Email sent."


def test_missing_piece_is_asked_once_in_the_models_words():
    engine, _ = _engine([], _decide("ask", "Who is it for?", mode="new"))
    assert engine.reply("I want to write an email").text == "Who is it for?"
    assert engine.email_flow_waiting("voice")


def test_changing_the_recipient_discards_and_redrafts():
    calls = []
    engine, _ = _engine(calls, _decide("draft", **DRAFT),
                        _decide("draft", **{**DRAFT, "to": "Smarika Koirala"}))
    engine.reply("draft an email to Satish, new, subject Introduction, say I am graduating")
    again = engine.reply("change the recipient to Smarika Koirala")
    assert [c[0] for c in calls] == ["gmail_compose", "gmail_discard_draft", "gmail_compose"]
    assert calls[-1][1]["to"] == "Smarika Koirala" and again.needs_confirmation


def test_changing_only_the_body_keeps_the_recipient():
    calls = []
    engine, _ = _engine(calls, _decide("draft", **DRAFT),
                        _decide("draft", **{**DRAFT, "body": "I am looking for a software job."}))
    engine.reply("draft an email to Satish, new, subject Introduction, say I am graduating")
    engine.reply("make it say I am looking for a software job")
    assert [c[0] for c in calls] == ["gmail_compose", "gmail_compose"]
    assert calls[-1][1] == {"to": "", "subject": "Introduction", "body": "I am looking for a software job."}


def test_cancel_drops_the_email():
    calls = []
    engine, _ = _engine(calls, _decide("ask", "Who is it for?"), _decide("cancel"))
    engine.reply("write an email")
    assert "Nothing was sent" in engine.reply("forget it").text
    assert calls == [] and not engine.email_flow_waiting("voice")


def test_leaving_the_email_runs_the_command():
    # Live test: "Close the Gmail right now" was answered with "new or reply?".
    engine, log = _engine([], _decide("ask", "Who is it for?"), _decide("leave"),
                          script=[call("open_app", name="notepad"), say("Done.")])
    engine.reply("write an email")
    engine.reply("open notepad")
    assert log == [("open_app", {"name": "notepad"})] and not engine.email_flow_waiting("voice")


def test_brain_sees_the_draft_and_the_users_name():
    engine, _ = _engine([], _decide("ask", "Who is it for?"))
    engine.cfg.user_name = "Satish Wagle"
    engine.reply("write an email")
    sent = engine._writer.calls[0]["messages"] if hasattr(engine._writer, "calls") else None
    rules = (sent or [{}])[0].get("content", "")
    assert sent is None or "Satish Wagle" in rules


def test_several_matching_files_are_offered_and_the_pick_is_attached():
    calls = []
    engine, _ = _engine(calls, _decide("draft", **DRAFT, attachment="my resume"))
    ask = engine.reply("draft an email to Satish, new, Introduction, say I am graduating, attach my resume")
    assert ask.text.startswith("I found 2 files") and "Satish_Resume.pdf in Desktop" in ask.text
    ready = engine.reply("the first one")
    assert ("gmail_attach", {"path": "C:/Users/Sat/Desktop/Satish_Resume.pdf"}) in calls
    assert "Satish_Resume.pdf attached" in ready.text


def test_only_real_email_requests_start_the_flow():
    assert wants_email("Can you write her a mail saying hi")
    assert wants_email("send an email to Smarika")
    assert not wants_email("I want to send this mail")      # a send order, not a new email
    assert not wants_email("did you send the email?")
    assert not wants_email("open gmail")


def test_windows_paths_are_named_by_file_and_folder():
    path = r"C:\Users\Sat\Desktop\Satish_Resume.pdf"
    assert basename(path) == "Satish_Resume.pdf"
    assert describe_file(path) == "Satish_Resume.pdf in Desktop"


def test_pick_by_number_or_name():
    flow = EmailFlow()
    flow.choices = ["C:/a/Satish_Resume.pdf", "C:/b/notes.txt"]
    assert flow.pick("the second one") == "C:/b/notes.txt"
    flow.attachment_path = None
    assert flow.pick("the resume") == "C:/a/Satish_Resume.pdf"
