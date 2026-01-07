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

#====AI SETUP====
grok_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT)) #create window 
pygame.display.set_caption("HoloDesk - Step 5: Gesture + Voice + AI + Desktop Control") #window title 
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

# v gesture for voice activation ( instead of spacebar)
v_gesture_cooldown = 0 # prevents triggering multiple times 

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

#Function to speak using Windows SAPI directly (more reliable than pyttsx3)
def speak(text): 
    print(f"SPEAKING: {text}")  # Debug
    try:
        import comtypes.client  # Windows COM interface
        speaker = comtypes.client.CreateObject("SAPI.SpVoice")
        speaker.Rate = 1  # Speed: -10 (slow) to 10 (fast)
        speaker.Volume = 100  # Volume: 0 to 100
        speaker.Speak(text)
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

#Function to listen for voice commands ( runs in the background)
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


        # 2 Press spacebar to toggle voice command 
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

            # ======= Voice Activation (V-Gesture) ======= 
            # Get finger landmarks 
            middle_tip = hand_landmarks.landmark[12] # middle finger tip 
            middle_base = hand_landmarks.landmark[9] # middle finger base
            ring_tip = hand_landmarks.landmark[16] # ring finger tip
            ring_base = hand_landmarks.landmark[13] # ring finger base
            pinky_tip = hand_landmarks.landmark[20] # pinky finger tip
            pinky_base = hand_landmarks.landmark[17] # pinky finger base

            #check which fingers are up ( tip higher than base = smaller y value )
            index_up = index_tip.y < hand_landmarks.landmark[5].y # is index finger up?
            middle_up = middle_tip.y < middle_base.y # is middle finger up?
            ring_down = ring_tip.y > ring_base.y # is ring finger down?
            pinky_down = pinky_tip.y > pinky_base.y # is pinky finger down?

            # V gesture: index and middle up , ring and pinky down 
            is_v_gesture = index_up and middle_up and ring_down and pinky_down

            # Activate voice with v gesture !
            if is_v_gesture and not is_listening and v_gesture_cooldown <= 0:
                print("V Gesture detected! Activating voice activation...")
                threading.Thread(target=listen_for_command, daemon=True).start()
                v_gesture_cooldown = 60 # Wait 60 frames (1 second) before allowing another v gesture

            # ======= THUMBS UP/DOWN for Continuous Scrolling =======
            thumb_base = hand_landmarks.landmark[2]   # Thumb base (near palm)
            index_mcp = hand_landmarks.landmark[5]    # Index finger knuckle
            
            # Check if fingers are curled (fist shape - all fingertips below their base)
            fingers_curled = (
                index_tip.y > index_mcp.y and      # Index curled
                middle_tip.y > middle_base.y and   # Middle curled
                ring_tip.y > ring_base.y and       # Ring curled
                pinky_tip.y > pinky_base.y         # Pinky curled
            )
            
            # Thumbs UP: thumb tip is much higher than index knuckle, fingers curled
            is_thumbs_up = thumb_tip.y < index_mcp.y - 0.08 and fingers_curled
            
            # Thumbs DOWN: thumb tip is much lower than thumb base, fingers curled  
            is_thumbs_down = thumb_tip.y > thumb_base.y + 0.08 and fingers_curled
            
            # Continuous scroll while holding gesture (only when not listening)
            if is_thumbs_up and not is_listening and not is_v_gesture:
                pyautogui.scroll(50)  # Scroll UP continuously - FAST!
                
            if is_thumbs_down and not is_listening and not is_v_gesture:
                pyautogui.scroll(-50)  # Scroll DOWN continuously - FAST!

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

            # Decrease V gesture cooldown timer 
            if v_gesture_cooldown > 0:
                v_gesture_cooldown -= 1
        
    # ==== PROCESS VOICE COMMANDS ==== 
    if last_command:
        print(f"PROCESSING COMMAND: {last_command}")  # Debug
        if "reset" in last_command:
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
            threading.Thread(target=speak, args=("I can help you with the following commands: reset, color, hello, bye, thanks",), daemon=True).start()
        
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



    # Rotate for pygame display (pygame.surfarray needs rotated data)
    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

    # Create pygame surface from the frame 
    frame_surface = pygame.surfarray.make_surface(frame)

    # Scale to fit window 
    frame_surface = pygame.transform.scale(frame_surface, (WINDOW_WIDTH, WINDOW_HEIGHT))
    
    # Mirror horizontally AND flip vertically to correct orientation
    frame_surface = pygame.transform.flip(frame_surface, True, True)

    #4. DRAW EVERYTHING 
    screen.blit(frame_surface, (0,0))

    #5. Draw Draggable Card 
    pygame.draw.rect(screen, card_color, (card_x, card_y, card_width, card_height))

    #Draw border ( thicker when grabbing)
    border_color = (255, 255, 0 ) if is_grabbing else (255, 255, 255)
    border_width = 5 if is_grabbing else 2
    pygame.draw.rect(screen, border_color, (card_x, card_y, card_width, card_height), border_width)
    #6. Calculate and display FPS 
    fps = clock.get_fps()
    font = pygame.font.Font(None, 36) 
    fps_text = font.render(f"FPS: {int(fps)}", True, (0, 255, 0)) 
    screen.blit(fps_text, (10, 10))  # blit = " copy this image onto the screen"

    #7 show listening status
    if is_listening:
        if ready_to_speak:
            # Big green "SPEAK NOW!" when ready
            big_font = pygame.font.Font(None, 72)
            speak_text = big_font.render("SPEAK NOW!", True, (0, 255, 0))
            # Center it on screen
            text_rect = speak_text.get_rect(center=(WINDOW_WIDTH // 2, 80))
            screen.blit(speak_text, text_rect)
        else:
            # Yellow "Preparing..." while adjusting for noise
            listening_text = font.render("Preparing mic...", True, (255, 255, 0))
            screen.blit(listening_text, (10, 50))

    #7. Draw cursor dot 
    pygame.draw.circle(screen, (255,0,0), (cursor_x, cursor_y), 15) 

    #8. Update display
    pygame.display.flip() # update the display to show the new frame
    clock.tick(FPS_CAP) 

# ==============CLEAN UP============== 
cap.release()
pygame.quit() 




