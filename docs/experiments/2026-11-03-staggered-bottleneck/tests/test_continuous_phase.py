"""The two surviving physical lanes already have a valid staggered phase."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location("continuous_phase_rules", Path(os.environ.get(
    "RULES_PATH", "variants/phase5g_pure_formation/noa/native_rules.py")))
rules = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rules
spec.loader.exec_module(rules)


class ContinuousPhaseTests(unittest.TestCase):
    def car(self, key, x, lane):
        return rules.Vehicle(key, x, (lane + .5) * rules.LANE_WIDTH, 28.8, lane)

    def test_surviving_lane_offsets_do_not_flip_with_lane_count(self):
        self.assertEqual([rules._phase(i, 3) for i in range(3)], [0, 15, 0])
        self.assertEqual([rules._phase(i, 2) for i in range(2)], [0, 15])

    def test_same_actual_pair_has_continuous_error_at_preparation_boundary(self):
        left, middle = self.car(0, 700, 0), self.car(1, 685, 1)
        before = rules._pair_error(left, middle, 3, 701)[0]
        after = rules._pair_error(left, middle, 2, 640)[0]
        self.assertAlmostEqual(before, 0)
        self.assertAlmostEqual(after, before)

    def test_valid_staggered_heads_do_not_brake_to_change_layer(self):
        left, middle = self.car(0, 700, 0), self.car(1, 685, 1)
        for ego, peer in ((left, middle), (middle, left)):
            with self.subTest(lane=ego.lane):
                command, _ = rules.decide(ego, (peer,), rules.Memory(), "transform")
                self.assertAlmostEqual(command.speed, rules.CRUISE)
                self.assertAlmostEqual(command.target_x, ego.x)
                self.assertEqual(command.formation_state, 1)

    def test_passing_the_drop_does_not_flip_pair_again(self):
        left, middle = self.car(0, 1060, 0), self.car(1, 1045, 1)
        command, _ = rules.decide(left, (middle,), rules.Memory(), "transform")
        self.assertAlmostEqual(command.speed, rules.CRUISE)

    def test_noa_has_no_phase_target(self):
        left, middle = self.car(0, 700, 0), self.car(1, 685, 1)
        command, _ = rules.decide(left, (middle,), rules.Memory(), "noa")
        self.assertAlmostEqual(command.speed, rules.CRUISE)
        self.assertIsNone(command.target_x)
        self.assertEqual(command.formation_state, 0)


if __name__ == "__main__":
    unittest.main()
