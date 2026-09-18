# HoloDesk Handoff: Accessibility Desktop Agent

Read this file first and only this file. It is the single source of truth.
Any model (Fable, Sonnet, Opus) must be able to resume from it cold.

## 0. Rules for the agent doing this work

1. Do one phase at a time, in order. Do not read files a phase does not list.
2. Use Grep to find a symbol, then Read only ~40 lines around it. Never read whole large files (`app/main.py`, `agents/task_agent.py`, `agents/desktop_grounding_agent.py` are 700-1000+ lines).
3. After finishing a phase: run its check, then update section 9 (Progress Log) with what changed, the check result, and anything left. This is how the next model resumes.
4. Never read `node_modules`, `.venv`, `graphify-out/`, `artifacts/`.
5. Python on this machine: `python` resolves to the Windows Store stub. Use `C:\Users\Dipendra\AppData\Local\Programs\Python\Python312\python.exe` (in bash: `/c/Users/Dipendra/AppData/Local/Programs/Python/Python312/python`).
6. Test command: `<python> -m pytest -q`. Baseline: 54 passed. Never end a phase with fewer passing.
7. Commit per phase on branch `codex/holo-chatbot-3d-overlay` (PR #4 open). The post-commit hook prints "Python was not found"; that is a known harmless warning.
8. Trust nothing in this file that is not marked VERIFIED. Most of section 3 comes from docs and code reading, not from running the app. Phase 0 exists to find out what really works. If you find this file wrong, fix the file.

## 1. Goal

A voice-first personal agent that lets someone who cannot comfortably use a mouse/keyboard operate the whole Windows laptop:
open/switch/close any app or tab, scroll, click anything, fill forms, use ElevateU (job side first), open Canvas and Claude, help with assignments, answer "what's on my screen", remember facts and habits, and lock/sleep/shut down.
Hand gestures are a low-latency secondary input (scroll, switch tab, start/stop listening).

Hard requirement: it must not hallucinate actions. It only claims what a tool actually did and observed.

## 2. Non-negotiable safety rules (keep in code, not just prompts)

- Confirm before: send (email/message), submit (job application/form), delete, purchase/payment, shutdown/restart. Reuse `TaskAgent._set_pending_confirm` / `_confirm_yes` / `_confirm_cancel` in `agents/task_agent.py`. Do not invent a second confirmation system.
- Passwords: HoloDesk never stores, logs, speaks, or sends passwords to any LLM. Login is done by Chrome's own password manager inside the "HoloDesk Automation" profile: agent focuses the username field, Chrome shows its saved-credential suggestion, agent selects it (ArrowDown + Enter). The user saves each login once in that profile manually. `GroundingSafetyPolicy.BLOCKED_KEYWORDS` in `agents/desktop_grounding_agent.py` currently blocks "login"/"sign in"/"password"; relax only for the autofill tool described in Phase 3, nowhere else.
- Every action tool returns an observation (new window title, page URL, field value, visible text). The brain's reply must be built from observations only.

## 3. Current state (honest, as of 2026-09-18)

The full app (`app/main.py`) was NOT run in the session that wrote this file. Voice, gestures, overlay and routing were never exercised live. Treat them as "code exists" until Phase 0 proves them.

VERIFIED (actually run):
- `pytest -q`: 54 passed. These are unit tests with fakes; they prove logic, not the live app.
- All modules import cleanly (`agents.orchestrator`, `agents.task_agent`, `agents.desktop_grounding_agent`, `browser.*`).
- OmniParser HTTP fix: a live request reached the OmniParser server and it detected icons. OmniParser then crashed with out-of-memory on a full 1920x1080 screenshot (Florence-2 captioning tried to allocate 5.4 GB).
- Installed: `playwright` 1.62 + Chromium, GitHub CLI (authenticated as Sat-ish77).

CODE EXISTS, NOT VERIFIED LIVE (claims come from `PROJECT_STATE.md` and code reading):
- Overlay/orb/chat/games: `app/holo_overlay.py`, started by `app/main.py`.
- Voice: local `faster_whisper` "small" on CPU in `app/main.py` (~line 297). `PROJECT_STATE.md` says recognition is noisy ("close facebook" heard as "close facebooking").
- Gestures: `core/vision_thread.py` (MediaPipe, `model_complexity=0`) emits only `"V_GESTURE"` and `"OPEN_PALM"` on `gesture_queue`. `PROJECT_STATE.md` says gestures are sensitive to light/angle and pinch is unreliable.
- Routing: `agents/orchestrator.py` `OrchestratorAgent`; calls `ProductionControlAgent.route()` (`agents/production_control.py`) then a long keyword/regex block (~lines 270-450) building `(agent, action, context)` intents.
- Actions: `agents/task_agent.py` `TaskAgent.execute(action, context)`: open_app (`APP_MAP`), open_web, open_web_in_browser (`BROWSER_PATH_CANDIDATES`, `_find_browser_executable`), close/minimize/maximize, scroll, type_text, media_control, lock_screen, shutdown/restart with confirm.
- Browser automation: `browser/playwright_controller.py` (`controller.ensure_page()`, `open_url`, `click`, `type_into`, `press_key`, `read_text`, `is_visible`, `screenshot`; accept `role/name/label/placeholder/text`; return dicts, never raise). Site adapters `browser/sites/{gmail,facebook,instagram}.py`. Wired via `DesktopActionExecutor._try_browser_send_flow` and `TaskAgent._run_grounded_desktop` / `_send_via_browser`. Never run against a real browser. See known issues 1-4: as written it almost certainly does not work live.
- Memory: `agents/memory_agent.py` `MemoryAgent` (SQLite, schema `storage/schema.sql`): app usage logging, `detect_habits`, `log_voice_command`, `get_recent_voice_commands`, `format_habits_for_prompt`.
- LLMs: `connectors/openai_client.py` (primary), `connectors/groq_client.py` (fallback). `app/main.py` also has a separate legacy `ask_ai()` using Groq `llama-3.1-8b-instant` (duplicate chat path). User has Anthropic and Gemini keys, not yet in `.env`.

KNOWN ISSUES (found by reading code/config; each must be fixed or disproven in Phase 0):
1. Chrome remote debugging is blocked on the default profile. Since Chrome 136, `--remote-debugging-port` is ignored when using the default user data directory. `_launch_automation_chrome` in `browser/playwright_controller.py` passes only `--profile-directory`, so it stays inside the default data dir. Also, if normal Chrome is already open, the launch just opens a window in the existing process and ignores the flags. Fix: add `--user-data-dir=%LOCALAPPDATA%\HoloDesk\chrome-profile` (a separate folder); drop `--profile-directory`.
2. Playwright's sync API is bound to the thread that started it. `app/main.py` appears to run each command in a new `threading.Thread(target=_run, daemon=True)` (~line 1046; not read in full). The module-level `controller` in `browser/playwright_controller.py` would then be reused from a different thread on the next command and fail. Fix: run all Playwright calls on one dedicated worker thread (a `queue.Queue` of callables), or create/close Playwright per call. Verify the threading first.
3. Gmail recipient is a name, not an address. `_extract_gmail_recipient` returns "Satish Wagle"; `browser/sites/gmail.py` `fill_recipient` types that into To without selecting Gmail's autocomplete suggestion, so the chip may not form. Fix: after typing, wait for the suggestion and press Enter, then read back the To field.
4. Site selectors in `browser/sites/*` were written without seeing the live pages. Expect some to be wrong. Verify each one against the real logged-in page with `snapshot_text` (Phase 3) and record the working selectors here.
5. `.env` has `OMNIPARSER_SERVER_URL=http://127.0.0.1:8000`, which is the ElevateU backend, not OmniParser. `build_default_parser()` in `vision/ui_parser.py` picks the OmniParser adapter whenever that variable is set and never falls back at runtime, so vision grounding currently hits the wrong server and fails. Fix: comment it out (OpenAI vision becomes the parser) or point it at 8001 with OmniParser running.
6. `.env` has `HOLODESK_BROWSER_AUTOMATION_ENABLED=1` already, so the unverified browser path is live. Set it to 0 until issues 1-4 are fixed.
7. `python app/main.py` fails on this machine because `python` is the Store stub. Use the full interpreter path from rule 5. Earlier run instructions given to the user were wrong on this point.
8. Two copies of the ElevateU backend were seen running on port 8000 (one from `backend\.venv`, one from a codex runtime python). Harmless to HoloDesk but confusing; note which one is real in Phase 4.
9. pip warns about broken package folders `~penai`, `~treamlit`, `~yspark` in site-packages (leftovers from an interrupted uninstall). If `openai` imports fail, reinstall `openai`.
10. `agents/production_control.py` `_workflow_for()` and `ProductionRoute.workflow` are never executed (only tests read them). `TaskAgent.draft_email` / `draft_message` only fire when grounding keywords don't match. Leave them; don't build on them.
11. `DesktopActionExecutor._run_step` opens apps by typing into Win+R. Replaced in Phase 2.
12. `pywinauto` and `uiautomation` are installed but used nowhere.
13. `tests/test_browser_automation.py` `test_browser_send_flow_returns_none_when_disabled` has a pointless `... if False else ...` expression. Simplify to `DesktopActionExecutor.__new__(DesktopActionExecutor)`.

UNKNOWN (nobody has checked): gesture latency numbers, Whisper latency, whether the overlay steals focus from other windows, how the app behaves on a second monitor, how `ChatAgent` and legacy `ask_ai()` split traffic.

ElevateU (separate repo `C:\Users\Dipendra\Desktop\study-helper`, FastAPI backend in `backend/`, live site https://www.elevateuapp.org):
- Local backend: `uvicorn main:app --port 8000`. Routes (prefix `/api/v1`): `/assignments`, `/canvas`, `/dashboard`, and job routes under `/api/v1/job`: `GET /jobs/feed`, `GET /jobs/search`, `GET /jobs/{job_id}/workspace`, `POST /jobs/score/{job_id}`, `GET|POST /applications`, `PUT /applications/{id}`, `GET /profile`, `GET /profile/setup-status`, `GET /autopilot/status`, `POST /autopilot/run-now`.
- All routes require `Depends(get_current_user)`. VERIFY FIRST (Phase 4 step 1): the auth scheme in `backend/dependencies.py` (likely Supabase JWT bearer) and the production API host the site calls. Do not guess these.

## 4. Target architecture (keep it this small)

```
voice/gesture/typed text
  -> OrchestratorAgent (existing fast deterministic intents; unchanged, low latency)
  -> if no intent matched: BrainAgent (NEW, one LLM tool-calling loop)
        tools = thin wrappers over EXISTING functions + a few new ones
        loop: model picks tool -> tool runs -> observation -> model continues (max 8 steps)
        risky tools go through TaskAgent confirmation
  -> reply spoken from observations only
```

Perception order for "click X" (cheapest and most exact first):
1. Browser page: Playwright locators (DOM/accessibility tree).
2. Native app: Windows UI Automation via `pywinauto` (`Desktop(backend="uia")`), find control by name/role.
3. Last resort: vision on the active window only (`OpenAIVisionUIParser` on a cropped screenshot), then click the box.

## 5. Phases

Each phase: files, exact changes, check. Keep diffs minimal; reuse existing helpers named here.

### Phase 0: Prove the foundation (do this before building anything)

Goal: replace guesses in section 3 with facts. Record every result in section 9 as PASS/FAIL with one line of evidence.

1. Config fixes (issues 5, 6): in `.env`, comment out `OMNIPARSER_SERVER_URL`, set `HOLODESK_BROWSER_AUTOMATION_ENABLED=0`.
2. Start the app with the full Python path (issue 7). Record: does the overlay appear, does the camera start, does Whisper load, any tracebacks. Save the startup log to `artifacts/phase0_startup.log`.
3. Typed/voice smoke tests, one at a time, record PASS/FAIL and the spoken reply: `open notepad`, `open youtube in chrome`, `scroll down`, `minimize`, `what's on my screen`, `game menu khola`, `shutdown` then `cancel`.
4. Gestures: V starts listening, open palm stops. Record rough delay in seconds.
5. Threading (issue 2): read `app/main.py` around the `threading.Thread(target=_run` call (~line 1046, read ~30 lines) and write down which thread runs orchestrator commands.
6. Chrome (issue 1): apply the `--user-data-dir` fix, then run one script that calls `controller.ensure_page("https://example.com")` and prints `page.title()`. PASS = "Example Domain".
7. Playwright threading (issue 2): fix with a single worker thread; test that two `ensure_page` calls from two different threads both succeed.
8. Only now set `HOLODESK_BROWSER_AUTOMATION_ENABLED=1`, log into Gmail in the new automation profile, and try the Gmail draft flow. Fix issue 3. Stop before Send.
9. Rewrite section 3: move each item to VERIFIED or BROKEN based on the results. Delete claims that turned out false.

Check: section 9 has a PASS/FAIL line for every step above; `pytest -q` still passes.

### Phase 1: BrainAgent with tool calling

Files: CREATE `agents/brain_agent.py`, CREATE `tests/test_brain_agent.py`, UPDATE `agents/orchestrator.py`, UPDATE `.env.example`, UPDATE `requirement.txt`.

- Model: Anthropic Messages API with tools. `pip install anthropic`, add `anthropic` to `requirement.txt`, add `ANTHROPIC_API_KEY=` and `HOLODESK_BRAIN_MODEL=claude-sonnet-5` to `.env.example`. Use `claude-haiku-4-5-20251001` if latency matters more; set it via the env var, not code.
- `BrainAgent.__init__(self, task_agent, memory_agent)`; `run(self, text: str) -> dict` returning `{"success", "response"}` like every other agent.
- Tool registry: a plain dict `name -> (json_schema, callable)`. Phase 1 tools, all wrapping existing code:
  - `open_app(name)` -> `task_agent.execute("open_app", {"app_name": name, "raw": ...})`
  - `open_website(url_or_name)` -> `task_agent.execute("open_web", ...)`
  - `scroll(direction, amount)`, `type_text(text)`, `press_keys(keys)` (pyautogui hotkey), `minimize`, `maximize`, `close_app(name)` (already confirm-gated)
  - `get_active_window()` -> title + process via module-level `_get_active_window` in `agents/memory_agent.py`
  - `remember(fact)`, `recall(query)` (Phase 6 fills these; stub returns "not yet available")
- System prompt must say: act only through tools; after each action check the observation; if a tool fails, say so plainly; ask when the target is ambiguous; never claim an action you didn't observe.
- Loop cap 8 tool calls; on cap, stop and report what was done.
- Orchestrator: find where it falls back to chat when no intents matched (grep `chat_agent` in `agents/orchestrator.py`). Route there to `BrainAgent.run` first; keep ChatAgent for pure conversation.
- Test: fake Anthropic client returning a scripted tool_use then text; assert the right tool callable was invoked and the reply text returned. No network.

Check: `pytest -q` passes; manually, typed "open notepad and type hello" works end to end.

### Phase 2: Native app control via UI Automation

Files: CREATE `automation/win_ui.py`, UPDATE `agents/brain_agent.py` (register tools), UPDATE `agents/desktop_grounding_agent.py` (`_run_step` open_application branch).

- `win_ui.py` functions (each returns dict, never raises):
  - `list_windows()` -> titles of top-level windows
  - `focus_window(title_substring)`
  - `click_control(name, control_type=None)` in the foreground window: `Desktop(backend="uia").window(active_only=True)` then `child_window(title_re=..., control_type=...)`, `.click_input()`
  - `read_controls(limit=40)` -> names/types of visible controls in the foreground window (lets the brain "see" native UI as text, no vision cost)
  - `set_text(name, text)`
- Replace Win+R app launch in `_run_step` "open_application" with `os.startfile` on a Start Menu shortcut found by fuzzy match: scan `.lnk` files under `%APPDATA%\Microsoft\Windows\Start Menu\Programs` and `%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs`, match with `rapidfuzz` (already a dependency). This makes "open any app" work without a hardcoded map. Keep `APP_MAP` as the first lookup.
- Brain tools: `open_any_app(name)`, `switch_to(window)`, `list_windows`, `read_screen_controls`, `click(name)`, `set_field(name, text)`.

Check: unit test with pywinauto mocked; manually "open calculator, click seven" works.

### Phase 3: Generic browser tools + password autofill

Files: UPDATE `browser/playwright_controller.py` (add `snapshot_text(page, limit=60)` returning visible interactive elements as `role: name` lines, via `page.locator("a,button,input,textarea,select,[role]")`), UPDATE `agents/brain_agent.py`.

- Brain tools: `browser_open(url)`, `browser_read()` (snapshot_text), `browser_click(text_or_label)`, `browser_fill(label, value)`, `browser_press(key)`, `browser_tabs()`, `browser_switch_tab(index)`, `browser_new_tab(url)`, `browser_close_tab()`.
- `browser_login_autofill(site)`: open login page, focus username field, press ArrowDown, Enter (selects Chrome's saved credential), click sign-in. Never reads or passes password values. Exempt only this tool from the login block.
- Site shortcuts: Canvas `https://untsystem.instructure.com` (already in `WEBSITE_MAP`), Claude `https://claude.ai`, ElevateU `https://www.elevateuapp.org`.
- Set `HOLODESK_BROWSER_AUTOMATION_ENABLED=1` in `.env` for manual testing. On first launch the user logs in and saves passwords in the "HoloDesk Automation" Chrome profile.

Check: FakePage tests in `tests/test_browser_automation.py` style; manually "open canvas and read my dashboard".

### Phase 4: ElevateU connector

Files: CREATE `connectors/elevateu_client.py`, UPDATE `agents/brain_agent.py`, UPDATE `.env.example`.

1. VERIFY: grep `get_current_user` in `C:\Users\Dipendra\Desktop\study-helper\backend\dependencies.py` (read ~40 lines) and find the production API base URL (grep `VITE_API` in `study-helper-frontend`). Write findings into section 9 before coding.
2. Env: `ELEVATEU_API_BASE` (default `http://127.0.0.1:8000`), `ELEVATEU_TOKEN`. If tokens are short-lived Supabase JWTs, store the refresh token with `keyring`, not in `.env`.
3. `ElevateUClient` methods, `requests` with 20s timeout, return dicts: `job_feed()`, `search_jobs(q)`, `job_workspace(job_id)`, `list_applications()`, `update_application(id, status)`, `profile()`, `assignments()`, `autopilot_status()`.
4. Brain tools: `elevateu_jobs(query=None)`, `elevateu_job_details(job_id)`, `elevateu_applications()`, `elevateu_assignments()`. Speak the top 3-5 results, not everything.

Check: tests with `requests` mocked; manually "what jobs did ElevateU find today".

### Phase 5: Job application form filling

Files: CREATE `browser/form_filler.py`, UPDATE `agents/brain_agent.py`.

- `fill_application(page, profile: dict) -> dict`: scan form fields (labels, placeholders, input types), map to profile keys with a small alias table (name, email, phone, linkedin, github, location, work authorization, sponsorship, years of experience) plus `rapidfuzz` match; fill only confident matches; return `{"filled": [...], "unfilled": [...]}`.
- Unfilled fields: brain asks the user by voice, then calls `browser_fill`. Resume upload: `locator.set_input_files(path)` with `HOLODESK_RESUME_PATH`.
- Submit is a separate tool `browser_submit()` that always goes through `_set_pending_confirm`.
- Flow: "apply to job 3" -> `elevateu_job_details` -> open apply URL -> `fill_application` -> report filled/unfilled -> confirm -> submit -> `update_application(id, "applied")`.

Check: FakePage test with a fake form; manually on one real posting, stop before submit.

### Phase 6: Memory of the user

Files: UPDATE `storage/schema.sql` (add `facts(id, text, created_at)`), UPDATE `agents/memory_agent.py` (`remember(text)`, `recall(query, limit=5)` using `LIKE` + rapidfuzz), UPDATE `agents/brain_agent.py`.

- Brain system prompt includes `format_habits_for_prompt()` plus top recalled facts for the current request. Tools `remember`/`recall` become real.
- Never store secrets: reject facts matching password/token/card-number patterns.

Check: unit test remember then recall; manually "remember my advisor is Dr. X" then "who is my advisor".

### Phase 7: Low-lag gestures

Files: UPDATE `core/vision_thread.py`, UPDATE the gesture handler in `app/main.py` (grep `gesture_queue`).

- Keep the gesture set tiny and reliable: V = start listening, open palm = stop, pinch + vertical move = continuous scroll (speed by distance), two-finger swipe left/right = `ctrl+shift+tab` / `ctrl+tab`, fist held 1s = `alt+tab`.
- Latency: process frames at 320x240, drop stale frames instead of queueing, debounce with N consecutive frames (existing debouncer), emit scroll deltas instead of repeated discrete events. Log ms per frame; target under 40 ms.

Check: log shows per-frame ms; manual scroll feels continuous.

### Phase 8: "What's on my screen" and assignments help

Files: UPDATE `agents/brain_agent.py`.

- Tool `look_at_screen(question)`: screenshot the active window only (crop by window rect from `win_ui`), send to Claude vision (same Anthropic client), return the answer. Used for understanding, never for coordinates when DOM/UIA can do it.
- Assignments: `elevateu_assignments()` + `browser_open` Canvas + `browser_read`. The brain explains and outlines; it does not auto-submit coursework.

### Phase 9: System control

- Tools: `lock()` (existing `lock_screen`), `sleep()` (`rundll32.exe powrprof.dll,SetSuspendState 0,1,0`), `shutdown()` / `restart()` (existing, confirm-gated), `volume(up/down/mute)`.

## 6. Latency budget

- Deterministic intents (orchestrator regex) handle common commands with no LLM call. Add new common phrases there, not in the brain.
- Brain model via env var; Haiku for speed, Sonnet for reliability.
- Whisper "small" on CPU is the biggest voice delay. Measure before changing; `base` is the fallback option.

## 7. Out of scope

Mac/Linux, multi-monitor coordinate mapping, wake word engine changes, overlay visual redesign, payments.

## 8. Open decisions (defaults chosen; user may override)

| Decision | Default |
|---|---|
| Brain LLM | Anthropic, `claude-sonnet-5` via `HOLODESK_BRAIN_MODEL` |
| Password handling | Chrome password manager in automation profile, never HoloDesk |
| ElevateU auth | Verify in Phase 4; bearer token from env or refresh token in `keyring` |
| OmniParser | Last resort only, port 8001, active-window crop |

## 9. Progress log (update after every phase)

- 2026-09-18: Handoff written. Baseline 54 tests passing (unit tests only; app never run live this session). PR #4 open. Known issues 1-13 listed in section 3. Next: Phase 0.
