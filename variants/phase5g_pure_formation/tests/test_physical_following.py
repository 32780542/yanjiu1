"""Common physical following and preserved low-speed counterexamples for C8."""
from dataclasses import replace
from math import sqrt
import unittest

from noa import native_rules as r


def car(track, x, lane=0, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class PhysicalFollowingTests(unittest.TestCase):
    def command(self, ego, rows=(), mode='transform', drop=None):
        return r.decide(ego, tuple(rows), r.Memory(), mode, drop)[0]

    def test_all_modes_obey_the_same_stopped_front_safety_limit(self):
        ego, front = car(0, 100, speed=25), car(1, 110, speed=0)
        cap = sqrt(2 ** 2 + 2 * 10 * (10 - 4 - 1.5)) - 2
        for mode in ('noa', 'formation', 'transform'):
            with self.subTest(mode=mode):
                self.assertAlmostEqual(r.safe_speed(ego, (front,)), cap)
                self.assertLessEqual(self.command(ego, (front,), mode).speed, cap)

    def test_a_straddling_ego_is_protected_in_both_occupied_lanes(self):
        ego = replace(car(0, 100), y=3.3, vy=-3.3)
        for lane in (0, 1):
            with self.subTest(lane=lane):
                front = car(1, 110, lane, 0)
                self.assertLess(r.safe_speed(ego, (front,)), 10)
                self.assertLessEqual(self.command(ego, (front,)).speed, r.safe_speed(ego, (front,)))

    def test_parked_adjacent_body_is_not_a_same_lane_braking_reference(self):
        ego, adjacent = car(0, 100), car(1, 110, 1, 0)
        self.assertEqual(r.safe_speed(ego, (adjacent,)), r.MAX_SPEED)
        self.assertGreater(self.command(ego, (adjacent,), mode='formation').speed, 20)

    def test_far_visible_front_is_followed_without_the_old_low_speed_zero_artifact(self):
        # C6's 50-200 m branch subtracted 28.8 from an already relaxed speed.
        ego, front = car(0, 900.951, 1, 0), car(1, 1078.776, 1, 20)
        expected = .2 * (20 + .3 * (1078.776 - 5.5 - 900.951))
        command = self.command(ego, (front,))
        self.assertAlmostEqual(command.speed, expected)
        self.assertGreater(command.speed, 10)
        self.assertEqual(command.reference, front.track)

    def test_far_hole_with_a_phase_peer_keeps_a_positive_low_speed_request(self):
        ego, front = car(0, 900, 1, 0), car(1, 1050, 1, 20)
        peer = car(2, 895, 0, 0)
        command = self.command(ego, (front, peer))
        self.assertGreater(command.speed, 5)
        self.assertLessEqual(command.speed, r.safe_speed(ego, (front, peer)))

    def test_compatible_phase_is_kept_but_cannot_reverse_a_real_front_correction(self):
        ego, front = car(0, 100), car(1, 125)
        base = self.command(ego, (front,), mode='formation').speed
        opposed = self.command(ego, (front, car(2, 100, 1)), mode='formation').speed
        compatible = self.command(ego, (front, car(2, 70, 1)), mode='formation').speed
        self.assertLess(base, ego.speed)
        self.assertAlmostEqual(opposed, base)
        self.assertLessEqual(compatible, base)

    def test_closing_corridor_is_rejected_using_relative_speed(self):
        ego, rear = car(0, 100, 2, 10), car(1, 88, 1, 30)
        self.assertFalse(r._clear(ego, (rear,), 1))
        self.assertIsNone(self.command(ego, (rear,), drop=200).lane)

    def test_low_speed_entry_slot_keeps_two_unchanged_eight_metre_clearances(self):
        self.assertEqual(r._entry_spacing(0), 16)
        self.assertEqual(r._entry_spacing(5), 16)
        self.assertAlmostEqual(r._entry_spacing(20), 5.5 + .85 * 20)


if __name__ == '__main__':
    unittest.main()
