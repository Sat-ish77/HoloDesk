# Handoff round 3: interact with any page element, not per-site selectors

Read this file first. Branch: `brain-v3-test`. Earlier rounds:
`docs/HANDOFF_ROUND2.md` (your notes in its section 5), `docs/HANDOFF_PLAYWRIGHT.md`.
Token rules: `CLAUDE.md`.

## 1. Goal (the user's words, condensed)

Control the whole laptop by voice, from the laptop or the phone (Telegram),
including any website: Gmail compose with recipient and subject, liking a
specific post, Claude.ai, ChatGPT, Drive. "It still can't freely interact with
the UI elements on screen; without that, 100% voice control is impossible."

Per-site CSS selectors (`RESULT_SELECTORS`, `LIKE_SELECTORS`, Gmail's `Reply`)
cannot scale to "any page". Round 3 replaces guessing with a page map the
model reads.

## 1a. What the user truly wants (the north star; this is THE main focus now)

HoloDesk should do, by voice (laptop mic now, phone via Telegram later),
anything the user could do sitting at the laptop: **literally see the screen
and act on it**, properly and reliably, and never pretend.

First, in this order, these must really work end to end:

1. **Social:** like a specific post the user is looking at, and **comment** on
   it (write the comment, read it back, post after one confirmation).
2. **Gmail:** draft a new email (recipient by name, subject, body), read it
   back, **send** after one confirmation; also reply to an open email; search mail.
3. **Talk to Claude (claude.ai, also ChatGPT):** open it, type a prompt into
   the chat box, send, wait for the answer to finish, **read the answer back**.
4. **Files:** save, find ("where is my resume?"), open, move and rename files
   and folders by voice. The tools exist (`find_files`, `move_path`,
   `open_path`, `write_text_file`); make sure they are reachable and reliable by
   voice, and that "save this" works from a page/app where it makes sense.
5. **General UI:** click any button/link/menu/tab, fill any field, scroll to
   something, pick from a dropdown, in the browser first, then native Windows
   apps (Windows UI Automation tree via `list_ui_elements`/`click_ui_element`).

Every action is **see → act → verify**: look at the current state, act on one
element, look again, and report only what is verified. If it can't, it says
so plainly and says what it tried.

**Think first, then build.** Before coding, write `docs/DESIGN_UI_CONTROL.md`
(one page max): how HoloDesk should see and act on any UI, and how it gets as
close as possible to the north star. Cover at least:
- browser: accessibility snapshot + act-by-ref (section 3.1) vs DOM selectors
  vs screenshots; how to point at "this post" (the one in the viewport centre);
- native apps: the Windows UIA tree, and when a vision fallback (screenshot →
  coordinates, e.g. Claude computer use or OmniParser-style element detection)
  is needed, with its cost/latency. Recommend; don't build vision this round;
- the see→act→verify loop: where it lives (tools vs engine), step limits,
  how failures are reported;
- multi-step tasks (compose: open → fill To → pick suggestion → subject →
  body → read back → confirm → send) without the model losing its place;
- safety: what stays DANGER (post, comment, send, delete, buy), one
  confirmation that quotes exactly what will happen;
- what you'd measure to know it works (task success on a fixed list of voice
  tasks, steps, seconds).
Then implement section 3 following that design. If the design shows a better
path than section 3 says, take it and explain why in section 6.

## 1b. Long-term architecture (design for it now, build it in later rounds)

Example task the user wants to give from the phone, laptop out of reach:
"Open Canvas, go to the dashboard, open the assignment instructions, open
Claude in a new tab, paste the instructions and ask for help, save the file I
prepared to the Desktop, go back to Canvas, open the submission page, upload
the file." Many apps, many steps, no laptop in sight. (Submitting work the user
did not write is off the table; the agent uploads files the user prepared.)

