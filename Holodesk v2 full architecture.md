# HoloDesk v2 — Full Production Architecture
### Ambient Multi-Agent Desktop Co-pilot
**Document Type:** Complete Technical Specification  
**Authors:** Sat + Friend  
**Timeline:** 3 Weeks to Working Product  
**Challenge:** Codex Challenge ($100 API Credit)

---

# TABLE OF CONTENTS

1. What We Are Building
2. Why This Is Different
3. Full System Architecture
4. Threading Model — The Foundation
5. Agent System — Every Agent Explained
6. Data Architecture — Memory & Privacy
7. API Strategy — Which AI for What
8. UI Architecture
9. Security & Privacy — Technical Guarantees
10. Improvement Tracking — How HoloDesk Gets Better
11. Background Processing — What's Real
12. Production Checklist — Every Step
13. Folder Structure
14. 3-Week Sprint Plan
15. Division of Work
16. Tech Stack Reference

---

# 1. What We Are Building

HoloDesk v2 is a **transparent always-on overlay** that floats above every application on a Windows PC. It is not a chatbot you open. It is not a voice assistant you talk at. It is an **ambient AI layer** — it sits silently, watches what you do (with strict privacy controls), learns your patterns, and helps you before you even ask.

Think of it as a **personal AI chief of staff** that lives inside your computer.

### The core experience:

**Morning:** You open your laptop. Before you click anything, a friendly voice says:
> *"Hey Sat. You've got a 2pm sync with David. You left a bug open in main.py last night. Your assignment is due Friday. Want me to pull up the file?"*

You say "yeah" and it opens the file, extracts the bug, sends it to Claude, and reads back the fix — while you pour your coffee.

**During the day:** You're reading a confusing error message. You raise your hand briefly (V-gesture) and say "explain this." HoloDesk takes a screenshot, sends it to GPT-4o Vision, and speaks the explanation in plain English. You never switched windows.

**At night:** You're done working. HoloDesk has quietly logged which apps you used, what time, what you were working on. Over 2 weeks, it knows your rhythm better than any tool you've used.

### What makes this genuinely novel:

Every existing AI tool (Claude, Gemini, Copilot, ChatGPT) requires you to:
1. Stop what you're doing
2. Switch to a different app
3. Type or speak a prompt
4. Wait for a response
5. Go back to what you were doing

**HoloDesk eliminates all five steps.** That is the product.

---

# 2. Why This Is Different

| Tool | What it does | What it can't do |
|---|---|---|
| Claude / ChatGPT | Answers questions | Knows nothing about your workflow |
| Gemini | Google integration | Requires you to open it |
| GitHub Copilot | Code completion | Only works in editors |
| Windows Copilot | OS-level assistant | Requires you to click it |
| **HoloDesk v2** | **Lives above everything, learns you, acts first** | — |

The gap is **ambient + proactive + personalized.** Nobody has this at the desktop OS layer for regular users. That is the window.

---

# 3. Full System Architecture

## 3.1 Bird's Eye View

```
+==================================================================+
|                        USER'S WINDOWS PC                         |
|                                                                   |
|  +------------------------------------------------------------+  |
|  |              HOLODESK OVERLAY (Pygame)                     |  |
|  |                                                            |  |
|  |  [Face ID]  [Status Bar]  [Chat Panel]  [3D Objects]      |  |
|  |  [Morning Card]  [Notification Cards]  [Gesture Cursor]   |  |
|  +------------------------+-----------------------------------+  |
|                           |  Events / Render commands            |
|  +------------------------v-----------------------------------+  |
|  |                 ORCHESTRATOR AGENT                         |  |
|  |           (Central Brain -- always running)                |  |
|  |                                                            |  |
|  |  Input router -> Task planner -> Agent dispatcher          |  |
|  |  Parallel task manager -> Response aggregator             |  |
|  +---+------+------+------+------+------+------+------------+  |
|      |      |      |      |      |      |      |               |
|  +---v-+ +--v-+ +--v-+ +--v-+ +--v-+ +--v-+ +--v--+         |
|  |SCRN | |MEM | |CAL | |VOI | |TSK | |CHT | |NTFY |         |
|  |AGNT | |AGT | |AGT | |AGT | |AGT | |AGT | |AGT  |         |
|  +---+-+ +--+-+ +--+-+ +--+-+ +--+-+ +--+-+ +--+--+         |
|      |      |      |      |      |      |      |               |
|  +---v------v------v------v------v------v------v-----------+  |
|  |                  LOCAL SQLITE DATABASE                    |  |
|  |     (AES-256 encrypted, never leaves device)             |  |
|  +-----------------------------------------------------------+  |
|                                                                   |
|  +-----------------------------------------------------------+  |
|  |              EXTERNAL API CONNECTORS                      |  |
|  |  Groq API   GPT-4o Vision   Claude API   Gemini Flash    |  |
|  |  Google Calendar API  (called only on explicit trigger)   |  |
|  +-----------------------------------------------------------+  |
+===================================================================+
```

## 3.2 Data Flow Principles

Three rules that govern every data flow in the system:

**Rule 1 — Nothing blocks the UI thread.**
The Pygame render loop runs at exactly 30fps. Any operation over 33ms must happen on a background thread. AI calls, screenshot capture, DB writes — all background.

**Rule 2 — Agents communicate via queues, not direct calls.**
No agent calls another agent directly. They put tasks into a shared queue. The Orchestrator reads from queues and dispatches. This prevents deadlocks and makes the system debuggable.

**Rule 3 — Every external API call is optional.**
If Groq is down, fall back to Gemini. If GPT-4o Vision is unavailable, tell the user and skip. The app never crashes because an API is unreachable.

---

# 4. Threading Model — The Foundation

This is the most important section. Get threading wrong and everything else fails. Implement this first in Week 1 before any feature work.

## 4.1 Why Threading Matters Here

Python's GIL means true parallelism is not possible for CPU-bound tasks. But HoloDesk's tasks are mostly I/O-bound (waiting for API responses, waiting for camera frames) — which means Python threading works perfectly here.

While one thread waits for a Groq API response (1-2 seconds), other threads keep running. The UI never freezes.

## 4.2 Thread Architecture

