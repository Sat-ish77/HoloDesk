import pygame #window + drawing
import cv2  #webcam 
import time 


#settings 
WINDOW_WIDTH = 1280 # width of window 
WINDOW_HEIGHT = 720 # height of window 
FPS_CAP = 60 # frames per second 


# SETUP 
pygame.init()  #  start pygame engine 
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT)) #create window 
pygame.display.set_caption("HoloDesk- Step 0") #window title 
clock = pygame.time.Clock()  # controls timing 
cap = cv2.VideoCapture(0) # open webcam ( 0= default camera)


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
    
    #2. Read webcam frame (this is where the webcam image is read)
    success, frame = cap.read()
    if not success: 
        continue 

    #3. Convert frame for pygame 
    #opencv uses BGR (blue, green, red) but pygame uses RGB (red, green, blue) - so we flip the colors. 
    frame= cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 

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

    #5. Calculate and display FPS 
    fps = clock.get_fps()
    font = pygame.font.Font(None, 36) 
    fps_text = font.render(f"FPS: {int(fps)}", True, (0, 255, 0)) 
    screen.blit(fps_text, (10, 10))  # blit = " copy this image onto the screen"

    #6. Update display
    pygame.display.flip() # update the display to show the new frame
    clock.tick(FPS_CAP) 

# ==============CLEAN UP============== 
cap.release()
pygame.quit() 




