"""Focused T+R composition contracts; directly exercise rules without SUMO."""

import argparse
from dataclasses import asdict, replace
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[4]
PARENT = ROOT / "tmp/literature_trials/T/native_rules.py"
SOURCE = ROOT / "tmp/literature_trials/TR/native_rules.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RecoveryOnTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r, cls.parent = load("TR_candidate", SOURCE), load("TR_parent", PARENT)

    def car(self, track, x, speed=20.0, lane=1, time=1.0):
        return self.r.Vehicle(track, x, (lane + 0.5) * self.r.LANE_WIDTH, speed, lane, time=time)

    def completion(self):
        ego = self.car(37, 100)
        rows = (self.car(9, 120), self.car(51, 80, 12))
        memory = self.r.Memory(lane_target=1, gap=(9, 51), joining=True)
        command, memory = self.r.decide(ego, rows, memory, "formation", None)
        return ego, rows, command, memory

    def test_actual_completion_continues_the_current_feasible_join_request(self):
        ego, rows, command, memory = self.completion()
        expected_speed, expected_target, _ = self.r._join_speed(ego, rows, self.r.Memory(gap=(9, 51)), 1)
        self.assertEqual((command.speed, command.target_x), (expected_speed, expected_target))
        self.assertEqual(command.reference, 9)
        self.assertIsNone(memory.lane_target)
        self.assertIsNone(memory.gap)
        self.assertTrue(memory.joining)

    def test_halfway_uses_offset_from_T_then_returns_exactly_to_T_after_half_second(self):
        ego, rows, first, memory = self.completion()
        initial_target = self.parent._front_following(ego, rows)[1]
        later = replace(ego, speed=24.0, time=1.25)
        current_target = self.parent._front_following(later, rows)[1]
        expected_target = current_target + 0.5 * (first.target_x - initial_target)
        command, memory = self.r.decide(later, rows, memory, "formation", None)
        self.assertAlmostEqual(command.target_x, expected_target)
        self.assertAlmostEqual(command.speed, self.r._request(later, expected_target, 18.0))
        final = replace(later, time=1.5)
        command, memory = self.r.decide(final, rows, memory, "formation", None)
        baseline, _ = self.parent.decide(final, rows, self.parent.Memory(joining=True), "formation", None)
        self.assertEqual(asdict(command), asdict(baseline))
        self.assertIsNone(getattr(memory, "recovery", None))

    def test_measured_completion_and_pending_request_remain_required(self):
        ego, rows, _, _ = self.completion()
        for moving in (replace(ego, pending_lane=1), replace(ego, y=5.4, vy=-1.0)):
            command, memory = self.r.decide(moving, rows,
                self.r.Memory(lane_target=1, gap=(9, 51), joining=True), "formation", None)
            self.assertEqual(command.reason, "executing")
            self.assertEqual(memory.lane_target, 1)
            self.assertIsNone(getattr(memory, "recovery", None))

    def test_lost_changed_or_departed_actual_front_discards_recovery(self):
        ego, rows, _, memory = self.completion()
        ego = replace(ego, time=1.1)
        for changed in ((), (replace(rows[0], track=64), rows[1]),
                        (replace(rows[0], lane=0, y=1.65),), (replace(rows[0], x=151),)):
            with self.subTest(rows=changed):
                command, after = self.r.decide(ego, changed, memory, "formation", None)
                expected, _ = self.r.decide(ego, changed, self.r.Memory(joining=True), "formation", None)
                self.assertEqual(command, expected)
                self.assertIsNone(getattr(after, "recovery", None))

    def test_NOA_ignores_and_clears_recovery_and_matches_T(self):
        ego, rows, _, memory = self.completion()
        for others in (rows, (), (self.car(9, 130, 28.8),)):
            command, after = self.r.decide(ego, others, memory, "noa", None)
            expected, _ = self.parent.decide(ego, others, self.parent.Memory(joining=True), "noa", None)
            self.assertEqual(asdict(command), asdict(expected))
            self.assertEqual(command.formation_state, 0)
            self.assertIsNone(getattr(after, "recovery", None))

    def test_T_equilibrium_and_shared_NOA_following_remain(self):
        for speed in (0.0, 5.0, 10.0, 20.0, 28.8, 31.0):
            with self.subTest(speed=speed):
                distance = 5.5 + (30.0 - 5.5) / 28.8 * speed
                ego, front = self.car(37, 100, speed), self.car(9, 100 + distance, speed)
                noa, _ = self.r.decide(ego, (front,), self.r.Memory(), "noa", None)
                formed, _ = self.r.decide(ego, (front,), self.r.Memory(), "formation", None)
                self.assertAlmostEqual(noa.speed, speed)
                self.assertAlmostEqual(formed.speed, speed)
                self.assertEqual((noa.formation_state, formed.formation_state), (0, 1))

    def test_urgent_current_front_safety_is_never_smoothed(self):
        ego, rows, _, memory = self.completion()
        ego, front = replace(ego, time=1.1), replace(rows[0], x=107, speed=0)
        command, _ = self.r.decide(ego, (front, rows[1]), memory, "formation", None)
        self.assertEqual(command.reference, front.track)
        self.assertEqual(command.speed, self.r.safe_speed(ego, (front, rows[1])))
        self.assertLess(command.speed, 4.0)

    def test_token_relabeling_and_unobservable_remote_rows_preserve_motion(self):
        ego, rows, command, memory = self.completion()
        other_ego = replace(ego, track=2)
        other_rows = (replace(rows[0], track=900), replace(rows[1], track=1))
        other, other_memory = self.r.decide(other_ego, (*other_rows, self.car(5, 301)),
            self.r.Memory(lane_target=1, gap=(900, 1), joining=True), "formation", None)
        self.assertEqual(replace(command, reference=900), other)
        a, _ = self.r.decide(replace(ego, time=1.2), rows, memory, "formation", None)
        b, _ = self.r.decide(replace(other_ego, time=1.2), other_rows, other_memory, "formation", None)
        self.assertEqual(replace(a, reference=900), b)

    def test_helper_without_recovery_keeps_T_and_does_not_add_T2(self):
        ego = self.car(37, 100)
        rows = (self.car(9, 125, 22), self.car(51, 165, 18))
        self.assertEqual(self.r._front_following(ego, rows), self.parent._front_following(ego, rows))
        self.assertEqual(self.r._following(ego, (), 3), self.parent._following(ego, (), 3))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=SOURCE)
    args, remaining = parser.parse_known_args()
    SOURCE = args.rules.resolve()
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
