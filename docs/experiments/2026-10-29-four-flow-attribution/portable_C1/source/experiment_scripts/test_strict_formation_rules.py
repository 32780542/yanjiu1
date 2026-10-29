"""C1 removes C0 ordinary overtake only; cooperation and straight delegation stay."""
import ast
from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys
import unittest

from test_cooperative_rules import CooperativeRulesTests, c, h, vehicle


PARENT = Path(__file__).resolve().parents[1] / "H_cooperative_ablation"
spec = importlib.util.spec_from_file_location("c0_frozen_reference", PARENT / "noa/native_rules.py")
c0 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c0
spec.loader.exec_module(c0)


def action(mod, mode, drop=1000.0):
    ego = vehicle(mod, 0, 700, 0, 20)
    rows = (vehicle(mod, 1, 720, 0, 20),)
    command, memory = mod._decide(ego, rows, mod.Memory(), mode, drop)
    return asdict(command), asdict(memory)


class StrictFormationTests(unittest.TestCase):
    def test_prepare_slow_lane0_no_longer_ordinary_overtakes_in_C1(self):
        self.assertEqual(action(c0, "cooperative")[0]["reason"], "normal_overtake")
        self.assertNotEqual(action(h, "transform")[0]["reason"], "normal_overtake")
        strict = action(c, "cooperative")
        self.assertEqual(strict[0]["reason"], "cooperative_follow")
        self.assertIsNone(strict[0]["lane"])

    def test_NOA_still_has_identical_ordinary_overtake(self):
        expected = action(h, "noa")
        self.assertEqual(expected[0]["reason"], "normal_overtake")
        self.assertEqual(action(c, "noa"), expected)
        self.assertEqual(action(c0, "noa"), expected)

    def test_prepare_cooperative_never_calls_group_following_or_fill(self):
        calls = []
        def profile(frame, event, arg):
            if event == "call" and frame.f_code.co_filename == c.__file__ and frame.f_code.co_name in ("_following", "_fill"):
                calls.append(frame.f_code.co_name)
        previous = sys.getprofile()
        sys.setprofile(profile)
        try:
            action(c, "cooperative")
        finally:
            sys.setprofile(previous)
        self.assertEqual(calls, [])

    def test_straight_complete_NOA_delegation_is_unchanged(self):
        self.assertEqual(action(c, "cooperative", None), action(c0, "cooperative", None))
        self.assertEqual(action(c, "cooperative", None), action(h, "noa", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
