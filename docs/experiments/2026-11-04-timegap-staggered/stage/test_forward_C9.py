"""C9 replaces ending-based cascade by an observable front-side insertion gap."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C9_200.py'))
spec = importlib.util.spec_from_file_location('forward_C9_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **kw)


class C9ReceivableGeometry(unittest.TestCase):
    def decide(self, ego, rows, known=True):
        return r.decide(ego, rows, r.Memory(), 'transform', 1000. if known else None)[0]

    def test_known_front_space_opens_rear_gap_only_with_current_safe_corridor(self):
        for rear_gap in (22., 3.5):
            with self.subTest(rear_gap=rear_gap):
                ego = car(1, 880., 0)
                peer = car(2, ego.x + rear_gap, 1)
                actual = car(3, peer.x + 32., 0)
                command = self.decide(ego, (peer, actual))
                if rear_gap >= r.CLEARANCE:
                    self.assertEqual(command.reference, peer.track)
                    self.assertAlmostEqual(command.target_x, peer.x - r._entry_spacing(ego.speed))
                    self.assertLess(command.speed, r.CRUISE)
                else:
                    self.assertEqual(command.reference, actual.track)

    def test_insufficient_front_space_rejects_old_cascade_and_uses_entry_pitch(self):
        cases = ((880., 895., 910., 28.8), (880., 892., 904., 0.))
        for ego_x, peer_x, actual_x, speed in cases:
            with self.subTest(speed=speed):
                ego, peer = car(1, ego_x, 0, speed), car(2, peer_x, 1, speed)
                actual = car(3, actual_x, 0, speed)
                ending = car(4, actual_x, 2, speed)
                command = self.decide(ego, (peer, actual, ending))
                self.assertEqual(command.reference, actual.track)

    def test_unknown_needs_actual_motion_and_empty_front_interval_must_be_visible(self):
        ego, peer, actual = car(1, 880., 0), car(2, 902., 1), car(3, 934., 0)
        stationary = self.decide(ego, (peer, actual), known=False)
        self.assertEqual(stationary.reference, actual.track)
        moving = self.decide(ego, (car(2, 902., 1, vy=-.4), actual), known=False)
        self.assertEqual(moving.reference, peer.track)
        near_empty = self.decide(ego, (peer,))
        self.assertEqual(near_empty.reference, peer.track)
        outside_interval = self.decide(ego, (car(2, 1065., 1),))
        self.assertIsNone(outside_interval.reference)


def load_tests(loader, tests, pattern):
    import test_forward_C8 as shared
    shared.r = r
    tests.addTests(loader.loadTestsFromModule(shared))
    return tests


if __name__ == '__main__':
    unittest.main()
