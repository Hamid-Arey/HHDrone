"""Test small pan/tilt movements without camera tracking or PD corrections."""
import argparse
from time import sleep


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin-numbering", choices=("bcm", "physical"), default="bcm")
    args = parser.parse_args()
    from pd_controller import ScratchPDController, configure_servo_pwm
    factory = configure_servo_pwm()
    controller = None
    try:
        prefix = "GPIO" if args.pin_numbering == "bcm" else "BOARD"
        controller = ScratchPDController(0, 0, prefix + "12", prefix + "13")
        for name, servo in (("PAN", controller.pan), ("TILT", controller.tilt)):
            for angle in (0, -10, 0, 10, 0):
                print(f"{name}: commanded {angle:+d} degrees", flush=True)
                servo.angle = angle
                sleep(2)
    finally:
        try:
            if controller is not None:
                controller.close()
        finally:
            factory.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
