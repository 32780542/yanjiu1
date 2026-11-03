"""Gain-only experiment for staggered and parallel state-contract sources."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_C8_phase06_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('phase06_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class PhaseGainExperiment(unittest.TestCase):
    def test_small_phase_error_doubles_control_increment(self):
        ego = car(1, 0., 0)
        for error in (-2., 2.):
            with self.subTest(error=error):
                peer = car(2, -r._phase(1, 3, ego.speed) + error, 1)
                command, _ = r.decide(ego, (peer,), r.Memory(), 'formation', None)
                self.assertAlmostEqual(command.speed - r.CRUISE, .06 * error)

    def test_zero_phase_and_real_cth_equilibrium_are_unchanged(self):
        ego = car(1, 0., 0)
        front = car(2, r.desired_spacing(ego.speed), 0)
        peer = car(3, -r._phase(1, 3, ego.speed), 1)
        command, _ = r.decide(ego, (front, peer), r.Memory(), 'formation', None)
        self.assertAlmostEqual(command.speed, r.CRUISE)
        self.assertIsNone(command.lane)

    def test_large_phase_saturates_and_noa_remains_original(self):
        ego = car(1, 0., 0)
        for error in (-30., 30.):
            with self.subTest(error=error):
                peer = car(2, -r._phase(1, 3, ego.speed) + error, 1)
                command, _ = r.decide(ego, (peer,), r.Memory(), 'formation', None)
                expected = r.CRUISE + (1 if error > 0 else -1) * r.SPEED_RELAXATION * 2
                self.assertAlmostEqual(command.speed, expected)
        self.assertEqual(r.POSITION_GAIN, .3)
        slow, front = car(1, 100., 1, 20.), car(2, 120., 1, 20.)
        command, _ = r.decide(slow, (front,), r.Memory(), 'noa', None)
        self.assertEqual(command.reason, 'normal_overtake')
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.speed, 19.85)


if __name__ == '__main__':
    unittest.main()