1. **Cheap seeing, layered, cheapest first:**
   (a) accessibility tree (browser ARIA snapshot, Windows UIA): free, fast,
   exact. Default for every step.
   (b) change detection: perceptual hash of the active-window screenshot; skip
   re-analysis when nothing changed. (The user's earlier holodesk-lens project
   used frame differencing to verify a fan slowing down; same idea.)
   (c) screenshot + vision model only when (a) has nothing usable: downscale,
   crop to the active window, optionally number detected boxes (Set-of-Mark /
   OmniParser-style) so the model answers "click #7", not coordinates.
2. **Task recipes (learned skills).** When a task succeeds, save its steps as a
   recipe in SQLite memory: each step = action + element descriptor (role,
   accessible name, nearby text/landmark; never raw coordinates) +
   precondition + expected postcondition. Next time: replay without the LLM,
   checking pre/postconditions per step. If a step's element is missing (UI
   changed), only that step falls back to snapshot → LLM (→ vision), and the
   repaired step is written back. Recipes are per task intent ("like the post on
   screen", "submit file to Canvas assignment X") with parameters.
3. **Verified completion, no hallucination.** Every step's success is a
   code-checked fact (URL, element state like "Remove Like"/"Submitted", field
   value, file exists). The final reply is built only from those facts; a failed
   check reports the exact step it stopped at. Vision verifies only when no
   fact check exists.
4. **Remote control.** Telegram voice notes already reach the brain. Long
   tasks run in the background with progress messages and a final screenshot;
   DANGER confirmations go to the phone (Yes/No). Later: Twilio, both outbound
   (it calls the user on important events) and inbound (the user calls, speech
   goes through the same engine, the reply is spoken). The laptop must stay awake
   and unlocked for UI actions, so the allowlist and phone confirmations are
   mandatory.

Build order: round 3 = page map + act-by-ref + verify (this round). Round 4 =
recipes + change detection. Round 5 = Telegram background tasks + phone
confirmations. Round 6 = Twilio + vision fallback. Round 3's design doc should
show where recipes plug in, so round 4 doesn't need a rewrite.

## 2. Live voice test of round 2 (2026-11-13, Windows, real mic)

Worked: Google search plus `browser_open_result` 1; `look_at_screen` summary;
`browser_new_tab` (it opened); `browser_type` into Gmail "Search mail" with Enter;
`click_ui_element 'Compose'` (Windows UIA) opened Gmail compose.

Failed:

```
TOOL: browser_back {}
HOLO: I tried to go back, but it timed out...        (it did go back)

TOOL: browser_new_tab {'target': 'facebook'}         (Facebook visible on screen)
TOOL: browser_read_page {'max_chars': 1500}
HOLO: It seems I'm still on the Google search results page...
      -> the tools stayed on the old tab. document.visibilityState is not a
         usable signal under the full-screen overlay (your round-2 caveat).

YOU:  Can you see Facebook or not?
TOOL: list_windows {}                                 (wrong tool for "what page")

YOU:  I want to like this picture.            (the post the user had just asked about)
HOLO: ...would you like me to like the post...?      (model asks in prose)
HOLO: I need your OK first: click 'Like'...          (policy asks again)
TOOL: browser_click_text {'text': 'Like'}
HOLO: Done ... Clicked 'Like'.
YOU:  I didn't see the post being liked yet.   -> two more confirmations, same result
      -> clicked some "Like" (first in the DOM? on the hidden tab?), not the
         post on screen, and never verified the result.

TOOL: gmail_draft_reply {'body': 'Good night and good morning.'}
HOLO: ...I can't find the Reply button.  (x3; user wanted a NEW email: no compose tool)
      After Compose opened, nothing could fill To / Subject / Body.

HOLO: ...I still need to find the Reply button. Let me check again.   (then nothing)
```

Also: the automation Chrome is a separate profile
(`%LOCALAPPDATA%\HoloDesk\chrome-profile`). The user thought it was incognito.
That is by design (Chrome 136+ blocks debugging the default profile); say so
once when it first launches ("This is HoloDesk's own Chrome; log in once").

## 3. Your task

1. **Page map + act by ref (the core).** Add:
   - `browser_snapshot`: SAFE. Returns a compact list of the *visible*
     interactive elements of the current tab (role, accessible name, value,
     state such as pressed/checked, and a short stable ref like `e12`), e.g.
     from Playwright's accessibility/ARIA snapshot or a DOM walk limited to the
     viewport. Cap the size (~150 elements / ~4k chars); include the page title
     and URL. Group by landmark/article where possible so "this post" means
     the article nearest the viewport centre.
   - `browser_click_ref`, `browser_type_ref` (with optional Enter), and
     optionally `browser_hover_ref`. Risk is decided from the element's name and
     role with the same rules as `browser_click_text` / `browser_type`
     (send/post/buy/delete/Enter-in-a-non-search-box = DANGER, Like/React =
     DANGER). Refs expire on navigation; a stale ref returns a clear error
     telling the model to snapshot again.
   - Tool descriptions and the system prompt: for anything on a web page,
     snapshot first, then act by ref. Keep `browser_click_text` as the quick path.
2. **Verify after acting.** Click/type/react tools return the element's state
   after the action (e.g. Like `aria-pressed` / label "Remove Like", field
   value, new URL). The reply must reflect the verified state. "Clicked" alone
   is not success.
3. **Current tab.** After `browser_new_tab`, `open_in_automation`, or a
   click that opens a tab, that tab becomes the current page (`use_tab`). Use
   visibility only when exactly one tab reports visible; otherwise keep the
   last tab HoloDesk used. `browser_back`: a timeout with a changed URL is success.
4. **Gmail compose.** `gmail_compose(to, subject, body)` = ACT, draft only:
   opens compose if needed, fills To (type the name, pick the autocomplete
   suggestion, and return the resolved address so the user can hear it),
   Subject, Body. `gmail_send` must work for compose drafts too (DANGER,
   quotes recipient + subject + body). If the snapshot tools make this a thin
   wrapper, good.
5. **One confirmation, not three.** The model asked in prose, then the policy
   asked again. Tell the model in the prompt that the system asks for DANGER
   actions and it must call the tool directly. If the same DANGER action is
   re-requested right after one was confirmed, do not stack confirmations.
6. **Tool choice nudges:** "what page / can you see X tab" goes to
   `browser_snapshot` or `browser_read_page`, not `list_windows`. The claim
   guard in `brain/engine.py` (`_CLAIMS_ACTION`) misses promises such as "Let
   me check again." with no tool call; extend it cheaply if you can.

Out of scope: native-app vision/computer-use (phase 2, the user decides cost),
wake word, Telegram setup, Twilio, always-on.

## 4. What I (Claude Opus, local) fixed this round. Review briefly

All 171 tests pass. Commit after `f34b8bb`.

- **Warning flood** (protobuf `SymbolDatabase.GetPrototype` once per camera
  frame): a library re-enabled warnings mid-session inside `catch_warnings`.
  Quiet mode now also sets `warnings.showwarning` to a no-op. Verified: nothing
  prints even under `simplefilter("always")`.
- **Echo prefixes:** lines like "Would you like me to click it? Yes, please
  click it." kept HOLO's tail. `_strip_echo_prefix` in `app/main.py` cuts the
  longest (3+ word) head that equals the end of HOLO's last reply. 5/5 real
  transcripts correct, including "open the first one" kept.
- **Spelled names:** "S-M-A-R-I-K-A K-O-I-R-A-L-A" was typed into Gmail
  with dashes. `_join_spelled` in `brain/engine.py` turns it into "Smarika Koirala"
  before the model sees it. 1 new test.

## 5. Done means

- `docs/DESIGN_UI_CONTROL.md` written first (section 1a).
- Section 3 items 1–4 done (5–6 if cheap), Playwright mocked in tests, existing
  tests green (171 now). Commenting on a post and the Claude.ai
  type → send → read-answer flow work through the snapshot tools (or a thin
  wrapper), and file find/move/open is reachable by voice.
- Eval cases for snapshot→click flows in en / ne / ne-roman.
- Commit and push to `brain-v3-test` only. Say plainly what you could not run,
  and list voice checks: like the post on screen (verify it shows liked), Gmail
  "write an email to Smarika Koirala, subject Hello, saying good morning" (draft
  then send with one confirmation), comment "congrats!" on the post on screen
  (one confirmation), ask Claude.ai "what is MCP in one line" and hear the
  answer, "find my resume and move it to Documents", open a new tab and read
  it, go back.

## 6. Your notes for the next round

Written by Fable in the cloud, 2026-11-13. Design and review of the earlier
fixes: `docs/DESIGN_UI_CONTROL.md`.

### What was verified, and how

200 tests pass. New this round: 26 tests in `tests/test_page_map.py` run in a
**real headless Chromium** against local fixture pages (`tests/fixtures/`: a
feed, a mail client, a chatbot, a settings form). The real controller was also
driven by hand over a live DevTools connection (open, snapshot, like, new tab,
click that opens a tab, back, close tab, Chrome killed and restarted).
The full suite now takes about 40 s; the browser tests skip themselves if
Playwright finds no Chromium, Chrome or Edge.

NOT run: Facebook, Instagram, Gmail, Claude.ai, ChatGPT, Windows, the overlay,
a microphone, a live model, the live eval (19 new cases, 111 total). The
fixtures prove the mechanism in a browser, not that those sites behave alike.

### Where I left section 3

- Page map by our own DOM walk (`brain/tools/pagemap.py`), not Playwright's
  ARIA snapshot; reasons in the design doc. Open shadow roots are walked.
  **Iframes are not.**
- `browser_hover_ref` not built (no task needed it).
- Intent tools added on top of the map, with no site selectors:
  `social_comment`, `ask_chatbot`, `gmail_compose`. `social_react` now uses
  the map too; `LIKE_SELECTORS` is gone. `gmail_compose` / `gmail_send` still
  use the label names in `browser/sites/gmail.py` ("To", "Subject", "Message
  Body", `[email]` chips), unverified on real Gmail. If they miss, compose
  through `browser_snapshot` + `browser_type_ref` still works.
- `browser_snapshot` is always offered when automation is on; it adds
  `browser_click_ref` / `browser_type_ref` to the turn. Only the newest map
  stays in the conversation. Step limit raised from 8 to 12.
- One confirmation: the prompt tells the model the system asks; a confirmed
  action that **failed** may be retried once within 2 minutes without asking
  again (same tool, same arguments). A success is never a standing approval.
- Tabs: HoloDesk follows tabs it opens (new tab, a click that opens one). It
  switches to a tab the user chose by hand only when the current tab reports
  hidden and exactly one other reports visible.
- Found on a real Chrome and fixed: after Chrome was killed, the controller
  still looked connected and the next open failed. It now asks the browser
  for its version before each use and rebuilds the connection if that fails.
- Files (1a item 4): no code change. `find_files`, `move_path`, `open_path`
  are reachable (eval cases added). "Save this" from a page is not built.

### Most likely to need a fix after the live test

1. Facebook's comment box is a rich editor; `fill()` may not register. The tool
   then reports the box value it read and posts nothing.
2. Which element counts as the post: grouping uses the outermost
   `article` / `[role=article]`. If Facebook nests the feed differently, the
   `ON SCREEN` group is wrong. `browser_snapshot` output shows the grouping.
3. Chat answers are read as "new lines on the page since the prompt"; site
   chrome may leak into the answer.
4. `elementFromPoint` hides elements under a transparent overlay inside the
   page (some sites use one); they would be missing from the map.

### Round 4 hooks

Every act returns `element` (role, name, group), `before` and `after`. A recipe
step is that record plus the tool name; replay finds the element by
role + name + group in a fresh map and compares `after`.
