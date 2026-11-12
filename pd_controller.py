
from gpiozero import AngularServo
from time import monotonic


def configure_servo_pwm():
    """Use pigpio's DMA-timed pulses on the Pi 4; never silently fall back."""
    try:
        from gpiozero import Device
        from gpiozero.pins.pigpio import PiGPIOFactory
        factory = PiGPIOFactory(host="localhost")
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Servo PWM needs python3-pigpio and a running local pigpiod service. "
            "Start it with: sudo systemctl start pigpiod"
        ) from exc
    Device.pin_factory = factory
    return factory


class ScratchPDController:
    """PD visual servoing: speed = Kp * pixel_error + Kd * d(error)/dt.

    Pan uses delta_x and tilt uses delta_y. Integrate the bounded speed into
    servo angles; there is no integral-error term. Directions depend on mounting.
    """
    def __init__(self, kp, kd, pan_pin, tilt_pin, deadband=5,
                 max_speed=45, pan_direction=-1, tilt_direction=1):
        self.deadband = deadband
        self.max_speed = max_speed
        self.pan_direction = pan_direction
        self.tilt_direction = tilt_direction
        self.kp = kp
        self.kd = kd

        self.pan = AngularServo(
            pan_pin,
            min_angle=-90,
            max_angle=90
        )

        try:
            self.tilt = AngularServo(
                tilt_pin, min_angle=-90, max_angle=90
            )
        except BaseException:
            self.pan.close()
            raise

        self.pan_position = 0
        self.tilt_position = 0

        self.prev_x = 0
        self.prev_y = 0
        self.prev_time = None

    def update_position(self, delta_x, delta_y):
        now = monotonic()
        # Corrections are angular speeds, integrated over elapsed time.
        # Limit elapsed time so a delayed frame cannot cause a large jump.
        elapsed = now - self.prev_time if self.prev_time is not None else 1 / 60
        sample_dt = max(elapsed, 0.001)
        dt = min(sample_dt, 0.1)
        dx = (delta_x - self.prev_x) / sample_dt if self.prev_time is not None else 0
        dy = (delta_y - self.prev_y) / sample_dt if self.prev_time is not None else 0

        def correction(error, derivative):
            if abs(error) <= self.deadband:
                return 0.0
            speed = self.kp * error + self.kd * derivative
            return max(-self.max_speed, min(self.max_speed, speed))

        self.pan_position += self.pan_direction * correction(delta_x, dx) * dt
        self.tilt_position += self.tilt_direction * correction(delta_y, dy) * dt

        self.pan_position = max(-90, min(90, self.pan_position))
        self.tilt_position = max(-90, min(90, self.tilt_position))

        self.pan.angle = self.pan_position
        self.tilt.angle = self.tilt_position

        self.prev_x = delta_x
        self.prev_y = delta_y
        self.prev_time = now

    def reset(self):
        self.prev_time = None

    def close(self):
        try:
            self.pan.close()
        finally:
            self.tilt.close()

