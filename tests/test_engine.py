from brain.llm import LLMError, LLMResponse, ToolCall
from brain.engine import detect_language
from helpers import call, make_engine, say


def test_plain_answer_needs_no_tool():
    engine, _, log = make_engine([say("Kathmandu is the capital of Nepal.")])
    reply = engine.reply("what is the capital of nepal")
    assert reply.ok and "Kathmandu" in reply.text and log == []


def test_tool_call_then_answer():
    engine, backend, log = make_engine([call("open_app", name="chrome"), say("Chrome is open.")])
    reply = engine.reply("open chrome")
    assert log == [("open_app", {"name": "chrome"})]
    assert reply.text == "Chrome is open."
    assert reply.tool_calls == [{"name": "open_app", "arguments": {"name": "chrome"}, "ok": True}]
    # The tool result was fed back to the model on the second turn.
    assert backend.calls[1]["messages"][-1]["role"] == "tool"


def test_danger_waits_for_yes_and_runs_only_after():
    engine, _, log = make_engine([call("delete_path", path="~/old.txt")])
    reply = engine.reply("delete old.txt")
    assert reply.needs_confirmation and "delete ~/old.txt" in reply.text
    assert log == []                       # nothing ran yet
    done = engine.reply("yes")
    assert log == [("delete_path", {"path": "~/old.txt"})]
    assert done.ok and done.text.startswith("Done")


def test_danger_cancel_runs_nothing():
    engine, _, log = make_engine([call("delete_path", path="~/old.txt")])
    engine.reply("delete old.txt")
    reply = engine.reply("cancel")
    assert log == [] and "cancel" in reply.text.lower()
    # And a later bare "yes" has nothing to confirm: it goes to the model.
    assert engine.policy.get_pending("voice") is None


def test_confirmation_in_nepali():
    engine, _, log = make_engine([call("delete_path", path="~/old.txt")])
    asked = engine.reply("पुरानो फाइल मेटाऊ")
    assert asked.needs_confirmation and "अनुमति" in asked.text
    engine.reply("हुन्छ")
    assert log == [("delete_path", {"path": "~/old.txt"})]


def test_confirmation_is_per_source():
    engine, _, log = make_engine([call("delete_path", path="~/a.txt"), say("ok")])
    engine.reply("delete a.txt", source="telegram")
    engine.reply("yes", source="voice")     # someone at the desk says yes to something else
    assert log == []                        # the phone's request was not confirmed by voice


def test_new_request_drops_pending_confirmation():
    engine, _, log = make_engine([call("delete_path", path="~/a.txt"),
                                  call("open_app", name="notepad"), say("Opened.")])
    engine.reply("delete a.txt")
    engine.reply("actually open notepad")
    assert log == [("open_app", {"name": "notepad"})]
    assert engine.policy.get_pending("voice") is None


def test_blocked_tool_never_runs_and_model_is_told():
    engine, backend, log = make_engine([call("format_disk"), say("I can't do that.")])
    reply = engine.reply("format my disk")
    assert log == [] and reply.text == "I can't do that."
    assert "blocked by the safety policy" in backend.calls[1]["messages"][-1]["content"]


def test_kill_switch_refuses_everything():
    engine, _, log = make_engine([call("open_app", name="chrome")])
    engine.halt()
    reply = engine.reply("open chrome")
    assert log == [] and "halted" in reply.text.lower()
    engine.resume()
    engine.backend.script = [call("open_app", name="chrome"), say("Open.")]
    engine.reply("open chrome")
    assert log == [("open_app", {"name": "chrome"})]


def test_halt_clears_pending_confirmation():
    engine, _, log = make_engine([call("delete_path", path="~/a.txt")])
    engine.reply("delete a.txt")
    engine.halt()
    engine.resume()
    engine.backend.script = [say("Nothing to confirm.")]
    engine.reply("yes")
    assert log == []


def test_tool_failure_is_reported_to_model_not_hidden():
    engine, backend, _ = make_engine([call("broken"), say("That failed: it broke.")])
    reply = engine.reply("do the broken thing")
    assert '"ok": false' in backend.calls[1]["messages"][-1]["content"]
    assert reply.tool_calls[0]["ok"] is False


def test_unknown_tool_gets_error_not_crash():
    engine, backend, log = make_engine([call("launch_rocket"), say("I can't do that yet.")])
    reply = engine.reply("launch a rocket")
    assert log == [] and "unknown tool" in backend.calls[1]["messages"][-1]["content"]
    assert reply.ok


