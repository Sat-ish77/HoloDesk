"""
HoloDesk brain — the tool-calling core.

    voice / phone / chat  ->  ReplyEngine  ->  tools  ->  the laptop

Nothing in this package imports Windows-only modules at import time, so the
whole brain can be unit-tested on any machine with a fake LLM backend.
"""

from .engine import ReplyEngine, Reply  # noqa: F401
