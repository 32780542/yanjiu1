"""Audit the simplified centralized reference against paired local observations."""

import argparse
import csv
import gzip
import json
from pathlib import Path
from statistics import mean

from summarize_shared_physics import (
    HISTORICAL, ROOT, digest, evaluate_case, extract_case, read_json, read_report_rows, stop_and_merge,
)


FLOWS = (1500, 1750, 2000)
SEEDS = (211, 212)
DEFAULT_REPORT = HISTORICAL / "data/formal600_main/per_case.csv"
MODES = ("noa", "transform", "global")
TIMES = (200, 400, 550)
CASE_KEYS = (
    "seed", "flow_veh_h_lane", "demand_duration_s", "scenario", "max_time_s", "step_s",
    "lane_change_duration_s", "gui", "diagnostic",
)
INPUT_KEYS = ("arrivals", "physical", "speed_mode", "lane_change_mode", "insertion", "positions_step_s",
              "longitudinal_coordinate", "lateral_coordinate", "source_sha256")
NETWORK_FILES = ("native.nod.xml", "native.edg.xml", "native.con.xml", "native.rou.xml")
ENDPOINTS = ("status", "safe", "all_completed", "requested", "departed", "completed", "pending_final",
             "onroad_final", "actual_end_s", "collisions", "teleports", "error")
METRICS = ("mean_system_time_s", "mean_travel_time_s", "mean_entry_wait_s", "mean_segment_800_1100_s",
           "flow_1000m_veh_h", "exit_flow_veh_h", "region_mean_speed_mps", "region_low_speed_vehicle_s",
           "stop_sample_vehicle_s", "fuel_g_per_km", "merge_2to1_mean_x_m")


