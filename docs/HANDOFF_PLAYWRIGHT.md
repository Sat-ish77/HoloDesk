# Handoff: stitch Playwright browser tools into brain v3

Read this file first. It is the single source of truth for this task.
Branch to work on: `brain-v3-test`. Do not push to any other branch.

## 1. Where things stand (verified 2026-11-12/13 on the user's Windows laptop)

`brain-v3-test` = Fable's `claude/brain-v3` (tool-calling brain, 37 tools,
SAFE/ACT/DANGER/BLOCKED policy, SQLite memory, Telegram bridge, Nepali speech)
plus two fix commits:

- `79fd027` English requests got no language rule, so the Nepali-heavy system
  prompt pulled replies into Nepali. Added the `else` branch in
  `ReplyEngine._system_prompt`. OpenAI fallback (`FallbackBackend` in
  `brain/llm.py`, key `OPENAI_API_KEY`, model `HOLODESK_FALLBACK_MODEL`,
  default `gpt-4o-mini`). Quiet console (`HOLODESK_QUIET`, default on: only
  `YOU:` / `HOLO:` / `TOOL:` / error lines).
- `298f817` Voice "stop" phrases end the conversation (`_is_exit_phrase` in
  `app/main.py`); Whisper's Urdu label for Nepali is retried as Nepali
  (`speech/stt.py`); after one primary failure the fallback is used directly
  for 10 minutes.

Measured:

| Check | Result |
|---|---|
| `python -m pytest -q` | 132 passed |
| Live eval, all languages (before fixes) | 43/54 (80%); en 20/30, ne 14/15, ne-roman 9/9 |
| Live eval, English only (after fixes) | 29/30 (97%), avg 5.3 s |
| Voice test | open/close Notepad in Nepali OK, open Facebook OK, YouTube search OK, scroll OK, Bikram Sambat date OK |

Groq's free tier hit its 200K tokens/day limit during the voice test; the
OpenAI fallback answered every turn after that.

## 2. Known problems (not your task unless listed in section 3)

1. **No in-page browser control.** "Open the first video" on YouTube just
   scrolled. No tool can click inside a web page, like a post, or use Gmail.
   This is the task.
2. Self-echo: after HOLO speaks, the mic sometimes transcribes HOLO's own
   last sentence as the user (`YOU: You can check the results now.`). The
   echo check in `app/main.py` (`_is_echo_of_ai`) misses it with neural TTS.
3. Whisper mishears Romanized/Nepali speech (e.g. "Chroma Fissure Kölöne").
   `HOLODESK_STT_LANGUAGE=ne` is the user's choice to make, not a code change.
4. The VLC-install eval case: the model asks permission in prose instead of
   calling the tool and letting the policy ask.

## 3. The task: Playwright browser tools

The working Playwright code already exists on branch
`codex/holo-chatbot-3d-overlay` (the user's older local branch, now pushed).
Port it; do not rewrite it from scratch:

```
git fetch origin codex/holo-chatbot-3d-overlay
git show origin/codex/holo-chatbot-3d-overlay:browser/playwright_controller.py
git show origin/codex/holo-chatbot-3d-overlay:browser/sites/facebook.py
git show origin/codex/holo-chatbot-3d-overlay:browser/sites/instagram.py
git show origin/codex/holo-chatbot-3d-overlay:browser/sites/gmail.py
git show origin/codex/holo-chatbot-3d-overlay:browser/form_filler.py
git show origin/codex/holo-chatbot-3d-overlay:HANDOFF_FABLE.md   # section 2: password and Chrome-profile rules
```

That branch also has a graphify knowledge graph at `graphify-out/graph.json`.
If `graphify` is installed, `graphify query "<question>"` finds the right
lines faster than reading files.

Build `brain/tools/browser.py` and register it in `brain/tools/__init__.py`.
Tools to add (names are suggestions):

| Tool | Risk | Does |
|---|---|---|
| `browser_open_result` | ACT | Open the Nth search result / video on the current page (YouTube first) |
| `browser_click_text` | ACT | Click a link or button on the current page by its visible text |
| `browser_read_page` | SAFE | Return the page title, URL and main visible text (truncated) |
| `browser_play_pause` | ACT | Play/pause the current video |
| `social_react` | DANGER | Like/react to the current Facebook or Instagram post |
| `gmail_draft_reply` | ACT | Draft a reply to the open email (not sent) |
| `gmail_send` | DANGER | Send the drafted email |

Rules (non-negotiable):

- DANGER tools go through the existing confirm flow in `brain/policy.py`.
  Do not build a second confirmation system.
- Passwords are never stored, logged, spoken or sent to an LLM. Login is done
  by Chrome's own password manager in the "HoloDesk Automation" profile, as
  the old branch does it.
- Every tool returns an observation (URL, title, what was clicked, field
  value) so the reply is built only from tool results.
- Keywords in English, Nepali (Devanagari) and Romanized Nepali, like the
  other tools.
- Playwright is imported lazily inside the tool, so the brain still starts
  when Playwright is not installed.
- Keep the diff minimal. No refactors of files you don't need to touch.

## 4. Done means

1. Unit tests for every new tool with Playwright mocked (pattern:
   `tests/test_tools.py`). `python -m pytest -q` passes (132 now, plus yours).
2. A few cases per tool in `evals/cases.jsonl`, in en / ne / ne-roman.
3. Section 1 of this file updated with what you changed and the test count.
4. Committed on `brain-v3-test` and pushed. You cannot run Windows UI or a
   real browser in the cloud; say so plainly in the commit message and list
   what the user must test by voice.

## 5. How the user will test on Windows

```
cd C:\Users\Dipendra\Desktop\holodesk-brain-v3
git pull
C:\Users\Dipendra\AppData\Local\Programs\Python\Python312\python.exe -m pytest -q
C:\Users\Dipendra\AppData\Local\Programs\Python\Python312\python.exe app\main.py
```

Voice checks: "search Kapil Sharma on YouTube" then "open the first video";
open Facebook, "like this post" (must ask first); open Gmail, "reply to this
email saying I'll be there" (drafts), "send it" (must ask first).
