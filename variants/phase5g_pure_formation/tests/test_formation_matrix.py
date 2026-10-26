"""Preregistered finite-cohort formation sensitivity design."""

import unittest
import json
import tempfile
from pathlib import Path

from experiments.formation_matrix import planned_cases, run_matrix


class FormationMatrixTests(unittest.TestCase):
    def test_matrix_covers_lanes_demand_and_parameters_without_duplicates(self):
        cases = planned_cases()
        self.assertEqual(len(cases), 39)
        self.assertEqual(len({case["name"] for case in cases}), 39)
        base = [case for case in cases if case["kind"] == "lane_flow"]
        self.assertEqual({case["lane_count"] for case in base}, {2, 3, 4})
        self.assertEqual({case["offered_per_lane_veh_h"] for case in base},
                         {300, 600, 900})
        self.assertEqual({case["seed"] for case in base}, {1, 2, 3})
        self.assertTrue(all(case["duration_s"] > case["last_scheduled_departure_s"]
                            for case in cases))
        self.assertTrue(all(case["duration_s"] - case["last_scheduled_departure_s"]
                            == 200.0 for case in cases))

    def test_parallel_runner_preserves_each_short_case_and_aggregate(self):
        cases = []
        for lanes in (2, 4):
            case = next(row for row in planned_cases()
                        if row["lane_count"] == lanes)
            cases.append({**case, "name": f"short_lanes{lanes}",
                          "vehicle_count": 4, "departure_interval_s": 0.1,
                          "last_scheduled_departure_s": 0.3,
                          "duration_s": 0.4})
        with tempfile.TemporaryDirectory() as temp:
            root = run_matrix(Path(temp), cases=cases, workers=2)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in
                    (root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(summary["case_count"], 2)
            self.assertEqual(summary["completed_count"], 2, rows)
            self.assertEqual({row["name"] for row in rows},
                             {"short_lanes2", "short_lanes4"})
            self.assertTrue(all(row["recording_valid"] for row in rows))


if __name__ == "__main__":
    unittest.main()
