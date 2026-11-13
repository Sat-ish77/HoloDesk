import queue
from types import SimpleNamespace as NS

import pytest

import agents.brain_agent as brain_mod
from agents.brain_agent import BrainAgent
from agents.orchestrator import OrchestratorAgent
from core.queues import voice_reply_queue


def tool_use(name, args, id_="t1"):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", name=name, input=args, id=id_)])


def text(msg):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=msg)])


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


class FakeTask:
    def __init__(self, open_ok=True):
        self.open_ok = open_ok
        self.opened = []
        self.scrolls = 0
        self._pending_confirm = None

    def open_app(self, name):
        self.opened.append(name)
        return {"success": self.open_ok, "response": f"Opening {name}." if self.open_ok else f"No app called {name}."}

    def scroll(self, direction, amount=5):
        self.scrolls += 1
        return {"success": True, "response": ""}

    def pending_confirmation(self):
        return self._pending_confirm

    def _set_pending_confirm(self, message, fn, kind="generic"):
        self._pending_confirm = {"message": message, "fn": fn, "kind": kind}
        return {"success": True, "response": message}

    def shutdown_with_confirm(self):
        return self._set_pending_confirm("About to shut down. Say yes or cancel.", lambda: None, kind="shutdown")

    def __getattr__(self, name):  # tools the tests don't exercise
        return lambda *a, **k: {"success": True, "response": name}


@pytest.fixture(autouse=True)
def no_waits(monkeypatch):
    monkeypatch.setattr(brain_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(brain_mod, "_get_active_window", lambda: ("notepad.exe", "Untitled - Notepad"))


def test_runs_tool_and_returns_model_text():
    client = FakeClient([tool_use("open_app", {"name": "notepad"}), text("Notepad is open.")])
    task = FakeTask()
    result = BrainAgent(task, client=client).run("open notepad please")

    assert task.opened == ["notepad"]
    assert result["response"] == "Notepad is open."
    assert result["tool_log"][0]["active_window"] == "Untitled - Notepad"
    # The observation went back to the model as a tool_result for the same id.
    tool_result = client.calls[1]["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and tool_result["is_error"] is False


def test_pending_confirmation_stops_loop_and_returns_gate_message():
    client = FakeClient([tool_use("shutdown", {}), text("should never be requested")])
    task = FakeTask()
    result = BrainAgent(task, client=client).run("turn the laptop off")

    assert len(client.calls) == 1
    assert result["response"] == "About to shut down. Say yes or cancel."
    assert task._pending_confirm["kind"] == "shutdown"


def test_step_cap_stops_runaway_loop():
    client = FakeClient([tool_use("scroll", {"direction": "down"})])
    task = FakeTask()
    result = BrainAgent(task, client=client).run("keep scrolling forever")

    assert task.scrolls == BrainAgent.MAX_TOOL_CALLS
    assert result["response"].startswith("I stopped after")


def test_claim_without_any_tool_is_replaced():
    client = FakeClient([text("I've opened Notepad for you.")])
    result = BrainAgent(FakeTask(), client=client).run("open notepad")
    assert "didn't take any action" in result["response"]


def test_failed_tool_is_reported_even_if_model_omits_it():
    client = FakeClient([tool_use("open_app", {"name": "blender"}), text("Blender is ready.")])
    result = BrainAgent(FakeTask(open_ok=False), client=client).run("open blender")
    assert "open_app failed: No app called blender." in result["response"]
    assert result["success"] is False


def test_press_keys_rejects_unknown_and_gates_delete():
    task = FakeTask()
    brain = BrainAgent(task, client=FakeClient([text("x")]))
    assert brain._press_keys(["ctrl", "banana"])["success"] is False
    obs = brain._call_tool("press_keys", {"keys": ["shift", "delete"]})
    assert obs.get("pending_confirmation") is True
    assert task._pending_confirm["kind"] == "keys"


def test_no_api_key_means_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert BrainAgent(FakeTask()).available is False


def test_orchestrator_routes_unmatched_command_to_brain(monkeypatch):
    monkeypatch.setenv("HOLODESK_OPENAI_PLANNER_ENABLED", "0")
    seen = []
    brain = NS(available=True, execute=lambda action, context: seen.append(context["raw"]) or {"success": True, "response": "brain reply"})
    orch = OrchestratorAgent(agents={"brain_agent": brain, "task_agent": FakeTask()})
    while not voice_reply_queue.empty():
        voice_reply_queue.get_nowait()

    orch._process("what's the capital of peru", source="voice")

    assert seen == ["what's the capital of peru"]
    assert voice_reply_queue.get(timeout=1)["text"] == "brain reply"


def test_silent_success_is_not_reported_as_failure():
    assert OrchestratorAgent._merge_results([{"success": True, "response": ""}]) == "Done."
    assert OrchestratorAgent._merge_results([{"success": False, "response": ""}]) == "That didn't work."


@pytest.fixture
def memory(tmp_path, monkeypatch):
    import agents.memory_agent as mem_mod
    from storage.db import Database

    monkeypatch.setattr(mem_mod, "db", Database(tmp_path / "facts.db"))
    return mem_mod.MemoryAgent()


def test_remember_then_recall(memory):
    assert memory.remember("My advisor is Dr. Lee")["success"] is True
    memory.remember("I went shopping on Friday")  # "pin" inside a word must not trip the secret filter
    assert memory.recall("who is my advisor") == ["My advisor is Dr. Lee"]
    assert "I went shopping on Friday" in memory.recall("shopping")


def test_secrets_are_never_stored(memory):
    for secret in ("my gmail password is hunter2", "card 4111 1111 1111 1111", "api key sk-abc123", "my pin is 4821"):
        assert memory.remember(secret)["success"] is False, secret
    assert memory.recall("password") == []


def test_brain_puts_recalled_facts_after_the_cache_breakpoint(memory):
    memory.remember("My advisor is Dr. Lee")
    client = FakeClient([text("Your advisor is Dr. Lee.")])
    BrainAgent(FakeTask(), memory_agent=memory, client=client).run("who is my advisor")

    system = client.calls[0]["system"]
    assert "cache_control" in system[0] and "Dr. Lee" not in system[0]["text"]
    assert "Dr. Lee" in system[1]["text"] and "cache_control" not in system[1]
