"""Tiny end-to-end fixtures; no SUMO installation or simulations required."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("analyze_trials.py")
SOURCES = ("experiments/native_sumo.py", "experiments/global_reference.py",
           "experiments/complete_layers.py", "noa/native_rules.py",
           "run_native_flow.py", "research/common.py")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root, candidate="base", mode="transform", *, unsafe=False):
    run = root / (candidate + "_" + mode)
    run.mkdir()
    hashes = {}
    for name in SOURCES:
        data = (candidate if name == "noa/native_rules.py" else name).encode()
        path = run / "source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    case = dict(mode=mode, seed=1, flow_veh_h_lane=1250,
                demand_duration_s=600, scenario="lane_drop", max_time_s=900,
                step_s=0.1, lane_change_duration_s=1.0, gui=False, diagnostic=False,
                runtime={"python_version": "3.fixture"})
    arrival = dict(vehicle_id="v", requested_s=599.8, depart_lane=0,
                   depart_x=0, depart_speed=10)
    write_json(run / "input.json", dict(case=case, arrivals=[arrival],
               physical=dict(length=4.0, width=1.8, minGap=1.5, tau=0.2, accel=5.0,
                             decel=10.0, emergencyDecel=30.0, maxSpeed=33.3,
                             speedFactor=1.0, speedDev=0.0, sigma=0.0,
                             carFollowModel="IDM", emissionClass="HBEFA3/PC_G_EU4"), speed_mode=31,
               lane_change_mode=512, positions_step_s=0.1,
               positions_schema="time_s, states[id]=[x,y,speed,acceleration]",
               formation_state_schema="formation_states[id]=0|1",
               source_sha256=hashes))
    direct = dict(vehicle_seconds=0.2, participating_vehicle_seconds=0.2,
                  participation_rate=1.0, mean_participants=1.0,
                  peak_participants=1, episodes=1,
                  mean_episode_s=0.2, max_episode_s=0.2)
    result = dict(**case, status="unsafe" if unsafe else "drained", safe=not unsafe,
                  all_completed=not unsafe, performance_comparison_eligible=not unsafe,
                  requested=1, departed=1, completed=0 if unsafe else 1,
                  actual_end_s=600, collisions=int(unsafe), teleports=0,
                  error=None, source_sha256=hashes, sumo_version="SUMO fixture",
                  formation_state=direct, mean_travel_time_s=0.2,
                  mean_system_time_s=0.2, mean_entry_wait_s=0,
                  fuel_g_per_km=2, completed_subset_mean_travel_time_s=0.2,
                  completed_subset_mean_system_time_s=0.2,
                  departed_subset_mean_entry_wait_s=0,
                  completed_subset_fuel_g_per_km=2, completion_fraction=int(not unsafe),
                  lane_changes=1, lane_transitions={"0->1": 1},
                  lane_change_completions=1)
    write_json(run / "result.json", result)
    write_json(run / "trips.json", [dict(**arrival, entered_s=599.8,
               exited_s=None if unsafe else 600, distance_m=1200, fuel_mg=2400,
               lane_changes=1, lane_completion_events=[{"time_s": 599.9}])])
    frames = [dict(time_s=t, states={"v": [x, 1.65, 10, 0]},
                   formation_states={"v": flag})
              for t, x, flag in ((599.8, 0, 1), (599.9, 700, 1), (600, 1200, 0))]
    with gzip.open(run / "positions.jsonl.gz", "wt", encoding="utf-8") as stream:
        for frame in frames:
            stream.write(json.dumps(frame) + "\n")
    write_json(run / "sumo_command.json", ["sumo", "--net-file", str(run / "native.net.xml"),
               "--step-length", ".1", "--seed", "1"])
    return dict(candidate=candidate, stage="trial", flow=1250, seed=1,
                scenario="lane_drop", mode=mode, run_dir=str(run))


class AnalyzeTrialsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def analyze(self, records):
        manifest = self.root / "manifest.json"
        write_json(manifest, records)
        output = self.root / "out"
        process = subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(manifest),
                                  "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        for filename in ("per_case.csv", "paired.csv", "paired_aggregates.csv",
                         "segment_vehicles.csv", "report.md"):
            self.assertTrue((output / filename).is_file(), filename)
        return json.loads((output / "analysis.json").read_text(encoding="utf-8"))

    def change_json(self, run, name, mutate):
        path = Path(run["run_dir"]) / name
        data = json.loads(path.read_text())
        mutate(data)
        write_json(path, data)

    def test_valid_pair_uses_direct_stats_and_observed_crossings(self):
        base = fixture(self.root)
        trial = fixture(self.root, "T")
        self.change_json(trial, "result.json", lambda d: d.update(mean_travel_time_s=0.25))
        data = self.analyze([base, trial])
        self.assertTrue(all(case["eligible"] for case in data["cases"]))
        case = data["cases"][1]
        self.assertEqual(case["flag_peak_participants"], 1)
        self.assertAlmostEqual(case["flag_recomputed_mean_episode_s"], 0.2)
        self.assertAlmostEqual(case["upstream_mean_time_s"], 0.1 * 500 / 700)
        self.assertAlmostEqual(case["bottleneck_mean_time_s"],
                               0.1 * 60 / 700 + 0.1 * 400 / 500)
        pair = next(p for p in data["pairs"] if p["comparison"] == "candidate_vs_base")
        self.assertTrue(pair["eligible"])
        self.assertAlmostEqual(pair["delta_mean_travel_time_s"], 0.05)

    def test_unsafe_case_retained_and_aggregate_suppressed(self):
        data = self.analyze([fixture(self.root), fixture(self.root, "T", unsafe=True)])
        self.assertEqual(len(data["cases"]), 2)
        self.assertFalse(data["cases"][1]["eligible"])
        self.assertIsNone(data["pairs"][0]["delta_mean_travel_time_s"])
        self.assertTrue(data["aggregates"][0]["suppressed"])

    def test_snapshot_tampering_blocks_pair(self):
        base, trial = fixture(self.root), fixture(self.root, "T")
        (Path(trial["run_dir"]) / "source/noa/native_rules.py").write_text("tampered")
        data = self.analyze([base, trial])
        self.assertIn("snapshot_hash", data["cases"][1]["issues"])
        self.assertFalse(data["pairs"][0]["eligible"])

    def test_demand_and_unrelated_source_mismatch_block_pair(self):
        base, trial = fixture(self.root), fixture(self.root, "T")
        self.change_json(trial, "input.json", lambda d: d["arrivals"][0].update(depart_lane=1))
        data = self.analyze([base, trial])
        self.assertIn("demand_mismatch", data["pairs"][0]["issues"])
        self.assertFalse(data["pairs"][0]["eligible"])

    def reseal_source(self, record, name, contents):
        run = Path(record["run_dir"])
        data = contents.encode()
        (run / "source" / name).write_bytes(data)
        for filename in ("input.json", "result.json"):
            self.change_json(record, filename, lambda d: d["source_sha256"].update(
                {name: hashlib.sha256(data).hexdigest()}))

    def test_same_candidate_modes_must_have_identical_rules(self):
        noa, transform = fixture(self.root, mode="noa"), fixture(self.root)
        self.reseal_source(transform, "noa/native_rules.py", "different rules")
        data = self.analyze([noa, transform])
        self.assertTrue(all(c["eligible"] for c in data["cases"]))
        self.assertIn("rules_mismatch", data["pairs"][0]["issues"])

    def test_unrelated_source_change_is_not_a_candidate_rule_difference(self):
        base, trial = fixture(self.root), fixture(self.root, "T")
        self.reseal_source(trial, "experiments/native_sumo.py", "changed recorder")
        data = self.analyze([base, trial])
        self.assertIn("sources_mismatch", data["pairs"][0]["issues"])

    def test_nonbinary_flags_are_rejected(self):
        base, trial = fixture(self.root), fixture(self.root, "T")
        path = Path(trial["run_dir"]) / "positions.jsonl.gz"
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            frames = [json.loads(line) for line in stream]
        frames[0]["formation_states"]["v"] = True
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            stream.writelines(json.dumps(frame) + "\n" for frame in frames)
        data = self.analyze([base, trial])
        self.assertIn("invalid_formation_flags", data["cases"][1]["issues"])

    def test_missing_physics_and_sumo_command_block_provenance(self):
        base, trial = fixture(self.root), fixture(self.root, "T")
        self.change_json(trial, "input.json", lambda d: d.pop("physical"))
        (Path(trial["run_dir"]) / "sumo_command.json").unlink()
        data = self.analyze([base, trial])
        self.assertIn("missing_physical_evidence", data["cases"][1]["issues"])
        self.assertIn("missing_sumo_command", data["cases"][1]["issues"])

    def test_sumo_command_difference_and_physics_difference_block_pair(self):
        base, trial = fixture(self.root), fixture(self.root, "T")
        self.change_json(trial, "input.json", lambda d: d["physical"].update(width=1.9))
        self.change_json(trial, "sumo_command.json", lambda d: d.extend(["--collision.action", "none"]))
        data = self.analyze([base, trial])
        self.assertIn("physics_mismatch", data["pairs"][0]["issues"])
        self.assertIn("sumo_mismatch", data["pairs"][0]["issues"])

    def test_one_bad_seed_suppresses_whole_group_without_dropping_its_row(self):
        records = [fixture(self.root), fixture(self.root, "T")]
        second = self.root / "seed2"
        second.mkdir()
        for record in (fixture(second), fixture(second, "T", unsafe=True)):
            record["seed"] = 2
            self.change_json(record, "input.json", lambda d: d["case"].update(seed=2))
            self.change_json(record, "result.json", lambda d: d.update(seed=2))
            records.append(record)
        data = self.analyze(records)
        group = next(g for g in data["aggregates"] if g["comparison"] == "candidate_vs_base")
        self.assertEqual(group["pairs"], 2)
        self.assertEqual(group["eligible_pairs"], 1)
        self.assertTrue(group["suppressed"])
        self.assertIsNone(group["mean_delta_mean_travel_time_s"])

    def test_missing_run_and_missing_mode_remain_visible(self):
        missing = dict(candidate="T", stage="trial", flow=1250, seed=1,
                       scenario="lane_drop", mode="transform", run_dir=str(self.root / "missing"))
        data = self.analyze([fixture(self.root, mode="noa"), missing])
        self.assertEqual(len(data["cases"]), 2)
        self.assertTrue(any("missing_" in p["issues"] for p in data["pairs"]))

    def test_invalid_flags_and_saved_summary_mismatch_block_pair(self):
        base, trial = fixture(self.root), fixture(self.root, "T")
        self.change_json(trial, "result.json", lambda d: d["formation_state"].update(peak_participants=2))
        data = self.analyze([base, trial])
        self.assertIn("flag_summary_mismatch", data["cases"][1]["issues"])
        self.assertFalse(data["cases"][1]["eligible"])

    def test_same_candidate_noa_vs_transform_and_partial_segment_eligibility(self):
        noa, transform = fixture(self.root, mode="noa"), fixture(self.root)
        path = Path(transform["run_dir"]) / "positions.jsonl.gz"
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            frames = [json.loads(line) for line in stream]
        frames[-1]["states"]["v"][0] = 800
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            stream.writelines(json.dumps(frame) + "\n" for frame in frames)
        data = self.analyze([noa, transform])
        pair = next(p for p in data["pairs"] if p["comparison"] == "transform_vs_noa")
        self.assertTrue(pair["eligible"])
        self.assertEqual(data["cases"][1]["bottleneck_eligible_vehicles"], 0)
        self.assertEqual(data["cases"][1]["upstream_eligible_vehicles"], 1)
        self.assertIsNone(pair["delta_bottleneck_mean_time_s"])
        self.assertEqual(pair.get("bottleneck_matched_vehicles"), 0)
        self.assertEqual(pair.get("upstream_matched_vehicles"), 1)


if __name__ == "__main__":
    unittest.main()
