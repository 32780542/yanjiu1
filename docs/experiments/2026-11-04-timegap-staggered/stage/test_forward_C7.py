"""Low-speed long-hole phase uses the same relaxed free-driving baseline."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C7_200.py'))
spec = importlib.util.spec_from_file_location('forward_C7_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class C7LongHole(unittest.TestCase):
    def check_phase(self, sign):
        for speed in (0., 10., 28.8):
            with self.subTest(speed=speed, sign=sign):
                ego, front = car(1, 0., 0, speed), car(2, 80., 0, 28.8)
                peer = car(3, -r.desired_spacing(speed) / 2 + sign * 5., 1, speed)
                rows = (front, peer)
                formed = r._following(ego, rows)[0]
                free = r._request(ego, ego.x, r.CRUISE)
                phase = formed - free
                self.assertGreater(sign * phase, 0.)
                expected = r._front_following(ego, rows, 200.)[0] + phase
                command, _ = r.decide(ego, rows, r.Memory(), 'formation', None)
                self.assertEqual(command.reference, front.track)
                self.assertAlmostEqual(command.speed, expected)
                self.assertGreater(command.speed, speed)

    def test_positive_phase_at_standstill_low_speed_and_cruise(self):
        self.check_phase(1)

    def test_negative_phase_at_standstill_low_speed_and_cruise(self):
        self.check_phase(-1)


def load_tests(loader, tests, pattern):
    import test_forward_C6 as shared
    shared.r = r
    tests.addTests(loader.loadTestsFromModule(shared))
    return tests


if __name__ == '__main__':
    unittest.main()
