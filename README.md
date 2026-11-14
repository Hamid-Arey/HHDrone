# Raspberry Pi 4B / NoIR V2 IR tracking and BB84 simulation

Run everything from this directory with the Pi's Python environment:

```sh
python3 MAIN_FINAL.py
```

The default run lasts 120 seconds, enables the gimbal on BCM GPIO 12 (pan)
and 13 (tilt), and writes `results.csv`. Tracking runs on every captured frame;
BB84 is sampled once per second. A live camera window opens by default, with
the center and tracked target marked. Press q in the window, close the window,
or press Ctrl+C to stop.

CSV output includes current drone/IR-target pixel coordinates `x`, `y` (origin
at the top left), center-relative `dx = x - center_x`, `dy = y - center_y`
(positive right/down), and resultant `r = sqrt(dx*dx + dy*dy)`. At 640 x 480
the center pixel is (320, 240). Coordinates are blank when no current target
is detected; historical rows without coordinates remain blank.
`w` is the detected blob radius used as the simulated connection-width proxy;
larger values apply a greater rate penalty as described below.
CSV output also includes `qber_below_11_percent` (`TRUE` only for QBER < 0.11)
and `useful` (`TRUE` when that threshold passes and key length is at least 8).
QBER remains a fraction: 0.11 means 11%; exactly 11% fails.
`sampling_rate_hz` measures BB84 batches per second using elapsed time between
samples; the first row uses `1 / --interval`. This includes processing delays
and is separate from camera FPS. Set `--interval` to change the batch interval.
`estimated_useful_keys_per_second` is zero for rejected or short keys; otherwise
it is `floor(key_length / 8) * sampling_rate_hz / (1 + w*w)`.
This counts complete 8-bit chunks with an assumed inverse-area width penalty,
so larger `w` reduces the estimated rate at fixed key length and sampling rate.
The penalty is an uncalibrated simulation assumption, not measured throughput.
The existing photon-survival model also depends on `r` and `w`, so stochastic
key lengths can vary independently of this penalty. Historical CSV rows use
their recorded timestamps, with a one-second interval assumed for the first row.

```sh
python3 MAIN_FINAL.py --show --runtime 120
python3 MAIN_FINAL.py --no-servos --runtime 30
```

The camera window requires a graphical desktop on the Pi (local or remote).
For SSH sessions without a desktop, use `python3 MAIN_FINAL.py --headless`.
`arm.py` starts the same combined program. Do not run a second camera script
at the same time.

## Pi environment and hardware

The Python environment must provide `numpy`, `cv2` (OpenCV), `picamera2`, and,
when servos are enabled, `rpi-hardware-pwm` with the Pi 4 PWM overlay enabled.
Use a Raspberry Pi OS environment with working Picamera2 camera support.
The camera must support the resolution and requested frame rate configured
in `OpenCV_initialization.py`; lower `FPS` if your camera cannot sustain it.

Camera configuration requests 640 x 480 at 90 FPS for the NoIR V2, explicitly
selecting the 640 x 480, 10-bit sensor mode (cropped field of view).
Actual processing rate depends on exposure and Pi workload.

Servo signals use **BCM GPIO12 (pan, physical header pin 32)** and
**BCM GPIO13 (tilt, physical header pin 33)**. Hardware PWM is fixed to these
pins by the overlay below. `--pin-numbering physical` is rejected when servos
are enabled: header pins 12/13 do not provide the required pair of PWM outputs.
Confirm your servos' pulse range and travel limits before attaching the load.
Without a confirmed target, pan sweeps at 18 degrees/second between -90 and
+90 degrees, three times the previous 6 degrees/second search speed; tilt holds its current angle.
Once the 5 Hz light is confirmed, the sweep stops and both axes use PD
corrections to center it. Defaults are Kp=0.8 and Kd=0.01, with a 12-pixel
deadzone and tracking speed capped at 120 degrees/second per axis. The controller
retains an established lock through blink-off phases and brief processing gaps.
After losing the target, both axes hold their angles for 5 seconds from the
last current locked detection. Reacquisition restarts that timer. Only after
the hold expires does the 18 degrees/second search sweep resume. Old target coordinates are never reused.
Derivative history resets during missing frames to prevent reacquisition kicks.
Damping can stop a correction but cannot reverse it away from the target.

```sh
sudo .venv/bin/python MAIN_FINAL.py --headless --kp 0.8 --kd 0.01
```

Default tracking directions are pan +1 and tilt -1, reversed from the earlier
configuration. At a steady 100-pixel error the proportional speed is now
80 degrees/second, up to a 120 degrees/second cap per axis. The actual
servo speed depends on the motor and load; during blink-off phases it holds.
Use `--invert-pan` or `--invert-tilt` if the corresponding tracking axis moves
the light away from center. `--invert-pan` also reverses initial search direction.
Hardware PWM remains at 50 Hz on GPIO12/GPIO13. Use a suitable servo supply
with a shared ground to the Pi. Camera preview and BB84 logging still use
confirmed 5 Hz detections.

The BB84 code is a simulation, not an optical quantum communication system.
It models photon survival using pixel offset and detected blob radius; these
are uncalibrated proxies for physical beam displacement and beam width. A
missing target yields an empty key and QBER 1.0 as an untrusted sentinel.
The simulation does not perform error correction or privacy amplification;
its resulting bits must not be used as production encryption keys.

