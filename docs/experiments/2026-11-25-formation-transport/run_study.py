"""Run fixed-cohort demos or matched traffic with a fresh, frozen native SUMO runner.

Example from the repository root:
  python docs/experiments/2026-11-25-formation-transport/run_study.py --stage demo --label trial01
  python docs/experiments/2026-11-25-formation-transport/run_study.py --stage traffic --label traffic01 --roads 3to2,4to3 --seeds 6,20 --flows 1500,1750,2000 --duration 600 --workers 4 --publish

One row per attempt. A drained, safe cohort passes the geometry check only if
all requested IDs form the same group on both roads over positive hold times.
For traffic, geometric participation is a measurement; no cutoff is imposed.
For failed simulations the batch retains partial output, logs and an error row.
In fixed-cohort rows "actual" counts the observed SUMO lane-index crossings.
Completion events reach the lane center later and are reported separately.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_VARIANT = ROOT / "variants/phase5g_pure_formation"
ROADS = {"3to2": ("lane_drop", "formation_demo"), "4to3": ("four_to_three", "four_to_three_demo"),
         "2to3": ("two_to_three", "two_to_three_demo"), "3to4": ("three_to_four", "three_to_four_demo")}
REQUIRED = ("run_native_flow.py", "configs/tools.json", "experiments/__init__.py",
            "experiments/native_sumo.py", "experiments/global_reference.py", "experiments/complete_layers.py",
            "research/__init__.py", "research/common.py", "noa/__init__.py", "noa/native_rules.py")
OPTIONAL = ("noa/transport.py", "noa/staggered.py")
COHORTS = ("stream", "uneven9", "uneven13", "skew12", "balanced12", "split12", "chain24")


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def cohort_tape(cohort, lanes, entry):
    """Fixtures use only physical departures. No controller-specific fields are supplied."""
    if cohort == "balanced12":
        return [dict(lane=i % lanes, x=180-30*(i//lanes)-15*((i%lanes)%2), speed=28.8)
                for i in range(12)]
    if cohort == "chain24":
        # Consecutive neighbours are within range, but the 506 m envelope exceeds any view.
        return [dict(lane=entry[i % len(entry)], x=20+22*(23-i), speed=28.8) for i in range(24)]
    size = {"uneven9": 9, "uneven13": 13}.get(cohort, 12)
    rows = []
    for i in range(size):
        lane = lanes-1 if cohort == "skew12" else entry[i % len(entry)]
        delay = 10. if cohort == "split12" and i >= 6 else 0.
        rows.append(dict(lane=lane, depart=round(i*.7+delay, 1), x=0, speed=28.8))
    return rows


def freeze(batch, variant, args):
    source = batch / "source"
    source.mkdir(parents=True, exist_ok=False)
    files = [*REQUIRED, *(name for name in OPTIONAL if (variant / name).is_file())]
    for name in files:
        target = source / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(variant / name, target)
    (source / "tmp").mkdir()
    # The evaluator is run in a fresh process beside the frozen complete_layers module.
    shutil.copyfile(HERE / "measure.py", source / "measure.py")
    shutil.copyfile(Path(__file__), batch / "run_study.py")
    source_hashes = {name: hash_file(source/name) for name in files}
    if any(hash_file(variant/name) != value for name, value in source_hashes.items()):
        raise RuntimeError("Variant changed during freeze; use a fresh batch label")
    manifest = dict(arguments=vars(args), variant_directory=str(variant), files=source_hashes,
                    measure_sha256=hash_file(source/"measure.py"), driver_sha256=hash_file(batch/"run_study.py"))
    if args.stage == "demo":
        # Use the same twelve departures as the GUI and seal the arrays independently of the runner.
        sys.path.insert(0, str(ROOT))
        from runrun import DEMO_ENTRY_LANES
        manifest["initial_sha256"] = {}
        for road, cohort in itertools.product(args.roads, args.cohorts):
            lanes = int(road[0])
            initial = (json.loads(Path(args.initial).read_text(encoding="utf-8-sig")) if args.initial
                       else cohort_tape(cohort, lanes, DEMO_ENTRY_LANES[lanes]))
            filename = f"{road}_{cohort}.json"
            write_json(batch / filename, initial)
            manifest["initial_sha256"][filename] = hash_file(batch/filename)
    write_json(batch / "manifest.json", manifest)
    return source, source_hashes


def audit_row(folder, report, stage):
    result = json.loads((folder/"result.json").read_bytes())
    base_keys = ("status", "requested", "departed", "completed", "collisions", "teleports", "safe",
                 "performance_comparison_eligible", "mean_travel_time_s", "mean_system_time_s", "mean_entry_wait_s",
                 "lane_changes", "lane_change_completions", "fuel_g_per_km", "arrivals_sha256")
    row = {k: report[k] for k in base_keys}
    for key in ("exit_flow_veh_h", "clearance_after_demand_s", "pending_final", "onroad_final"):
        row[key] = result[key]
    if stage == "traffic":
        stop = result["demand_duration_s"]
        trips = json.loads((folder/"trips.json").read_bytes())
        entered = sum(r["entered_s"] is not None and r["entered_s"] <= stop for r in trips)
        exited = sum(r["exited_s"] is not None and r["exited_s"] <= stop for r in trips)
        due = sum(r["requested_s"] <= stop for r in trips)
        row.update(entered_at_demand_end=entered, exited_at_demand_end=exited,
                   pending_at_demand_end=due-entered, onroad_at_demand_end=entered-exited)
    row["safe_drained"] = bool(row["safe"] and row["status"] == "drained" and row["completed"] == row["requested"])
    local = result["formation_state"] or {}
    for key in ("participation_rate", "peak_participants", "mean_episode_s"):
        row["local_"+key] = local.get(key)
    for reason, counts in (report.get("transport_certificates") or {}).items():
        for key, value in counts.items():
            row[reason+"_"+key] = value
    row["crossing_counts"] = "/".join(map(str, report["downstream_first_observation_counts"]))
    for region in ("upstream", "downstream"):
        stats = report[region+"_sampled_geometry"]
        for key in ("vehicle_samples", "formed_vehicle_samples", "formed_pct", "peak_multilayer_size"):
            row[region+"_"+key] = stats[key]
    if stage == "demo":
        for region in ("upstream", "downstream"):
            for k in ("peak_size", "whole_hold_s", "whole_total_s", "all_present_total_s", "formed_pct_while_all_present"):
                row[region+"_"+k] = report[region][k]
            row[region+"_whole_episode_count"] = len(report[region]["whole_episodes"])
            counts = (report[region]["peak"] or {}).get("counts", [])
            row[region+"_peak_counts"] = "/".join(map(str, counts))
        row["same_ids_peak"] = report["paired_peak"]["size"]
        row["cohort_formed_both"] = (row["same_ids_peak"] == row["requested"] and
                                     min(row["upstream_whole_hold_s"], row["downstream_whole_hold_s"]) > 0)
        for prefix in ("formation", "transform"):
            movement = report[prefix+"_moves"]
            actual = movement["midpoint"] if movement else {}
            completed = movement["completed"] if movement else {}
            for key in ("min_total_crossings", "min_max_crossings"):
                row[prefix+"_"+key] = movement[key] if movement else None
                for tail in ("free_balanced_tail", "three_lane_outer_first"):
                    row[prefix+"_"+tail+"_"+key] = movement[tail][key] if movement else None
            for key in ("total", "max_per_car", "vehicles_multiple"):
                row[prefix+"_actual_"+key] = actual.get(key)
            row[prefix+"_completed_total"] = completed.get("total")
            row[prefix+"_completed_max_per_car"] = completed.get("max_per_car")
            row[prefix+"_completion_chain_verified"] = not completed["mismatch_ids"] if movement else None
            row[prefix+"_event_chain_verified"] = not actual["mismatch_ids"] if movement else None
            row[prefix+"_at_both_bounds"] = (row[prefix+"_event_chain_verified"] and
                actual["total"] == movement["min_total_crossings"] and
                actual["max_per_car"] == movement["min_max_crossings"]) if movement else None
            settled = report["settled_"+prefix+"_moves"]
            row[prefix+"_settled_start_latest_s"] = settled["start_time_range_s"][1] if settled else None
            row[prefix+"_settled_end_s"] = settled["end_time_range_s"][1] if settled else None
            row[prefix+"_settled_completed"] = settled["completed"]["total"] if settled else None
            row[prefix+"_settled_chain_verified"] = not settled["completed"]["mismatch_ids"] if settled else None
        late = report["after_last_downstream_shape_events"]
        row["after_last_shape_actual_total"] = late["midpoint"]["total"] if late else None
        row["after_last_shape_completed_total"] = late["completed"]["total"] if late else None
    return row


def one_case(batch, source, manifest, stage, spec, mode="transform"):
    road, seed, flow, duration, cohort = spec
    key = f"{road}_s{seed}_q{flow:g}"
    if cohort and cohort != "stream":
        key += "_"+cohort
    home = batch / key
    home.mkdir()
    scenario = ROADS[road][int(stage == "demo")]
    if cohort:
        tape = batch/f"{road}_{cohort}.json"
        duration = max(duration, round(max(r.get("depart", 0.) for r in json.loads(tape.read_bytes()))+.1, 1))
    row = dict(road=road, mode=mode, cohort=cohort, seed=seed, flow=flow, duration_s=duration, scenario=scenario,
               case_dir=relative(home))
    cmd = [sys.executable, "-E", "-B", str(source/"run_native_flow.py"), "--mode", mode,
           "--scenario", scenario, "--seed", str(seed), "--flow", str(flow), "--duration", str(duration),
           "--output-base", str(home)]
    if stage == "demo":
        cmd.extend(["--initial", str(tape)])
    write_json(home / "command.json", cmd)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    try:
        with (home/"runner.log").open("wb") as log:
            rc = subprocess.run(cmd, cwd=source, stdout=log, stderr=subprocess.STDOUT, env=env).returncode
        matches = list(home.glob("*/result.json"))
        if len(matches) != 1:
            raise RuntimeError(f"Runner exit {rc}, found {len(matches)} native results")
        folder = matches[0].parent
        row["run_dir"] = relative(folder)
        result = json.loads(matches[0].read_bytes())
        for k in ("status", "error", "requested", "departed", "completed", "collisions", "teleports", "safe"):
            row[k] = result.get(k)
        input_data = json.loads((folder/"input.json").read_bytes())
        if result["mode"] != mode or input_data["case"]["mode"] != mode:
            raise ValueError("Frozen runner reported a different control mode")
        hashes = result["source_sha256"]
        if not hashes or hashes != input_data["source_sha256"] or any(
                manifest.get(k) != v or hash_file(folder/"source"/k) != v for k, v in hashes.items()):
            raise ValueError("Run source hashes disagree with the frozen batch")
        row["controller_sha256"] = hashes["noa/native_rules.py"]
        row["input_sha256"] = hash_file(folder/"input.json")
        row["result_sha256"] = hash_file(matches[0])
        if rc:
            raise RuntimeError(f"Native runner exited {rc}: {row['error']}")
        audit_cmd = [sys.executable, "-E", "-B", str(source/"measure.py"), str(folder)]
        if stage == "demo":
            audit_cmd.append("--cohort")
        with (home/"measure.json").open("wb") as output, (home/"measure.log").open("wb") as errors:
            subprocess.run(audit_cmd, cwd=source, stdout=output, stderr=errors, env=env, check=True)
        row.update(audit_row(folder, json.loads((home/"measure.json").read_bytes()), stage))
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        row["error"] = str(error)
    write_json(home / "row.json", row)
    return row


def values(text, convert):
    return list(dict.fromkeys(convert(x.strip()) for x in text.split(",")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("demo", "traffic"), required=True)
    parser.add_argument("--mode", choices=("transform", "noa"), default="transform")
    parser.add_argument("--label", required=True, help="New directory name under tmp/nov25study")
    parser.add_argument("--roads", default="3to2,4to3,2to3,3to4")
    parser.add_argument("--seeds", help="Comma-separated; default 20 (demo) or 6,20 (traffic)")
    parser.add_argument("--flows", help="Comma-separated; default 1750 (demo) or 1500,1750,2000 (traffic)")
    parser.add_argument("--duration", type=float, help="Demand seconds; default 8 for demo and 600 for traffic")
    parser.add_argument("--variant", default=str(DEFAULT_VARIANT), help="Native variant directory")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--cohorts", help="Fixed layouts: "+", ".join(COHORTS)+"; default stream")
    parser.add_argument("--initial", help="Custom fixed JSON array of native physical departures (one road)")
    parser.add_argument("--publish", action="store_true", help="Copy the compact CSV into the study folder")
    args = parser.parse_args()
    if not re.fullmatch("[A-Za-z0-9][A-Za-z0-9_-]*", args.label):
        parser.error("Label must use letters, digits, - or _")
    args.roads = values(args.roads, str)
    if args.stage != "demo" and (args.cohorts or args.initial):
        parser.error("--cohorts and --initial require --stage demo")
    if args.initial and (args.cohorts or len(args.roads) != 1):
        parser.error("--initial needs one road and supplies its own cohort")
    args.cohorts = ["custom"] if args.initial else values(args.cohorts or "stream", str)
    if not args.initial and set(args.cohorts)-set(COHORTS):
        parser.error("Unknown cohort")
    args.seeds = values(args.seeds or ("20" if args.stage == "demo" else "6,20"), int)
    args.flows = values(args.flows or ("1750" if args.stage == "demo" else "1500,1750,2000"), float)
    if args.duration is None:
        args.duration = 8. if args.stage == "demo" else 600.
    if set(args.roads)-ROADS.keys() or args.workers < 1:
        parser.error("Unknown road or non-positive worker count")
    if args.stage == "demo" and len(args.flows) > 1:
        parser.error("The fixed 12 arrivals override random demand; select a single nominal flow")
    variant = Path(args.variant).resolve()
    batch = ROOT / "tmp/nov25study" / args.label
    batch.mkdir(parents=True, exist_ok=False)
    source, manifest = freeze(batch, variant, args)
    jobs = list(itertools.product(args.roads, args.seeds, args.flows, [args.duration],
                                  args.cohorts if args.stage == "demo" else [None]))
    rows = {}
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(one_case, batch, source, manifest, args.stage, spec, args.mode): spec for spec in jobs}
        for future in as_completed(futures):
            spec = futures[future]
            row = rows[spec] = future.result()
            print(spec, row.get("status"), row.get("completed"), row.get("error") or "", flush=True)
    ordered = [rows[spec] for spec in jobs]
    names = list(dict.fromkeys(key for row in ordered for key in row))
    path = batch / "summary.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, names)
        writer.writeheader()
        writer.writerows(ordered)
    if args.publish:
        target = HERE / (args.label+".csv")
        with target.open("xb") as dest, path.open("rb") as src:
            shutil.copyfileobj(src, dest)
    print(relative(path), flush=True)
    return int(any(row.get("error") for row in ordered))


if __name__ == "__main__":
    raise SystemExit(main())
