"""Physical predecessor following and two-lane staggered transformation."""
import unittest
from dataclasses import replace
from noa import native_rules as r


def car(track, x, lane, speed=28.8, vy=0.):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, vy)


class ChainTransformTests(unittest.TestCase):
    def call(self, ego, rows, memory=None, drop=1000):
        return r.decide(ego, rows, memory or r.Memory(), 'transform', drop)

    def test_observed_front_folding_starts_following_before_own_road_view(self):
        ego, leader = car(0, 700, 2), car(7, 820, 2, vy=-.8)
        command, memory = self.call(ego, (leader,))
        self.assertEqual(command.lane, 1)
        self.assertTrue(memory.transforming)

    def test_chain_target_is_half_a_time_gap_behind_the_actual_predecessor(self):
        ego, front = car(0, 810, 1, 20), car(7, 840, 0, 20)
        command, _ = self.call(ego, (front,))
        self.assertEqual(command.reference, 7)
        self.assertAlmostEqual(command.target_x, 840 - (5.5 + .85 * 20) / 2)
        self.assertIsNone(command.lane)

    def test_same_lane_predecessor_calls_for_the_other_retained_lane(self):
        ego, front = car(0, 810, 1), car(7, 840, 1)
        command, _ = self.call(ego, (front,))
        self.assertEqual(command.lane, 0)

    def test_ending_vehicle_reaches_lane_zero_in_two_adjacent_moves(self):
        ego, front = car(0, 810, 2), car(7, 840, 1)
        first, memory = self.call(ego, (front,))
        self.assertEqual(first.lane, 1)
        arrived = replace(ego, lane=1, y=1.5 * r.LANE_WIDTH)
        second, _ = self.call(arrived, (front,), memory)
        self.assertEqual(second.lane, 0)

    def test_the_held_physical_predecessor_survives_its_lane_change(self):
        ego, front = car(0, 810, 1), car(7, 840, 0)
        _, memory = self.call(ego, (front,))
        changed = replace(front, lane=1, y=1.5 * r.LANE_WIDTH)
        command, _ = self.call(ego, (changed,), memory)
        self.assertEqual(command.reference, 7)
        self.assertEqual(command.lane, 0)


if __name__ == '__main__':
    unittest.main()