## Local checks

```sh
python3 -m unittest discover -s tests -v
```

Tests cover BB84, the combined loop, CSV output, cleanup, and servo control
with simulated hardware. Camera image processing and physical motion require
validation on the Pi.

## Jitter or one axis not moving

The combined program drives the Pi 4 hardware PWM channels through the Linux
PWM interface using `rpi-hardware-pwm`. GPIO Zero, lgpio and pigpiod are no
longer used. Both channels run at 50 Hz. Angles -90/0/+90 map to pulse widths
1/1.5/2 ms, matching the previous servo defaults. Hardware keeps generating
pulses independently of camera processing; delayed frames can still delay
updates to the requested angle.

On the Pi, edit `/boot/firmware/config.txt` (`/boot/config.txt` on older OS
versions). Under `[all]`, set the following, replacing any existing conflicting
PWM overlay and `dtparam=audio=on` line. Analog audio shares the PWM peripheral.

```ini
[all]
dtparam=audio=off
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

Reboot, then install the Python dependency in a virtual environment that can
also access the Pi's system camera packages:

```sh
sudo reboot
# After reconnecting, in ~/Documents/team10:
sudo apt install python3-venv
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install rpi-hardware-pwm
ls /sys/class/pwm/pwmchip0
```

Copy updated `MAIN_FINAL.py`, `pd_controller.py` and `servo_test.py` together.
Test the outputs with clearance for movement. If your account does not have
write permission to the PWM sysfs files, these commands run with root access:

```sh
sudo .venv/bin/python servo_test.py
sudo .venv/bin/python MAIN_FINAL.py --headless
```

With PWM write permission configured for your account, run
`.venv/bin/python MAIN_FINAL.py` normally for the camera preview. Do not run
another program using the same PWM channels concurrently. There is no software
PWM fallback if hardware setup is missing.

The camera-free test commands pan and then tilt through 0, -10, 0, +10, 0
degrees with two seconds at each angle. It initializes both servos at center;
provide clearance for that initial motion. Stop other servo programs first.

For default BCM numbering, pan signal is physical pin 32 (GPIO12) and tilt
signal is physical pin 33 (GPIO13). Both grounds and the external servo supply
negative must connect to Pi ground. Supply voltage must match the servo rating,
and the supply must support both motors' combined stall current.

If an axis jitters while holding a fixed command in this test, camera detection
is not the cause. Check power, ground, connections, servo, and mechanical load.
To isolate a stationary pan motor, power off and swap only the two signal leads:
if that motor works on the tilt output, inspect the pan wiring/output; if it
still does not work, inspect its power, motor and mechanism. Restore the leads
before running the sweep again.

References: [hardware PWM library and overlay setup](https://github.com/Pioreactor/rpi_hardware_pwm)
and [Raspberry Pi PWM overlay reference](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/arch/arm/boot/dts/overlays/README).

## 5 Hz light selection

Each bright blob is tracked separately. Acquisition requires at least four
blink periods with a median frequency of 4.5–5.5 Hz and consistent periods
within 45 ms of 200 ms. The established target gets priority in association,
with smoothed velocity prediction and size checks. Its matching radius adapts
to motion up to 140 pixels; overlapping identical lights can still be ambiguous.
Single-frame dimming at 90 FPS is debounced (off intervals below 25 ms are not
counted as new blink edges). Once locked, occasional missed complete flashes
are tolerated when measuring periods. Visual lock expires after 1 second without
seeing the target or sufficient evidence of 5 Hz blinking, but the gimbal
continues holding until 5 seconds after the last locked detection. A steady light or
changed blink frequency eventually releases lock; there is no indefinite latch.

Only current on-phase coordinates steer the gimbal. Motion predictions are
used for matching, never to command servos while the LED is invisible. During
off phases the servos hold and the yellow vector shows the last measurement.
The preview displays LOCKED, holding through blink/gap, or SEARCHING.

Blink timing uses SensorTimestamp metadata from the same capture request as
the image, so processing latency does not alter measured frequency. Camera
buffer requests are released even on image errors. Cached-frame queuing is
disabled. A lighter 3x3 blur replaces the old 5x5 blur and morphological opening,
which could erase small LEDs; small contours are still filtered by area.
Headless mode skips all preview rendering. Real camera/servo testing remains
necessary; exposure, threshold and extreme motor movement can still affect
visibility.

Deploy `blink_tracker.py` alongside the updated `opencv.py` and
`OpenCV_initialization.py` on the Pi.

Vector calculation, detection and servo commands run once per processed frame,
with no separate refresh timer. The requested camera rate is 90 FPS; actual
processing throughput can be lower. Per-frame console output is disabled by
default to avoid slowing the loop. Servo hardware pulses remain at 50 Hz.

## Exposure during tracking

Before acquisition, the camera uses automatic exposure/gain. On the first
confirmed visible LED detection, its ExposureTime and AnalogueGain metadata
are saved and applied with automatic exposure disabled. These settings stay
fixed during tracking, blink-off phases, and the full 5-second loss hold.
Reacquiring within that hold does not change exposure or gain. Automatic
exposure resumes only when the hold expires and searching resumes. Separate
manual exposure/gain mode controls are also set when the installed libcamera
supports them. Camera controls can take several frames to take effect.
