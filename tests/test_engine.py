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
    assert reply.tool_calls == [{"name": "open_app", "arguments": {"name": "chrome"}, "ok": True, "risk": "act"}]
    # The tool result was fed back to the model on the second turn.
    assert backend.calls[1]["messages"][-1]["role"] == "tool"


def test_danger_waits_for_yes_then_the_same_task_carries_on():
    # Before, "yes" ran the step and answered from a template: the model never
    # saw the result, so nothing was checked and a multi-step task stopped there.
    engine, backend, log = make_engine([call("delete_path", path="~/old.txt"),
                                        call("open_app", name="explorer"), say("Deleted it and opened Explorer.")])
    reply = engine.reply("delete old.txt and then open explorer")
    assert reply.needs_confirmation and "delete ~/old.txt" in reply.text
    assert log == []                       # nothing ran yet
    done = engine.reply("yes")
    assert log == [("delete_path", {"path": "~/old.txt"}), ("open_app", {"name": "explorer"})]
    assert done.ok and done.text == "Deleted it and opened Explorer."
    seen = backend.calls[1]["messages"]    # the model got the result of the confirmed step
    assert seen[-1]["role"] == "tool" and "delete_path done" in seen[-1]["content"]
    assert seen[1]["content"].startswith("delete old.txt")          # same conversation, not a new one


def test_words_other_than_yes_steer_the_held_task():
    engine, backend, log = make_engine([call("delete_path", path="~/old.txt"),
                                        call("delete_path", path="~/older.txt")])
    engine.reply("delete old.txt")
    asked = engine.reply("not that one, the older one")
    assert log == [] and asked.needs_confirmation and "older.txt" in asked.text
    sent = backend.calls[1]["messages"]
    assert "NOT RUN" in sent[-2]["content"] and sent[-1] == {"role": "user", "content": "not that one, the older one"}


