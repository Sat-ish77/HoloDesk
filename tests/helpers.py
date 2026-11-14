"""Shared test fixtures: a tiny registry of fake tools and a scripted LLM."""

from brain.config import BrainConfig
from brain.engine import ReplyEngine
from brain.llm import FakeBackend, LLMResponse, ToolCall
from brain.memory import MemoryStore
from brain.policy import Risk
from brain.tools.registry import Tool, ToolError, ToolRegistry


def call(tool_name, /, **arguments):
    return LLMResponse(tool_calls=[ToolCall(id=f"c_{tool_name}", name=tool_name, arguments=arguments)])


def say(text):
    return LLMResponse(content=text)


def make_engine(script, extra_tools=(), memory=True):
    log = []

    def record(name, result=None, fail=False):
        def handler(args, ctx):
            log.append((name, dict(args)))
            if fail:
                raise ToolError("it broke")
            return result if result is not None else {"ok": True, "message": f"{name} done"}
        return handler

    registry = ToolRegistry()
    registry.register_all([
        Tool("open_app", "Open an application.", record("open_app"), risk=Risk.ACT),
        Tool("system_status", "Laptop status.", record("system_status", {"ok": True, "cpu_percent": 7})),
        Tool("delete_path", "Delete a file.", record("delete_path"), risk=Risk.DANGER,
             summarize=lambda a: f"delete {a.get('path')}"),
        Tool("format_disk", "Never allowed.", record("format_disk"), risk=Risk.BLOCKED),
        Tool("broken", "Always fails.", record("broken", fail=True)),
        Tool("take_screenshot", "Screenshot.", record("take_screenshot", {"ok": True, "photo_path": "/tmp/s.png"})),
        *extra_tools,
    ])
    cfg = BrainConfig()
    cfg.verify = False      # the screen check costs one scripted model reply; tests that want it switch it on
    cfg.max_turns = 5
    backend = FakeBackend(script)
    store = MemoryStore(":memory:") if memory else None
    cfg.memory_enabled = memory
    engine = ReplyEngine(registry, backend=backend, cfg=cfg, memory=store, background_learning=False)
    return engine, backend, log
