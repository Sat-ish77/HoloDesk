import pytest

from brain.llm import LLMError, OpenAICompatibleBackend
from brain.tools import build_default_registry
from brain.tools.registry import ToolContext
from helpers import call, make_engine, say


class Resp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code, self._p, self.headers = status, payload or {}, headers or {}
        self.text = str(payload)

    def json(self):
        return self._p


class FakeHTTP:
    def __init__(self, replies):
        self.replies, self.payloads = list(replies), []

    def post(self, url, headers=None, json=None, timeout=None):
        self.payloads.append(json)
        return self.replies.pop(0)


def _completion(message):
    return Resp(200, {"choices": [{"message": message}]})


def test_backend_parses_tool_calls_including_double_encoded_arguments():
    http = FakeHTTP([_completion({"content": None, "tool_calls": [
        {"id": "a", "function": {"name": "open_app", "arguments": '{"name": "chrome"}'}},
        {"id": "b", "function": {"name": "open_app", "arguments": '"{\\"name\\": \\"edge\\"}"'}},
        {"id": "c", "function": {"name": "open_app", "arguments": "{not json"}},
    ]})])
    backend = OpenAICompatibleBackend("https://x/v1", "k", "m", session=http)
    out = backend.chat([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    assert [c.arguments for c in out.tool_calls[:2]] == [{"name": "chrome"}, {"name": "edge"}]
    assert out.tool_calls[2].parse_error
    assert http.payloads[0]["tool_choice"] == "auto"


def test_backend_retries_rate_limits_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    http = FakeHTTP([Resp(429, {"error": "slow down"}), _completion({"content": "hello"})])
    backend = OpenAICompatibleBackend("https://x/v1", "k", "m", session=http)
    assert backend.chat([{"role": "user", "content": "hi"}]).content == "hello"


def test_backend_raises_on_client_error():
    backend = OpenAICompatibleBackend("https://x/v1", "k", "m", session=FakeHTTP([Resp(400, {"error": "bad"})]))
    with pytest.raises(LLMError):
        backend.chat([{"role": "user", "content": "hi"}])


def test_orchestrator_uses_brain_and_falls_back_when_llm_is_down(monkeypatch):
    monkeypatch.setenv("HOLODESK_BRAIN", "0")          # do not build a real engine
    from agents.orchestrator import OrchestratorAgent
    from core.queues import voice_reply_queue

    orch = OrchestratorAgent(agents={})
    assert orch.brain is None and orch._try_brain("open chrome") is False

    orch.brain, _, log = make_engine([call("open_app", name="chrome"), say("Chrome is open.")])
    assert orch._try_brain("open chrome") is True
    assert voice_reply_queue.get_nowait() == {"text": "Chrome is open.", "prompt": True}
    assert log == [("open_app", {"name": "chrome"})]

    def down(messages, tools):
        raise LLMError("offline")
    orch.brain, _, _ = make_engine([down])
    assert orch._try_brain("open chrome") is False      # legacy regex router takes over


def test_brain_is_off_without_a_key(monkeypatch):
    from brain.bootstrap import build_engine
    from brain.config import BrainConfig
    monkeypatch.delenv("HOLODESK_BRAIN", raising=False)
    cfg = BrainConfig()
    cfg.llm_api_key = "gsk_your_groq_key_here"
    assert build_engine(cfg=cfg) is None


def test_system_tools_work_on_this_machine():
    pytest.importorskip("psutil")
    r = build_default_registry()
    status = r.get("system_status").handler({}, ToolContext())
    assert status["ok"] and 0 <= status["ram_percent"] <= 100 and status["disk_free_gb"] >= 0
    procs = r.get("list_processes").handler({"limit": 5}, ToolContext())
    assert 1 <= len(procs["processes"]) <= 5


def test_llm_router_picks_are_offered(monkeypatch):
    engine, backend, _ = make_engine([say('{"tools": ["take_screenshot"]}'), say("ok")])
    engine.cfg.llm_router, engine.cfg.max_tools_per_request = True, 2
    engine.reply("मेरो स्क्रिन देखाऊ")
    offered = {t["function"]["name"] for t in backend.calls[1]["tools"]}
    assert "take_screenshot" in offered
    assert backend.calls[0]["model"] == engine.cfg.fast_model      # router uses the cheap tier


def test_llm_router_failure_falls_back_to_keywords():
    def down(messages, tools):
        raise LLMError("offline")
    engine, backend, _ = make_engine([down, say("ok")])
    engine.cfg.llm_router, engine.cfg.max_tools_per_request = True, 2
    assert engine.reply("hello").text == "ok"


def test_models_are_auto_selected_from_what_the_provider_serves():
    from brain.config import BrainConfig
    from brain.llm import resolve_models

    class Provider:
        default_model = "auto"

        def list_models(self):
            return ["whisper-large-v3", "openai/gpt-oss-20b", "qwen/qwen3.8-27b",
                    "meta-llama/llama-4-scout-17b-16e-instruct"]

    cfg, provider = BrainConfig(), Provider()
    cfg.chat_model = cfg.fast_model = cfg.vision_model = ""
    resolve_models(cfg, provider)
    assert cfg.chat_model == "qwen/qwen3.8-27b"          # best chat model that exists
    assert cfg.fast_model == "openai/gpt-oss-20b"
    assert cfg.vision_model.startswith("meta-llama/llama-4-scout")
    assert provider.default_model == cfg.chat_model

    pinned = BrainConfig()
    pinned.chat_model, pinned.fast_model, pinned.vision_model = "my-model", "", ""
    resolve_models(pinned, Provider())
    assert pinned.chat_model == "my-model"               # an explicit choice always wins


def test_models_fall_back_when_the_provider_lists_nothing():
    from brain.config import CHAT_MODEL_PREFERENCES, BrainConfig
    from brain.llm import resolve_models
    cfg = BrainConfig()
    cfg.chat_model = cfg.fast_model = cfg.vision_model = ""
    resolve_models(cfg, object())
    assert cfg.chat_model == CHAT_MODEL_PREFERENCES[0] and cfg.fast_model and cfg.vision_model == ""
