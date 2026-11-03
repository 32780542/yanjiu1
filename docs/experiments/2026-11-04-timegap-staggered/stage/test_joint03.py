"""Joint .3 feedback experiment: remove only the opposite-direction phase gate."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_C8_joint03_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('joint03_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class JointFeedback(unittest.TestCase):
    def test_negative_phase_corrects_geometry_during_forward_catchup(self):
        ego, front = car(1, 0., 0, 20.), car(2, 30., 0, 22.)
        peer = car(3, -r.desired_spacing(20.) / 2 - 4., 1, 20.)
        rows = (front, peer)
        cth = r._front_following(ego, rows)[0]
        self.assertGreater(cth, ego.speed)
        command, _ = r.decide(ego, rows, r.Memory(), 'formation', None)
        self.assertAlmostEqual(command.speed, cth - .12)

    def test_positive_phase_during_braking_stays_inside_common_safe_speed(self):
        ego, front = car(1, 0., 0, 28.8), car(2, 12., 0, 0.)
        peer = car(3, -r.desired_spacing(28.8) / 2 + 4., 1, 28.8)
        rows = (front, peer)
        cth = r._front_following(ego, rows)[0]
        raw = r._following(ego, rows)[0]
        cap = r.safe_speed(ego, rows)
        command, _ = r.decide(ego, rows, r.Memory(), 'formation', None)
        self.assertLess(cth, ego.speed)
        self.assertLess(cap, raw)
        self.assertAlmostEqual(command.speed, cap)
        self.assertAlmostEqual(raw, cth + .12)

    def test_zero_error_and_noa_remain_unchanged(self):
        ego = car(1, 0., 0, 28.8)
        rows = (car(2, r.desired_spacing(28.8), 0, 28.8),
                car(3, -r.desired_spacing(28.8) / 2, 1, 28.8))
        command, _ = r.decide(ego, rows, r.Memory(), 'formation', None)
        self.assertAlmostEqual(command.speed, 28.8)
        self.assertIsNone(command.lane)
        slow, front = car(1, 100., 1, 20.), car(2, 120., 1, 20.)
        command, _ = r.decide(slow, (front,), r.Memory(), 'noa', None)
        self.assertEqual(command.reason, 'normal_overtake')
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.speed, 19.85)
        self.assertEqual(r.POSITION_GAIN, .3)


if __name__ == '__main__':
    unittest.main()
