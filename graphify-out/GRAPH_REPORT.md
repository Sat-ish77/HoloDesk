# Graph Report - holodesk  (2026-11-13)

## Corpus Check
- 75 files · ~70,013 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: .example 1, (none) 1, .jsonl 1)

## Summary
- 1242 nodes · 2993 edges · 77 communities (49 shown, 28 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 358 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `173499bc`
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
- engine.py
- memory_agent.py
- startup.py
- 12. Production Checklist — Every Step
- Holodesk v2 full architecture.md
- daemon.py
- 5. Agent System — Every Agent Explained
- 4. Threading Model — The Foundation
- FakeLocator
- _like
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
- test_page_map.py
- engine.py
- test_integration.py
- gmail_page
- test_remote.py
- LLMError
- HoloDesk (brain v3)
- browser_snapshot
- browser.py
- FakeKeyboard
- test_browser_tools.py
- _pw
- policy.py
- registry.py
- _join_spelled
- ask_chatbot
- FakeKeyboard
- tab
- record

## God Nodes (most connected - your core abstractions)
1. `ToolError` - 80 edges
2. `ToolContext` - 80 edges
3. `TaskAgent` - 54 edges
4. `make_engine()` - 52 edges
5. `call()` - 43 edges
6. `Risk` - 38 edges
7. `build()` - 35 edges
8. `build_default_registry()` - 35 edges
9. `say()` - 35 edges
10. `Reply` - 33 edges

## Surprising Connections (you probably didn't know these)
- `Step 7: Screen Vision (NEW)` --references--> `analyze_screen()`  [INFERRED]
  PROJECT_STATE.md → app/main.py
- `1. Goal (the user's words, condensed)` --references--> `Reply`  [INFERRED]
  docs/HANDOFF_ROUND3.md → brain/engine.py
- `Not verified yet` --references--> `speak()`  [INFERRED]
  docs/BRAIN.md → app/main.py
- `2. Earlier fixes by Claude Opus (from commit messages and diffs only)` --references--> `_join_spelled()`  [INFERRED]
  docs/DESIGN_UI_CONTROL.md → brain/engine.py
- `4. What I (Claude Opus, local) fixed this round. Review briefly` --references--> `_join_spelled()`  [INFERRED]
  docs/HANDOFF_ROUND3.md → brain/engine.py

## Import Cycles
- 2-file cycle: `brain/tools/__init__.py -> brain/tools/browser.py -> brain/tools/__init__.py`
- 3-file cycle: `brain/tools/__init__.py -> brain/tools/desktop.py -> brain/tools/browser.py -> brain/tools/__init__.py`

## Communities (77 total, 28 thin omitted)

### Community 0 - "ToolContext"
Cohesion: 0.06
Nodes (78): _find_tool(), build(), click_ui_element(), clipboard(), close_app(), _find_window(), _focus(), focus_window() (+70 more)

### Community 1 - "make_engine"
Cohesion: 0.19
Nodes (37): Reply, call(), make_engine(), say(), test_send_shows_the_draft_and_waits_for_yes(), test_a_confirmed_action_that_failed_can_be_retried_once_without_asking_again(), test_a_promise_with_no_tool_call_is_challenged_even_after_other_tools(), test_blocked_tool_never_runs_and_model_is_told() (+29 more)

### Community 3 - "test_speech.py"
Cohesion: 0.09
Nodes (24): CloudSTT, _drop_prompt_echo(), _env(), _looks_like_silence(), _prompt(), transcribe_command(), clean_for_speech(), _env() (+16 more)

### Community 4 - "playwright_controller.py"
Cohesion: 0.05
Nodes (46): job(), job(), browser_call(), click(), click_best(), close_tab(), _debug_port(), _debug_port_open() (+38 more)

### Community 5 - "MemoryStore"
Cohesion: 0.14
Nodes (11): MemoryStore, redact(), redact_obj(), test_audit_keeps_structure_and_redacts_values(), test_facts_dedupe_and_update(), test_forget_removes_matching_facts_only(), test_recall_ranks_by_overlap_and_handles_nepali(), test_secrets_are_redacted_before_storage() (+3 more)

### Community 6 - "Monitors"
Cohesion: 0.14
Nodes (31): browser_back(), browser_click_text(), browser_close_tab(), browser_new_tab(), browser_open_result(), job(), browser_play_pause(), browser_press_key() (+23 more)

### Community 8 - "🧠 HoloDesk"
Cohesion: 0.08
Nodes (22): Adding a tool, Architecture, First run, HoloDesk Brain v3, Phone setup (5 minutes), Running 24/7, What changed, Acknowledgments (+14 more)

### Community 9 - "TelegramBridge"
Cohesion: 0.11
Nodes (7): _done(), TelegramBridge, TelegramSender, main(), Monitors, test_battery_alert_fires_once_then_rearms(), test_disk_and_sustained_ram_alerts()

### Community 10 - "ReplyEngine"
Cohesion: 0.14
Nodes (5): _describe(), _json(), ReplyEngine, _t(), 1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop)