```
MAIN THREAD (Pygame UI)
  -> render_loop() — 30fps, reads from output queues, draws everything

THREAD 2 (Camera)
  -> camera_loop() — captures frames at 30fps, puts in frame_queue

THREAD 3 (Vision/Gesture)
  -> vision_loop() — reads frame_queue, runs MediaPipe, puts landmarks
                     in landmark_queue, runs gesture detection

THREAD 4 (Audio Input)
  -> audio_loop() — always listening for wake word (tiny model)
                    on wake: records command, puts in command_queue

THREAD 5 (Orchestrator)
  -> orchestrator_loop() — reads command_queue and gesture_queue
                           dispatches tasks to agent thread pool

THREAD POOL (Agent Workers — up to 5 concurrent)
  -> agent_worker() — picks up tasks from task_queue
                      runs agent logic (may call APIs)
                      puts result in response_queue

THREAD 6 (Memory Logger)
  -> memory_loop() — every 60s, logs active window to SQLite
                     low priority, never blocks anything
```

## 4.3 Queue Architecture

```python
# core/queues.py — shared across all modules
import queue

# Camera frames (maxsize=1 means always latest frame, old ones discarded)
frame_queue = queue.Queue(maxsize=1)

# MediaPipe landmarks (latest only)
landmark_queue = queue.Queue(maxsize=1)

# Detected gestures (keep last 5)
gesture_queue = queue.Queue(maxsize=5)

# Voice commands ready for processing
command_queue = queue.Queue(maxsize=10)

# Tasks dispatched to agent workers
task_queue = queue.Queue(maxsize=20)

# Completed responses ready to display/speak
response_queue = queue.Queue(maxsize=10)

# UI render commands (what to show on overlay)
render_queue = queue.Queue(maxsize=20)
```

## 4.4 Camera Thread — Production Implementation

```python
# core/camera_thread.py
import cv2
import threading
import queue
from core.queues import frame_queue

class CameraThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)  # daemon=True: dies when main thread dies
        self.running = False
        self.cap = None

    def run(self):
        self.running = True
        # Try multiple camera indices in case built-in is not index 0
        for idx in [0, 1, 2]:
            self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # CAP_DSHOW faster on Windows
            if self.cap.isOpened():
                break

        if not self.cap.isOpened():
            return  # No camera — gesture features disabled gracefully

        # Set capture properties for performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer lag

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)  # Mirror for natural interaction

            # Non-blocking put: if queue is full, discard old frame
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    frame_queue.get_nowait()
                    frame_queue.put_nowait(frame)
                except:
                    pass

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
```

## 4.5 Gesture Detector — The Debounce Fix

This kills phantom triggers. Simple but critical.

```python
# vision/gesture_detector.py

class GestureDetector:
    # Gesture must be held for this many consecutive frames to fire
    REQUIRED_FRAMES = 8

    # Hand must be in top 40% of camera frame to be "intentional"
    # Eliminates casual hand movements when typing/eating/etc
    INTENT_ZONE_Y = 0.4

    # Cooldown after gesture fires (prevents rapid re-triggering)
    COOLDOWN_FRAMES = 15

    def __init__(self):
        self.last_gesture = None
        self.frame_count = 0
        self.cooldown = 0

    def detect(self, landmarks, frame_height):
        if self.cooldown > 0:
            self.cooldown -= 1
            return None

        # Check intent zone: wrist (landmark 0) must be in top 40% of frame
        wrist_y = landmarks.landmark[0].y  # Normalized 0.0=top, 1.0=bottom
        if wrist_y > self.INTENT_ZONE_Y:
            self._reset()
            return None

        gesture = self._classify(landmarks)

        if gesture == self.last_gesture and gesture is not None:
            self.frame_count += 1
        else:
            self.frame_count = 1
            self.last_gesture = gesture

        if self.frame_count >= self.REQUIRED_FRAMES:
            self._reset()
            self.cooldown = self.COOLDOWN_FRAMES
            return gesture

        return None

    def _reset(self):
        self.last_gesture = None
        self.frame_count = 0

    def _classify(self, landmarks):
        lm = landmarks.landmark

        # V-gesture: index + middle up, ring + pinky down
        if (self._finger_up(lm, 8, 6) and
            self._finger_up(lm, 12, 10) and
            not self._finger_up(lm, 16, 14) and
            not self._finger_up(lm, 20, 18)):
            return "V_GESTURE"

        # Open palm: all fingers up
        if (self._finger_up(lm, 8, 6) and
            self._finger_up(lm, 12, 10) and
            self._finger_up(lm, 16, 14) and
            self._finger_up(lm, 20, 18)):
            return "OPEN_PALM"

        return None

    def _finger_up(self, lm, tip_idx, pip_idx):
        # Tip above PIP joint = finger is up (y inverted in normalized coords)
        return lm[tip_idx].y < lm[pip_idx].y
```

## 4.6 Main Render Loop — Never Blocks

```python
# app/main.py
import pygame
import queue
from core.queues import gesture_queue, response_queue

def main():
    # Start all background threads first
    camera_thread = CameraThread()
    vision_thread = VisionThread()
    audio_thread = AudioThread()
    orchestrator_thread = OrchestratorThread()
    memory_logger_thread = MemoryLoggerThread()

    for t in [camera_thread, vision_thread, audio_thread,
              orchestrator_thread, memory_logger_thread]:
        t.start()

    overlay = Overlay()
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # NON-BLOCKING reads from queues — never wait, never block
        try:
            gesture = gesture_queue.get_nowait()
            overlay.handle_gesture(gesture)
        except queue.Empty:
            pass

        try:
            response = response_queue.get_nowait()
            overlay.handle_response(response)
        except queue.Empty:
            pass

        # Render always happens regardless of agent activity
        overlay.render()
        pygame.display.flip()

        clock.tick(30)  # Lock to 30fps
```

---

# 5. Agent System — Every Agent Explained

## 5.1 OrchestratorAgent — The Brain

The Orchestrator never does work itself. It reads inputs, decides what needs to happen, and dispatches to the right agents — sometimes in parallel.

