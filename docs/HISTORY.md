# HoloDesk brain v3: full history, problems, fixes, numbers (2026-11-11 to 2026-11-14)

Written for an agent starting cold. Read it all once; then work from `docs/HANDOFF_ROUND4.md`.
Two agents worked on this branch: **Fable** (cloud, via the user's phone; rounds 1-3 below) and
**Opus** (local Claude Code on the user's Windows laptop: reviews, live tests, fixes). Every
"live test" below was the user talking to HoloDesk on the real laptop; transcripts are quoted from
the console (`YOU:` = what speech-to-text heard, `TOOL:` = a tool actually called, `HOLO:` = reply).

---

## 1. The user, the goal, the machine

**User:** Satish ("Sat") Wagle, UNT CS senior graduating Dec 2026, job-seeking; HoloDesk is a
portfolio project. Speaks English and Nepali (often mixed, Romanized). Wants to be treated as the
boss: "obey me like a manager", honest results, numbers, no pretending.

**Goal (north star):** control the whole laptop by voice, from the laptop and later from the phone:
see whatever is on screen, act with full permission except for genuinely dangerous things
(send to others, post, delete, pay, submit, shutdown, credentials), and verify each task is really
done. Concrete wishes so far: Gmail (compose new / reply, recipient by name or spoken address,
AI-written body, attachments, change anything before sending, send), like and comment on
Facebook/Instagram posts, ask Claude/ChatGPT and read the answer, find/move/open files, any button
in any app. Later: Telegram voice notes, Twilio calls (it calls him on important events; he calls
it), always-on laptop, task "recipes" that are learned once and replayed.

**Machine (verified):**
- Windows 11 Home, **8 GB RAM** (free RAM is often ~1 GB; this matters, see 4.9), screen 1920x1080
  (pyautogui logical), one built-in microphone, **speakers, no headphones** (echo risk), webcam.
- Python: `C:\Users\Dipendra\AppData\Local\Programs\Python\Python312\python.exe` (`python` alone is
  the Windows Store stub). In bash: `/c/Users/Dipendra/AppData/Local/Programs/Python/Python312/python`.
- Working copy: `C:\Users\Dipendra\Desktop\holodesk-brain-v3`, a git worktree of the HoloDesk repo
  (`github.com/Sat-ish77/HoloDesk`) on branch `brain-v3-test`. The user's older version lives in
  `Desktop\holodesk` on branch `codex/holo-chatbot-3d-overlay` (35 commits Fable never saw: a
  Claude-based BrainAgent, Playwright browser automation, ElevateU connector). **Fable's brain v3 was
  built from April's `main`**, so it duplicated some of that; the Playwright code was later ported in.
- Start: `cd C:\Users\Dipendra\Desktop\holodesk-brain-v3` then `<python> app\main.py`. Talk: click
  the overlay, press **Space** (or V-sign gesture); wait for `SPEECH DONE`; quit with **ESC**.
  The wake word has never worked (see 8).
- HoloDesk drives its own Chrome profile at `%LOCALAPPDATA%\HoloDesk\chrome-profile` (Chrome 136+
  refuses remote debugging on the default profile). The user thought it was incognito; he logs in
  there once (Gmail, Facebook).
- Git hooks print "Python was not found" (graphify hook calls `python`): harmless.

**`.env` (names only; values are local):** `GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`HOLODESK_LLM_BASE_URL=https://api.openai.com/v1`, `HOLODESK_LLM_API_KEY=${OPENAI_API_KEY}`,
`HOLODESK_CHAT_MODEL=gpt-5.5`, `HOLODESK_FAST_MODEL=gpt-5.4-mini`, `HOLODESK_BROWSER_AUTOMATION_ENABLED=1`,
`HOLODESK_STT_NAMES=Kapil Sharma, Smarika Koirala`, `HOLODESK_USER_NAME=Satish Wagle`,
`HOLODESK_WAKE_WORD_ENABLED=1` (phrase `hey holo`, but code listens for "hey desk"), plus older keys.
Writer model `HOLODESK_WRITER_MODEL` defaults to `gpt-5.5`. Computer use: `HOLODESK_COMPUTER_MODEL`
defaults to `claude-opus-5-5`. Quiet console: `HOLODESK_QUIET` (default 1).

**Models available on the user's OpenAI key (listed live):** gpt-5.5, gpt-5.5-pro, gpt-5.4,
gpt-5.4-mini, gpt-5.4-nano, gpt-5.2, gpt-5.1, gpt-5.6-luna/sol/terra, o3 and older. The user prefers
**Groq first, OpenAI as backup** in principle, but for testing the main model was switched to OpenAI
(see 4.10). **Groq free tier limits hit live:** 200K tokens/day (exhausted within ~1 hour of voice
use, twice) and 8K tokens/minute.

---

## 2. Timeline (what was built, by whom)

| Commit | Who | What |
|---|---|---|
| 9aecd0b | Fable | Brain v3: tool-calling agent loop (37 tools), SAFE/ACT/DANGER/BLOCKED policy, SQLite memory, Telegram bridge, daemon, Nepali speech (Groq whisper-large-v3, edge-tts Nepali voice), 129 tests, 54-case eval |
| 79fd027 | Opus | English rule in system prompt; Groq -> OpenAI fallback; quiet console |
| 298f817 | Opus | voice "stop"; Urdu-labelled Nepali retried as Nepali; fallback cooldown 10 min |
| 8270798, e7065c8 | Opus | Playwright handoff; repo `CLAUDE.md` token rules; graphify graph |
| 764ee3f | Fable | Round 1: Playwright browser tools (open result, click text, read page, play/pause, like, Gmail reply/send) |
| b80182b | Opus | .gitignore for graphify cache |
| 5d4771c | Opus | echo window 2.5 s -> 12 s; claim guard; "...stop" ends conversation |
| f34b8bb | Fable | Round 2: one Chrome (no silent fallback), back/close tab/new tab/type/press key, Like -> social_react; reviewed Opus fixes (added echo onset-grace rule) |
| 9d30ea4 | Opus | warning flood silenced; strip echoed reply heads; join spelled names |
| ae6ddf1, 173499b | Opus | Round-3 handoff (north star, long-term architecture) |
| 1f61ffc | Fable | Round 3: page map with refs (`browser_snapshot`, `browser_click_ref`, `browser_type_ref`), verified actions, `social_comment`, `gmail_compose`, `ask_chatbot`, current-tab rules, Chrome relaunch; `docs/DESIGN_UI_CONTROL.md`; 200 tests incl. 26 against real headless Chromium |
| 14bd39e .. ed1381e | Opus | exit-word fixes, process exit fixes, echo root cause, history fix, smoke test (details in 4) |
| 93f127a | Opus | replies matched to requests (one-behind bug) |
| 3527704 .. 2b1d656 | Opus | email: guided flow -> yes phrases -> gpt-5.5 writer -> attachments -> computer use -> live fixes -> model-driven email (details in 5) |
| 7bb5e83, d65a497 | Opus | round-4 handoff |

Tests: 129 -> 153 -> 170 -> 200 -> **222** (latest full run 218-222 depending on file; one browser
test flaked once and passed on re-run).

---

## 3. Evals and measurements (all real)

| Measure | Result |
|---|---|
| Fable's 54-case live eval, Groq gpt-oss-120b, before fixes | **43/54 (80%)**; en 20/30, ne 14/15, ne-roman 9/9; avg 14-20 s per request |
| Same, English only, after the English-rule fix | **29/30 (97%)**, avg 5.3 s |
| Smoke test (`scripts/smoke_test.py`, 6 commands, real model + real tools), gpt-4o-mini | **6/6**, twice back to back; "go back" ~17.6 s, others 2-7 s |
| Smoke test with gpt-5.5 | started, did not finish within 8+ min (stuck on a browser step while the user's Gmail compose windows were open); **not measured yet** |
| One gpt-5.5 tool call (open notepad) | 1.1-2.8 s, correct tool |
| One full brain reply on gpt-5.5 ("how are you") | 3.3 s (router 0.7 s + chat 1.2 s) |
| gpt-5.5 writing an email body | 4.2 s |
| Email brain (gpt-5.5) on the user's 6 real utterances | **6/6 correct decisions**, 2-5 s per turn |
| SAPI speech wait loop | returned after **1.2 s** of a **12.4 s** reply (root cause of echo); `WaitUntilDone` waits 12.4 s |
| Computer use (Claude Opus 5.5, toolset), read-only live run | correct screen description, 9.7 s, 0 actions |
| "yes"/"no" phrase understanding, before -> after | yes 3/8 -> 8/8, no 1/5 -> 6/6, traps 4/4 |
| Echo-prefix stripping on real transcripts | 7/7 |

---

## 4. Every problem found live, its root cause, the fix (non-email)

**4.1 English answered in Nepali.** `_system_prompt` added a language line for Nepali and Romanized
Nepali but nothing for English, and the rest of the prompt is Nepali-heavy. Fix: an English line
(79fd027). 20/30 -> 29/30.

**4.2 Wrong version tested.** First voice test ran the old HoloDesk (`Desktop\holodesk`), not brain
v3. Always start from `Desktop\holodesk-brain-v3`.

**4.3 Groq quota.** 200K tokens/day exhausted in ~1 hour; also 8K tokens/minute. Fallback to OpenAI
worked; it now skips Groq for 10 min after a failure (298f817).

**4.4 Speech-to-text.** Nepali written in Urdu script -> Urdu added to Nepali look-alikes (298f817).
Names misheard ("Papil Sharma", "Zemail", "NMCP") -> name hints via `HOLODESK_STT_NAMES` (Fable r2).
Spelled names typed with dashes -> `_join_spelled` (9d30ea4). Whisper invents "Thank you." from room
noise; it ended a conversation -> lone hallucination phrases dropped in `speech/stt.py` (ed1381e).
Spoken email address became "Erfosht kja në jupon dhe Gmail" -> the email model now normalises
spoken and spelled addresses (2b1d656).

**4.5 "Stop" didn't stop.** Exit words matched only exact phrases; then substring matching made
"see you" inside "see youtube" and "thank you, now open gmail" end conversations. Now: a sentence
ending in "stop" (not "don't/never stop") ends it; keywords match whole words in sentences of <= 6
words (14bd39e). Mid-speech interrupt: open palm gesture (mic is off while HOLO speaks).

**4.6 The echo saga (the biggest lesson).** HOLO heard itself and even acted on it
(`YOU: Let me know which video you'd like to open...` -> `TOOL: browser_open_result`). Fixes were
stacked on the symptom: echo window 2.5 -> 12 s (5d4771c), Fable's "speech must start within 1 s of
TTS end" (f34b8bb, which made it worse on this hardware), strip echoed heads (9d30ea4), match by
content (e91edb8). **Root cause, finally measured (ed1381e):** `speak()` polled
`SpVoice.Status.RunningState` right after an async `Speak`; it reads 0 (not started) so the loop
exited after 1.2 s of a 12.4 s reply and the mic opened while HOLO was still talking. Fix:
`while not sapi_speaker.WaitUntilDone(100)`. The content filters remain as a backstop; Fable flagged
them as band-aids.

**4.7 Two Chromes / stale tab.** Tools acted on the automation Chrome while pages opened in the
user's normal Chrome; `close_app chrome` killed the automation Chrome; `document.visibilityState`
is unreliable under the full-screen overlay. Fable r2/r3: no silent fallback, relaunch on a dead
connection, HoloDesk follows tabs it opens. Hand-picked tabs may still be missed.

**4.8 Claims without action.** "I've scrolled down the page for you" with no tool call; later
"I removed the incorrect email reference" after calling `forget_memory`. `_CLAIMS_ACTION` (English
regex) challenges one such reply per turn (5d4771c, verbs extended twice). Nepali claims unchecked.

**4.9 Processes, memory, audio.** Overlay window closed with no message (quiet mode hid it) -> exit
reasons printed (`EXIT:` lines, 14bd39e). The closed overlay left `python.exe` alive (~870 MB);
the next start died with `mkl_malloc: failed to allocate memory` on 8 GB -> `os._exit` on close
(0efa8fd) and in `sys.excepthook` for Ctrl+C/crash (526f109). Four ghost processes were found stuck in
a driver (1 thread each, unkillable even with taskkill); a **reboot** cleared them and also brought
back HoloDesk's voice, which had been silent while the Windows test voice worked.

**4.10 Acting on its own / wrong answers.** A run killed before its reply was saved left an
unanswered request in the 30-min history; the next "hello" re-ran that Google search -> unanswered
user turns are dropped from history (51b346a). Replies came back **one request behind**: a slow Gmail
step outlived the 60 s reply wait and its late answer was given to the next question -> replies carry
the request id (`ts`), late ones are skipped, wait 120 s (93f127a). gpt-oss-120b (Groq) and
gpt-4o-mini wandered on multi-step tasks (opened 3 tabs, clicked random refs, ran out of 8 steps,
chose `gmail_draft_reply` for a new email, `find_files` for a contact) -> main model switched to
**gpt-5.5** (`.env`). "What page is this" answered from history -> prompt rule: look, don't remember.
The 8-step limit message read the internal tool log aloud -> plain sentence (ed1381e).

**4.11 Console noise.** MediaPipe/protobuf `SymbolDatabase.GetPrototype()` warning flooded once per
camera frame after a library re-enabled warnings inside `catch_warnings` -> quiet mode no-ops
`warnings.showwarning` (9d30ea4). Startup C++ lines (pygame, TFLite, W0000) still print.

**4.12 Smoke test pitfalls.** It shared HoloDesk's memory, so a second run answered from the first
run's history ("Notepad is already open") -> in-memory store per run. It kept running after printing
(browser worker thread) -> `os._exit` (5502a9e).

---

## 5. The email saga in detail (the reason for round 4)

**v1 guided script (3527704):** fixed questions: who -> new/reply -> subject -> body -> read back ->
"shall I send?". Unit tests passed. Then:
- "Yes, yes, yes, go ahead, send it" was ignored and the confirmation repeated: `is_yes` was an
  exact word list -> phrase-level yes with a confirmation-word whitelist ("yes, delete everything
  else too" must not approve), "no" wins on mixed (d77a588).
- The user wanted AI to write the email -> gpt-5.5 writer for described bodies / "you choose" subjects
  (d77a588). gpt-5 models reject `max_tokens` and `temperature` (live HTTP 400) -> `brain/llm.py`
  sends `max_completion_tokens` for gpt-5/o-series.
- Attachments (74db296): "Any attachment?" -> `find_files` ranked by spoken words -> pick among up
  to 5 -> `gmail_attach` (Playwright file chooser, no Windows dialog; succeeds only when Gmail shows
  the file name). A regex lost a backslash in a heredoc so Windows paths were not split (936d230 fix).

**Live Gmail test 1 (failures):**
```
YOU:  The subject will be introduction.          -> subject sent literally
TOOL: gmail_compose {'to': 'Erfosht kja në jupon dhe Gmail', ...}
HOLO: ... subject: Locator.fill: Timeout ... get_by_label("Subject") resolved to <tr role="row" ...>
YOU:  ... The new message should go to Sati Swagli.
TOOL: gmail_open_latest {'query': 'Sati Swagli'} / gmail_draft_reply {...}   (agent chose a reply)
TOOL: forget_memory {...}  HOLO: I removed the incorrect email reference.     (false)
YOU:  Close the Gmail right now.   HOLO: Sorry, a new email or a reply to an existing thread?  (trap)
```
Fixes (9ebb3f7, fa37e54): compose fields by `input[name=subjectbox]` and the Message Body textbox
(`browser/sites/gmail.py`, `compose_open`); recipient sanity check and spoken-address conversion;
close/stop/exit leave the flow; every subject/body through the writer; change-anything-before-send
(new recipient -> `gmail_discard_draft` + redraft; other changes refill in place).

**Live Gmail test 2 (still failing, user frustrated):**
```
YOU:  It should go to Sati Swagli. It should be a new email.   HOLO: I didn't catch who.  (rule: name only, <= 4 words)
YOU:  ... S-A-T-I-S-H-W-A-Z-L-E.                               HOLO: I didn't catch who.
TOOL: gmail_compose ... HOLO: the body did not take   (it had: Gmail's read-back was truncated)
HOLO body signed "Best regards, Smarika Koirala"               (invented sender)
YOU:  Just press send.  HOLO: Who should the email go to? / new or reply?   ("send ... mail" restarted the flow)
```
The user also had to remove a wrong recipient chip by hand. **Conclusion: regex/script email flows
fight real speech.** Fix (2b1d656): `ReplyEngine._email_turn` sends each utterance plus the current
draft to gpt-5.5, which returns JSON `{to, mode, subject, body, attachment, action, say}` with action
in ask/draft/send/cancel/leave. Code does Gmail, reads back what Gmail shows, keeps the email open on
failure, signs as `HOLODESK_USER_NAME`. Body check compares the opening only.
**Live check of the email brain on the user's real lines: 6/6 correct, 2-5 s/turn.** Not yet
re-tested end to end by voice with real Gmail.

**Computer use (936d230):** `brain/tools/computer.py`, tool `computer_task(goal)`: Claude Opus 5.5
with `computer_toolset_20260801` (no beta header), screenshots scaled to 1366 px, clicks scaled back,
batch stops at first failure, every result echoes `toolset_name`, pauses with "NEEDS OK:" before
irreversible steps, mouse-to-corner aborts (pyautogui failsafe), halted engine stops it. anthropic SDK
0.85 predates `output_config`/`fallbacks`, so they go in `extra_body`. Live read-only run passed;
**no live clicking task run yet.** Anthropic recommends a sandboxed machine; this drives the real
desktop.

---

## 6. Current architecture (files to know)

- `app/main.py`: overlay, camera/vision threads, voice loop (`VoiceAssistantThread`: wake ->
  `record_with_vad` -> transcribe -> `_dispatch_and_speak` -> follow-up loop), `speak()` (SAPI,
  `WaitUntilDone`; Nepali via edge-tts), echo guards, exit phrases, quiet mode, `os._exit` paths.
- `agents/orchestrator.py`: reads `command_queue`, calls the brain, replies on `voice_reply_queue`
  with the request id.
- `brain/engine.py` (`ReplyEngine`): reply -> pending confirmation -> email turn -> agent loop
  (router picks <= 10 tools, max 8 turns, claim guard, history without unanswered requests).
  Email: `_email_turn`, `_email_brain`, `_draft_now`, `_put_in_gmail`, `_send_email`, `_find_files_for`.
- `brain/email_flow.py`: draft state, file picking helpers.
- `brain/policy.py`: risk tiers, pending confirmation, phrase-level `is_yes`/`is_no`.
- `brain/llm.py`: OpenAI-compatible backend (gpt-5 param handling), `FallbackBackend` (cooldown).
- `brain/tools/`: `system`, `files`, `desktop` (apps, windows, UIA, keys, mouse, look_at_screen),
  `knowledge`, `browser` (page map, refs, social, Gmail incl. attach/discard/open_latest, chatbot),
  `computer` (vision + mouse).
- `browser/playwright_controller.py`, `browser/sites/gmail.py`: Chrome over CDP, Gmail selectors.
- `speech/stt.py`, `speech/tts.py`. `scripts/smoke_test.py`. `evals/run_evals.py`, `evals/cases.jsonl`.
- Tests: `tests/helpers.py` `make_engine(script, extra_tools)` with `FakeBackend`. Pitfall: adding
  many tools switches on the LLM router, which consumes the first scripted response.

---

## 7. Verified vs not verified

Verified live: chat, open/close apps, Google/YouTube search, open result N, go back, read page,
describe screen, scroll, English/Nepali replies, OpenAI fallback, Groq quota fallback, echo root-cause
fix (by measurement), reply/request matching, process exit, smoke 6/6 (gpt-4o-mini), email brain
decisions (6/6), gpt-5.5 writer, computer-use read-only.

Not verified live: Gmail compose with the new field selectors and the email brain end to end; send;
change-before-send with real Gmail (`Discard draft` label unverified); attachments (`Attach files`
label unverified); like/comment on real Facebook (one earlier live like "clicked" but the user saw no
like); ask_chatbot on real Claude.ai; computer_task clicking; smoke test on gpt-5.5; Telegram;
always-on; wake word.

## 8. Open problems

1. Too many narrow tools and per-task code; email alone took two days. Need one general
   see-act-verify loop (round 4).
2. No real-time seeing: the screen is looked at only when a tool asks.
3. Wake word never worked (Whisper `tiny` for wake words hallucinates; code listens for "hey desk"
   while `.env` says "hey holo"). Recommended: openWakeWord. Space/V-sign work.
4. Latency: 2-5 s per model turn; browser steps up to ~18 s; a stuck browser step can hang.
5. Speakers + mic on one laptop: echo guards still matter; headphones remove it.
6. Mid-speech voice interrupt impossible (mic off while speaking); open palm works.
7. Groq free tier too small for real use; OpenAI is the main model now.

## 9. Process lessons for whoever continues

- **Live tests beat unit tests.** Every major bug passed fake-backed tests. Add a live check for each
  fix (smoke test, live eval) and report numbers.
- **Measure the root cause before patching.** The echo got four symptom patches before a short timing
  measurement found it.
- **Small, separate commits; push to `brain-v3-test` only.** The user tests by voice after each batch.
- Windows: backslashes in shell heredocs get eaten; write files with an editor, use raw strings.
- Keep the user's preferences: he decides models and cost; he wants honesty, numbers and plain words.
