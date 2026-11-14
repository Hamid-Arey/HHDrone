"""Track individual light sources and acquire/retain a measured 5 Hz lock."""
from collections import deque
from math import hypot
from statistics import median


class BlinkTracker:
    def __init__(self, frequency=5.0, tolerance=0.5, match_radius=40,
                 lock_timeout=1.0):
        self.lock_timeout = lock_timeout
        self.frequency = frequency
        self.tolerance = tolerance
        self.match_radius = match_radius
        self.reset()

    def reset(self):
        self.tracks = []
        self.last_time = None
        self.locked = None

    @property
    def is_locked(self):
        return self.locked is not None

    def _prediction(self, track, now):
        dt = min(max(now - track['seen'], 0), .2)
        x, y, _ = track['point']
        vx, vy = track['velocity']
        return x + vx * dt, y + vy * dt

    def _matches_frequency(self, track, now, retained=False):
        rises = list(track['rises'])
        if len(rises) < 5 or now - rises[-1] > .25:
            return False
        periods = [b - a for a, b in zip(rises, rises[1:])][-6:]
        if retained:
            # Missing a whole flash must not look like a changed blink rate.
            periods = [p / max(1, min(3, round(p * self.frequency))) for p in periods]
        good = [p for p in periods if abs(p - 1 / self.frequency) <= .045]
        if len(good) < max(3, len(periods) - (1 if retained else 0)):
            return False
        return abs(1 / median(good) - self.frequency) <= self.tolerance

    def update(self, detections, now):
        """Return fresh locked coordinates; keep lock separately during darkness.

        Debounce short dropouts before counting blink edges. Match with bounded
        velocity prediction, prioritize the locked track, and use blob size to
        reject unrelated objects. No predicted positions command the servos.
        """
        if self.last_time is not None and now <= self.last_time:
            self.reset()
        self.last_time = now
        self.tracks = [t for t in self.tracks if now - t['seen'] < self.lock_timeout]
        if self.locked is not None and not any(t is self.locked for t in self.tracks):
            self.locked = None

        assignments, used = {}, set()
        # Give the established target first choice; other tracks cannot steal it.
        order = sorted(range(len(self.tracks)), key=lambda i: self.tracks[i] is not self.locked)
        for i in order:
            track = self.tracks[i]
            px, py = self._prediction(track, now)
            speed = hypot(*track['velocity'])
            gap = now - track['seen']
            gate = min(140, self.match_radius + speed * min(gap, .2))
            if track is self.locked:
                gate = max(gate, 80)
            choices = []
            for j, point in enumerate(detections):
                if j in used:
                    continue
                ratio = max(point[2], 1) / max(track['point'][2], 1)
                if not .4 <= ratio <= 2.5:
                    continue
                distance = hypot(point[0] - px, point[1] - py)
                if distance <= gate:
                    # Do not steal a known steady distractor during an off phase.
                    owned = any(other is not track and other['on']
                                and now - other['seen'] < .05
                                and hypot(point[0] - other['point'][0],
                                          point[1] - other['point'][1]) < min(10, distance)
                                for other in self.tracks)
                    if not owned:
                        choices.append((distance + 8 * abs(ratio - 1), j))
            if choices:
                _, j = min(choices)
                assignments[i] = j
                used.add(j)

        for i, track in enumerate(self.tracks):
            present = i in assignments
            track['on'] = present
            if not present:
                if track['off_since'] is None:
                    track['off_since'] = now
                continue
            point = detections[assignments[i]]
            elapsed = now - track['seen']
            if elapsed > 0:
                vx = max(-1500, min(1500, (point[0] - track['point'][0]) / elapsed))
                vy = max(-1500, min(1500, (point[1] - track['point'][1]) / elapsed))
                track['velocity'] = (.5 * track['velocity'][0] + .5 * vx,
                                     .5 * track['velocity'][1] + .5 * vy)
            track['point'], track['seen'] = point, now
            # One/two dim frames at 90 FPS are not a real blink-off interval.
            if track['off_since'] is not None and now - track['off_since'] >= .025:
                if not track['rises'] or now - track['rises'][-1] >= .04:
                    track['rises'].append(now)
            track['off_since'] = None
            if self._matches_frequency(track, now, retained=track is self.locked):
                track['confirmed_at'] = now

        for j, point in enumerate(detections):
            if j not in used:
                self.tracks.append(dict(point=point, seen=now, on=True,
                                        velocity=(0., 0.), off_since=None,
                                        rises=deque([now], maxlen=9), confirmed_at=None))

        if self.locked is not None:
            if now - self.locked['confirmed_at'] >= self.lock_timeout:
                self.locked = None
        if self.locked is None:
            self.locked = next((t for t in self.tracks
                                if t['on'] and self._matches_frequency(t, now)), None)
        if self.locked is not None and self.locked['on']:
            return self.locked['point']
        return None
