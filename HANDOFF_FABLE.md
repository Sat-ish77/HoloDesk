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

## 3. Current state (after Phase 0, 2026-09-18)

Design and full analysis: `DESIGN.md` (every claim tagged VERIFIED or ASSUMED). Phase 0 evidence is in section 9.

VERIFIED (actually run):
- `pytest -q`: 54 passed (unit tests with fakes).
- App startup with the full Python path: overlay window appears (transparent, topmost, orb visible, ~29 FPS), camera and vision threads start, Whisper "small" loads, voice thread starts, no tracebacks. The overlay takes foreground focus at launch.
- Orchestrator routing and actions, driven by a script with the same agents as `app/main.py` (not via mic or the pygame chat box): `open notepad`, `minimize`, `open youtube in chrome` (opens in the default browser; "in chrome" is dropped by the production router), `what's on my screen` (GPT-4o answered in ~20 s), `game menu khola` (routes to overlay `open_game_menu`), `shutdown` then `cancel` (arms, then cancels; no OS shutdown pending afterwards).
- Chrome attach: with `--user-data-dir=%LOCALAPPDATA%\HoloDesk\chrome-profile`, a separate automation Chrome launches while normal Chrome is open and Playwright reads `Example Domain` over CDP.
- Commands run sequentially on the `OrchestratorAgent` thread (code read). The `threading.Thread(target=_run)` at `app/main.py:1046` is screen vision, not command dispatch.
- Real Python is first on PATH in both PowerShell and Git Bash on this machine.

BROKEN (found in Phase 0):
- `scroll down` scrolls but replies "That didn't work." `TaskAgent.scroll` returns success with an empty response and `_merge_results` turns an all-empty result into the failure text. False failure report. Fix in Phase 1.
- The app exited on its own after ~2 minutes with exit code 0 and no log line. The main loop only exits on `pygame.QUIT` or Esc; the overlay had keyboard focus, so a stray key press is the likely cause. Not proven.
- One smoke run hung for over 7 minutes with no output and was killed; the identical rerun finished in ~30 s. Cause unknown; OpenAI calls have no short timeout, which is the prime suspect.

NOT YET TESTED (needs the user at the laptop): real voice input and Whisper accuracy/latency, gestures and their delay, the pygame chat box, overlay focus behavior during use, second monitor.

CODE EXISTS, NOT VERIFIED LIVE: site adapters `browser/sites/*` and their selectors, Gmail draft flow, OmniParser, `MemoryAgent` habit output.

KNOWN ISSUES status (numbers match the original list):
1. Chrome debugging on default profile: FIXED in Phase 0 (`_launch_automation_chrome` uses `--user-data-dir`), verified live.
2. Playwright thread-binding: real but narrower than described. Only the orchestrator's parallel thread pool can cross threads today. Browser worker thread is Phase 3.
3. Gmail recipient autocomplete: real, Phase 3.
4. Site selectors unverified: still unverified, Phase 3.
5. `OMNIPARSER_SERVER_URL` pointed at ElevateU: FIXED in `.env` (commented out).
6. Browser automation enabled: FIXED in `.env` (set to 0). `HOLODESK_OPENAI_PLANNER_ENABLED=0` also added.
7. `python` is the Store stub: NOT REPRODUCED here; the full path still works and is safest.
8. Two ElevateU backends: not checked, Phase 4.
9. Broken `~penai` folders: warnings only; `openai` imports and works.
10. `_workflow_for` dead: confirmed, leave.
11. Win+R app launch: confirmed, Phase 2.
12. `pywinauto`/`uiautomation` unused: confirmed, Phase 2.
13. `if False` in a test: confirmed, cosmetic.
Additional issues 14-20 are listed in `DESIGN.md` section 2.2 (planner LLM hop, 60 s voice wait and stale reply, Brain insertion point, forced-English Whisper, dead `ask_ai`, Next.js API env name, pinch gesture conflict).

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
- 2026-09-18 Phase 0 (DESIGN.md written and approved first). Results:
  - PASS `.env`: OMNIPARSER_SERVER_URL commented out, HOLODESK_BROWSER_AUTOMATION_ENABLED=0, HOLODESK_OPENAI_PLANNER_ENABLED=0.
  - PASS startup: overlay, camera, vision, Whisper, voice thread up, no tracebacks. Log in artifacts/phase0_startup.log (gitignored). App later exited with code 0, cause unproven (likely Esc on the focused overlay).
  - Smoke via orchestrator script (not mic): PASS open notepad; FAIL scroll down (scrolls, but replies "That didn't work."); PASS minimize; PASS open youtube in chrome (default browser, "in chrome" dropped); PASS what's on my screen (~20 s); PASS game menu khola (overlay action, stubbed); PASS shutdown then cancel.
  - NOT RUN real voice and gestures: need the user present. Owner: user, before or during Phase 1 manual test.
  - PASS threading read: commands run on the OrchestratorAgent thread.
  - PASS Chrome attach: `Example Domain` via CDP with separate --user-data-dir, while normal Chrome was open.
  - Moved to Phase 3 per DESIGN.md: Playwright worker thread, Gmail draft flow.
  - pytest: 54 passed.
  - Next: Phase 1 (BrainAgent), including the scroll false-failure fix.
