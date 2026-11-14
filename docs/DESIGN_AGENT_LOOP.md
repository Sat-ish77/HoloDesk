# Design: one loop that sees, acts and checks (round 4)

## Verdict on the current architecture

Right parts: the risk policy, tools that read back what they changed, the page
map with refs, one Chrome. Wrong shape around them. Four faults caused most of
`HISTORY.md` section 5:

1. **Two brains.** `_email_turn` took the conversation away from the agent
   loop and kept the draft in a Python object. Every sentence it had no rule
   for became a trap. State belongs on the screen; the model reads it there.
2. **A router before the model.** A small model picked 10 of 59 tools from
   keywords. The driver could not use what it was not handed (`find_files`
   for a contact). It also cost 0.7 s per request.
3. **A confirmation ended the task.** After "yes" the action ran and the
   reply was a template; the model never saw the result, so nothing was
   checked and multi-step tasks stopped halfway.
4. **"Done" was the model's word.** Tools verify single elements; nobody
   checked the goal. The claim regex is English-only and guesses.

## The loop

```
look  ->  act  ->  (fresh view comes back with the result)  ->  ... ->  check  ->  reply
```

- **Eyes, cheapest first.** `look` returns a map with refs: the page map for
  HoloDesk's Chrome (`e12`), the Windows UI tree for any other window (`u7`).
  `look_at_screen` reads pixels. `computer_task` (Claude, pixels + mouse) is
  the last resort for what has no tree: about 10 s a step and it cannot tell
  the policy what it clicks, so it must not be the main loop.
- **Hands.** `click(ref)`, `type(ref, text)`, keys, scroll. Every act returns
  the element before and after **and the new view**, so the next step always
  uses fresh refs and needs no extra look. Only the newest view stays in
  context (about 1k tokens).
- **Risk is judged on the element's name**, by `brain/policy.py`, never by
  the model. One question that quotes the action. "Yes" **resumes** the task;
  anything else said at that point steers it.
- **Check.** After a task that acted, a second, cheap model call sees the
  request, the reply and the screen now, and must quote the proof from the
  screen. Code checks the quote is really there. No quote: one more round,
  then an honest "I could not confirm".
- **Obedience.** One brain, so there is no script to fight. New words during
  a task (`engine.steer`) override the plan between steps; "stop" ends it.
- **Skills, not flows.** `gmail_compose`, `gmail_attach`, `gmail_send` stay as
  one-call shortcuts with live-fixed selectors. They hold no conversation
  state. The same email can be done with look / click / type.

Seeing "in real time": a fresh look per step is realistic (map: under 0.1 s on
a page; screenshot to a model: 3 to 10 s and about 1.4k tokens). Continuous
video is about 84k tokens a minute at 1 frame a second; not worth it. A free
watcher (hash of a small screenshot each second) can say "the screen changed"
and is the right next step for "tell me when it finishes"; not built here.

Model: gpt-5.5 drives (1 to 3 s a step, measured); the checker and memory use
the fast model. A typical task is 3 to 6 driver steps plus one check.

## Deleted

| Deleted | Replaced by |
|---|---|
| `_email_turn`, `_email_brain`, `_draft_now`, `_put_in_gmail`, `_send_email`, `brain/email_flow.py` | the loop + Gmail skills; draft state is read from Gmail |
| LLM tool router, `registry.select`, router settings | a fixed menu; rare tools via `find_tool` |
| `social_react`, `social_comment`, `ask_chatbot` | look / click / type / `wait_for_page` |
| `browser_snapshot`, `browser_click_ref`, `browser_type_ref`, `browser_click_text`, `browser_type`, `browser_press_key`, `list_ui_elements`, `click_ui_element`, `mouse_click`, `type_text` | `look`, `click`, `type` |
| "confirmation ends the task" and its template reply | pause and resume |

Kept on purpose: the claim regex (only for replies with no tool call at all),
the echo guards, and every tool verified live (`browser_open_result`,
`browser_back`, `browser_read_page`).

Delete next, once the live eval is green: the Gmail skills if tasks 3, 4 and 8
pass with look / click / type alone; `computer_task`'s own "NEEDS OK" prompt.

## Risks

1. The Windows UI tree path has never run on Windows. If it is slow or empty
   on real apps, native tasks fall back to keys and `computer_task`.
2. The checker can be wrong in both directions. It never repeats an action
   itself; it only sends the driver back to look.
3. Cost: every step sends the whole menu (40 tools) to gpt-5.5.
