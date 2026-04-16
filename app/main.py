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
import re

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
from core.queues import (
    frame_queue,
    landmark_queue,
    gesture_queue,
    response_queue,
    command_queue,
    voice_reply_queue,
)
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
            { "role": "system", "content": "You are HoloDesk, a helpful AI assistant on the user's Windows desktop. Keep responses short and conversational (2-3 sentences max). Always end with a brief, natural follow-up like 'Want to know more?' or 'Need help with anything else?' — vary it each time."},
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

# Optional Moonshine STT fallback (requires model download/config)
ENABLE_MOONSHINE_FALLBACK = os.getenv("ENABLE_MOONSHINE_FALLBACK", "0").strip() == "1"
MOONSHINE_MODEL_PATH = os.getenv("MOONSHINE_MODEL_PATH", "").strip()
MOONSHINE_MODEL_ARCH = os.getenv("MOONSHINE_MODEL_ARCH", "").strip()
_moonshine_transcriber = None

voice_ui_state = "IDLE"   # IDLE | WAKE | LISTENING | PROCESSING | SPEAKING | UNAVAILABLE
audio_level = 0.0
last_exchange = ""
followup_context = ""
tts_active = threading.Event()
# Main loop puts the response TEXT here after processing a voice command.
# Orchestrator + Agents
from agents.orchestrator import OrchestratorAgent
from agents.task_agent import TaskAgent
from agents.chat_agent import ChatAgent
from agents.memory_agent import MemoryAgent

# Instantiate agents (singletons for the app lifetime)
memory_agent = MemoryAgent()
chat_agent = ChatAgent()
task_agent = TaskAgent(screen_agent=screen_agent if SCREEN_VISION_AVAILABLE else None)

