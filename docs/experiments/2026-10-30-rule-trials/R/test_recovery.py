"""Isolated behavioral checks for completion-reference recovery; no SUMO runs."""

import argparse
from dataclasses import asdict, replace
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[4]
BASELINE = ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"


def load_rules(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RecoveryTests(unittest.TestCase):
    def car(self, track, x, lane=1, speed=20.0, time=1.0):
        return self.r.Vehicle(track, x, (lane + 0.5) * self.r.LANE_WIDTH, speed, lane, time=time)

    def completion(self, front_x=120.0, rear_x=80.0):
        ego = self.car(37, 100.0)
        rows = (self.car(9, front_x), self.car(51, rear_x, speed=12.0))
        memory = self.r.Memory(lane_target=1, gap=(9, 51), joining=True)
        command, memory = self.r.decide(ego, rows, memory, "formation", None)
        return ego, rows, command, memory

    def test_first_completed_request_continues_current_feasible_gap_reference(self):
        ego, rows, command, memory = self.completion()
        expected_speed, expected_target, _ = self.r._join_speed(
            ego, rows, self.r.Memory(gap=(9, 51)), 1
        )
        self.assertEqual(command.target_x, expected_target)
        self.assertEqual(command.speed, expected_speed)
        self.assertEqual(command.reference, 9)
        self.assertIsNone(memory.lane_target)
        self.assertIsNone(memory.gap)
        self.assertTrue(memory.joining)

    def test_both_setpoints_recover_over_existing_half_second_response(self):
        ego, rows, first, memory = self.completion()
        halfway = replace(ego, time=ego.time + 0.25)
        command, memory = self.r.decide(halfway, rows, memory, "formation", None)
        self.assertAlmostEqual(command.target_x, 95.0)
        self.assertAlmostEqual(command.speed, self.r._request(halfway, 95.0, 18.0))
        final = replace(ego, time=ego.time + 0.5)
        command, memory = self.r.decide(final, rows, memory, "formation", None)
        speed, target, reference, _ = self.r._following(final, rows, 3)
        self.assertEqual((command.speed, command.target_x, command.reference), (speed, target, reference))
        self.assertIsNone(getattr(memory, "recovery", None))
        self.assertNotEqual(first.target_x, target)

    def test_expanded_and_compressed_organization_gaps_both_recover(self):
        for distance in (20.0, 40.0):
            with self.subTest(distance=distance):
                ego, rows, command, memory = self.completion(100.0 + distance, 100.0 - distance)
                self.assertEqual(command.target_x, ego.x)
                final = replace(ego, time=1.5)
                command, memory = self.r.decide(final, rows, memory, "formation", None)
                self.assertAlmostEqual(command.target_x, rows[0].x - self.r.GAP)
                self.assertIsNone(getattr(memory, "recovery", None))

    def test_completion_requires_measured_center_and_no_pending_actuation(self):
        ego = self.car(37, 100.0)
        rows = (self.car(9, 120.0), self.car(51, 80.0))
        for measured in (replace(ego, pending_lane=1), replace(ego, y=5.4, vy=-1.0)):
            command, memory = self.r.decide(
                measured, rows, self.r.Memory(lane_target=1, gap=(9, 51), joining=True),
                "formation", None,
            )
            self.assertEqual(command.reason, "executing")
            self.assertEqual(memory.lane_target, 1)
            self.assertIsNone(getattr(memory, "recovery", None))

    def test_new_or_lost_actual_predecessor_clears_recovery_immediately(self):
        ego, rows, _, memory = self.completion()
        later = replace(ego, time=1.1)
        for changed in ((), (replace(rows[0], track=64), rows[1]), (replace(rows[0], lane=0, y=1.65),)):
            with self.subTest(changed=changed):
                command, after = self.r.decide(later, changed, memory, "formation", None)
                fresh, _ = self.r.decide(later, changed, self.r.Memory(joining=True), "formation", None)
                self.assertEqual(command, fresh)
                self.assertIsNone(getattr(after, "recovery", None))

    def test_hard_safety_uses_the_unsmoothed_current_front(self):
        ego, rows, _, memory = self.completion()
        later = replace(ego, time=1.1)
        stopped = replace(rows[0], x=107.0, speed=0.0)
        command, _ = self.r.decide(later, (stopped, rows[1]), memory, "formation", None)
        self.assertEqual(command.reference, stopped.track)
        self.assertAlmostEqual(command.speed, self.r.safe_speed(later, (stopped, rows[1])))
        self.assertLess(command.speed, 4.0)

    def test_tokens_only_associate_geometry_and_remote_rows_do_not_matter(self):
        ego, rows, command, memory = self.completion()
        mapping = {37: 2, 9: 900, 51: 1}
        other_ego = replace(ego, track=mapping[ego.track])
        other_rows = tuple(replace(c, track=mapping[c.track]) for c in rows)
        other, other_memory = self.r.decide(
            other_ego, (*other_rows, self.car(5, 301.0)),
            self.r.Memory(lane_target=1, gap=(900, 1), joining=True), "formation", None,
        )
        self.assertEqual(replace(command, reference=900), other)
        a, _ = self.r.decide(replace(ego, time=1.2), rows, memory, "formation", None)
        b, _ = self.r.decide(replace(other_ego, time=1.2), other_rows, other_memory, "formation", None)
        self.assertEqual(replace(a, reference=900), b)
        self.assertEqual(set(self.r.Vehicle.__dataclass_fields__), set(self.base.Vehicle.__dataclass_fields__))

    def test_noa_and_mandatory_merge_priority_match_the_baseline(self):
        scenarios = (
            ((700.0, 2, 28.8), ()),
            ((700.0, 2, 28.8), ((705.0, 1, 28.8),)),
            ((1000.0, 2, 0.0), ()),
            ((100.0, 0, 20.0), ((130.0, 0, 20.0),)),
        )
        for ego_data, row_data in scenarios:
            with self.subTest(ego=ego_data, rows=row_data):
                outputs = []
                for rules in (self.r, self.base):
                    def car(track, item):
                        x, lane, speed = item
                        return rules.Vehicle(track, x, (lane + 0.5) * rules.LANE_WIDTH, speed, lane)
                    result, _ = rules.decide(car(37, ego_data), tuple(car(i + 10, c) for i, c in enumerate(row_data)), rules.Memory(), "noa")
                    outputs.append(asdict(result))
                self.assertEqual(*outputs)
        ego, mandatory = self.car(37, 700.0, 0), self.car(9, 700.0, 2)
        self.assertTrue(self.r._mandatory_priority(ego, (mandatory,), 1, 1000.0))
        self.assertEqual(self.r._mandatory_priority(ego, (mandatory,), 1, 1000.0), self.base._mandatory_priority(ego, (mandatory,), 1, 1000.0))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=ROOT / "tmp/literature_trials/R/native_rules.py")
    parser.add_argument("--regressions", action="store_true")
    args = parser.parse_args()
    RecoveryTests.r = load_rules("recovery_candidate", args.rules)
    RecoveryTests.base = load_rules("recovery_baseline", BASELINE)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryTests)
    if args.regressions:
        sys.path.insert(0, str(BASELINE.parents[1]))
        import noa
        sys.modules["noa.native_rules"] = RecoveryTests.r
        noa.native_rules = RecoveryTests.r
        checks = load_rules("baseline_rule_tests", BASELINE.parents[1] / "tests/test_native_rules.py")
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(checks))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