def test_steps_after_a_held_one_in_the_same_turn_are_answered_not_run():
    from brain.llm import LLMResponse, ToolCall
    both = LLMResponse(tool_calls=[ToolCall("a", "delete_path", {"path": "~/x"}), ToolCall("b", "open_app", {"name": "n"})])
    engine, backend, log = make_engine([both, say("Deleted.")])
    engine.reply("delete x and open n")
    engine.reply("yes")
    assert log == [("delete_path", {"path": "~/x"})]
    tools = [m for m in backend.calls[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tools] == ["a", "b"] and "NOT RUN" in tools[1]["content"]


def test_danger_cancel_runs_nothing():
    engine, _, log = make_engine([call("delete_path", path="~/old.txt")])
    engine.reply("delete old.txt")
    reply = engine.reply("cancel")
    assert log == [] and "cancel" in reply.text.lower()
    # And a later bare "yes" has nothing to confirm: it goes to the model.
    assert engine.policy.get_pending("voice") is None


def test_confirmation_in_nepali():
    engine, _, log = make_engine([call("delete_path", path="~/old.txt"), say("मेटाएँ।")])
    asked = engine.reply("पुरानो फाइल मेटाऊ")
    assert asked.needs_confirmation and "अनुमति" in asked.text
    engine.reply("हुन्छ")
    assert log == [("delete_path", {"path": "~/old.txt"})]


def test_confirmation_is_per_source():
    engine, _, log = make_engine([call("delete_path", path="~/a.txt"), say("ok")])
    engine.reply("delete a.txt", source="telegram")
    engine.reply("yes", source="voice")     # someone at the desk says yes to something else
    assert log == []                        # the phone's request was not confirmed by voice


def test_a_new_request_instead_of_yes_does_not_run_the_held_step():
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


def test_shelved_tools_are_off_the_menu_until_find_tool_brings_them_in():
    from brain.tools.registry import Tool
    rare = Tool("list_processes", "List running processes.", lambda a, c: {"ok": True}, shelf=True)
    engine, backend, log = make_engine([call("find_tool", query="running processes"), say("ok")], extra_tools=[rare])
    engine.reply("hmm")
    first = {t["function"]["name"] for t in backend.calls[0]["tools"]}
    second = {t["function"]["name"] for t in backend.calls[1]["tools"]}
    assert "open_app" in first and "list_processes" not in first and "list_processes" in second


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


def test_claimed_action_without_a_tool_is_challenged():
    # Voice test: "I've scrolled down the page for you." with no tool call.
    engine, _, log = make_engine([say("I've opened Notepad for you."),
                                  call("open_app", name="notepad"), say("Notepad is open.")])
    reply = engine.reply("open notepad")
    assert log == [("open_app", {"name": "notepad"})]
    assert reply.text == "Notepad is open."


def test_plain_chat_is_not_challenged():
    engine, _, log = make_engine([say("I'm doing well, thanks for asking!")])
    assert engine.reply("how are you").text == "I'm doing well, thanks for asking!"


def test_spelled_names_are_joined():
    from brain.engine import _join_spelled
    assert _join_spelled("search S-M-A-R-I-K-A K-O-I-R-A-L-A") == "search Smarika Koirala"
    assert _join_spelled("open a new tab") == "open a new tab"


def test_a_promise_with_no_tool_call_is_challenged_even_after_other_tools():
    # Voice test: "...I still need to find the Reply button. Let me check again." then silence.
    engine, _, log = make_engine([call("system_status"), say("Let me check again."),
                                  call("open_app", name="gmail"), say("Gmail is open.")])
    reply = engine.reply("open my mail")
    assert [name for name, _ in log] == ["system_status", "open_app"] and reply.text == "Gmail is open."
    engine, _, _ = make_engine([say("Let me know which video you'd like to open.")])
    assert engine.reply("play something").text.startswith("Let me know")        # a question back is fine


def test_only_the_newest_view_of_the_screen_stays_in_context():
    from brain.tools.registry import Tool
    views = iter(["VIEW-ONE", "VIEW-TWO"])
    act = Tool("click", "Click.", lambda a, c: {"ok": True, "message": f"clicked {a['ref']}", "view": next(views)})
    engine, backend, _ = make_engine([call("click", ref="e1"), call("click", ref="e2"), say("done")], extra_tools=[act])
    engine.reply("click twice")
    sent = " ".join(str(m.get("content")) for m in backend.calls[2]["messages"])
    assert "VIEW-TWO" in sent and "VIEW-ONE" not in sent and "older view removed" in sent
    assert "clicked e1" in sent                     # the result itself stays; only the old map goes


def test_a_confirmed_action_that_failed_can_be_retried_once_without_asking_again():
    # Voice test: one Like needed three confirmations because each retry asked again.
    from brain.policy import Risk
    from brain.tools.registry import Tool
    results = iter([{"ok": False, "error": "did not show as liked"}, {"ok": True}, {"ok": True}])
    like = Tool("like_post", "Like the post.", lambda a, c: next(results), risk=Risk.DANGER,
                summarize=lambda a: "like the post")
    engine, _, _ = make_engine([call("like_post"), say("It did not take."), call("like_post"), say("Liked now."),
                                call("like_post")], extra_tools=[like])
    assert engine.reply("like this post").needs_confirmation
    failed = engine.reply("yes")                                        # confirmed, ran, failed
    assert failed.text == "It did not take." and failed.tool_calls[-1]["ok"] is False
    retried = engine.reply("it didn't work, try again")
    assert not retried.needs_confirmation and retried.text == "Liked now."
    assert engine.reply("like it again").needs_confirmation             # a success is not a standing approval


def test_short_spelled_runs_stay_upper_case():
    from brain.engine import _join_spelled
    assert _join_spelled("I study at U-N-T") == "I study at UNT"


def test_unanswered_request_from_history_is_not_replayed():
    # Live test: the last run was killed before its reply was saved, and the next
    # "hello" re-ran that old search.
    engine, backend, log = make_engine([say("Hi! How can I help?")])
    engine.memory.add_turn("voice", "user", "search difference between MCP and API keys")
    reply = engine.reply("hey hello how you doing")
    sent = [m["content"] for m in backend.calls[0]["messages"]]
    assert not any("MCP and API keys" in c for c in sent)
    assert log == [] and reply.text == "Hi! How can I help?"


def test_gone_back_without_a_tool_is_challenged():
    # Smoke test: "I've gone back to the Google search results" with no tool call.
    from brain.engine import _CLAIMS_ACTION
    assert _CLAIMS_ACTION.search("I've gone back to the Google search results.")


# ---------------------------------------------------------------- steering
def test_stop_said_mid_task_ends_it_between_steps():
    engine, _, log = make_engine([])

    def first(messages, tools):
        engine.steer("okay stop")                   # the user speaks while step 1 runs
        return call("open_app", name="one")
    engine.backend.script = [first, call("open_app", name="two"), say("never said")]
    reply = engine.reply("open one, then two")
    assert log == [("open_app", {"name": "one"})]
    assert reply.text.startswith("Stopped") and len(engine.backend.script) == 2


def test_new_words_mid_task_override_the_plan():
    engine, backend, log = make_engine([])

    def first(messages, tools):
        engine.steer("no, open paint instead")
        return call("open_app", name="notepad")
    engine.backend.script = [first, call("open_app", name="paint"), say("Paint is open.")]
    assert engine.reply("open notepad").text == "Paint is open."
    said = backend.calls[1]["messages"][-1]
    assert said["role"] == "user" and "no, open paint instead" in said["content"] and "newest instruction" in said["content"]


def test_halt_mid_task_stops_the_loop_and_stale_steering_is_dropped():
    engine, _, log = make_engine([])

    def first(messages, tools):
        engine.halt()
        return call("system_status")
    engine.backend.script = [first, call("open_app", name="x")]
    assert engine.reply("status then open x").text.startswith("Stopped") and log == []     # halted: nothing runs
    engine.resume()
    engine.steer("stop")                            # said after the task ended: must not kill the next one
    engine.backend.script = [say("Hello.")]
    assert engine.reply("hello there").text == "Hello."


def test_stop_words():
    from brain.engine import _is_stop
    for text in ["stop", "Stop.", "okay stop", "please stop it", "cancel", "रोक", "ruk"]:
        assert _is_stop(text), text
    for text in ["don't stop", "open the bus stop page", "stop sign pictures", "continue"]:
        assert not _is_stop(text), text


# ---------------------------------------------------------------- the check
def checked_engine(script, screen, act_result=None):
    """An engine whose registry has look + an acting tool, with the check on."""
    from brain.tools.registry import Tool
    tools = [Tool("look", "See the screen.", lambda a, c: {"ok": True, "view": screen["text"]}),
             Tool("save", "Save.", lambda a, c: dict(act_result or {"ok": True, "message": "pressed save"}),
                  risk=__import__("brain.policy", fromlist=["Risk"]).Risk.ACT)]
    engine, backend, log = make_engine(script, extra_tools=tools)
    engine.cfg.verify = True
    return engine, backend


def verdict(**fields):
    import json
    return say(json.dumps({"claims_done": True, "confirmed": True, "evidence": "", "missing": "", **fields}))


def test_done_is_confirmed_by_a_quote_found_on_the_screen():
    screen = {"text": 'window "notes.txt - Notepad"\n  u1 Document "Text editor"'}
    engine, backend = checked_engine([call("save"), say("Saved as notes.txt."), verdict(evidence="notes.txt - Notepad")], screen)
    reply = engine.reply("save this as notes.txt")
    assert reply.verified is True and reply.evidence == "notes.txt - Notepad" and reply.text == "Saved as notes.txt."
    asked = backend.calls[2]
    assert asked["model"] == engine.cfg.fast_model and "SCREEN NOW" in asked["messages"][1]["content"]


def test_a_quote_that_is_not_on_the_screen_does_not_count():
    screen = {"text": 'window "Untitled - Notepad"'}
    engine, _ = checked_engine([call("save"), say("Saved as notes.txt."), verdict(evidence="notes.txt - Notepad"),
                                say("It is still untitled; the save did not happen."),
                                verdict(claims_done=False)], screen)
    reply = engine.reply("save this as notes.txt")
    assert reply.text == "It is still untitled; the save did not happen." and reply.verified is None


def test_an_unconfirmed_answer_gets_one_more_round_then_says_so():
    screen = {"text": 'window "Untitled - Notepad"'}
    engine, backend = checked_engine([call("save"), say("Saved."), verdict(confirmed=False, missing="the file name in the title"),
                                      say("Saved."), verdict(confirmed=False, missing="still untitled")], screen)
    reply = engine.reply("save this")
    assert reply.verified is False and reply.text == "Saved. I could not confirm this on the screen."
    nudge = backend.calls[3]["messages"][-1]["content"]
    assert "the file name in the title" in nudge and "do not repeat an action" in nudge
    assert not engine.backend.script                 # two checks at most, never a third round


def test_no_check_for_chat_for_read_only_tasks_or_when_the_checker_fails():
    from brain.llm import LLMError
    screen = {"text": "x"}
    engine, backend = checked_engine([say("Kathmandu.")], screen)
    assert engine.reply("capital of nepal?").verified is None and len(backend.calls) == 1
    engine, backend = checked_engine([call("look"), say("It shows x.")], screen)
    assert engine.reply("what is on screen").verified is None and len(backend.calls) == 2

    def down(messages, tools):
        raise LLMError("offline")
    engine, _ = checked_engine([call("save"), say("Saved."), down], screen)
    reply = engine.reply("save")
    assert reply.text == "Saved." and reply.verified is None        # the check never blocks a reply


# ---------------------------------------------------------------- tools that ask mid-way
def test_a_tool_that_needs_an_ok_is_held_by_the_same_policy_and_resumed():
    from brain.tools.registry import Tool
    seen = []

    def eye_and_mouse(args, ctx):
        seen.append(dict(args))
        if not args.get("approved"):
            return {"ok": True, "needs_ok": "click Send in the mail window"}
        return {"ok": True, "message": "Sent."}
    engine, backend, _ = make_engine([call("computer_task", goal="send the mail"), say("It is sent.")],
                                     extra_tools=[Tool("computer_task", "Eye and mouse.", eye_and_mouse)])
    asked = engine.reply("send the mail with the mouse")
    assert asked.needs_confirmation and "click Send in the mail window" in asked.text
    assert engine.policy.get_pending("voice").tool == "computer_task"
    assert engine.reply("yes").text == "It is sent."
    assert seen == [{"goal": "send the mail"}, {"goal": "send the mail", "approved": "click Send in the mail window"}]
