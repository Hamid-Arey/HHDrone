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
when servos are enabled, `gpiozero` with a pin backend supported by your Pi.
Use a Raspberry Pi OS environment with working Picamera2 camera support.
The camera must support the resolution and requested frame rate configured
in `OpenCV_initialization.py`; lower `FPS` if your camera cannot sustain it.

Camera configuration starts at 640 x 480 and 60 FPS for the NoIR V2.
Actual processing rate depends on exposure and Pi workload.

Servo output defaults to **BCM GPIO12 for pan and GPIO13 for tilt**. If your
wires are instead connected to physical header positions 12 and 13, run with
`--pin-numbering physical`; gpiozero accepts explicit `BOARD12`/`BOARD13` names.
See [gpiozero pin numbering](https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering).
Confirm your servos' pulse range and travel limits before attaching the load.
The camera must move with the pan/tilt gimbal for centering to work. Servos
follow each current blinking-light detection, hold within five pixels of
center, and hold their angle while the light is off or lost. Motion is capped
at 15 degrees per second with angle limits of -90 to +90 degrees.

If an axis moves the light away from the center, reverse that axis:

```sh
python3 MAIN_FINAL.py --invert-pan
python3 MAIN_FINAL.py --invert-tilt
python3 MAIN_FINAL.py --invert-pan --invert-tilt
```

Each current detection supplies `delta_x = light_x - center_x` to pan and
`delta_y = light_y - center_y` to tilt. The PD law for each axis is
`speed = Kp * delta + Kd * (delta - previous_delta) / elapsed_seconds`.
The signed, bounded speed is integrated into the servo angle. The derivative
history resets when tracking is lost to avoid a jump when reacquiring.

Tune both gains from the command line, for example:

```sh
python3 MAIN_FINAL.py --kp 0.10 --kd 0.002
```

These are starting values; hardware tuning is still required. Deadband and
speed settings are in `pd_controller.py`. Use a suitable servo supply with a shared ground to the Pi.

The tracker chooses the largest bright blob and checks for repeated on/off
transitions over 60 captured frames. It does not verify an exact 5 Hz frequency
or distinguish multiple blinking sources. Tune the threshold, history size,
and camera settings for your light and surroundings. Picamera2's RGB888 array
is processed in OpenCV's BGR channel order.

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

The combined program explicitly uses a local pigpio pin factory for stable
servo pulse timing on the Pi 4B. It stops with an error if unavailable rather
than falling back to a software PWM backend. Install the `pigpio` daemon and
Python `pigpio` package for your OS, then start the daemon:

```sh
sudo systemctl start pigpiod
python3 servo_test.py
```

The camera-free test commands pan and then tilt through 0, -10, 0, +10, 0
degrees with two seconds at each angle. It initializes both servos at center;
provide clearance for that initial motion. Stop other servo programs first.
Use `--pin-numbering physical` only if wired to header positions 12/13.

For default BCM numbering, pan signal is physical pin 32 (GPIO12) and tilt
signal is physical pin 33 (GPIO13). Both grounds and the external servo supply
negative must connect to Pi ground. Supply voltage must match the servo rating,
and the supply must support both motors' combined stall current.

If an axis jitters while holding a fixed command in this test, camera/PD gains
are not the cause. Check power, ground, connections, servo, and mechanical load.
To isolate a stationary pan motor, power off and swap only the two signal leads:
if that motor works on the tilt output, inspect the pan wiring/output; if it
still does not work, inspect its power, motor and mechanism. Restore the leads
before tracking. If both axes pass this test but tracking moves away from the
light, use the corresponding `--invert-pan` or `--invert-tilt` option.

References: [gpiozero PWM backend guidance](https://gpiozero.readthedocs.io/en/v1.6.0/api_output.html#servo)
and [pigpio pin factory](https://gpiozero.readthedocs.io/en/stable/api_pins.html#pigpio).
