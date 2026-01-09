# HoloDesk Project State 🖐️🎤🤖

## What is HoloDesk?
A **gesture-controlled AI desktop assistant** - like having Jarvis on your computer! You can control your computer using **hand gestures** and **voice commands**, and have **AI conversations**.

**Vision:** Build an accessibility tool for people who can't use traditional input devices (mouse/keyboard).

---

## Current Status: Step 6 COMPLETE ✅

---

# ULTRA-DETAILED EXPLANATION OF EVERYTHING WE BUILT

## Step 0: Basic Setup
**What we did:** Created a Pygame window that displays webcam feed.

**Key concepts:**
- `pygame.init()` - Starts the Pygame engine
- `cv2.VideoCapture(0)` - Opens webcam (0 = default camera)
- `while running:` - Main game loop runs 60 times per second
- `pygame.display.flip()` - Updates the screen with new frame

---

## Step 1: Hand Tracking
**What we did:** Added MediaPipe to detect hands and track finger position.

**Key concepts:**
- MediaPipe provides 21 "landmarks" (points) on your hand
- Landmark 8 = Index fingertip (we use this as cursor)
- `results = mp_hands.process(frame)` - Finds hands in webcam frame
- Convert landmark (0-1 range) to screen coordinates (pixels)

**Code logic:**
```python
index_tip = hand_landmarks.landmark[8]  # Get index finger tip
cursor_x = int((1 - index_tip.x) * WINDOW_WIDTH)  # Convert to pixels
cursor_y = int(index_tip.y * WINDOW_HEIGHT)
```

---

## Step 2: Pinch to Grab
**What we did:** Detect pinch gesture (thumb + index close together) to grab objects.

**Key concepts:**
- Calculate distance between thumb tip (landmark 4) and index tip (landmark 8)
- If distance < 50 pixels = pinching!
- State machine: `is_grabbing` tracks if we're currently holding something

**Code logic:**
```python
distance = ((cursor_x - thumb_x) ** 2 + (cursor_y - thumb_y) ** 2) ** 0.5
is_pinching = distance < 50  # Pixels
if is_pinching and cursor_over_card:
    is_grabbing = True
```

---

## Step 3: Voice Commands
**What we did:** Added speech recognition (Whisper) and text-to-speech (Windows SAPI).