```python
# agents/orchestrator.py
import re
from concurrent.futures import ThreadPoolExecutor

class OrchestratorAgent:

    ROUTING_RULES = {
        r"screen|error|what.*screen|explain.*this|read.*screen": ["screen_agent"],
        r"calendar|schedule|today|tomorrow|meeting|deadline": ["calendar_agent"],
        r"open|launch|close|scroll|click": ["task_agent"],
        r"remember|habit|last time|yesterday|history": ["memory_agent"],
        r"remind|notification|alert": ["notify_agent"],
    }

    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        self.agents = {}  # Populated at startup

    def route(self, input_text: str) -> list:
        matched = []
        for pattern, agents in self.ROUTING_RULES.items():
            if re.search(pattern, input_text.lower()):
                matched.extend(agents)
        return list(set(matched)) if matched else ["chat_agent"]

    def dispatch(self, agents: list, context: dict):
        if len(agents) == 1:
            # Single agent — direct
            result = self.agents[agents[0]].execute(context)
            self.response_queue.put(result)
        else:
            # Multiple agents — parallel
            futures = {
                name: self.thread_pool.submit(
                    self.agents[name].execute, context
                )
                for name in agents
            }
            results = {name: f.result(timeout=30) for name, f in futures.items()}
            merged = self._merge(results)
            self.response_queue.put(merged)

    def _merge(self, results: dict) -> dict:
        responses = [r["response"] for r in results.values() if r.get("success")]
        return {
            "success": True,
            "response": " | ".join(responses)
        }
```

**Why parallel dispatch matters:**
User says "check my calendar and explain what's on my screen." Without parallel: 0.3s (calendar) + 2s (GPT-4o) = 2.3s total. With parallel: max(0.3, 2) = 2s total. Saves time and feels faster on every multi-agent request.

---

## 5.2 ScreenAgent — Eyes on Your Desktop

```python
# agents/screen_agent.py
import pyautogui
import base64
import io
import win32gui
from PIL import Image
from connectors.openai_client import OpenAIClient

class ScreenAgent:

    BLOCKED_KEYWORDS = [
        "1password", "lastpass", "bitwarden",
        "banking", "chase ", "wells fargo",
        "private -", "incognito",
        "social security", "tax return"
    ]

    TARGET_WIDTH = 1280  # Resize before API call — saves cost, still readable

    def __init__(self):
        self.client = OpenAIClient()
        self.enabled = True

    def get_active_window_title(self) -> str:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd).lower()

    def is_blocked(self) -> bool:
        title = self.get_active_window_title()
        return any(kw in title for kw in self.BLOCKED_KEYWORDS)

    def capture(self):
        if not self.enabled or self.is_blocked():
            return None

        screenshot = pyautogui.screenshot()
        ratio = self.TARGET_WIDTH / screenshot.width
        new_h = int(screenshot.height * ratio)
        return screenshot.resize((self.TARGET_WIDTH, new_h), Image.LANCZOS)

    def execute(self, context: dict) -> dict:
        question = context.get("question", "What is on this screen?")
        image = self.capture()

        if image is None:
            return {
                "success": False,
                "response": "I cannot see that window — it may be a protected app.",
                "agent": "screen_agent"
            }

        # Encode to base64 for API
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        response = self.client.vision_query(
            image_b64=b64,
            question=question,
            system="""You are HoloDesk, an ambient desktop assistant.
            Answer in 2-3 sentences maximum. Be direct and specific.
            For errors: explain cause and fix.
            For documents: state the key point.
            For code: explain what it does."""
        )

        return {"success": True, "response": response, "agent": "screen_agent"}
```

**Cost math:** GPT-4o Vision at 1280x720 = ~$0.002 per call. $100 credit = ~50,000 screen reads. Only triggered manually. No surprise bills.

---

## 5.3 MemoryAgent — The Learning System

The intelligence of HoloDesk. Not ML. Just SQL + frequency analysis + LLM for narration.

```python
# agents/memory_agent.py
from datetime import datetime
import win32gui, win32process, psutil
from storage.db import db

class MemoryAgent:

    def log_app_event(self):
        """Called every 60 seconds from background thread."""
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)

        if self._is_blocked(title):
            return  # Never log protected windows

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            app_name = psutil.Process(pid).name()
        except:
            app_name = "unknown"

        db.insert("app_events", {
            "session_id": self.session_id,
            "app_name": app_name,
            "window_title": title[:200],
            "timestamp": datetime.now().isoformat(),
            "day_of_week": datetime.now().weekday(),
            "hour_of_day": datetime.now().hour
        })

    def detect_habits(self) -> list:
        """Find apps opened consistently at the same time. Pure SQL."""
        return db.query("""
            SELECT
                app_name,
                hour_of_day,
                day_of_week,
                COUNT(*) as frequency
            FROM app_events
            WHERE timestamp > datetime('now', '-14 days')
            GROUP BY app_name, hour_of_day, day_of_week
            HAVING frequency >= 5
            ORDER BY frequency DESC
            LIMIT 20
        """)

    def get_unfinished_context(self) -> list:
        """What was the user working on at end of last session?"""
        return db.query("""
            SELECT app_name, window_title, timestamp
            FROM app_events
            WHERE session_id = (
                SELECT id FROM sessions
                ORDER BY start_time DESC
                LIMIT 1 OFFSET 1
            )
            ORDER BY timestamp DESC
            LIMIT 5
        """)

    def generate_morning_context(self) -> dict:
        return {
            "habits": self.detect_habits(),
            "unfinished_work": self.get_unfinished_context(),
            "days_active": db.query(
                "SELECT COUNT(DISTINCT date(start_time)) as days FROM sessions"
            )[0]["days"]
        }
```

**Cold start handling — what to show on Day 1 vs Day 14:**

```
Day 1-3:   HoloDesk is reactive only. Answers questions, reads screen.
           Shows: "HoloDesk is learning your routine. Day 1 of 14."

Day 4-7:   First patterns. Simple suggestions based on frequency.
           "You usually open VS Code around this time."

Day 7-14:  Full habit awareness. Proactive briefings personalized.
           "You've been debugging Study Helper every evening this week."

Day 14+:   Confident habit model. High-value proactive suggestions only.
```

---

## 5.4 CalendarAgent — Schedule Awareness

```python
# agents/calendar_agent.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime

class CalendarAgent:
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    def authenticate(self):
        """OAuth2 flow — runs once, stores token locally forever."""
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', self.SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open('data/calendar_token.json', 'w') as f:
            f.write(creds.to_json())
        return creds

    def get_todays_events(self) -> list:
        service = build('calendar', 'v3', credentials=self.creds)
        now = datetime.utcnow().isoformat() + 'Z'
        end = datetime.utcnow().replace(hour=23, minute=59).isoformat() + 'Z'

        result = service.events().list(
            calendarId='primary',
            timeMin=now,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return [{
            "title": e.get('summary', 'Untitled'),
            "start": e['start'].get('dateTime', e['start'].get('date')),
            "description": e.get('description', '')[:200]
        } for e in result.get('items', [])]

    def execute(self, context: dict) -> dict:
        events = self.get_todays_events()
        return {"success": True, "events": events, "agent": "calendar_agent"}
```

