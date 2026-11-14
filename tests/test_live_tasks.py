"""The live eval's own plumbing, with a scripted model on the local test pages.
The real run (real model, Gmail, Windows apps) is `python scripts/live_tasks.py`."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from brain.tools import browser as bt
from brain.tools import ui
from browser import playwright_controller as pw
from helpers import call, make_engine, say
from test_ui_loop import act, verdict

spec = importlib.util.spec_from_file_location("live_tasks", Path(__file__).parent.parent / "scripts" / "live_tasks.py")
live = importlib.util.module_from_spec(spec)
sys.modules["live_tasks"] = live          # dataclasses look the module up by name
spec.loader.exec_module(live)
TASK = {task.id: task for task in live.TASKS}


@pytest.fixture()
def harness(tab, monkeypatch):
    monkeypatch.setattr(pw, "open_in_automation_browser",
                        lambda url: tab["page"].goto(url) and {"success": True, "url": url})

    def engine_for(script):
        engine, _, _ = make_engine(script, extra_tools=ui.build() + bt.build())
        engine.cfg.verify, engine.cfg.max_turns = True, 12
        return engine
    return engine_for


def test_there_are_ten_tasks_and_each_line_can_be_filled():
    assert [t.id for t in live.TASKS] == list(range(1, 11))
    run = live.Run(marker="1114", email="me@example.com")
    for task in live.TASKS:
        for line in task.say:
            assert "{" not in run.fill(line), line


def test_like_task_passes_only_when_the_page_shows_it_and_one_question_was_asked(harness):
    engine = harness([call("look"), act("click", "Like"), say("Liked."), verdict('button "Remove Like"')])
    run = live.Run(marker="x")
    ok, detail = live.run_task(engine, TASK[5], run, in_thread=False)
    assert ok and run.asked == 1 and "Remove Like" in detail and len(run.tools) == 2 and run.seconds > 0

    engine = harness([say("I liked it for you.")])          # a model that only says so
    ok, detail = live.run_task(engine, TASK[5], live.Run(marker="x"), in_thread=False)
    assert not ok and "'Like'" in detail


def test_form_task_checks_the_page_and_the_honest_refusal(harness):
    done = json.dumps({"claims_done": False})
    good = [call("look"), act("type", "Country", text="United States"), act("click", "Save changes"),
            say("Country is United States and the changes are saved."), verdict('button "Saved"'),
            call("look"), say("There is no Purple Elephant button on this page.")]
    ok, detail = live.run_task(harness(good), TASK[10], live.Run(marker="x"), in_thread=False)
    assert ok, detail

    liar = good[:5] + [call("look"), act("click", "Next"), say("Clicked it."), say(done)]
    ok, detail = live.run_task(harness(liar), TASK[10], live.Run(marker="x"), in_thread=False)
    assert not ok and "clicked=True" in detail


def test_stop_task_is_judged_on_the_reply_and_what_ran():
    def slow_open(messages, tools):
        import time
        time.sleep(0.4)
        return call("open_app", name="notepad")
    task = live.Task(9, "stop", TASK[9].say, live.check_stopped, steer=(0.2, "stop"))
    run = live.Run(marker="x")
    engine, _, _ = make_engine([slow_open, call("open_app", name="calc"), say("never")])
    ok, detail = live.run_task(engine, task, run)
    assert ok and "0 of 3 apps" in detail and run.steer_at <= run.ended_at       # the step it had chosen never ran


def test_a_task_that_hangs_is_stopped_and_failed():
    def hang(messages, tools):
        import time
        time.sleep(1.2)
        return say("late")
    task = live.Task(1, "hang", ["do something slow"], lambda run: (True, ""), timeout=0.3)
    ok, detail = live.run_task(make_engine([hang])[0], task, live.Run(marker="x"))
    assert not ok and "no answer within" in detail
