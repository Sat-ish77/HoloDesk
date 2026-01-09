# 🧠 HoloDesk

**A gesture-controlled multimodal AI desktop assistant** *(learning project)*

---

## What is HoloDesk?

HoloDesk is an experimental desktop AI assistant that explores new ways of interacting with computers using:

- **Hand gestures** (via webcam + computer vision)
- **Voice commands** (speech-to-text with Whisper)
- **AI reasoning** (LLM-powered responses via Groq)
- **Desktop automation** (control apps, scroll, open/close windows)

Instead of traditional mouse-and-keyboard input, HoloDesk focuses on **human-computer interaction** where gestures and speech drive on-screen actions.

This project was built **incrementally from scratch** as a learning journey into computer vision, real-time systems, and AI integration.

---

## Core Features (Working)

| Feature | Description |
|---------|-------------|
| ✋ **Hand Cursor** | Move cursor with your index finger |
| 🤏 **Pinch to Grab** | Pinch gesture to grab and drag on-screen objects |
| ✌️ **V-Gesture Voice** | Show peace sign → speak command → auto off |
| 🎙️ **Voice Commands** | "scroll down", "open chrome", "change color", etc. |
| 🧠 **AI Conversations** | Ask anything - powered by Groq LLM (Llama 3.1) |
| 👍👎 **Toggle Scroll** | Thumbs up/down ONCE = continuous scrolling |
| ✋ **Open Palm Stop** | Stop scrolling OR stop AI speech instantly |
| 🖥️ **App Control** | Open Chrome, Notepad, Facebook, YouTube, Netflix |
| 🔊 **Interruptible TTS** | AI speaks - but you can stop it with palm! |
| 👻 **Transparent Overlay** | See-through window that floats above all apps |

---

## Development Progress

| Step | Status | Description |
|------|--------|-------------|
| Step 0 | ✅ Done | Desktop window, webcam feed, FPS display |
| Step 1 | ✅ Done | Hand tracking → cursor follows index finger |
| Step 2 | ✅ Done | Pinch gesture → grab & drag virtual card |
| Step 3 | ✅ Done | Voice commands with Whisper STT + Windows SAPI TTS |
| Step 4 | ✅ Done | AI agent integration (Groq LLM API) |
| Step 5 | ✅ Done | Desktop control (scroll, apps, gesture activation) |
| Step 5.5 | ✅ Done | Simplified: V-gesture voice, toggle scroll, palm stop |
| Step 6 | ✅ Done | Transparent overlay - always-on-top, see-through window |

---

## Future Roadmap

| Feature | Description |
|---------|-------------|
| 🔐 **User Authentication** | Email signup + OTP verification |
| 👤 **Face Recognition** | Login with face detection |
| ♿ **Accessibility Mode** | Full voice-only or gesture-only operation |
| 🌐 **Multi-language** | Support for non-English speakers |
| 📊 **Screen Analysis** | AI describes what's on screen (for visually impaired) |
| 💾 **Session Storage** | Save conversations and preferences |

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python** | Core programming language |
| **Pygame** | Real-time UI rendering & game loop |
| **OpenCV** | Webcam access & image processing |
| **MediaPipe** | Hand landmark detection (21 points) |
| **faster-whisper** | Local speech-to-text (OpenAI Whisper) |
| **Windows SAPI** | Text-to-speech output |
| **Groq API** | LLM reasoning (Llama 3.1 70B) |
| **PyAutoGUI** | Desktop automation (scroll, click, hotkeys) |
| **pywin32** | Windows API for transparent, always-on-top window |

---

## Why This Project?

This project was built to **learn by doing**, focusing on:

- 👁️ **Computer Vision** fundamentals (hand tracking, gesture recognition)
- 🔄 **Real-time Programming** (event loops, state machines, threading)
- 🤖 **Multimodal AI** (vision + speech + reasoning working together)
- 🏗️ **System Design** (clean architecture, incremental development)

Rather than optimizing for production, the goal is **deep understanding**.

---

## How to Run

```bash
# Clone the repository
git clone https://github.com/Sat-ish77/HoloDesk.git
cd HoloDesk

# Install dependencies
pip install -r requirements.txt

# Add your Groq API key to .env file
# GROQ_API_KEY=your_key_here

# Run the application
python app/main.py
```

### Controls

| Input | Action |
|-------|--------|
| ✌️ **V-Gesture (peace sign)** | Start voice command (auto-off after) |
| 🤏 Pinch | Grab/release objects |
| 👍 Thumbs Up (once) | START scrolling up |
| 👎 Thumbs Down (once) | START scrolling down |
| ✋ **Open Palm** | STOP scrolling / STOP AI speech |

### Voice Commands

- `"stop"` - Stop scrolling
- `"hello"` - Greeting
- `"change color to [red/blue/green/purple/yellow]"` - Change card color
- `"reset"` - Reset card position and color
- `"scroll up/down"` - Scroll the active window
- `"open chrome/notepad/facebook/youtube/netflix"` - Launch apps
- `"close window"` - Close current window (Alt+F4)
- `"minimize"` - Minimize all windows
- `"[any question]"` - Ask AI anything!

---

## Project Structure

```
holodesk/
├── app/
│   └── main.py          # Main application (all current logic)
├── vision/              # (Future) Computer vision modules
├── ui/                  # (Future) UI components
├── audio/               # (Future) Audio processing
├── storage/             # (Future) Data persistence
├── .env                 # API keys (not in git)
├── .gitignore
├── requirements.txt
├── README.md
└── PROJECT_STATE.md     # Detailed development notes
```

---

## Lessons Learned

Key concepts explored in this project:

1. **Threading** - Running voice recognition without freezing UI
2. **State Machines** - Managing IDLE/HOVER/GRAB states for interactions
3. **Coordinate Systems** - Transforming hand positions to screen coordinates
4. **API Integration** - Connecting to LLM services for AI responses
5. **Desktop Automation** - Controlling OS-level actions from Python
6. **Toggle States** - Scroll mode persists until palm stop
7. **Async Speech** - Interruptible text-to-speech using Windows SAPI
8. **Gesture Recognition** - V-gesture, thumbs up/down, open palm
9. **UX Iteration** - Learned that "always-on mic" causes more problems than it solves!

---

## Author

Built as a **personal learning project**, with AI tools used as assistants for exploration and iteration.

The focus is on **understanding system design**, not writing every line manually from memory.

---

## Acknowledgments

- [MediaPipe](https://mediapipe.dev/) - Google's hand tracking
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized Whisper
- [Groq](https://groq.com/) - Fast LLM inference
- [Pygame](https://www.pygame.org/) - Python game development
