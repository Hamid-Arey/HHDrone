import unittest
from unittest.mock import MagicMock, patch

from pd_controller import PDTrackingController


class PDTrackingTests(unittest.TestCase):
    def controller(self, **kwargs):
        with patch('pd_controller.HardwarePWMServo', side_effect=lambda pin: MagicMock()):
            return PDTrackingController('GPIO12', 'GPIO13', **kwargs)

    def test_search_runs_at_eighteen_degrees_per_second_and_reverses(self):
        c = self.controller()
        with patch('pd_controller.monotonic', side_effect=[0, .1, .2, .3]):
            c.update(None, None)
            previous = c.pan_position
            c.update(None, None)
            self.assertAlmostEqual(c.pan_position - previous, 1.8)
            c.pan_position = 89.9
            c.update(None, None)
            self.assertEqual(c.pan_position, 90)
            c.update(None, None)
            self.assertAlmostEqual(c.pan_position, 88.2)
        self.assertEqual(c.tilt_position, 0)

    def test_lock_stops_sweep_and_holds_blink_off_phases(self):
        c = self.controller()
        with patch('pd_controller.monotonic', side_effect=[0, .1, .2, .3, .4, .5, 5.4]):
            c.update(None, None)
            c.update(100, -100)
            self.assertAlmostEqual(c.pan_position, 8)
            self.assertAlmostEqual(c.tilt_position, 8)
            held = (c.pan_position, c.tilt_position)
            c.update(None, None)
            self.assertEqual((c.pan_position, c.tilt_position), held)
            c.update(100, -100)
            self.assertAlmostEqual(c.pan_position, 16)  # No derivative kick.
            c.update(12, -12)
            held = (c.pan_position, c.tilt_position)
            c.update(None, None)
            self.assertEqual((c.pan_position, c.tilt_position), held)
            c.update(None, None)
            self.assertAlmostEqual(c.pan_position, held[0] + 1.8)
            self.assertEqual(c.tilt_position, held[1])

    def test_derivative_damping_limits_and_inversion(self):
        c = self.controller(pan_direction=-1, tilt_direction=1)
        with patch('pd_controller.monotonic', side_effect=[0, .1, .11, .21]):
            c.update(100, 100)
            previous = c.pan_position
            c.update(80, 80)
            self.assertAlmostEqual(c.pan_position - previous, -6.2)
            self.assertGreater(c.tilt_position, 0)
            held = c.pan_position
            c.update(13, 13)  # Large derivative cannot drive away from target.
            self.assertEqual(c.pan_position, held)
            c.pan_position, c.tilt_position = -89.9, 89.9
            c.update(100000, 100000)
            self.assertEqual((c.pan_position, c.tilt_position), (-90, 90))

    def test_tracking_speed_is_capped_at_one_hundred_twenty_degrees_per_second(self):
        c = self.controller()
        with patch('pd_controller.monotonic', side_effect=[0, .1]):
            c.update(1000, 1000)
            c.update(1000, 1000)
        self.assertAlmostEqual(c.pan_position, 12)
        self.assertAlmostEqual(c.tilt_position, -12)

    def test_retained_visual_lock_prevents_search_without_stale_steering(self):
        c = self.controller()
        with patch('pd_controller.monotonic', side_effect=[0, .1, 1, 2, 5.1]):
            c.update(100, 100, target_locked=True)
            c.update(100, 100, target_locked=True)
            held = (c.pan_position, c.tilt_position)
            c.update(None, None, target_locked=True)
            c.update(None, None, target_locked=True)
            self.assertEqual((c.pan_position, c.tilt_position), held)
            c.update(None, None, target_locked=False)
            self.assertAlmostEqual(c.pan_position, held[0] + 1.8)
            self.assertEqual(c.tilt_position, held[1])

    def test_five_second_hold_and_reacquisition_restart_timer(self):
        c = self.controller()
        with patch('pd_controller.monotonic', side_effect=[0, .1, 1.2, 4.9, 5, 5.1, 10, 10.1]):
            c.update(100, 100, target_locked=True)
            c.update(100, 100, target_locked=True)
            held = (c.pan_position, c.tilt_position)
            c.update(None, None)
            c.update(None, None)
            self.assertEqual((c.pan_position, c.tilt_position), held)
            c.update(0, 0, target_locked=True)
            c.update(None, None)
            self.assertEqual((c.pan_position, c.tilt_position), held)
            c.update(None, None)
            self.assertAlmostEqual(c.pan_position, held[0] + 1.8)
            c.update(None, None)
            self.assertAlmostEqual(c.pan_position, held[0] + 3.6)
