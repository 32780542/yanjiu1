"""Measure downstream two-layer geometry and persistence from the full native trace.

A link is the ordered IDs of two adjacent full rows. Its age resets when any
member, ordering or geometric test changes. A vehicle may belong to two links;
it gets at most one exposure credit per threshold and instant. Error RMS uses
two-layer-link seconds after one second of continuous qualification.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

from measure import road_layout, groups_at, lane_of


def pair_errors(pair, states):
    front, rear = pair
    gap = [states[i][0]-states[j][0]-30. for i, j in zip(front, rear)]
    phase = [states[row[i]][0]-states[row[j]][0]-15.*(j%2-i%2) for row in pair
             for i in range(len(row)) for j in range(i+1, len(row))]
    speeds = [states[k][2] for row in pair for k in row]
    mean = sum(speeds)/len(speeds)
    return (sum(x*x for x in gap)/len(gap), sum(x*x for x in phase)/len(phase),
            sum((x-mean)**2 for x in speeds)/len(speeds))


def links(states, lanes):
    views = [states] if lanes % 2 or lanes == 2 else []
    if lanes % 2 == 0:
        views.append({k: (s[0], 3.3*lanes-s[1], *s[2:]) for k, s in states.items()})
    return {pair for view in views for group in groups_at(view, lanes)
            for pair in zip(group["layers"], group["layers"][1:])}


def measure_persistence(folder, *, first_seen=None):
    folder = Path(folder)
    (_, boundary), (lanes, length) = road_layout(folder)
    inputs = json.loads((folder/"input.json").read_bytes())
    result = json.loads((folder/"result.json").read_bytes())
    holds = (0, 1, 3, 5)
    exposure = dict.fromkeys(holds, 0.)
    prior = None
    since = {}
    link_seconds, total = 0., 0.
    square_errors = [0., 0., 0.]
    with gzip.open(folder/"positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            t = frame["time_s"]
            if first_seen is not None:
                for k, state in frame["states"].items():
                    if k not in first_seen:
                        first_seen[k] = (lane_of(state[1]), round(state[0], 6), round(state[2], 6))
            if prior is not None:
                start, old = prior
                if abs(t-start-inputs["positions_step_s"]) > 1e-6:
                    raise ValueError("Discontinuous samples")
                total += len(old)*(t-start)
                first = {}
                for pair, onset in since.items():
                    for row in pair:
                        for k in row:
                            first[k] = min(first.get(k, onset), onset)
                    duration = max(0., t-max(start, onset+1.))
                    if duration > 0:
                        link_seconds += duration
                        for i, mse in enumerate(pair_errors(pair, old)):
                            square_errors[i] += mse*duration
                for h in holds:
                    exposure[h] += sum(max(0., t-max(start, onset+h)) for onset in first.values())
            states = {k: s for k, s in frame["states"].items() if boundary <= s[0] < boundary+length}
            since = {pair: since.get(pair, t) for pair in links(states, lanes)}
            prior = (t, states)
    out = dict(mode=result["mode"], scenario=result["scenario"], seed=result["seed"],
        flow=result["flow_veh_h_lane"], duration_s=result["demand_duration_s"],
        arrivals_sha256=hashlib.sha256(json.dumps(inputs["arrivals"], sort_keys=True).encode()).hexdigest(),
        status=result["status"], completed=result["completed"], requested=result["requested"],
        collisions=result["collisions"], teleports=result["teleports"], downstream_vehicle_s=total,
        downstream_length_m=length, lanes=lanes, links_confirmed_1s_seconds=link_seconds)
    root = Path(__file__).resolve().parents[3]
    out["run_dir"] = folder.resolve().relative_to(root).as_posix() if folder.resolve().is_relative_to(root) else str(folder)
    for name, summed in zip(("same_lane_spacing_rms_m", "cross_lane_phase_rms_m", "speed_rms_mps"), square_errors):
        out[name] = math.sqrt(summed/link_seconds) if link_seconds else None
    for h in holds:
        out[f"held_{h}s_vehicle_s"] = exposure[h]
        out[f"held_{h}s_pct"] = 100*exposure[h]/total if total else None
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--csv", type=Path, help="New compact per-run CSV")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.workers > 1:
        with ProcessPoolExecutor(args.workers) as pool:
            rows = list(pool.map(measure_persistence, args.folders))
    else:
        rows = [measure_persistence(folder) for folder in args.folders]
    if args.csv:
        with args.csv.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, rows[0])
            writer.writeheader()
            writer.writerows(rows)
        print(args.csv, len(rows))
    else:
        print(json.dumps(rows[0] if len(rows) == 1 else rows, indent=2))
