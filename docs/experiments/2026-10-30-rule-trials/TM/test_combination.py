"""Incremental braking-cost contracts on the shared time-headway baseline."""
import argparse
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "tmp/literature_trials/TM/native_rules.py"
spec = importlib.util.spec_from_file_location("T_contracts", Path(__file__).parents[1] / "T/test_time_headway.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)


class CombinationTests(contracts.TimeHeadwayTests):
    @classmethod
    def setUpClass(cls):
        contracts.SOURCE = SOURCE
        super().setUpClass()

    def fill_scene(self):
        car = lambda key, x, lane, speed=28.8: self.car(key, x, speed, lane)
        return car(0, 285, 0), [car(1, 300, 2), car(2, 270, 2), car(3, 255, 1),
                               car(4, 300, 0), car(5, 270, 0)]

    def test_counterfactual_model_uses_the_shared_time_headway_law(self):
        self.assertTrue(hasattr(self.r, "cf_speed"))
        for speed in (5., 20., 28.8):
            ego, front = self.car(0, 100, speed), self.car(8, 125, speed - 1)
            expected = min(self.r._front_following(ego, (front,))[0], self.r.safe_speed(ego, (front,)))
            self.assertAlmostEqual(self.r.cf_speed(ego, (front,)), expected)

    def test_useful_equal_speed_fill_survives(self):
        ego, rows = self.fill_scene()
        self.assertEqual(self.r._fill(ego, rows, 3), 1)

    def test_target_follower_braking_is_not_paid_by_release_elsewhere(self):
        ego, rows = self.fill_scene()
        ego = replace(ego, speed=20.)
        rows[2] = replace(rows[2], x=265., speed=31.)
        rows.append(self.car(6, 275, 31.))
        self.assertTrue(self.r._clear(ego, rows, 1))
        self.assertIsNone(self.r._fill(ego, rows, 3))

    def test_lower_braking_fill_wins_the_same_geometric_opportunity(self):
        ego, rows = self.fill_scene()
        rows.append(self.car(6, 285, 25., 2))
        self.assertEqual(self.r._fill(ego, rows, 3), 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=SOURCE)
    args, remaining = parser.parse_known_args()
    SOURCE = args.rules.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
