import time
from blink_tracker import BlinkTracker
from picamera2 import Picamera2

# -----------------------------
# CAMERA CONFIGURATION
# -----------------------------

#We are initializing the variables here
WIDTH = 640
HEIGHT = 480
FPS = 90  # Requested camera rate; actual processing rate depends on workload

# Brightness threshold for IR detection
IR_THRESHOLD = 220

# Required LED blink frequency in Hz
BLINK_FREQUENCY = 5

BLINK_TOLERANCE = 0.5  # Allow camera sampling jitter (4.5–5.5 Hz)


# -----------------------------
# INITIALIZE CAMERA
# -----------------------------
picam2 = None
latest_metadata = {}
exposure_frozen = False
last_tracked_time = None
tracking_hold_active = False
LOSS_HOLD_SECONDS = 5.0


def start_camera():
    """Open one shared camera, only when tracking starts."""
    global picam2, last_position, last_radius
    global latest_metadata, exposure_frozen, last_tracked_time, tracking_hold_active
    if picam2 is not None:
        return picam2
    camera = Picamera2()
    try:
        config = camera.create_video_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
            sensor={"output_size": (640, 480), "bit_depth": 10},
            controls={"FrameRate": FPS},
            queue=False,
        )
        camera.configure(config)
        camera.start()
        time.sleep(2)
    except BaseException:
        camera.close()
        raise
    latest_metadata = {}
    exposure_frozen = False
    last_tracked_time = None
    tracking_hold_active = False
    blink_tracker.reset()
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

blink_tracker = BlinkTracker(BLINK_FREQUENCY, BLINK_TOLERANCE)


def capture_timed_frame():
    """Pair the image with its sensor timestamp, not processing completion time."""
    global latest_metadata
    request = start_camera().capture_request()
    try:
        frame = request.make_array("main")
        latest_metadata = request.get_metadata()
        timestamp = latest_metadata["SensorTimestamp"] / 1_000_000_000
        return frame, timestamp
    finally:
        request.release()


def update_tracking_exposure(target_visible, locked, timestamp):
    """Freeze exposure/gain across tracking and the five-second loss hold."""
    global last_tracked_time, tracking_hold_active, exposure_frozen
    if locked and target_visible:
        last_tracked_time = timestamp
    tracking_hold_active = locked or (last_tracked_time is not None
                                     and timestamp - last_tracked_time < LOSS_HOLD_SECONDS)
    if tracking_hold_active == exposure_frozen:
        return
    controls = {"AeEnable": not tracking_hold_active}
    # Newer libcamera exposes separate manual/auto modes as well.
    for name in ("ExposureTimeMode", "AnalogueGainMode"):
        if name in picam2.camera_controls:
            controls[name] = 1 if tracking_hold_active else 0
    if tracking_hold_active:
        controls["ExposureTime"] = latest_metadata["ExposureTime"]
        controls["AnalogueGain"] = latest_metadata["AnalogueGain"]
    picam2.set_controls(controls)
    exposure_frozen = tracking_hold_active


def close_program():
    global picam2
    camera, picam2 = picam2, None
    if camera is not None:
        try:
            camera.stop()
        finally:
            camera.close()