**One-time Google Calendar setup (15 minutes):**
1. Go to console.cloud.google.com
2. Create project → Enable Google Calendar API
3. Create OAuth2 credentials → Download credentials.json → place in project root
4. First run opens browser for user to authorize
5. Token saved locally — auto-refreshes forever after

---

## 5.5 VoiceAgent — Speech In and Out

```python
# agents/voice_agent.py
from faster_whisper import WhisperModel
import pyaudio
import numpy as np
import win32com.client
import threading

class VoiceAgent:
    WAKE_WORD = "hey desk"
    WAKE_ENERGY_THRESHOLD = 3000  # Tune this for your environment
    SILENCE_DURATION = 1.5        # Seconds of silence = end of command

    def __init__(self):
        # Loads once at startup (~2 seconds), then cached in memory
        self.model = WhisperModel("base", device="cpu", compute_type="int8")
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.speaking = False

    def listen_for_wake_word(self) -> bool:
        """Energy-based detection. Cheap, no API needed."""
        audio = self._record_chunk(duration=1.0)
        energy = np.abs(audio).mean()
        if energy < self.WAKE_ENERGY_THRESHOLD:
            return False
        transcript = self._transcribe(audio)
        return self.WAKE_WORD in transcript.lower()

    def listen_for_command(self) -> str:
        audio = self._record_until_silence(max_duration=10)
        return self._transcribe(audio)

    def _transcribe(self, audio_data) -> str:
        segments, _ = self.model.transcribe(audio_data, beam_size=5)
        return " ".join([s.text for s in segments]).strip()

    def speak(self, text: str):
        """Non-blocking TTS — UI never freezes."""
        def _speak():
            self.speaking = True
            self.speaker.Speak(text, 1)  # 1 = async
            self.speaking = False
        threading.Thread(target=_speak, daemon=True).start()

    def stop_speaking(self):
        """Called on OPEN_PALM gesture."""
        self.speaker.Pause()
        self.speaking = False
```

**Why Whisper local matters:** Zero API cost. Works offline. No data leaves the device for voice. Whisper "base" model is 74MB and handles English commands extremely well.

---

## 5.6 TaskAgent — Does Things For You

```python
# agents/task_agent.py
import subprocess
import pyautogui
import pyperclip
from connectors.claude_client import ClaudeClient

class TaskAgent:

    BLOCKED_ACTIONS = ["delete", "format", "rm ", "shutdown", "regedit"]

    APP_MAP = {
        "chrome": "start chrome",
        "firefox": "start firefox",
        "notepad": "start notepad",
        "vscode": "code .",
        "spotify": "start spotify",
        "terminal": "start cmd",
        "youtube": "start chrome https://youtube.com",
        "netflix": "start chrome https://netflix.com",
    }

    def execute(self, context: dict) -> dict:
        action = context.get("action", "").lower()

        if any(b in action for b in self.BLOCKED_ACTIONS):
            return {"success": False, "response": "I cannot do that."}

        if "open" in action or "launch" in action:
            return self._open_app(action)
        elif "scroll up" in action:
            pyautogui.scroll(5)
            return {"success": True, "response": ""}
        elif "scroll down" in action:
            pyautogui.scroll(-5)
            return {"success": True, "response": ""}
        elif "ask claude" in action or "send to claude" in action:
            return self._delegate_to_claude(context)
        elif "type" in action or "paste" in action:
            pyperclip.copy(context.get("text", ""))
            pyautogui.hotkey('ctrl', 'v')
            return {"success": True, "response": "Done."}

        return {"success": False, "response": "I don't know how to do that yet."}

    def _open_app(self, action: str) -> dict:
        for app, cmd in self.APP_MAP.items():
            if app in action:
                subprocess.Popen(cmd, shell=True)
                return {"success": True, "response": f"Opening {app}."}
        return {"success": False, "response": "I don't recognize that app."}

    def _delegate_to_claude(self, context: dict) -> dict:
        """Send work to Claude, paste result back."""
        client = ClaudeClient()
        result = client.complete(prompt=context.get("prompt", ""))
        pyperclip.copy(result)
        return {"success": True, "response": "Done. Result copied to clipboard."}
```

---

## 5.7 ChatAgent — Conversation Handler

```python
# agents/chat_agent.py
from connectors.groq_client import GroqClient

class ChatAgent:
    MAX_HISTORY = 10

    def __init__(self):
        self.client = GroqClient()
        self.history = []

    def execute(self, context: dict) -> dict:
        message = context.get("message", "")
        system = self._build_system(context)

        self.history.append({"role": "user", "content": message})
        if len(self.history) > self.MAX_HISTORY * 2:
            self.history = self.history[-(self.MAX_HISTORY * 2):]

        response = self.client.complete(
            messages=self.history,
            system=system
        )
        self.history.append({"role": "assistant", "content": response})

        return {"success": True, "response": response, "agent": "chat_agent"}

    def _build_system(self, context: dict) -> str:
        habits = context.get("habits_summary", "Not yet detected")
        calendar = context.get("calendar_summary", "No events today")
        screen = context.get("screen_context", "")

        return f"""You are HoloDesk, an ambient AI layer on the user's desktop.
        User habits: {habits}
        Today's schedule: {calendar}
        Current screen: {screen}
        
        Be concise. Max 3 sentences. Never say "As an AI language model".
        You can take actions — if you can do something, say so and do it."""

    def clear_history(self):
        self.history = []
```

---

# 6. Data Architecture — Memory & Privacy

## 6.1 SQLite Schema

