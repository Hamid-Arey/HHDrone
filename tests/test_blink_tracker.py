import unittest
from blink_tracker import BlinkTracker


class BlinkTrackerTests(unittest.TestCase):
    def simulate(self, frequency, fps=60, steady=False):
        tracker = BlinkTracker()
        results = []
        for frame in range(180):
            now = frame / fps
            on = steady or (now * frequency) % 1 < .5
            result = tracker.update([(100, 100, 4)] if on else [], now)
            results.append(result)
            if not on:
                self.assertIsNone(result)
        return results

    def test_accepts_five_hz_at_different_frame_rates(self):
        for fps in (30, 45, 60, 90):
            with self.subTest(fps=fps):
                self.assertTrue(any(self.simulate(5, fps)))

    def test_rejects_other_frequencies_and_steady_light(self):
        for frequency in (1, 2, 3, 4, 6, 8, 10):
            with self.subTest(frequency=frequency):
                self.assertFalse(any(self.simulate(frequency)))
        self.assertFalse(any(self.simulate(0, steady=True)))

    def test_separate_sources_and_off_frames(self):
        tracker = BlinkTracker()
        found = False
        for frame in range(180):
            now = frame / 60
            points = [(200, 200, 20)]  # Larger steady distractor.
            on = frame % 12 < 6
            if on:
                points.append((100, 100, 3))
            result = tracker.update(points, now)
            if result is not None:
                found = True
                self.assertEqual(result, (100, 100, 3))
                self.assertTrue(on)
        self.assertTrue(found)
        self.assertIsNone(tracker.update([(100, 100, 3)], 5))

    def test_lost_or_steady_target_loses_confirmation(self):
        tracker = BlinkTracker()
        for frame in range(120):
            tracker.update([(100, 100, 3)] if frame % 12 < 6 else [], frame / 60)
        results = [tracker.update([(100, 100, 3)], frame / 60)
                   for frame in range(120, 240)]
        self.assertIsNone(results[-1])

    def test_retains_lock_through_off_phases_at_ninety_fps(self):
        tracker = BlinkTracker()
        for frame in range(360):
            now = frame / 90
            on = frame % 18 < 9
            point = (100 + frame // 18, 100, 3)
            target = tracker.update([point] if on else [], now)
            if frame >= 100:
                self.assertTrue(tracker.is_locked)
                self.assertEqual(target, point if on else None)
        for frame in range(360, 450):
            tracker.update([], frame / 90)
        self.assertFalse(tracker.is_locked)

    def test_processing_delay_does_not_restart_acquisition(self):
        tracker = BlinkTracker()
        for frame in range(270):
            # Skip 100 ms while already locked.
            if 100 <= frame < 109:
                continue
            now = frame / 90
            on = frame % 18 < 9
            tracker.update([(100, 100, 3)] if on else [], now)
            if frame >= 90:
                self.assertTrue(tracker.is_locked)

    def test_steady_light_eventually_releases_lock(self):
        tracker = BlinkTracker()
        for frame in range(180):
            tracker.update([(100, 100, 3)] if frame % 18 < 9 else [], frame / 90)
        self.assertTrue(tracker.is_locked)
        for frame in range(180, 300):
            tracker.update([(100, 100, 3)], frame / 90)
        self.assertFalse(tracker.is_locked)

    def test_moving_light_with_dim_frames_and_missed_flashes(self):
        tracker = BlinkTracker()
        for frame in range(540):
            now = frame / 90
            cycle, phase = divmod(frame, 18)
            on = phase < 9
            # One-frame dimming while lit; occasionally miss an entire flash.
            visible = on and not (cycle >= 6 and phase == 3)
            visible = visible and cycle not in (10, 11, 21)
            point = (100 + frame * .6, 140 + frame * .15, 4)
            target = tracker.update([point] if visible else [], now)
            if frame >= 100:
                self.assertTrue(tracker.is_locked, f'Lost lock at frame {frame}')
                if target is not None:
                    self.assertEqual(target, point)

    def test_prediction_follows_motion_over_blink_gap(self):
        tracker = BlinkTracker()
        for frame in range(270):
            now = frame / 90
            # After lock, 10 px/frame during a gap exceeds the old 80 px gate.
            x = 100 if frame < 108 else 100 + (frame - 108) * 10
            point = (x, 100, 4)
            target = tracker.update([point] if frame % 18 < 9 else [], now)
            if frame >= 100:
                self.assertTrue(tracker.is_locked)
                if frame % 18 < 9:
                    self.assertEqual(target, point)

    def test_locked_target_does_not_jump_to_steady_distractor(self):
        tracker = BlinkTracker()
        for frame in range(270):
            now = frame / 90
            on = frame % 18 < 9
            target = (100 + frame * .1, 100, 3)
            points = [(150, 120, 12)]
            if on:
                points.append(target)
            result = tracker.update(points, now)
            if frame >= 100:
                self.assertTrue(tracker.is_locked)
                self.assertEqual(result, target if on else None)

    def test_wrong_frequency_after_lock_expires(self):
        for frequency in (0, 4, 6, 10):
            tracker = BlinkTracker()
            for frame in range(180):
                tracker.update([(100, 100, 3)] if frame % 18 < 9 else [], frame / 90)
            for frame in range(180, 540):
                on = frequency == 0 or ((frame / 90) * frequency) % 1 < .5
                tracker.update([(100, 100, 3)] if on else [], frame / 90)
            self.assertFalse(tracker.is_locked, f'Kept {frequency} Hz lock')
