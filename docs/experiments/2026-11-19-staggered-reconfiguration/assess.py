"""Measure physical two-lane alternation in a native SUMO trace (either lane may lead)."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

VARIANT = Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"
sys.path.insert(0, str(VARIANT))
from experiments.complete_layers import groups_at
from experiments.native_sumo import ROAD_LAYOUT


def alternating_windows(states):
    """Return all consecutive four-car windows and the largest valid chain."""
    ordered = sorted(states, key=lambda key: -states[key][0])
    windows, peak = set(), 0
    for i, head in enumerate(ordered):
        lo = hi = states[head][2]
        for j in range(i, len(ordered)):
            x, y, speed = states[ordered[j]][:3]
            lane = round(y / 3.3 - .5)
            if lane not in (0, 1) or abs(y - (lane + .5) * 3.3) > .3:
                break
            lo, hi = min(lo, speed), max(hi, speed)
            if hi - lo > .5:
                break
            if j > i:
                front = states[ordered[j - 1]]
                half = (5.5 + .85 * (front[2] + speed) / 2) / 2
                if round(front[1] / 3.3 - .5) == lane or abs(front[0] - x - half) > 2.:
                    break
            if j > i + 1:
                same = states[ordered[j - 2]]
                gap = 5.5 + .85 * (same[2] + speed) / 2
                if abs(same[0] - x - gap) > 2.:
                    break
            size = j - i + 1
            if size == 4:
                windows.add(tuple(ordered[i:j + 1]))
            if size >= 2:
                peak = max(peak, size)
    return windows, peak


def measure(folder, cohort=False):
    inputs = json.loads((folder / "input.json").read_bytes())
    case = inputs["case"]
    result = json.loads((folder / "result.json").read_bytes())
    boundary, length, retained = ROAD_LAYOUT[case["scenario"]]
    if retained != 2:
        raise ValueError("Requires a three-to-two lane drop")
    n = result["requested"]
    crossings, since = {}, {}
    best = {"three": (0., None), "two": (0., None)}
    start = dict.fromkeys(best)
    prior, eligible, total, imbalance = None, 0., 0., 0.
    peak = up_samples = up_formed = 0
    with gzip.open(folder / "positions.jsonl.gz", "rt") as frames:
        for line in frames:
            frame = json.loads(line)
            t, states = frame["time_s"], frame["states"]
            down = {k: v for k, v in states.items() if boundary <= v[0] < boundary + length}
            counts = [0, 0]
            for key, car in down.items():
                lane = round(car[1] / 3.3 - .5)
                if lane in (0, 1):
                    counts[lane] += 1
                crossings.setdefault(key, lane)
            windows, size = alternating_windows(down)
            peak = max(peak, size)
            # Left-hold the previous sample; credit a vehicle once after any of
            # its unchanged four-car windows has accumulated one full second.
            if prior is not None:
                old_t, old_count, old_diff = prior
                total += (t - old_t) * old_count
                imbalance += (t - old_t) * old_diff
                first = {}
                for group, onset in since.items():
                    for key in group:
                        first[key] = min(first.get(key, t), onset + 1.)
                eligible += sum(max(0., t - max(old_t, confirm)) for confirm in first.values())
            since = {group: since.get(group, t) for group in windows}
            prior = t, len(down), abs(counts[0] - counts[1])
            if cohort or abs(t - round(t)) < 1e-8:
                up = {k: v for k, v in states.items() if 0 <= v[0] < boundary - 200.}
                if abs(t - round(t)) < 1e-8:
                    up_samples += len(up)
                    up_formed += sum(g["size"] for g in groups_at(up, 3, gap=29.98) if g["layer_count"] >= 2)
            if cohort:
                three = (len(up) == n and n % 3 == 0 and
                         any(g["size"] == n for g in groups_at(up, 3, gap=29.98)))
                for region, valid in (("three", three), ("two", size == n and len(down) == n)):
                    if valid:
                        if start[region] is None:
                            start[region] = t
                        duration = t - start[region]
                        if duration > best[region][0]:
                            best[region] = duration, start[region]
                    else:
                        start[region] = None
    arrivals = json.dumps(inputs["arrivals"], sort_keys=True).encode()
    travel = result["mean_travel_time_s"]
    row = dict(status=result["status"], requested=n, completed=result["completed"], collisions=result["collisions"],
               teleports=result["teleports"], travel_s=round(travel, 3) if travel is not None else None,
               crossing0=list(crossings.values()).count(0), crossing1=list(crossings.values()).count(1),
               peak_down=peak, downstream_vehicle_s=round(total, 2),
               stable_vehicle_s=round(eligible, 2),
               stable_pct=round(100 * eligible / total, 3) if total else None,
               imbalance_pct=round(100 * imbalance / total, 3) if total else None,
               upstream_samples=up_samples, upstream_formed=up_formed,
               upstream_6plus_pct=round(100 * up_formed / up_samples, 3) if up_samples else None,
               arrivals_sha256=hashlib.sha256(arrivals).hexdigest())
    if cohort:
        for region, (duration, onset) in best.items():
            row[region + "_longest_s"] = round(duration, 2) if region != "three" or n % 3 == 0 else None
            row[region + "_start_s"] = onset
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--cohort", action="store_true", help="also measure the complete input cohort")
    args = parser.parse_args()
    print(json.dumps(measure(args.run, args.cohort), indent=2))