```sql
-- storage/schema.sql

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    face_encoding_path TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    start_time TEXT NOT NULL,
    end_time TEXT,
    total_duration_minutes INTEGER
);

CREATE TABLE IF NOT EXISTS app_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    app_name TEXT NOT NULL,
    window_title TEXT,
    timestamp TEXT NOT NULL,
    day_of_week INTEGER,
    hour_of_day INTEGER
);

CREATE TABLE IF NOT EXISTS voice_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    command_text TEXT NOT NULL,
    response_summary TEXT,
    agent_used TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS habit_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    pattern_type TEXT,
    pattern_data TEXT,
    confidence_score REAL,
    last_computed TEXT,
    times_confirmed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    trigger_type TEXT,
    agent_used TEXT,
    user_accepted INTEGER,
    user_dismissed INTEGER,
    response_latency_ms INTEGER,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for fast habit queries
CREATE INDEX IF NOT EXISTS idx_app_events_time
    ON app_events(app_name, hour_of_day, day_of_week);
CREATE INDEX IF NOT EXISTS idx_feedback_agent
    ON feedback_events(agent_used, user_accepted);
```

## 6.2 Thread-Safe Database Wrapper

```python
# storage/db.py
import sqlite3
import threading
from pathlib import Path

class Database:
    def __init__(self, db_path: str = "data/holodesk.db"):
        self.db_path = db_path
        self._local = threading.local()
        Path("data").mkdir(exist_ok=True)
        self._init_schema()

    @property
    def conn(self):
        """Each thread gets its own connection — eliminates threading conflicts."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent writes
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def insert(self, table: str, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        cursor = self.conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        self.conn.commit()
        return cursor.lastrowid

    def query(self, sql: str, params: tuple = ()) -> list:
        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def _init_schema(self):
        with open("storage/schema.sql") as f:
            self.conn.executescript(f.read())
        self.conn.commit()

db = Database()  # Global singleton
```

---

# 7. API Strategy — Which AI for What

## 7.1 Routing Decision Matrix

```
Task                                    API            Reason
----------------------------------------------------------------------
Morning briefing narration              Groq           Sub-second speed
General conversation                    Groq           Speed + free tier
Complex reasoning (architecture, etc)  Claude         Best reasoning quality
Screen content analysis                 GPT-4o Vision  Best vision model
Code explanation / debugging            Claude         Best for code tasks
Calendar summary narration              Groq           Simple, fast
Habit pattern narration                 Groq           Simple, fast
Groq unavailable                        Gemini Flash   Fallback
Long document > 32K tokens              Gemini Flash   1M context window
```

## 7.2 LLM Router With Automatic Fallback

```python
# connectors/llm_router.py

class LLMRouter:
    def __init__(self):
        self.groq = GroqClient()
        self.claude = ClaudeClient()
        self.openai = OpenAIClient()
        self.gemini = GeminiClient()

    def complete(self, prompt: str, task_type: str = "chat") -> str:
        primary, fallback = self._get_providers(task_type)

        try:
            return primary.complete(prompt)
        except Exception as e:
            print(f"Primary LLM failed: {e}")
            if fallback:
                try:
                    return fallback.complete(prompt)
                except Exception as e2:
                    print(f"Fallback failed: {e2}")
            return "I'm having trouble connecting. Please try again."

    def _get_providers(self, task_type: str):
        return {
            "chat":      (self.groq, self.gemini),
            "reasoning": (self.claude, self.groq),
            "vision":    (self.openai, None),
            "fast":      (self.groq, self.gemini),
        }.get(task_type, (self.groq, self.gemini))
```

## 7.3 Groq Client

```python
# connectors/groq_client.py
from groq import Groq
import os

class GroqClient:
    MODEL = "llama-3.3-70b-versatile"

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def complete(self, messages: list = None, prompt: str = None,
                 system: str = None, max_tokens: int = 500) -> str:

        if prompt and not messages:
            messages = [{"role": "user", "content": prompt}]

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=all_messages,
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content
```

---

# 8. UI Architecture

## 8.1 Overlay Layer Stack

```
Layer 5 (Top):   Notification cards, morning briefing card
Layer 4:         Chatbot panel (slides in from right)
Layer 3:         3D stress objects (interactive)
Layer 2:         Status bar, agent activity indicator, gesture cursor
Layer 1 (Base):  Transparent window background
```

## 8.2 Chatbot Panel Layout

```
+-----------------------------------+
|  HoloDesk Chat           [x] [-]  |
+-----------------------------------+
|                                   |
|  [You]: What's on my screen?     |
|                                   |
|  [HoloDesk]: You have VS Code    |
|  open with main.py. There is a   |
|  TypeError on line 42...          |
|                                   |
|  [You]: Fix it                    |
|                                   |
|  [HoloDesk]: Fixed. Copied to    |
|  clipboard.                       |
|                                   |
+-----------------------------------+
|  [Type here...]         [Send]    |
|  [Mic Voice]            [Clear]   |
+-----------------------------------+
```

Behavior:
- Default: minimized icon in overlay corner
- Trigger: "open chat" voice command OR click icon
- Slide animation: 300ms ease-out from right edge
- Both text and voice work inside the panel
- Conversation persists for the session
- Clear resets to fresh conversation

## 8.3 3D Stress Object — Pure Math, No Game Engine

```python
# ui/stress_objects.py
import numpy as np
import pygame

class StressObject3D:
    def __init__(self):
        self.rotation = np.array([0.0, 0.0, 0.0])
        self.position = np.array([400.0, 300.0])
        self.scale = 1.0
        self.velocity = np.array([0.0, 0.0])
        self.angular_velocity = np.array([0.0, 0.02, 0.01])  # Idle spin
        self.vertices, self.edges = self._build_cube()

    def _build_cube(self):
        v = np.array([
            [-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
            [-1,-1, 1],[1,-1, 1],[1,1, 1],[-1,1, 1]
        ], dtype=float)
        e = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
             (0,4),(1,5),(2,6),(3,7)]
        return v, e

    def update(self, hand_landmarks=None):
        if hand_landmarks:
            wrist = hand_landmarks.landmark[0]
            self.rotation[1] = (wrist.x - 0.5) * 4  # Wrist X -> Y rotation
            self.rotation[0] = (wrist.y - 0.5) * 4  # Wrist Y -> X rotation
        else:
            self.rotation += self.angular_velocity  # Idle spin

        # Physics
        self.position += self.velocity
        self.velocity *= 0.95  # Damping

        # Bounce off edges
        if not (50 < self.position[0] < 750):
            self.velocity[0] *= -0.8
        if not (50 < self.position[1] < 550):
            self.velocity[1] *= -0.8

    def project(self, v):
        x, y, z = v * self.scale * 60
        rx, ry = self.rotation[0], self.rotation[1]

        # Y rotation
        x, z = x * np.cos(ry) - z * np.sin(ry), x * np.sin(ry) + z * np.cos(ry)
        # X rotation
        y, z = y * np.cos(rx) - z * np.sin(rx), y * np.sin(rx) + z * np.cos(rx)

        # Perspective
        fov = 300
        px = x * fov / (z + 5) + self.position[0]
        py = y * fov / (z + 5) + self.position[1]
        return px, py

    def render(self, surface):
        projected = [self.project(v) for v in self.vertices]
        for e in self.edges:
            pygame.draw.line(surface, (100, 200, 255), projected[e[0]], projected[e[1]], 2)
```

