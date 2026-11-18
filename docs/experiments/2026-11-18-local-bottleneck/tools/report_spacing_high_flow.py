"""Recompute the 2000 veh/h/lane spacing comparisons, including both interrupted attempts."""

import argparse
import csv
import json
from math import isclose
from multiprocessing import Pool
from pathlib import Path
from statistics import mean
import xml.etree.ElementTree as ET

from run_shared_physics import ROOT, PROFILES, digest, read_json, write_json
from summarize_shared_physics import evaluate_case
from experiments.bottleneck_attribution import _region


HERE = Path(__file__).resolve().parents[1]
RUNS = ROOT / "tmp/staggered_bottleneck"
RULE = "noa/native_rules.py"
BATCHES = {
    "tau_only": {
        "OriginalNOA": ["n18_tau2000_old_noa_r01"],
        "VisibleGapNOA": ["n18_tau2000_visible_r01", "n18_tau2000_visible_r02"],
        "ReceivingOnly": ["n18_tau2000_spacing_r01", "n18_tau2000_spacing_r02"],
    },
    "transfer": {
        "VisibleGapNOA": ["n18_transfer_long_visible_r02"],
        "ReceivingOnly": ["n18_transfer_long_spacing_r02"],
    },
}
METRICS = (
    "mean_system_time_s", "mean_entry_wait_s", "mean_travel_time_s",
    "mean_segment_100_600_s", "mean_segment_800_1100_s",
    "low_speed_vehicle_s", "flow_1000m_veh_h", "fuel_g_per_km", "last_exit_s",
    "waiting_at_demand_end", "onroad_at_demand_end",
)


def inspect_attempts(batches, mode):
    completed, interrupted = {}, []
    for name in batches:
        batch = RUNS / name
        protocol = read_json(batch / "protocol.json")
        workers = {row["seed"]: row for row in read_json(batch / "manifest.json")}
        for task in protocol["tasks"]:
            seed = task["seed"]
            assert task["flow"] == 2000 and task["mode"] == mode
            folder = batch / "case" / f"{task['profile']}_2000_{seed}_{mode}"
            run, = (file.parent for file in folder.glob("*/result.json"))
            if seed not in workers:
                result = read_json(run / "result.json")
                assert result["status"] == "starting" and not (run / "trips.json").exists()
                interrupted.append(dict(run=run.relative_to(ROOT).as_posix(), seed=seed, status="starting"))
                continue
            worker = workers[seed]
            log = read_json(folder / "worker.log")
            assert log["status"] == "completed" and log["returncode"] == worker["worker_exit"] == 0
            assert worker["verified"] and Path(worker["run"]) == run and seed not in completed
            completed[seed] = run
    return completed, interrupted


def measure(run, label, profile, seed, end):
    inp = read_json(run / "input.json")
    res = read_json(run / "result.json")
    case = inp["case"].copy()
    assert res["status"] == "drained" and res["collisions"] == res["teleports"] == 0
    assert res["safe"] and res["all_completed"] and res["completed"] == len(inp["arrivals"])
    assert case.pop("mode") == ("transform" if label == "ReceivingOnly" else "noa")
    assert case["seed"] == seed and case["scenario"] == "lane_drop" and case["flow_veh_h_lane"] == 2000
    assert case["demand_duration_s"] == end and case["max_time_s"] == (2700 if end == 1800 else 1200)
    assert all(float(inp["physical"][k]) == float(v) for k, v in PROFILES[profile].items())
    vtype = ET.parse(run / "native.rou.xml").getroot().find("vType")
    assert vtype.attrib == {"id": "CAV_ICV", **{k: str(v) for k, v in inp["physical"].items()}}
    rules = (RUNS / "n18_phys_r01/src/control" / RULE if label == "OriginalNOA"
             else HERE / "rules" / (label + ".py"))
    assert inp["source_sha256"][RULE] == digest(rules.read_bytes())
    assert inp["source_sha256"] == res["source_sha256"]
    audit = evaluate_case(run)
    assert audit["attribution_eligible"] and audit["all_completed"] and audit["safe"], audit["audit_issues"]
    window = _region(audit["region_steps"], 100, end, True)
    assert window["window_complete"]
    crossings = sum(100 <= car["gates"]["1000"]["time_s"] <= end for car in audit["vehicles"])
    metrics = {k: audit[k] for k in METRICS[:5]}
    trips = audit["vehicles"]
    metrics.update(low_speed_vehicle_s=window["low_speed_vehicle_s"], flow_1000m_veh_h=crossings*3600/(end-100),
                   fuel_g_per_km=res["fuel_g_per_km"], last_exit_s=max(t["exited_s"] for t in trips),
                   waiting_at_demand_end=sum(t["requested_s"] <= end < t["entered_s"] for t in trips),
                   onroad_at_demand_end=sum(t["entered_s"] <= end < t["exited_s"] for t in trips))
    for k in METRICS[:3]:
        assert isclose(metrics[k], res[k], rel_tol=1e-9)
    metadata = {**inp, "case": case, "source_sha256": {k: v for k, v in inp["source_sha256"].items() if k != RULE},
                "sumo_version": res["sumo_version"]}
    fingerprint = digest(json.dumps(metadata, sort_keys=True).encode())
    return dict(label=label, seed=seed, run=run.relative_to(ROOT).as_posix(), common_input_sha256=fingerprint,
                demand_sha256=audit["demand_sha256"], rule_sha256=inp["source_sha256"][RULE],
                positions_sha256=audit["positions_sha256"], trips_sha256=audit["trips_sha256"],
                requested=res["requested"], completed=res["completed"], actual_end_s=res["actual_end_s"],
                collisions=res["collisions"], teleports=res["teleports"], crossing_count=crossings, **metrics)


