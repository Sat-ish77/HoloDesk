# Graph Report - holodesk-brain-v3  (2026-11-13)

## Corpus Check
- 72 files · ~60,979 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 2, .example 1, .jsonl 1)

## Summary
- 1137 nodes · 2676 edges · 71 communities (41 shown, 30 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 321 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f34b8bbb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ToolError
- make_engine
- TaskAgent
- test_speech.py
- playwright_controller.py
- MemoryStore
- browser.py
- MemoryAgent
- 🧠 HoloDesk
- time
- ReplyEngine
- OrchestratorAgent
- Risk
- Database
- main.py
- OpenAIClient
- VoiceAssistantThread
- GestureDetector
- Tool
- engine.py
- GroqClient
- engine.py
- task_agent.py
- on_startup
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
- build_engine
- files.py
- HoloDesk Project State
- HoloDesk (brain v3)
- Handoff round 3: interact with any page element, not per-site selectors
- browser_play_pause
- Handoff: stitch Playwright browser tools into brain v3
- config.py
- monitors.py
- Handoff round 2: browser reliability (after the first live voice test)

## God Nodes (most connected - your core abstractions)
1. `ToolContext` - 73 edges
2. `ToolError` - 72 edges
3. `TaskAgent` - 55 edges
4. `make_engine()` - 45 edges
5. `Risk` - 43 edges
6. `ReplyEngine` - 36 edges
7. `call()` - 35 edges
8. `MemoryStore` - 34 edges
9. `build_default_registry()` - 33 edges
10. `FakePage` - 32 edges

## Surprising Connections (you probably didn't know these)
- `Step 7: Screen Vision (NEW)` --references--> `analyze_screen()`  [INFERRED]
  PROJECT_STATE.md → app/main.py
- `1. Goal (the user's words, condensed)` --references--> `Reply`  [INFERRED]
  docs/HANDOFF_ROUND3.md → brain/engine.py
- `3. Fixes I (Claude Opus, local) made. Please review them and suggest improvements` --references--> `browser_open_result()`  [INFERRED]
  docs/HANDOFF_ROUND2.md → brain/tools/browser.py
- `Nepali` --references--> `get_datetime()`  [INFERRED]
  docs/BRAIN.md → brain/tools/knowledge.py
- `Not verified yet` --references--> `speak()`  [INFERRED]
  docs/BRAIN.md → app/main.py

## Import Cycles
- None detected.

## Communities (71 total, 30 thin omitted)

### Community 0 - "ToolError"
Cohesion: 0.06
Nodes (75): _find_tool(), build(), click_ui_element(), clipboard(), close_app(), _find_window(), _focus(), focus_window() (+67 more)

### Community 1 - "make_engine"
Cohesion: 0.05
Nodes (77): Reply, FakeBackend, FallbackBackend, LLMBackend, LLMError, LLMResponse, make_backend(), OpenAICompatibleBackend (+69 more)

### Community 3 - "test_speech.py"
Cohesion: 0.09
Nodes (24): CloudSTT, _drop_prompt_echo(), _env(), _looks_like_silence(), _prompt(), transcribe_command(), clean_for_speech(), _env() (+16 more)

### Community 4 - "playwright_controller.py"
Cohesion: 0.05
Nodes (48): job(), job(), browser_call(), click(), click_best(), close_tab(), _debug_port(), _debug_port_open() (+40 more)

### Community 5 - "MemoryStore"
Cohesion: 0.11
Nodes (15): MemoryStore, _norm(), _overlap(), redact(), redact_obj(), tokenize(), test_audit_keeps_structure_and_redacts_values(), test_facts_dedupe_and_update() (+7 more)

### Community 6 - "browser.py"
Cohesion: 0.14
Nodes (36): browser_back(), browser_click_text(), browser_close_tab(), browser_new_tab(), browser_open_result(), job(), browser_press_key(), browser_read_page() (+28 more)

### Community 8 - "🧠 HoloDesk"
Cohesion: 0.08
Nodes (23): Adding a tool, Architecture, First run, HoloDesk Brain v3, Nepali, Phone setup (5 minutes), Running 24/7, What changed (+15 more)

### Community 9 - "time"
Cohesion: 0.07
Nodes (10): _done(), TelegramBridge, TelegramSender, _acquire_lock(), main(), _setup_logging(), Monitors, main() (+2 more)

### Community 10 - "ReplyEngine"
Cohesion: 0.26
Nodes (3): _describe(), ReplyEngine, _t()

### Community 12 - "Risk"
Cohesion: 0.11
Nodes (16): _answers_pending_confirmation(), classify_shell(), Decision, _first_word(), is_no(), is_yes(), _norm_reply(), PendingAction (+8 more)

### Community 14 - "main.py"
Cohesion: 0.09
Nodes (7): analyze_screen(), _run(), ask_ai(), setup_transparent_window(), speak(), stop_ai_speech(), record_tts_finished()

### Community 18 - "Tool"
Cohesion: 0.18
Nodes (3): Tool, ToolRegistry, Review of fixes A, B, C

### Community 19 - "engine.py"
Cohesion: 0.31
Nodes (3): main(), run_case(), stub_registry()

### Community 20 - "GroqClient"
Cohesion: 0.15
Nodes (3): ChatAgent, ChatResult, GroqClient

### Community 22 - "engine.py"
Cohesion: 0.21
Nodes (4): detect_language(), _json(), _parse_facts(), test_language_detection()

### Community 24 - "on_startup"
Cohesion: 0.32
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
Cohesion: 0.07
Nodes (10): FakeContext, FakeKeyboard, FakePage, tab(), test_click_text_clicks_and_reports(), test_open_result_clicks_the_nth_video_and_reports_it(), test_open_result_falls_back_to_generic_results_on_other_sites(), test_open_result_says_when_there_are_too_few_or_none() (+2 more)

### Community 54 - "build_default_registry"
Cohesion: 0.11
Nodes (27): Risk, _click_risk(), build_default_registry(), facebook_page(), test_a_failed_open_is_an_error_and_never_a_second_chrome(), test_back_goes_back_and_says_when_it_cannot(), test_click_like_is_confirmed_and_uses_the_like_button_not_text(), test_clicks_that_send_post_or_buy_need_confirmation() (+19 more)

### Community 55 - "build_engine"
Cohesion: 0.20
Nodes (5): connected_controller(), FakeBrowser, test_controller_follows_the_tab_the_user_is_looking_at(), test_controller_rebuilds_a_dead_connection_instead_of_failing(), test_controller_reports_an_error_when_chrome_cannot_come_back()

### Community 57 - "build_engine"
Cohesion: 0.23
Nodes (7): build_engine(), _lazy(), _make_screen_agent(), _make_task_agent(), BrainConfig, load_config(), test_brain_is_off_without_a_key()

### Community 59 - "files.py"
Cohesion: 0.28
Nodes (7): on_click(), gmail_page(), sendable_page(), test_draft_reply_needs_gmail_and_an_open_email(), test_draft_reply_opens_reply_writes_and_does_not_send(), test_send_reports_sent_only_when_gmail_confirms(), test_type_fills_a_named_field_reads_it_back_and_can_press_enter()

### Community 61 - "HoloDesk Project State"
Cohesion: 0.12
Nodes (16): API Keys Required, Architecture Decisions Made (Permanent Cuts), Current Status: Step 7 COMPLETE, Dependencies (requirement.txt), File Structure (Current), For New Chat Session, Gestures, Gestures + Voice Commands (Full List) (+8 more)

### Community 62 - "HoloDesk (brain v3)"
Cohesion: 0.50
Nodes (3): HoloDesk (brain v3), Rules, Save tokens

### Community 64 - "Handoff round 3: interact with any page element, not per-site selectors"
Cohesion: 0.25
Nodes (7): _join_spelled(), 1. Goal (the user's words, condensed), 4. What I (Claude Opus, local) fixed this round. Review briefly, 5. Done means, 6. Your notes for the next round, Handoff round 3: interact with any page element, not per-site selectors, test_spelled_names_are_joined()

### Community 65 - "browser_play_pause"
Cohesion: 0.24
Nodes (10): job(), browser_play_pause(), job(), _gmail(), _host(), _like(), _on_screen(), _site() (+2 more)

### Community 66 - "Handoff: stitch Playwright browser tools into brain v3"
Cohesion: 0.29
Nodes (5): 1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop), 2. Known problems (not your task unless listed in section 3), 4. Done means, 5. How the user will test on Windows, Handoff: stitch Playwright browser tools into brain v3

### Community 67 - "config.py"
Cohesion: 0.53
Nodes (4): _env(), _env_bool(), _env_ids(), _env_int()

### Community 70 - "Handoff round 2: browser reliability (after the first live voice test)"
Cohesion: 0.33
Nodes (5): 1. What happened in the live voice test (2026-11-13, Windows, real mic), 3. Fixes I (Claude Opus, local) made. Please review them and suggest improvements, 4. Done means, 5. Your notes for the next round, Handoff round 2: browser reliability (after the first live voice test)

## Knowledge Gaps
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskAgent` connect `TaskAgent` to `browser.py`, `main.py`, `OpenAIClient`, `GroqClient`, `task_agent.py`, `.open_web_in_browser`, `build_engine`, `._schedule_power_action`, `._resolve_app_name`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Are the 53 inferred relationships involving `ToolContext` (e.g. with `_find_tool()` and `ReplyEngine`) actually correct?**
  _`ToolContext` has 53 INFERRED edges - model-reasoned connections that need verification._
- **Should `ToolError` be split into smaller, more focused modules?**
  _Cohesion score 0.06282828282828283 - nodes in this community are weakly interconnected._
- **Why does `ToolContext` connect `ToolError` to `browser_play_pause`, `make_engine`, `browser.py`, `ReplyEngine`, `build_default_registry`, `engine.py`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `ToolError` (e.g. with `ReplyEngine` and `_key_risk()`) actually correct?**
  _`ToolError` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `make_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.05080091533180778 - nodes in this community are weakly interconnected._
- **Why does `MemoryStore` connect `MemoryStore` to `make_engine`, `ReplyEngine`, `engine.py`, `engine.py`, `build_default_registry`, `build_engine`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._