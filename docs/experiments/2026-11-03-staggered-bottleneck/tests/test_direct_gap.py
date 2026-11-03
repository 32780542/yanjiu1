"""Direct local gap control removes waiting for a hypothetical distant helper."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("direct_gap_rules", Path(os.environ.get(
    "RULES_PATH", "variants/phase5g_pure_formation/noa/native_rules.py")))
rules = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rules
spec.loader.exec_module(rules)


class DirectGapTests(unittest.TestCase):
    def car(self, key, x, lane, speed=28.8):
        return rules.Vehicle(key, x, (lane + .5) * rules.LANE_WIDTH, speed, lane)

    def test_ending_follower_adjusts_its_own_actual_receiving_gap(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 2), self.car(2, 704, 1), self.car(3, 675, 1))
        command, _ = rules.decide(ego, rows, rules.Memory(), "transform")
        self.assertEqual(command.reason, "approach_gap")
        self.assertAlmostEqual(command.target_x, (704 + 675) / 2)
        self.assertLess(command.speed, rules.CRUISE)

    def test_receiver_keeps_actual_front_following_without_phantom_yield(self):
        ego = self.car(0, 700, 1)
        rows = (self.car(1, 740, 1), self.car(2, 720, 2), self.car(3, 700, 0))
        command, _ = rules.decide(ego, rows, rules.Memory(joining=True), "transform")
        expected = rules._front_following(ego, rows)
        self.assertEqual(command.reason, "join_follow")
        self.assertAlmostEqual(command.speed, expected[0])
        self.assertEqual(command.reference, expected[2])

    def test_blocked_middle_car_does_not_commit_to_a_distant_helper_role(self):
        ego = self.car(0, 704, 1)
        rows = (self.car(1, 730, 2), self.car(2, 700, 2),
                self.car(3, 675, 1), self.car(4, 704, 0))
        command, memory = rules.decide(ego, rows, rules.Memory(), "transform")
        self.assertNotIn(command.reason, ("make_room", "prepare_room", "open_gap"))
        self.assertIsNone(command.lane)
        self.assertIsNone(memory.lane_target)

    def test_clear_ending_car_still_performs_a_real_necessary_merge(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 1), self.car(2, 670, 1))
        command, memory = rules.decide(ego, rows, rules.Memory(), "transform")
        self.assertEqual((command.lane, command.reason), (1, "merge"))
        self.assertEqual(memory.lane_target, 1)

    def test_true_nearest_front_and_hard_safety_remain(self):
        ego, front = self.car(0, 700, 1), self.car(1, 710, 1, 0)
        command, _ = rules.decide(ego, (front,), rules.Memory(), "transform")
        self.assertLessEqual(command.speed, rules.safe_speed(ego, (front,)))


if __name__ == "__main__":
    unittest.main()
