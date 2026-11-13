# Design: how HoloDesk sees and acts on any UI (round 3)

## 1. Is the approach right?

Yes, with three changes to section 3 of the handoff.

- **Page map by a DOM walk we own, not Playwright's ARIA snapshot.** The ARIA
  snapshot gives no stable refs through the public API and its format moves
  between versions. An injected script lists the *visible* interactive elements
  (role, accessible name, value, state), tags each with `data-holo-ref`, and
  groups them by dialog, post (`article`) or landmark. Acting by ref is then a
  plain locator. A navigation wipes the tags, so a stale ref fails loudly.
- **"This post" is decided in code.** The map marks the post nearest the
  viewport centre `ON SCREEN`; an open dialog outranks it. The model no
  longer picks among fifty "Like" buttons.
- **Keep a few intent tools on top of the map.** Compose, comment, like and
  "ask a chatbot" are 5 to 8 steps each. Through raw snapshot/click/type the
  model loses its place and each step costs a model call and a snapshot of
  tokens. A wrapper runs the steps in code, verifies each, and asks once.
  These wrappers contain no site selectors; they use the same map.

See → act → verify lives **inside each tool** (one element, checked before and
after). The engine only sequences steps (limit 12) and keeps just the newest
page map in context. Failures name the step that stopped and what was seen.

Native apps: same contract over the Windows UIA tree (`list_ui_elements`,
`click_ui_element`), next round. Vision (screenshot → numbered boxes → "click
#7") only when both trees are empty: canvas apps, games, remote desktops.
It costs about 1 to 3 s and an image call per step, so never the default.

Recipes (round 4) plug in at the tool result: every act returns the element
descriptor (role, name, group) and before/after state, never coordinates. A
recipe is that list; replay re-finds each element by descriptor and checks the
recorded after-state, and only a failed step goes back to the model.

Safety: post, comment, send, delete, buy, like and Enter outside a search box
stay DANGER through `brain/policy.py`. One question that quotes the text and
the target. Passwords are never read or typed.

Measure: a fixed list of voice tasks (the handoff's section 5 list), scored on
success verified by a person, model calls, seconds, confirmations asked.

## 2. Earlier fixes by Claude Opus (from commit messages and diffs only)

| Fix | Verdict | Why |
|---|---|---|
| English reply rule (`79fd027`) | keep | root cause, measured 20→29/30 |
| OpenAI fallback + 10 min cooldown (`79fd027`, `298f817`) | keep, change later | a per-minute 429 also triggers 10 paid minutes; read `retry-after` and cool down only when it is long. Page maps and screen text go to OpenAI while it is active |
| Quiet console by replacing `builtins.print` (`79fd027`) | band-aid, keep for now | hides every print that lacks a prefix, including tracebacks printed by libraries; move to `logging` |
| `warnings.showwarning` no-op (`9d30ea4`) | band-aid, keep for now | root cause is the mediapipe/protobuf version pair; pin protobuf |
| Exit on "stop" (`298f817`, `5d4771c`) | keep | with the "don't stop" guard; "make the video stop" still exits |
| Urdu → Nepali retry (`298f817`) | keep | same class as Hindi |
| Echo window 12 s (`5d4771c`), echo-head strip (`9d30ea4`) | band-aids, keep for now | three layers now guess at echo after the fact. Root cause: the mic records while HOLO speaks. Fix: gate the recorder during TTS, or use a headset / echo cancellation |
| Claim regex (`5d4771c`) | band-aid, keep and extend | English only. This round adds verified tool results; the regex stays as the backstop and now also catches promises ("let me check") |
| `_join_spelled` (`9d30ea4`) | keep, change | "U-N-T" became "Unt"; short runs now stay upper case |

## 3. Top 3 risks

1. **The map is only tested on fixture pages.** Real Facebook, Gmail and
   Claude.ai use virtualised lists, custom editors and iframes. Expect the
   first live run to need fixes to naming or grouping, not to the design.
2. **Wrong tab.** Chrome's visibility signal is unreliable under the overlay.
   HoloDesk now follows only tabs it opened itself; a tab the user switches to
   by hand is not followed unless Chrome clearly reports it.
3. **Token and rate limits.** A page map is about 1k tokens. Free-tier Groq
   allows about 8k a minute, so multi-step web tasks will hit the fallback
   model often. The wrappers and "newest map only" reduce this; they do not
   remove it.
