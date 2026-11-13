# Graph Report - holodesk  (2026-11-13)

## Corpus Check
- 71 files · ~59,729 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: .example 1, (none) 1, .jsonl 1)

## Summary
- 1128 nodes · 2620 edges · 74 communities (40 shown, 34 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 251 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5d4771c6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ToolContext
- make_engine
- TaskAgent
- test_speech.py
- playwright_controller.py
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
- .ensure_page
- GestureDetector
- gmail.py
- time
- GroqClient
- threading
- time
- memory_agent.py
- startup.py
- 12. Production Checklist — Every Step
- Holodesk v2 full architecture.md
- 5. Agent System — Every Agent Explained
- 4. Threading Model — The Foundation
- FakeLocator
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
- FakePage
- build_default_registry
- connected_controller
- engine.py
- gmail_page
- config.py
- HoloDesk (brain v3)
- open_in_automation_browser
- test_browser_tools.py
- FakeKeyboard
- login_autofill
- _LazyPlaywright
- monitors.py
- tab

## God Nodes (most connected - your core abstractions)
1. `ToolContext` - 70 edges
2. `ToolError` - 66 edges
3. `TaskAgent` - 54 edges
4. `make_engine()` - 45 edges
5. `Risk` - 35 edges
6. `call()` - 35 edges
7. `MemoryStore` - 33 edges
8. `build_default_registry()` - 33 edges
9. `FakePage` - 32 edges
10. `say()` - 30 edges

## Surprising Connections (you probably didn't know these)
- `Step 7: Screen Vision (NEW)` --references--> `analyze_screen()`  [INFERRED]
  PROJECT_STATE.md → app/main.py
- `Nepali` --references--> `get_datetime()`  [INFERRED]
  docs/BRAIN.md → brain/tools/knowledge.py
- `Not verified yet` --references--> `speak()`  [INFERRED]
  docs/BRAIN.md → app/main.py
- `2. Your task (in priority order)` --references--> `open_in_automation()`  [INFERRED]
  docs/HANDOFF_ROUND2.md → brain/tools/browser.py
- `What changed` --references--> `open_in_automation()`  [INFERRED]
  docs/HANDOFF_ROUND2.md → brain/tools/browser.py

## Import Cycles
- None detected.

## Communities (74 total, 34 thin omitted)

### Community 0 - "ToolContext"
Cohesion: 0.06
Nodes (74): _find_tool(), Risk, open_in_automation(), build(), click_ui_element(), clipboard(), close_app(), _find_window() (+66 more)

### Community 1 - "make_engine"
Cohesion: 0.10
Nodes (53): detect_language(), Reply, ToolCall, call(), make_engine(), record(), handler(), say() (+45 more)

### Community 3 - "test_speech.py"
Cohesion: 0.05
Nodes (29): analyze_screen(), _run(), speak(), VoiceAssistantThread, read_tts_state(), CloudSTT, _drop_prompt_echo(), _env() (+21 more)

### Community 4 - "playwright_controller.py"
Cohesion: 0.18
Nodes (16): click_best(), close_tab(), _debug_port_open(), _find_chrome_executable(), _launch_automation_chrome(), list_tabs(), new_tab(), job() (+8 more)

### Community 5 - "MemoryStore"
Cohesion: 0.11
Nodes (15): MemoryStore, _norm(), _overlap(), redact(), redact_obj(), tokenize(), test_audit_keeps_structure_and_redacts_values(), test_facts_dedupe_and_update() (+7 more)

### Community 6 - "Monitors"
Cohesion: 0.11
Nodes (44): browser_back(), browser_click_text(), job(), browser_close_tab(), browser_new_tab(), browser_open_result(), job(), browser_play_pause() (+36 more)

### Community 8 - "🧠 HoloDesk"
Cohesion: 0.08
Nodes (23): Adding a tool, Architecture, First run, HoloDesk Brain v3, Nepali, Phone setup (5 minutes), Running 24/7, What changed (+15 more)

### Community 9 - "TelegramBridge"
Cohesion: 0.11
Nodes (7): _done(), TelegramBridge, TelegramSender, main(), Monitors, test_battery_alert_fires_once_then_rearms(), test_disk_and_sustained_ram_alerts()

### Community 10 - "ReplyEngine"
Cohesion: 0.07
Nodes (10): _describe(), _json(), ReplyEngine, _t(), ToolRegistry, 1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop), 2. Known problems (not your task unless listed in section 3), 4. Done means (+2 more)

### Community 12 - "Risk"
Cohesion: 0.10
Nodes (17): _answers_pending_confirmation(), _parse_facts(), classify_shell(), Decision, _first_word(), is_no(), is_yes(), _norm_reply() (+9 more)

### Community 14 - "main.py"
Cohesion: 0.10
Nodes (3): ask_ai(), setup_transparent_window(), stop_ai_speech()

