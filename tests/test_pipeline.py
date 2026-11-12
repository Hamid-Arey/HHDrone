import csv
import io
from pathlib import Path
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import numpy as np
import BB84
import MAIN_FINAL


class PipelineTests(unittest.TestCase):
    def test_bb84_without_eavesdropper(self):
        with patch.object(BB84, "rng", np.random.default_rng(42)):
            with redirect_stdout(io.StringIO()):
                key, errors, tapped, qber = BB84.bb84(1000, 0, .25, 0, 10)
        self.assertGreater(len(key), 8)
        self.assertEqual((errors, tapped, qber), (0, 0, 0))

    def test_missing_target(self):
        self.assertEqual(BB84.bb84(1000, .25, .25, None, None), ([], 0, 0, 1.0))

    def test_single_camera_loop_and_csv(self):
        camera = MagicMock()
        tracker = MagicMock()
        tracker.main.return_value = (None, None, None, None)
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "results.csv")
            with patch.dict("sys.modules", {"OpenCV_initialization": camera, "opencv": tracker}):
                with patch("MAIN_FINAL.time.monotonic", side_effect=[0, 0, .1, 2]):
                    MAIN_FINAL.run(runtime=1, show=False, servos=False, output=output)
            with open(output, newline="") as file:
                rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key_length"], "0")
        camera.start_camera.assert_called_once()
        camera.close_program.assert_called_once()

    def test_camera_cleanup_on_capture_failure(self):
        camera = MagicMock()
        tracker = MagicMock()
        tracker.main.side_effect = RuntimeError("capture failed")
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("sys.modules", {"OpenCV_initialization": camera, "opencv": tracker}):
                with self.assertRaisesRegex(RuntimeError, "capture failed"):
                    MAIN_FINAL.run(show=False, servos=False, output=str(Path(directory) / "results.csv"))
        camera.close_program.assert_called_once()

    def test_pin_numbering_and_gains_reach_controller(self):
        for numbering, pan, tilt in [("bcm", "GPIO12", "GPIO13"),
                                      ("physical", "BOARD12", "BOARD13")]:
            with self.subTest(numbering=numbering):
                camera, tracker, pd = MagicMock(), MagicMock(), MagicMock()
                tracker.main.return_value = (20, -10, 22, 5)
                with tempfile.TemporaryDirectory() as directory:
                    with patch.dict("sys.modules", {"OpenCV_initialization": camera,
                                                    "opencv": tracker, "pd_controller": pd}):
                        with patch("MAIN_FINAL.time.monotonic", side_effect=[0, 0, .1, 2]):
                            with redirect_stdout(io.StringIO()):
                                MAIN_FINAL.run(runtime=1, show=False, kp=.4, kd=.02,
                                               pin_numbering=numbering,
                                               output=str(Path(directory) / "results.csv"))
                pd.configure_servo_pwm.assert_called_once_with()
                pd.configure_servo_pwm.return_value.close.assert_called_once_with()
                pd.ScratchPDController.assert_called_once_with(
                    .4, .02, max_speed=15, pan_pin=pan, tilt_pin=tilt,
                    pan_direction=-1, tilt_direction=1)
                pd.ScratchPDController.return_value.update_position.assert_called_once_with(20, -10)

    def test_pd_starts_without_derivative_kick_and_clamps(self):
        fake_gpio = types.ModuleType("gpiozero")
        fake_gpio.AngularServo = MagicMock()
        with patch.dict("sys.modules", {"gpiozero": fake_gpio}):
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_pd", "pd_controller.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        controller = module.ScratchPDController(.3, .01, 12, 13)
        with patch.object(module, "monotonic", side_effect=[0, .02, .04, .06]):
            controller.update_position(100, 100)
            self.assertAlmostEqual(controller.pan_position, -.5)
            self.assertAlmostEqual(controller.tilt_position, .5)
            held = (controller.pan_position, controller.tilt_position)
            controller.update_position(3, -3)
            self.assertEqual((controller.pan_position, controller.tilt_position), held)
            controller.update_position(100000, 100000)
            self.assertAlmostEqual(controller.pan_position, held[0] - .9)
            controller.pan_position = -89.9
            controller.tilt_position = 89.9
            controller.update_position(100000, 100000)
            self.assertEqual(controller.pan_position, -90)
            self.assertEqual(controller.tilt_position, 90)
        # The gentler runtime tuning limits abrupt changes in either direction.
        gentle = module.ScratchPDController(.10, .002, 12, 13, max_speed=15)
        with patch.object(module, "monotonic", side_effect=[2, 2.02, 2.04]):
            gentle.update_position(0, 100)
            self.assertAlmostEqual(gentle.tilt_position, 10 / 60)
            previous = gentle.tilt_position
            gentle.update_position(0, -100)
            self.assertLessEqual(abs(gentle.tilt_position - previous), .3 + 1e-9)
            previous = gentle.tilt_position
            gentle.update_position(0, 2)
            self.assertEqual(gentle.tilt_position, previous)
        gentle.close()
        # A decreasing error produces a negative derivative that damps motion.
        derivative_controller = module.ScratchPDController(0, .01, 12, 13)
        with patch.object(module, "monotonic", side_effect=[1, 1.02]):
            derivative_controller.update_position(100, 0)
            self.assertEqual(derivative_controller.pan_position, 0)
            derivative_controller.update_position(80, 0)
            self.assertAlmostEqual(derivative_controller.pan_position, .2)
            self.assertEqual(derivative_controller.tilt_position, 0)
        derivative_controller.close()
        controller.reset()
        self.assertIsNone(controller.prev_time)
        controller.close()

        reversed_controller = module.ScratchPDController(
            .3, .01, 12, 13, pan_direction=1, tilt_direction=-1
        )
        reversed_controller.update_position(100, 100)
        self.assertGreater(reversed_controller.pan_position, 0)
        self.assertLess(reversed_controller.tilt_position, 0)
        reversed_controller.close()



if __name__ == "__main__":
    unittest.main()
