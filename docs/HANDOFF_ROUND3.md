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

- Section 3 items 1–4 done (5–6 if cheap), Playwright mocked in tests, existing
  tests green (171 now).
- Eval cases for snapshot→click flows in en / ne / ne-roman.
- Commit and push to `brain-v3-test` only. Say plainly what you could not run,
  and list voice checks: like the post on screen (verify it shows liked), Gmail
  "write an email to Smarika Koirala, subject Hello, saying good morning" (draft
  then send with one confirmation), open a new tab and read it, go back, click
  a named button on Claude.ai or ChatGPT.

## 6. Your notes for the next round

(Fill in.)
