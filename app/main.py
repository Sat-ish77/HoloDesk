import pygame
import os
import sys
import queue
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from groq import Groq
import time
import speech_recognition as sr
import pyttsx3
import threading
from faster_whisper import WhisperModel
import tempfile
import wave
import pyautogui
import audioop

# Add project root to path so agents/, connectors/, core/, vision/ are importable
sys.path.insert(0, str(Path(__file__).parent.parent))
# app/ itself must also be on sys.path so startup.py can be imported as 'startup'
sys.path.insert(0, str(Path(__file__).parent))

# ===== MORNING BRIEFING STARTUP =====
from startup import on_startup
from storage.db import db as _db

DEMO_MODE = "--demo" in sys.argv
on_startup(DEMO_MODE)

# ===== THREADING REFACTOR (Step 8) =====
from core.queues import frame_queue, landmark_queue, gesture_queue, response_queue
from core.camera_thread import CameraThread
from core.vision_thread import VisionThread

# ===== SCREEN VISION (Step 7) =====
try:
    from agents.screen_agent import screen_agent
    SCREEN_VISION_AVAILABLE = True
    print("[OK] Screen vision loaded - say 'what's on my screen' to use it!")
except Exception as e:
    SCREEN_VISION_AVAILABLE = False
    print(f"[INFO] Screen vision not available: {e}") 
# ===== STEP 6: WINDOW TRANSPARENCY IMPORTS =====
try: 
    import win32gui      # Access Windows window management
    import win32con      # Windows constants (flags)
    import win32api      # Windows API functions (RGB color conversion)
    WIN32_AVAILABLE = True
    print("[OK] Windows API loaded - Transparency enabled!")
except ImportError:
    WIN32_AVAILABLE = False
    print("[WARNING] pywin32 not installed. Run: pip install pywin32")

# Disable pyautogui's built-in delay (default is 0.1 sec between actions = SLOW!)
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False  # Disable fail-safe (moving mouse to corner won't crash)



#====AI SETUP====
grok_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ===== STEP 6: TRANSPARENCY SETUP FUNCTION =====
def setup_transparent_window(hwnd):
    """
    Makes the Pygame window transparent and always-on-top.
    
    What this does:
    1. Adds WS_EX_LAYERED flag (enables transparency support)
    2. Sets color key transparency (black = invisible)
    3. Makes window always-on-top (stays above all apps)
    """
    if not WIN32_AVAILABLE:
        return
    
    try:
        # Step 1: Get current window style
        current_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        
        # Step 2: Add WS_EX_LAYERED flag (enables transparency)
        new_style = current_style | win32con.WS_EX_LAYERED
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
        
        # Step 3: Set color key transparency (black becomes invisible)
        win32gui.SetLayeredWindowAttributes(
            hwnd,
            win32api.RGB(0, 0, 0),  # Black color = transparent
            0,                      # Alpha value (not used with color key)
            win32con.LWA_COLORKEY   # Use color key mode
        )
        
        # Step 4: Make window always-on-top
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
        
        print("[OK] Window is now transparent and always-on-top!")
    except Exception as e:
        print(f"[WARNING] Transparency setup failed: {e}")

last_ai_response_cache = "I'm having trouble answering that right now."

def ask_ai(question):
    '''Ask the AI a question and get a response'''
    global last_ai_response_cache
    try: 
        response = grok_client.chat.completions.create(
            model = "llama-3.1-8b-instant",
            messages= [
            { "role": "system", "content": "You are HoloDesk, a helpful AI assistant. Keep responses short and conversational (1-2 sentences max)."},
            {"role": "user", "content": question}
            ],
            max_tokens = 100,
        )
        last_ai_response_cache = response.choices[0].message.content
        return last_ai_response_cache
    except Exception as e:
        print(f"AI ERROR: {e}")
        return f"{last_ai_response_cache} I'm having connection issues."



#settings 
WINDOW_WIDTH = 1280 # width of window 
WINDOW_HEIGHT = 720 # height of window 
FPS_CAP = 30  # 30fps — matches camera thread rate, UI has no reason to run faster


# SETUP 
pygame.init()  #  start pygame engine 
pygame.mixer.quit() # disable audio mixer to free microphone. 

# ===== STEP 6: CREATE BORDERLESS WINDOW =====
# pygame.NOFRAME = removes title bar, minimize/maximize buttons, borders
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.NOFRAME)
pygame.display.set_caption("HoloDesk - Step 6: Transparent Overlay")

