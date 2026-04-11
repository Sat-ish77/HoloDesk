# HoloDesk Project State

## What is HoloDesk?
A **transparent always-on-top AI overlay** for Windows. Floats above every app. Controlled by hand gestures and voice commands. Reads your screen using GPT-4o Vision. Logs your app usage silently to learn your daily patterns. Eventually gives you a personalized morning briefing before you ask for anything.

**Target:** OpenAI Codex Challenge submission. 3-week build.

---

## Current Status: Step 7 COMPLETE

| Step | Feature | Status |
|------|---------|--------|
| 0 | Pygame window + webcam display | DONE |
| 1 | Hand tracking (MediaPipe 21 landmarks) | DONE |
| 2 | Pinch to grab objects | DONE |
| 3 | Voice commands (Whisper STT + SAPI TTS) | DONE |
| 4 | AI chat (Groq API — Llama 3) | DONE |
| 5 | Desktop control (scroll, open apps, hotkeys) | DONE |
| 5.5 | Simplified UX (V-gesture single activation, toggle scroll, palm stop) | DONE |
| 6 | Transparent always-on-top overlay (win32gui color-key transparency) | DONE |
| **7** | **Screen vision (GPT-4o Vision — reads active screen on voice command)** | **DONE** |
| 8 | Morning briefing (startup analysis + Groq narration + TTS) | TODO |
| 9 | Habit detection display + proactive notifications | TODO |
| 10 | Chat panel UI (slide-in from right) | TODO |
| 11 | Polish + demo video | TODO |

---

## What Was Built in Each Step

### Step 7: Screen Vision (NEW)

**New files:**
- `connectors/openai_client.py` — GPT-4o Vision API wrapper (lazy-loads, handles missing key gracefully)
- `agents/screen_agent.py` — Screenshot + privacy blocklist + resize + base64 + vision call
- `agents/memory_agent.py` — Background 60-second app usage logger (run `start_logger.py`)
- `storage/db.py` — Thread-safe SQLite wrapper (threading.local, WAL mode)
- `storage/schema.sql` — 7 tables: users, sessions, app_events, voice_commands, habit_patterns, feedback_events, preferences
- `start_logger.py` — Standalone script to start habit data collection

**Changes to `app/main.py`:**
- `sys.path.insert` so agents/ and connectors/ are importable from app/
- `analyze_screen()` function — runs vision API on background thread, speaks result
- Screen vision voice commands: "what's on my screen", "explain this", "explain this error", "explain this code" (+ 10 Whisper spelling variations)
- Screen vision status indicator on overlay (pulsing cyan while analyzing, green when done)

**Voice commands added:**
| Command | What it does |
|---------|-------------|
| "what's on my screen" / "read my screen" / "explain this" | General screen analysis via GPT-4o |
| "explain this error" / "debug this" / "what went wrong" | Error-focused analysis |
| "explain this code" / "what does this code do" | Code-focused analysis |

---

## Architecture Decisions Made (Permanent Cuts)

These were in the original v2 spec but are **removed from the build plan**:

| Removed | Why |
|---------|-----|
| `face_recognition` / dlib | Requires cmake + Visual C++ build tools — documented install failure on Python 3.12. Adds nothing to judging criteria. |
| `sqlcipher3` | No pre-built wheel for Python 3.11/3.12 on Windows. Fails silently. Plain SQLite is fine for this submission. |
| 3D stress cube | Looks like a toy. Actively hurts the "serious productivity tool" story. Judge time is better spent on screen vision demo. |
| Google Calendar OAuth | Requires judges to complete a browser flow. Use mock data instead. |
| Face ID login | Complex install, no judging value. Removed entirely. |

---

## File Structure (Current)

```
holodesk/
├── app/
│   └── main.py                  ← Entry point (~834 lines)
├── agents/
│   ├── __init__.py
│   ├── memory_agent.py          ← Session logger + habit SQL queries
│   └── screen_agent.py          ← Screenshot + GPT-4o Vision
├── connectors/
│   ├── __init__.py
│   └── openai_client.py         ← GPT-4o Vision API wrapper
├── storage/
│   ├── __init__.py
│   ├── db.py                    ← Thread-safe SQLite wrapper
│   └── schema.sql               ← 7-table schema
├── data/                        ← gitignored — runtime DB + logs
│   └── holodesk.db              ← SQLite database (created on first run)
├── start_logger.py              ← Run this daily to collect habit data
├── .env                         ← GROQ_API_KEY + OPENAI_API_KEY (never commit)
├── .env.example                 ← Key template for new installs
├── requirement.txt
├── .gitignore
└── PROJECT_STATE.md             ← This file
```

