"""Run against RULES_PATH to compare the frozen baseline and one candidate."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest


path = Path(os.environ.get("RULES_PATH", "variants/phase5g_pure_formation/noa/native_rules.py"))
spec = importlib.util.spec_from_file_location("gap_projection_rules", path)
rules = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rules
spec.loader.exec_module(rules)


class GapProjectionTests(unittest.TestCase):
    def car(self, track, x, lane, speed=28.8):
        return rules.Vehicle(track, x, (lane + .5) * rules.LANE_WIDTH, speed, lane)

    def command(self, ego, rows, mode="transform"):
        return rules.decide(ego, rows, rules.Memory(), mode)[0]

    def test_already_feasible_insert_does_not_chase_gap_midpoint(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 1), self.car(2, 690, 1))
        command = self.command(ego, rows)
        self.assertEqual(command.lane, 1)
        self.assertAlmostEqual(command.target_x, ego.x)
        self.assertAlmostEqual(command.speed, ego.speed)

    def test_projection_chooses_nearest_safe_boundary(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 1), self.car(2, 695, 1))
        command = self.command(ego, rows)
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.target_x, 703.0)

    def test_closing_rear_is_included_in_one_second_interval(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 1), self.car(2, 690, 1, 33.3))
        command = self.command(ego, rows)
        self.assertAlmostEqual(command.target_x, 702.5)

    def test_ordinary_noa_keeps_its_existing_gap_target(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 1), self.car(2, 690, 1))
        command = self.command(ego, rows, "noa")
        self.assertAlmostEqual(command.target_x, 710.0)
        self.assertEqual(command.formation_state, 0)

    def test_track_relabeling_does_not_choose_a_different_position(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 1), self.car(2, 690, 1))
        expected = self.command(ego, rows)
        actual = self.command(ego, (self.car(901, 690, 1), self.car(404, 730, 1)))
        self.assertEqual((actual.speed, actual.lane, actual.target_x),
                         (expected.speed, expected.lane, expected.target_x))


if __name__ == "__main__":
    unittest.main()
