"""User-facing time gap, road visibility and reactive-driving requirements."""
from math import sqrt
import unittest
from unittest.mock import patch

from noa import native_rules as r


def car(track, x, lane=0, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class UserTimeGapTests(unittest.TestCase):
    def decide(self, ego, rows=(), mode='noa', drop=1000):
        return r.decide(ego, rows, r.Memory(), mode, drop)[0]

    def test_headway_is_exactly_point_eighty_five(self):
        self.assertEqual(r.HEADWAY, .85)

    def test_cross_lane_equilibrium_scales_with_time_gap(self):
        for speed in (5., 10., 20., 28.8):
            with self.subTest(speed=speed):
                distance = 5.5 + .85 * speed
                ego = car(0, 100, speed=speed)
                peer = car(1, 100 - distance / 2, lane=1, speed=speed)
                error, _ = r._pair_error(ego, peer, 3)
                self.assertAlmostEqual(error, 0.)

    def test_pair_error_is_antisymmetric_at_unequal_speeds(self):
        ego, peer = car(0, 100, speed=10), car(1, 93, lane=1, speed=16)
        self.assertAlmostEqual(r._pair_error(ego, peer, 3)[0],
                               -r._pair_error(peer, ego, 3)[0])

    def test_invisible_bottleneck_does_not_change_noa_motion(self):
        ego = car(0, 700, lane=2)
        self.assertEqual(self.decide(ego, drop=1000), self.decide(ego, drop=None))

    def test_shared_warning_changes_when_the_road_is_known(self):
        ego = car(0, 700, lane=2)
        with patch.object(r, 'ROAD_PREVIEW', 200., create=True):
            direct = self.decide(ego)
        with patch.object(r, 'ROAD_PREVIEW', 300., create=True):
            warned = self.decide(ego)
        self.assertIsNone(direct.lane)
        self.assertEqual(warned.lane, 1)

    def test_noa_waits_for_a_gap_without_tracking_its_midpoint(self):
        ego = car(0, 810, lane=2)
        peer = car(1, 810, lane=1)
        command = self.decide(ego, (peer,))
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.speed, r.CRUISE)
        self.assertIsNone(command.target_x)

    def test_blocked_ending_lane_uses_the_physical_stop_line(self):
        ego = car(0, 995, lane=2, speed=10)
        peer = car(1, 995, lane=1, speed=10)
        stop_cap = sqrt((10 * .2) ** 2 + 2 * 10 * (1000 - 995 - 1.5)) - 10 * .2
        for mode in ('noa', 'transform'):
            with self.subTest(mode=mode):
                self.assertLessEqual(self.decide(ego, (peer,), mode).speed, stop_cap)

    def test_noa_retains_active_overtaking_and_zero_formation_state(self):
        ego, front = car(0, 400, lane=1, speed=20), car(1, 425, lane=1, speed=18)
        command = self.decide(ego, (front,), drop=None)
        self.assertIn(command.lane, (0, 2))
        self.assertEqual(command.formation_state, 0)


if __name__ == '__main__':
    unittest.main()