---

# 9. Security & Privacy — Technical Guarantees

## 9.1 What Leaves the Device

```
NEVER leaves the device:
  - Face encodings (local .pkl files, never uploaded)
  - App usage patterns and habit data
  - Window titles and session logs
  - Voice recordings (Whisper is 100% local)
  - All passive observation data

Leaves ONLY on explicit user trigger:
  - Screenshot -> GPT-4o Vision API
    (user is notified every single time this happens)
  - Chat message -> Groq / Claude / Gemini API
    (user initiated every time)
  - Calendar: READ only from Google Calendar API
    (nothing written, nothing stored in cloud)
```

## 9.2 Privacy Dashboard

Always visible in overlay. User controls everything:

```
+--------------------------------------+
|  Privacy Dashboard                   |
+--------------------------------------+
|  Screen reading:      [ON]  [OFF]    |
|  App usage logging:   [ON]  [OFF]    |
|  Voice logging:       [ON]  [OFF]    |
|  Calendar access:     [ON]  [OFF]    |
|                                      |
|  Data stored: 4.2 MB  [Delete All]  |
|  Sessions logged: 12                 |
|  Habits detected: 3                  |
|                                      |
|  Note: When screen is read, content  |
|  is sent to OpenAI's servers.        |
|  All other data stays on this device.|
+--------------------------------------+
```

## 9.3 Encrypted SQLite (Production)

```python
# storage/encrypted_db.py
import sqlcipher3  # pip install sqlcipher3

class EncryptedDatabase:
    def __init__(self, db_path: str, password: str):
        self.conn = sqlcipher3.connect(db_path)
        self.conn.execute(f"PRAGMA key='{password}'")
        self.conn.execute("PRAGMA cipher_page_size=4096")
        self.conn.execute("PRAGMA kdf_iter=256000")
        self.conn.execute("SELECT count(*) FROM sqlite_master")  # Verify
```

Password = user's PIN set at first launch. Zero access for anyone else including you as the developer.

---

# 10. Improvement Tracking — How HoloDesk Gets Better

No MLflow. No model training. Two simple mechanisms:

**Mechanism 1 — Data accumulation.**
More sessions = more accurate habit patterns. Confidence scores increase over 14 days.

**Mechanism 2 — Dismissal rate tuning.**

```python
# agents/improvement_tracker.py

class ImprovementTracker:
    THRESHOLD = 0.7  # Initial confidence required to surface suggestion

    def should_suggest(self, pattern_type: str) -> bool:
        rate_data = db.query("""
            SELECT AVG(CAST(user_accepted AS FLOAT)) as rate, COUNT(*) as total
            FROM feedback_events
            WHERE trigger_type = 'proactive' AND agent_used = ?
            AND timestamp > datetime('now', '-7 days')
        """, (pattern_type,))

        if not rate_data or rate_data[0]['total'] < 5:
            return True  # Not enough data, show freely

        rate = rate_data[0]['rate']

        # Ignored more than 50% -> raise threshold (show less)
        if rate < 0.5:
            self.THRESHOLD = min(0.9, self.THRESHOLD + 0.05)
        # Accepted more than 80% -> lower threshold (show more)
        elif rate > 0.8:
            self.THRESHOLD = max(0.5, self.THRESHOLD - 0.05)

        return rate >= self.THRESHOLD

    def weekly_report(self) -> list:
        return db.query("""
            SELECT agent_used,
                   COUNT(*) as total,
                   AVG(CAST(user_accepted AS FLOAT)) as acceptance_rate,
                   AVG(response_latency_ms) as avg_latency_ms
            FROM feedback_events
            WHERE timestamp > datetime('now', '-7 days')
            GROUP BY agent_used
            ORDER BY total DESC
        """)
```

Progress shown to user in overlay:

```
HoloDesk Status
Day 6 of 14 — Learning your routine
Acceptance rate this week: 73%
Fastest feature: Screen reader (avg 1.2s)
Most used: Voice commands (34 times today)
```

---

# 11. Background Processing — What's Real

## 11.1 Honest Constraints

| Device state | What HoloDesk can do |
|---|---|
| On + logged in | Full background processing, all agents active |
| Sleeping | Python process suspended by OS. Nothing runs. |
| Off | Nothing. |

## 11.2 The Solution: Analysis on Wake

```python
# app/startup.py
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

def on_startup():
    """
    Run background analysis immediately on launch.
    Happens in 2-3 seconds while Pygame loads.
    To the user, feels like it ran overnight.
    """
    last_run = config.get("last_analysis")
    if last_run:
        hours_since = (datetime.now() - datetime.fromisoformat(last_run)).seconds / 3600
        if hours_since < 4:
            return  # Ran recently, skip

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_patterns = executor.submit(memory_agent.analyze_patterns)
        f_events   = executor.submit(calendar_agent.get_todays_events)
        f_stats    = executor.submit(improvement_tracker.weekly_report)

        patterns = f_patterns.result(timeout=10)
        events   = f_events.result(timeout=10)
        stats    = f_stats.result(timeout=5)

    # Generate natural morning briefing via Groq
    briefing = groq.complete(
        prompt=f"""
        User habits: {patterns}
        Today's calendar: {events}
        Weekly stats: {stats}
        Unfinished from last session: {memory_agent.get_unfinished_context()}
        
        Generate a friendly, specific, 2-3 sentence morning briefing.
        Mention real app names and real events. Be helpful not corporate.
        """
    )

    config.set("pending_briefing", briefing)
    config.set("last_analysis", datetime.now().isoformat())
```

User experience: laptop opens -> 3 second load -> morning briefing plays immediately. Feels like HoloDesk worked all night. That is the UX trick.

---

# 12. Production Checklist — Every Step