### Community 12 - "Risk"
Cohesion: 0.16
Nodes (11): classify_shell(), Decision, PendingAction, Policy, Risk, test_audit_never_raises(), test_catastrophic_commands_are_blocked(), test_changing_commands_need_confirmation() (+3 more)

### Community 14 - "main.py"
Cohesion: 0.09
Nodes (7): analyze_screen(), _run(), ask_ai(), setup_transparent_window(), speak(), stop_ai_speech(), record_tts_finished()

### Community 16 - ".ensure_page"
Cohesion: 0.07
Nodes (18): VoiceAssistantThread, read_tts_state(), API Keys Required, Architecture Decisions Made (Permanent Cuts), Current Status: Step 7 COMPLETE, Dependencies (requirement.txt), File Structure (Current), For New Chat Session (+10 more)

### Community 19 - "time"
Cohesion: 0.16
Nodes (6): ChatResult, _parse_tool_calls(), ToolCall, main(), run_case(), stub_registry()

### Community 22 - "engine.py"
Cohesion: 0.24
Nodes (3): _parse_facts(), LLMBackend, make_backend()

### Community 24 - "startup.py"
Cohesion: 0.24
Nodes (3): generate_briefing(), _insert_demo_data(), on_startup()

### Community 25 - "12. Production Checklist — Every Step"
Cohesion: 0.18
Nodes (11): 12. Production Checklist — Every Step, Phase 0: Foundation, Phase 1: Data Layer, Phase 2: Face ID, Phase 3: Screen Vision, Phase 4: Calendar, Phase 5: Morning Briefing, Phase 6: Chatbot Panel (+3 more)

### Community 26 - "Holodesk v2 full architecture.md"
Cohesion: 0.22
Nodes (8): 10. Improvement Tracking — How HoloDesk Gets Better, 13. Folder Structure, 16. Tech Stack Reference, 2. Why This Is Different, Ambient Multi-Agent Desktop Co-pilot, HoloDesk v2 — Full Production Architecture, TABLE OF CONTENTS, The One-Line Pitch

### Community 27 - "daemon.py"
Cohesion: 0.14
Nodes (3): _acquire_lock(), _setup_logging(), main()

### Community 28 - "5. Agent System — Every Agent Explained"
Cohesion: 0.25
Nodes (8): 5.1 OrchestratorAgent — The Brain, 5.2 ScreenAgent — Eyes on Your Desktop, 5.3 MemoryAgent — The Learning System, 5.4 CalendarAgent — Schedule Awareness, 5.5 VoiceAgent — Speech In and Out, 5.6 TaskAgent — Does Things For You, 5.7 ChatAgent — Conversation Handler, 5. Agent System — Every Agent Explained

