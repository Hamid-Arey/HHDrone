import time
import cv2
from collections import deque
from picamera2 import Picamera2

# -----------------------------
# CAMERA CONFIGURATION
# -----------------------------

#We are initializing the variables here
WIDTH = 640
HEIGHT = 480
FPS = 90

# Brightness threshold for IR detection
IR_THRESHOLD = 220

# Expected LED frequency (Change later)
BLINK_FREQUENCY = 5

# Number of recent frames used to check blinking
HISTORY_SIZE = 90


# -----------------------------
# INITIALIZE CAMERA
# -----------------------------
picam2 = Picamera2()

#Configures the camera
config = picam2.create_video_configuration(

#Setting the video resolution and format
    main={
        "size": (WIDTH, HEIGHT),
        "format": "RGB888" #How the video data is formatted (3 color components RGB)
    },

#Sets the desired frame rate
    controls={
        "FrameRate": FPS
    }
)

#Telling the camera to use above settings when running the camera
picam2.configure(config)

#Starting the camera
picam2.start()

#Pauses the program to give the camera time to boot up
time.sleep(2)

# -----------------------------
# TRACKING VARIABLES
# -----------------------------

#Calculate the center pixel of the camera
center_x = WIDTH // 2
center_y = HEIGHT // 2

#Since this is the first pixel we don't have anything to compare it to
last_position = None
last_radius = None

#Creates a brightness history (keeping only the last 30) looks at past 30 brightnesses
brightness_history = deque(maxlen=HISTORY_SIZE)


def close_program():

    #This closes the openCV windows and the camera 
    picam2.stop()
    cv2.destroyAllWindows()

    print("IR tracker stopped")