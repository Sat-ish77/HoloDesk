import pygame #window + drawing
import os 
from dotenv import load_dotenv
#load api key from .env file 
load_dotenv() 
from groq import Groq
import cv2  #webcam 
import time 
import mediapipe as mp
import speech_recognition as sr
import pyttsx3
import threading 
from faster_whisper import WhisperModel
import tempfile 
import wave 
import pyautogui 
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
FPS_CAP = 60 # frames per second 


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

clock = pygame.time.Clock()  # controls timing 
cap = cv2.VideoCapture(0) # open webcam ( 0= default camera)


# reduce webcam resolution to speed up processing 
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640) 
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480) 


#-----------HAND TRACKING SETUP------------ 
mp_hands = mp.solutions.hands.Hands(
    static_image_mode=False,  #False= video mode ( faster ) 
    max_num_hands=1, #only track one hand 
    min_detection_confidence=0.5, # confidence threshold for hand detection
    min_tracking_confidence = 0.5 # confidence threshold for hand tracking 

)
mp_draw = mp.solutions.drawing_utils # for drawing hand skeleton


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
v_gesture_cooldown = 0      # Prevents rapid V-gesture triggers
open_palm_cooldown = 0      # Prevents rapid stop triggers
is_ai_speaking = False      # Track if AI is currently talking
stop_speaking_flag = False  # Signal to stop speech
frame_count = 0             # Frame counter for throttling operations
is_v_gesture_active = False # Track V-gesture state (for UI display)

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
    
    #2. Read webcam frame (this is where the webcam image is read)
    success, frame = cap.read()
    if not success: 
        continue 

    #3. Convert frame for pygame 
    #opencv uses BGR (blue, green, red) but pygame uses RGB (red, green, blue) - so we flip the colors. 
    frame= cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 

    #-------------HAND TRACKING------------- 
    #process the frame to find hands 
    results = mp_hands.process(frame)

    # if a hand is detected 
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            #get index finger tip ( landmark 8)
            index_tip = hand_landmarks.landmark[8]

            #convert from 0-1 range to screen coordinates
            cursor_x = int((1 - index_tip.x) * WINDOW_WIDTH) 
            cursor_y = int(index_tip.y * WINDOW_HEIGHT)

            # Detect pinch gesture (thumb and index finger distance)
            thumb_tip = hand_landmarks.landmark[4]
            thumb_x = int((1 - thumb_tip.x) * WINDOW_WIDTH)
            thumb_y = int(thumb_tip.y * WINDOW_HEIGHT)

            # Calculate the distance between the thumb and index finger 
            distance = ((cursor_x - thumb_x) ** 2 + (cursor_y - thumb_y) ** 2) ** 0.5 

            # If distance is small = pinching gesture
            pinch_threshold = 50  # pixels 
            is_pinching = distance < pinch_threshold 

            # ======= Finger Landmarks (used for all gestures) ======= 
            middle_tip = hand_landmarks.landmark[12]   # middle finger tip 
            middle_base = hand_landmarks.landmark[9]   # middle finger base
            ring_tip = hand_landmarks.landmark[16]     # ring finger tip
            ring_base = hand_landmarks.landmark[13]    # ring finger base
            pinky_tip = hand_landmarks.landmark[20]    # pinky finger tip
            pinky_base = hand_landmarks.landmark[17]   # pinky finger base
            index_mcp = hand_landmarks.landmark[5]     # index finger knuckle
            
            # ======= Check which fingers are UP or DOWN =======
            # STRICT thresholds to avoid false triggers!
            index_up = index_tip.y < index_mcp.y - 0.08      # index CLEARLY up
            middle_up = middle_tip.y < middle_base.y - 0.08  # middle CLEARLY up
            ring_up = ring_tip.y < ring_base.y               # ring up?
            pinky_up = pinky_tip.y < pinky_base.y            # pinky up?
            thumb_out = abs(thumb_tip.x - index_mcp.x) > 0.1  # thumb sticking out sideways?
            
            index_down = index_tip.y > index_mcp.y + 0.05    # index CLEARLY curled
            middle_down = middle_tip.y > middle_base.y + 0.05  # middle CLEARLY curled
            ring_down = ring_tip.y > ring_base.y + 0.03      # ring curled
            pinky_down = pinky_tip.y > pinky_base.y + 0.03   # pinky curled

            # ======= STRICT V-GESTURE ✌️ (Single Voice Activation) =======
            # Index VERY high + Middle VERY high + Ring CLEARLY down + Pinky CLEARLY down
            is_v_gesture = (
                index_up and            # Index finger clearly UP
                middle_up and           # Middle finger clearly UP  
                ring_down and           # Ring finger clearly DOWN
                pinky_down and          # Pinky finger clearly DOWN
                not is_open_palm        # Make sure it's not open palm (add this check below)
            )
            
            # First check for open palm (before V-gesture to avoid conflict)
            is_open_palm_check = (
                index_tip.y < index_mcp.y and 
                middle_tip.y < middle_base.y and 
                ring_tip.y < ring_base.y and 
                pinky_tip.y < pinky_base.y
            )
            
            # Re-evaluate V-gesture with palm check
            is_v_gesture = (
                index_up and            
                middle_up and           
                ring_down and           
                pinky_down and          
                not is_open_palm_check  # NOT open palm!
            )
            
            # Activate voice with V gesture (single activation - not toggle!)
            if is_v_gesture and not is_listening and v_gesture_cooldown <= 0:
                print("✌️ V-GESTURE detected! Starting voice...")
                threading.Thread(target=listen_for_command, daemon=True).start()
                v_gesture_cooldown = 90  # 1.5 second cooldown (longer to prevent re-trigger)
            
            # Update global V-gesture state (for UI display)
            is_v_gesture_active = is_v_gesture
            
            # ======= OPEN PALM ✋ (Stop scrolling + Stop AI speech) =======
            # All 5 fingers extended (already checked above as is_open_palm_check)
            is_open_palm = is_open_palm_check and thumb_out
            
            # Open palm stops everything!
            if is_open_palm and open_palm_cooldown <= 0:
                # Stop scrolling
                if is_scrolling:
                    is_scrolling = False
                    scroll_direction = 0
                    print("✋ OPEN PALM - Scrolling stopped!")
                
                # Stop AI speech
                if is_ai_speaking:
                    stop_ai_speech()
                    print("✋ OPEN PALM - AI speech stopped!")
                
                open_palm_cooldown = 30  # 0.5 second cooldown

            # ======= THUMBS UP/DOWN for TOGGLE Scrolling =======
            thumb_base = hand_landmarks.landmark[2]   # Thumb base (near palm)
            
            # Check if fingers are curled (fist shape - all fingertips below their base)
            fingers_curled = (
                index_down and      # Index curled
                middle_down and     # Middle curled
                ring_down and       # Ring curled
                pinky_down          # Pinky curled
            )
            
            # Thumbs UP: thumb tip is much higher than index knuckle, fingers curled
            is_thumbs_up = thumb_tip.y < index_mcp.y - 0.08 and fingers_curled
            
            # Thumbs DOWN: thumb tip is much lower than thumb base, fingers curled  
            is_thumbs_down = thumb_tip.y > index_mcp.y + 0.08 and fingers_curled
            
            # TOGGLE scrolling with thumbs up/down (one gesture = start, stays on)
            if is_thumbs_up and not is_listening and not is_scrolling:
                is_scrolling = True
                scroll_direction = 1  # UP
                print("👍 THUMBS UP - Scrolling UP started!")
                
            if is_thumbs_down and not is_listening and not is_scrolling:
                is_scrolling = True
                scroll_direction = -1  # DOWN
                print("👎 THUMBS DOWN - Scrolling DOWN started!")
            
            # Actually perform the continuous scrolling (every 5th frame to save CPU)
            if is_scrolling and frame_count % 5 == 0:
                pyautogui.scroll(scroll_direction * 200)  # Scroll speed

            # ======= Grab Logic ======= (State Machine)

            # Check if cursor is over the card 
            cursor_over_card = (card_x < cursor_x < card_x + card_width and 
                               card_y < cursor_y < card_y + card_height)

            # Grab Logic 
            if is_pinching and cursor_over_card:
                is_grabbing = True
            elif not is_pinching:
                is_grabbing = False

            # If grabbing, move the card with the cursor 
            if is_grabbing: 
                card_x = cursor_x - card_width // 2 
                card_y = cursor_y - card_height // 2

            # Decrease cooldown timers 
            if v_gesture_cooldown > 0:
                v_gesture_cooldown -= 1
            if open_palm_cooldown > 0:
                open_palm_cooldown -= 1
    else:
        # No hand detected - reset V-gesture state
        is_v_gesture_active = False
        
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

        
        else: 
            #If no soecific command, ask AI 
            ai_response = ask_ai( last_command )
            threading.Thread(target=speak, args=(ai_response,), daemon=True).start()
        last_command = "" 



    # ===== STEP 6: DON'T DRAW WEBCAM (process in background only) =====
    # We still process the frame for hand tracking above, but don't display it!
    # Black fill becomes transparent (color key mode)
    screen.fill((0, 0, 0))  # Fill entire screen with black (transparent)

    # ===== STEP 6: CUSTOM UI ELEMENTS (ONLY VISIBLE PARTS) =====
    
    # Check if hand is detected (for cursor visibility)
    hand_detected = results.multi_hand_landmarks is not None
    
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
        ai_status = ai_font.render("🎤 AI Speaking... (Palm=Stop)", True, (255, 100, 255))  # Pink
        screen.blit(ai_status, (WINDOW_WIDTH - 300, WINDOW_HEIGHT - 40))
    
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
cap.release()
pygame.quit() 




