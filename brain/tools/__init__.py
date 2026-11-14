"""Built-in tool catalogue."""

from __future__ import annotations

from . import browser, computer, desktop, files, knowledge, system
from .registry import Tool, ToolContext, ToolError, ToolRegistry  # noqa: F401


def build_default_registry(task_agent_provider=lambda: None,
                           screen_agent_provider=lambda: None) -> ToolRegistry:
    """Everything HoloDesk can do, as tools.

    The providers are callables so the heavy Windows-only agents are created
    lazily, the first time a tool that needs them actually runs."""
    registry = ToolRegistry()
    registry.register_all(system.build())
    registry.register_all(files.build())
    registry.register_all(desktop.build(task_agent_provider, screen_agent_provider))
    registry.register_all(knowledge.build())
    registry.register_all(browser.build())
    registry.register_all(computer.build())
    return registry