### Community 29 - "4. Threading Model — The Foundation"
Cohesion: 0.29
Nodes (7): 4.1 Why Threading Matters Here, 4.2 Thread Architecture, 4.3 Queue Architecture, 4.4 Camera Thread — Production Implementation, 4.5 Gesture Detector — The Debounce Fix, 4.6 Main Render Loop — Never Blocks, 4. Threading Model — The Foundation

### Community 31 - "_like"
Cohesion: 0.14
Nodes (22): job(), job(), _comment_box(), _is_liked(), _like(), _look(), _members(), _outcome() (+14 more)

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
Cohesion: 0.14
Nodes (5): FakePage, test_click_text_clicks_and_reports(), test_open_result_falls_back_to_generic_results_on_other_sites(), test_play_pause_falls_back_when_the_key_does_nothing_and_off_youtube(), test_type_never_touches_password_fields()

### Community 54 - "build_default_registry"
Cohesion: 0.15
Nodes (14): build_default_registry(), test_a_failed_open_is_an_error_and_never_a_second_chrome(), test_router_finds_the_round_2_tools_in_three_languages(), test_sites_and_searches_open_in_the_automation_tab_when_enabled(), home(), test_catalogue_is_valid_for_the_openai_tool_format(), test_file_roundtrip_and_overwrite_needs_confirmation(), test_memory_tools_roundtrip() (+6 more)

### Community 55 - "connected_controller"
Cohesion: 0.16
Nodes (6): connected_controller(), FakeBrowser, test_controller_keeps_its_tab_unless_chrome_is_sure_the_user_moved(), test_controller_notices_a_killed_chrome_that_still_looks_connected(), test_controller_rebuilds_a_dead_connection_instead_of_failing(), test_controller_reports_an_error_when_chrome_cannot_come_back()

### Community 56 - "test_page_map.py"
Cohesion: 0.14
Nodes (23): browser_click_ref(), browser_type_ref(), gmail_compose(), social_comment(), chromium(), ref_of(), snapshot(), tab() (+15 more)

### Community 57 - "engine.py"
Cohesion: 0.18
Nodes (11): build_engine(), _lazy(), _make_screen_agent(), _make_task_agent(), BrainConfig, _env(), _env_bool(), _env_ids() (+3 more)

### Community 58 - "test_integration.py"
Cohesion: 0.13
Nodes (11): OpenAICompatibleBackend, resolve_models(), _completion(), FakeHTTP, Resp, test_backend_parses_tool_calls_including_double_encoded_arguments(), test_backend_raises_on_client_error(), test_backend_retries_rate_limits_then_succeeds() (+3 more)

### Community 59 - "gmail_page"
Cohesion: 0.32
Nodes (7): gmail_page(), sendable_page(), test_draft_reply_needs_gmail_and_an_open_email(), test_draft_reply_opens_reply_writes_and_does_not_send(), on_click(), test_send_reports_sent_only_when_gmail_confirms(), test_type_fills_a_named_field_reads_it_back_and_can_press_enter()

### Community 60 - "test_remote.py"
Cohesion: 0.19
Nodes (16): drain(), FakeResponse, FakeSTT, FakeTelegram, make_bridge(), test_dangerous_action_from_phone_waits_for_yes(), test_empty_allowlist_obeys_nobody(), test_group_chats_are_ignored() (+8 more)

### Community 61 - "LLMError"
Cohesion: 0.16
Nodes (14): FakeBackend, FallbackBackend, LLMError, LLMResponse, test_fallback_answers_when_primary_fails(), groq_down(), test_fallback_skips_primary_after_a_failure(), groq_down() (+6 more)

### Community 62 - "HoloDesk (brain v3)"
Cohesion: 0.50
Nodes (3): HoloDesk (brain v3), Rules, Save tokens

