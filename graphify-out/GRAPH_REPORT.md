# Graph Report - holodesk-brain-v3  (2026-11-12)

## Corpus Check
- 63 files · ~49,528 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 2, .example 1, .jsonl 1)

## Summary
- 896 nodes · 2056 edges · 53 communities (28 shown, 25 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 203 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `82707982`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ToolContext
- make_engine
- TaskAgent
- test_speech.py
- VoiceAssistantThread
- MemoryStore
- test_remote.py
- MemoryAgent
- 🧠 HoloDesk
- time
- ReplyEngine
- OrchestratorAgent
- Risk
- Database
- main.py
- OpenAIClient
- Tool
- GestureDetector
- Policy
- engine.py
- GroqClient
- threading
- logging
- task_agent.py
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

## God Nodes (most connected - your core abstractions)
1. `ToolError` - 59 edges
2. `ToolContext` - 59 edges
3. `TaskAgent` - 53 edges
4. `make_engine()` - 40 edges
5. `ReplyEngine` - 36 edges
6. `MemoryStore` - 34 edges
7. `Risk` - 32 edges
8. `call()` - 31 edges
9. `Reply` - 27 edges
10. `Tool` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Nepali` --references--> `get_datetime()`  [INFERRED]
  docs/BRAIN.md → brain/tools/knowledge.py
- `Not verified yet` --references--> `speak()`  [INFERRED]
  docs/BRAIN.md → app/main.py
- `Step 7: Screen Vision (NEW)` --references--> `analyze_screen()`  [INFERRED]
  PROJECT_STATE.md → app/main.py
- `1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop)` --references--> `FallbackBackend`  [INFERRED]
  docs/HANDOFF_PLAYWRIGHT.md → brain/llm.py
- `Not verified yet` --references--> `search_in_browser()`  [INFERRED]
  docs/BRAIN.md → brain/tools/desktop.py

## Import Cycles
- None detected.

## Communities (53 total, 25 thin omitted)

### Community 0 - "ToolContext"
Cohesion: 0.05
Nodes (85): _find_tool(), build(), click_ui_element(), clipboard(), close_app(), _find_window(), _focus(), focus_window() (+77 more)

### Community 1 - "make_engine"
Cohesion: 0.07
Nodes (58): BrainConfig, Reply, FakeBackend, FallbackBackend, LLMBackend, LLMError, LLMResponse, make_backend() (+50 more)

### Community 3 - "test_speech.py"
Cohesion: 0.09
Nodes (22): CloudSTT, _drop_prompt_echo(), _env(), _looks_like_silence(), transcribe_command(), clean_for_speech(), _env(), is_nepali() (+14 more)

### Community 4 - "VoiceAssistantThread"
Cohesion: 0.06
Nodes (21): analyze_screen(), _run(), speak(), VoiceAssistantThread, read_tts_state(), API Keys Required, Architecture Decisions Made (Permanent Cuts), Current Status: Step 7 COMPLETE (+13 more)

### Community 5 - "MemoryStore"
Cohesion: 0.11
Nodes (15): MemoryStore, _norm(), _overlap(), redact(), redact_obj(), tokenize(), test_audit_keeps_structure_and_redacts_values(), test_facts_dedupe_and_update() (+7 more)

### Community 6 - "test_remote.py"
Cohesion: 0.13
Nodes (19): Monitors, drain(), FakeResponse, FakeSTT, FakeTelegram, make_bridge(), test_battery_alert_fires_once_then_rearms(), test_dangerous_action_from_phone_waits_for_yes() (+11 more)

### Community 8 - "🧠 HoloDesk"
Cohesion: 0.08
Nodes (23): Adding a tool, Architecture, First run, HoloDesk Brain v3, Nepali, Phone setup (5 minutes), Running 24/7, What changed (+15 more)

### Community 9 - "time"
Cohesion: 0.06
Nodes (19): build_engine(), _lazy(), _make_screen_agent(), _make_task_agent(), _env(), _env_bool(), _env_ids(), _env_int() (+11 more)

### Community 10 - "ReplyEngine"
Cohesion: 0.15
Nodes (4): _describe(), ReplyEngine, _t(), 1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop)

### Community 12 - "Risk"
Cohesion: 0.20
Nodes (12): _answers_pending_confirmation(), classify_shell(), Decision, _first_word(), is_no(), is_yes(), _norm_reply(), Risk (+4 more)

### Community 14 - "main.py"
Cohesion: 0.10
Nodes (3): ask_ai(), setup_transparent_window(), stop_ai_speech()

### Community 18 - "Policy"
Cohesion: 0.23
Nodes (5): PendingAction, Policy, test_audit_never_raises(), test_decisions(), test_pending_expires()

### Community 19 - "engine.py"
Cohesion: 0.16
Nodes (5): ChatResult, detect_language(), _json(), _parse_facts(), test_language_detection()

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
Nodes (5): 2. Known problems (not your task unless listed in section 3), 3. The task: Playwright browser tools, 4. Done means, 5. How the user will test on Windows, Handoff: stitch Playwright browser tools into brain v3

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

## Knowledge Gaps
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskAgent` connect `TaskAgent` to `time`, `main.py`, `OpenAIClient`, `GroqClient`, `task_agent.py`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `ToolError` (e.g. with `ReplyEngine` and `_move_risk()`) actually correct?**
  _`ToolError` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `ToolContext` be split into smaller, more focused modules?**
  _Cohesion score 0.054993678887484194 - nodes in this community are weakly interconnected._
- **Why does `MemoryAgent` connect `MemoryAgent` to `main.py`, `task_agent.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 41 inferred relationships involving `ToolContext` (e.g. with `_find_tool()` and `ReplyEngine`) actually correct?**
  _`ToolContext` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Should `make_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.06511746680286006 - nodes in this community are weakly interconnected._
- **Why does `ReplyEngine` connect `ReplyEngine` to `ToolContext`, `make_engine`, `MemoryStore`, `time`, `Risk`, `Tool`, `Policy`, `engine.py`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._