- 2026-09-18 Phase 1 (BrainAgent). Results:
  - Added `agents/brain_agent.py`: Claude tool loop (model from HOLODESK_BRAIN_MODEL, default claude-sonnet-5, effort low), cap 8 tool calls / 45 s, stops on a pending TaskAgent confirmation. Tools: open_app, open_website, scroll, type_text, press_keys (delete and alt+f4 confirm-gated), minimize, maximize, close_app (gated), get_active_window, lock_screen, sleep_pc, shutdown/restart (gated), volume, look_at_screen. Phases 8 and 9 folded in here per DESIGN.md.
  - Honesty backstops in code: an action claim with zero tool calls is replaced; a failed tool the reply omits is appended.
  - Orchestrator sends unmatched commands to the Brain when ANTHROPIC_API_KEY is set, before the declared-action refusal. Without the key, behavior is unchanged.
  - FIXED scroll false failure: `_merge_results` returns "Done." for silent successes. PASS: `scroll down` now replies "Done." (smoke script).
  - FIXED (found this phase) "what's on my screen" in the real app: `app/main.py` passed `screen_agent=None` to the orchestrator (lazy-load never ran; `analyze_screen()` has no callers). Now imported at startup. Phase 0's PASS for that step came from the smoke script, which built the real ScreenAgent.
  - Removed dead `ask_ai()` and its Groq client from `app/main.py`. Voice reply wait raised 60 -> 120 s.
  - PASS pytest: 63 passed (54 + 9 new in tests/test_brain_agent.py, fake client, no network).
  - PASS app startup with Phase 1 changes (artifacts/phase1_startup.log), closed via WM_CLOSE.
  - BLOCKED manual check "open notepad and type hello": no ANTHROPIC_API_KEY on this machine (.env, environment, CLI). Owner: user adds the key to .env, then rerun. Real API request shape is untested until then.
  - Next: Phase 6 (memory facts), then Phase 2.
- 2026-09-18 Phase 6 (memory facts), done before Phase 2 per DESIGN.md. Results:
  - `facts` table in storage/schema.sql; `MemoryAgent.remember(text)` rejects passwords, PINs, API keys, tokens, card numbers; `recall(query)` ranks the newest 500 facts with rapidfuzz token_set_ratio >= 50.
  - Brain tools `remember` and `recall`; recalled facts and habits go in a second system block after the cached prefix.
  - PASS pytest: 66 passed (3 new: remember/recall, secret rejection incl. "shopping" not tripping the PIN rule, facts placed after the cache breakpoint).
  - PASS real DB: `facts` table created in data/holodesk.db on init.
  - BLOCKED manual "remember my advisor is Dr. X" / "who is my advisor": needs ANTHROPIC_API_KEY.
  - Note for future agents: the Bash tool here halves backslashes inside heredocs and python -c. Use the Edit/Write tools, or chr(92), for any text containing backslashes.
  - Next: Phase 2 (native UI automation).