### Community 64 - "browser_snapshot"
Cohesion: 0.15
Nodes (13): browser_snapshot(), job(), render(), 1. Goal (the user's words, condensed), 1b. Long-term architecture (design for it now, build it in later rounds), 5. Done means, 6. Your notes for the next round, Handoff round 3: interact with any page element, not per-site selectors (+5 more)

### Community 65 - "browser.py"
Cohesion: 0.14
Nodes (21): _automation_on(), job(), build(), _click_ref_risk(), _click_risk(), _gmail(), _host(), _key_combo() (+13 more)

### Community 66 - "FakeKeyboard"
Cohesion: 0.40
Nodes (4): 2. Known problems (not your task unless listed in section 3), 4. Done means, 5. How the user will test on Windows, Handoff: stitch Playwright browser tools into brain v3

### Community 67 - "test_browser_tools.py"
Cohesion: 0.12
Nodes (15): test_back_counts_as_done_when_the_page_changed_despite_a_timeout(), test_back_goes_back_and_says_when_it_cannot(), test_brain_starts_without_playwright_and_reports_it(), test_clicks_that_send_post_or_buy_need_confirmation(), test_enter_asks_first_unless_it_is_a_search_box(), test_normal_browser_is_used_only_when_automation_is_off(), test_open_result_clicks_the_nth_video_and_reports_it(), test_open_result_says_when_there_are_too_few_or_none() (+7 more)

### Community 68 - "_pw"
Cohesion: 0.20
Nodes (9): job(), job(), job(), _first_run_note(), _gmail_draft(), job(), open_in_automation(), _pw() (+1 more)

### Community 69 - "policy.py"
Cohesion: 0.15
Nodes (7): _answers_pending_confirmation(), _first_word(), is_no(), is_yes(), _norm_reply(), read_sensors(), test_yes_no_in_both_languages()

### Community 70 - "registry.py"
Cohesion: 0.24
Nodes (5): detect_language(), _norm(), _overlap(), tokenize(), test_language_detection()

### Community 71 - "_join_spelled"
Cohesion: 0.22
Nodes (7): _join_spelled(), 2. Earlier fixes by Claude Opus (from commit messages and diffs only), 3. Top 3 risks, Design: how HoloDesk sees and acts on any UI (round 3), 4. What I (Claude Opus, local) fixed this round. Review briefly, test_short_spelled_runs_stay_upper_case(), test_spelled_names_are_joined()

### Community 72 - "ask_chatbot"
Cohesion: 0.25
Nodes (8): ask_chatbot(), job(), answer(), _open_tab(), page_text(), test_ask_chatbot_opens_the_site_in_a_new_tab_when_needed(), test_ask_chatbot_says_when_there_is_no_chat_box(), test_ask_chatbot_waits_for_the_answer_to_finish_and_returns_it()

## Knowledge Gaps
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskAgent` connect `TaskAgent` to `browser.py`, `main.py`, `OpenAIClient`, `GroqClient`, `memory_agent.py`, `engine.py`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ToolError` (e.g. with `ReplyEngine` and `_key_risk()`) actually correct?**
  _`ToolError` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Should `ToolContext` be split into smaller, more focused modules?**
  _Cohesion score 0.06118811881188119 - nodes in this community are weakly interconnected._
- **Why does `ToolContext` connect `ToolContext` to `browser_snapshot`, `browser.py`, `test_browser_tools.py`, `Monitors`, `registry.py`, `ask_chatbot`, `ReplyEngine`, `engine.py`, `build_default_registry`, `test_page_map.py`, `test_integration.py`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 59 inferred relationships involving `ToolContext` (e.g. with `_find_tool()` and `ReplyEngine`) actually correct?**
  _`ToolContext` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Should `TaskAgent` be split into smaller, more focused modules?**
  _Cohesion score 0.06688311688311688 - nodes in this community are weakly interconnected._
- **Why does `ToolError` connect `ToolContext` to `browser.py`, `make_engine`, `test_browser_tools.py`, `_pw`, `Monitors`, `registry.py`, `ask_chatbot`, `ReplyEngine`, `record`, `time`, `engine.py`, `build_default_registry`, `test_page_map.py`, `gmail_page`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._