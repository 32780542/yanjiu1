"""Ablation boundaries against frozen H; real function profiling, no replacement."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from noa import native_rules as c
from experiments.native_sumo import MODES

package = Path(__file__).resolve().parent
base = json.loads((package / "base_manifest.json").read_text(encoding="utf-8"))
spec = importlib.util.spec_from_file_location("h_frozen_reference", Path(base["source_root"]) / "noa/native_rules.py")
h = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = h
spec.loader.exec_module(h)


def vehicle(mod, track, x, lane, speed=28.8, pending_lane=None):
    return mod.Vehicle(track, x, (lane + 0.5) * 3.3, speed, lane, pending_lane=pending_lane)


class CooperativeRulesTests(unittest.TestCase):
    def decide(self, mod, ego, rows, memory, mode, drop):
        try:
            command, saved = mod._decide(ego, rows, memory, mode, drop)
        except ValueError as exc:
            self.fail(str(exc))
        return asdict(command), asdict(saved)

    def six(self, mod, ego_index, *, pending=None):
        cars = tuple(vehicle(mod, i, x, lane, pending_lane=pending if i == ego_index else None) for i, (x, lane) in enumerate(((700, 2), (670, 2), (685, 1), (655, 1), (700, 0), (670, 0))))
        return cars[ego_index], tuple(car for car in cars if car.track != ego_index)

    def assert_six_action_same(self, ego_index, expected_reason, *, pending=None):
        e, rows = self.six(h, ego_index, pending=pending)
        expected = self.decide(h, e, rows, h.Memory(), "transform", 1000)
        e, rows = self.six(c, ego_index, pending=pending)
        actual = self.decide(c, e, rows, c.Memory(), "cooperative", 1000)
        self.assertEqual(actual, expected)
        self.assertEqual(actual[0]["reason"], expected_reason)

    def test_runner_records_cooperative_as_an_actual_mode(self):
        self.assertIn("cooperative", MODES)

    def test_helper_action_and_memory_equal_h(self):
        self.assert_six_action_same(2, "make_room")

    def test_middle_receiving_action_and_memory_equal_h(self):
        self.assert_six_action_same(3, "open_gap")

    def test_lower_receiving_action_and_memory_equal_h(self):
        self.assert_six_action_same(5, "open_gap")

    def test_necessary_merge_action_and_memory_equal_h(self):
        self.assert_six_action_same(0, "merge")

    def test_pending_execution_keeps_h_join_tracking(self):
        self.assert_six_action_same(2, "executing", pending=0)

    def profiled(self, mode):
        calls = []
        def profile(frame, event, arg):
            if event == "call" and frame.f_code.co_filename == c.__file__ and frame.f_code.co_name in ("_following", "_fill"):
                calls.append(frame.f_code.co_name)
        previous = sys.getprofile()
        sys.setprofile(profile)
        try:
            result = self.decide(c, vehicle(c, 0, 100, 0), (vehicle(c, 1, 140, 0),), c.Memory(), mode, 1000)
        finally:
            sys.setprofile(previous)
        return calls, result

    def test_group_following_and_fill_are_not_called_by_cooperative(self):
        positive, _ = self.profiled("transform")
        self.assertIn("_following", positive)
        self.assertIn("_fill", positive)
        calls, (command, memory) = self.profiled("cooperative")
        self.assertEqual(calls, [])
        self.assertEqual(command["reason"], "cooperative_follow")
        self.assertEqual(command["speed"], 28.8)

    def test_straight_cooperative_delegates_the_complete_noa_overtake_action(self):
        expected = self.decide(h, vehicle(h, 0, 100, 1, 20), (vehicle(h, 1, 120, 1, 20),), h.Memory(), "noa", None)
        actual = self.decide(c, vehicle(c, 0, 100, 1, 20), (vehicle(c, 1, 120, 1, 20),), c.Memory(), "cooperative", None)
        self.assertEqual(actual, expected)
        self.assertEqual(actual[0]["reason"], "normal_overtake")

    def test_straight_pending_execution_also_delegates_complete_noa(self):
        expected = self.decide(h, vehicle(h, 0, 100, 1, 20, pending_lane=0), (), h.Memory(lane_target=0), "noa", None)
        actual = self.decide(c, vehicle(c, 0, 100, 1, 20, pending_lane=0), (), c.Memory(lane_target=0), "cooperative", None)
        self.assertEqual(actual, expected)
        self.assertEqual(actual[0]["speed"], 28.8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
