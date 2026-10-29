"""Measured gate times, exposure integration, censoring and flow-safe pairing."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


class BottleneckAttributionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("experiments.bottleneck_attribution"),
            "The independent bottleneck evaluator is missing",
        )
        from experiments import bottleneck_attribution

        self.module = bottleneck_attribution
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def case(self, *, mode="noa", scenario="lane_drop", flow=500, seed=1,
             frames=None, end=12.1, completed=True, vehicles=("v",)):
        from experiments.native_comparison import SOURCES

        path = self.root / f"{flow}_{scenario}_{mode}_{seed}"
        path.mkdir()
        hashes = {}
        for name in SOURCES:
            target = path / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            content = name.encode()
            target.write_bytes(content)
            hashes[name] = hashlib.sha256(content).hexdigest()
        arrivals = [dict(vehicle_id=v, requested_s=0.0, lane=0, x=0.0, speed=100.0)
                    for v in vehicles]
        config = dict(mode=mode, scenario=scenario, seed=seed,
                      flow_veh_h_lane=flow, demand_duration_s=10.0,
                      max_time_s=700.0, step_s=0.1, lane_change_duration_s=1.0)
        self.write(path / "input.json", dict(
            case=config, arrivals=arrivals, source_sha256=hashes,
            physical={"tau": 0.2}, speed_mode=31, lane_change_mode=512,
            insertion="SUMO native", positions_step_s=0.1))
        self.write(path / "result.json", dict(
            **config, status="drained" if completed else "time_limit", safe=True,
            requested=len(vehicles), departed=len(vehicles),
            completed=len(vehicles) if completed else 0,
            all_completed=completed, collisions=0, teleports=0, error=None,
            actual_end_s=end, sumo_version="SUMO synthetic", source_sha256=hashes))
        self.write(path / "trips.json", [dict(
            **a, entered_s=0.0, exited_s=end if completed else None,
            distance_m=1200.0, fuel_mg=1000.0, lane_completion_events=[])
            for a in arrivals])
        if frames is None:
            frames = [dict(time_s=i / 10, states={
                v: [i * 10.0, 1.65, 100.0, 0.0] for v in vehicles})
                for i in range(121)]
            frames.append(dict(time_s=12.1, states={}))
        self.write_frames(path, frames)
        return path

    def write_frames(self, path, frames):
        with gzip.open(path / "positions.jsonl.gz", "wt", encoding="utf-8") as stream:
            for frame in frames:
                stream.write(json.dumps(frame) + "\n")

    def report(self, paths, output=None):
        manifest = self.root / "manifest.json"
        self.write(manifest, {"cases": [str(p.relative_to(self.root)) for p in paths]})
        return self.module.summarize_cases(manifest, output)

    def test_constant_speed_gates_segments_and_full_region_exposure(self):
        run = self.module.evaluate_case(self.case())
        self.assertTrue(run["attribution_eligible"], run["audit_issues"])
        vehicle = run["vehicles"][0]
        self.assertEqual(set(vehicle["gates"]), {"100", "600", "640", "800", "1000", "1100"})
        self.assertAlmostEqual(vehicle["gates"]["640"]["time_s"], 6.4)
        self.assertAlmostEqual(vehicle["segments_s"]["640_1100"], 4.6)
        self.assertAlmostEqual(run["mean_segment_100_600_s"], 5.0)
        region = run["region_full"]
        self.assertAlmostEqual(region["vehicle_s"], 2.0)
        self.assertAlmostEqual(region["mean_speed_mps"], 100.0)
        self.assertAlmostEqual(region["density_veh_km_lane"], 2.0 / 12.1 / 0.6)
        self.assertEqual(region["low_speed_vehicle_s"], 0.0)
        self.assertFalse(run["region_window"]["window_complete"])
        self.assertIsNone(run["flow_1000m_veh_h"])

    def test_linear_interpolation_uses_adjacent_measured_samples(self):
        frames = [dict(time_s=i / 10, states={"v": [99 + 20 * i, 1.65, 200, 0]})
                  for i in range(57)]
        run = self.module.evaluate_case(self.case(frames=frames, end=5.6))
        gate = run["vehicles"][0]["gates"]["100"]
        self.assertEqual(gate["status"], "observed")
        self.assertAlmostEqual(gate["time_s"], 0.005)

    def test_stationary_samples_count_vehicle_seconds_and_strict_speed_threshold(self):
        frames = [dict(time_s=i / 10, states={
            "a": [850, 1.65, 0, 0], "b": [900, 4.95, 5, 0]}) for i in range(11)]
        run = self.module.evaluate_case(self.case(frames=frames, end=1.0, completed=False,
                                                vehicles=("a", "b")))
        region = run["region_full"]
        self.assertAlmostEqual(region["vehicle_s"], 2.0)
        self.assertAlmostEqual(region["low_speed_vehicle_s"], 1.0)
        self.assertAlmostEqual(region["low_speed_fraction"], 0.5)
        self.assertEqual(region["max_simultaneous_low_speed"], 1)
        self.assertAlmostEqual(region["density_veh_km_lane"], 2 / 0.6)
        self.assertAlmostEqual(region["mean_speed_mps"], 2.5)

    def test_first_observation_beyond_gate_is_left_censored(self):
        frames = [dict(time_s=i / 10, states={"v": [110 + 10 * i, 1.65, 100, 0]})
                  for i in range(101)]
        run = self.module.evaluate_case(self.case(frames=frames, end=10.0))
        gate = run["vehicles"][0]["gates"]["100"]
        self.assertEqual(gate["status"], "left_censored")
        self.assertIsNone(gate["time_s"])
        self.assertIsNone(run["mean_segment_100_600_s"])
        self.assertFalse(run["attribution_eligible"])

    def test_unpassed_and_unobserved_requests_remain_and_suppress_means(self):
        frames = [dict(time_s=i / 10, states={"a": [i * 10, 1.65, 100, 0]})
                  for i in range(91)]
        run = self.module.evaluate_case(self.case(frames=frames, end=9, completed=False,
                                                vehicles=("a", "b")))
        self.assertEqual(len(run["vehicles"]), 2)
        a, b = run["vehicles"]
        self.assertEqual(a["gates"]["1000"]["status"], "right_censored")
        self.assertEqual(b["gates"]["100"]["status"], "not_observed")
        self.assertIsNone(a["segments_s"]["640_1100"])
        self.assertEqual(run["segment_censored_n"]["640_1100"], 2)
        self.assertIsNone(run["mean_segment_640_1100_s"])

    def test_global_and_vehicle_gaps_never_interpolate_crossings(self):
        for missing_vehicle in (False, True):
            with self.subTest(missing_vehicle=missing_vehicle):
                frames = [dict(time_s=i / 10, states={"v": [90 + 10 * i, 1.65, 100, 0]})
                          for i in range(5)]
                if missing_vehicle:
                    frames[1]["states"] = {}
                else:
                    del frames[1]
                path = self.case(seed=int(missing_vehicle) + 1, frames=frames, end=0.4)
                run = self.module.evaluate_case(path)
                self.assertFalse(run["attribution_eligible"])
                self.assertIsNone(run["vehicles"][0]["gates"]["100"]["time_s"])
                self.assertTrue(any("gap" in issue for issue in run["audit_issues"]))

    def test_empty_truncated_and_nonmonotonic_trace_are_ineligible(self):
        for seed, frames in enumerate(([], [dict(time_s=0, states={})],
                                     [dict(time_s=0.1, states={}), dict(time_s=0, states={})]), 1):
            run = self.module.evaluate_case(self.case(seed=seed, frames=frames))
            self.assertFalse(run["attribution_eligible"])
            self.assertTrue(run["audit_issues"])
        path = self.case(seed=4)
        with gzip.open(path / "positions.jsonl.gz", "at", encoding="utf-8") as stream:
            stream.write('{"time_s":')
        run = self.module.evaluate_case(path)
        self.assertFalse(run["attribution_eligible"])

    def test_missing_vehicle_samples_at_entry_or_before_exit_are_ineligible(self):
        for seed, missing in ((1, {0, 1, 2}), (2, set(range(112, 121)))):
            frames = [dict(time_s=i / 10, states={"v": [10 * i, 1.65, 100, 0]}
                           if i not in missing and i < 121 else {}) for i in range(122)]
            run = self.module.evaluate_case(self.case(seed=seed, frames=frames))
            self.assertFalse(run["attribution_eligible"])
            self.assertTrue(any("observation_gap" in issue for issue in run["audit_issues"]))

    def test_window_flow_counts_first_crossings_in_inclusive_100_to_600(self):
        frames = [dict(time_s=i / 10, states={"v": [i - 1, 1.65, 10, 0]})
                  for i in range(6002)]
        run = self.module.evaluate_case(self.case(frames=frames, end=600.1))
        self.assertEqual(run["flow_1000m_crossings"], 1)
        self.assertAlmostEqual(run["flow_1000m_veh_h"], 7.2)
        self.assertTrue(run["region_window"]["window_complete"])
        self.assertEqual(run["region_window"]["duration_s"], 500)

    def test_manifest_pairs_flows_separately_and_uses_noa_minus_transform_reduction(self):
        paths = [self.case(mode=mode, scenario=scenario, flow=flow)
                 for flow in (500, 750) for scenario in ("lane_drop", "straight3")
                 for mode in ("noa", "transform")]
        report = self.report(paths, self.root / "report")
        self.assertEqual(len(report["attributions"]), 2)
        self.assertEqual({r["flow_veh_h_lane"] for r in report["attributions"]}, {500, 750})
        self.assertTrue(all(r["pair_eligible"] for r in report["attributions"]))
        self.assertTrue(all(r["reduction_mean_segment_640_1100_s"] == 0 for r in report["attributions"]))
        self.assertTrue((self.root / "report" / "vehicles.csv").is_file())
        self.assertIn("evaluator_source_sha256", report["metadata"])
        self.assertTrue(all(r["input_sha256"] for r in report["runs"]))
        self.assertEqual(len(report["run_means"]), 8)
        self.assertTrue(all(r["mean_segment_640_1100_s_mean"] == 4.6 for r in report["run_means"]))
        with self.assertRaises(FileExistsError):
            self.report(paths, self.root / "report")

    def test_missing_seed_and_incomplete_run_suppress_all_seed_mean(self):
        paths = [self.case(mode=mode, scenario=scenario, seed=seed,
                           completed=not (seed == 2 and mode == "transform"))
                 for seed in (1, 2) for scenario in ("lane_drop", "straight3")
                 for mode in ("noa", "transform")]
        report = self.report(paths)
        self.assertEqual(report["attribution_means"][0]["eligible_n"], 1)
        self.assertIsNone(report["attribution_means"][0]["reduction_mean_segment_640_1100_s_mean"])
        transform = next(row for row in report["run_means"]
                         if row["mode"] == "transform" and row["scenario"] == "lane_drop")
        self.assertEqual(transform["eligible_n"], 1)
        self.assertIsNone(transform["mean_segment_640_1100_s_mean"])
        report = self.report(paths[:-1])
        self.assertEqual(len(report["attributions"]), 2)
        self.assertFalse(report["attributions"][-1]["pair_eligible"])

    def test_nonzero_difference_in_differences_separates_upstream_and_bottleneck(self):
        paths = []
        for mode, scenario, pauses in (
            ("noa", "straight3", ()),
            ("noa", "lane_drop", ((7.0, 2.0),)),
            ("transform", "straight3", ((5.0, 1.0),)),
            ("transform", "lane_drop", ((5.0, 0.5), (9.0, 0.5))),
        ):
            end = 12.1 + sum(pause for _, pause in pauses)
            frames = []
            for tick in range(round(end * 10) + 1):
                now = tick / 10
                road_time = now
                prior_delay = 0
                for start, pause in pauses:
                    road_time -= min(max(0, now - start - prior_delay), pause)
                    prior_delay += pause
                states = {"v": [100 * road_time, 1.65, 100, 0]} if road_time <= 12 else {}
                frames.append(dict(time_s=now, states=states))
            path = self.case(mode=mode, scenario=scenario, frames=frames, end=end)
            trips = json.loads((path / "trips.json").read_text(encoding="utf-8"))
            trips[0]["exited_s"] = end
            self.write(path / "trips.json", trips)
            paths.append(path)
        report = self.report(paths)
        row = report["attributions"][0]
        self.assertTrue(row["pair_eligible"], row["rejection_reasons"])
        self.assertAlmostEqual(row["reduction_mean_segment_640_1100_s"], 1.5)
        self.assertAlmostEqual(row["reduction_mean_travel_time_s"], 2.0)
        self.assertAlmostEqual(row["reduction_mean_segment_100_600_s"], 0.5)
        self.assertTrue(row["supports_bottleneck_time_reduction"])

    def test_source_mismatch_and_formation_ablation_are_explicit(self):
        paths = [self.case(mode=mode, scenario=scenario)
                 for scenario in ("lane_drop", "straight3")
                 for mode in ("noa", "formation", "transform")]
        report = self.report(paths)
        self.assertEqual(len(report["ablations"]), 2)
        self.assertTrue(all(row["scenario"] == "lane_drop" for row in report["ablations"]))
        (paths[-1] / "source/noa/native_rules.py").write_text("changed", encoding="utf-8")
        report = self.report(paths)
        self.assertFalse(report["attributions"][0]["pair_eligible"])
        self.assertTrue(any("source_digest_mismatch" in reason for reason in report["runs"][-1]["audit_issues"]))

    def test_duplicate_flow_seed_scenario_mode_is_rejected(self):
        path = self.case()
        with self.assertRaisesRegex(ValueError, "Duplicate flow/seed/scenario/mode"):
            self.report([path, path])


if __name__ == "__main__":
    unittest.main()
