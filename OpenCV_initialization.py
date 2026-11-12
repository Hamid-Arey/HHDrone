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
FPS = 60  # Starting target for Pi 4B + NoIR V2 tracking and preview

# Brightness threshold for IR detection
IR_THRESHOLD = 220

# Expected LED frequency (Change later)
BLINK_FREQUENCY = 5

# Number of recent frames used to check blinking
HISTORY_SIZE = FPS  # Approximately one second at the requested frame rate


# -----------------------------
# INITIALIZE CAMERA
# -----------------------------
picam2 = None


def start_camera():
    """Open one shared camera, only when tracking starts."""
    global picam2, last_position, last_radius
    if picam2 is not None:
        return picam2
    camera = Picamera2()
    try:
        config = camera.create_video_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
            controls={"FrameRate": FPS},
        )
        camera.configure(config)
        camera.start()
        time.sleep(2)
    except BaseException:
        camera.close()
        raise
    brightness_history.clear()
    last_position = None
    last_radius = None
    picam2 = camera
    return camera


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
    global picam2
    camera, picam2 = picam2, None
    if camera is not None:
        try:
            camera.stop()
        finally:
            camera.close()
