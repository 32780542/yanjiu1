"""Hand-calculated first adjustment / confirmed two-lane membership events."""

import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def three(front=600.0):
    return {
        v: [front - dx, (lane + 0.5) * 3.3, 0.0, 0.0]
        for v, lane, dx in (
            ("A1", 2, 0),
            ("A2", 2, 30),
            ("B1", 1, 15),
            ("B2", 1, 45),
            ("C1", 0, 0),
            ("C2", 0, 30),
        )
    }


def two(front=800.0):
    return {
        v: [front - dx, (lane + 0.5) * 3.3, 0.0, 0.0]
        for v, lane, dx in (
            ("A1", 1, 0),
            ("A2", 1, 30),
            ("B2", 1, 60),
            ("C1", 0, 15),
            ("B1", 0, 45),
            ("C2", 0, 75),
        )
    }


class NativeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("experiments.native_recovery"),
            "Independent offline recovery evaluator is missing",
        )
        from experiments.native_recovery import evaluate_recovery, summarize_manifest

        self.evaluate = evaluate_recovery
        self.summarize = summarize_manifest
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.counter = 0

    def case(self, frames, exits=None, mode="transform", scenario="lane_drop"):
        self.counter += 1
        case = self.root / f"case_{self.counter}"
        case.mkdir()
        with gzip.open(case / "positions.jsonl.gz", "wt", encoding="utf-8") as stream:
            for t, states in frames:
                stream.write(json.dumps(dict(time_s=t, states=states)) + "\n")
        ids = sorted({v for _, states in frames for v in states})
        trips = [dict(vehicle_id=v, exited_s=(exits or {}).get(v)) for v in ids]
        (case / "trips.json").write_text(json.dumps(trips), encoding="utf-8")
        (case / "input.json").write_text(
            json.dumps(dict(case=dict(mode=mode, seed=1, scenario=scenario))), encoding="utf-8"
        )
        return case

    def test_exact_seconds_from_formed_three_lanes_to_adjustment_and_two_lanes(self):
        result = self.evaluate(
            self.case([(0.0, three()), (1.0, three(610.0)), (2.0, three(700.0)), (3.0, two()), (4.0, two())])
        )
        self.assertEqual((result["subjects"], result["recovered"], result["censored"]), (6, 6, 0))
        for row in result["per_vehicle"]:
            self.assertEqual(row["t_adjust_s"], 2.0)
            self.assertEqual(row["t_two_lane_s"], 4.0)
            self.assertEqual(row["delay_s"], 2.0)
            self.assertTrue(row["upstream_formed"])
            self.assertEqual(row["upstream_first_confirmed_s"], 1.0)
        self.assertEqual(result["upstream_formed"]["recovered"], 6)
        self.assertEqual(result["conditional_mean_delay_s"], 2.0)
        self.assertEqual(result["conditional_median_delay_s"], 2.0)
        self.assertEqual(result["conditional_p95_delay_s"], 2.0)

    def test_nonrecovery_until_exit_is_censored_instead_of_zero_delay(self):
        exits = {v: 3.0 for v in three()}
        result = self.evaluate(
            self.case([(0.0, three()), (1.0, three()), (2.0, three(700.0)), (3.0, {})], exits)
        )
        self.assertEqual((result["recovered"], result["censored"]), (0, 6))
        self.assertIsNone(result["conditional_mean_delay_s"])
        self.assertTrue(
            all(v["delay_s"] is None and v["censor_reason"] == "road_exit" for v in result["per_vehicle"])
        )

    def test_recording_end_without_recovery_is_censored(self):
        result = self.evaluate(self.case([(0.0, three()), (1.0, three()), (2.0, three(700.0))]))
        self.assertEqual(result["censored"], 6)
        self.assertTrue(all(v["censor_reason"] == "recording_end" for v in result["per_vehicle"]))

    def test_tail_arrival_does_not_reset_confirmed_prefix_relationships(self):
        full = two()
        prefix = {v: s for v, s in full.items() if v not in ("B2", "C2")}
        result = self.evaluate(self.case([(0.0, prefix), (0.5, full), (1.0, full), (1.5, full)]))
        rows = {v["vehicle_id"]: v for v in result["per_vehicle"]}
        self.assertEqual(rows["A1"]["t_two_lane_s"], 1.0)
        self.assertEqual(rows["B2"]["t_two_lane_s"], 1.5)
        self.assertEqual(result["recovered"], 6)
        self.assertEqual(result["upstream_formed"]["subjects"], 0)

    def test_less_than_one_second_two_lane_membership_does_not_recover(self):
        broken = {v: [s[0], 6.6, *s[2:]] for v, s in two().items()}
        result = self.evaluate(self.case([(0.0, two()), (0.9, broken), (2.0, broken)]))
        self.assertEqual(result["recovered"], 0)
        self.assertEqual(result["censored"], 6)

    def test_exit_after_confirmation_does_not_undo_observed_recovery(self):
        exits = {v: 2.0 for v in two()}
        result = self.evaluate(self.case([(0.0, two()), (1.0, two()), (2.0, two(1300.0))], exits))
        self.assertEqual((result["recovered"], result["censored"]), (6, 0))
        self.assertTrue(all(v["delay_s"] == 1.0 for v in result["per_vehicle"]))

    def test_short_upstream_membership_is_not_prior_formation(self):
        result = self.evaluate(self.case([(0.0, three()), (0.5, three(700.0)), (1.0, two()), (2.0, two())]))
        self.assertEqual(result["upstream_formed"]["subjects"], 0)
        self.assertEqual(result["not_upstream_formed"]["recovered"], 6)

    def test_coarse_interval_uses_the_same_left_held_confirmation_clock(self):
        result = self.evaluate(self.case([(2.0, two()), (4.0, two())]))
        self.assertTrue(all(v["t_two_lane_s"] == 3.0 for v in result["per_vehicle"]))
        self.assertTrue(all(v["adjust_start_is_first_observation"] for v in result["per_vehicle"]))
        self.assertEqual(result["max_position_sample_step_s"], 2.0)

    def test_one_layer_is_not_a_recovered_group(self):
        states = {v: s for v, s in two().items() if v in ("A1", "C1")}
        result = self.evaluate(self.case([(0.0, states), (3.0, states)]))
        self.assertEqual(result["recovered"], 0)

    def test_mode_only_changes_interpretation_not_event_detection(self):
        frames = [(0.0, two()), (1.0, two())]
        noa = self.evaluate(self.case(frames, mode="noa"))
        transform = self.evaluate(self.case(frames, mode="transform"))
        self.assertEqual(noa["per_vehicle"], transform["per_vehicle"])
        self.assertIn("geometry", noa["event_interpretation"])

    def test_no_adjusting_subject_has_undefined_conditional_statistics(self):
        result = self.evaluate(self.case([(0.0, three()), (2.0, three())]))
        self.assertEqual(result["subjects"], 0)
        self.assertIsNone(result["conditional_mean_delay_s"])

    def test_straight_road_is_explicitly_not_a_lane_drop_recovery(self):
        result = self.evaluate(self.case([(0.0, two()), (2.0, two())], scenario="straight3"))
        self.assertFalse(result.get("applicable", True))
        self.assertEqual(result["subjects"], 0)
        self.assertIsNone(result["conditional_mean_delay_s"])

    def test_local_clock_membership_matches_frozen_complete_layers_mature(self):
        from experiments.complete_layers import groups_at, _mature
        from experiments.native_recovery import _membership_times, _relation_keys

        states = two()
        groups = groups_at(states, 2)
        born = {key: (0.5 if key[0] == "row" else 0.8) for key in _relation_keys(groups)}
        for t in (0.0, 1.0, 1.5, 1.8, 2.0):
            expected = {v for g in _mature(groups, born, t, 1.0, states, 2, 30.0) for v in g["vehicle_ids"]}
            actual = {v for v, when in _membership_times(groups, born, 1.0).items() if when <= t + 1e-9}
            self.assertEqual(actual, expected)

    def test_odd_original_cohort_does_not_gate_recovered_even_subset(self):
        def nine(front):
            return dict(
                three(front),
                A3=[front - 60.0, 8.25, 0.0, 0.0],
                B3=[front - 75.0, 4.95, 0.0, 0.0],
                C3=[front - 60.0, 1.65, 0.0, 0.0],
            )

        restored = dict(
            two(900.0), A3=[810.0, 4.95, 0.0, 0.0], C3=[795.0, 1.65, 0.0, 0.0], B3=[700.0, 6.6, 0.0, 0.0]
        )
        result = self.evaluate(
            self.case(
                [(0.0, nine(600.0)), (1.0, nine(600.0)), (2.0, nine(750.0)), (3.0, restored), (4.0, restored)]
            )
        )
        self.assertEqual(result["upstream_formed"]["subjects"], 9)
        self.assertEqual((result["recovered"], result["censored"]), (8, 1))
        self.assertEqual(result["conditional_mean_delay_s"], 2.0)
        self.assertIsNone(next(v for v in result["per_vehicle"] if v["vehicle_id"] == "B3")["delay_s"])

    def test_manifest_saves_json_and_both_reviewable_csv_tables(self):
        case = self.case([(0.0, two()), (1.0, two())])
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"cases": [case.name]}), encoding="utf-8")
        output = self.root / "report"
        result = self.summarize(manifest, output)
        self.assertEqual(len(result["runs"]), 1)
        for name in ("summary.json", "runs.csv", "per_vehicle.csv"):
            self.assertTrue((output / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
