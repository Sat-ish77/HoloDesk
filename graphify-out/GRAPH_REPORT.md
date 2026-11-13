# Graph Report - holodesk  (2026-11-12)

## Corpus Check
- 70 files · ~55,716 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: .example 1, (none) 1, .jsonl 1)

## Summary
- 1060 nodes · 2464 edges · 64 communities (35 shown, 29 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 256 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e7065c84`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ToolContext
- make_engine
- TaskAgent
- test_speech.py
- VoiceAssistantThread
- MemoryStore
- Monitors
- MemoryAgent
- 🧠 HoloDesk
- TelegramBridge
- ReplyEngine
- OrchestratorAgent
- Risk
- Database
- main.py
- OpenAIClient
- Tool
- GestureDetector
- playwright_controller.py
- engine.py
- GroqClient
- threading
- time
- memory_agent.py
- startup.py
- 12. Production Checklist — Every Step
- Holodesk v2 full architecture.md
- 5. Agent System — Every Agent Explained
- 4. Threading Model — The Foundation
- Handoff: stitch Playwright browser tools into brain v3
- CameraThread
- 14. 3-Week Sprint Plan
- 15. Division of Work
- 7. API Strategy — Which AI for What
- 8. UI Architecture
- 9. Security & Privacy — Technical Guarantees
- 11. Background Processing — What's Real
- 1. What We Are Building
- 3. Full System Architecture
- 6. Data Architecture — Memory & Privacy
- test_browser_tools.py
- build_default_registry
- build_engine
- FakeTelegram
- run_evals.py
- config.py
- HoloDesk (brain v3)

## God Nodes (most connected - your core abstractions)
1. `ToolContext` - 68 edges
2. `ToolError` - 67 edges
3. `TaskAgent` - 53 edges
4. `make_engine()` - 43 edges
5. `Risk` - 38 edges
6. `ReplyEngine` - 36 edges
7. `MemoryStore` - 34 edges
8. `call()` - 34 edges
9. `build_default_registry()` - 30 edges
10. `Tool` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Not verified yet` --references--> `speak()`  [INFERRED]
  docs/BRAIN.md → app/main.py
- `Step 7: Screen Vision (NEW)` --references--> `analyze_screen()`  [INFERRED]
  PROJECT_STATE.md → app/main.py
- `1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop)` --references--> `FallbackBackend`  [INFERRED]
  docs/HANDOFF_PLAYWRIGHT.md → brain/llm.py
- `Nepali` --references--> `get_datetime()`  [INFERRED]
  docs/BRAIN.md → brain/tools/knowledge.py
- `Playwright browser tools (added 2026-11-13; cloud only, never run against a real browser)` --references--> `login_autofill()`  [INFERRED]
  docs/HANDOFF_PLAYWRIGHT.md → browser/playwright_controller.py

## Import Cycles
- None detected.

## Communities (64 total, 29 thin omitted)

### Community 0 - "ToolContext"
Cohesion: 0.05
Nodes (88): _find_tool(), browser_click_text(), browser_open_result(), job(), browser_play_pause(), job(), browser_read_page(), job() (+80 more)

### Community 1 - "make_engine"
Cohesion: 0.06
Nodes (72): Reply, FakeBackend, FallbackBackend, LLMBackend, LLMError, LLMResponse, make_backend(), OpenAICompatibleBackend (+64 more)

### Community 3 - "test_speech.py"
Cohesion: 0.09
Nodes (22): CloudSTT, _drop_prompt_echo(), _env(), _looks_like_silence(), transcribe_command(), clean_for_speech(), _env(), is_nepali() (+14 more)

### Community 4 - "VoiceAssistantThread"
Cohesion: 0.07
Nodes (20): analyze_screen(), _run(), speak(), VoiceAssistantThread, API Keys Required, Architecture Decisions Made (Permanent Cuts), Current Status: Step 7 COMPLETE, Dependencies (requirement.txt) (+12 more)

### Community 5 - "MemoryStore"
Cohesion: 0.11
Nodes (15): MemoryStore, _norm(), _overlap(), redact(), redact_obj(), tokenize(), test_audit_keeps_structure_and_redacts_values(), test_facts_dedupe_and_update() (+7 more)

### Community 6 - "Monitors"
Cohesion: 0.33
Nodes (3): Monitors, test_battery_alert_fires_once_then_rearms(), test_disk_and_sustained_ram_alerts()

### Community 8 - "🧠 HoloDesk"
Cohesion: 0.08
Nodes (22): Adding a tool, Architecture, First run, HoloDesk Brain v3, Phone setup (5 minutes), Running 24/7, What changed, Acknowledgments (+14 more)

### Community 9 - "TelegramBridge"
Cohesion: 0.18
Nodes (3): _done(), TelegramBridge, TelegramSender

### Community 12 - "Risk"
Cohesion: 0.12
Nodes (17): _answers_pending_confirmation(), classify_shell(), Decision, _first_word(), is_no(), is_yes(), _norm_reply(), PendingAction (+9 more)

### Community 14 - "main.py"
Cohesion: 0.09
Nodes (4): ask_ai(), setup_transparent_window(), stop_ai_speech(), record_tts_finished()

### Community 18 - "playwright_controller.py"
Cohesion: 0.06
Nodes (45): job(), job(), browser_call(), click(), click_best(), close_tab(), _debug_port(), _debug_port_open() (+37 more)

### Community 19 - "engine.py"
Cohesion: 0.16
Nodes (5): _describe(), detect_language(), _json(), _parse_facts(), test_language_detection()

### Community 20 - "GroqClient"
Cohesion: 0.17
Nodes (3): ChatAgent, ChatResult, GroqClient

### Community 22 - "time"
Cohesion: 0.15
Nodes (4): _acquire_lock(), main(), _setup_logging(), main()

### Community 24 - "startup.py"
Cohesion: 0.24
Nodes (3): generate_briefing(), _insert_demo_data(), on_startup()

### Community 25 - "12. Production Checklist — Every Step"
Cohesion: 0.18
Nodes (11): 12. Production Checklist — Every Step, Phase 0: Foundation, Phase 1: Data Layer, Phase 2: Face ID, Phase 3: Screen Vision, Phase 4: Calendar, Phase 5: Morning Briefing, Phase 6: Chatbot Panel (+3 more)

### Community 26 - "Holodesk v2 full architecture.md"
Cohesion: 0.22
Nodes (8): 10. Improvement Tracking — How HoloDesk Gets Better, 13. Folder Structure, 16. Tech Stack Reference, 2. Why This Is Different, Ambient Multi-Agent Desktop Co-pilot, HoloDesk v2 — Full Production Architecture, TABLE OF CONTENTS, The One-Line Pitch

### Community 28 - "5. Agent System — Every Agent Explained"
Cohesion: 0.25
Nodes (8): 5.1 OrchestratorAgent — The Brain, 5.2 ScreenAgent — Eyes on Your Desktop, 5.3 MemoryAgent — The Learning System, 5.4 CalendarAgent — Schedule Awareness, 5.5 VoiceAgent — Speech In and Out, 5.6 TaskAgent — Does Things For You, 5.7 ChatAgent — Conversation Handler, 5. Agent System — Every Agent Explained

### Community 29 - "4. Threading Model — The Foundation"
Cohesion: 0.29
Nodes (7): 4.1 Why Threading Matters Here, 4.2 Thread Architecture, 4.3 Queue Architecture, 4.4 Camera Thread — Production Implementation, 4.5 Gesture Detector — The Debounce Fix, 4.6 Main Render Loop — Never Blocks, 4. Threading Model — The Foundation

### Community 30 - "Handoff: stitch Playwright browser tools into brain v3"
Cohesion: 0.33
Nodes (5): 1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop), 2. Known problems (not your task unless listed in section 3), 4. Done means, 5. How the user will test on Windows, Handoff: stitch Playwright browser tools into brain v3