def test_duplicate_call_is_not_executed_twice():
    engine, _, log = make_engine([call("open_app", name="chrome"), call("open_app", name="chrome"),
                                  say("Chrome is open.")])
    engine.reply("open chrome")
    assert log == [("open_app", {"name": "chrome"})]


def test_malformed_arguments_are_bounced_back():
    bad = LLMResponse(tool_calls=[ToolCall(id="x", name="open_app", arguments={},
                                           parse_error="could not decode arguments")])
    engine, _, log = make_engine([bad, call("open_app", name="chrome"), say("Open.")])
    engine.reply("open chrome")
    assert log == [("open_app", {"name": "chrome"})]


def test_llm_down_is_honest_and_not_ok():
    def boom(messages, tools):
        raise LLMError("network error")
    engine, _, log = make_engine([boom])
    reply = engine.reply("open chrome")
    assert not reply.ok and reply.tool_calls == [] and log == []


def test_runaway_loop_stops_at_max_turns():
    script = [call("open_app", name=f"app{i}") for i in range(10)]
    engine, _, log = make_engine(script)
    reply = engine.reply("open everything")
    assert len(log) == engine.cfg.max_turns and not reply.ok


def test_photos_are_collected_for_the_phone():
    engine, _, _ = make_engine([call("take_screenshot"), say("Here it is.")])
    reply = engine.reply("show me my screen", source="telegram")
    assert reply.photos == ["/tmp/s.png"]


def test_conversation_is_shared_across_sources():
    engine, backend, _ = make_engine([say("Your build is at 40%."), say("Still 40%.")])
    engine.reply("how is the build going", source="voice")
    engine.reply("and now?", source="telegram")
    history = [m["content"] for m in backend.calls[1]["messages"]]
    assert "how is the build going" in history and "Your build is at 40%." in history


def test_memory_reaches_the_system_prompt():
    engine, backend, _ = make_engine([say("नमस्ते!")])
    engine.memory.add_fact("directives", "Always answer briefly.")
    engine.memory.add_fact("user", "The user's sister is named Asha.")
    engine.reply("hello there my friend")
    system = backend.calls[0]["messages"][0]["content"]
    assert "Always answer briefly." in system and "Asha" in system


def test_find_tool_expands_the_catalogue_mid_conversation():
    engine, backend, log = make_engine([call("find_tool", query="screenshot"), say("ok")])
    engine.cfg.max_tools_per_request = 2          # force routing to hide most tools
    engine.reply("hmm")
    first = {t["function"]["name"] for t in backend.calls[0]["tools"]}
    second = {t["function"]["name"] for t in backend.calls[1]["tools"]}
    assert "take_screenshot" not in first and "take_screenshot" in second


def test_learns_facts_from_json_reply():
    engine, _, _ = make_engine([say('Sure: {"facts": [{"branch": "user", "fact": "The user studies at UNT."},'
                                    ' {"branch": "bogus", "fact": ""}]}')])
    assert engine.learn_from("i study at unt by the way", "Noted.") == 1
    assert engine.memory.facts("user")[0]["fact"] == "The user studies at UNT."


def test_language_detection():
    assert detect_language("क्रोम खोल") == "ne"
    assert detect_language("malai chrome khol deu") == "ne-roman"
    assert detect_language("ke cha") == "ne-roman"
    assert detect_language("open chrome and go to youtube") == "en"
    assert detect_language("what is on my screen") == "en"


def test_english_request_is_told_to_answer_in_english():
    engine, _, _ = make_engine([])
    assert "Reply in English" in engine._system_prompt("voice", "en")


def test_fallback_answers_when_primary_fails():
    from brain.llm import FakeBackend, FallbackBackend

    def groq_down(messages, tools):
        raise LLMError("HTTP 429: rate limited")

    backend = FallbackBackend(FakeBackend([groq_down]), FakeBackend([LLMResponse(content="from openai")]))
    assert backend.chat([{"role": "user", "content": "hi"}]).content == "from openai"


def test_fallback_skips_primary_after_a_failure():
    from brain.llm import FakeBackend, FallbackBackend

    def groq_down(messages, tools):
        raise LLMError("HTTP 429: tokens per day")

    # The primary has only one scripted reply, so a second call to it would fail the test.
    backend = FallbackBackend(FakeBackend([groq_down]),
                              FakeBackend([LLMResponse(content="a"), LLMResponse(content="b")]))
    assert [backend.chat([]).content, backend.chat([]).content] == ["a", "b"]
