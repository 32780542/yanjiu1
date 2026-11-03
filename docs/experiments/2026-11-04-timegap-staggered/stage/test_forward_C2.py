"""C2 differences plus the twelve still-applicable frozen C behavior cases."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C2_200.py'))
spec = importlib.util.spec_from_file_location('forward_C2_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **kw)


class C2Differences(unittest.TestCase):
    def decide(self, ego, rows, memory=None, mode='formation', drop=None):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, mode, drop)

    def test_positive_local_phase_preserves_the_public_A_following_output(self):
        for speed in (20., 28.8):
            with self.subTest(speed=speed):
                d = r.desired_spacing(speed)
                ego, front, peer = car(1, 0., 0, speed), car(2, d, 0, speed), car(3, -d / 2 + 5., 1, speed)
                expected = r._following(ego, (front, peer))
                command, _ = self.decide(ego, (front, peer))
                self.assertGreater(expected[0], r._front_following(ego, (front, peer))[0])
                self.assertAlmostEqual(command.speed, expected[0])

    def test_negative_phase_is_not_cancelled_again_by_far_hole_closure(self):
        ego, front, peer = car(1, 0., 0), car(2, 80., 0), car(3, -20., 1)
        phase = r._following(ego, (front, peer))[0] - r.CRUISE
        self.assertLess(phase, 0.)
        expected = r._front_following(ego, (front, peer), 200.)[0] + phase
        command, _ = self.decide(ego, (front, peer))
        self.assertAlmostEqual(command.speed, expected)
        self.assertGreater(command.speed, r.CRUISE)

    def test_positive_phase_is_not_clipped_to_far_front_cth_request(self):
        ego, front, peer = car(1, 0., 0), car(2, 80., 0), car(3, -10., 1)
        phase = r._following(ego, (front, peer))[0] - r.CRUISE
        self.assertGreater(phase, 0.)
        expected = r._front_following(ego, (front, peer), 200.)[0] + phase
        command, _ = self.decide(ego, (front, peer))
        self.assertAlmostEqual(command.speed, expected)

    def test_former_ending_vehicle_uses_the_same_real_slot_as_any_receiver(self):
        ego, front = car(1, 900., 2), car(2, 950., 1)
        command, memory = self.decide(ego, (front,), mode='transform', drop=1000.)
        self.assertEqual(command.lane, 1)
        done = car(1, 920., 1)
        command, _ = self.decide(done, (car(2, 940., 1), car(3, 960., 0), car(4, 850., 0)),
                                  memory, mode='transform', drop=1000.)
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reference, 3)
        self.assertAlmostEqual(command.target_x, 960. - r.desired_spacing(done.speed))

    def test_former_ending_vehicle_still_requires_full_real_rear_space(self):
        ego = car(1, 900., 2)
        _, memory = self.decide(ego, (car(2, 950., 1),), mode='transform', drop=1000.)
        done = car(1, 920., 1)
        command, _ = self.decide(done, (car(2, 940., 1), car(3, 960., 0), car(4, 920., 0)),
                                  memory, mode='transform', drop=1000.)
        self.assertIsNone(command.lane)


def load_tests(loader, tests, pattern):
    import test_forward_C as shared
    shared.r = r
    for case in loader.loadTestsFromTestCase(shared.ForwardGapBehavior):
        if case._testMethodName != 'test_ending_car_does_not_later_chase_an_adjacent_lane_color':
            tests.addTest(case)
    return tests


if __name__ == '__main__':
    unittest.main()