def timegap_effects(rows):
    controls = {}
    for r in read_json(HERE / "stage/visible_gap_noa_600.json")["cases"]:
        if r["flow"] == 2000:
            controls["OriginalNOA", r["seed"]] = Path(r["original"]["path"])
            controls["VisibleGapNOA", r["seed"]] = Path(r["gap"]["path"])
    with (HERE / "stage/spacing_standard/per_case.csv").open(encoding="utf-8-sig") as stream:
        for r in csv.DictReader(stream):
            if r["candidate"] == "ReceivingOnly" and r["scenario"] == "lane_drop" and float(r["flow"]) == 2000:
                controls["ReceivingOnly", int(r["seed"])] = Path(r["run_dir"])
    effects = []
    for row in rows:
        control = controls[row["label"], row["seed"]]
        run = ROOT / row["run"]
        a, b = (read_json(p / "input.json") for p in (control, run))
        assert {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)} == {"physical", "source_sha256"}
        assert {**a["physical"], "tau": 0.65} == b["physical"] and a["physical"]["tau"] == 0.2
        native = "experiments/native_sumo.py"
        assert {**a["source_sha256"], native: b["source_sha256"][native]} == b["source_sha256"]
        original = (control / "source" / native).read_bytes()
        assert original.count(b"    tau=0.2,") == 1
        assert original.replace(b"    tau=0.2,", b"    tau=0.65,") == (run / "source" / native).read_bytes()
        result = read_json(control / "result.json")
        assert result["safe"] and result["all_completed"] and result["completed"] == row["completed"]
        assert result["sumo_version"] == read_json(run / "result.json")["sumo_version"]
        times = {k: result[k] for k in METRICS[:3]}
        effects.append(dict(label=row["label"], seed=row["seed"], control=control.relative_to(ROOT).as_posix(),
                            time_at_tau_020=times, tau_065_minus_020={k: row[k] - v for k, v in times.items()}))
    return effects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=BATCHES)
    args = parser.parse_args()
    profile = args.profile
    seeds, end = ([211, 212], 600) if profile == "tau_only" else ([221, 222], 1800)
    tasks, incomplete = [], []
    for label, names in BATCHES[profile].items():
        runs, skipped = inspect_attempts(names, "transform" if label == "ReceivingOnly" else "noa")
        assert set(runs) == set(seeds)
        incomplete.extend(skipped)
        for seed in seeds:
            tasks.append((runs[seed], label, profile, seed, end))
    with Pool(min(4, len(tasks))) as pool:
        rows = pool.starmap(measure, tasks)
    pairs = []
    for seed in seeds:
        matched = [r for r in rows if r["seed"] == seed]
        assert len({r["common_input_sha256"] for r in matched}) == 1
        candidate, = (r for r in matched if r["label"] == "ReceivingOnly")
        for baseline in matched:
            if baseline is not candidate:
                pairs.append(dict(seed=seed, baseline=baseline["label"],
                                  **{k: candidate[k] - baseline[k] for k in METRICS}))
    means = {label: {k: mean(p[k] for p in pairs if p["baseline"] == label) for k in METRICS}
             for label in BATCHES[profile] if label != "ReceivingOnly"}
    report = dict(profile=profile, physical=PROFILES[profile], window_s=[100, end], region_m=[800, 1000],
                  low_speed_mps=5, interrupted_attempts=incomplete, cases=rows, receiving_minus_baseline=pairs,
                  equal_seed_deltas=means)
    if profile == "tau_only":
        report["timegap_effects_same_controller"] = timegap_effects(rows)
    write_json(HERE / "stage/shared_physics" / f"spacing_2000_{profile}.json", report)


if __name__ == "__main__":
    main()
