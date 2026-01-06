import pygame #window + drawing
import cv2  #webcam 
import time 
import mediapipe as mp
import speech_recognition as sr
import pyttsx3
import threading 


#settings 
WINDOW_WIDTH = 1280 # width of window 
WINDOW_HEIGHT = 720 # height of window 
FPS_CAP = 60 # frames per second 


# SETUP 
pygame.init()  #  start pygame engine 
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT)) #create window 
pygame.display.set_caption("HoloDesk- Step 2: Grab & Drag") #window title 
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

#=============VOICE SETUP============== 
recognizer = sr.Recognizer()
mic = sr.Microphone()

#Text-to-Speech engine 
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150) #speed of speech( words per minute)

#Variable to store last voice command 
last_command = ""
is_listening = False

#Function to speak ( runs in the background so it doesn't freezes the app)
def speak(text): 
    tts_engine.say(text)
    tts_engine.runAndWait()

#Function to listen for voice commands ( runs in the background)
def listen_for_command():
    global last_command, is_listening

    with mic as source: 
        recognizer.adjust_for_ambient_noise(source, duration=0.5) 
        is_listening = True 
        print("Listening...")
    
        try: 
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            command = recognizer.recognize_google(audio).lower()
            print(f"You said: {command}")
            last_command = command
        except sr.WaitTimeoutError:
            print("No voice input detected")
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError:
            print("Could not request results from Google Speech Recognition service")
        finally: 
            is_listening = False 



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
        
    # ==== PROCESS VOICE COMMANDS ==== 
    if last_command:
        if "reset" in last_command:
            card_x = 400 
            card_y = 300 
            threading.Thread(target=speak, args=("Card reset!",), daemon=True).start()

        elif "color" in last_command or "colour" in last_command:
            import random
            card_color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
            threading.Thread(target=speak, args=("Card color changed!",), daemon=True).start()

        elif "hello" in last_command or "hi" in last_command:
            threading.Thread(target=speak, args=("Hello! How can I help you today?",), daemon=True).start()
        elif "bye" in last_command or "goodbye" in last_command:
            threading.Thread(target=speak, args=("Goodbye! Have a great day!",), daemon=True).start()
        elif "thank you" in last_command or "thanks" in last_command:
            threading.Thread(target=speak, args=("You're welcome!",),daemon=True).start()
        elif "help" in last_command:
            threading.Thread(target=speak, args=("I can help you with the following commands: reset, color, hello, bye, thanks",), daemon=True).start()
        
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
        listening_text = font.render("Listening...", True, (255, 255, 0))
        screen.blit(listening_text, (10, 50))

    #7. Draw cursor dot 
    pygame.draw.circle(screen, (255,0,0), (cursor_x, cursor_y), 15) 

    #8. Update display
    pygame.display.flip() # update the display to show the new frame
    clock.tick(FPS_CAP) 

# ==============CLEAN UP============== 
cap.release()
pygame.quit() 




