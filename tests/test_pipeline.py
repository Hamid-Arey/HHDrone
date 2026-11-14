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
    def test_key_metrics_threshold_length_sampling_and_width(self):
        self.assertEqual(MAIN_FINAL.key_metrics(.11, 16, 1, 10), (False, False, 0))
        self.assertEqual(MAIN_FINAL.key_metrics(.10, 7, 1, 10), (True, False, 0))
        self.assertEqual(MAIN_FINAL.key_metrics(.10, 8, 1, 10), (True, True, 5))
        self.assertEqual(MAIN_FINAL.key_metrics(.10, 23, 1, 10), (True, True, 10))
        self.assertEqual(MAIN_FINAL.key_metrics(.10, 16, 1, 20)[2], 20)
        self.assertLess(MAIN_FINAL.key_metrics(.10, 16, 2, 10)[2],
                        MAIN_FINAL.key_metrics(.10, 16, 1, 10)[2])
        self.assertEqual(MAIN_FINAL.key_metrics(1, 0, None, 10), (False, False, 0))

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
        self.assertEqual(rows[0]["qber_below_11_percent"], "FALSE")
        self.assertEqual(rows[0]["useful"], "FALSE")
        for name in ("x", "y", "dx", "dy", "r", "w"):
            self.assertEqual(rows[0][name], "")
        self.assertEqual(float(rows[0]["estimated_useful_keys_per_second"]), 0)
        camera.start_camera.assert_called_once()
        camera.close_program.assert_called_once()

    def test_csv_current_coordinates_and_useful_rate(self):
        camera, tracker = MagicMock(), MagicMock()
        camera.center_x, camera.center_y = 320, 240
        tracker.main.return_value = (3, -4, 5, 2)
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "results.csv")
            with patch.dict("sys.modules", {"OpenCV_initialization": camera, "opencv": tracker}):
                with patch("MAIN_FINAL.time.monotonic", side_effect=[0, 0, .1, .2, .7, 2]):
                    with patch.object(BB84, "bb84", return_value=([0] * 16, 0, 0, .10)):
                        MAIN_FINAL.run(runtime=1, interval=.5, show=False, servos=False, output=output)
            with open(output, newline="") as file:
                rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 2)
        self.assertEqual([rows[0][name] for name in ("x", "y", "dx", "dy", "r", "w")],
                         ["323", "236", "3", "-4", "5", "2"])
        self.assertEqual(rows[0]["qber_below_11_percent"], "TRUE")
        self.assertEqual(rows[0]["useful"], "TRUE")
        self.assertAlmostEqual(float(rows[0]["estimated_useful_keys_per_second"]), .8)
        self.assertAlmostEqual(float(rows[1]["sampling_rate_hz"]), 1 / .6)

    def test_camera_cleanup_on_capture_failure(self):
        camera = MagicMock()
        tracker = MagicMock()
        tracker.main.side_effect = RuntimeError("capture failed")
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("sys.modules", {"OpenCV_initialization": camera, "opencv": tracker}):
                with self.assertRaisesRegex(RuntimeError, "capture failed"):
                    MAIN_FINAL.run(show=False, servos=False, output=str(Path(directory) / "results.csv"))
        camera.close_program.assert_called_once()

    def test_tracking_receives_current_detection_or_missing_target(self):
        for detected in (True, False):
            with self.subTest(detected=detected):
                camera, tracker, pd = MagicMock(), MagicMock(), MagicMock()
                camera.blink_tracker.is_locked = detected
                tracker.main.return_value = ((20, -10, 22, 5) if detected
                                             else (None, None, None, None))
                with tempfile.TemporaryDirectory() as directory:
                    with patch.dict("sys.modules", {"OpenCV_initialization": camera,
                                                    "opencv": tracker, "pd_controller": pd}):
                        with patch("MAIN_FINAL.time.monotonic", side_effect=[0, 0, .1, 2]):
                            with redirect_stdout(io.StringIO()):
                                MAIN_FINAL.run(runtime=1, show=False,
                                               pin_numbering="bcm",
                                               output=str(Path(directory) / "results.csv"))
                pd.PDTrackingController.assert_called_once_with(
                    pan_pin="GPIO12", tilt_pin="GPIO13", pan_direction=1,
                    tilt_direction=-1, kp=.8, kd=.01)
                pd.PDTrackingController.return_value.update.assert_called_once_with(
                    20 if detected else None, -10 if detected else None,
                    target_locked=detected)

    def test_passive_sweep_speed_limits_and_tilt_hold(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_sweep", "pd_controller.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.HardwarePWMServo = MagicMock(side_effect=lambda *args: MagicMock())
        controller = module.PassiveSweepController(12, 13)
        with patch.object(module, "monotonic", side_effect=[0, .1, .2, .3, .4, 10]):
            controller.sweep()
            self.assertEqual(controller.pan_position, 0)
            controller.sweep()
            self.assertAlmostEqual(controller.pan_position, -1.8)
            controller.pan_position = -89.9
            controller.sweep()
            self.assertEqual(controller.pan_position, -90)
            controller.sweep()
            self.assertAlmostEqual(controller.pan_position, -88.2)
            controller.pan_position = 89.9
            controller.sweep()
            self.assertEqual(controller.pan_position, 90)
            controller.sweep()
            self.assertAlmostEqual(controller.pan_position, 88.2)
        self.assertEqual(controller.tilt_position, 0)
        controller.close()
        controller.pan.close.assert_called_once()
        controller.tilt.close.assert_called_once()
        reverse = module.PassiveSweepController(12, 13, pan_direction=1)
        with patch.object(module, "monotonic", side_effect=[0, .1]):
            reverse.sweep()
            reverse.sweep()
        self.assertAlmostEqual(reverse.pan_position, 1.8)
        reverse.close()


if __name__ == "__main__":
    unittest.main()
