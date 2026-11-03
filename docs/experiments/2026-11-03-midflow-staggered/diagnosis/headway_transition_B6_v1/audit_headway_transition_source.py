"""Read-only 20m headway profile and same-front response around the 640m gate."""
import argparse
from bisect import bisect_right
from collections import defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean
from audit_raw_midflow import read, sha, write_csv, quantile, HEADWAY, LANE_WIDTH, WIDTH, CRUISE


def analyze(folder, output, upstream_scale, window):
    record = read(folder / "case_record.json")
    assert record.get("seal_status") == "verified"
    run = Path(record["run_dir"])
    trips, result, seal = read(run / "trips.json"), read(run / "result.json"), read(folder / "evidence/seal.json")
    raw = run / "positions.jsonl.gz"
    assert sha(raw) == seal["originals"][raw.name]["sha256"]
    ident = {k: record[k] for k in ("candidate", "flow", "seed", "scenario", "mode")}
    lanes = {t["vehicle_id"]: t["lane"] for t in trips}
    changes = defaultdict(list)
    for t in trips:
        for e in t["lane_events"]:
            changes[round(e["time_s"] * 10)].append((t["vehicle_id"], e["to_lane"]))
    stats, gap_values, events, schedule = defaultdict(lambda: defaultdict(float)), defaultdict(list), [], defaultdict(list)
    old_states, observed_crossings = {}, set()
    with gzip.open(raw, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            now, states = frame["time_s"], frame["states"]
            tick = round(now * 10)
            for key, lane in changes[tick]:
                lanes[key] = lane
            ordered = sorted(states.items(), key=lambda kv: (kv[1][0], kv[1][1]))
            corridors = [[(key, s) for key, s in ordered if abs(s[1] - (lane + .5) * LANE_WIDTH) < LANE_WIDTH / 2 + WIDTH / 2] for lane in range(3)]
            xs = [[s[0] for _, s in corridor] for corridor in corridors]

            def front(key):
                s, lane = states[key], lanes[key]
                return next(((other, fs) for other, fs in corridors[lane][bisect_right(xs[lane], s[0]):]
                             if other != key and fs[0] - s[0] <= 200), None)

            if window[0] <= now < window[1]:
                for key, s in states.items():
                    x, y, v, a = s
                    peer = front(key)
                    lo = int(x // 20) * 20
                    for lane in (-1, lanes[key]):
                        group = lo, lane
                        row = stats[group]
                        row["vehicle_s"] += .1
                        row["speed_integral_m"] += v * .1
                        row["positive_speed_deficit_s"] += max(0, 1 - v / CRUISE) * .1
                        row["hard_brake_vehicle_s"] += (a <= -6) * .1
                        if peer:
                            gap = peer[1][0] - x
                            gap_values[group].append(gap)
                            row["observed_front_vehicle_s"] += .1
                            row["gap_integral_m_s"] += gap * .1
                            scale = upstream_scale if x < 640 else 1.0
                            row["organization_reference_residual_integral_m_s"] += (gap - scale * (5.5 + HEADWAY * v)) * .1
                    if key not in observed_crossings and key in old_states and old_states[key][0] < 640 <= x:
                        observed_crossings.add(key)
                        peer = front(key)
                        event = dict(vehicle_id=key, anchor_s=now, anchor_lane=lanes[key], anchor_front=peer[0] if peer else None)
                        for offset in (0, 5, 10, 20, 50):
                            schedule[tick + offset].append((event, offset / 10))
            for event, relative in schedule.pop(tick, ()):
                key = event["vehicle_id"]
                own = states.get(key)
                if own is None:
                    continue
                peer = front(key)
                original = states.get(event["anchor_front"])
                events.append(dict(**ident, **event, relative_s=relative, time_s=now, x=own[0], lane=lanes[key], speed=own[2], acceleration=own[3],
                                   current_front=peer[0] if peer else None, current_gap_m=peer[1][0] - own[0] if peer else None,
                                   same_front=bool(peer and peer[0] == event["anchor_front"]),
                                   original_front_dx_m=original[0] - own[0] if original else None))
            old_states = states
    rows = []
    for (lo, lane), values in sorted(stats.items()):
        observed = values["observed_front_vehicle_s"]
        rows.append(dict(**ident, x0_m=lo, x1_m=lo + 20, lane=lane, **values,
                         mean_speed_mps=values["speed_integral_m"] / values["vehicle_s"],
                         mean_gap_m=values.get("gap_integral_m_s", 0) / observed if observed else None,
                         gap_p05_m=quantile(gap_values[lo, lane], .05), gap_p50_m=quantile(gap_values[lo, lane], .5),
                         gap_p95_m=quantile(gap_values[lo, lane], .95)))
    # Independent original region ledger checks the exact diagnostic time window.
    ledger_dir = (folder / "evidence" / seal["traffic_metadata"]).parent
    expected = [0.0, 0.0]
    for line in list(gzip.open(ledger_dir / "region_steps.jsonl.gz", "rt", encoding="utf-8"))[1:]:
        t0, t1, n, low, speed_sum = json.loads(line)
        dt = max(0, min(t1, window[1]) - max(t0, window[0]))
        expected[0] += n * dt
        expected[1] += speed_sum * dt
    chosen = [r for r in rows if r["lane"] == -1 and 800 <= r["x0_m"] < 1000]
    actual = [sum(r["vehicle_s"] for r in chosen), sum(r["speed_integral_m"] for r in chosen)]
    errors = [abs(a - b) for a, b in zip(actual, expected)]
    assert max(errors) < 1e-6
    write_csv(output / (folder.name + "_profile20m.csv"), rows)
    write_csv(output / (folder.name + "_gate640_followers.csv"), events)
    info = dict(**ident, case_dir=str(run), positions_sha256=seal["originals"][raw.name]["sha256"],
                window_s=window, upstream_reference_scale=upstream_scale, cross640_n=len(observed_crossings),
                independent_region_ledger_errors=errors, mean_entry_wait_s=result["mean_entry_wait_s"],
                mean_system_time_s=result["mean_system_time_s"], mean_travel_time_s=result["mean_travel_time_s"],
                total_entry_wait_s=sum(t["entered_s"] - t["requested_s"] for t in trips),
                limitations=["20m statistics use the fixed demand window; cross640 cohort is first sampled crossing in that window and followed for 5s.",
                             "Same-front means exact observed nearest-front identity, and is evaluated only offline. Front changes are retained, not imputed.",
                             "Reference scale annotates a metric only; it does not change any observation, motion, controller or evaluator."])
    (output / (folder.name + "_provenance.json")).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(**ident, crossings=len(observed_crossings), output=str(output))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--batch", type=Path)
    group.add_argument("--case", type=Path, action="append")
    parser.add_argument("--expected-cases", type=int)
    parser.add_argument("--upstream-scale", type=float, default=1.0)
    parser.add_argument("--window-start", type=float, default=30)
    parser.add_argument("--window-end", type=float, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folders = args.case
    if args.batch:
        records = read(args.batch / "manifest.json")
        assert len(records) == args.expected_cases
        folders = [Path(r["case_output"]) for r in records]
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "audit_headway_transition_source.py").write_bytes(Path(__file__).read_bytes())
    for folder in folders:
        analyze(folder, args.output, args.upstream_scale, (args.window_start, args.window_end))
