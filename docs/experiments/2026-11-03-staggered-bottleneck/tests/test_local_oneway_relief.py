"""F contracts; default target is frozen E, not production TM."""
from dataclasses import asdict, replace
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import sys
import unittest


REPO = Path(__file__).resolve().parents[4]
E_PATH = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
E_SHA = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
assert hashlib.sha256(E_PATH.read_bytes()).hexdigest() == E_SHA


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load("relief_frozen_e", E_PATH)
rules = load("local_oneway_relief_rules", os.environ["RULES_PATH"]) if os.environ.get("RULES_PATH") else baseline


class LocalOnewayReliefTests(unittest.TestCase):
    def car(self, key, x, lane, speed=28.8, module=rules):
        return module.Vehicle(key, x, (lane + .5) * module.LANE_WIDTH, speed, lane)

    def decide(self, ego, rows=(), memory=None):
        return rules.decide(ego, rows, memory or rules.Memory(), "transform")

    def test_middle_ego_relief_uses_its_own_clear_gap_and_future_load(self):
        ego, incoming = self.car(0, 700, 1), self.car(1, 715, 2)
        command, memory = self.decide(ego, (incoming,))
        self.assertEqual((command.lane, command.reason), (0, "local_relief"))
        self.assertEqual(memory.lane_target, 0)
        self.assertTrue(memory.joining)

    def test_pressure_counts_only_the_fixed_ego_window_including_boundaries(self):
        ego = self.car(0, 700, 1)
        for position in (640, 730):
            with self.subTest(included=position):
                self.assertEqual(self.decide(ego, (self.car(1, position, 2),))[0].lane, 0)
        for position in (639.9, 730.1):
            with self.subTest(excluded=position):
                command, memory = self.decide(ego, (self.car(1, position, 2),))
                self.assertIsNone(command.lane)
                self.assertIsNone(memory.lane_target)

    def test_no_relief_without_future_pressure(self):
        ego = self.car(0, 700, 1)
        command, memory = self.decide(ego)
        self.assertIsNone(command.lane)
        self.assertIsNone(memory.lane_target)
        self.assertIsNone(memory.gap)

    def test_blocked_relief_does_not_bind_gap_or_prepare_by_changing_speed(self):
        ego = self.car(0, 700, 1)
        rows = (self.car(1, 715, 2), self.car(2, 685, 2), self.car(3, 700, 0))
        command, memory = self.decide(ego, rows)
        prior, _ = baseline.decide(baseline.Vehicle(**asdict(ego)),
                                  tuple(baseline.Vehicle(**asdict(c)) for c in rows),
                                  baseline.Memory(), "transform")
        self.assertIsNone(command.lane)
        self.assertIsNone(memory.lane_target)
        self.assertIsNone(memory.gap)
        self.assertEqual(command.speed, prior.speed)

    def test_closing_left_rear_fails_original_one_second_clearance(self):
        ego = self.car(0, 700, 1)
        rows = (self.car(1, 715, 2), self.car(2, 685, 2), self.car(3, 690, 0, 33.3))
        self.assertFalse(rules._clear(ego, rows, 0))
        command, memory = self.decide(ego, rows)
        self.assertIsNone(command.lane)
        self.assertIsNone(memory.lane_target)

    def test_preparing_left_lane_does_not_free_fill_back_into_middle(self):
        ego = self.car(0, 700, 0)
        rows = tuple(self.car(i + 1, x, 0) for i, x in enumerate((640, 655, 670, 685, 715)))
        command, memory = self.decide(ego, rows)
        self.assertIsNone(command.lane)
        self.assertNotEqual(command.reason, "fill_layer")
        self.assertIsNone(memory.lane_target)

    def test_ending_car_keeps_its_independent_real_gap_merge(self):
        ego = self.car(0, 700, 2)
        rows = (self.car(1, 730, 1), self.car(2, 670, 1))
        command, memory = self.decide(ego, rows)
        self.assertEqual((command.lane, command.reason), (1, "merge"))
        self.assertEqual(memory.lane_target, 1)

    def test_already_moving_own_lane_change_keeps_priority(self):
        ego = replace(self.car(0, 700, 1), y=3.8, vy=-1.0)
        command, memory = self.decide(ego, (), rules.Memory(lane_target=0, joining=True))
        self.assertEqual((command.lane, command.reason), (0, "executing"))
        self.assertEqual(memory.lane_target, 0)

    def test_own_pending_actuation_keeps_priority_before_lateral_motion(self):
        ego = replace(self.car(0, 700, 1), pending_lane=0)
        command, memory = self.decide(ego)
        self.assertEqual((command.lane, command.reason), (0, "executing"))
        self.assertEqual(memory.lane_target, 0)

    def test_relabeling_reordering_and_remote_traffic_do_not_change_local_relief(self):
        ego = self.car(0, 700, 1)
        expected, _ = self.decide(ego, (self.car(1, 715, 2),))
        actual, _ = self.decide(replace(ego, track=981),
                               (self.car(5001, 1600, 0), self.car(4008, 715, 2)))
        self.assertEqual((actual.lane, actual.speed, actual.target_x),
                         (expected.lane, expected.speed, expected.target_x))

    def test_actual_front_and_hard_stopping_safety_still_apply(self):
        ego = self.car(0, 700, 1)
        rows = (self.car(1, 710, 1, 0), self.car(2, 700, 0), self.car(3, 715, 2))
        command, _ = self.decide(ego, rows)
        self.assertLessEqual(command.speed, rules.safe_speed(ego, rows))

    def test_noa_formation_and_transform_outside_preparation_equal_frozen_e(self):
        rng = random.Random(202611031)
        for mode, low, high in (("noa", 630, 1010), ("formation", 630, 1010),
                                ("transform", 200, 630), ("transform", 1020, 1150)):
            for _ in range(150):
                x, lane = rng.uniform(low, high), rng.randrange(3)
                if mode == "transform" and low > 1000:
                    lane = rng.randrange(2)
                values = [(0, x, lane, rng.uniform(0, 33.3))]
                values += [(i, x + rng.uniform(-130, 230), rng.randrange(3), rng.uniform(0, 33.3))
                           for i in range(1, 10)]
                cars = [[self.car(*v, module=m) for v in values] for m in (rules, baseline)]
                actual = rules.decide(cars[0][0], cars[0][1:], rules.Memory(), mode)
                expected = baseline.decide(cars[1][0], cars[1][1:], baseline.Memory(), mode)
                self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))


if __name__ == "__main__":
    unittest.main()