### Community 32 - "14. 3-Week Sprint Plan"
Cohesion: 0.50
Nodes (4): 14. 3-Week Sprint Plan, Week 1 — Solid Foundation (Days 1-7), Week 2 — Power Features (Days 8-14), Week 3 — Polish + Wow Factor (Days 15-21)

### Community 33 - "15. Division of Work"
Cohesion: 0.50
Nodes (4): 15. Division of Work, Friend — Systems + UI, Sat — AI Brain + Agent Logic, Sync Points (Both must attend)

### Community 34 - "7. API Strategy — Which AI for What"
Cohesion: 0.50
Nodes (4): 7.1 Routing Decision Matrix, 7.2 LLM Router With Automatic Fallback, 7.3 Groq Client, 7. API Strategy — Which AI for What

### Community 35 - "8. UI Architecture"
Cohesion: 0.50
Nodes (4): 8.1 Overlay Layer Stack, 8.2 Chatbot Panel Layout, 8.3 3D Stress Object — Pure Math, No Game Engine, 8. UI Architecture

### Community 36 - "9. Security & Privacy — Technical Guarantees"
Cohesion: 0.50
Nodes (4): 9.1 What Leaves the Device, 9.2 Privacy Dashboard, 9.3 Encrypted SQLite (Production), 9. Security & Privacy — Technical Guarantees

