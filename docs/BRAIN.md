# HoloDesk Brain v3

A tool-calling brain for HoloDesk: one agent loop that can control the laptop,
understands English and Nepali, remembers across sessions, and is reachable
from your phone. It needs **no GPU**: the language model and the heavy speech
model run on Groq's free tier.

Everything here was written and unit-tested on Linux with a fake LLM. It has
**not yet been run on Windows with a real model, mic or Telegram bot**. Section
"First run" is the checklist for that; section "Not verified yet" lists what to
watch.

## What changed

| Before | Now |
|---|---|
| Regex and keyword lists pick the action | The model picks from 37 tools by schema; new phrasing needs no code |
| Chat model could say "done" without doing anything | A reply can only claim an action if a tool result confirms it |
| Last 10 turns in RAM, lost on restart | SQLite memory: facts, standing instructions, searchable history, diary |
| English only | English, Nepali (Devanagari) and Romanized Nepali, in and out |
| Only at the desk | Telegram bridge: text or voice notes from anywhere |
| Runs while the overlay is open | Headless daemon, starts at login, restarts itself |
| Confirm-before list checked by substring | Four risk tiers, a kill switch and an audit log |
| No tests | 128 unit tests + a 54-case live eval in three languages |

The old regex router is still there. If the model is unreachable, or you set
`HOLODESK_BRAIN=0`, HoloDesk behaves exactly as before.

## Architecture

```
 voice (overlay)        phone (Telegram)
      │                      │
      └──────► ReplyEngine ◄─┘            brain/engine.py
                 │
   1. pending confirmation?   yes / cancel handled without the model
   2. tool router             fast model picks ≤6 tools; keywords fill to 10
   3. system prompt           identity, language rules, time, warm memory
   4. agent loop (≤8 turns)   model calls tool → policy → run / ask / refuse
   5. save turn, learn facts  background, on the fast model
                 │
        Policy (brain/policy.py)
   SAFE     runs                     list files, status, read screen
   ACT      runs                     open app, type, click, volume
   DANGER   asks "yes?" first        delete, kill, shutdown, overwrite,
                                     any shell command not provably read-only
   BLOCKED  never, even after yes    format disk, wipe system folders,
                                     encoded payloads, disable Defender
                 │
        Tools (brain/tools/)
   system.py     run_powershell, system_status, list/kill/watch process, power, volume
   files.py      list, read, write, find, move, delete, open (home folder only)
   desktop.py    apps, websites, windows, UI elements by name, keys, mouse,
                 clipboard, screenshot, look_at_screen, timer
   knowledge.py  remember, recall, forget, date/time + Bikram Sambat, notify phone, audit
```

Ideas borrowed from isair/jarvis (design only, no code: its licence is
non-commercial share-alike): tool router before the loop, a fast/chat model
split, warm profile injected into every reply, fact branches
(user / directives / world), fail-open fallbacks, tools return raw data and
the model does the wording, and an eval suite that is part of the repo.

## First run

```powershell
pip install -r requirement.txt
python -m pytest                       # 128 tests, about a second
python app\main.py                     # overlay, as before
```

With `GROQ_API_KEY` already in `.env` the brain turns itself on. Look for
`brain ready: 37 tools` in the console. Then try, by voice:

