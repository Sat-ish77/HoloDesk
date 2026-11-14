"""
Tool registry.

A tool is a name, a description the model reads, a JSON schema for its
arguments, a risk tier and a Python handler. Adding a capability to HoloDesk
means registering one more Tool. No routing code changes anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ..policy import Risk


class ToolError(Exception):
    """Raise from a handler for an expected failure the model should see."""


@dataclass
class ToolContext:
    source: str = "voice"            # "voice" | "telegram" | "text"
    cfg: Any = None
    memory: Any = None
    notify: Callable[[str], None] | None = None   # push a message to the phone
    send_photo: Callable[[str, str], None] | None = None
    engine: Any = None
    # Tools offered to the model for THIS request (name -> Tool). find_tool
    # adds shelved ones mid-conversation.
    offered: dict = field(default_factory=dict)


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[[dict, ToolContext], Any]
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    risk: Risk | Callable[[dict], Risk] = Risk.SAFE
    # Extra words (English, Nepali, Romanized Nepali) find_tool matches on.
    keywords: tuple[str, ...] = ()
    # Human-readable one-liner for the confirmation question.
    summarize: Callable[[dict], str] | None = None
    # Off the default menu; the model reaches it through find_tool. For rare
    # tools, so every step doesn't pay for their schemas.
    shelf: bool = False

    def risk_for(self, args: dict) -> Risk:
        if callable(self.risk):
            try:
                return self.risk(args)
            except Exception:
                return Risk.DANGER
        return self.risk

    def summary_for(self, args: dict) -> str:
        if self.summarize:
            try:
                return self.summarize(args)
            except Exception:
                pass
        shown = ", ".join(f"{k}={str(v)[:80]!r}" for k, v in (args or {}).items())
        return f"{self.name}({shown})"

    def schema(self) -> dict:
        params = dict(self.parameters)
        params.setdefault("type", "object")
        params.setdefault("properties", {})
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": params}}


_TOKEN_RE = re.compile(r"[^\s\.,!?;:।\"'()\[\]{}<>/\\|_\-]+")


def tokenize(text: str) -> list[str]:
    """Language-agnostic tokenizer. Unlike \\w+, it keeps Devanagari words
    whole (matras are combining marks and would otherwise split words)."""
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", tool.name):
            raise ValueError(f"bad tool name: {tool.name!r}")
        self._tools[tool.name] = tool

    def register_all(self, tools: list[Tool]) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def all(self) -> list[Tool]:
        return [self._tools[n] for n in self.names()]

    def __len__(self) -> int:
        return len(self._tools)

    def rank(self, query: str) -> list[tuple[float, Tool]]:
        """All tools scored by keyword overlap with the query, best first."""
        q = set(tokenize(query))
        scored: list[tuple[float, Tool]] = []
        for t in self.all():
            name_tokens = set(tokenize(t.name.replace("_", " ")))
            kw_tokens: set[str] = set()
            for kw in t.keywords:
                kw_tokens.update(tokenize(kw))
            desc_tokens = set(tokenize(t.description))
            score = (3.0 * len(q & name_tokens) + 2.0 * len(q & kw_tokens)
                     + 0.5 * len(q & desc_tokens))
            scored.append((score, t))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        return scored

    def menu(self) -> list[Tool]:
        """What the model is offered on every step. No per-request routing:
        a router that guessed wrong hid the tool the task needed."""
        return [t for t in self.all() if not t.shelf]
