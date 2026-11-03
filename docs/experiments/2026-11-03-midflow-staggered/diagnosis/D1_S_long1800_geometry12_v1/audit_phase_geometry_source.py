"""Measured local interleaving geometry at fixed one-second snapshots.

Not a count of platoons, not a proof of fixed-initial-state recovery, and no use
of reported formation flags. Desired physical phases are the shared 0/15/0 law.
"""
import argparse
from bisect import bisect_right
from collections import defaultdict
import gzip
import importlib.util
import json
from pathlib import Path
import sys
from audit_raw_midflow import read, sha, write_csv, quantile, HEADWAY, LANE_WIDTH, WIDTH


def region(x):
    return "0_100" if x < 100 else "100_600" if x < 600 else "600_640" if x < 640 else "640_800" if x < 800 else "800_1000" if x < 1000 else "1000_1100" if x < 1100 else "1100_exit"


def analyze(folder, output, window):
    record = read(folder / "case_record.json")
    assert record.get("seal_status") == "verified" and record["candidate"] in ("S", "D", "DR", "DP")
    run = Path(record["run_dir"])
    trips, result, seal = read(run / "trips.json"), read(run / "result.json"), read(folder / "evidence/seal.json")
    raw, source = run / "positions.jsonl.gz", run / "source/noa/native_rules.py"
    assert sha(raw) == seal["originals"][raw.name]["sha256"] and sha(source) == result["source_sha256"]["noa/native_rules.py"]
    spec = importlib.util.spec_from_file_location("frozen_phase_geometry", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.GAP == 30
    ids = {t["vehicle_id"]: i + 1 for i, t in enumerate(trips)}
    lanes = {t["vehicle_id"]: t["lane"] for t in trips}
    changes = defaultdict(list)
    for trip in trips:
        for e in trip["lane_events"]:
            changes[round(e["time_s"] * 10)].append((trip["vehicle_id"], e["to_lane"]))
    pairs, gaps, cth, nvehicles = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(int)
    previous, old_time, snapshots = {}, None, 0
    for line in gzip.open(raw, "rt", encoding="utf-8"):
        frame = json.loads(line)
        now, states = frame["time_s"], frame["states"]
        tick = round(now * 10)
        for key, lane in changes[tick]:
            lanes[key] = lane
        if tick % 10 == 0 and window[0] <= now < window[1]:
            snapshots += 1
            cars = [module.Vehicle(ids[k], s[0], s[1], s[2], lanes[k],
                    (s[1] - previous[k][1]) / (now - old_time) if k in previous else 0.0, s[3], now) for k, s in states.items()]
            phase = {c.track: module._physical_phase(c, 3) for c in cars}
            def nearest(car, lane):
                return min((c for c in cars if c.lane == lane and abs(c.x - car.x) <= 50),
                    key=lambda c: (abs(c.x - car.x + phase[c.track] - phase[car.track]), abs(c.x - car.x),
                                   c.x - car.x + phase[c.track] - phase[car.track], c.x, c.y, c.speed, c.vy), default=None)
            seen = set()
            ordered = sorted(cars, key=lambda c: (c.x, c.y))
            corridors = [[c for c in ordered if abs(c.y - (lane + .5) * LANE_WIDTH) < LANE_WIDTH / 2 + WIDTH / 2] for lane in range(3)]
            xs = [[c.x for c in cs] for cs in corridors]
            for car in cars:
                r = region(car.x)
                nvehicles[r, car.lane] += 1
                front = next((c for c in corridors[car.lane][bisect_right(xs[car.lane], car.x):] if c.x - car.x <= 200), None)
                if front:
                    distance = front.x - car.x
                    gaps[r, car.lane].append(distance)
                    if distance <= 50:
                        cth[r, car.lane].append(distance - 5.5 - HEADWAY * car.speed)
                for lane in (car.lane - 1, car.lane + 1):
                    if not 0 <= lane < 3:
                        continue
                    peer = nearest(car, lane)
                    if peer is None or nearest(peer, car.lane) is not car:
                        continue
                    key = tuple(sorted((car.track, peer.track)))
                    if key in seen:
                        continue
                    seen.add(key)
                    low, high = sorted((car, peer), key=lambda c: c.lane)
                    dx = high.x - low.x
                    error = dx + phase[high.track] - phase[low.track]
                    pairs[region((low.x + high.x) / 2), f"{low.lane}_{high.lane}"].append((dx, error))
        previous, old_time = states, now
    ident = {k: record[k] for k in ("candidate", "flow", "seed", "scenario", "mode")}
    pair_rows = []
    for (r, lane_pair), values in sorted(pairs.items()):
        errors = [abs(e) for dx, e in values]
        raw_dx = [dx for dx, e in values]
        pair_rows.append(dict(**ident, region=r, lanes=lane_pair, sampled_mutual_pairs_n=len(values),
                              abs_phase_error_p50_m=quantile(errors, .5), abs_phase_error_p95_m=quantile(errors, .95),
                              fraction_error_le2m=sum(e <= 2 for e in errors) / len(errors),
                              actual_signed_dx_p05_m=quantile(raw_dx, .05), actual_signed_dx_p50_m=quantile(raw_dx, .5),
                              actual_signed_dx_p95_m=quantile(raw_dx, .95)))
    gap_rows = []
    for (r, lane), count in sorted(nvehicles.items()):
        g, e = gaps[r, lane], cth[r, lane]
        gap_rows.append(dict(**ident, region=r, lane=lane, sampled_car_n=count, visible_front200_n=len(g),
                            controlled_front50_n=len(e), actual_gap200_p50_m=quantile(g, .5), actual_gap200_p95_m=quantile(g, .95),
                            cth_residual_front50_p50_m=quantile(e, .5), cth_residual_front50_p95_m=quantile(e, .95)))
    write_csv(output / (folder.name + "_phase_pairs.csv"), pair_rows)
    write_csv(output / (folder.name + "_headway.csv"), gap_rows)
    info = dict(**ident, source_sha256=sha(source), positions_sha256=seal["originals"][raw.name]["sha256"], window_s=window,
                sampled_snapshots=snapshots, sample_period_s=1.0, sampled_mutual_pairs=sum(len(v) for v in pairs.values()),
                limitations=["No reported flags, modulo distances, inferred global slots or common platoon size.",
                             "Only actual adjacent-lane mutual nearest pairs within50m; their geometry is not all-road formation success or 24/45 perturbation recovery.",
                             "Pair region uses midpoint x. Headway region uses ego x; CTH residual limited to actual physical fronts within50m, with visible200m gaps and coverage separately retained."])
    (output / (folder.name + "_provenance.json")).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(**ident, pairs=info["sampled_mutual_pairs"], output=str(output))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, action="append")
    parser.add_argument("--case", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-start", type=float, default=30)
    parser.add_argument("--window-end", type=float, default=180)
    args = parser.parse_args()
    folders = list(args.case)
    for batch in args.batch or []:
        folders.extend(Path(r["case_output"]) for r in read(batch / "manifest.json"))
    assert folders
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "audit_phase_geometry_source.py").write_bytes(Path(__file__).read_bytes())
    for folder in folders:
        analyze(folder, args.output, (args.window_start, args.window_end))
