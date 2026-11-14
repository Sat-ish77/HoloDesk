from brain.email_flow import wants_email
from brain.policy import Risk
from brain.tools.registry import Tool
from helpers import make_engine


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
    engine._writer = FakeBackend([])                             # any call to it would fail the test
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