### Community 16 - ".ensure_page"
Cohesion: 0.16
Nodes (5): _debug_port(), is_enabled(), _is_visible_tab(), PlaywrightController, _visible_page()

### Community 18 - "gmail.py"
Cohesion: 0.20
Nodes (15): job(), job(), click(), is_visible(), _locator(), press_key(), read_text(), type_into() (+7 more)

### Community 19 - "time"
Cohesion: 0.31
Nodes (4): _parse_tool_calls(), main(), run_case(), stub_registry()

### Community 20 - "GroqClient"
Cohesion: 0.16
Nodes (3): ChatAgent, ChatResult, GroqClient

### Community 22 - "time"
Cohesion: 0.16
Nodes (3): _acquire_lock(), _setup_logging(), main()

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

### Community 53 - "FakePage"
Cohesion: 0.13
Nodes (5): FakePage, test_click_text_clicks_and_reports(), test_open_result_falls_back_to_generic_results_on_other_sites(), test_play_pause_falls_back_when_the_key_does_nothing_and_off_youtube(), test_type_never_touches_password_fields()

### Community 54 - "build_default_registry"
Cohesion: 0.12
Nodes (21): build_default_registry(), test_enter_asks_first_unless_it_is_a_search_box(), test_normal_browser_is_used_only_when_automation_is_off(), test_router_finds_the_round_2_tools_in_three_languages(), test_router_finds_the_tools_in_three_languages(), test_sites_and_searches_open_in_the_automation_tab_when_enabled(), test_tools_are_registered_with_the_right_risk(), test_system_tools_work_on_this_machine() (+13 more)

### Community 55 - "connected_controller"
Cohesion: 0.20
Nodes (5): connected_controller(), FakeBrowser, test_controller_follows_the_tab_the_user_is_looking_at(), test_controller_rebuilds_a_dead_connection_instead_of_failing(), test_controller_reports_an_error_when_chrome_cannot_come_back()

### Community 57 - "engine.py"
Cohesion: 0.06
Nodes (35): build_engine(), _lazy(), _make_screen_agent(), _make_task_agent(), BrainConfig, _env(), _env_bool(), _env_ids() (+27 more)

### Community 59 - "gmail_page"
Cohesion: 0.28
Nodes (7): on_click(), gmail_page(), sendable_page(), test_draft_reply_needs_gmail_and_an_open_email(), test_draft_reply_opens_reply_writes_and_does_not_send(), test_send_reports_sent_only_when_gmail_confirms(), test_type_fills_a_named_field_reads_it_back_and_can_press_enter()

### Community 61 - "config.py"
Cohesion: 0.12
Nodes (16): API Keys Required, Architecture Decisions Made (Permanent Cuts), Current Status: Step 7 COMPLETE, Dependencies (requirement.txt), File Structure (Current), For New Chat Session, Gestures, Gestures + Voice Commands (Full List) (+8 more)

### Community 62 - "HoloDesk (brain v3)"
Cohesion: 0.50
Nodes (3): HoloDesk (brain v3), Rules, Save tokens

### Community 64 - "open_in_automation_browser"
Cohesion: 0.29
Nodes (5): browser_call(), open_in_automation_browser(), with_page(), job(), _worker_loop()

### Community 65 - "test_browser_tools.py"
Cohesion: 0.14
Nodes (17): _click_risk(), facebook_page(), test_a_failed_open_is_an_error_and_never_a_second_chrome(), test_back_goes_back_and_says_when_it_cannot(), test_brain_starts_without_playwright_and_reports_it(), test_click_like_is_confirmed_and_uses_the_like_button_not_text(), test_clicks_that_send_post_or_buy_need_confirmation(), test_everything_is_off_until_enabled() (+9 more)

### Community 67 - "login_autofill"
Cohesion: 0.38
Nodes (6): fill_field(), _first_visible(), login_autofill(), password_filled(), pick_saved(), submit()

## Knowledge Gaps
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskAgent` connect `TaskAgent` to `Monitors`, `main.py`, `OpenAIClient`, `GroqClient`, `.open_web_in_browser`, `engine.py`, `._schedule_power_action`, `task_agent.py`, `._resolve_app_name`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `ToolContext` (e.g. with `delete_path()` and `find_files()`) actually correct?**
  _`ToolContext` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Should `ToolContext` be split into smaller, more focused modules?**
  _Cohesion score 0.06320197982105463 - nodes in this community are weakly interconnected._
- **Why does `MemoryAgent` connect `MemoryAgent` to `main.py`, `memory_agent.py`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `ToolError` (e.g. with `_move_risk()` and `_write_risk()`) actually correct?**
  _`ToolError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Should `make_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.0951048951048951 - nodes in this community are weakly interconnected._
- **Why does `make_engine()` connect `make_engine` to `ToolContext`, `test_browser_tools.py`, `MemoryStore`, `ReplyEngine`, `engine.py`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._