### Community 37 - "11. Background Processing — What's Real"
Cohesion: 0.67
Nodes (3): 11.1 Honest Constraints, 11.2 The Solution: Analysis on Wake, 11. Background Processing — What's Real

### Community 38 - "1. What We Are Building"
Cohesion: 0.67
Nodes (3): 1. What We Are Building, The core experience:, What makes this genuinely novel:

### Community 39 - "3. Full System Architecture"
Cohesion: 0.67
Nodes (3): 3.1 Bird's Eye View, 3.2 Data Flow Principles, 3. Full System Architecture

### Community 40 - "6. Data Architecture — Memory & Privacy"
Cohesion: 0.67
Nodes (3): 6.1 SQLite Schema, 6.2 Thread-Safe Database Wrapper, 6. Data Architecture — Memory & Privacy

### Community 53 - "test_browser_tools.py"
Cohesion: 0.06
Nodes (22): facebook_page(), on_click(), FakeKeyboard, FakeLocator, FakePage, gmail_page(), sendable_page(), tab() (+14 more)

### Community 54 - "build_default_registry"
Cohesion: 0.11
Nodes (30): build(), delete_path(), find_files(), list_directory(), move_path(), _move_risk(), open_path(), read_text_file() (+22 more)

### Community 55 - "build_engine"
Cohesion: 0.24
Nodes (7): build_engine(), _lazy(), _make_screen_agent(), _make_task_agent(), BrainConfig, load_config(), test_brain_is_off_without_a_key()

### Community 59 - "run_evals.py"
Cohesion: 0.36
Nodes (3): main(), run_case(), stub_registry()

### Community 61 - "config.py"
Cohesion: 0.53
Nodes (4): _env(), _env_bool(), _env_ids(), _env_int()

### Community 62 - "HoloDesk (brain v3)"
Cohesion: 0.50
Nodes (3): HoloDesk (brain v3), Rules, Save tokens

## Knowledge Gaps
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskAgent` connect `TaskAgent` to `main.py`, `OpenAIClient`, `GroqClient`, `build_engine`, `.open_web_in_browser`, `._schedule_power_action`, `task_agent.py`, `._resolve_app_name`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Are the 48 inferred relationships involving `ToolContext` (e.g. with `_find_tool()` and `ReplyEngine`) actually correct?**
  _`ToolContext` has 48 INFERRED edges - model-reasoned connections that need verification._
- **Should `ToolContext` be split into smaller, more focused modules?**
  _Cohesion score 0.053562653562653564 - nodes in this community are weakly interconnected._
- **Why does `ToolError` connect `ToolContext` to `make_engine`, `ReplyEngine`, `Tool`, `engine.py`, `test_browser_tools.py`, `build_default_registry`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `ToolError` (e.g. with `ReplyEngine` and `_move_risk()`) actually correct?**
  _`ToolError` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `make_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.05843913368185213 - nodes in this community are weakly interconnected._
- **Why does `OrchestratorAgent` connect `OrchestratorAgent` to `make_engine`, `threading`, `main.py`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._