orchestrator = OrchestratorAgent(agents={
    "screen_agent": screen_agent if SCREEN_VISION_AVAILABLE else None,
    "task_agent": task_agent,
    "memory_agent": memory_agent,
    "chat_agent": chat_agent,
})
orchestrator.start()

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
    
    if stop_speaking_flag:
        stop_speaking_flag = False
        return
        
    is_ai_speaking = True
    tts_active.set()
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
        time.sleep(0.8)
        tts_active.clear()
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
    """
    Sequential state machine — the production pattern used by every working
    voice assistant. The mic and TTS are in the SAME thread, so they can
    never overlap. No flags, no events, no race conditions.

    Flow per iteration:
        detect_wake_word → record_with_vad → transcribe → dispatch →
        BLOCK on voice_reply_queue.get() → speak() → set followup → loop
    """

    FILLER_WORDS = {"um", "uh", "like", "you know"}

    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.force_wake = threading.Event()
        self._last_ai_response = ""

    def request_wake(self):
        self.force_wake.set()

    def request_redirect_listen(self):
        pass

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
            segments, _ = whisper_model.transcribe(
                wav_path,
                beam_size=5,
                language="en",
                temperature=0.0,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                compression_ratio_threshold=2.4,
            )
            seg_list = list(segments)
            if seg_list:
                avg_logprob = sum(getattr(seg, "avg_logprob", -10.0) for seg in seg_list) / len(seg_list)
                if avg_logprob < -1.0:
                    # low confidence: optionally try Moonshine fallback before giving up
                    if ENABLE_MOONSHINE_FALLBACK:
                        ms = self._moonshine_transcribe(wav_path)
                        if ms:
                            return self._normalize_transcript(ms)
                    return ""
            text = " ".join(seg.text for seg in seg_list).strip().lower()
            text = self._normalize_transcript(text)
            # If confidence is weak and transcript is long/fluently garbage-y, treat as non-speech
            if seg_list:
                avg_logprob = sum(getattr(seg, "avg_logprob", -10.0) for seg in seg_list) / len(seg_list)
                if avg_logprob < -0.6 and len(text.split()) >= 8:
                    return ""
            return text
        except Exception as e:
            print(f"[WARNING] Whisper failed, fallback STT: {e}")
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            try:
                return self._normalize_transcript(recognizer.recognize_google(audio_data).strip().lower())
            except Exception:
                if ENABLE_MOONSHINE_FALLBACK:
                    ms = self._moonshine_transcribe(wav_path)
                    if ms:
                        return self._normalize_transcript(ms)
                return ""

    @staticmethod
    def _normalize_transcript(text: str) -> str:
        t = (text or "").lower().strip()
        if not t:
            return ""
        # collapse punctuation to spaces
        t = re.sub(r"[^a-z0-9\s'.:-]+", " ", t)
        # collapse repeated whitespace
        t = re.sub(r"\s+", " ", t).strip()
        # remove immediate duplicate words: "can you can you" -> "can you"
        parts = t.split()
        out = []
        for w in parts:
            if out and out[-1] == w:
                continue
            out.append(w)
        return " ".join(out)

    def _moonshine_transcribe(self, wav_path: str) -> str:
        """
        Moonshine fallback transcription.
        Requires:
          ENABLE_MOONSHINE_FALLBACK=1
          MOONSHINE_MODEL_PATH=<downloaded path>
          MOONSHINE_MODEL_ARCH=<arch number or constant>
        """
        global _moonshine_transcriber
        if not ENABLE_MOONSHINE_FALLBACK:
            return ""
        if not MOONSHINE_MODEL_PATH or not MOONSHINE_MODEL_ARCH:
            return ""
        try:
            from moonshine_voice import Transcriber, load_wav_file
        except Exception:
            return ""
        try:
            if _moonshine_transcriber is None:
                # model_arch is an integer in Moonshine CLI output; keep as int when possible
                try:
                    model_arch = int(MOONSHINE_MODEL_ARCH)
                except Exception:
                    model_arch = MOONSHINE_MODEL_ARCH
                _moonshine_transcriber = Transcriber(model_path=MOONSHINE_MODEL_PATH, model_arch=model_arch)

            audio_data, sample_rate = load_wav_file(wav_path)
            transcript = _moonshine_transcriber.transcribe_without_streaming(audio_data, sample_rate)

            # Try common shapes: transcript.lines[*].text OR transcript.get_text()
            if hasattr(transcript, "get_text"):
                return (transcript.get_text() or "").strip()
            if hasattr(transcript, "lines"):
                texts = []
                for line in transcript.lines:
                    txt = getattr(line, "text", "") or ""
                    if txt.strip():
                        texts.append(txt.strip())
                return " ".join(texts).strip()
            return ""
        except Exception:
            return ""

    def strip_fillers(self, text):
        cleaned = text
        for filler in self.FILLER_WORDS:
            cleaned = cleaned.replace(f" {filler} ", " ")
            if cleaned.startswith(f"{filler} "):
                cleaned = cleaned[len(filler) + 1:]
        return " ".join(cleaned.split())

    def record_with_vad(self, source, max_seconds=15.0, silence_ms=1500):
        chunk_ms = 100
        rate = source.SAMPLE_RATE
        chunk_size = int(rate * (chunk_ms / 1000.0))
        bytes_per_chunk = chunk_size * source.SAMPLE_WIDTH
        silence_chunks_needed = int(silence_ms / chunk_ms)
        silence_count = 0
        frames = []
        started = False
        started_at = None
        rms_sum = 0
        rms_n = 0
        start = time.time()
        self.push_state("LISTENING")
        wait_for_speech_timeout = 10.0
        start_threshold = 420  # raise to avoid breath/click false-starts
        while time.time() - start < max_seconds:
            elapsed = time.time() - start
            if not started and elapsed > wait_for_speech_timeout:
                break
            raw = source.stream.read(chunk_size)
            if len(raw) < bytes_per_chunk:
                continue
            rms = audioop.rms(raw, source.SAMPLE_WIDTH)
            level = min(1.0, rms / 1500.0)
            self.push_state("LISTENING", level=level)
            if rms >= start_threshold:
                started = True
                if started_at is None:
                    started_at = time.time()
                silence_count = 0
            elif started:
                silence_count += 1
            if started:
                frames.append(raw)
                rms_sum += rms
                rms_n += 1
            if started and silence_count >= silence_chunks_needed:
                break
        if not frames:
            return None
        # False-start guard: if we only captured a tiny blip, do not transcribe (prevents hallucinations)
        captured_seconds = (len(frames) * chunk_ms) / 1000.0
        avg_rms = (rms_sum / rms_n) if rms_n else 0
        if captured_seconds < 0.6 and avg_rms < (start_threshold + 80):
            return None
        temp_wav = tempfile.mktemp(suffix=".wav")
        with wave.open(temp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(source.SAMPLE_WIDTH)
            wf.setframerate(rate)
            wf.writeframes(b"".join(frames))
        return temp_wav

    def detect_wake_word(self, _unused=0):
        if self.force_wake.is_set():
            self.force_wake.clear()
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

    EXIT_PHRASES_EXACT = {
        "no", "nah", "nope", "nothing", "bye", "goodbye", "bye bye",
        "no thanks", "no thank you", "that's all", "that's it",
        "nevermind", "never mind", "i'm good", "all good", "i'm done",
    }
    EXIT_KEYWORDS = [
        "that's all", "that's it", "bye", "goodbye", "i'm done",
        "have a good day", "have a nice day", "good night",
        "thank you", "thanks", "see you later", "see you",
        "talk to you later", "take care",
    ]

    CONVERSATION_WINDOW_SEC = 30
    FOLLOWUP_LISTEN_SEC = 45.0
    FOLLOWUP_SILENCE_MS = 5000

    def _is_echo_of_ai(self, text):
        """Detect if transcribed text is actually the AI's own speech (echo)."""
        if not self._last_ai_response:
            return False
        t = text.lower().strip()
        ai = self._last_ai_response.lower()
        words = t.split()
        if len(words) < 3:
            return False
        # Check if a 3+ word phrase from the transcription appears in AI's last response
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            if phrase in ai:
                print(f"[VOICE] Echo detected — discarding: '{t[:50]}...'")
                return True
        return False

    def _is_exit_phrase(self, text):
        t = text.lower().strip().rstrip(".!?,")
        if t in self.EXIT_PHRASES_EXACT:
            return True
        return any(kw in t for kw in self.EXIT_KEYWORDS)

    def _dispatch_and_speak(self, text):
        """Send command to main loop, wait for reply, speak it.
        Returns the reply dict or None on failure."""
        try:
            command_queue.put_nowait({"type": "USER_COMMAND", "text": text, "source": "voice", "ts": time.time()})
        except queue.Full:
            return None

        print(f"[VOICE] Dispatched: '{text}' — waiting for response...")
        try:
            reply = voice_reply_queue.get(timeout=60)
        except queue.Empty:
            print("[VOICE] Timeout waiting for reply")
            return None

        if reply is None or (isinstance(reply, dict) and reply.get("text") is None):
            return None

        reply_text = reply["text"] if isinstance(reply, dict) else reply

        print(f"[VOICE] Speaking: {reply_text[:60]}...")
        self._last_ai_response = reply_text
        speak(reply_text)
        time.sleep(1.5)
        print("[VOICE] Speech done — mic safe")
        return reply

    def run(self):
        if not voice_available or mic is None:
            self.push_state("UNAVAILABLE")
            return

        while self.running:
            try:
                # --- STATE: IDLE / WAKE DETECTION ---
                if not self.detect_wake_word(0):
                    self.push_state("IDLE")
                    continue

                # --- STATE: LISTENING (record user speech) ---
                self.push_state("WAKE")
                with mic as source:
                    wav_path = self.record_with_vad(source, max_seconds=45.0, silence_ms=5000)

                # --- STATE: PROCESSING (transcribe) ---
                self.push_state("PROCESSING")
                if not wav_path:
                    self.push_state("IDLE")
                    continue
                try:
                    text = self.strip_fillers(self.transcribe_audio(wav_path))
                finally:
                    if os.path.exists(wav_path):
                        os.unlink(wav_path)

                if not text or len(text.split()) < 2:
                    self.push_state("IDLE")
                    continue

                # --- DISPATCH, SPEAK, then CONVERSATION WINDOW ---
                result = self._dispatch_and_speak(text)
                if result is None:
                    self.push_state("IDLE")
                    continue

                # --- 15-SECOND CONVERSATION WINDOW ---
                # Loop listening for follow-ups. Each record_with_vad call
                # listens for up to 5s. If the user stays silent for the
                # full 15s window, conversation ends naturally.
                conversation_end = time.time() + self.CONVERSATION_WINDOW_SEC
                while time.time() < conversation_end and self.running:
                    self.push_state("IDLE")
                    with mic as source:
                        followup_wav = self.record_with_vad(
                            source,
                            max_seconds=self.FOLLOWUP_LISTEN_SEC,
                            silence_ms=self.FOLLOWUP_SILENCE_MS,
                        )

                    if not followup_wav:
                        continue

                    self.push_state("PROCESSING")
                    try:
                        followup_text = self.strip_fillers(
                            self.transcribe_audio(followup_wav)
                        )
                    finally:
                        if os.path.exists(followup_wav):
                            os.unlink(followup_wav)

                    if not followup_text:
                        continue

                    print(f"[VOICE] Follow-up heard: '{followup_text}'")

                    if self._is_exit_phrase(followup_text):
                        speak("Alright, I'm here if you need me.")
                        break

                    if len(followup_text.split()) < 2:
                        continue

                    if self._is_echo_of_ai(followup_text):
                        continue

                    result = self._dispatch_and_speak(followup_text)
                    if result is None:
                        break
                    # Reset the window — each exchange gets another 15s
                    conversation_end = time.time() + self.CONVERSATION_WINDOW_SEC

                self.push_state("IDLE")

            except Exception as e:
                print(f"[VOICE] Error in voice loop (recovering): {e}")
                self.push_state("IDLE")
                time.sleep(0.5)


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
            open_palm_cooldown = 15   # 0.5s at 30fps

    except queue.Empty:
        pass

    # Voice thread / background threads -> main loop events
    while True:
        try:
            voice_event = response_queue.get_nowait()
        except queue.Empty:
            break

        if voice_event.get("type") == "VOICE_RETRY":
            voice_reply_queue.put({"text": "I didn't catch that", "prompt": False})
            voice_thread.request_wake()
        elif voice_event.get("type") == "VOICE_STATE":
            voice_ui_state = voice_event.get("state", voice_ui_state)
            audio_level = voice_event.get("level", audio_level)
        elif voice_event.get("type") == "TIMER_DONE":
            # Deliver timer completion into the voice thread's request/response channel.
            try:
                voice_reply_queue.put_nowait({"text": voice_event.get("text", "Timer done."), "prompt": False})
            except queue.Full:
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
        
    # Voice commands are routed through OrchestratorAgent via command_queue.



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
