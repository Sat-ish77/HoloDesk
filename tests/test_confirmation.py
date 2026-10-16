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
