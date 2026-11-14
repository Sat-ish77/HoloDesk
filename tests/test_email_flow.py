from brain.email_flow import wants_email
from brain.policy import Risk
from brain.tools.registry import Tool
import pytest

from brain.engine import ReplyEngine
from brain.llm import LLMResponse
from helpers import call, make_engine, say


class _EchoWriter:
    """Stands in for gpt-5.5: returns what was said, in the writer's format."""

    def chat(self, messages, **kw):
        ask = dict(line.split(": ", 1) for line in messages[-1]["content"].splitlines())
        body = ask["Body, as said"]
        subject = ask.get("Subject, as said")
        return LLMResponse(content=f"Subject: {subject}\n\n{body}" if subject else body)


@pytest.fixture(autouse=True)
def _echo_writer(monkeypatch):
    monkeypatch.setattr(ReplyEngine, "_writer", _EchoWriter(), raising=False)


def _gmail_tools(calls):
    def tool(name, result, risk=Risk.ACT):
        def handler(args, ctx):
            calls.append((name, dict(args)))
            return result
        return Tool(name, name, handler, risk=risk)
    return [
        tool("gmail_compose", {"ok": True, "to": ["smarika@example.com"], "subject": "Greetings",
                               "body": "Hey, how are you doing today?"}),
        tool("gmail_open_latest", {"ok": True, "thread": "Smarika Koirala - Lunch?"}),
        tool("gmail_draft_reply", {"ok": True, "draft": "Sounds good, see you then."}),
        tool("gmail_attach", {"ok": True, "attached": "Satish_Resume.pdf"}),
        tool("gmail_discard_draft", {"ok": True}),
        tool("find_files", {"ok": True, "matches": ["C:/Users/Sat/Desktop/Satish_Resume.pdf",
                                                   "C:/Users/Sat/Documents/Resume_old.docx",
                                                   "C:/Users/Sat/Documents/notes.txt"]}),
        tool("gmail_send", {"ok": True, "sent": True, "message": "Email sent."}, risk=Risk.DANGER),
    ]


def test_new_email_asks_each_step_then_waits_for_yes():
    calls = []
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    assert engine.reply("I want to draft an email").text == "Who should the email go to?"
    assert "new email, or a reply" in engine.reply("Smarika Koirala").text
    assert engine.reply("new").text == "What's the subject?"
    assert engine.reply("Greetings").text == "What should the email say?"
    assert engine.reply("Hey, how are you doing today?").text.startswith("Any attachment?")
    ready = engine.reply("no")
    assert calls == [("gmail_compose", {"to": "Smarika Koirala", "subject": "Greetings",
                                        "body": "Hey, how are you doing today?"})]
    assert ready.needs_confirmation and "smarika@example.com" in ready.text and "send" in ready.text
    engine.reply("yes")
    assert calls[-1] == ("gmail_send", {})


def test_reply_opens_the_latest_thread_and_skips_subject():
    calls = []
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    engine.reply("send an email to Smarika Koirala")          # recipient taken from the request
    assert engine.reply("reply to the existing thread").text == "What should the email say?"
    engine.reply("Sounds good, see you then.")
    engine.reply("no attachment")
    assert [c[0] for c in calls] == ["gmail_open_latest", "gmail_draft_reply"]
    assert calls[0][1] == {"query": "Smarika Koirala"}


def test_cancel_drops_the_draft_and_sends_nothing():
    calls = []
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    engine.reply("write an email")
    assert "Nothing was sent" in engine.reply("cancel").text
    assert calls == [] and not engine.email_flow_waiting("voice")


def test_unclear_mode_is_asked_again():
    engine, _, _ = make_engine([], extra_tools=_gmail_tools([]))
    engine.reply("compose an email to Smarika")
    assert "new email or a reply" in engine.reply("hmm whatever").text


def test_only_real_email_requests_start_the_flow():
    assert wants_email("Can you write her a mail saying hi")
    assert not wants_email("did you send the email?")
    assert not wants_email("open gmail")


def test_described_body_is_written_by_the_writer_model():
    from brain.llm import FakeBackend, LLMResponse
    calls = []
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    engine._writer = FakeBackend([LLMResponse(content="Subject: Running late\n\nHi Smarika, I'll be ten minutes late.")])
    engine.reply("send an email to Smarika Koirala")
    engine.reply("new")
    engine.reply("you choose")                                   # subject
    engine.reply("tell her I'll be ten minutes late")            # describes, doesn't dictate
    engine.reply("no")
    assert calls[0] == ("gmail_compose", {"to": "Smarika Koirala", "subject": "Running late",
                                          "body": "Hi Smarika, I'll be ten minutes late."})


def test_dictated_body_is_sent_as_spoken():
    from brain.llm import FakeBackend
    calls = []
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    for said in ["write an email to Smarika", "new", "Greetings", "Hey, how are you doing today?", "no"]:
        engine.reply(said)
    assert calls[0][1]["body"] == "Hey, how are you doing today?"


