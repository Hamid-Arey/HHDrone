"""Test small pan/tilt movements without camera tracking."""
import argparse
from time import sleep


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin-numbering", choices=("bcm",), default="bcm")
    args = parser.parse_args()
    from pd_controller import PassiveSweepController
    controller = None
    try:
        controller = PassiveSweepController("GPIO12", "GPIO13")
        for name, servo in (("PAN", controller.pan), ("TILT", controller.tilt)):
            for angle in (0, -10, 0, 10, 0):
                print(f"{name}: commanded {angle:+d} degrees", flush=True)
                servo.angle = angle
                sleep(2)
    finally:
        if controller is not None:
            controller.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
