# HoloDesk Project State 🖐️🎤🤖

## What is HoloDesk?
A **gesture-controlled AI desktop assistant** - like having Jarvis on your computer! You can control your computer using **hand gestures** and **voice commands**, and have **AI conversations**.

**Vision:** Build an accessibility tool for people who can't use traditional input devices (mouse/keyboard).

---

## Current Status: Step 5 COMPLETE ✅

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
│   └── main.py              ← ALL the code (~485 lines)
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

| Command | What it does | Code location |
|---------|--------------|---------------|
| "reset" / "reset the card" | Move card to center | Line ~300 |
| "color red/blue/green/yellow/purple/orange/white/black/pink" | Change card color | Line ~305 |
| "color" (no specific color) | Random color | Line ~325 |
| "scroll up" / "screw up" / "scrawl up" | Scroll page up | Line ~350 |
| "scroll down" / "screw down" | Scroll page down | Line ~355 |
| "scroll up/down a lot" | Big scroll | Same lines |
| "open chrome" | Opens Chrome browser | Line ~365 |
| "open facebook" | Opens Facebook in Chrome | Line ~370 |
| "open youtube" | Opens YouTube in Chrome | Line ~375 |
| "open netflix" | Opens Netflix in Chrome | Line ~380 |
| "open notepad" | Opens Notepad | Line ~385 |
| "minimize" / "minimize window" | Minimize current window | Line ~395 |
| "close window" / "close this" / "close app" | Close current window | Line ~390 |
| "hello" / "hi" | Greeting response | Line ~330 |
| "bye" / "goodbye" | Farewell response | Line ~332 |
| "help" | List commands | Line ~338 |
| "thank you" / "thanks" | You're welcome | Line ~336 |
| Anything else | Sent to AI for response | Line ~410 |

---

# ALL GESTURE CONTROLS

| Gesture | What it does | Detection logic |
|---------|--------------|-----------------|
| ☝️ Point (index finger) | Move cursor | Track landmark 8 position |
| 🤏 Pinch (thumb + index close) | Grab/drag objects | Distance < 50 pixels |
| ✌️ V sign (peace) | Activate voice listening | Index+Middle UP, Ring+Pinky DOWN |
| 👍 Thumbs up | Scroll up continuously | Thumb UP, all fingers curled |
| 👎 Thumbs down | Scroll down continuously | Thumb DOWN, all fingers curled |

---

# KNOWN ISSUES & SOLUTIONS

| Issue | Why | Solution |
|-------|-----|----------|
| Whisper mishears words | Accent/pronunciation | Added spelling variations ("screw" = "scroll") |
| Scroll doesn't work | Wrong window focused | Click on target window first |
| "hi" triggers on "something" | Substring match | Changed to whole-word matching |
| Voice not detected | Pygame using mic | Added `pygame.mixer.quit()` |
| TTS no audio | pyttsx3 threading bug | Switched to Windows SAPI |

---

# HOW TO RUN

```bash
cd holodesk
python app/main.py
```

Wait for "Whisper model loaded successfully!" then:
- Show ✌️ to activate voice
- Show 👍/👎 to scroll
- Pinch to grab the card

---

# FUTURE ROADMAP

### Step 6: Transparent Overlay
- Make HoloDesk see-through
- Float on top of other apps
- Only show cursor and UI elements

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
> "Please read @PROJECT_STATE.md and help me continue building HoloDesk. We're on Step 5 complete, ready for Step 6."

---

**Last Updated:** Step 5 Complete
**Lines of Code:** ~485
**Author:** Satish Wagle
