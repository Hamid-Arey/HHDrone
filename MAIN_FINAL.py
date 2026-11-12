"""One camera loop for IR tracking, optional gimbal control, and BB84 logging."""
import argparse
import csv
import time

import BB84


def run(runtime=120, interval=1.0, show=True, servos=True, output="results.csv",
        invert_pan=False, invert_tilt=False, kp=0.10, kd=0.002,
        pin_numbering="bcm"):
    if pin_numbering not in ("bcm", "physical"):
        raise ValueError("pin_numbering must be bcm or physical")
    if kp < 0 or kd < 0:
        raise ValueError("PD gains must be nonnegative")
    if runtime <= 0 or interval <= 0:
        raise ValueError("runtime and interval must be positive")
    import OpenCV_initialization as camera
    import opencv

    gimbal = None
    pin_factory = None
    try:
        if servos:
            from pd_controller import ScratchPDController, configure_servo_pwm
            pin_factory = configure_servo_pwm()
            gimbal = ScratchPDController(
                kp, kd, max_speed=15,
                pan_pin="BOARD12" if pin_numbering == "physical" else "GPIO12",
                tilt_pin="BOARD13" if pin_numbering == "physical" else "GPIO13",
                pan_direction=1 if invert_pan else -1,
                tilt_direction=-1 if invert_tilt else 1,
            )
        camera.start_camera()
        if show:
            opencv.cv2.namedWindow("IR tracking", opencv.cv2.WINDOW_NORMAL)
        start = time.monotonic()
        next_sample = start
        with open(output, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["second", "r", "w", "QBER", "key_length", "useful"])
            while time.monotonic() - start < runtime:
                dx, dy, distance, radius = opencv.main(show=show)
                if gimbal is not None:
                    if dx is not None:
                        gimbal.update_position(dx, dy)
                    else:
                        gimbal.reset()
                now = time.monotonic()
                if now >= next_sample:
                    key, _, _, qber = BB84.bb84(
                        1000, 0.25, 0.25, distance, radius
                    )
                    writer.writerow([round(now - start, 3), distance, radius,
                                     qber, len(key), len(key) >= 8])
                    file.flush()
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
                if pin_factory is not None:
                    pin_factory.close()
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
    parser.add_argument("--invert-pan", action="store_true", help="Reverse horizontal servo direction")
    parser.add_argument("--invert-tilt", action="store_true", help="Reverse vertical servo direction")
    parser.add_argument("--kp", type=float, default=0.10, help="Proportional gain (degrees/second/pixel)")
    parser.add_argument("--kd", type=float, default=0.002, help="Derivative gain (degrees/pixel)")
    parser.add_argument("--pin-numbering", choices=("bcm", "physical"), default="bcm",
                        help="Numbering for pan pin 12 and tilt pin 13 (default: bcm)")
    args = parser.parse_args()
    try:
        run(args.runtime, args.interval, args.show, not args.no_servos, args.output,
            args.invert_pan, args.invert_tilt, args.kp, args.kd, args.pin_numbering)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
