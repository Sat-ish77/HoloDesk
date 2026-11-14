"""Fixed live smoke test: 6 commands through the real model and real tools.

Run after every change and compare the pass count; a change that lowers it
does not stay. No mic or speakers involved, so it isolates brain + tools.

    python scripts/smoke_test.py
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from brain.bootstrap import build_engine  # noqa: E402
from brain.memory import MemoryStore  # noqa: E402

# (command, tools that count as success; empty = must answer without tools)
CASES = [
    ("how are you today", set()),
    ("open notepad", {"open_app"}),
    ("search model context protocol on google", {"search_in_browser", "open_website", "browser_new_tab"}),
    ("open the first result", {"browser_open_result", "browser_click_ref", "browser_click_text"}),
    ("go back", {"browser_back"}),
    ("what page is this", {"browser_read_page", "browser_snapshot"}),
]


def main() -> int:
    engine = build_engine()
    if engine is None:
        print("brain disabled or no LLM key")
        return 2
    # Fresh memory every run: a second run read the first run's history and
    # answered "Notepad is already open" instead of acting, so runs weren't comparable.
    engine.memory = MemoryStore(":memory:")
    passed = 0
    for text, want in CASES:
        t = time.time()
        reply = engine.reply(text, source="voice")
        secs = time.time() - t
        called = {c["name"] for c in reply.tool_calls if c["ok"]}
        ok = reply.ok and (not reply.tool_calls if not want else bool(called & want))
        passed += ok
        tools = ", ".join(f"{c['name']}{'' if c['ok'] else '(failed)'}" for c in reply.tool_calls) or "-"
        print(f"{'PASS' if ok else 'FAIL'}  {secs:5.1f}s  {text!r:45}  tools: {tools}")
        print(f"       reply: {reply.text[:110]!r}")
    print(f"\nSmoke: {passed}/{len(CASES)} passed  (model: {engine.cfg.chat_model or 'auto'})")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