def sample_speed(run):
    """Window centered at each paper time and x=1000 m, with equal vehicle-step weight."""
    counts = dict.fromkeys(TIMES, 0)
    totals = dict.fromkeys(TIMES, 0.0)
    positions = run / "positions.jsonl.gz"
    if not positions.is_file():
        return {time: dict(raw_positions_available=False, vehicle_steps=None, mean_speed_mps=None)
                for time in TIMES}
    with gzip.open(positions, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            now = frame["time_s"]
            if now >= TIMES[-1] + 5:
                break
            for time in TIMES:
                if time - 5 <= now < time + 5:
                    speeds = [s[2] for s in frame["states"].values() if 975 <= s[0] < 1025]
                    counts[time] += len(speeds)
                    totals[time] += sum(speeds)
    return {time: dict(raw_positions_available=True, vehicle_steps=counts[time],
                       mean_speed_mps=totals[time] / counts[time]
                       if counts[time] else None) for time in TIMES}


def same_input(run, source, result, historical, old_source, old_result):
    return (all(old_source[key] == source[key] for key in INPUT_KEYS)
            and all(old_source["case"][key] == source["case"][key] for key in CASE_KEYS)
            and old_result["sumo_version"] == result["sumo_version"]
            and all(digest(historical / file) == digest(run / file) for file in NETWORK_FILES))


def summarize(batch, out, history_path=DEFAULT_REPORT, candidate="C12_200", seeds=SEEDS):
    history = {(row["flow"], row["seed"], row["mode"]): row for row in read_report_rows(history_path)
               if row["candidate"] == candidate and row["scenario"] == "lane_drop"}
    frozen = read_json(batch / "src/freeze.json")["sha256"]
    assert all(digest(batch / "src" / path) == sha for path, sha in frozen.items())
    rows = []
    snapshots = []
    pairs = []
    for flow in FLOWS:
        for seed in seeds:
            case = batch / "cases" / f"{flow}_{seed}"
            worker_exit = int((case / "worker_exit.txt").read_text(encoding="utf-8").strip())
            result_files = list(case.glob("*/result.json"))
            if len(result_files) != 1:
                raise ValueError(f"Expected one result for {flow}, seed {seed}. Found {len(result_files)}.")
            run = result_files[0].parent
            source = read_json(run / "input.json")
            result = read_json(run / "result.json")
            captured = source["source_sha256"]
            assert captured == result["source_sha256"] and len(captured) == 6
            assert all(digest(run / "source" / path) == frozen[path] == sha for path, sha in captured.items())
            assert source["case"]["mode"] == "global" and source["case"]["reference_is_full_paper_reproduction"] is False
            audit = evaluate_case(run)
            measured = {**result, **audit, **stop_and_merge(run)}
            mode_rows = {}
            for mode in MODES[:-1]:
                record = history[flow, seed, mode]
                old_run = Path(record["run_dir"])
                old_source, old_result, old_metrics = extract_case(old_run, record)
                matched = same_input(run, source, result, old_run, old_source, old_result)
                mode_rows[mode] = case_row(flow, seed, mode, old_run, old_result, old_metrics,
                                           matched, record["attribution_eligible"], [])
            matched = all(row["matched"] for row in mode_rows.values())
            issues = list(audit["audit_issues"])
            if worker_exit:
                issues.append(f"worker_exit_{worker_exit}")
            mode_rows["global"] = case_row(flow, seed, "global", run, result, measured, matched,
                                           audit["attribution_eligible"] and worker_exit == 0, issues)
            for mode in MODES[:-1]:
                local, reference = mode_rows[mode], mode_rows["global"]
                eligible = local["eligible"] and reference["eligible"]
                pair = dict(flow=flow, seed=seed, local_mode=mode, eligible=eligible)
                for key in METRICS:
                    a, b = local[key], reference[key]
                    pair[f"local_minus_global_{key}"] = a - b if eligible and a is not None and b is not None else None
                pairs.append(pair)
            for mode, row in mode_rows.items():
                rows.append(row)
                if flow == 1500:
                    for time, stats in sample_speed(ROOT / row["run"]).items():
                        snapshots.append(dict(flow=flow, seed=seed, mode=mode, time_s=time, **stats))
            print(flow, seed, result["status"], result["completed"], result["requested"], matched,
                  audit["attribution_eligible"], issues[:3], flush=True)

    means = []
    for flow in FLOWS:
        group = [row for row in rows if row["flow"] == flow]
        eligible = all(row["eligible"] for row in group)
        for mode in MODES:
            mode_rows = [row for row in group if row["mode"] == mode]
            means.append(dict(flow=flow, mode=mode, seeds=len(mode_rows), eligible=eligible, **{
                name: mean(row[name] for row in mode_rows)
                if eligible and all(row[name] is not None for row in mode_rows) else None for name in METRICS
            }))
    out.mkdir(parents=True, exist_ok=True)
    for name, table in (("cases", rows), ("means", means), ("pairs", pairs), ("speed_samples", snapshots)):
        with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows(table)
    (out / "audit.json").write_text(json.dumps(dict(
        batch=str(batch.relative_to(ROOT)), historical_report=str(history_path.relative_to(ROOT)), candidate=candidate,
        seeds=list(seeds), source_sha256=frozen, cases=rows, means=means, pairs=pairs, speed_samples=snapshots,
        reference="Simplified Cai-style centralized assignment implemented in native SUMO",
        speed_sample_window=dict(x_m=[975, 1025], t_radius_s=5, weighting="each vehicle at each recorded 0.1 s step"),
    ), allow_nan=False, indent=2) + "\n", encoding="utf-8")


def case_row(flow, seed, mode, run, result, metrics, matched, eligible, issues):
    return dict(flow=flow, seed=seed, mode=mode, run=str(run.relative_to(ROOT)), matched=matched,
                eligible=matched and eligible, audit_issues=issues, **{key: result.get(key) for key in ENDPOINTS},
                **{key: metrics.get(key, result.get(key)) for key in METRICS})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--history-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--candidate", default="C12_200")
    parser.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("--seeds must be unique")
    summarize(args.batch.resolve(), args.out.resolve(), args.history_report.resolve(), args.candidate, args.seeds)
