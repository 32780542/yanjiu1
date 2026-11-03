"""B behavior checks; TRIPLET_RULES can select the frozen A source for the red run."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('TRIPLET_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/triplet_B200.py'))
spec = importlib.util.spec_from_file_location('triplet_rules_under_test', SOURCE)
rules = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rules
spec.loader.exec_module(rules)


def car(track, x, lane, speed=28.8, **kwargs):
    return rules.Vehicle(track, x, (lane + .5) * rules.LANE_WIDTH, speed, lane, **kwargs)


def unit(x=900., track_offset=0):
    return (car(41 + track_offset, x, 0),
            car(17 + track_offset, x - rules.GAP / 2, 1),
            car(83 + track_offset, x, 2))


def front_unit(x, tail_lane):
    d = rules.GAP / 2
    return (car(101, x, tail_lane), car(102, x + d, 1 - tail_lane),
            car(103, x + 2 * d, tail_lane))


class TripletBehavior(unittest.TestCase):
    def decide(self, ego, others, memory=None, drop_x=1000.):
        return rules.decide(ego, others, rules.Memory() if memory is None else memory,
                            'transform', drop_x)

    def test_leading_alpha_moves_middle_left(self):
        a, b, c = unit()
        command, _ = self.decide(b, (a, c))
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.target_x, a.x - rules.GAP)

    def test_alpha_ending_car_tracks_half_spacing_before_merging(self):
        a, b, c = unit()
        command, _ = self.decide(c, (a, b))
        self.assertEqual(command.lane, 1)
        self.assertIsNotNone(command.target_x)
        self.assertAlmostEqual(command.target_x, a.x - rules.GAP / 2)

    def test_beta_after_zero_tail_keeps_middle_in_lane_one(self):
        a, b, c = unit()
        command, _ = self.decide(b, (a, c, *front_unit(930., 0)))
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.target_x, c.x - rules.GAP)

    def test_alpha_after_one_tail_moves_middle_to_zero(self):
        a, b, c = unit()
        command, _ = self.decide(b, (a, c, *front_unit(930., 1)))
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.target_x, a.x - rules.GAP)

    def test_completed_visible_front_shape_activates_without_road_flag(self):
        a, b, c = unit(600.)
        command, _ = self.decide(b, (a, c, *front_unit(630., 0)), drop_x=1000.)
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.target_x, c.x - rules.GAP)

    def test_missing_outer_car_does_not_assign_middle_left(self):
        _, b, c = unit()
        command, _ = self.decide(b, (c,))
        self.assertIsNone(command.lane)

    def test_observed_own_ending_peer_motion_propagates_without_road_flag(self):
        a, b, c = unit(600.)
        _, memory = self.decide(b, (a, c), drop_x=1000.)
        c_moving = rules.Vehicle(c.track, c.x, c.y - .2, c.speed, 2, vy=-.5)
        command, _ = self.decide(b, (a, c_moving), memory, drop_x=1000.)
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.target_x, a.x - rules.GAP)

    def test_necessary_merge_while_waiting_retains_observed_unit(self):
        a, b, c = unit()
        a_front, b_front, c_front = unit(930., track_offset=100)
        command, memory = self.decide(c, (a, b, a_front, b_front, c_front))
        self.assertEqual(command.lane, 1)
        c_done = car(c.track, c.x, 1)
        command, _ = self.decide(c_done, (a, b, *front_unit(930., 0)), memory)
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.target_x, 930. - rules.GAP / 2)
        self.assertEqual(command.reference, 101)

    def test_held_alpha_keeps_whole_spacing_after_peers_change_lanes(self):
        a, b, c = unit()
        _, memory = self.decide(b, (a, c))
        b_done = car(b.track, a.x - rules.GAP, 0)
        c_done = car(c.track, a.x - rules.GAP / 2, 1)
        command, _ = self.decide(b_done, (a, c_done), memory)
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.target_x, a.x - rules.GAP)

    def test_lost_peer_does_not_transfer_held_orientation_to_replacement(self):
        a, b, c = unit()
        _, memory = self.decide(b, (a, c))
        replacement = car(999, c.x, 2)
        command, _ = self.decide(b, (a, replacement), memory, drop_x=2000.)
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.target_x, b.x)

    def test_actual_same_lane_front_remains_a_speed_constraint(self):
        a, b, c = unit()
        front = car(212, b.x + 6., 1, speed=12.)
        command, _ = self.decide(b, (a, c, front))
        following = rules._front_following(b, (a, c, front))[0]
        self.assertLessEqual(command.speed, following)

    def test_track_renaming_and_neighbor_order_do_not_change_action(self):
        a, b, c = unit()
        original, _ = self.decide(b, (a, c))
        a2, b2, c2 = (car(8000, a.x, 0), car(2, b.x, 1), car(3, c.x, 2))
        renamed, _ = self.decide(b2, (c2, a2))
        self.assertEqual(original.lane, renamed.lane)
        self.assertAlmostEqual(original.target_x, renamed.target_x)
        self.assertAlmostEqual(original.speed, renamed.speed)


if __name__ == '__main__':
    unittest.main()