- 2026-09-18 Phase 2 (native app control). Results:
  - Added `automation/win_ui.py`: launch_app (Windows' own installed-app list via shell:AppsFolder, covers Store apps like Calculator/Notepad that have no .lnk), list_windows, focus_window, read_controls, click_control (UIA invoke, then click_input), set_text (reads back the value). All return dicts, never raise; COM initialized per thread.
  - `TaskAgent.open_app` tries the installed-app list for names not in APP_MAP before the old fuzzy guess. Grounding `_run_step` open_application tries it before Win+R (kept as fallback).
  - Brain tools: list_windows, switch_to, read_screen_controls, click (send/submit/delete/buy/... names are confirm-gated), set_field.
  - PASS live, worker thread, no Brain: launch Calculator, focus it, read controls in 0.42 s, click Clear/Seven/Plus/Two/Equals, display read back "Display is 9".
  - PASS live set_text on the Run dialog: value read back exactly, including + ( ) { } characters.
  - PASS live "open settings" through the orchestrator (not in APP_MAP): Settings opened, reply "Opening Settings." Took 5.5 s cold; the window opened behind Chrome (Windows focus rules), so the Brain may need switch_to after launching.
  - Found and fixed while testing: pywinauto 0.6.9 descendants(depth=) raises AttributeError (no depth limit now); rapidfuzz 3 matching is case-sensitive by default (now default_process everywhere); WRatio sent "vs code" to "Developer PowerShell for VS 2022" (now exact-ignoring-spaces, shortest first, then token_set_ratio >= 85). Checked names: chrome, calculator, word, note pad, notepad, notepad plus plus, edge, file explorer, settings all correct; vs code, teams, spotify give no match (not installed or ambiguous) and fall back to the old path.
  - Installed-app list takes 3-10 s to build; cached for the process, rebuilt at most once a minute on a miss, warmed in a background thread at app startup.
  - PASS pytest: 71 passed (5 new in tests/test_win_ui.py).
  - BLOCKED "open calculator, click seven" by voice through the Brain: needs ANTHROPIC_API_KEY. The same actions pass when called directly.
  - Left open: Calculator, Settings windows from the tests.
  - Next: Phase 3 (browser worker thread, generic browser tools, password autofill). Needs the user to log in to sites once in the automation Chrome profile.
- 2026-09-18 Phase 3 (browser worker, generic browser tools, password autofill). Results:
  - `browser/playwright_controller.py`: single BrowserWorker thread (`browser_call`), `with_page` returns url/title with every result, current-tab tracking, and page tools: snapshot, page_text, click_best, fill_field (refuses password fields), press, list/switch/new/close tab, login_autofill (Chrome saved password; checks only whether the password field is non-empty, never its value).
  - Existing Gmail/Facebook/Instagram draft flow and the confirmed Send now run on the worker thread.
  - Brain tools: browser_open (knows canvas, claude, elevateu, ...), browser_read, browser_page_text, browser_click (send/submit/delete/buy... gated), browser_fill, browser_press, browser_tabs, browser_switch_tab, browser_new_tab, browser_close_tab, browser_login. Registered only when HOLODESK_BROWSER_AUTOMATION_ENABLED=1.
  - Gmail `fill_recipient` now waits for Gmail's contact suggestion, presses Enter, and checks a chip formed. The chip selector `[email]` is UNVERIFIED.
  - PASS live (artifacts/phase3_live.log), via the Brain's tool wiring against the automation Chrome: open a local test page, read headings/links/buttons/fields, fill "Full name" and read it back, password fill refused, click "Say hi" and page text shows the change, "Submit application" click gated, login autofill honestly reports no saved password, new tab from a second thread, list/switch/close tabs.
  - PASS pytest: 75 passed (4 new in tests/test_browser_tools.py).
  - `.env`: HOLODESK_BROWSER_AUTOMATION_ENABLED=1 again.
  - NOT DONE (needs the user): log in once to Canvas, Gmail, ElevateU, Claude in the HoloDesk Chrome window (profile folder %LOCALAPPDATA%\HoloDesk\chrome-profile) and let Chrome save each password; then verify Gmail/Facebook/Instagram selectors on the real logged-in pages and "open canvas and read my dashboard" by voice.
  - Next: Phase 4 (ElevateU connector).
- 2026-09-18 Phase 4 (ElevateU connector). Results:
  - VERIFIED from source (study-helper/backend): auth is `Authorization: Bearer <token>`, Supabase `auth.get_user(token)`; `Bearer dev-token` works only when ALLOW_DEV_AUTH=true, which backend/.env sets, and maps to DEV_USER_ID (currently `local-dev-user`, not your real account). The job app (`jobhunt/core/auth.py`) uses the same rule.
  - VERIFIED routes: GET /api/v1/job/jobs/feed (returns {jobs, total}), GET /api/v1/job/jobs/search?role=, GET /api/v1/job/jobs/{id}/workspace, GET|PUT /api/v1/job/applications[/{id}], GET /api/v1/job/profile, GET /api/v1/job/autopilot/status, GET /api/v1/assignments (returns {assignments, count}, ordered by due_at).
  - Handoff correction: the frontend is Next.js; its API base is NEXT_PUBLIC_API_URL (study-helper-frontend/lib/api.ts), not VITE_API. The production API host is not in the repo.
  - Added `connectors/elevateu_client.py` (requests, 20 s timeout, dict results, plain messages for backend down / 401 / HTTP errors) and Brain tools elevateu_jobs, elevateu_job_details, elevateu_applications, elevateu_assignments (top 5 spoken, ids kept).
  - PASS pytest: 79 passed (4 new, requests mocked).
  - PASS live failure path: backend not running on 8000 -> "The ElevateU backend isn't running at http://127.0.0.1:8000." Issue 8 (two backends on 8000) could not be checked: nothing was listening.
  - NOT DONE (user decision): start the backend and set DEV_USER_ID in study-helper/backend/.env to your real Supabase user id (DESIGN.md open question 3). I did not edit the other repo or start its server. Then "what jobs did ElevateU find today" by voice.
  - Next: Phase 5 (job application form filling).