## Phase 0: Foundation
- [ ] Camera thread separated from main thread
- [ ] Vision/gesture thread separated
- [ ] Audio thread separated
- [ ] All threads use queue communication (no shared variables)
- [ ] Main loop locked to 30fps with clock.tick(30)
- [ ] Gesture: 8-frame buffer implemented
- [ ] Gesture: intent zone (top 40% only) implemented
- [ ] Gesture: cooldown after trigger implemented
- [ ] Graceful crash if camera not found
- [ ] Graceful crash if API key missing
- [ ] All errors logged to data/holodesk.log

## Phase 1: Data Layer
- [ ] SQLite schema created with all tables
- [ ] DB wrapper: thread-safe (thread-local connections)
- [ ] WAL mode enabled
- [ ] Memory logger running every 60 seconds
- [ ] Blocklist: banking/password windows never logged
- [ ] Session start/end properly recorded
- [ ] User can delete all data from privacy dashboard

## Phase 2: Face ID
- [ ] dlib + face_recognition installed
- [ ] Setup flow: 5 photo capture + encoding stored
- [ ] Login flow: webcam check at startup
- [ ] Multi-user: multiple encodings supported
- [ ] Fallback: manual PIN if face not detected
- [ ] Encodings never uploaded anywhere

## Phase 3: Screen Vision
- [ ] Blocklist check before every screenshot
- [ ] Screenshot resized to 1280px width before API call
- [ ] GPT-4o Vision call wrapped in try/catch
- [ ] User notified when screen content sent to OpenAI
- [ ] Screen vision toggle in privacy dashboard
- [ ] Response shown in overlay AND spoken via TTS

## Phase 4: Calendar
- [ ] Google Calendar API credentials.json in place
- [ ] OAuth flow on first startup, token stored
- [ ] Token auto-refresh handled
- [ ] Fetch runs at startup + every 60 minutes
- [ ] Graceful if user declines calendar permission

## Phase 5: Morning Briefing
- [ ] Startup analysis runs before UI loads
- [ ] CalendarAgent + MemoryAgent run in parallel on startup
- [ ] Groq generates natural language briefing
- [ ] Briefing plays via TTS on startup
- [ ] Briefing text shown as dismissable overlay card
- [ ] User can say "dismiss" or open palm to skip

## Phase 6: Chatbot Panel
- [ ] Panel slides in/out with smooth animation
- [ ] Text input works
- [ ] Voice input works inside panel
- [ ] Session history persists
- [ ] Context injected: habits + calendar + screen
- [ ] Clear button works
- [ ] Groq falls back to Gemini if unavailable

## Phase 7: 3D Objects
- [ ] Cube renders with perspective projection
- [ ] Idle rotation when not interacting
- [ ] Hand-controlled rotation via wrist angle
- [ ] Pinch to grab
- [ ] Throw physics with damping
- [ ] Bounce off overlay edges
- [ ] Second shape (sphere or blob)

## Phase 8: Polish
- [ ] Overlay themes (dark / light / neon)
- [ ] Smooth animations on all UI transitions
- [ ] All errors show friendly message (no raw exceptions)
- [ ] CPU usage under 15% at idle
- [ ] RAM stable over 2 hours (no memory leaks)
- [ ] All API keys from .env, never hardcoded

## Phase 9: Packaging
- [ ] PyInstaller spec file created
- [ ] All MediaPipe model files bundled
- [ ] Whisper model included in bundle
- [ ] First-run wizard: enter API key, stored in AppData
- [ ] Inno Setup installer script created
- [ ] Installer creates Start Menu shortcut + uninstaller
- [ ] Tested on clean Windows machine (not dev machine)

---

# 13. Folder Structure

```
holodesk/
+-- app/
|   +-- main.py                   # Entry point
|   +-- startup.py                # Boot sequence + background analysis
|
+-- agents/
|   +-- orchestrator.py           # Central brain + parallel dispatch
|   +-- screen_agent.py           # Screenshot + GPT-4o Vision
|   +-- memory_agent.py           # SQLite logs + habit detection
|   +-- calendar_agent.py         # Google Calendar API
|   +-- voice_agent.py            # Whisper STT + SAPI TTS
|   +-- task_agent.py             # Desktop automation
|   +-- chat_agent.py             # Groq conversation
|   +-- notify_agent.py           # Proactive notifications
|   +-- improvement_tracker.py   # Feedback loop
|
+-- ui/
|   +-- overlay.py                # Main Pygame window
|   +-- chatbot_panel.py          # Expandable chat UI
|   +-- notification_card.py      # Morning briefing + alerts
|   +-- face_id_screen.py         # Login + setup UI
|   +-- stress_objects.py         # 3D interactive objects
|   +-- privacy_dashboard.py     # Privacy controls
|
+-- vision/
|   +-- hand_tracker.py           # MediaPipe (threaded)
|   +-- gesture_detector.py       # Debounced gesture recognition
|   +-- face_detector.py          # face_recognition wrapper
|
+-- core/
|   +-- queues.py                 # All shared queues
|   +-- camera_thread.py          # Camera capture thread
|   +-- vision_thread.py          # MediaPipe processing thread
|   +-- thread_pool.py            # Agent worker thread pool
|
+-- connectors/
|   +-- llm_router.py             # Routes to right LLM + fallback
|   +-- groq_client.py            # Groq wrapper
|   +-- openai_client.py          # GPT-4o Vision wrapper
|   +-- claude_client.py          # Anthropic wrapper
|   +-- gemini_client.py          # Gemini wrapper
|   +-- calendar_client.py        # Google Calendar OAuth
|
+-- storage/
|   +-- db.py                     # Thread-safe SQLite wrapper
|   +-- encrypted_db.py           # SQLCipher version
|   +-- schema.sql                # Database schema
|   +-- memory_store.py           # High-level memory operations
|
+-- utils/
|   +-- screenshot.py             # Screen capture + blocklist
|   +-- audio.py                  # Audio recording helpers
|   +-- config.py                 # Config read/write
|   +-- logger.py                 # Logging setup
|
+-- data/                         # Runtime generated, gitignored
|   +-- holodesk.db               # SQLite database
|   +-- holodesk.log              # Error logs
|   +-- calendar_token.json       # Google OAuth token
|
+-- models/                       # Runtime generated, gitignored
|   +-- face_encodings/           # User face data (.pkl files)
|
+-- assets/
|   +-- sounds/
|   +-- fonts/
|
+-- .env                          # API keys, never in git
+-- .env.example                  # Template for setup
+-- config.json                   # User preferences
+-- requirements.txt
+-- holodesk.spec                 # PyInstaller spec
+-- README.md
```

