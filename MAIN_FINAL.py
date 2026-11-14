"""One camera loop for IR tracking, optional gimbal control, and BB84 logging."""
import argparse
import csv
from math import isfinite
import time

import BB84


def key_metrics(qber, key_length, w, sampling_rate_hz):
    """Return acceptance, usability, and modeled 8-bit keys/second.

    The inverse-area width penalty is an uncalibrated simulation assumption.
    Sampling rate is the BB84 batch rate, not the requested camera FPS.
    """
    accepted = isfinite(qber) and 0 <= qber < 0.11
    useful = accepted and key_length >= 8
    rate = 0.0
    if (useful and w is not None and isfinite(w) and w > 0
            and isfinite(sampling_rate_hz) and sampling_rate_hz > 0):
        rate = (key_length // 8) * sampling_rate_hz / (1 + w * w)
    return accepted, useful, rate


def run(runtime=120, interval=1.0, show=True, servos=True, output="results.csv",
        invert_pan=False, pin_numbering="bcm", kp=0.8, kd=0.01,
        invert_tilt=False):
    if pin_numbering not in ("bcm", "physical"):
        raise ValueError("pin_numbering must be bcm or physical")
    if servos and pin_numbering != "bcm":
        raise ValueError("Hardware PWM uses BCM GPIO12/GPIO13 (header pins 32/33); use --pin-numbering bcm")
    if not all(isfinite(v) and v > 0 for v in (runtime, interval)):
        raise ValueError("runtime and interval must be positive")
    if not all(isfinite(v) and v >= 0 for v in (kp, kd)):
        raise ValueError("PD gains must be finite and nonnegative")
    import OpenCV_initialization as camera
    import opencv

    gimbal = None
    try:
        if servos:
            from pd_controller import PDTrackingController
            gimbal = PDTrackingController(
                pan_pin="GPIO12",
                tilt_pin="GPIO13",
                pan_direction=-1 if invert_pan else 1,
                tilt_direction=1 if invert_tilt else -1,
                kp=kp, kd=kd,
            )
        camera.start_camera()
        if show:
            opencv.cv2.namedWindow("IR tracking", opencv.cv2.WINDOW_NORMAL)
        start = time.monotonic()
        next_sample = start
        previous_sample = None
        with open(output, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["second", "x", "y", "dx", "dy", "r", "w", "QBER", "key_length", "useful",
                             "qber_below_11_percent", "sampling_rate_hz",
                             "estimated_useful_keys_per_second"])
            while time.monotonic() - start < runtime:
                dx, dy, distance, radius = opencv.main(show=show)
                if gimbal is not None:
                    gimbal.update(dx, dy, target_locked=camera.blink_tracker.is_locked)
                now = time.monotonic()
                if now >= next_sample:
                    key, _, _, qber = BB84.bb84(
                        1000, 0.25, 0.25, distance, radius
                    )
                    sample_period = interval if previous_sample is None else now - previous_sample
                    sampling_rate = 1.0 / sample_period
                    accepted, useful, rate = key_metrics(qber, len(key), radius, sampling_rate)
                    x = camera.center_x + dx if dx is not None else None
                    y = camera.center_y + dy if dy is not None else None
                    writer.writerow([round(now - start, 3), x, y, dx, dy, distance, radius,
                                     qber, len(key), str(useful).upper(),
                                     str(accepted).upper(), sampling_rate, rate])
                    file.flush()
                    previous_sample = now
                    next_sample = now + interval
                if show:
                    if opencv.cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                    if opencv.cv2.getWindowProperty("IR tracking", opencv.cv2.WND_PROP_VISIBLE) < 1:
                        break
    finally:
        try:
            if gimbal is not None:
                gimbal.close()
        finally:
            try:
                camera.close_program()
            finally:
                if show:
                    opencv.cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=float, default=120)
    parser.add_argument("--interval", type=float, default=1)
    display = parser.add_mutually_exclusive_group()
    display.add_argument("--show", dest="show", action="store_true", help="Show camera window (default)")
    display.add_argument("--headless", dest="show", action="store_false", help="Run without a camera window")
    parser.set_defaults(show=True)
    parser.add_argument("--no-servos", action="store_true")
    parser.add_argument("--output", default="results.csv")
    parser.add_argument("--invert-pan", action="store_true", help="Reverse pan tracking and initial sweep direction")
    parser.add_argument("--invert-tilt", action="store_true", help="Reverse tilt tracking direction")
    parser.add_argument("--kp", type=float, default=0.8, help="Proportional gain (degrees/second/pixel)")
    parser.add_argument("--kd", type=float, default=0.01, help="Derivative gain (degrees/pixel)")
    parser.add_argument("--pin-numbering", choices=("bcm", "physical"), default="bcm",
                        help="Hardware PWM requires bcm: GPIO12/GPIO13 (header pins 32/33)")
    args = parser.parse_args()
    try:
        run(args.runtime, args.interval, args.show, not args.no_servos, args.output,
            args.invert_pan, args.pin_numbering, args.kp, args.kd, args.invert_tilt)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
