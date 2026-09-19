# HoloDesk Design: Accessibility-First Desktop Agent

Written 2026-09-18 from `HANDOFF_FABLE.md` plus targeted reads of the files it names. The app was not run while writing this.

Every statement carries one tag:

- **[V]** VERIFIED: I read the code, config, or installed package and saw it.
- **[A]** ASSUMED: from docs, the handoff, or general knowledge; not checked on this machine. Phase 0 exists to turn these into [V] or delete them.

---

## 1. Goal and user

**User.** One person who controls a Windows 11 laptop mainly by voice, with hand gestures as a low-latency backup. Mouse and keyboard are uncomfortable, not impossible. [V: handoff section 1]

**Goal.** A personal agent that can do, by voice, anything the user would otherwise do with a mouse: open, switch, close apps and tabs; scroll; click named things; fill forms; use ElevateU (job side first), Canvas and Claude; explain what is on screen; remember facts and habits; lock, sleep, shut down. [V: handoff section 1]

**Hard rule.** It never claims an action it did not observe. Every reply about an action is built from what a tool returned. [V: handoff section 1]

**"Done" looks like** (each line is a manual check the user performs by voice, in the running app):

1. "Open Notepad and type hello world" opens Notepad and the text appears. Reply names both observations.
2. "Open Canvas and read my dashboard" opens the automation Chrome, lands on Canvas logged in (via Chrome's saved password), and reads back the visible headings.
3. "What jobs did ElevateU find today" speaks the top 3 to 5 jobs from the ElevateU API.
4. "Apply to job 2" fills the form from the ElevateU profile, reads back what was filled and what was not, asks before submit, and only submits on "yes".
5. "What's on my screen" describes the active window.
6. "Remember my advisor is Dr. X" then, later, "who is my advisor" returns Dr. X.
7. V gesture starts listening, open palm stops speech and scrolling, thumbs up/down scrolls, all within about half a second.
8. "Shut down" asks first; "cancel" aborts. Nothing sends, submits, deletes, pays, or powers off without a spoken "yes".
9. A failed tool produces "I couldn't ..." with the tool's error, never a success claim.
10. `pytest -q` passes with at least the 54-test baseline.

---

## 2. Findings from analysis

### 2.1 What the current code actually does (threading and flow)

- Commands from voice and from the typed chat box both land on `command_queue` and are consumed by one thread, `OrchestratorAgent` (a `threading.Thread`, `agents/orchestrator.py:11-46`). Voice puts at `app/main.py:850`, chat UI puts at `app/main.py:1092`. [V]
- The orchestrator runs each command sequentially on its own thread. It only uses its `ThreadPoolExecutor(max_workers=5)` when `_looks_parallel()` is true and there is more than one intent (`agents/orchestrator.py:122-131`). [V]
- The `threading.Thread(target=_run, daemon=True)` at `app/main.py:1046` that the handoff blamed for Playwright thread-hopping is `analyze_screen()` (GPT-4o screen vision), not command execution. [V]
- The voice thread blocks on `voice_reply_queue.get(timeout=60)` after dispatch (`app/main.py:856`). `voice_reply_queue` has `maxsize=1` (`core/queues.py:22`). If a command takes longer than 60 s, the late reply is left in the queue and will be spoken as the answer to the next command. [V for the code; the stale-reply consequence is A, it follows from the code but I did not run it]
- Routing order inside `_process()`: pending-confirmation words → `ProductionControlAgent.route()` → `_detect_intents()` regex → if nothing matched: `_looks_like_declared_action()` sends to `declared_task_unsupported`, else `chat_agent`. (`agents/orchestrator.py:57-112`) [V]
- `ProductionControlAgent.route()` calls OpenAI `json_query` (planner model, default `gpt-5.2`) for any command it cannot classify deterministically that has 6+ words or looks Nepali (`agents/production_control.py:89-93, 361-362`). Gated by `HOLODESK_OPENAI_PLANNER_ENABLED` (default on). This is an LLM hop that runs before the planned Brain and duplicates it. [V]
- Confirmation gate: `TaskAgent._pending_confirm` set by `_set_pending_confirm(message, fn, kind)`; consumed by `_confirm_yes` / `_confirm_cancel`. Checked in two places: orchestrator `_process()` for short yes/cancel words, and `TaskAgent.execute()` for any raw text (`agents/task_agent.py:200-205, 356-379`). Shutdown and restart arm it (`task_agent.py:867-889`); close app goes through `close_app_with_confirm`. [V]
- Gestures: `VisionThread` (MediaPipe, complexity 0, camera 640x480) emits only `V_GESTURE` and `OPEN_PALM` after a 6-frame debounce and 15-frame cooldown. But the main loop also reads raw landmarks every frame and implements thumbs-up/down → toggle continuous scroll, and pinch → drag the overlay card (`app/main.py:1218-1270`). So gesture scrolling already exists. [V]
- Voice: `faster_whisper` "small", int8, CPU, `beam_size=5`, `language="en"` forced (`app/main.py:297, 493-497`). Nepali phrases the normalizer expects ("game menu khola") will be transcribed as English-sounding text. [V for the code; effect A]
- TTS: Windows SAPI via `comtypes`, `pyttsx3` fallback (`app/main.py:388-424`). [V]
- Legacy `ask_ai()` (Groq `llama-3.1-8b-instant`) at `app/main.py:152` has zero callers. Dead. [V]
- `ChatAgent` uses OpenAI `gpt-5.2-chat-latest` with Groq fallback and a 10-turn history (`agents/chat_agent.py`). [V]
- Screen vision: `ScreenAgent.execute(question)` takes a full screenshot, resizes, sends to GPT-4o, refuses when the active window title matches a blocklist (`agents/screen_agent.py:72-131`). [V]
- Grounding parser: `build_default_parser()` prefers `OmniParserServerAdapter` whenever `OMNIPARSER_SERVER_URL` is set, then `OpenAIVisionUIParser` when `OPENAI_API_KEY` is set, then local OmniParser, then mock (`vision/ui_parser.py:370-379`). [V]
- Overlay window: pygame `NOFRAME`, `WS_EX_LAYERED`, `HWND_TOPMOST`. No `WS_EX_NOACTIVATE` in the grep, so clicking the overlay can steal focus from the target app. [V for the flags; the focus effect is A]
- Installed with the full Python path: Python 3.12.3, `anthropic` 0.85.0, `playwright` 1.62.0, `faster-whisper` 1.2.1, `pywinauto` 0.6.9, `uiautomation` 2.0.29, `rapidfuzz` 3.14.5, `openai` 2.26.0, `groq` 0.37.1, `mediapipe` 0.10.14, `pyautogui` 0.9.54. `keyring` is not installed. [V]
- Test count by function: 18 + 26 + 6 + 4 = 54, matching the handoff's "54 passed". I did not re-run them. [V count; pass state A, from handoff]

### 2.2 The 13 known issues: real or not, and what each blocks

| # | Issue | Verdict | Evidence | Blocks |
|---|---|---|---|---|
| 1 | Chrome remote debugging ignored on default profile | **Real** [V code, A Chrome behavior] | `_launch_automation_chrome` passes `--remote-debugging-port` and `--profile-directory` only, no `--user-data-dir` (`browser/playwright_controller.py:91-98`). Chrome 136+ ignores the debugging switch on the default data dir, and a launch while normal Chrome is open just opens a new window in the existing process. | All browser automation |
| 2 | Playwright sync API thread-bound | **Real but misdiagnosed** [V] | Commands run on the orchestrator thread, not a new thread per command. Playwright is started lazily inside `ensure_page()` so it binds to the orchestrator thread on first use. Hazards remain: the parallel path uses pool threads, and Phase 1+ tools or future callers could touch `controller` from elsewhere. | Browser tools called from the thread pool; any future non-orchestrator caller |
| 3 | Gmail recipient is a name, no autocomplete select | **Real** [V] | `_extract_gmail_recipient` returns the captured name (`desktop_grounding_agent.py:278-291`); `fill_recipient` types it and stops (`browser/sites/gmail.py:36-40`). | Gmail send flow |
| 4 | Site selectors unverified | **Cannot verify without running** [A] | Written blind per the module docstring. | Gmail/Facebook/Instagram adapters |
| 5 | `OMNIPARSER_SERVER_URL` points at the ElevateU backend | **Real** [V] | `.env:6` is `http://127.0.0.1:8000`; `build_default_parser()` picks the server adapter whenever the variable is set. | Vision grounding path (`grounded_desktop` intents) |
| 6 | Browser automation enabled while broken | **Real** [V] | `.env:8` is `HOLODESK_BROWSER_AUTOMATION_ENABLED=1`. | Makes issues 1-4 reachable from voice |
| 7 | `python` is the Store stub | **Path works** [V]; stub claim [A] | Full path runs Python 3.12.3. I did not test bare `python`. | Running anything |
| 8 | Two ElevateU backends on 8000 | **Cannot verify without running** [A] | Process state, not code. | Nothing in HoloDesk; confusion only |
| 9 | Broken `~penai` etc. folders | **Real, harmless so far** [V] | pip prints the three warnings; `openai` 2.26.0 still reports installed. | Nothing unless `import openai` fails |
| 10 | `_workflow_for` / `ProductionRoute.workflow` dead | **Real** [V] | Only computed inside `route()` and read by one test. | Nothing; do not build on it |
| 11 | Win+R app launch in grounding executor | **Real** [V] | `_run_step` uses `pyautogui.hotkey("win","r")` for open_application, open_website and open_folder (`desktop_grounding_agent.py:527, 541, 561`). `TaskAgent.open_app` uses `APP_MAP` then `start ""` (`task_agent.py:395-404`), which is the path the Brain will use. | Reliability of "open any app" |
| 12 | `pywinauto` / `uiautomation` unused | **Real** [V] | Only imported as availability probes with `noqa: F401` (`task_agent.py:63, 69`). | Nothing; native control is unbuilt |
| 13 | `if False else` in a test | **Real, cosmetic** [V] | `tests/test_browser_automation.py:208`. | Nothing |

**Additional issues not in the handoff** (all [V] unless noted):

- 14. Production-control LLM hop (section 2.1) adds an OpenAI round trip before the Brain for 6+-word commands. Disable with the existing env flag once the Brain exists.
- 15. Voice reply timeout and stale reply hazard (section 2.1). The Brain must finish within the voice thread's wait, or the wait must be raised.
- 16. `_looks_like_declared_action` guard sits exactly where the Brain must be inserted; if the Brain goes after it, "click submit" never reaches the Brain.
- 17. Whisper forced to English while Nepali phrases exist in normalizer and orchestrator. [effect A]
- 18. `ask_ai()` dead code in `app/main.py`.
- 19. Handoff Phase 4 says the frontend uses `VITE_API`; the frontend is Next.js and reads `NEXT_PUBLIC_API_URL || "http://localhost:8000"` (`study-helper-frontend/lib/api.ts:3`). The production API host is not in the repo grep; it lives in deployment env.
- 20. Handoff Phase 7 proposes pinch + vertical move for scroll; pinch is already the overlay card drag and thumbs up/down already scroll. Adding pinch-scroll would conflict.

### 2.3 Keep, dead, replace

**Keep (reuse as-is or with small edits):**
- `agents/orchestrator.py` deterministic routing, confirm-word handling, `_reply`, `_execute_one`.
- `agents/task_agent.py` everything: action methods, `APP_MAP`, `WEBSITE_MAP`, the confirmation gate, `BLOCKED_COMMANDS`, `CONFIRM_BEFORE`.
- `browser/playwright_controller.py` primitives (`open_url`, `click`, `type_into`, `press_key`, `read_text`, `is_visible`, `screenshot`) and the dict-never-raise contract.
- `agents/memory_agent.py`, `storage/schema.sql`, `storage/db.py`.
- `agents/screen_agent.py` for "what's on my screen".
- `core/*` threads and queues, `vision/gesture_detector.py`, `app/holo_overlay.py`.
- `VoiceAssistantThread` and `speak()` in `app/main.py`.
- `agents/command_normalizer.py`, `connectors/openai_client.py`, `connectors/groq_client.py`.
- `tests/*` and the `FakePage` / `FakeLocator` pattern in `tests/test_browser_automation.py:26-62`.

**Dead (delete when a phase touches the file; otherwise leave):**
- `app/main.py` `ask_ai()` and the Groq client setup that only serves it (`grok_client`).
- `agents/production_control.py` `_workflow_for`, `WorkflowStep`, `ProductionRoute.workflow` (test-only).
- `agents/production_brain.py` (re-export shim; 9 lines). [V content; grep found no importer]
- `tests/test_browser_automation.py:208` `if False` expression.
- `uiautomation` import probe; the package itself can stay installed.

**Replace:**
- `_launch_automation_chrome` launch flags (issue 1).
- Thread ownership of `controller` (issue 2): a single browser worker thread.
- `browser/sites/gmail.py:fill_recipient` (issue 3).
- `.env` values for `OMNIPARSER_SERVER_URL` and `HOLODESK_BROWSER_AUTOMATION_ENABLED` (issues 5, 6).
- App launch: add Start-Menu shortcut lookup behind `TaskAgent.open_app` (the Brain's path) and reuse it in `_run_step` (issue 11).
- `ProductionControlAgent` LLM hop: turn off by env (issue 14).
- Site adapters `browser/sites/*`: keep, but demote to optional shortcuts behind the generic browser tools; verify selectors live before trusting.

**Cannot verify without running:** overlay behavior and focus, camera start, Whisper latency and accuracy, gesture latency, all site selectors, Chrome's saved-password keyboard selection, OmniParser memory use, ElevateU backend process state.

---

## 3. Tech stack

| Concern | Choice | Why | Rejected alternative | Cost / latency |
|---|---|---|---|---|
| Speech to text | `faster-whisper` "small", int8, CPU, local (existing) [V] | Already wired with VAD, echo guard, and tunables; offline; no per-call cost | Cloud STT (OpenAI/Deepgram): adds network latency and cost, sends audio off-device. Whisper `base`: faster, less accurate; keep as the fallback if Phase 0 shows "small" is too slow | $0. Latency unknown until Phase 0 [A: typically 1-3 s for a short utterance on CPU] |
| Text to speech | Windows SAPI via `comtypes`, `pyttsx3` fallback (existing) [V] | Instant, offline, already has the stop-speech path used by open palm | Neural TTS APIs: nicer voice, 0.5-2 s network delay and cost per call | $0, sub-second [A] |
| Gestures | MediaPipe Hands, complexity 0, 640x480, in `VisionThread` (existing) [V] | Already running at camera rate; V, open palm, thumbs up/down implemented | Custom classifier or OmniParser hand model: no benefit for four gestures | $0. Latency unknown until Phase 7 measurement [A: roughly 20-40 ms per frame on this class of CPU] |
| Brain LLM | Anthropic Messages API with tools, manual loop, `anthropic` 0.85.0 already installed [V]. Model from `HOLODESK_BRAIN_MODEL`, default `claude-sonnet-5` (handoff default, user's choice) | Native tool calling, `strict: true` schemas, prompt caching for the fixed system prompt and tool list. The manual loop is about 40 lines and lets us stop the loop on a pending confirmation and on a wall-clock cap, which the SDK tool runner does not expose as cleanly | OpenAI planner already in repo: would keep two brains; handoff chose Anthropic. Local model: too slow and unreliable for tool use on CPU. `claude-opus-5`: more reliable on hard multi-step tasks at 2.5x the price and higher latency; switch via env if Sonnet misbehaves. `claude-haiku-4-5`: fastest, use if latency dominates | Sonnet 5 $2 in / $10 out per 1M; Opus 5 $5 / $25; Haiku 4.5 $1 / $5 (from the Claude API reference, cached 2026-06-24). One command ≈ 2-3 calls × ~4k input tokens ≈ $0.03 uncached, ≈ $0.01 with the system+tools prefix cached [A]. Latency ≈ 1-3 s per call [A] |
| Thinking / effort | Adaptive thinking (default on Sonnet 5), `output_config.effort` `"low"` for this voice loop [A: from the reference; not tested here] | Voice needs speed; tool calls are simple | `"high"` default: slower, no gain for one-step desktop actions | Lower effort means fewer tokens and fewer tool calls |
| Browser automation | Playwright sync, `connect_over_cdp` to a Chrome launched by HoloDesk with its own `--user-data-dir` (existing design, fixed flags) [V code] | Chrome launched without `--enable-automation` keeps Google sign-in and the Chrome password manager working; DOM locators are exact and free | `chromium.launch_persistent_context(channel="chrome")`: simpler, but Google blocks sign-in in automation-flagged browsers and the password bubble may be suppressed [A]. Pixel clicking via vision: expensive and inexact | $0. Locator actions 50-500 ms [A] |
| Native UI automation | `pywinauto` with `backend="uia"` (installed, unused) [V] | Reads control names and types as text, so the Brain "sees" native apps without vision cost; clicks by name | `uiautomation` package: equivalent, less documented; pick one. Vision-only: cost and imprecision | $0. Control tree reads 0.1-3 s depending on window size [A]; limit depth |
| App launch | `APP_MAP` first, then Start-Menu `.lnk` fuzzy match with `rapidfuzz` and `os.startfile` [A: design] | Opens any installed app by spoken name without a hardcoded map | Win+R typing (existing): fails for apps not on PATH, races on focus | $0, under 1 s [A] |
| Vision fallback | Existing `OpenAIVisionUIParser` (gpt-4o) for click coordinates when DOM and UIA both fail; existing `ScreenAgent` (gpt-4o) for "what's on my screen" [V code] | Already built, tested, has a privacy blocklist; reuse costs zero new code | OmniParser local: crashed OOM on a 1080p screenshot [V per handoff]; only as opt-in on port 8001 with an active-window crop. Claude vision for `look_at_screen`: viable later, one-line swap; not worth a second vision path now | ~$0.002 per screen read per `.env.example` [A] |
| Memory store | SQLite (existing `storage/db.py`, schema) plus a new `facts` table; recall with `LIKE` then `rapidfuzz` ranking [A: design] | Hundreds of facts at most; no server | Vector DB or embeddings: overkill, adds a dependency | $0, milliseconds |
| ElevateU access | `requests` against the FastAPI backend, header `Authorization: Bearer <token>` [V: `backend/dependencies.py:137-152`] | Direct API beats scraping the site. Locally the backend accepts `Bearer dev-token` when `ALLOW_DEV_AUTH=true`, which `backend/.env:28` sets [V] | Production API with a Supabase session JWT: needs a login flow and refresh-token storage (`keyring`, not installed). Scraping via Playwright: slow, brittle | $0 |
| Confirmation gate | Existing `TaskAgent._set_pending_confirm` [V] | One system, already voice-tested in unit tests | A second gate in the Brain: two states to desync | none |

---

## 4. Architecture

### 4.1 Data flow

```
mic ──VoiceAssistantThread──► Whisper ──► text ─┐
typed chat box (main thread) ───────────────────┼──► command_queue
                                                │
camera ──CameraThread──► frame_queue ──VisionThread──► landmark_queue (main loop: cursor, thumbs scroll, pinch drag)
                                                └─► gesture_queue  (main loop: V = wake voice, open palm = stop)

command_queue ──OrchestratorAgent thread──► _process(text)
   1. pending confirmation? yes/cancel words → TaskAgent._confirm_yes / _confirm_cancel
   2. ProductionControlAgent.route() deterministic part (LLM part disabled by env)
   3. _detect_intents() regex → TaskAgent / ScreenAgent / MemoryAgent / ReminderAgent / overlay
   4. nothing matched → BrainAgent.run(text)            ◄── NEW, inserted before _looks_like_declared_action
        loop ≤ 8 tool calls, ≤ 45 s wall clock:
          Claude picks tool → tool runs → observation dict → back to Claude
          tool returns pending_confirmation → loop ends, message returned as the reply
        tools = thin wrappers over TaskAgent, win_ui, browser worker, ElevateU client, MemoryAgent, ScreenAgent
   5. reply → voice_reply_queue (voice) or response_queue CHAT_REPLY (chat UI)

voice thread: speak(reply) → log_voice_command → listen again
```

### 4.2 Threads and who owns what

| Thread | Exists | Runs |
|---|---|---|
| Main (pygame) | [V] | Overlay drawing, keyboard events, landmark consumption, thumbs scroll, pinch drag, gesture events, `response_queue` drain |
| `CameraThread` | [V] | Camera capture into `frame_queue` |
| `VisionThread` | [V] | MediaPipe, `GestureDetector`, puts to `landmark_queue` and `gesture_queue` |
| `VoiceAssistantThread` | [V] | Wake, VAD, Whisper, dispatch, block on reply, `speak()` |
| `OrchestratorAgent` | [V] | All routing and all agent execution including `BrainAgent.run` and every tool callable, sequentially |
| Orchestrator `ThreadPoolExecutor` | [V] | Only explicit parallel commands ("open X and Y"). Browser tools must not run here directly |
| **Browser worker** | NEW | Owns Playwright. `browser_call(fn, *args)` puts a callable on a queue and waits for the result. Started lazily by `playwright_controller`. Every function that touches `controller` or a `page` goes through it, including `TaskAgent._send_via_browser` and the confirmation callbacks |
| `MemoryAgent._logging_loop` | [V] | Active-window logging every 60 s |
| `threading.Timer` in TaskAgent | [V] | Delayed shutdown/restart and timers |

Playwright's sync API is bound to the thread that called `sync_playwright().start()`; a call from another thread raises a greenlet error. [A: Playwright documented behavior] The browser worker makes the binding explicit instead of relying on the orchestrator being the only caller.

### 4.3 Where the confirmation gate sits

Only in `TaskAgent._pending_confirm`. [V]

- Existing deterministic paths already arm it (shutdown, restart, close app, browser send). [V]
- Brain tools that need confirmation call `task_agent._set_pending_confirm(message, fn, kind)` and return `{"success": True, "pending_confirmation": True, "response": message}`. The Brain loop stops on that flag and returns `message` verbatim as the reply. The next utterance "yes" is caught at orchestrator step 1 before the Brain ever sees it, and `fn` runs on the orchestrator thread (using `browser_call` if it needs the page). [A: design]
- The gate is code, not prompt. A tool that can send, submit, delete, pay, or power off has no code path that performs the action on first call.

### 4.4 No-hallucination rules (structural, not just prompt)

1. Every tool returns an observation dict: `{"success", "response", ...}` plus what changed (window title, URL, field value, visible text). Failures return `success: False` with the error text; nothing raises. [V: existing contract in TaskAgent, playwright_controller, site adapters]
2. `BrainAgent.run` returns `{"success", "response", "tool_log": [...]}`. If `tool_log` is empty and the text looks like a declared action (`orchestrator._looks_like_declared_action`), the reply is replaced with the existing honest refusal. [A: design]
3. If any tool in `tool_log` failed, the reply must contain "couldn't" or the tool's error; enforce by appending "Note: <tool> failed: <error>" in code when the model's text omits it. [A: design]
4. System prompt: act only through tools; check each observation; never state an action you did not observe; when the target is ambiguous, ask. [A: prompt text; effect not measurable until run]
5. The final spoken reply is the model's text, so rule 4 is the weak link. Rules 2 and 3 are the code backstops.

---

## 5. Components

Each entry: inputs, outputs, failure behavior, files and functions.

### 5.1 Voice input (existing)

- Files: `app/main.py` `VoiceAssistantThread` (line 453), `transcribe_audio` (487), `_dispatch_and_speak` (846). [V]
- Input: mic audio. Output: `{"type": "USER_COMMAND", "text", "source": "voice"}` on `command_queue`. [V]
- Failure: timeout after 60 s → returns None, nothing spoken; stale reply hazard (section 2.1). [V]
- Change: raise `voice_reply_queue.get(timeout=...)` to 120 s and cap the Brain at 45 s so a reply is always earlier than the wait. [A: design] Upgrade path: tag replies with the command `ts` and drop mismatches.

### 5.2 Gesture input (existing)

- Files: `core/vision_thread.py`, `vision/gesture_detector.py`, main loop `app/main.py:1131-1270`. [V]
- Input: camera frames. Output: `V_GESTURE`, `OPEN_PALM` on `gesture_queue`; thumbs scroll and pinch drag handled inline. [V]
- Failure: no hand → landmarks empty, all states reset (`main.py:1283`). [V]
- Change (Phase 7): add tab switch; log per-frame ms; keep everything else.

### 5.3 Orchestrator (existing, one insertion)

- File: `agents/orchestrator.py`. Insert at the `if not intents:` block (line 103): if `brain_agent` is configured, `intents = [("brain_agent", "run", {"raw": command})]`; the `_looks_like_declared_action` refusal becomes the fallback when the Brain is unavailable. Add a `brain_agent` branch in `_execute_one` (line 151). [A: design]
- `app/main.py:348` `OrchestratorAgent(agents={...})` gets `"brain_agent": BrainAgent(task_agent, memory_agent, screen_agent, ...)`. [V location]
- `.env`: `HOLODESK_OPENAI_PLANNER_ENABLED=0` so the OpenAI planner hop stops. [V flag exists]

### 5.4 BrainAgent (new)

- File: `agents/brain_agent.py`. `BrainAgent(task_agent, memory_agent, screen_agent=None)`; `run(text) -> dict`.
- Tool registry: `dict[name] -> (schema, callable)`; schemas carry `strict: True` and `additionalProperties: False`. Tool definitions and the system prompt are built once and marked `cache_control: {"type": "ephemeral"}` so repeated commands pay for the prefix once. [A: from the API reference]
- Loop: `client.messages.create(model, system, tools, messages, max_tokens=1024, output_config={"effort": "low"})`; on `stop_reason == "tool_use"` run every tool block, append all results in one user message, repeat; stop on `end_turn`, on 8 calls, on 45 s, or on a `pending_confirmation` result. On `refusal` or `max_tokens`, report plainly. [A: design; API shapes from the reference]
- Rolling history: last 6 user/assistant text turns kept in memory so "what did I just say" and follow-ups work; tool blocks are not carried across commands. [A: design]
- Failure: no `ANTHROPIC_API_KEY` → `run` returns `success: False` and the orchestrator falls back to the old chat/refusal path. API errors → "I couldn't reach my brain: <error class>". [A: design]
- Test: fake client whose `messages.create` returns scripted responses (a `tool_use` then a text turn); assert the callable ran with the parsed input and the returned text; assert the loop stops on `pending_confirmation`; assert the 8-call cap. No network.

Phase 1 tools (all wrap existing code): `open_app`, `open_website`, `scroll`, `type_text`, `press_keys`, `minimize`, `maximize`, `close_app`, `get_active_window` (`memory_agent._get_active_window`), `lock`, `sleep`, `shutdown`, `restart`, `volume`, `look_at_screen` (`screen_agent.execute`), `remember`, `recall`.

### 5.5 Native UI automation (new)

- File: `automation/win_ui.py`. Functions return dicts, never raise: `list_windows()`, `focus_window(title_substring)`, `read_controls(limit=40, depth=3)`, `click_control(name, control_type=None)`, `set_text(name, text)`, `active_window_rect()`, `launch_app(name)` (Start-Menu `.lnk` fuzzy match then `os.startfile`). [A: design]
- Uses `pywinauto.Desktop(backend="uia")`; `read_controls` limits descendants by depth so large windows do not take seconds. [A]
- Failure: control not found → `success: False, response: "No control named X in <window title>"` and the list of the nearest names so the Brain can retry once. [A: design]
- Hook `launch_app` into `TaskAgent.open_app` after the `APP_MAP` miss and before `start ""`, and into `_run_step` "open_application". Note `_resolve_app_name` may reject unknown names first (`task_agent.py:390`); read it in Phase 2 before wiring. [V line; behavior A]

### 5.6 Browser automation (existing plus worker and generic tools)

- File: `browser/playwright_controller.py`. Fix `_launch_automation_chrome` args: `--user-data-dir=%LOCALAPPDATA%\HoloDesk\chrome-profile`, drop `--profile-directory`. Add the worker thread and `browser_call`. Add `snapshot_text(page, limit=60)` returning `role: name` lines from `a, button, input, textarea, select, [role]`, skipping `input[type=password]` values. [A: design]
- Brain tools: `browser_open`, `browser_read`, `browser_click`, `browser_fill` (refuses `type=password` targets in code), `browser_press`, `browser_tabs`, `browser_switch_tab`, `browser_new_tab`, `browser_close_tab`, `browser_login_autofill(site)`, `browser_submit` (confirm-gated). [A: design]
- Observation after every action: `page.url`, `page.title()`, and for fills the read-back value. [A: design]
- Failure: locator timeout → `success: False` with the selector tried and the top of `snapshot_text` so the Brain can pick a real name. [A: design]
- `browser/sites/*`: keep as optional; `fill_recipient` gains "wait for suggestion, Enter, read back the To chip". [A: design]

### 5.7 ElevateU client (new)

- File: `connectors/elevateu_client.py`. `ElevateUClient(base_url, token)` with `requests`, 20 s timeout; methods `job_feed`, `search_jobs`, `job_workspace`, `list_applications`, `update_application`, `profile`, `assignments`, `autopilot_status`; all return dicts with `success`. [A: design]
- Env: `ELEVATEU_API_BASE` default `http://127.0.0.1:8000`, `ELEVATEU_TOKEN` default `dev-token`. [A: design; the dev-token path is V in the backend]
- Failure: connection refused → "ElevateU backend isn't running on <base>". 401 → "ElevateU rejected my token". [A]
- Brain tools: `elevateu_jobs`, `elevateu_job_details`, `elevateu_applications`, `elevateu_assignments`; each speaks at most 5 items.

### 5.8 Form filler (new)

- File: `browser/form_filler.py`. `fill_application(page, profile) -> {"filled": [...], "unfilled": [...]}`; alias table plus `rapidfuzz` on label/placeholder/name; fills only matches with score ≥ 85; never touches `type=password`; resume via `set_input_files(HOLODESK_RESUME_PATH)`. [A: design]
- Submit only via `browser_submit`, which arms the gate.

### 5.9 Memory (existing plus facts)

- Files: `storage/schema.sql` add `facts(id, text, created_at)`; `agents/memory_agent.py` add `remember(text)` and `recall(query, limit=5)`. Reject text matching password, token, card-number patterns. [A: design]
- System prompt includes `format_habits_for_prompt()` [V exists] plus top recalled facts for the current text, placed after the cached prefix so the cache still hits. [A]

### 5.10 System control (existing plus two lines)

- `lock_screen`, `shutdown_with_confirm`, `restart_with_confirm` exist. [V] Add `sleep` (`rundll32.exe powrprof.dll,SetSuspendState 0,1,0`) and `volume` via `pyautogui.press("volumeup"|"volumedown"|"volumemute")`. [A: design]

---

## 6. Safety

**Confirm before** (code-gated through `TaskAgent._pending_confirm`):
send email or message; submit a form or job application; delete file, folder, email, or message; empty recycle bin; close an app; shutdown, restart, sign out; any purchase or payment flow (currently blocked outright by `GroundingSafetyPolicy.BLOCKED_KEYWORDS`, keep it blocked). [V for existing entries; browser_submit and delete tools are A: design]

**Blocked outright** (`BLOCKED_COMMANDS`, `BLOCKED_KEYWORDS`): destructive shell commands, registry, banking and payments. [V]

**Passwords.**
- HoloDesk never stores, logs, speaks, or sends a password to any LLM. No Brain tool has a password parameter. `browser_fill` refuses password fields in code. `remember` rejects secret-looking text. `snapshot_text` omits password field values. [A: design]
- Login is done by Chrome's password manager inside the HoloDesk automation profile: `browser_login_autofill` focuses the username field, presses ArrowDown then Enter to pick the saved credential, then clicks sign in. It reads nothing from the password field. The user saves each site's login in that profile once, by hand. [A: Chrome keyboard behavior unverified; Phase 3 checks it]
- `GroundingSafetyPolicy.BLOCKED_KEYWORDS` keeps "login", "sign in", "password" for the grounding path; only `browser_login_autofill` is exempt. [V current list]
- Screen vision keeps the title blocklist in `ScreenAgent` and `MemoryAgent`. [V]

**No hallucination.** Section 4.4.

---

## 7. Phases

Numbering follows the handoff so section 9 of the handoff stays comparable. Corrections to the handoff are marked.

### Phase 0: Prove the foundation

Do:
1. `.env`: comment out `OMNIPARSER_SERVER_URL`; set `HOLODESK_BROWSER_AUTOMATION_ENABLED=0`; add `HOLODESK_OPENAI_PLANNER_ENABLED=0`.
2. Start `app/main.py` with the full Python path; save the log to `artifacts/phase0_startup.log`; record overlay, camera, Whisper load, tracebacks.
3. Smoke tests by typed chat and by voice: `open notepad`, `open youtube in chrome`, `scroll down`, `minimize`, `what's on my screen`, `game menu khola`, `shutdown` then `cancel`. Record each reply.
4. Gestures: V wakes, open palm stops; rough delay.
5. Chrome attach: apply the `--user-data-dir` fix (two lines) and run a one-off script calling `controller.ensure_page("https://example.com")` and printing `page.title()`.
6. Rewrite handoff section 3 from results.

Correction: handoff step 5 (read the threading) is answered in section 2.1 here: commands run on the orchestrator thread. Handoff steps 7 and 8 (Playwright worker thread, Gmail login and draft) are building work, not proving; moved to Phase 3. Reason: the Gmail flow depends on generic browser tools and the worker, and doing it before the Brain exists would be tested through the old grounding path that Phase 3 demotes.

Avoid: fixing anything beyond the two-line Chrome flag change; reading whole files.
Risks: the app may not start at all (camera, pyaudio, model download); OpenAI key may be missing for screen vision.
Verify: `pytest -q` still 54; section 9 has PASS/FAIL per step.
Done: [ ] .env changed [ ] startup log saved [ ] 7 smoke results recorded [ ] gesture delay recorded [ ] example.com title printed [ ] handoff section 3 rewritten [ ] committed.

### Phase 1: BrainAgent

Do: create `agents/brain_agent.py`, `tests/test_brain_agent.py`; insert into orchestrator at line 103 and `_execute_one`; construct in `app/main.py:348`; add `anthropic` to `requirement.txt`; add `ANTHROPIC_API_KEY=`, `HOLODESK_BRAIN_MODEL=claude-sonnet-5` to `.env.example`; raise the voice wait to 120 s; delete `ask_ai()`. Register the Phase 1 tools from section 5.4 including `look_at_screen`, `lock`, `sleep`, `shutdown`, `restart`, `volume`, and stub `remember`/`recall` only if Phase 6 is not done in the same sitting.

Correction: handoff Phases 8 (`look_at_screen`) and 9 (system control) are each a few lines of tool registration over existing code; fold them here. Phase 6 (facts) is independent and small; do it right after Phase 1.

Avoid: a second confirmation system; the SDK tool runner (the loop needs the confirmation stop); putting the Brain after `_looks_like_declared_action`; forced `tool_choice`.
Risks: latency over the voice wait; model claims success on a failed tool (backstop in 4.4 rule 3); cache misses if the system prompt contains the date or recalled facts before the breakpoint.
Verify: `pytest -q` ≥ 55; typed "open notepad and type hello" end to end; typed "click the nonexistent button" gives an honest failure.
Done: [ ] tests pass [ ] manual open+type works [ ] failure case honest [ ] `ask_ai` removed [ ] planner flag off [ ] committed.

### Phase 2: Native app control

Do: create `automation/win_ui.py` (section 5.5); wire `launch_app` into `TaskAgent.open_app` and `_run_step`; register `open_any_app`, `switch_to`, `list_windows`, `read_screen_controls`, `click`, `set_field`.
Avoid: walking the whole UIA tree; vision when UIA can name the control.
Risks: UIA is slow on Electron and browser windows (they expose little); some apps need elevation.
Verify: unit test with `pywinauto` mocked; manual "open calculator, click seven".
Done: [ ] mocked tests [ ] calculator works [ ] Notepad `set_field` works [ ] committed.

### Phase 3: Generic browser tools, worker thread, password autofill

Do: browser worker and `browser_call`; `snapshot_text`; the tools in 5.6; `browser_login_autofill`; fix `fill_recipient`; verify every selector in `browser/sites/*` against the live logged-in page and record the working ones in handoff section 9; then set `HOLODESK_BROWSER_AUTOMATION_ENABLED=1`; user saves Canvas, Gmail, ElevateU logins in the automation profile by hand.
Avoid: letting any tool read password fields; running Playwright outside the worker.
Risks: Google refuses sign-in in the automation profile (mitigated by launching Chrome without automation flags); Chrome's credential dropdown may need a click rather than ArrowDown.
Verify: FakePage tests for `snapshot_text`, worker round trip from two threads, `browser_fill` refusing a password field; manual "open canvas and read my dashboard"; Gmail draft to a name stops before Send and the To chip reads back correctly.
Done: [ ] tests [ ] two-thread test passes [ ] Canvas read works [ ] Gmail draft stops before send [ ] selectors recorded [ ] committed.

### Phase 4: ElevateU connector

Do: `connectors/elevateu_client.py` (5.7), Brain tools, env vars. First confirm which process serves port 8000 and that `ALLOW_DEV_AUTH=true` and the right `DEV_USER_ID` are set in `study-helper/backend/.env` (see open question 3).
Correction: the frontend is Next.js; the API base is `NEXT_PUBLIC_API_URL` (verified), not `VITE_API`. The production host must be read from the deployment environment or the live site's network calls, not from the repo.
Avoid: scraping the site; storing a Supabase password anywhere.
Risks: `DEV_USER_ID` mismatch returns empty data for the real account.
Verify: tests with `requests` mocked; manual "what jobs did ElevateU find today".
Done: [ ] tests [ ] live feed spoken [ ] auth choice recorded in handoff [ ] committed.

### Phase 5: Job application form filling

Do: `browser/form_filler.py` (5.8); flow "apply to job N" → details → open apply URL → fill → report → confirm → `browser_submit` → `update_application`.
Avoid: auto-submitting; guessing unmatched fields.
Risks: ATS sites with iframes or multi-step forms; file upload dialogs.
Verify: FakePage form test; one real posting, stop before submit.
Done: [ ] fake form test [ ] real posting filled and reported [ ] submit gated [ ] committed.

### Phase 6: Memory of the user

Do: `facts` table, `remember`, `recall`, secret filter, prompt injection of habits and facts.
Verify: unit test remember → recall; manual advisor example.
Done: [ ] tests [ ] manual works [ ] secret text rejected [ ] committed.

### Phase 7: Low-lag gestures

Do: keep V, open palm, thumbs up/down scroll (existing). Add two-finger swipe left/right → `ctrl+shift+tab` / `ctrl+tab`. Process at 320x240 and drop stale frames (frame queue already `maxsize=1`). Log ms per frame.
Correction: drop the handoff's pinch + vertical scroll (pinch is the card drag; thumbs already scroll) and the fist alt+tab (fist overlaps the thumbs-down pose and the "fingers curled" test). Add them only if the user asks after trying the existing set.
Verify: per-frame ms in the log; scroll feels continuous; swipe switches tabs.
Done: [ ] ms logged [ ] swipe works [ ] no regression in V/open palm [ ] committed.

### Phase 8: Assignments help

Do: `elevateu_assignments` plus Canvas via browser tools; the Brain outlines and explains; never submits coursework. Optional: crop `look_at_screen` to the active window using `win_ui.active_window_rect()`.
Verify: manual "what assignments are due this week".

### Phase 9: System control

Folded into Phase 1. Verify `sleep` and `volume` manually there.

---

## 8. Open questions (recommended default first)

1. **Brain model.** Default `claude-sonnet-5` at effort `low` for speed, switchable by env. Alternative: `claude-opus-5` if Sonnet misreads observations in Phase 1 testing. Decide after the Phase 1 manual test.
2. **Chat traffic.** Default: everything the deterministic router does not match goes to the Brain, including plain conversation; `ChatAgent` stays only as the fallback when `ANTHROPIC_API_KEY` is missing. Alternative: keep `ChatAgent` for chat and Brain for actions, which needs a classifier we do not have.
3. **ElevateU auth.** Default: local backend with `Bearer dev-token` and `DEV_USER_ID` set to your real Supabase user id in `study-helper/backend/.env` so the data is yours. Alternative: production API with a session JWT, which needs a one-time login script and `keyring` for the refresh token; more work, no HoloDesk benefit while the backend runs locally.
4. **Screen vision provider.** Default: keep GPT-4o through the existing `ScreenAgent` and `OpenAIVisionUIParser` (two keys in `.env`). Alternative: move `look_at_screen` to Claude vision so only one key is needed; a one-line swap later.
5. **Whisper language.** Default: leave `language="en"` and let the Brain handle English. If you want Nepali commands, switch to auto-detect and measure the accuracy hit in Phase 0.
6. **Site adapters.** Default: keep `browser/sites/*` but only after their selectors are verified in Phase 3; the generic tools do the same job. Alternative: delete them and their 18 tests, which lowers the test count below the 54 baseline rule.
7. **Voice wait.** Default: 120 s wait, 45 s Brain cap, no reply tagging. Alternative: tag replies with the command timestamp and discard stale ones; do this if a stale reply is ever heard.

---

## 9. Verification summary

- Read directly: `HANDOFF_FABLE.md`, `.env.example`, `requirement.txt`, `.env` (key names and non-secret flags only), `storage/schema.sql`, `core/vision_thread.py`, `core/queues.py`, `agents/chat_agent.py`, `browser/sites/gmail.py`, and targeted ranges of `app/main.py`, `agents/orchestrator.py`, `agents/task_agent.py`, `agents/desktop_grounding_agent.py`, `agents/production_control.py`, `agents/memory_agent.py`, `agents/screen_agent.py`, `browser/playwright_controller.py`, `vision/ui_parser.py`, `vision/gesture_detector.py`, `connectors/openai_client.py`, `study-helper/backend/dependencies.py`, `study-helper/study-helper-frontend/lib/api.ts`.
- Checked with pip using the full Python path: versions in section 2.1.
- Not run: the app, pytest, Chrome, OmniParser, the ElevateU backend.
