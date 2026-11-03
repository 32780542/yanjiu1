"""Behavior examples for forward-only C; FORWARD_RULES selects a frozen source."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C200.py'))
spec = importlib.util.spec_from_file_location('forward_rules_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **kw)


class ForwardGapBehavior(unittest.TestCase):
    def decide(self, ego, rows, memory=None, mode='transform', drop=1000.):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, mode, drop)

    def test_retained_car_never_waits_for_a_held_reference_behind_it(self):
        ego, ending = car(1, 1030., 0, 0.), car(2, 998.5, 2, 0.)
        command, _ = self.decide(ego, (ending,), r.Memory(front=2, transforming=True))
        self.assertGreater(command.speed, 0.)
        self.assertNotEqual(command.reference, ending.track)

    def test_too_close_stopped_ending_does_not_stop_receiver(self):
        ego, ending = car(1, 995., 1, 0.), car(2, 998.5, 2, 0.)
        command, _ = self.decide(ego, (ending,))
        self.assertGreater(command.speed, 0.)
        self.assertNotEqual(command.reference, ending.track)

    def test_feasible_ending_is_a_whole_cth_virtual_front(self):
        ego, ending, front = car(1, 880., 1), car(2, 895., 2), car(3, 930., 1)
        command, _ = self.decide(ego, (front, ending))
        self.assertEqual(command.reference, ending.track)
        self.assertAlmostEqual(command.target_x, ending.x - r.desired_spacing(ego.speed))

    def test_cascade_requires_two_current_executable_corridors(self):
        ego, middle, ending = car(1, 865., 0), car(2, 880., 1), car(3, 895., 2)
        command, _ = self.decide(ego, (middle, ending, car(4, 930., 0), car(5, 930., 1)))
        self.assertEqual(command.reference, middle.track)
        self.assertAlmostEqual(command.target_x, middle.x - r.desired_spacing(ego.speed))

    def test_blocked_middle_corridor_rejects_cascade_yield(self):
        ego, middle, ending = car(1, 865., 0), car(2, 880., 1), car(3, 895., 2)
        blocker = car(4, 884., 0)
        command, _ = self.decide(ego, (middle, ending, blocker, car(5, 930., 1)))
        self.assertEqual(command.reference, blocker.track)

    def test_front_boundary_too_close_also_rejects_virtual_insertion(self):
        ego, ending, front = car(1, 880., 1), car(2, 895., 2), car(3, 899., 1)
        command, _ = self.decide(ego, (front, ending))
        self.assertEqual(command.reference, front.track)

    def test_real_vacancy_is_front_minus_d_not_gap_midpoint(self):
        ego, front = car(1, 800., 1), car(2, 820., 1)
        adjacent_front, rear = car(3, 850., 0), car(4, 760., 0)
        command, _ = self.decide(ego, (front, adjacent_front, rear))
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reference, adjacent_front.track)
        self.assertAlmostEqual(command.target_x, adjacent_front.x - r.desired_spacing(ego.speed))
        self.assertNotAlmostEqual(command.target_x, (adjacent_front.x + rear.x) / 2)

    def test_vacancy_requires_rear_cth_space_not_only_eight_meters(self):
        ego, front = car(1, 800., 1), car(2, 820., 1)
        adjacent_front, rear = car(3, 850., 0), car(4, 800., 0)
        command, _ = self.decide(ego, (front, adjacent_front, rear))
        self.assertIsNone(command.lane)
        self.assertNotEqual(command.reference, adjacent_front.track)

    def test_slot_can_be_approached_until_the_predicted_corridor_is_clear(self):
        ego, own_front = car(1, 800., 1), car(2, 815., 1)
        adjacent_front, rear = car(3, 830., 0, 0.), car(4, 740., 0, 0.)
        command, memory = self.decide(ego, (own_front, adjacent_front, rear))
        self.assertIsNone(command.lane)
        self.assertEqual(command.reference, adjacent_front.track)
        slow_ego = car(1, 800., 1, 10.)
        command, _ = self.decide(slow_ego, (own_front, adjacent_front, rear), memory)
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reference, adjacent_front.track)

    def test_entry_pitch_is_twice_eight_at_low_speed(self):
        ego, front = car(1, 80., 1, 0.), car(2, 90., 1, 0.)
        adjacent_front, rear = car(3, 104., 0, 0.), car(4, 72., 0, 0.)
        command, _ = self.decide(ego, (front, adjacent_front, rear), drop=100.)
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.target_x, 104. - 2 * r.CLEARANCE)

    def test_settled_post_merge_spacing_returns_to_original_cth(self):
        ego, front = car(1, 1020., 0, 0.), car(2, 1040., 0, 0.)
        command, _ = self.decide(ego, (front,), r.Memory(transforming=True))
        self.assertAlmostEqual(command.target_x, front.x - r.desired_spacing(ego.speed))

    def test_formation_closes_visible_hole_beyond_fifty_meters(self):
        ego, front = car(1, 800., 0), car(2, 950., 0)
        command, _ = self.decide(ego, (front,), mode='formation', drop=None)
        self.assertEqual(command.reference, front.track)
        self.assertAlmostEqual(command.target_x, front.x - r.desired_spacing(ego.speed))
        self.assertGreater(command.speed, r.CRUISE)

    def test_ending_car_does_not_later_chase_an_adjacent_lane_color(self):
        ego, front = car(1, 900., 2), car(2, 950., 1)
        command, memory = self.decide(ego, (front,))
        self.assertEqual(command.lane, 1)
        done = car(1, 920., 1)
        command, _ = self.decide(done, (car(2, 940., 1), car(3, 960., 0), car(4, 850., 0)), memory)
        self.assertIsNone(command.lane)


if __name__ == '__main__':
    unittest.main()
