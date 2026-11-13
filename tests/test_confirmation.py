"""Confirmation handling, using the exact phrases that looped in the live test."""
import pytest

from agents.orchestrator import OrchestratorAgent
from agents.task_agent import TaskAgent
from core.queues import voice_reply_queue


@pytest.mark.parametrize("said,expected", [
    ("yes", "yes"),
    ("yes cancel the chrome.", "yes"),                      # first signal wins
    ("yes you can confirm it. yes.", "yes"),
    ("please close the chrome yes close the chrome", "yes"),
    ("sure, go ahead", "yes"),
    ("cancel", "cancel"),
    ("no, leave it alone", "cancel"),
    ("never mind", "cancel"),
    ("did you close the chrome or not", None),              # a question, not an answer
    ("open notepad", None),
])
def test_confirm_signal_reads_whole_sentences(said, expected):
    assert TaskAgent.confirm_signal(said) == expected


@pytest.fixture
def armed():
    task = TaskAgent()
    ran = []
    task._set_pending_confirm(
        "Close chrome? Say yes to confirm, or cancel to stop.",
        lambda: ran.append(True) or {"success": True, "response": "Closed chrome."},
        kind="close",
    )
    orch = OrchestratorAgent(agents={"task_agent": task})
    while not voice_reply_queue.empty():
        voice_reply_queue.get_nowait()
    return task, orch, ran


def test_sentence_yes_runs_the_action_once_and_does_not_re_ask(armed, monkeypatch):
    monkeypatch.setenv("HOLODESK_OPENAI_PLANNER_ENABLED", "0")
    task, orch, ran = armed

    orch._process("yes cancel the chrome.", source="voice")

    assert ran == [True]
    reply = voice_reply_queue.get(timeout=1)["text"]
    assert "Say yes to confirm" not in reply   # this was the infinite loop
    assert task.pending_confirmation() is None


def test_unrelated_answer_re_asks_instead_of_arming_a_second_confirmation(armed, monkeypatch):
    monkeypatch.setenv("HOLODESK_OPENAI_PLANNER_ENABLED", "0")
    task, orch, ran = armed

    orch._process("did you close the chrome or not", source="voice")

    assert ran == []
    assert "still need a yes or a cancel" in voice_reply_queue.get(timeout=1)["text"]
    assert task.pending_confirmation() is not None  # same one, not a new one


def test_stale_confirmation_is_dropped(armed):
    task, _, _ = armed
    task._pending_confirm["ts"] -= TaskAgent.PENDING_TTL_SECONDS + 1
    assert task.pending_confirmation() is None


def test_long_request_goes_to_the_brain_not_keyword_matching(monkeypatch):
    """The live failure: a 30-word complaint matched "facebook" and opened facebook."""
    from types import SimpleNamespace as NS

    monkeypatch.setenv("HOLODESK_OPENAI_PLANNER_ENABLED", "0")
    seen = []
    brain = NS(available=True, execute=lambda action, context: seen.append(context["raw"]) or {"success": True, "response": "I'll open all three in one window."})
    task = TaskAgent()
    orch = OrchestratorAgent(agents={"task_agent": task, "brain_agent": brain})
    while not voice_reply_queue.empty():
        voice_reply_queue.get_nowait()

    said = ("open two it's the different tab i don't understand why you open so many chrome tab "
            "i just want one chrome tab and in there i want facebook gmail and instagram open")
    orch._process(said, source="voice")

    assert seen == [said]
    assert voice_reply_queue.get(timeout=1)["text"] == "I'll open all three in one window."


def test_short_command_still_takes_the_fast_deterministic_path(monkeypatch):
    from types import SimpleNamespace as NS

    monkeypatch.setenv("HOLODESK_OPENAI_PLANNER_ENABLED", "0")
    seen = []
    brain = NS(available=True, execute=lambda action, context: seen.append(context["raw"]) or {"success": True, "response": "brain"})
    opened = []
    task = TaskAgent()
    monkeypatch.setattr(task, "open_app", lambda name: opened.append(name) or {"success": True, "response": f"Opening {name}."})
    orch = OrchestratorAgent(agents={"task_agent": task, "brain_agent": brain})
    while not voice_reply_queue.empty():
        voice_reply_queue.get_nowait()

    orch._process("open notepad", source="voice")

    assert seen == [] and opened == ["notepad"]
