"""Synthetic native artifacts verify independent recomputation and pairing gates."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCES = (
    "experiments/native_sumo.py",
    "experiments/global_reference.py",
    "noa/native_rules.py",
    "run_native_flow.py",
    "research/common.py",
)


class NativeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("experiments.native_comparison"),
            "Independent native comparison summarizer is missing",
        )
        from experiments.native_comparison import summarize_cases

        self.summarize = summarize_cases
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def edit(self, path, change):
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        self.write(path, data)

    def case(self, mode="noa", seed=1, travel=10.0, scenario="lane_drop", version="same"):
        path = self.root / f"{scenario}_{mode}_{seed}_{version}"
        path.mkdir()
        source = {}
        for name in SOURCES:
            target = path / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            content = (name + version).encode()
            target.write_bytes(content)
            source[name] = hashlib.sha256(content).hexdigest()
        arrivals = [
            dict(vehicle_id=f"v{lane}_{row}", requested_s=0.0, lane=lane, x=0.0, speed=5.0)
            for row in range(2)
            for lane in range(3)
        ]
        config = dict(
            mode=mode,
            seed=seed,
            scenario=scenario,
            flow_veh_h_lane=1250.0,
            demand_duration_s=20.0,
            max_time_s=100.0,
            step_s=0.1,
            lane_change_duration_s=1.0,
            request_acceleration_limit_mps2=2.0,
            request_deceleration_limit_mps2=2.0,
            gui=False,
            diagnostic=False,
        )
        self.write(
            path / "input.json",
            dict(
                case=config,
                arrivals=arrivals,
                physical=dict(emissionClass="HBEFA3/PC_G_EU4", tau=0.2),
                speed_mode=31,
                lane_change_mode=512,
                positions_step_s=0.1,
                insertion="SUMO native",
                source_sha256=source,
            ),
        )
        trips = [
            dict(
                **a,
                entered_s=2.0,
                exited_s=2.0 + travel,
                distance_m=1000.0,
                fuel_mg=7500.0,
                lane_events=[],
                lane_completion_events=[],
            )
            for a in arrivals
        ]
        trips[2]["lane_completion_events"] = [
            dict(time_s=8.0, x=990.0, from_lane=2, to_lane=1, y=4.95, vy=0.0)
        ]
        # A lane-index transition alone is a midpoint, not completed lateral motion.
        trips[5]["lane_events"] = [dict(time_s=8.0, x=999.0, from_lane=2, to_lane=1)]
        self.write(path / "trips.json", trips)
        self.write(
            path / "result.json",
            dict(
                **config,
                status="drained",
                safe=True,
                all_completed=True,
                requested=6,
                departed=6,
                completed=6,
                collisions=0,
                teleports=0,
                error=None,
                actual_end_s=20.0,
                sumo_version="SUMO test",
                source_sha256=source,
                mean_travel_time_s=999.0,
                fuel_source="SUMO emissions-device fuel_abs, mg",
            ),
        )
        with gzip.open(path / "positions.jsonl.gz", "wt", encoding="utf-8") as stream:
            for step in range(201):
                t = step / 10
                states = (
                    {
                        a["vehicle_id"]: [
                            300.0 - 30.0 * row - 15.0 * (lane == 1),
                            (lane + 0.5) * 3.3,
                            0.0,
                            0.0,
                        ]
                        for row in range(2)
                        for lane in range(3)
                        for a in [arrivals[row * 3 + lane]]
                    }
                    if 2.0 <= t < 2.0 + travel
                    else {}
                )
                if t >= 8.0 and arrivals[2]["vehicle_id"] in states:
                    states[arrivals[2]["vehicle_id"]][1] = 4.95
                stream.write(json.dumps(dict(time_s=t, states=states)) + "\n")
        return path

    def edit_positions(self, path, change):
        positions = path / "positions.jsonl.gz"
        with gzip.open(positions, "rt", encoding="utf-8") as stream:
            frames = [json.loads(line) for line in stream]
        with gzip.open(positions, "wt", encoding="utf-8") as stream:
            for frame in change(frames):
                stream.write(json.dumps(frame) + "\n")

    def report(self, paths, **kwargs):
        manifest = self.root / "manifest.json"
        self.write(manifest, {"cases": [str(p.relative_to(self.root)) for p in paths]})
        return self.summarize(manifest, **kwargs)

    def reported_case(self):
        path = self.case("transform")
        self.edit(path / "input.json", lambda r: r.update(formation_state_schema="formation_states[id]=0|1"))
        with gzip.open(path / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
            frames = [json.loads(line) for line in stream]
        for frame in frames:
            frame["formation_states"] = {key: 1 for key in frame["states"]}
        self.edit_positions(path, lambda _: frames)
        # Six vehicles each spend ten seconds in state one in a twenty-second record.
        self.edit(path / "result.json", lambda r: r.update(formation_state=dict(
            vehicle_seconds=60.0, participating_vehicle_seconds=60.0,
            participation_rate=1.0, mean_participants=3.0, peak_participants=6,
            episodes=6, mean_episode_s=10.0, max_episode_s=10.0,
        )))
        return path

    def test_self_reported_case_uses_direct_flags_without_complete_layer_detection(self):
        path = self.reported_case()
        with patch("experiments.native_comparison.evaluate_layers", side_effect=AssertionError("geometry should not run")):
            report = self.report([path])
        run = report["runs"][0]
        self.assertTrue(run["performance_eligible"], run["audit_issues"])
        self.assertEqual(run["state_participation_rate"], 1.0)
        self.assertEqual(run["state_peak_participants"], 6)
        self.assertAlmostEqual(run["state_mean_episode_s"], 10.0)
        self.assertNotIn("upstream_mean_multilayer_size", run)
        self.assertEqual(report["run_means"][0]["state_participation_rate_mean"], 1.0)

    def test_declared_reports_cannot_be_replaced_by_geometric_inference(self):
        path = self.reported_case()
        self.edit_positions(path, lambda frames: [
            {k: v for k, v in frame.items() if k != "formation_states"} for frame in frames
        ])
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("missing_formation_state_trace", run["audit_issues"])

    def test_every_physical_vehicle_requires_a_flag(self):
        path = self.reported_case()
        def remove_one(frames):
            flags = next(f for f in frames if f["states"])["formation_states"]
            flags.pop(next(iter(flags)))
            return frames
        self.edit_positions(path, remove_one)
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertTrue(any("formation state vehicle IDs" in issue for issue in run["audit_issues"]))

    def test_recorded_summary_is_checked_against_direct_state_recount(self):
        path = self.reported_case()
        self.edit(path / "result.json", lambda r: r["formation_state"].update(participation_rate=.123))
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("formation_state_summary_mismatch", run["audit_issues"])
        self.assertEqual(run["state_participation_rate"], 1.0)

    def test_recomputes_trip_metrics_and_complete_layers_from_real_artifacts(self):
        report = self.report([self.case()])
        run = report["runs"][0]
        self.assertTrue(run["performance_eligible"])
        self.assertEqual(run["completed"], 6)
        self.assertAlmostEqual(run["mean_entry_wait_s"], 2.0)
        self.assertAlmostEqual(run["mean_travel_time_s"], 10.0)
        self.assertAlmostEqual(run["mean_system_time_s"], 12.0)
        self.assertAlmostEqual(run["fuel_g_per_km"], 7.5)
        self.assertAlmostEqual(run["exit_flow_veh_h"], 1080.0)
        self.assertEqual(run["upstream_peak_multilayer_size"], 6)
        # Six seconds before the merge: five confirmed seconds, one stable second.
        self.assertAlmostEqual(run["upstream_formation_participation_rate"], 5.0 / 10.0)
        self.assertAlmostEqual(run["upstream_stable_participation_rate"], 1.0 / 10.0)
        self.assertAlmostEqual(run["merge_completion_before_drop_rate"], 0.5)
        self.assertIn("detected geometry", run["mode_label"])

    def test_paired_differences_have_candidate_minus_baseline_sign(self):
        report = self.report([self.case(), self.case("transform", travel=9.0)])
        pair = report["pairs"][0]
        self.assertTrue(pair["pair_eligible"])
        self.assertEqual((pair["baseline_mode"], pair["candidate_mode"]), ("noa", "transform"))
        self.assertAlmostEqual(pair["delta_mean_travel_time_s"], -1.0)
        self.assertAlmostEqual(pair["delta_mean_system_time_s"], -1.0)
        self.assertEqual(report["pair_means"][0]["eligible_n"], 1)

    def test_demand_mismatch_is_retained_and_not_compared(self):
        baseline, candidate = self.case(), self.case("transform")
        self.edit(candidate / "input.json", lambda d: d["arrivals"][0].update(requested_s=0.1))
        self.edit(candidate / "trips.json", lambda d: d[0].update(requested_s=0.1))
        report = self.report([baseline, candidate])
        self.assertIn("demand_mismatch", report["pairs"][0]["rejection_reasons"])
        self.assertIsNone(report["pairs"][0]["delta_mean_travel_time_s"])

    def test_parameter_and_source_version_mismatches_are_not_paired(self):
        baseline, candidate = self.case(), self.case("transform", version="other")
        self.edit(candidate / "input.json", lambda d: d["physical"].update(tau=0.3))
        pair = self.report([baseline, candidate])["pairs"][0]
        self.assertIn("parameters_mismatch", pair["rejection_reasons"])
        self.assertIn("source_version_mismatch", pair["rejection_reasons"])
        self.assertFalse(pair["pair_eligible"])

    def test_snapshot_digest_is_verified_against_saved_source_bytes(self):
        path = self.case()
        (path / "source/noa/native_rules.py").write_text("tampered", encoding="utf-8")
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertTrue(any("source_digest_mismatch" in issue for issue in run["audit_issues"]))

    def test_unsafe_run_is_retained_even_if_result_claims_safe(self):
        baseline, candidate = self.case(), self.case("transform")
        self.edit(candidate / "result.json", lambda d: d.update(collisions=1))
        report = self.report([baseline, candidate])
        self.assertEqual(len(report["runs"]), 2)
        run = next(r for r in report["runs"] if r["mode"] == "transform")
        self.assertFalse(run["performance_eligible"])
        self.assertEqual(run["completed"], 6)
        self.assertIsNone(run["mean_travel_time_s"])
        self.assertFalse(report["pairs"][0]["pair_eligible"])

    def test_incomplete_seed_blocks_success_only_mean_performance(self):
        paths = [
            self.case(seed=1),
            self.case("transform", seed=1),
            self.case(seed=2),
            self.case("transform", seed=2),
        ]
        self.edit(
            paths[-1] / "result.json",
            lambda d: d.update(status="time_limit", all_completed=False, completed=5),
        )
        self.edit(paths[-1] / "trips.json", lambda d: d[-1].update(exited_s=None))
        report = self.report(paths)
        summary = report["pair_means"][0]
        self.assertEqual(summary["attempted_n"], 2)
        self.assertEqual(summary["eligible_n"], 1)
        self.assertFalse(summary["group_eligible"])
        self.assertIsNone(summary["delta_mean_travel_time_s_mean"])

    def test_global_label_is_explicit_and_straight_road_has_whole_region(self):
        run = self.report([self.case("global", scenario="straight3")])["runs"][0]
        self.assertIn("not full paper reproduction", run["mode_label"])
        self.assertEqual(run["whole_peak_multilayer_size"], 6)
        self.assertIsNone(run["merge_completion_before_drop_rate"])

    def test_midpoint_or_completed_motion_after_drop_is_not_counted(self):
        path = self.case()
        self.edit(path / "trips.json", lambda d: d[2]["lane_completion_events"][0].update(x=1001.0))
        self.assertEqual(self.report([path])["runs"][0]["merge_completion_before_drop_rate"], 0.0)

    def test_csv_and_json_outputs_are_saved_without_overwriting_old_report(self):
        destination = self.root / "report"
        report = self.report([self.case(), self.case("transform")], output_dir=destination)
        for name in ("summary.json", "runs.csv", "pairs.csv", "run_means.csv", "pair_means.csv"):
            self.assertTrue((destination / name).is_file(), name)
        self.assertEqual(
            json.loads((destination / "summary.json").read_text(encoding="utf-8"))["pairs"], report["pairs"]
        )
        with self.assertRaises(FileExistsError):
            self.report([self.root / "lane_drop_noa_1_same"], output_dir=destination)

    def test_duplicate_seed_scenario_mode_is_an_explicit_error(self):
        path = self.case()
        with self.assertRaises(ValueError):
            self.report([path, path])

    def test_missing_mode_for_a_seed_is_not_silently_dropped_from_paired_mean(self):
        report = self.report([self.case(seed=1), self.case("transform", seed=1), self.case(seed=2)])
        self.assertEqual(len(report["pairs"]), 2)
        missing = next(p for p in report["pairs"] if p["seed"] == 2)
        self.assertIn("missing_candidate", missing["rejection_reasons"])
        self.assertFalse(report["pair_means"][0]["group_eligible"])
        self.assertIsNone(report["pair_means"][0]["delta_mean_travel_time_s_mean"])

    def test_earlier_merge_followed_by_reentry_is_not_final_merge_completion(self):
        path = self.case()
        self.edit(
            path / "trips.json", lambda d: d[2]["lane_completion_events"][0].update(time_s=3.0, x=400.0)
        )
        self.assertEqual(self.report([path])["runs"][0]["merge_completion_before_drop_rate"], 0.0)

    def test_result_and_input_simulation_parameters_must_agree(self):
        path = self.case()
        self.edit(path / "result.json", lambda d: d.update(step_s=0.2))
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("input_result_case_mismatch", run["audit_issues"])

    def test_missing_physical_parameters_are_not_silently_treated_as_equal(self):
        path = self.case()
        self.edit(path / "input.json", lambda d: d.pop("physical"))
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("missing_common_parameters", run["audit_issues"])

    def test_different_actuation_limits_are_not_paired(self):
        for index, key in enumerate(("request_acceleration_limit_mps2", "request_deceleration_limit_mps2")):
            with self.subTest(parameter=key):
                baseline, candidate = self.case(seed=index), self.case("transform", seed=index)
                self.edit(candidate / "input.json", lambda d: d["case"].update({key: 3.0}))
                self.edit(candidate / "result.json", lambda d: d.update({key: 3.0}))
                report = self.report([baseline, candidate])
                pair = report["pairs"][0]
                self.assertFalse(pair["pair_eligible"])
                self.assertIn("parameters_mismatch", pair["rejection_reasons"])
                self.assertIsNone(pair["delta_mean_travel_time_s"])

    def test_result_and_input_actuation_limits_must_agree(self):
        for index, key in enumerate(("request_acceleration_limit_mps2", "request_deceleration_limit_mps2")):
            with self.subTest(parameter=key):
                path = self.case(seed=index)
                self.edit(path / "result.json", lambda d: d.update({key: 9.0}))
                run = self.report([path])["runs"][0]
                self.assertFalse(run["performance_eligible"])
                self.assertIn("input_result_case_mismatch", run["audit_issues"])

    def test_missing_input_actuation_value_cannot_match_the_result(self):
        path = self.case()
        self.edit(path / "input.json", lambda d: d["case"].pop("request_deceleration_limit_mps2"))
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("input_result_case_mismatch", run["audit_issues"])

    def test_legacy_unrecorded_limits_remain_readable_but_do_not_match_shaped_runs(self):
        legacy, shaped = self.case(), self.case("transform")
        for key in ("request_acceleration_limit_mps2", "request_deceleration_limit_mps2"):
            self.edit(legacy / "input.json", lambda d: d["case"].pop(key))
            self.edit(legacy / "result.json", lambda d: d.pop(key))
        report = self.report([legacy, shaped])
        self.assertTrue(report["runs"][0]["performance_eligible"])
        self.assertFalse(report["pairs"][0]["pair_eligible"])
        self.assertIn("parameters_mismatch", report["pairs"][0]["rejection_reasons"])

    def test_empty_position_trace_is_audit_failure(self):
        path = self.case()
        self.edit_positions(path, lambda frames: [])
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("empty_position_trace", run["audit_issues"])
        self.assertIsNone(run["first_position_sample_s"])
        self.assertIsNone(run["last_position_sample_s"])

    def test_truncated_position_tail_blocks_pair_and_group_means(self):
        baseline, candidate = self.case(), self.case("transform")
        self.edit_positions(candidate, lambda frames: frames[:-1])
        report = self.report([baseline, candidate])
        run = report["runs"][1]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("position_trace_end_mismatch", run["audit_issues"])
        self.assertAlmostEqual(run["last_position_sample_s"], 19.9)
        self.assertFalse(report["pairs"][0]["pair_eligible"])
        self.assertIsNone(report["pair_means"][0]["delta_mean_travel_time_s_mean"])

    def test_missing_interior_sample_is_audit_failure(self):
        path = self.case()
        self.edit_positions(path, lambda frames: [f for f in frames if f["time_s"] != 5.0])
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("position_sample_gap_exceeds_declared_step", run["audit_issues"])
        self.assertAlmostEqual(run["max_position_sample_step_s"], 0.2)

    def test_late_first_sample_is_audit_failure(self):
        path = self.case()
        self.edit_positions(path, lambda frames: frames[2:])
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("position_trace_start_mismatch", run["audit_issues"])
        self.assertAlmostEqual(run["first_position_sample_s"], 0.2)

    def test_all_empty_states_with_departed_vehicles_are_audit_failure(self):
        path = self.case()
        self.edit_positions(path, lambda frames: [dict(f, states={}) for f in frames])
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("position_trace_has_no_vehicles", run["audit_issues"])

    def test_full_trace_allows_zero_or_one_step_start_and_float_roundoff(self):
        for first_tick in (0, 1):
            with self.subTest(first_tick=first_tick):
                path = self.case(seed=first_tick + 1)
                self.edit_positions(
                    path,
                    lambda frames: [dict(f, time_s=f["time_s"] + 1e-10) for f in frames[first_tick:]],
                )
                run = self.report([path])["runs"][0]
                self.assertTrue(run["performance_eligible"], run["audit_issues"])
                self.assertIn("first_position_sample_s", run)
                self.assertAlmostEqual(run["first_position_sample_s"], first_tick / 10)
                self.assertAlmostEqual(run["last_position_sample_s"], 20.0)
                self.assertAlmostEqual(run["max_position_sample_step_s"], 0.1)

    def test_position_gaps_are_checked_against_declared_sampling_interval(self):
        path = self.case()
        self.edit(path / "input.json", lambda d: d.update(positions_step_s=0.05))
        run = self.report([path])["runs"][0]
        self.assertFalse(run["performance_eligible"])
        self.assertIn("position_sample_gap_exceeds_declared_step", run["audit_issues"])

    def test_metadata_records_current_offline_auditor_and_layer_evaluator(self):
        from experiments import native_comparison

        report = self.report([self.case()])
        metadata = report["metadata"]
        self.assertIn("audit_source_sha256", metadata)
        self.assertEqual(
            metadata["audit_source_sha256"],
            hashlib.sha256(Path(native_comparison.__file__).read_bytes()).hexdigest(),
        )
        self.assertEqual(
            metadata["layer_evaluator_source_sha256"],
            hashlib.sha256(
                Path(native_comparison.__file__).with_name("complete_layers.py").read_bytes()
            ).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
