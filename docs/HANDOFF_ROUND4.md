# Handoff round 4: one obedient agent that sees, acts and checks

Read `docs/HISTORY.md` first, all of it: every problem, root cause, fix, measurement and what
is still unverified, with live transcripts. Then this file. Branch `brain-v3-test`. Token rules:
`CLAUDE.md`. Earlier rounds: `docs/HANDOFF_ROUND3.md` (north star in 1a/1b),
`docs/DESIGN_UI_CONTROL.md` (your design).

## 1. What the user wants (their words, condensed)

"It should obey me like a manager. Understand what I mean, see whatever screen I'm
working on, and with full permission (except very dangerous things) just do the task,
then check that it's really done. Basically control anything for me. Once that works
we connect it to the phone and add the rest."

Phone, Telegram, Twilio, always-on: NOT this round. This round is the core loop.

## 2. What happened with email alone (a two-day saga, still not good)

Every row is a real live voice test. Unit tests passed every time; the live run failed.

| Symptom (live) | Root cause | Fix made |
|---|---|---|
| HOLO answered its own voice, acted on it | SAPI wait loop read RunningState=0 right after an async Speak and returned after 1.2 s of a 12.4 s reply; the mic opened mid-speech. Three echo filters were stacked on the symptom first. | `speak()` uses `WaitUntilDone(100)` (measured 12.4 s) |
| Every reply one request behind ("I say one thing, it answers another") | 60 s reply wait; a slow Gmail task's late answer was handed to the next question | replies carry the request id; late ones skipped |
| A Ctrl+C'd run's unanswered request re-ran on the next "hello" | 30-min cross-run history included a request with no saved reply | unanswered user turns dropped from history |
| 4 invisible HoloDesk processes, RAM exhausted, no voice | closed overlay / Ctrl+C left non-daemon threads alive | `os._exit` on close and in `sys.excepthook` |
| "Yes, go ahead, send it" ignored, confirmation repeated | `is_yes` was an exact-match word list | phrase-level yes/no, "no" wins on mixed |
| Agent claimed "I've scrolled / removed it" with no tool call | rule only in the prompt | `_CLAIMS_ACTION` challenge (English only) |
| gpt-4o-mini wandered: reply instead of new email, `find_files` for a contact, `forget_memory` to "remove a recipient" | small model, free-form loop | main model now gpt-5.5 (`.env`, local) |
| Scripted email flow fought the user: rejected "It should go to Sati Swagli. It should be a new email.", rejected spelled names, looped "new or reply?" on "close the Gmail", restarted on "just press send" | regex slot-filling script | replaced: gpt-5.5 runs the email turn and returns JSON {fields, action: ask/draft/send/cancel/leave} (`ReplyEngine._email_turn`). Live on the real lines: correct in 6/6 turns, 2-5 s each |
| Recipient "Erfosht kja në jupon dhe Gmail" typed into Gmail | Whisper on a spoken address; no sanity check | the model now normalises spoken/spelled addresses |
| Compose "Subject not visible" | `get_by_label("Subject")` matched an inbox row | `input[name=subjectbox]`, Message Body textbox |
| "Body did not take" when it had | Gmail's read-back was truncated; exact compare | compare the opening |
| Signed "Smarika Koirala" | model invented a sender | `HOLODESK_USER_NAME` |
| Stale tab, wrong Chrome, page "not found" | visibility signal unreliable under the overlay | your round-3 current-tab work |

Patterns behind all of it:
1. **Scripts and regex can't keep up with real speech.** Every rule broke on the next sentence.
2. **Small models don't follow multi-step intent.** gpt-5.5 fixed most of the email confusion.
3. **Timing and hardware bugs only show live** (SAPI timing, mic, display scaling, RAM).
4. **Fake-backed tests passed while live runs failed.** A live, repeatable check is the only truth
   (`scripts/smoke_test.py`: 6 commands, real model + real tools, 6/6 on gpt-4o-mini).
5. **Per-task features don't add up to "do anything".** Email took two days and is one task.

## 3. Your task: think first, then build ONE general loop

Step 1 (critic, short, in `docs/DESIGN_AGENT_LOOP.md`, max one page): given section 2, is the
current architecture (gpt-5.5 tool loop over ~55 narrow tools + page map + UIA + `computer_task`
vision tool + per-task flows) the right base for "obey me and do anything on screen"? What would you
change? Consider at least:
- **One agent loop for UI work**: observe (page map / UIA tree / screenshot, whichever fits; always a
  fresh look before acting) -> act -> observe again -> verify against the goal -> repeat until done or
  stuck. Today vision lives in a separate tool (`brain/tools/computer.py`, Claude Opus 5.5 computer
  toolset); should the main loop *be* that, with page-map and UIA as cheaper observation channels?
- **Obedience**: the user's latest words override the plan mid-task ("no, the other one", "change the
  recipient", "stop"). The agent asks only when truly blocked, never re-asks known facts.
- **Permission model**: act freely; one confirmation only for genuinely dangerous/irreversible actions
  (send to others, post, delete, pay, submit, shutdown, anything with credentials). Keep `brain/policy.py`.
- **Seeing "in real time"**: what is realistic (screenshot at each step, change detection by
  perceptual hash, a cheap watcher) vs. continuous video; cost/latency numbers.
- **Verification**: done = a fact checked on screen (element state, URL, file exists, Gmail's
  "Message sent"), never the model's word.
- **Model choice and latency**: which model drives the loop, per-step latency, cost per task.
- **What to delete**: per-task code made unnecessary by the general loop (be bold; less code).

Step 2: build the loop you designed, behind one tool or as the engine's default path for UI requests.
Keep `_email_turn` only if your loop doesn't do email as well; say which.

Step 3: a **live task eval** in `evals/live_tasks.md` + `scripts/live_tasks.py` (or extend the smoke
test): 10 fixed voice-style tasks run through the real model and real tools on Windows, each with a
machine check of success, e.g. open a site and read its title; Google search + open result N;
compose and send an email to the user's own address (subject marker, verify in Sent); attach a named
file; like the post in view (verify state); open File Explorer Downloads and name the newest file;
type into Notepad and save to Desktop (verify file); change a draft mid-task by a second instruction;
"stop" mid-task. Report success rate, steps and seconds per task. You can't run it in the cloud;
make it one command for the user.

## 4. Rules

- 222+ tests stay green (`python -m pytest -q`); fake-backed tests are not proof, the live eval is.
- No passwords or payment details typed by the agent, ever.
- Minimal, deletable code; comments say why. Keep what the live tests in section 2 fixed.
- Push to `brain-v3-test` only. Say plainly what you could not run, and give the user the exact
  commands: unit tests, smoke test, live task eval, and 5 voice checks.

## 5. Your notes

(Fill in: design summary, what you deleted, what's unverified, live-eval expectations.)