# ===== STEP 6: GET WINDOW HANDLE (HWND) AND APPLY TRANSPARENCY =====
hwnd = None
if WIN32_AVAILABLE:
    try:
        pygame_window_info = pygame.display.get_wm_info()
        hwnd = pygame_window_info['window']
        print(f"[OK] Window Handle (HWND): {hwnd}")
        setup_transparent_window(hwnd)
    except Exception as e:
        print(f"[WARNING] Could not get window handle: {e}")

clock = pygame.time.Clock()

# ===== START BACKGROUND THREADS =====
# Camera and MediaPipe run on their own threads — main loop never blocks
camera_thread = CameraThread()
vision_thread = VisionThread()
camera_thread.start()
vision_thread.start()
print("[OK] Camera thread started")
print("[OK] Vision thread started")


#------cursor position setup------ 
cursor_x = WINDOW_WIDTH // 2 # starting in the middle of the screen 
cursor_y = WINDOW_HEIGHT // 2 # starting in the middle of the screen 


#-----DRAGGABLE CARD SETUP------ 
card_x = 400 # card starting X position 
card_y = 300 # card starting Y position 
card_width = 200 # card width 
card_height = 150 # card height 
card_color = (255, 0, 0) # red 

# Grab state
is_grabbing = False

# (V-gesture replaced with Call Me gesture 🤙) 

#=============VOICE SETUP==============
recognizer = sr.Recognizer()
mic = None
voice_available = True

try:
    mic = sr.Microphone()
except Exception as e:
    voice_available = False
    print(f"[WARNING] Microphone unavailable: {e}")

#Text-to-Speech engine 
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150) #speed of speech( words per minute)

#whisper model for speech-to-text ( steup - loads once at startup) 
print("Loading Whisper model....please wait...")
whisper_model = WhisperModel("small", device = "cpu", compute_type = "int8")  # "small" is more accurate than "base" 
print("Whisper model loaded successfully!")

# Variable to store last voice command
last_command = ""
voice_ui_state = "IDLE"   # IDLE | WAKE | LISTENING | PROCESSING | SPEAKING | UNAVAILABLE
audio_level = 0.0
last_exchange = ""
followup_context = ""

# ====== Toggle States (Simplified) ======
is_scrolling = False        # When True = continuously scrolling
scroll_direction = 0        # 1 = up, -1 = down, 0 = stopped
v_gesture_cooldown = 0      # Prevents rapid V-gesture triggers (recalibrated for 30fps)
open_palm_cooldown = 0      # Prevents rapid stop triggers (recalibrated for 30fps)
is_ai_speaking = False      # Track if AI is currently talking
is_speaking = False         # Global mic-mute gate while TTS is active
last_speech_end_time = 0.0  # Enforce a short cool-down after TTS
stop_speaking_flag = False  # Signal to stop speech
frame_count = 0             # Frame counter for throttling operations
is_v_gesture_active = False # Track V-gesture state (for UI display)

# ===== SCREEN VISION STATE (Step 7) =====
is_analyzing_screen = False   # True while GPT-4o Vision call is in flight
screen_status_text = ""       # Short status shown on overlay ("Analyzing screen...")
screen_status_timer = 0       # Frames remaining to show screen_status_text

# ===== THREADING STATE (Step 8) =====
latest_landmarks = None   # Most recent hand landmarks from vision thread (or None)
is_pinching = False       # Tracked here; reset when no hand detected

# Thumbs debounce — require 5 consecutive frames to prevent accidental scroll start
thumbs_up_frames   = 0
thumbs_down_frames = 0
THUMBS_REQUIRED_FRAMES = 5

# Global speaker object for interruption support
sapi_speaker = None

#Function to speak using Windows SAPI directly (more reliable than pyttsx3)
def speak(text): 
    global is_ai_speaking, is_speaking, last_speech_end_time, stop_speaking_flag, sapi_speaker
    
    # Check if we should stop before even starting
    if stop_speaking_flag:
        stop_speaking_flag = False
        return
        
    is_ai_speaking = True
    is_speaking = True
    try:
        response_queue.put_nowait({"type": "VOICE_STATE", "state": "SPEAKING"})
    except queue.Full:
        pass
    print(f"SPEAKING: {text}")  # Debug
    try:
        import comtypes.client  # Windows COM interface
        sapi_speaker = comtypes.client.CreateObject("SAPI.SpVoice")
        sapi_speaker.Rate = 1  # Speed: -10 (slow) to 10 (fast)
        sapi_speaker.Volume = 100  # Volume: 0 to 100
        
        # Async speech (1 = SVSFlagsAsync) so we can interrupt
        sapi_speaker.Speak(text, 1)
        
        # Wait for speech to finish, but check stop flag
        while sapi_speaker.Status.RunningState == 2:  # 2 = SRSEIsSpeaking
            if stop_speaking_flag:
                sapi_speaker.Speak("", 2)  # 2 = SVSFPurgeBeforeSpeak (stops speech)
                print("SPEECH INTERRUPTED!")
                break
            time.sleep(0.1)  # Check every 100ms
            
        print("SPEECH DONE")  # Confirm it finished
    except Exception as e:
        print(f"SPEECH ERROR: {e}")
        # Fallback to pyttsx3 if comtypes fails
        try:
            engine = pyttsx3.init('sapi5')  # Force Windows SAPI driver
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 1.0)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            del engine
            print("SPEECH DONE (fallback)")
        except Exception as e2:
            print(f"FALLBACK SPEECH ERROR: {e2}")
    finally:
        is_ai_speaking = False
        is_speaking = False
        last_speech_end_time = time.time()
        stop_speaking_flag = False
        try:
            response_queue.put_nowait({"type": "VOICE_STATE", "state": "IDLE"})
        except queue.Full:
            pass