def _to_attachment_question(engine):
    for said in ["write an email to Smarika", "new", "Hi", "See attached."]:
        engine.reply(said)


def test_several_matching_files_are_offered_and_the_pick_is_attached():
    calls = []
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    _to_attachment_question(engine)
    ask = engine.reply("my resume").text
    assert ask.startswith("I found 2 files") and "Satish_Resume.pdf in Desktop" in ask
    ready = engine.reply("the first one")
    assert ("gmail_attach", {"path": "C:/Users/Sat/Desktop/Satish_Resume.pdf"}) in calls
    assert "Satish_Resume.pdf attached" in ready.text and ready.needs_confirmation


def test_one_matching_file_is_attached_without_asking():
    calls = []
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    _to_attachment_question(engine)
    engine.reply("attach my resume pdf")      # only Satish_Resume.pdf has both 'resume' and 'pdf'
    assert ("gmail_attach", {"path": "C:/Users/Sat/Desktop/Satish_Resume.pdf"}) in calls


def test_unknown_file_is_asked_again():
    engine, _, _ = make_engine([], extra_tools=_gmail_tools([]))
    _to_attachment_question(engine)
    assert "couldn't find a file like 'invoice'" in engine.reply("invoice").text


def test_windows_paths_are_named_by_file_and_folder():
    # A regex that split only on "/" read a whole Windows path as the file name.
    from brain.email_flow import _basename, _describe_file
    path = r"C:\Users\Sat\Desktop\Satish_Resume.pdf"
    assert _basename(path) == "Satish_Resume.pdf"
    assert _describe_file(path) == "Satish_Resume.pdf in Desktop"


def test_garbled_recipient_is_asked_again_and_spoken_address_is_parsed():
    # Live test: Whisper turned a spoken address into "Erfosht kja ne jupon dhe Gmail".
    engine, _, _ = make_engine([], extra_tools=_gmail_tools([]))
    engine.reply("I want to draft an email")
    assert engine.reply("Erfosht kja në jupon dhe Gmail").text.startswith("I didn't catch who")
    engine.reply("satish dot wagle at gmail dot com")
    assert engine._email_flows["voice"].to == "satish.wagle@gmail.com"


def test_close_leaves_the_email_and_runs_as_a_command():
    # Live test: "Close the Gmail right now" got "new email or reply?" again and again.
    # (the test registry has open_app, not close_app: any registered tool proves the command ran)
    # no Gmail tools: more tools switch on the router, which would eat the scripted reply
    engine, _, log = make_engine([call("open_app", name="notepad"), say("Done.")])
    engine.reply("write an email to Smarika")
    engine.reply("Close the Gmail right now.")
    assert not engine.email_flow_waiting("voice") and log == [("open_app", {"name": "notepad"})]


def _drafted(calls, *writer_outputs):
    from brain.llm import FakeBackend
    engine, _, _ = make_engine([], extra_tools=_gmail_tools(calls))
    engine._writer = FakeBackend([LLMResponse(content=c) for c in writer_outputs])
    for said in ["write an email to Satish Wagle", "new", "Introduction", "say I am looking for a job", "no"]:
        engine.reply(said)
    return engine


def test_changing_the_recipient_redrafts_and_asks_again():
    # Live test: the user asked mid-way to send it to a different person and nothing could change it.
    calls = []
    engine = _drafted(calls, "Subject: Introduction\n\nI am looking for a job.",
                      "To: Smarika Koirala\nSubject: Introduction\n\nI am looking for a job.")
    again = engine.reply("change the recipient to Smarika Koirala")
    assert [c[0] for c in calls] == ["gmail_compose", "gmail_discard_draft", "gmail_compose"]
    assert calls[-1][1]["to"] == "Smarika Koirala" and again.needs_confirmation
    engine.reply("yes, send it")
    assert calls[-1] == ("gmail_send", {}) and not engine.email_flow_waiting("voice")


def test_changing_only_the_body_keeps_the_recipient():
    calls = []
    engine = _drafted(calls, "Subject: Introduction\n\nI am looking for a job.",
                      "To: Satish Wagle\nSubject: Introduction\n\nI am looking for a software job.")
    engine.reply("make it say a software job")
    assert [c[0] for c in calls] == ["gmail_compose", "gmail_compose"]       # no discard
    assert calls[-1][1] == {"to": "", "subject": "Introduction", "body": "I am looking for a software job."}


def test_unclear_new_or_reply_is_asked_only_once():
    engine, _, _ = make_engine([], extra_tools=_gmail_tools([]))
    engine.reply("compose an email to Smarika")
    engine.reply("hmm")
    assert engine.reply("whatever").text == "What's the subject?"
