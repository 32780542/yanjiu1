"""Gain .6 / raw limit 5 experiment with unchanged CTH and physical safety."""
import importlib.util
import math
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_C8_phase06_limit5_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('phase06_limit5_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class PhaseAmplitudeExperiment(unittest.TestCase):
    def phase_command(self, error):
        ego = car(1, 0., 0)
        peer = car(2, -r._phase(1, 3, ego.speed) + error, 1)
        return r.decide(ego, (peer,), r.Memory(), 'formation', None)[0]

    def test_small_error_matches_the_existing_gain06_response(self):
        for error in (-2., 2.):
            with self.subTest(error=error):
                command = self.phase_command(error)
                self.assertAlmostEqual(command.speed - r.CRUISE, .06 * error)

    def test_larger_error_has_more_budget_but_never_exceeds_one_mps(self):
        for error, expected in ((-30., -1.), (-10., -.6), (10., .6), (30., 1.)):
            with self.subTest(error=error):
                delta = self.phase_command(error).speed - r.CRUISE
                self.assertAlmostEqual(delta, expected)
                self.assertLessEqual(abs(delta), 1. + 1e-9)

    def test_noa_and_safe_cap_are_unchanged_and_cf_priority_gate_remains(self):
        slow, front = car(1, 100., 1, 20.), car(2, 120., 1, 20.)
        command, _ = r.decide(slow, (front,), r.Memory(), 'noa', None)
        self.assertEqual(command.reason, 'normal_overtake')
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.speed, 19.85)
        self.assertEqual(r.POSITION_GAIN, .3)
        self.assertEqual(r.PHASE_GAIN, .6)
        ego, stopped = car(1, 0., 0), car(2, 12., 0, 0.)
        peer = car(3, -r._phase(1, 3, ego.speed) + 4., 1)
        rows = (stopped, peer)
        self.assertAlmostEqual(r._following(ego, rows)[0], r._front_following(ego, rows)[0])
        cap = r.safe_speed(ego, rows)
        self.assertAlmostEqual(cap, math.sqrt(134.) - 2.)
        command, _ = r.decide(ego, rows, r.Memory(), 'formation', None)
        self.assertAlmostEqual(command.speed, cap)


if __name__ == '__main__':
    unittest.main()
