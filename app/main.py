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
from core.queues import frame_queue, landmark_queue, gesture_queue
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

def ask_ai(question):
    '''Ask the AI a question and get a response'''
    try: 
        response = grok_client.chat.completions.create(
            model = "llama-3.1-8b-instant",
            messages= [
            { "role": "system", "content": "You are HoloDesk, a helpful AI assistant. Keep responses short and conversational (1-2 sentences max)."},
            {"role": "user", "content": question}
            ],
            max_tokens = 100,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI ERROR: {e}")
        return "I'm having trouble answering that. Please try again."



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
mic = sr.Microphone()

#Text-to-Speech engine 
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150) #speed of speech( words per minute)

#whisper model for speech-to-text ( steup - loads once at startup) 
print("Loading Whisper model....please wait...")
whisper_model = WhisperModel("small", device = "cpu", compute_type = "int8")  # "small" is more accurate than "base" 
print("Whisper model loaded successfully!")

#Variable to store last voice command 
last_command = ""
is_listening = False
ready_to_speak = False  # Shows "SPEAK NOW!" on screen

# ====== Toggle States (Simplified) ======
is_scrolling = False        # When True = continuously scrolling
scroll_direction = 0        # 1 = up, -1 = down, 0 = stopped
v_gesture_cooldown = 0      # Prevents rapid V-gesture triggers (recalibrated for 30fps)
open_palm_cooldown = 0      # Prevents rapid stop triggers (recalibrated for 30fps)
is_ai_speaking = False      # Track if AI is currently talking
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
    global is_ai_speaking, stop_speaking_flag, sapi_speaker
    
    # Check if we should stop before even starting
    if stop_speaking_flag:
        stop_speaking_flag = False
        return
        
    is_ai_speaking = True
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
        stop_speaking_flag = False

def stop_ai_speech():
    """Stop the AI from speaking immediately"""
    global stop_speaking_flag
    stop_speaking_flag = True
    print(">>> STOP SPEECH SIGNAL SENT <<<")

#Function to listen for voice commands ( runs in the background)
# Single activation: V-gesture → listen → process → auto OFF
def listen_for_command():
    global last_command, is_listening, ready_to_speak

    is_listening = True
    ready_to_speak = False
    print("Adjusting for noise...")
    
    with mic as source: 
        recognizer.adjust_for_ambient_noise(source, duration=0.5)  # Longer calibration
        recognizer.energy_threshold = 300  # Lower threshold for quieter speech
        ready_to_speak = True  # NOW the user can speak
        print(">>> NOW SPEAK! <<<")  # Clear signal to speak
    
        try: 
            # timeout=5: wait 5 sec max for speech to start
            # phrase_time_limit=5: max 5 sec of speech (shorter for commands)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

            # save audio to temporary WAV file for whisper 
            temp_path = tempfile.mktemp(suffix=".wav")
            with open(temp_path, "wb") as f:
                # Convert to 16kHz sample rate for Whisper
                f.write(audio.get_wav_data(convert_rate=16000, convert_width=2))

            # transcribe audio using whisper (force English language)
            segments, info = whisper_model.transcribe(
                temp_path, 
                beam_size=5,
                language="en"  # Force English to avoid hallucinations
            )
            command = ""
            for segment in segments: 
                command += segment.text
            command = command.strip().lower() 

            if command: 
                print(f"You said: {command}")
                last_command = command
            else: 
                print(" No speech detected ")
            
        except sr.WaitTimeoutError:
            print("No voice input detected")
        except Exception as e:
            print(f"Error : {e}")
        finally: 
            is_listening = False 
            ready_to_speak = False
            # Mic automatically turns OFF after processing - use V gesture to listen again! 


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
            if event.key == pygame.K_SPACE and not is_listening:
                # start listening in background thread 
                threading.Thread(target=listen_for_command, daemon=True).start()
    
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

        if gesture == "V_GESTURE" and not is_listening and v_gesture_cooldown <= 0:
            print("[GESTURE] V_GESTURE — starting voice...")
            threading.Thread(target=listen_for_command, daemon=True).start()
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
            open_palm_cooldown = 15   # 0.5s at 30fps

    except queue.Empty:
        pass

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
            if thumbs_up_frames >= THUMBS_REQUIRED_FRAMES and not is_listening and not is_scrolling:
                is_scrolling = True
                scroll_direction = 1
                thumbs_up_frames = 0
                print("[GESTURE] THUMBS UP — scrolling up")
        elif is_thumbs_down:
            thumbs_down_frames += 1
            thumbs_up_frames = 0
            if thumbs_down_frames >= THUMBS_REQUIRED_FRAMES and not is_listening and not is_scrolling:
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
            ai_response = ask_ai( last_command )
            threading.Thread(target=speak, args=(ai_response,), daemon=True).start()
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
    
    if is_v_gesture_active and is_listening:
        gesture_text = status_font.render("✌️ VOICE ACTIVE", True, (255, 255, 0))  # Yellow
        screen.blit(gesture_text, (WINDOW_WIDTH - 250, status_y))
        status_y += 30
    
    # ===== 3. VOICE LISTENING INDICATOR (center of screen) =====
    if is_listening:
        if ready_to_speak:
            # Big pulsing "SPEAK NOW!" when ready
            big_font = pygame.font.Font(None, 80)
            speak_text = big_font.render(">>> SPEAK NOW! <<<", True, (0, 255, 0))  # Green
            # Center it on screen
            text_rect = speak_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            screen.blit(speak_text, text_rect)
        else:
            # Yellow "Preparing mic..." while adjusting for noise
            prep_font = pygame.font.Font(None, 48)
            listening_text = prep_font.render("Preparing mic...", True, (255, 255, 0))  # Yellow
            text_rect = listening_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            screen.blit(listening_text, text_rect)
    
    # ===== 4. AI SPEAKING INDICATOR =====
    if is_ai_speaking:
        ai_font = pygame.font.Font(None, 28)
        ai_status = ai_font.render("AI Speaking... (Palm=Stop)", True, (255, 100, 255))  # Pink
        screen.blit(ai_status, (WINDOW_WIDTH - 300, WINDOW_HEIGHT - 40))

    # ===== 4b. SCREEN VISION STATUS (Step 7) =====
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
camera_thread.stop()
vision_thread.stop()
pygame.quit()




