# Handoff round 2: browser reliability (after the first live voice test)

Read this file first. Branch: `brain-v3-test`. Background and round 1 are in
`docs/HANDOFF_PLAYWRIGHT.md` (read only if you need it). Token rules: `CLAUDE.md`.

## 1. What happened in the live voice test (2026-11-13, Windows, real mic)

Your round-1 browser tools (`764ee3f`) were tested by voice. Groq's daily
quota ran out mid-session; the OpenAI fallback answered from then on.

Worked:
- open/close Notepad, open Drive, Google search, YouTube search
- `browser_open_result {'position': 1}` on YouTube: opened the video in the same tab
- `look_at_screen` described the screen correctly
- `social_react` asked for confirmation before liking

Failed (console excerpts, `YOU:` = transcribed user, `TOOL:` = tool actually called):

```
YOU:  ...do you see the first unsponsored result? ...model context protocol. Can you open that link?
TOOL: browser_open_result {'position': 1}
HOLO: I couldn't find the results on the page...
TOOL: browser_click_text {'text': 'model context protocol'}
HOLO: I couldn't find a clickable link for "model context protocol"...
      (look_at_screen in the same minute saw the Google results page)

YOU:  ...can we please like this post?   -> confirm -> "yes"
TOOL: browser_click_text {'text': 'Like'}
HOLO: I couldn't find a clickable "Like" button on the page...
      (the model chose browser_click_text, not social_react)

YOU:  No, no, no, go back.
HOLO: I need your OK first: run this command: ...SendKeys]::SendWait('^w')
      (wrong key, ^w closes the tab; only the DANGER confirm stopped it)

YOU:  ...close this YouTube and take me back to cloud
TOOL: close_app {'name': 'chrome'}          (closed all of Chrome, not the tab)

YOU:  open the Gmail ... in the same Chrome ... new tab
      (opened a separate Chrome window)

HOLO: I'm not able to control the YouTube player directly, so I can't skip the ad
HOLO: I'm not able to interact with that browser permission prompt (YouTube notifications)
HOLO: I can't search within your Gmail directly.
```

## 2. Your task (in priority order)

1. **Two Chromes.** `open_in_automation()` in `brain/tools/browser.py` returns
   None on any failure, and `open_website` / `search_in_browser` then silently
   open the user's normal Chrome. The page the user sees is not the page the
   tools act on, which explains the Google and Facebook failures. Also
   `close_app chrome` kills the automation Chrome, and the next open may hit a
   dead CDP connection. Fix: when `HOLODESK_BROWSER_AUTOMATION_ENABLED=1`,
   never fall back silently. Reconnect or relaunch the automation Chrome, and if
   that fails return an error the user hears. Confirm the tools act on the
   active tab of the window the user sees.
2. **Missing browser actions**, so the model said "I can't": add
   `browser_back`, `browser_close_tab` (prefer over `close_app chrome` when a
   tab is meant), `browser_new_tab` (same window), `browser_type` (type into a
   field by label/placeholder/role, e.g. Gmail search, then Enter), and
   `browser_press_key`. Launch the automation Chrome with notifications denied
   (`--disable-notifications` or a context permission) so that prompt never appears.
3. **Tool choice.** "Like this post" must reach `social_react`, not
   `browser_click_text 'Like'` (Facebook's Like is an aria-label, often with no
   visible text). Use tool descriptions/keywords, or have `browser_click_text`
   hand Like/React to `social_react`. "Skip ad" should use
   `browser_click_text 'Skip'`; say so in its description.
4. **(Small) STT vocabulary.** Whisper heard "Papil Sharma" (Kapil Sharma),
   "Zemail" (Gmail), "Maori ka koi raada" (Smarika Koirala). Add common app
   and site names to the bias prompt in `speech/stt.py`.

Not your task: the Groq-vs-OpenAI primary model choice (the user decides);
always-on, Telegram, Twilio, wake word (later).

## 3. Fixes I (Claude Opus, local) made. Please review them and suggest improvements

Commit: see `git log` after `b80182b`. All 155 tests pass locally.

| # | Problem in the test | Root cause | Fix |
|---|---|---|---|
| A | HOLO heard itself (`YOU: Let me know which video you'd like to open...`) and once ran `browser_open_result` on its own echo | `ECHO_LATENCY_WINDOW_SEC = 2.5` in `app/main.py`, but latency is measured at check time: after the 5 s follow-up silence wait (`FOLLOWUP_SILENCE_MS`) plus ~1.5 s STT. Every echo was rejected on time before the words were compared | Window to 12 s. Echoes now print `YOU: (ignored, own echo) ...`. Checked on the real transcripts: 3/3 pure echoes caught, 3/3 real commands kept, a mixed echo+speech line kept |
| B | `HOLO: I've scrolled down the page for you.` with no tool call | "Only claim what a tool did" was a prompt sentence, not enforced | `brain/engine.py`: if a reply claims an action (`_CLAIMS_ACTION`, English only) and no tool ran this turn, the model is challenged once to call the tool or admit it didn't. 2 new tests |
| C | "Y'all stop.", "Don't talk." went to the brain as chat | Exit check allowed only filler words around "stop" | `_is_exit_phrase`: a sentence ending in "stop" ends the conversation ("stop the timer" doesn't); added "don't talk". 8/8 real transcript cases pass |

Review questions for you:
- A: is a time window the right signal at all? Measuring from when the
  recording *started* relative to TTS end would be tighter. Is that worth it?
- B: a regex on the reply is crude, and Nepali claims ("खोलियो") are not
  checked. Is there a better structural check in the engine loop?
- C: any case where ending on "stop" would wrongly end a real command?

Change my code only if you find a real bug; otherwise put suggestions in the
commit message or section 5 below.

## 4. Done means

- Section 2 items 1–3 done (4 if cheap), with Playwright mocked in tests.
- `python -m pytest -q` green (155 now, plus yours).
- Eval cases added for the new tools in en / ne / ne-roman.
- Commit and push to `brain-v3-test` only. Say plainly what you could not run
  and list the exact voice checks the user should do:
  Google result by position and by text, "go back", "close this tab",
  "open Gmail in a new tab", "search Smarika Koirala in Gmail", "like this post"
  on Facebook, "skip the ad".

## 5. Your notes for the next round

(Fill in: answers to the review questions in section 3, anything unverified.)
