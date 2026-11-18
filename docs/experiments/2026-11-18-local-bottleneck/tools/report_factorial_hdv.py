"""按同一份发车清单配对四个编队组。从原始轨迹量接收道减速，从 SUMO 行程表复算 HDV 用时。"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import hashlib
import json
from math import isclose
from pathlib import Path
from statistics import mean
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
FLOWS = (1500, 1750, 2000)
SEEDS = range(311, 316)


def read(path):
    return json.loads(path.read_bytes())


def write_table(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def trajectory_measures(path):
    receiver_samples = braking = low_speed_samples = 0
    upstream = paired = phase_sum = 0
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for line in file:
            frame = json.loads(line)
            if frame["time_s"] >= 600:
                break
            if frame["time_s"] < 100:
                continue
            middle, ending = [], []
            for x, y, speed, accel in frame["states"].values():
                if 800 <= x < 1000:
                    low_speed_samples += speed < 5
                    if 3.3 <= y < 6.6:
                        receiver_samples += 1
                        braking += max(0, -accel)
                if 150 <= x < 650 and abs(y - 4.95) <= .15:
                    middle.append((x, speed))
                if 200 <= x < 600 and abs(y - 8.25) <= .15:
                    ending.append((x, speed))
            for x, speed in ending:
                upstream += 1
                if middle:
                    gap, other_speed = min((abs(other_x - x), v) for other_x, v in middle)
                    if gap <= 50:
                        paired += 1
                        phase_sum += gap / (5.5 + .85 * (speed + other_speed) / 2)
    return dict(receiver_vehicle_s=receiver_samples * .1,
                receiver_mean_deceleration_mps2=braking / receiver_samples,
                region_low_speed_vehicle_s=low_speed_samples * .1,
                upstream_lane2_samples=upstream, samples_with_neighbor=paired,
                upstream_mean_abs_offset_over_spacing=phase_sum / paired)


def formation_case(task):
    batch, candidate, mode, flow, seed, reference, expected_source = task
    case = batch / "cases" / f"{candidate}_{flow}_{seed}_lane_drop_{mode}"
    record = read(case / "case_record.json")
    run = Path(record["run_dir"])
    data, result = read(run / "input.json"), read(run / "result.json")
    assert record["seal_status"] == "verified" and record["returncode"] == 0
    assert result["performance_comparison_eligible"] and result["completed"] == len(reference["arrivals"])
    assert data == dict(reference, case=dict(reference["case"], mode=mode), source_sha256=expected_source)
    assert result["mode"] == mode and result["seed"] == seed and result["flow_veh_h_lane"] == flow
    trips = read(run / "trips.json")
    starts = [t for t in trips if t["lane"] == 2]
    merges = [next((e["x"] for e in t["lane_completion_events"]
                    if (e["from_lane"], e["to_lane"]) == (2, 1)), None) for t in starts]
    positions = run / "positions.jsonl.gz"
    with positions.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    assert read(case / "evidence/seal.json")["originals"][positions.name]["sha256"] == sha
    metrics = trajectory_measures(positions)
    return dict(flow=flow, seed=seed, geometry=candidate, mode=mode, requested=result["requested"],
                **{k: result[k] for k in ("completed", "collisions", "teleports", "mean_entry_wait_s",
                                          "mean_system_time_s", "mean_travel_time_s", "fuel_g_per_km")},
                last_exit_s=max(t["exited_s"] for t in trips),
                started_lane2=len(starts), first_merges_recorded=sum(x is not None for x in merges),
                first_merges_before_800m=sum(x is not None and x < 800 for x in merges),
                first_merges_at_or_after_900m=sum(x is not None and x >= 900 for x in merges),
                **metrics, positions_sha256=sha)


def hdv_case(directory, arrivals, trips_writer):
    result = read(directory / "result.json")
    assert result["all_arrived"] and not result["teleports"] and not result["collision_log_lines"]
    inputs = ET.parse(directory / "hdv.rou.xml").findall("vehicle")
    assert [(v.get("id"), int(v.get("departLane")), float(v.get("depart")), float(v.get("departPos")),
             float(v.get("departSpeed")), v.get("type")) for v in inputs] == [
                 (a["vehicle_id"], a["lane"], a["requested_s"], a["x"], a["speed"], "CAV_HDV") for a in arrivals]
    route = ET.parse(directory / "trips.xml").findall("tripinfo")
    requests = {r["vehicle_id"]: r["requested_s"] for r in arrivals}
    assert len(route) == len(requests) and {t.get("id") for t in route} == requests.keys()
    times = []
    for t in route:
        key, depart, exit_s = t.get("id"), float(t.get("depart")), float(t.get("arrival"))
        times.append((depart - requests[key], exit_s - depart, exit_s - requests[key], exit_s))
        trips_writer.writerow((result["profile"], result["flow"], result["seed"], key, requests[key], depart, exit_s))
    for i, metric in enumerate(("mean_entry_wait_s", "mean_travel_time_s", "mean_system_time_s", "last_exit_s")):
        actual = [t[i] for t in times]
        assert isclose(result[metric], max(actual) if i == 3 else mean(actual), abs_tol=1e-8)
    first_depart = min(float(t.get("depart")) for t in route)
    return dict(result, sumo=result["sumo"][1], first_depart_s=first_depart,
                first_depart_to_last_exit_s=result["last_exit_s"] - first_depart,
                exited_by_600=sum(t[3] <= 600 for t in times))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=Path, default=ROOT / "tmp/staggered_bottleneck")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    batches = args.batches
    on = batches / "20261118_current60_r01"
    off = batches / "20261118_formation_only15_r01"
    aligned = batches / "20261118_factorial30_r01"
    configs = [(on, "Current", "transform"), (off, "Current", "formation"),
               (aligned, "Aligned", "transform"), (aligned, "Aligned", "formation")]
    rules = Path("noa/native_rules.py")
    frozen = subprocess.check_output(["git", "show", "f87f652:variants/phase5g_pure_formation/noa/native_rules.py"], cwd=ROOT)
    assert (on / "sources/Current" / rules).read_bytes() == (off / "sources/Current" / rules).read_bytes() == frozen
    phase = b"return desired_spacing(speed) / 2 if lane % 2 else 0."
    assert frozen.count(phase) == 1 and (aligned / "sources/Aligned" / rules).read_bytes() == frozen.replace(phase, b"return 0.")

    tasks, hdvs = [], []
    args.output.mkdir(parents=True, exist_ok=False)
    with gzip.open(args.output / "hdv_trips.csv.gz", "wt", encoding="utf-8", newline="") as archive:
        writer = csv.writer(archive)
        writer.writerow(("profile", "flow", "seed", "vehicle", "requested_s", "depart_s", "exit_s"))
        for flow in FLOWS:
            for seed in SEEDS:
                ref = read(on / "cases" / f"Current_{flow}_{seed}_lane_drop_transform" / "case_record.json")
                data = read(Path(ref["run_dir"]) / "input.json")
                for batch, candidate, mode in configs:
                    source = data["source_sha256"].copy()
                    if candidate == "Aligned":
                        source[rules.as_posix()] = hashlib.sha256(frozen.replace(phase, b"return 0.")).hexdigest()
                    tasks.append((batch, candidate, mode, flow, seed, data, source))
                for profile in ("project", "matlab"):
                    directory = batches / f"20261118_hdv-{profile}_15_r02" / f"f{flow}_s{seed}"
                    hdvs.append(hdv_case(directory, data["arrivals"], writer))
    write_table(args.output / "hdv_cases.csv", hdvs)
    with ProcessPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(formation_case, tasks))
    write_table(args.output / "formation_cases.csv", rows)
    contrasts = []
    for flow in FLOWS:
        for seed in SEEDS:
            t = {(r["geometry"], r["mode"]): r["mean_system_time_s"] for r in rows
                 if (r["flow"], r["seed"]) == (flow, seed)}
            aligned_off, aligned_on = t["Aligned", "formation"], t["Aligned", "transform"]
            stagger_off, stagger_on = t["Current", "formation"], t["Current", "transform"]
            contrasts.append(dict(flow=flow, seed=seed, transform_gain_aligned_s=aligned_off-aligned_on,
                                  transform_gain_staggered_s=stagger_off-stagger_on,
                                  stagger_gain_off_s=aligned_off-stagger_off, stagger_gain_on_s=aligned_on-stagger_on,
                                  interaction_s=(aligned_on-stagger_on)-(aligned_off-stagger_off)))
    write_table(args.output / "paired_contrasts.csv", contrasts)


if __name__ == "__main__":
    main()
