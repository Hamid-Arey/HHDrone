import importlib.util
import types
import unittest
from unittest.mock import MagicMock, patch


class CameraTimingTests(unittest.TestCase):
    def module(self):
        fake_camera = types.ModuleType('picamera2')
        fake_camera.Picamera2 = MagicMock()
        with patch.dict('sys.modules', {'picamera2': fake_camera, 'cv2': MagicMock()}):
            spec = importlib.util.spec_from_file_location('camera_under_test', 'OpenCV_initialization.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module

    def test_frame_and_timestamp_share_request_and_release(self):
        module = self.module()
        module.picam2 = MagicMock()
        request = module.picam2.capture_request.return_value
        request.get_metadata.return_value = {'SensorTimestamp': 123456789000}
        frame, timestamp = module.capture_timed_frame()
        self.assertIs(frame, request.make_array.return_value)
        self.assertAlmostEqual(timestamp, 123.456789)
        request.make_array.assert_called_once_with('main')
        request.release.assert_called_once_with()

    def test_release_request_on_image_error(self):
        module = self.module()
        module.picam2 = MagicMock()
        request = module.picam2.capture_request.return_value
        request.make_array.side_effect = RuntimeError('capture failed')
        with self.assertRaises(RuntimeError):
            module.capture_timed_frame()
        request.release.assert_called_once_with()

    def test_configuration_requests_90fps_and_no_cached_frame(self):
        module = self.module()
        with patch.object(module.time, 'sleep'):
            module.start_camera()
        module.picam2.create_video_configuration.assert_called_once_with(
            main={'size': (640, 480), 'format': 'RGB888'},
            sensor={'output_size': (640, 480), 'bit_depth': 10},
            controls={'FrameRate': 90}, queue=False)

    def test_exposure_freezes_once_and_survives_loss_hold(self):
        module = self.module()
        module.picam2 = MagicMock()
        module.picam2.camera_controls = {}
        module.latest_metadata = {'ExposureTime': 4500, 'AnalogueGain': 2.0}
        module.update_tracking_exposure(True, True, 1)
        module.picam2.set_controls.assert_called_once_with({
            'AeEnable': False, 'ExposureTime': 4500, 'AnalogueGain': 2.0})
        # Changes reported by subsequent frames must not rewrite frozen values.
        module.latest_metadata = {'ExposureTime': 9000, 'AnalogueGain': 4.0}
        module.update_tracking_exposure(False, True, 1.1)
        module.update_tracking_exposure(False, False, 5.99)
        self.assertEqual(module.picam2.set_controls.call_count, 1)
        self.assertTrue(module.exposure_frozen)
        module.update_tracking_exposure(False, False, 6)
        module.picam2.set_controls.assert_called_with({'AeEnable': True})
        self.assertFalse(module.exposure_frozen)
        module.update_tracking_exposure(False, False, 7)
        self.assertEqual(module.picam2.set_controls.call_count, 2)

    def test_reacquisition_keeps_exposure_and_restarts_hold(self):
        module = self.module()
        module.picam2 = MagicMock()
        module.picam2.camera_controls = {'ExposureTimeMode': (), 'AnalogueGainMode': ()}
        module.latest_metadata = {'ExposureTime': 4000, 'AnalogueGain': 1.5}
        module.update_tracking_exposure(True, True, 1)
        module.picam2.set_controls.assert_called_once_with({
            'AeEnable': False, 'ExposureTimeMode': 1, 'AnalogueGainMode': 1,
            'ExposureTime': 4000, 'AnalogueGain': 1.5})
        module.update_tracking_exposure(False, False, 3)
        module.update_tracking_exposure(True, True, 4)
        module.update_tracking_exposure(False, False, 8.99)
        self.assertEqual(module.picam2.set_controls.call_count, 1)
        module.update_tracking_exposure(False, False, 9)
        module.picam2.set_controls.assert_called_with({
            'AeEnable': True, 'ExposureTimeMode': 0, 'AnalogueGainMode': 0})

    def test_search_before_first_lock_leaves_auto_exposure_enabled(self):
        module = self.module()
        module.picam2 = MagicMock()
        module.update_tracking_exposure(False, False, 10)
        self.assertFalse(module.exposure_frozen)
        module.picam2.set_controls.assert_not_called()