### Speech-to-Text (Hearing your voice):
- **Library:** `faster-whisper` (OpenAI's Whisper model, runs locally)
- **Model:** "small" (better accuracy than "base")
- **Flow:** Microphone → Audio → Whisper → Text

### Text-to-Speech (Computer speaking):
- **Library:** `comtypes` (Windows SAPI - built into Windows)
- **Why not pyttsx3?** It was buggy and audio kept failing

### Threading:
- Voice listening runs in a **background thread** so it doesn't freeze the UI
- `threading.Thread(target=listen_for_command, daemon=True).start()`

**Code flow:**
```
1. User shows ✌️ V gesture
2. listen_for_command() starts in background thread
3. Microphone captures audio
4. Whisper converts audio → text
5. Text is stored in `last_command`
6. Main loop processes command
7. speak() function responds via Windows SAPI
```

---

## Step 4: AI Integration
**What we did:** Connected Groq API (Llama 3.1) for intelligent conversations.

**Key concepts:**
- **Groq API:** Free, fast LLM API (uses Llama 3.1 model)
- **API Key:** Stored in `.env` file (never commit to GitHub!)
- `python-dotenv` loads the key from `.env`

**Code logic:**
```python
from groq import Groq
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def ask_ai(question):
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are HoloDesk..."},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content
```

**Command flow:**
- If command matches specific keywords (reset, color, scroll) → Do that action
- If no match → Send to AI for intelligent response

---

## Step 5: Desktop Control & Advanced Gestures
**What we did:** Added scroll, open apps, close/minimize, and gesture scrolling.

### pyautogui:
- `pyautogui.scroll(50)` - Scroll up
- `pyautogui.scroll(-50)` - Scroll down
- `pyautogui.hotkey('alt', 'F4')` - Close window
- `pyautogui.hotkey('win', 'm')` - Minimize window

### V Gesture (✌️) for Voice:
- Index finger UP + Middle finger UP
- Ring finger DOWN + Pinky finger DOWN
- When detected → Start voice listening

### Thumbs Up/Down (👍👎) for Scrolling:
- All fingers curled (fist shape)
- Thumb pointing UP → Continuous scroll up
- Thumb pointing DOWN → Continuous scroll down

**Finger detection logic:**
```python
# Finger is UP if tip is higher (lower y) than base
index_up = index_tip.y < index_base.y
middle_up = middle_tip.y < middle_base.y
ring_down = ring_tip.y > ring_base.y
pinky_down = pinky_tip.y > pinky_base.y

is_v_gesture = index_up and middle_up and ring_down and pinky_down
```

---

# TECH STACK EXPLAINED

| Component | Library | Why we use it |
|-----------|---------|---------------|
| Window/Graphics | Pygame | Easy to draw shapes, display webcam |
| Webcam | OpenCV (cv2) | Read frames from camera |
| Hand tracking | MediaPipe | Google's ML model, very accurate |
| Speech-to-Text | faster-whisper | OpenAI Whisper, works offline, good with accents |
| Text-to-Speech | comtypes (SAPI) | Windows built-in, reliable |
| AI Chat | Groq API | Free, fast, uses Llama 3.1 |
| Desktop control | pyautogui | Control mouse, keyboard, scroll |
| Environment | python-dotenv | Load secrets from .env file |

---

# FILE STRUCTURE

```
holodesk/
├── app/
│   └── main.py              ← ALL the code (~630 lines)
├── audio/                    ← Empty (for future)
├── vision/                   ← Empty (for future)
├── storage/                  ← Empty (for future)
├── ui/                       ← Empty (for future)
├── .env                      ← GROQ_API_KEY=gsk_xxx (SECRET!)
├── .gitignore                ← Ignores .env, __pycache__
├── requirement.txt           ← All pip dependencies
├── README.md                 ← Project description
└── PROJECT_STATE.md          ← THIS FILE (memory anchor)
```

---

# ALL VOICE COMMANDS

| Command | What it does |
|---------|--------------|
| **"stop"** / "stop scrolling" | Stop scrolling |
| "reset" / "reset the card" | Move card to center |
| "color red/blue/green/yellow/purple/orange/white/black/pink" | Change card color |
| "color" (no specific color) | Random color |
| "scroll up" / "screw up" / "scrawl up" | Scroll page up |
| "scroll down" / "screw down" | Scroll page down |
| "scroll up/down a lot" | Big scroll |
| "open chrome" | Opens Chrome browser |
| "open facebook" | Opens Facebook in Chrome |
| "open youtube" | Opens YouTube in Chrome |
| "open netflix" | Opens Netflix in Chrome |
| "open notepad" | Opens Notepad |
| "minimize" / "minimize window" | Minimize current window |
| "close window" / "close this" / "close app" | Close current window |
| "hello" / "hi" | Greeting response |
| "bye" / "goodbye" | Farewell response |
| "help" | AI explains what it can do (questions, open apps/webpages) |
| "thank you" / "thanks" | You're welcome |
| Anything else | Sent to AI for response |

---

# ALL GESTURE CONTROLS

| Gesture | What it does | Detection logic |
|---------|--------------|-----------------|
| ☝️ Point (index finger) | Move cursor | Track landmark 8 position |
| 🤏 Pinch (thumb + index close) | Grab/drag objects | Distance < 50 pixels |
| ✌️ V-Gesture (peace sign) | Activate voice (single use) | Index+Middle CLEARLY UP, Ring+Pinky CLEARLY DOWN |
| 👍 Thumbs up (once) | START scrolling up | Thumb UP, all fingers curled |
| 👎 Thumbs down (once) | START scrolling down | Thumb DOWN, all fingers curled |
| ✋ Open Palm | STOP scrolling + STOP AI speech | All 5 fingers extended |

---

# KNOWN ISSUES & SOLUTIONS

| Issue | Why | Solution |
|-------|-----|----------|
| Whisper mishears words | Accent/pronunciation | Added spelling variations ("screw" = "scroll") |
| Scroll doesn't work | Wrong window focused | Click on target window first |
| "hi" triggers on "something" | Substring match | Changed to whole-word matching |
| Voice not detected | Pygame using mic | Added `pygame.mixer.quit()` |
| TTS no audio | pyttsx3 threading bug | Switched to Windows SAPI |
| Call Me gesture = thumbs up | Gestures too similar | Removed Call Me, use V-gesture |
| "holo on" doesn't work | Can't hear if mic is off! | Removed, use V-gesture instead |
| Always-on mic unreliable | Background noise, CPU | Removed, single activation only |

---

# HOW TO RUN

```bash
cd holodesk
python app/main.py
```

Wait for "Whisper model loaded successfully!" then:
- Show ✌️ (V-gesture / peace sign) to activate voice → speak → auto off
- Show 👍 (once) to START scrolling up
- Show 👎 (once) to START scrolling down
- Show ✋ (Open Palm) to STOP scrolling or STOP AI speech
- Pinch to grab the card

---

## Step 5.5: Simplified Voice + Toggle Scroll + Palm Stop
**What we did:** Simplified the UX after learning that "always-on mic" doesn't work well!

### What we TRIED (and failed):
- ❌ **Call Me gesture** = confused with thumbs up
- ❌ **"holo on/off" commands** = can't say them if mic is off! (chicken-and-egg)
- ❌ **Always-on listening** = background noise, unreliable

### What we KEPT (works great!):

#### 1. STRICT V-Gesture ✌️ (Single Voice Activation)
**How to do it:** Index + Middle UP, Ring + Pinky DOWN (peace sign)

**How it works:**
- Show ✌️ → Mic ON → Speak command → Mic auto OFF
- Show ✌️ again for next command
- Simple and reliable!

**Strict detection (avoids false triggers):**
```python
is_v_gesture = (
    index_tip.y < index_mcp.y - 0.08 and   # Index CLEARLY up
    middle_tip.y < middle_base.y - 0.08 and # Middle CLEARLY up
    ring_tip.y > ring_base.y + 0.03 and    # Ring clearly down
    pinky_tip.y > pinky_base.y + 0.03 and  # Pinky clearly down
    not is_open_palm                        # NOT open palm!
)
```

#### 2. Toggle Scrolling (Works Great!)
- 👍 Thumbs up ONCE = START scrolling up
- 👎 Thumbs down ONCE = START scrolling down
- Keeps scrolling until stopped!

#### 3. Open Palm ✋ (Stop Everything)
- Stops scrolling
- Stops AI speech
- Universal "STOP" gesture

#### 4. AI Speech Interruption
- `speak()` runs asynchronously
- Open palm sets `stop_speaking_flag = True`
- AI stops immediately!

---

### What We Learned (Important!):

| What we tried | Why it failed |
|---------------|---------------|
| "holo on" voice command | Can't hear it if mic is OFF! |
| Always-on listening | Background noise, CPU usage, unreliable |
| Call Me gesture 🤙 | Too similar to thumbs up, false triggers |
| Continuous listening | Gaps between processing = missed commands |

**Key Lesson:** Simple > Smart. Single activation is more reliable than always-on!

---

### Current State Variables:
```python
is_scrolling = False        # Toggle for continuous scrolling
scroll_direction = 0        # 1=up, -1=down, 0=stopped
v_gesture_cooldown = 0      # Prevents rapid V-gesture triggers
open_palm_cooldown = 0      # Prevents rapid stop triggers
is_ai_speaking = False      # Track if AI is talking
stop_speaking_flag = False  # Signal to interrupt speech
```

---

### Future Improvement (Paid):
To enable "Hey Holo" wake word activation:
- Use **Picovoice Porcupine** (wake word detection library)
- Tiny model listens ONLY for "Hey Holo"
- When detected → activate full Whisper
- Requires paid API key

---

## Step 6: Transparent Overlay ✅ COMPLETE
**What we did:** Made the HoloDesk window transparent and always-on-top, so it floats above all apps like a HUD overlay.

**Key concepts:**
- **Windows API (win32gui, win32con, win32api):** Direct access to Windows window management
- **HWND (Window Handle):** Unique identifier for the window
- **WS_EX_LAYERED:** Windows flag that enables transparency
- **Color Key Transparency:** Black pixels become invisible (see-through)
- **HWND_TOPMOST:** Keeps window above all other windows

**How it works:**
1. Get the Pygame window's HWND (Windows handle)
2. Add `WS_EX_LAYERED` style flag (enables transparency)
3. Set color key: black (0,0,0) = transparent
4. Set window to `HWND_TOPMOST` (always on top)
5. Draw UI elements in colors (not black) so they're visible

**Code logic:**
```python
# Get window handle from Pygame
pygame_window_info = pygame.display.get_wm_info()
hwnd = pygame_window_info['window']

# Enable transparency
current_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
new_style = current_style | win32con.WS_EX_LAYERED
win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)

# Black = transparent
win32gui.SetLayeredWindowAttributes(
    hwnd,
    win32api.RGB(0, 0, 0),  # Black becomes invisible
    0,
    win32con.LWA_COLORKEY
)

# Always on top
win32gui.SetWindowPos(
    hwnd,
    win32con.HWND_TOPMOST,
    0, 0, 0, 0,
    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
)
```

**What you see:**
- Window has no title bar (borderless)
- Black background is transparent (you see desktop through it)
- Blue glowing cursor is visible (not black, so it shows)
- Status indicators (FPS, gestures) are visible
- Window stays on top of Chrome, Notepad, etc.

**Dependencies added:**
- `pywin32` - Windows API access

**Known issues:**
- Emoji characters (✅, ⚠️) don't work in Windows console → replaced with `[OK]` and `[WARNING]`

---

# FUTURE ROADMAP

### Step 7: AI Vision
- Take screenshot of screen
- Send to GPT-4 Vision API
- "What's on my screen?" command

### Step 8: Face Recognition Login
- Use `face_recognition` library
- Save user face on signup
- Verify face on login

### Step 9: Context-Aware Agent
- Remember conversation history
- Learn user preferences
- Proactive suggestions

---

# DEPENDENCIES (requirement.txt)

```
pygame==2.5.2
opencv-python==4.9.0.80
mediapipe
numpy==1.26.4
SpeechRecognition
pyttsx3
pyaudio
faster-whisper
comtypes
groq
python-dotenv
pyautogui
```

---

# GITHUB REPO
https://github.com/Sat-ish77/HoloDesk

---

# FOR NEW CHAT SESSION

When starting a new chat, say:
> "Please read @PROJECT_STATE.md and help me continue building HoloDesk. We're on Step 5.5 complete (simplified), ready for Step 6."

---

**Last Updated:** Step 6 Complete (Transparent overlay - always-on-top, see-through window)
**Lines of Code:** ~718
**Author:** Satish Wagle
