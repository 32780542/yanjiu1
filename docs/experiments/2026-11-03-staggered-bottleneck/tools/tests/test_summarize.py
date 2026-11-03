"""Archive-analysis pairing must reject duplicates and expose missing members."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class SummaryContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / "summarize.py").is_file(), "summarizer implementation is missing")
        import summarize
        self.tool = summarize

    def record(self, candidate="TM", mode="transform", stage="a"):
        return dict(candidate=candidate, flow=1750, seed=1, scenario="lane_drop", mode=mode, stage=stage)

    def case_row(self, candidate="TM", mode="transform"):
        row = self.record(candidate, mode)
        row["_run"] = dict(candidate=candidate, case_dir=candidate + mode,
            flow_veh_h_lane=1750, seed=1, scenario="lane_drop", attribution_eligible=True,
            rules_sha256=candidate, nonrule_source_sha256="same", demand_sha256="same",
            parameters_sha256="same", source_sha256={"rule": candidate}, mean_travel_time_s=40 if candidate == "TM" else 41)
        return row

    def test_duplicate_key_is_error_even_when_stage_differs(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.tool.unique([self.record(stage="a"), self.record(stage="b")])

    def test_missing_baseline_is_an_explicit_ineligible_pair(self):
        pairs = self.tool.build_pairs([self.case_row("A20")])
        self.assertEqual(len(pairs), 1)
        self.assertFalse(pairs[0]["pair_eligible"])
        self.assertIn("missing_pair_member", pairs[0]["rejection_reasons"])

    def test_candidate_pair_uses_existing_difference_and_source_checks(self):
        rows = [self.case_row("TM", "noa"), self.case_row("TM"), self.case_row("A20")]
        pairs = self.tool.build_pairs(rows)
        candidate = next(p for p in pairs if p["comparison"] == "A20-minus-TM_transform")
        self.assertTrue(candidate["pair_eligible"])
        self.assertEqual(candidate["delta_mean_travel_time_s"], 1)
        rows[-1]["_run"]["nonrule_source_sha256"] = "different"
        candidate = next(p for p in self.tool.build_pairs(rows) if p["comparison"] == "A20-minus-TM_transform")
        self.assertFalse(candidate["pair_eligible"])
        self.assertIsNone(candidate["delta_mean_travel_time_s"])


if __name__ == "__main__":
    unittest.main()
