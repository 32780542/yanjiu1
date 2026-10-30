"""Behavioral checks for normalized two-actual-front anticipation; no simulation."""

import argparse
import ast
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[4]
PARENT = ROOT / "tmp/literature_trials/T/native_rules.py"
SOURCE = ROOT / "tmp/literature_trials/T2/native_rules.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TwoFrontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r, cls.parent = load("T2_candidate", SOURCE), load("T2_parent", PARENT)

    def car(self, track, x, speed=20.0, lane=0):
        return self.r.Vehicle(track, x, (lane + 0.5) * self.r.LANE_WIDTH, speed, lane)

    def command(self, ego, rows, mode):
        return self.r.decide(ego, rows, self.r.Memory(joining=True), mode, None)[0]

    def test_normalized_position_and_speed_use_the_second_actual_front(self):
        ego, first, second = self.car(0, 100), self.car(51, 125, 22), self.car(7, 165, 18)
        distance = self.r.LENGTH + self.r.STANDSTILL + self.r.HEADWAY * ego.speed
        expected_target = (first.x - distance + 0.5 * (second.x - 2 * distance)) / 1.5
        expected_speed = self.r._request(ego, expected_target, (first.speed + 0.5 * second.speed) / 1.5)
        speed, target, reference, state = self.r._front_following(ego, (second, first))
        self.assertAlmostEqual(target, expected_target)
        self.assertAlmostEqual(speed, expected_speed)
        self.assertEqual((reference, state), (first.track, 1))

    def test_same_speed_equilibrium_including_low_and_cruise_speeds(self):
        for speed in (0.0, 5.0, 10.0, 20.0, 28.8, 31.0):
            with self.subTest(speed=speed):
                distance = 5.5 + (30.0 - 5.5) / 28.8 * speed
                ego = self.car(0, 100, speed)
                rows = (self.car(8, 100 + distance, speed), self.car(2, 100 + 2 * distance, speed))
                result = self.r._front_following(ego, rows)
                self.assertAlmostEqual(result[0], speed)
                self.assertAlmostEqual(result[1], ego.x)
                self.assertEqual(result[2:], (8, 1))

    def test_second_front_speed_and_position_both_affect_request(self):
        ego, first = self.car(0, 100), self.car(7, 125)
        slow = self.r._front_following(ego, (first, self.car(8, 150, 10)))
        fast = self.r._front_following(ego, (first, self.car(8, 150, 25)))
        farther = self.r._front_following(ego, (first, self.car(8, 160, 25)))
        self.assertLess(slow[0], fast[0])
        self.assertLess(fast[0], farther[0])
        self.assertLess(fast[1], farther[1])
        self.assertEqual((slow[2], fast[2], farther[2]), (7, 7, 7))

    def test_missing_off_corridor_or_disconnected_second_is_exact_T(self):
        ego, first = self.car(0, 100), self.car(7, 125, 19)
        for extras in ((), (self.car(8, 176, 0),), (self.car(8, 145, 0, lane=1),),
                       (self.car(8, 90, 0),), (self.car(8, 301, 0),)):
            with self.subTest(extras=extras):
                rows = (first, *extras)
                self.assertEqual(self.r._front_following(ego, rows), self.parent._front_following(ego, rows))

    def test_second_is_next_in_physical_order_and_can_be_beyond_first_fifty_metres(self):
        ego, first, second = self.car(0, 100), self.car(7, 140), self.car(8, 180, 10)
        third, adjacent = self.car(1, 195, 0), self.car(2, 160, 0, lane=1)
        expected = self.r._front_following(ego, (first, second))
        actual = self.r._front_following(ego, (third, adjacent, second, first))
        self.assertEqual(actual, expected)
        self.assertLess(actual[0], self.parent._front_following(ego, (first, second))[0])

    def test_without_a_near_first_keeps_original_T_head_handling(self):
        ego = self.car(0, 100, 28.8)
        rows = (self.car(7, 151, 28.8), self.car(8, 181, 28.8))
        self.assertEqual(self.r._front_following(ego, rows), (self.r.CRUISE, None, None, 0))
        self.assertEqual(self.r._following(ego, rows, 3), self.parent._following(ego, rows, 3))
        self.assertEqual(self.command(ego, rows, "noa").formation_state, 0)

    def test_noa_and_formation_share_anticipation_but_noa_state_is_zero(self):
        ego, first, second = self.car(0, 100, 28), self.car(7, 130, 30), self.car(8, 155, 14)
        rows = (first, second)
        noa, formation = self.command(ego, rows, "noa"), self.command(ego, rows, "formation")
        expected = self.r._front_following(ego, rows)
        self.assertEqual((noa.speed, noa.target_x, noa.reference), expected[:3])
        self.assertEqual((formation.speed, formation.target_x, formation.reference), expected[:3])
        self.assertEqual((noa.formation_state, formation.formation_state), (0, 1))

    def test_track_relabeling_and_remote_geometry_do_not_change_request(self):
        ego, first, second = self.car(0, 100), self.car(7, 125, 22), self.car(8, 160, 18)
        expected = self.r._front_following(ego, (first, second))
        actual = self.r._front_following(replace(ego, track=99),
            (replace(second, track=1), self.car(10, 1000, 0), replace(first, track=800)))
        self.assertEqual(actual[:2], expected[:2])
        self.assertEqual(actual[2:], (800, 1))

    def test_request_clipping_and_true_current_front_safety_are_retained(self):
        ego = self.car(0, 100, 28.8)
        fast = (self.car(7, 149, 200), self.car(8, 199, 200))
        self.assertEqual(self.r._front_following(ego, fast)[0], self.r.MAX_SPEED)
        stopped = self.car(0, 100, 0)
        compressed = (self.car(7, 105.5, 0), self.car(8, 106, 0))
        self.assertEqual(self.r._front_following(stopped, compressed)[0], 0.0)
        urgent = (self.car(7, 108, 0), self.car(8, 130, 70))
        for mode in ("noa", "formation"):
            command = self.command(ego, urgent, mode)
            self.assertAlmostEqual(command.speed, self.r.safe_speed(ego, urgent))
            self.assertLess(command.speed, self.r._front_following(ego, urgent)[0])

    def test_all_T_code_outside_front_following_is_unchanged(self):
        def other_code(path):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            tree.body = [node for node in tree.body if not isinstance(node, ast.FunctionDef)
                         or node.name != "_front_following"]
            return ast.dump(tree, include_attributes=False)
        self.assertEqual(other_code(SOURCE), other_code(PARENT))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=SOURCE)
    args, remaining = parser.parse_known_args()
    SOURCE = args.rules.resolve()
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