---

## API Keys Required

| Key | Used for | Where to get |
|-----|---------|--------------|
| `GROQ_API_KEY` | Chat, morning briefing narration | console.groq.com — free |
| `OPENAI_API_KEY` | Screen vision (GPT-4o) | platform.openai.com — needs credits |

Set both in `.env`:
```
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-proj-...
```

---

## How to Run

```powershell
cd c:\Users\Dipendra\Desktop\holodesk

# Run the overlay (main app)
python app/main.py

# Run the habit data collector (run daily in background)
python start_logger.py
```

**Do NOT run via Cursor's debug button (F5)** — it goes through debugpy which throws
`ConnectionRefusedError` when the debug adapter drops. Run from terminal only.

---

## Gestures + Voice Commands (Full List)

### Gestures
| Gesture | Action |
|---------|--------|
| ✌️ V-gesture (index + middle up, ring + pinky down) | Activate voice listening (single use) |
| 👍 Thumbs up | Start scrolling UP (toggle — stays on) |
| 👎 Thumbs down | Start scrolling DOWN (toggle — stays on) |
| ✋ Open palm | STOP scrolling + STOP AI speech |
| 🤏 Pinch | Grab and drag the card |

### Voice Commands
| Command | What it does |
|---------|-------------|
| "what's on my screen" / "explain this" / "read my screen" | GPT-4o reads + explains current screen |
| "explain this error" / "debug this" | Error-focused screen analysis |
| "explain this code" / "what does this code do" | Code-focused screen analysis |
| "scroll up/down" | Scroll active window |
| "open [app]" | Launch app (chrome, notepad, spotify, etc.) |
| "open youtube/netflix/facebook" | Open in Chrome |
| "close window" / "minimize" | Window control |
| "color [red/blue/green/...]" | Change card color |
| "reset" | Move card to center |
| "stop" | Stop scrolling |
| "hello" / "bye" / "thanks" | Greetings |
| anything else | Sent to Groq AI for response |

---

## Known Issues

| Issue | Status |
|-------|--------|
| Whisper mishears words | Handled — added spelling variations (e.g. "screw" = "scroll") |
| Emoji in console (✅, ⚠️) | Replaced with `[OK]` / `[WARNING]` — Windows console limitation |
| Cursor debug button crashes | Use terminal (`python app/main.py`) instead |
| Screen vision requires OpenAI key | Add `OPENAI_API_KEY` to `.env` — falls back gracefully if missing |
| TTS pyttsx3 buggy | Using Windows SAPI via comtypes — much more reliable |

---

## Dependencies (requirement.txt)

```
pygame==2.5.2       # overlay window
opencv-python       # webcam
mediapipe           # hand tracking
numpy==1.26.4       # math
SpeechRecognition   # mic capture
faster-whisper      # local STT
pyaudio             # mic access
comtypes            # Windows TTS (SAPI)
pyttsx3             # TTS fallback
groq                # Groq API (Llama 3)
openai              # GPT-4o Vision (Step 7)
pyautogui           # scroll, hotkeys, screenshot
Pillow              # image resize before API
psutil              # process names for memory logger
pywin32             # win32gui transparency + window control
python-dotenv       # .env loader
```

**NOT in requirements (cut deliberately):**
- `face_recognition` — dlib install breaks on Python 3.12 / Windows
- `sqlcipher3` — no Windows wheel for Python 3.11+
- `google-api-python-client` — Calendar OAuth too complex for judges to set up

---

## Next Steps (Priority Order)

1. **Morning briefing** — `agents/chat_agent.py` + `app/startup.py`
   Run memory analysis + Groq narration on startup. Speak a personalized briefing.
   Requires `start_logger.py` to have been running for several days.

2. **Habit data** — keep `start_logger.py` running daily. Need 7-14 days for patterns.

3. **Demo mode** — `--demo` flag loads pre-scripted 14-day dataset so morning briefing
   works on a fresh install for judges.

4. **Demo video script** — 60 seconds: morning briefing → screen vision → voice chat.

---

## For New Chat Session

Say:
> "Read PROJECT_STATE.md and help me continue building HoloDesk. Step 7 (screen vision) is complete. Next is the morning briefing system."

---

**Last Updated:** Step 7 complete — Screen Vision (GPT-4o) + Memory Logger
**Total lines of code:** ~834 (main.py) + 140 (db.py) + 172 (screen_agent.py) + 220 (memory_agent.py) + 102 (openai_client.py) ≈ 1,500 lines
**Author:** Satish Wagle
**GitHub:** https://github.com/Sat-ish77/HoloDesk
