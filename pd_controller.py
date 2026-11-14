"""Pi 4 hardware PWM servo output, search sweep, and PD tracking."""
from math import isfinite
from time import monotonic


class HardwarePWMServo:
    """50 Hz hardware pulses: -90/0/+90 degrees map to 1/1.5/2 ms."""
    def __init__(self, pin):
        channels = {12: 0, 13: 1, "GPIO12": 0, "GPIO13": 1}
        if pin not in channels:
            raise ValueError(
                "Hardware PWM requires BCM GPIO12/GPIO13 (header pins 32/33). "
                "Physical header pins 12/13 are not supported."
            )
        try:
            from rpi_hardware_pwm import HardwarePWM
        except ImportError as exc:
            raise RuntimeError(
                "Install rpi-hardware-pwm in your Python environment; "
                "see README.md hardware PWM setup."
            ) from exc
        self._closed = False
        try:
            self._pwm = HardwarePWM(pwm_channel=channels[pin], hz=50, chip=0)
        except Exception as exc:
            raise RuntimeError(
                "Cannot open hardware PWM. Enable "
                "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4, "
                "reboot, and check /sys/class/pwm/pwmchip0 permissions. "
                f"Backend error: {exc}"
            ) from exc
        try:
            self._pwm.start(7.5)
        except BaseException:
            self._pwm.stop()
            raise
        self._angle = 0

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        if self._closed:
            raise RuntimeError("Servo is closed")
        if not isfinite(value) or not -90 <= value <= 90:
            raise ValueError("Servo angle must be between -90 and +90 degrees")
        # At 50 Hz the period is 20 ms; pulse width ranges from 1 to 2 ms.
        self._pwm.change_duty_cycle(7.5 + value / 36)
        self._angle = value

    def close(self):
        if not self._closed:
            self._pwm.stop()
            self._closed = True


class PassiveSweepController:
    """Sweep pan continuously at 18 degrees/second, independent of detection."""
    def __init__(self, pan_pin, tilt_pin, pan_direction=-1):
        if pan_pin not in (12, "GPIO12") or tilt_pin not in (13, "GPIO13"):
            raise ValueError("Use GPIO12 for pan and GPIO13 for tilt (header pins 32/33)")
        self.pan = HardwarePWMServo(pan_pin)
        try:
            self.tilt = HardwarePWMServo(tilt_pin)
        except BaseException:
            self.pan.close()
            raise
        self.pan_position = 0
        self.tilt_position = 0
        self.direction = pan_direction
        self.prev_time = None

    def sweep(self):
        now = monotonic()
        elapsed = now - self.prev_time if self.prev_time is not None else 0
        self.prev_time = now
        # A delayed frame must not cause a sudden large movement.
        dt = min(max(elapsed, 0), 0.1)
        self._sweep(dt)

    def _sweep(self, dt, speed=18.0):
        self.pan_position += self.direction * speed * dt
        self.pan_position = max(-90, min(90, self.pan_position))
        if self.pan_position <= -90:
            self.direction = 1
        elif self.pan_position >= 90:
            self.direction = -1
        self.pan.angle = self.pan_position

    def close(self):
        try:
            self.pan.close()
        finally:
            self.tilt.close()


class PDTrackingController(PassiveSweepController):
    """Search at 18 degrees/second; steer only from confirmed target errors."""
    def __init__(self, pan_pin, tilt_pin, pan_direction=1, tilt_direction=-1,
                 kp=0.8, kd=0.01, deadband=12, max_speed=120.0, loss_hold=5.0):
        if not all(isfinite(v) and v >= 0 for v in (kp, kd, deadband, max_speed, loss_hold)):
            raise ValueError("PD gains, deadband and max_speed must be finite and nonnegative")
        super().__init__(pan_pin, tilt_pin, pan_direction)
        self.kp, self.kd = kp, kd
        self.deadband, self.max_speed = deadband, max_speed
        self.pan_direction, self.tilt_direction = pan_direction, tilt_direction
        self.loss_hold = loss_hold
        self.last_target_time = None
        self.previous_error = None

    def update(self, delta_x, delta_y, target_locked=False):
        now = monotonic()
        elapsed = max(now - self.prev_time, .001) if self.prev_time is not None else 0
        dt = min(elapsed, .1)
        self.prev_time = now
        if delta_x is None or delta_y is None:
            self.previous_error = None
            # A retained visual lock suppresses searching during blink-off frames.
            if not target_locked and (self.last_target_time is None or now - self.last_target_time >= self.loss_hold):
                self._sweep(dt, speed=18.0)
            return

        self.last_target_time = now
        errors = (delta_x, delta_y)
        speeds = []
        for i, error in enumerate(errors):
            derivative = ((error - self.previous_error[i]) / elapsed
                          if self.previous_error is not None else 0)
            speed = self.kp * error + self.kd * derivative
            # Damping may stop a correction, but never drive away from the target.
            if abs(error) <= self.deadband or speed * error < 0:
                speed = 0
            speeds.append(max(-self.max_speed, min(self.max_speed, speed)))
        self.pan_position = max(-90, min(90, self.pan_position + self.pan_direction * speeds[0] * dt))
        self.tilt_position = max(-90, min(90, self.tilt_position + self.tilt_direction * speeds[1] * dt))
        self.pan.angle = self.pan_position
        self.tilt.angle = self.tilt_position
        self.previous_error = errors
