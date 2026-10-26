"""Distinguish a long connected group from overlapping local join windows."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_local_admissions import audit_case, overlapping_pairs


class LocalAdmissionAuditTests(unittest.TestCase):
    def test_same_ninety_metre_local_window_ends_at_ninety_metres(self):
        self.assertEqual(overlapping_pairs(("rear", "front"),
                                           {"rear": 0.0, "front": 90.0}),
                         [["front", "rear"]])
        self.assertEqual(overlapping_pairs(("rear", "front"),
                                           {"rear": 0.0, "front": 100.0}), [])

    def test_conflict_requires_two_active_maneuvers_in_overlapping_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            case = source / "case"
            case.mkdir()
            event = {"time_s": 67.2, "joining_actors": ["rear", "front"]}
            (case / "detection.json").write_text(json.dumps({
                "default": {"admission_conflicts": [event]}}), encoding="utf-8")
            row = {"name": "example", "source": str(source),
                   "safety_passed": False,
                   "failure_reasons": ["simultaneous_admission_conflict"]}
            for separation, front_active, expected_safe in (
                    (261.0, True, True), (80.0, False, True),
                    (80.0, True, False)):
                (case / "trace.jsonl").write_text(json.dumps({
                    "initial": {
                        "rear": {"time_s": 67.2, "x_m": 0.0},
                        "front": {"time_s": 67.2, "x_m": separation},
                    },
                    "decisions": {
                        "rear": {"memory": {"plan": {"start_s": 67.0}}},
                        "front": {"memory": {
                            "plan": {"start_s": 67.0} if front_active else None}},
                    },
                }) + "\n", encoding="utf-8")
                result = audit_case(row)
                self.assertEqual(result["active_lane_change_window_safety_passed"],
                                 expected_safe)

            sample = json.loads((case / "trace.jsonl").read_text(encoding="utf-8"))
            sample["decisions"]["front"]["memory"]["plan"] = None
            (case / "trace.jsonl").write_text(json.dumps(sample) + "\n",
                                               encoding="utf-8")
            row["failure_reasons"] = ["simultaneous_admission_conflict",
                                      "lane_distribution_invalid"]
            result = audit_case(row)
            self.assertTrue(result["active_lane_change_window_safety_passed"])
            row["failure_reasons"] = ["simultaneous_admission_conflict",
                                      "collision_detected"]
            result = audit_case(row)
            self.assertFalse(result["active_lane_change_window_safety_passed"])


if __name__ == "__main__":
    unittest.main()