1. "open notepad" (ACT: runs)
2. "what's my battery?" (SAFE: runs)
3. "delete test.txt from my desktop" → it asks → "yes" (DANGER)
4. "आज कति गते हो?" (answers in Nepali with today's BS date)
5. "remember that my sister's name is Asha", restart, "what's my sister's name?"

Then the live eval (stubs every tool, so nothing touches your machine):

```powershell
python evals\run_evals.py              # writes evals\RESULTS.md
python evals\run_evals.py --lang ne
```

Put the score in the README. Failing cases are your to-do list.

## Phone setup (5 minutes)

1. In Telegram, message **@BotFather** → `/newbot` → copy the token into
   `TELEGRAM_BOT_TOKEN` in `.env`.
2. `python run_daemon.py`, then message your new bot anything. It replies
   with your user ID and does nothing else.
3. Put that number in `TELEGRAM_ALLOWED_USER_IDS`, restart the daemon. You get
   "🟢 HoloDesk is online".

Now text it or send a voice note, in English or Nepali. `/status`,
`/screenshot`, `/log`, `/stop`, `/resume`, `/help` are shortcuts.

Why this is safe to leave running: the laptop only makes outbound requests,
so no port is open to the internet. Only allowlisted user IDs are obeyed, only
in a private chat. Messages older than two minutes are dropped, so nothing
fires hours later when the laptop wakes up. `/stop` works even mid-task.
Treat the bot token like a password: anyone holding it can read your messages
to the bot, though they still cannot pass the allowlist.

## Running 24/7

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1   # start at login, restart on crash
powershell -ExecutionPolicy Bypass -File scripts\power_always_on.ps1     # as Administrator: never sleep on AC
```

The daemon is headless (no camera, mic or overlay) and can run alongside the
overlay; they share one memory. It messages you when the battery is low and
unplugged, the disk is nearly full, memory stays above 95%, or a process you
asked about exits ("tell me when python finishes").

It must be a Scheduled Task in your login session, not a Windows service:
services cannot see or click your windows. A locked screen is fine for shell
and file tools, but clicking and typing need an unlocked session.

## Nepali

| Piece | How | Why |
|---|---|---|
| Wake word | local Whisper `small`, unchanged | cheap, always on, never leaves the laptop |
| The command | Groq `whisper-large-v3` | far better Nepali than a CPU can run; free tier allows about 8 hours of audio a day |
| Nepali heard as Hindi | retried once forced to `ne` | Whisper's most common Nepali mistake |
| Thinking | system prompt rules + language detection | answers in the language you used; tool arguments stay English |
| Speaking | `edge-tts` Nepali neural voice | Windows SAPI has no Nepali voice |
| Dates | `get_datetime` tool + `nepali-datetime` | models get Bikram Sambat arithmetic wrong, so they are told never to try |
| Confirming | हुन्छ / होइन / huncha / hoina | you should not have to switch language to say yes |

If you mostly speak Nepali, set `HOLODESK_STT_LANGUAGE=ne`.

## Adding a tool

```python
# brain/tools/your_file.py
def fan_on(args, ctx):
    ...                       # do the thing
    return {"ok": True, "message": "Fan is on."}

Tool(name="fan_on", description="Turn the ceiling fan on.",
     handler=fan_on, risk=Risk.ACT, keywords=("fan", "पंखा", "pankha"))
```

Register it in `brain/tools/__init__.py`. No routing code changes. Add a line
to `evals/cases.jsonl` so it is measured.

## Not verified yet

Written from documentation and experience, not run on your machine:

- **Windows-only tools**: `pywinauto` element clicking, window focus, power
  actions, PowerShell output encoding.
- **Groq specifics**: model names move. Models are auto-picked from
  `GET /models`; if the pick is poor at tool calling, pin
  `HOLODESK_CHAT_MODEL`. The free tier allows roughly 8K tokens a minute on
  the big models, about two multi-step requests; the client waits and retries
  on a 429, which you will feel as a pause.
- **Screen vision on Groq**: `look_at_screen` uses a Groq vision model when
  one is listed, else falls back to your GPT-4o ScreenAgent.
- **edge-tts voices** `ne-NP-SagarNeural` / `ne-NP-HemkalaNeural`, and mp3
  playback through `pygame.mixer` while the overlay is running.
- **Merging with your local code**: the public repo was last pushed in April.
  `app/main.py` got four small hunks (UTF-8 console, Nepali exit words,
  `transcribe_command`, neural TTS in `speak`). If your local voice loop was
  rewritten around RealtimeSTT, keep yours and call
  `speech.stt.transcribe_command(wav)` and `speech.tts.speak_neural(text)`
  from it.

Known limits, by design or for later:

- No web search tool yet. `search_in_browser` opens results for you; it does
  not read them.
- GUI automation can route around the shell policy (the model could open a
  terminal and type). The policy guards the tools, not the keyboard. The
  audit log and `/stop` are the backstop.
- The wake word is still English ("hey desk").
- Memory recall is keyword overlap, not embeddings. Good enough for hundreds
  of facts; swap in a vector store when it stops being enough.
