"""Protocol mismatches stay visible and cannot enter eligible comparisons."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seal_case
import summarize


class ProtocolContracts(unittest.TestCase):
    def fixture(self):
        self.assertTrue(callable(getattr(summarize, "audit_protocol", None)), "protocol audit implementation is missing")
        sources = {name: "frozen_" + name for name in seal_case.tools()[0].SOURCES}
        arrival = dict(vehicle_id="car", requested_s=.1, lane=1, x=0., speed=28.8)
        inp = dict(case=dict(flow_veh_h_lane=1750., seed=1, scenario="lane_drop", mode="transform",
                            demand_duration_s=180., max_time_s=500.), source_sha256=sources, arrivals=[arrival])
        task = dict(candidate="TM", stage="fixture", flow=1750., seed=1, scenario="lane_drop", mode="transform",
                    duration=180., max_time=500., output="D:/owned/cases/one")
        record = {**task, "base_commit": "base", "case_output": task["output"], "run_dir": task["output"] + "/run"}
        original = {"input.json": inp, "result.json": {**inp["case"], "source_sha256": sources}, "trips.json": [arrival.copy()]}
        hashes = {"input.json": "input", "result.json": "result", "trips.json": "trips"}
        cached = dict(case_dir=record["run_dir"], input_sha256="input", result_sha256="result", trips_sha256="trips",
                      demand_sha256=seal_case.tools()[1].obj_sha([arrival]), source_sha256=sources)
        protocol = dict(base_commit="base", sources={"TM": sources})
        return record, task, protocol, original, hashes, cached

    def test_matching_original_request_and_source_is_accepted(self):
        self.assertEqual(summarize.audit_protocol(*self.fixture()), [])

    def test_duration_source_and_request_mismatches_are_explicit(self):
        data = list(self.fixture())
        data[3]["input.json"]["case"]["demand_duration_s"] = 10
        data[3]["input.json"]["source_sha256"] = {**data[3]["input.json"]["source_sha256"], "noa/native_rules.py": "other"}
        data[3]["trips.json"][0]["requested_s"] = 1.0
        issues = summarize.audit_protocol(*data)
        self.assertIn("protocol_input_mismatch:demand_duration_s", issues)
        self.assertIn("protocol_source_hash_mismatch:noa/native_rules.py", issues)
        self.assertIn("original_request_trip_mismatch:car", issues)

    def test_missing_and_unplanned_cases_both_remain_in_records(self):
        self.assertTrue(callable(getattr(summarize, "protocol_records", None)), "protocol records implementation is missing")
        with tempfile.TemporaryDirectory() as directory:
            batch = Path(directory)
            task = dict(candidate="TM", stage="fixture", flow=1750, seed=1, scenario="lane_drop", mode="transform", output=str(batch / "cases/one"))
            other = {**task, "seed": 4, "seal_status": "not_available_raw_retained"}
            (batch / "protocol.json").write_text(json.dumps(dict(base_commit="base", sources={}, tasks=[task])), encoding="utf-8")
            (batch / "manifest.json").write_text(json.dumps([other]), encoding="utf-8")
            rows = summarize.protocol_records(batch)
            self.assertEqual(len(rows), 2)
            self.assertEqual({issue for row in rows for issue in row["_protocol_issues"]},
                             {"missing_manifest_case", "unplanned_manifest_case"})


if __name__ == "__main__":
    unittest.main()