def stop_ai_speech():
    """Stop the AI from speaking immediately"""
    global stop_speaking_flag
    stop_speaking_flag = True
    print(">>> STOP SPEECH SIGNAL SENT <<<")

class VoiceAssistantThread(threading.Thread):
    FILLER_WORDS = {"um", "uh", "like", "you know"}

    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.force_wake = threading.Event()
        self.redirect_listen = threading.Event()
        self.followup_until = 0
        self.auto_relisten_done = False

    def request_wake(self):
        self.force_wake.set()

    def request_redirect_listen(self):
        self.redirect_listen.set()

    def push_state(self, state, level=None):
        payload = {"type": "VOICE_STATE", "state": state}
        if level is not None:
            payload["level"] = level
        try:
            response_queue.put_nowait(payload)
        except queue.Full:
            pass

    def transcribe_audio(self, wav_path):
        try:
            segments, _ = whisper_model.transcribe(wav_path, beam_size=5, language="en")
            text = " ".join(seg.text for seg in segments).strip().lower()
            return text
        except Exception as e:
            print(f"[WARNING] Whisper failed, fallback STT: {e}")
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            try:
                return recognizer.recognize_google(audio_data).strip().lower()
            except Exception:
                return ""

    def strip_fillers(self, text):
        cleaned = text
        for filler in self.FILLER_WORDS:
            cleaned = cleaned.replace(f" {filler} ", " ")
            if cleaned.startswith(f"{filler} "):
                cleaned = cleaned[len(filler) + 1:]
        return " ".join(cleaned.split())

    def record_with_vad(self, source, max_seconds=15.0):
        chunk_ms = 100
        rate = source.SAMPLE_RATE
        chunk_size = int(rate * (chunk_ms / 1000.0))
        bytes_per_chunk = chunk_size * source.SAMPLE_WIDTH
        silence_chunks_needed = int(1500 / chunk_ms)
        silence_count = 0
        frames = []
        started = False
        start = time.time()
        self.push_state("LISTENING")
        while time.time() - start < max_seconds:
            raw = source.stream.read(chunk_size)
            if len(raw) < bytes_per_chunk:
                continue
            rms = audioop.rms(raw, source.SAMPLE_WIDTH)
            level = min(1.0, rms / 1500.0)
            self.push_state("LISTENING", level=level)
            if rms >= 300:
                started = True
                silence_count = 0
            elif started:
                silence_count += 1
            if started:
                frames.append(raw)
            if started and silence_count >= silence_chunks_needed:
                break
        if not frames:
            return None
        temp_wav = tempfile.mktemp(suffix=".wav")
        with wave.open(temp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(source.SAMPLE_WIDTH)
            wf.setframerate(rate)
            wf.writeframes(b"".join(frames))
        return temp_wav

    def detect_wake_word(self):
        if self.force_wake.is_set():
            self.force_wake.clear()
            return True
        if self.followup_until > time.time():
            return True
        try:
            with mic as source:
                recognizer.energy_threshold = 300
                audio = recognizer.listen(source, timeout=0.8, phrase_time_limit=1.8)
            temp_path = tempfile.mktemp(suffix=".wav")
            try:
                with open(temp_path, "wb") as f:
                    f.write(audio.get_wav_data(convert_rate=16000, convert_width=2))
                text = self.transcribe_audio(temp_path)
                return "hey desk" in text
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception:
            time.sleep(0.2)
            return False

    def run(self):
        if not voice_available or mic is None:
            self.push_state("UNAVAILABLE")
            return
        while self.running:
            if is_speaking or (time.time() - last_speech_end_time) < 0.5:
                self.push_state("IDLE")
                time.sleep(0.05)
                continue
            if self.redirect_listen.is_set():
                self.redirect_listen.clear()
                self.followup_until = time.time() + 3
                self.force_wake.set()
            if not self.detect_wake_word():
                self.push_state("IDLE")
                continue
            self.push_state("WAKE")
            with mic as source:
                wav_path = self.record_with_vad(source, max_seconds=15.0)
            self.push_state("PROCESSING")
            if not wav_path:
                self.push_state("IDLE")
                continue
            try:
                text = self.strip_fillers(self.transcribe_audio(wav_path))
            finally:
                if os.path.exists(wav_path):
                    os.unlink(wav_path)
            if len(text.split()) < 3:
                if not self.auto_relisten_done:
                    self.auto_relisten_done = True
                    try:
                        response_queue.put_nowait({"type": "VOICE_RETRY"})
                    except queue.Full:
                        pass
                    self.followup_until = time.time() + 0.2
                    continue
                self.auto_relisten_done = False
                self.push_state("IDLE")
                continue
            self.auto_relisten_done = False
            try:
                response_queue.put_nowait({"type": "VOICE_COMMAND", "command": text})
            except queue.Full:
                pass
            self.followup_until = time.time() + 4


voice_thread = VoiceAssistantThread()
voice_thread.start()
print("[OK] Voice thread started")


# ===== SCREEN VISION HELPER (Step 7) =====
def analyze_screen(question: str = "What is on this screen? Explain it clearly."):
    """
    Run GPT-4o Vision in a background thread so the UI never freezes.
    Notifies the user before sending (privacy transparency).
    Speaks the result when done.
    """
    global is_analyzing_screen, screen_status_text, screen_status_timer

    if not SCREEN_VISION_AVAILABLE:
        threading.Thread(
            target=speak,
            args=("Screen vision is not set up yet. Add your OpenAI API key to the .env file.",),
            daemon=True
        ).start()
        return

    if is_analyzing_screen:
        return  # Already analyzing — don't stack calls

    def _run():
        global is_analyzing_screen, screen_status_text, screen_status_timer
        is_analyzing_screen = True
        screen_status_text = "Reading screen..."
        screen_status_timer = 300  # Show for ~5 seconds at 60fps

        # Tell the user we're about to capture — privacy transparency
        threading.Thread(
            target=speak,
            args=("Reading your screen now.",),
            daemon=True
        ).start()

        result = screen_agent.execute(question=question)

        if result["success"]:
            response = result["response"]
            screen_status_text = "Done."
            screen_status_timer = 180
        elif result.get("blocked"):
            response = result["response"]
            screen_status_text = "Blocked window."
            screen_status_timer = 180
        else:
            response = result["response"]
            screen_status_text = "Error."
            screen_status_timer = 180

        is_analyzing_screen = False
        # Speak the answer (runs async — UI keeps rendering)
        threading.Thread(target=speak, args=(response,), daemon=True).start()

    threading.Thread(target=_run, daemon=True).start()


#============MAIN LOOP============== 
''' everything happens inside the main loop  
like 60 times per second (FPS_CAP)''' 
running = True 
while running : 
    # 1 Handles events ( like closing the window) 
    # this checks : did the user click the X button to close the window? if yes, stop the loop. 
    for event in pygame.event.get():
        if event.type == pygame.QUIT: 
            running = False 

        # ===== STEP 6: ESC KEY TO EXIT (no title bar = no X button!) =====
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:  # ESC key pressed
                print("ESC pressed - Exiting HoloDesk...")
                running = False

        # 2 Press spacebar to toggle voice command (still works as backup)
        if event.type == pygame.KEYDOWN: 
            if event.key == pygame.K_SPACE:
                voice_thread.request_wake()
    
    # ===== MORNING BRIEFING — speak once on the first frame =====
    if frame_count == 1:
        _briefing = _db.get_pref("pending_briefing")
        if _briefing:
            _db.execute("DELETE FROM preferences WHERE key='pending_briefing'")
            threading.Thread(target=speak, args=(_briefing,), daemon=True).start()
            print(f"[Briefing] Speaking: {_briefing[:80]}...")

    # ===== STEP 8: READ FROM QUEUES (non-blocking — never waits) =====

    # Pull latest hand landmarks from vision thread
    try:
        latest_landmarks = landmark_queue.get_nowait()
    except queue.Empty:
        pass  # Keep last known value — cursor stays in place

    # Process any confirmed gesture events (V_GESTURE / OPEN_PALM)
    try:
        gesture = gesture_queue.get_nowait()

        if gesture == "V_GESTURE" and v_gesture_cooldown <= 0:
            print("[GESTURE] V_GESTURE — starting voice...")
            voice_thread.request_wake()
            v_gesture_cooldown = 45   # 1.5s at 30fps
            is_v_gesture_active = True

        elif gesture == "OPEN_PALM" and open_palm_cooldown <= 0:
            if is_scrolling:
                is_scrolling = False
                scroll_direction = 0
                print("[GESTURE] OPEN_PALM — scrolling stopped")
            if is_ai_speaking:
                stop_ai_speech()
                print("[GESTURE] OPEN_PALM — speech stopped")
                voice_thread.request_redirect_listen()
            open_palm_cooldown = 15   # 0.5s at 30fps

    except queue.Empty:
        pass

    # Voice thread -> main loop events
    while True:
        try:
            voice_event = response_queue.get_nowait()
        except queue.Empty:
            break

        if voice_event.get("type") == "VOICE_COMMAND":
            incoming = voice_event.get("command", "").strip()
            if incoming:
                last_command = incoming
        elif voice_event.get("type") == "VOICE_RETRY":
            threading.Thread(target=speak, args=("I didn't catch that",), daemon=True).start()
            voice_thread.request_wake()
        elif voice_event.get("type") == "VOICE_STATE":
            voice_ui_state = voice_event.get("state", voice_ui_state)
            audio_level = voice_event.get("level", audio_level)

    # ===== CURSOR + PINCH + THUMBS (from latest_landmarks) =====
    # These stay in the main loop — they depend on cursor screen coords,
    # not on debounced gesture detection. PRESERVED from original code.
    if latest_landmarks is not None:
        lm = latest_landmarks.landmark

        # Cursor position from index fingertip (landmark 8)
        # NOTE: CameraThread already flips the frame with cv2.flip(frame, 1)
        # so landmarks are pre-mirrored. Do NOT do (1 - x) — that was the old
        # compensation for an unflipped frame and now reverses the mirror.
        index_tip = lm[8]
        cursor_x = int(index_tip.x * WINDOW_WIDTH)
        cursor_y = int(index_tip.y * WINDOW_HEIGHT)

        # Pinch: distance between thumb tip (4) and index tip (8)
        thumb_tip = lm[4]
        thumb_x = int(thumb_tip.x * WINDOW_WIDTH)
        thumb_y = int(thumb_tip.y * WINDOW_HEIGHT)
        distance = ((cursor_x - thumb_x) ** 2 + (cursor_y - thumb_y) ** 2) ** 0.5
        is_pinching = distance < 50

        # Finger state flags (needed for thumbs up/down detection)
        index_mcp  = lm[5]
        middle_tip = lm[12];  middle_base = lm[9]
        ring_tip   = lm[16];  ring_base   = lm[13]
        pinky_tip  = lm[20];  pinky_base  = lm[17]

        # Thresholds deliberately loose so thumb gestures work without
        # requiring a perfect fist — index/middle just need to be past base
        index_down  = index_tip.y  > index_mcp.y   + 0.02
        middle_down = middle_tip.y > middle_base.y  + 0.02
        ring_down   = ring_tip.y   > ring_base.y    + 0.01
        pinky_down  = pinky_tip.y  > pinky_base.y   + 0.01
        fingers_curled = index_down and middle_down and ring_down and pinky_down

        # ======= THUMBS UP / DOWN — toggle scroll (5-frame debounce) =======
        is_thumbs_up   = thumb_tip.y < index_mcp.y - 0.08 and fingers_curled
        is_thumbs_down = thumb_tip.y > index_mcp.y + 0.08 and fingers_curled

        if is_thumbs_up:
            thumbs_up_frames += 1
            thumbs_down_frames = 0
            if thumbs_up_frames >= THUMBS_REQUIRED_FRAMES and not is_scrolling:
                is_scrolling = True
                scroll_direction = 1
                thumbs_up_frames = 0
                print("[GESTURE] THUMBS UP — scrolling up")
        elif is_thumbs_down:
            thumbs_down_frames += 1
            thumbs_up_frames = 0
            if thumbs_down_frames >= THUMBS_REQUIRED_FRAMES and not is_scrolling:
                is_scrolling = True
                scroll_direction = -1
                thumbs_down_frames = 0
                print("[GESTURE] THUMBS DOWN — scrolling down")
        else:
            thumbs_up_frames = 0
            thumbs_down_frames = 0

        # Perform continuous scroll (every 3rd frame at 30fps ≈ 10 events/sec)
        if is_scrolling and frame_count % 3 == 0:
            pyautogui.scroll(scroll_direction * 200)

        # ======= PINCH / GRAB — drag card (PRESERVED) =======
        cursor_over_card = (card_x < cursor_x < card_x + card_width and
                            card_y < cursor_y < card_y + card_height)
        if is_pinching and cursor_over_card:
            is_grabbing = True
        elif not is_pinching:
            is_grabbing = False
        if is_grabbing:
            card_x = cursor_x - card_width // 2
            card_y = cursor_y - card_height // 2

        # Cooldown timers decrement once per frame
        if v_gesture_cooldown > 0:
            v_gesture_cooldown -= 1
        if open_palm_cooldown > 0:
            open_palm_cooldown -= 1

    else:
        # No hand in frame — release grab, reset all debounce counters
        is_pinching = False
        is_grabbing = False
        is_v_gesture_active = False
        thumbs_up_frames = 0
        thumbs_down_frames = 0
        
    # ==== PROCESS VOICE COMMANDS ==== 
    if last_command:
        print(f"PROCESSING COMMAND: {last_command}")  # Debug
        voice_ui_state = "PROCESSING"
        current_command = last_command
        
        # ===== STOP COMMAND (Stops scrolling) =====
        if last_command == "stop" or "stop scrolling" in last_command or "stop scroll" in last_command:
            if is_scrolling:
                is_scrolling = False
                scroll_direction = 0
                threading.Thread(target=speak, args=("Scrolling stopped!",), daemon=True).start()
            else:
                threading.Thread(target=speak, args=("Nothing to stop.",), daemon=True).start()
        
        elif "reset" in last_command:
            card_x = 400 
            card_y = 300 
            threading.Thread(target=speak, args=("Card reset!",), daemon=True).start()

        elif "color" in last_command or "colour" in last_command:
            # Smart color detection - parse the color from command!
            if "red" in last_command:
                card_color = (255, 0, 0)
            elif "green" in last_command:
                card_color = (0, 255, 0)
            elif "blue" in last_command:
                card_color = (0, 0, 255)
            elif "yellow" in last_command:
                card_color = (255, 255, 0)
            elif "purple" in last_command:
                card_color = (128, 0, 128)
            elif "orange" in last_command:
                card_color = (255, 165, 0)
            elif "white" in last_command:
                card_color = (255, 255, 255)
            elif "black" in last_command:
                card_color = (0, 0, 0)
            elif "pink" in last_command:
                card_color = (255, 105, 180)
            else:
                # Random color if no specific color mentioned
                import random
                card_color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
            threading.Thread(target=speak, args=("Card color changed!",), daemon=True).start()

        elif "hello" in last_command or " hi " in f" {last_command} " or last_command == "hi":
            threading.Thread(target=speak, args=("Hello! How can I help you today?",), daemon=True).start()
        elif "bye" in last_command or "goodbye" in last_command:
            threading.Thread(target=speak, args=("Goodbye! Have a great day!",), daemon=True).start()
        elif "thank you" in last_command or "thanks" in last_command:
            threading.Thread(target=speak, args=("You're welcome!",),daemon=True).start()
        elif "help" in last_command:
            threading.Thread(target=speak, args=("I can help you with any questions you have. I can also open desktop apps or webpages like Facebook, YouTube, or Netflix. Just ask me anything!",), daemon=True).start()
        
        #==== SCROLL COMMAND ==== (with spelling variations for Whisper mishearing)
        elif "scroll up" in last_command or "scrawl up" in last_command or "screw up" in last_command or "scroll all up" in last_command:
            if "lot" in last_command or "more" in last_command:
                pyautogui.scroll(1000)  # HUGE scroll
            else:
                pyautogui.scroll(500)  # Normal scroll - BIG!
            threading.Thread(target=speak, args=("Scrolling up!",), daemon=True).start()
        
        elif "scroll down" in last_command or "scrawl down" in last_command or "screw down" in last_command or "scroll all down" in last_command or "screw all down" in last_command or "screw it down" in last_command:
            if "lot" in last_command or "more" in last_command:
                pyautogui.scroll(-1000)  # HUGE scroll
            else:
                pyautogui.scroll(-500)  # Normal scroll - BIG!
            threading.Thread(target=speak, args=("Scrolling down!",), daemon=True).start()

        #==== APP COMMANDS ==== 
        elif "open chrome" in last_command:
            import subprocess
            subprocess.Popen('start chrome', shell=True)
            threading.Thread(target=speak, args=("Opening Chrome...",), daemon=True).start()

        elif "open facebook" in last_command or "facebook" in last_command and "open" in last_command:
            import subprocess
            subprocess.Popen('start chrome https://facebook.com', shell=True)
            threading.Thread(target=speak, args=("Opening Facebook...",), daemon=True).start()

        elif "open youtube" in last_command or "youtube" in last_command and "open" in last_command:
            import subprocess
            subprocess.Popen('start chrome https://youtube.com', shell=True)
            threading.Thread(target=speak, args=("Opening YouTube...",), daemon=True).start()

        elif "open netflix" in last_command or "netflix" in last_command and "open" in last_command:
            import subprocess
            subprocess.Popen('start chrome https://netflix.com', shell=True)
            threading.Thread(target=speak, args=("Opening Netflix...",), daemon=True).start()

        elif "open notepad" in last_command:
            import subprocess
            subprocess.Popen('start notepad', shell=True)
            threading.Thread(target=speak, args=("Opening Notepad...",), daemon=True).start()

        elif "open notepad++" in last_command:
            import subprocess
            subprocess.Popen('start notepad++', shell=True)
            threading.Thread(target=speak, args=("Opening Notepad++...",), daemon=True).start()

        elif "close" in last_command and ("window" in last_command or "app" in last_command or "this" in last_command):
            pyautogui.hotkey('alt', 'F4')
            threading.Thread(target=speak, args=("Closing window...",), daemon=True).start()

        elif "minimize" in last_command:
            pyautogui.hotkey('win', 'm')  # minimize current window
            threading.Thread(target=speak, args=("Minimizing window...",), daemon=True).start()

        elif "open" in last_command:
            # Extract app name from command
            # "open chrome" → "chrome"
            # "open notepad" → "notepad"
            words = last_command.split()
            if "open" in words:
                app_index = words.index("open") + 1
                if app_index < len(words):
                    app_name = words[app_index]
                    try:
                        import subprocess
                        subprocess.Popen(f'start {app_name}', shell=True)
                        threading.Thread(target=speak, args=(f"Opening {app_name}",), daemon=True).start()
                    except:
                        threading.Thread(target=speak, args=(f"Sorry, I couldn't open {app_name}",), daemon=True).start()

        # ===== SCREEN VISION COMMANDS (Step 7) =====
        elif any(kw in last_command for kw in [
            "what's on my screen", "whats on my screen",
            "what is on my screen", "read my screen", "read the screen",
            "explain this", "explain my screen", "what do you see",
            "analyze screen", "analyse screen", "screen analysis",
            "what is this", "explain what's on screen",
        ]):
            analyze_screen(question=last_command if len(last_command) > 10 else
                           "What is on this screen? Explain it clearly.")

        elif any(kw in last_command for kw in [
            "explain this error", "what's this error", "whats this error",
            "what is this error", "debug this", "what went wrong",
        ]):
            analyze_screen(
                question="There is an error or bug on this screen. "
                         "What is it, what caused it, and how do I fix it? "
                         "Be specific and concise."
            )

        elif any(kw in last_command for kw in [
            "explain this code", "what does this code do",
            "explain the code", "what is this code",
        ]):
            analyze_screen(
                question="Explain what this code does in plain English. "
                         "Focus on purpose, not syntax. Two sentences max."
            )

        else: 
            #If no specific command, ask AI 
            prompt = current_command
            if followup_context:
                prompt = f"Previous exchange: {followup_context}\nUser follow-up: {current_command}"
            ai_response = ask_ai(prompt)
            threading.Thread(target=speak, args=(ai_response,), daemon=True).start()
            followup_context = f"user: {current_command}\nassistant: {ai_response}"
            last_exchange = followup_context
        last_command = "" 



    # ===== STEP 6: DON'T DRAW WEBCAM (process in background only) =====
    # We still process the frame for hand tracking above, but don't display it!
    # Black fill becomes transparent (color key mode)
    screen.fill((0, 0, 0))  # Fill entire screen with black (transparent)

    # ===== STEP 6: CUSTOM UI ELEMENTS (ONLY VISIBLE PARTS) =====
    
    # Hand detected = vision thread sent us real landmarks (not None)
    hand_detected = latest_landmarks is not None
    
    # ===== 1. GLOWING CURSOR (when hand detected) =====
    if hand_detected:
        # Draw multiple circles for "glow" effect (makes cursor visible on any background)
        pygame.draw.circle(screen, (100, 200, 255), (cursor_x, cursor_y), 25)      # Outer glow (light blue)
        pygame.draw.circle(screen, (0, 150, 255), (cursor_x, cursor_y), 18, 3)     # Middle ring (blue)
        pygame.draw.circle(screen, (255, 255, 255), (cursor_x, cursor_y), 8)       # Center dot (white)
    
    # ===== 2. GESTURE INDICATORS (top-right corner) =====
    status_font = pygame.font.Font(None, 32)
    status_y = 10
    
    if is_scrolling:
        if scroll_direction > 0:
            gesture_text = status_font.render("👍 SCROLLING UP", True, (0, 255, 100))  # Green
        else:
            gesture_text = status_font.render("👎 SCROLLING DOWN", True, (255, 100, 100))  # Red
        screen.blit(gesture_text, (WINDOW_WIDTH - 280, status_y))
        status_y += 30
    
    if is_v_gesture_active and voice_ui_state in ("WAKE", "LISTENING", "PROCESSING"):
        gesture_text = status_font.render("✌️ VOICE ACTIVE", True, (255, 255, 0))  # Yellow
        screen.blit(gesture_text, (WINDOW_WIDTH - 250, status_y))
        status_y += 30
    
    # ===== 3. VOICE OVERLAY STATE =====
    overlay_font = pygame.font.Font(None, 48)
    small_overlay_font = pygame.font.Font(None, 30)
    pulse = abs((frame_count % 40) - 20) / 20
    mic_color = (120, 120, 120) if voice_ui_state == "IDLE" else (0, 200 + int(55 * pulse), 0)
    pygame.draw.circle(screen, mic_color, (80, WINDOW_HEIGHT - 80), 22, 3)

    if voice_ui_state in ("WAKE", "LISTENING"):
        listening_text = overlay_font.render("Listening...", True, (0, 255, 0))
        screen.blit(listening_text, listening_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)))
        bar_w = int(220 * max(0.1, audio_level))
        pygame.draw.rect(screen, (0, 255, 120), (WINDOW_WIDTH // 2 - 110, WINDOW_HEIGHT // 2 + 35, bar_w, 12), border_radius=6)
    elif voice_ui_state == "PROCESSING":
        thinking = overlay_font.render("Thinking...", True, (120, 220, 255))
        screen.blit(thinking, thinking.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)))
        pygame.draw.circle(screen, (120, 220, 255), (WINDOW_WIDTH // 2 + 110, WINDOW_HEIGHT // 2), 8 + int(8 * pulse))
    elif voice_ui_state == "SPEAKING":
        speaking = small_overlay_font.render("HoloDesk speaking... (Palm to stop)", True, (255, 120, 255))
        screen.blit(speaking, (WINDOW_WIDTH - 390, WINDOW_HEIGHT - 40))
    elif voice_ui_state == "UNAVAILABLE":
        unavailable = overlay_font.render("Voice unavailable", True, (255, 120, 120))
        screen.blit(unavailable, unavailable.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)))

    # ===== 4. SCREEN VISION STATUS (Step 7) =====
    if screen_status_timer > 0:
        screen_status_timer -= 1
        sv_font = pygame.font.Font(None, 30)
        if is_analyzing_screen:
            # Pulsing cyan while GPT-4o is thinking
            pulse = abs((frame_count % 60) - 30) / 30  # 0.0 to 1.0
            r = int(0 + 100 * pulse)
            sv_color = (r, 220, 255)
        else:
            sv_color = (100, 255, 180)  # Green when done
        sv_text = sv_font.render(f"[Vision] {screen_status_text}", True, sv_color)
        screen.blit(sv_text, (10, WINDOW_HEIGHT - 65))
    
    # ===== 5. STATUS DOT (bottom-left: green = working, red = no hand) =====
    status_dot_color = (0, 255, 0) if hand_detected else (255, 0, 0)  # Green or red
    pygame.draw.circle(screen, status_dot_color, (20, WINDOW_HEIGHT - 20), 8)
    
    # ===== 6. FPS COUNTER (optional, top-left, small) =====
    fps = clock.get_fps()
    small_font = pygame.font.Font(None, 24)
    fps_text = small_font.render(f"FPS: {int(fps)}", True, (150, 150, 150))  # Gray
    screen.blit(fps_text, (10, 10))
    
    # ===== 7. ESC KEY HINT (bottom-right) =====
    hint_font = pygame.font.Font(None, 20)
    esc_hint = hint_font.render("Press ESC to exit", True, (100, 100, 100))  # Dark gray
    screen.blit(esc_hint, (WINDOW_WIDTH - 150, WINDOW_HEIGHT - 25)) 

    # ===== STEP 6: RE-ASSERT ALWAYS-ON-TOP (every 60 frames = once per second) =====
    # Windows might try to remove always-on-top when other apps request focus
    # So we re-apply it periodically to ensure it stays on top!
    if WIN32_AVAILABLE and hwnd and frame_count % 60 == 0:
        try:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
        except Exception:
            pass  # Silently fail if window handle is invalid

    #8. Update display
    pygame.display.flip() # update the display to show the new frame
    clock.tick(FPS_CAP)
    frame_count += 1  # Increment frame counter

# ==============CLEAN UP==============
voice_thread.running = False
camera_thread.stop()
vision_thread.stop()
pygame.quit()