---

# 14. 3-Week Sprint Plan

## Week 1 — Solid Foundation (Days 1-7)
Goal: Stable 30fps. No phantom gestures. Voice works. Agents talk to each other. Data layer ready.

| Day | Task | Owner |
|-----|------|-------|
| 1 | Refactor main.py -> modular structure. All folders created. | Both |
| 2 | Camera thread + vision thread with queues | Friend |
| 2 | SQLite schema + DB wrapper + memory logger | Sat |
| 3 | Gesture debouncer: 8-frame + intent zone + cooldown | Friend |
| 3 | Orchestrator skeleton: queue reader + agent router | Sat |
| 4 | VoiceAgent: wake word + Whisper STT + SAPI TTS | Friend |
| 4 | MemoryAgent: session logging + app event logging | Sat |
| 5 | End-to-end test: voice -> orchestrator -> response -> TTS | Both |
| 6 | LLM router: Groq primary + Gemini fallback | Sat |
| 6 | Overlay: status bar showing agent activity live | Friend |
| 7 | Bug fixes. Performance test. FPS validation. | Both |

End of Week 1 demo: Say "hey desk what time is it" -> responds. V-gesture activates. Open palm stops speech. Stable 30fps.

---

## Week 2 — Power Features (Days 8-14)
Goal: The jaw-drop features.

| Day | Task | Owner |
|-----|------|-------|
| 8 | Face ID: setup flow + login detection | Friend |
| 8 | CalendarAgent: OAuth setup + event fetch | Sat |
| 9 | ScreenAgent: screenshot + blocklist + GPT-4o Vision | Sat |
| 9 | Chatbot panel: slide animation + text input | Friend |
| 10 | Morning briefing: startup analysis + Groq narration + TTS | Sat |
| 10 | ChatAgent: full conversation + context injection | Sat |
| 11 | TaskAgent: app launch + scroll + Claude delegation | Sat |
| 11 | Chatbot panel: voice input inside panel | Friend |
| 12 | Parallel dispatch test: 2+ agents simultaneously | Both |
| 13 | Improvement tracker: feedback logging + acceptance rate | Sat |
| 13 | Notification cards: UI component for proactive alerts | Friend |
| 14 | Full end-to-end test: morning briefing flow works | Both |

End of Week 2 demo: Laptop opens -> briefing plays -> "read my screen" -> explains screen -> chatbot opens -> full conversation.

---

## Week 3 — Polish + Wow Factor (Days 15-21)
Goal: Looks and feels like a real product.

| Day | Task | Owner |
|-----|------|-------|
| 15 | 3D cube: projection math + idle spin | Friend |
| 15 | Habit pattern detection: SQL queries + LLM narration | Sat |
| 16 | 3D interaction: hand rotation + pinch + throw physics | Friend |
| 16 | Proactive notifications from habit patterns | Sat |
| 17 | Privacy dashboard: all toggles + data stats + delete all | Both |
| 18 | UI polish: animations, themes, fonts, transitions | Friend |
| 18 | Error handling: every API call has friendly fallback | Sat |
| 19 | Performance: CPU under 15% idle. RAM stable 2 hours. | Both |
| 20 | PyInstaller EXE + Inno Setup installer | Friend |
| 20 | README + demo video script | Sat |
| 21 | Final test on clean Windows machine. Submit. | Both |

---

# 15. Division of Work

## Sat — AI Brain + Agent Logic
- OrchestratorAgent: routing logic + parallel dispatch
- ScreenAgent: screenshot pipeline + GPT-4o Vision
- MemoryAgent: schema + habit SQL queries + pattern logic
- CalendarAgent: Google OAuth + briefing generation
- ChatAgent: conversation system + context injection
- TaskAgent: app launcher + Claude delegation + clipboard
- LLM Router: all four API clients + fallback logic
- Morning briefing: startup analysis pipeline
- Improvement tracker: acceptance rate tuning

## Friend — Systems + UI
- Threading: camera + vision + audio + orchestrator threads
- Queue system: all shared queues + non-blocking reads
- Gesture debouncer: frame buffer + intent zone + cooldown
- VoiceAgent: Whisper STT + SAPI TTS + wake word detection
- Face ID: face_recognition setup flow + login screen
- Chatbot panel UI: slide animation + inputs
- 3D stress objects: math + hand interaction + physics
- Privacy dashboard UI: toggles + data display
- Overlay polish: themes + animations
- PyInstaller + Inno Setup packaging

## Sync Points (Both must attend)
- End Day 5: First voice command end-to-end works
- End Day 10: Parallel agent dispatch works
- End Day 14: Full morning briefing flow works
- End Day 20: EXE installs on clean machine

---

# 16. Tech Stack Reference

| Component | Library | Install Command |
|---|---|---|
| UI / Overlay | pygame | pip install pygame |
| Hand tracking | mediapipe | pip install mediapipe |
| Face ID | face_recognition | pip install face_recognition |
| Local STT | faster-whisper | pip install faster-whisper |
| TTS | pywin32 | pip install pywin32 |
| Screen capture | pyautogui | pip install pyautogui |
| Desktop control | pyautogui + pywin32 | (above) |
| Audio recording | pyaudio | pip install pyaudio |
| Image processing | Pillow | pip install Pillow |
| Process info | psutil | pip install psutil |
| Database | sqlite3 | built into Python |
| DB encryption | sqlcipher3 | pip install sqlcipher3 |
| Groq LLM | groq | pip install groq |
| OpenAI Vision | openai | pip install openai |
| Claude | anthropic | pip install anthropic |
| Gemini | google-generativeai | pip install google-generativeai |
| Google Calendar | google-api-python-client | pip install google-api-python-client google-auth-oauthlib |
| Clipboard | pyperclip | pip install pyperclip |
| Env vars | python-dotenv | pip install python-dotenv |
| Packaging | pyinstaller | pip install pyinstaller |
| Installer | Inno Setup | Download from jrsoftware.org |

---

## The One-Line Pitch

> *"HoloDesk is the first ambient AI layer for Windows — a transparent overlay that passively learns your daily routine, orchestrates Claude, Groq, and your tools in parallel, and proactively helps you before you even ask."*

---

*Built in 3 weeks. Genuinely novel. Ships as a real product.*