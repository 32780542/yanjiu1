"""Explain each observed crossing with the two endpoint frames and every vehicle's actual lane events."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
from pathlib import Path

from measure import lane_of


def cut_counts(a, b, forward, backward):
    for k in range(min(a, b), max(a, b)):
        (forward if b > a else backward)[k] += 1


def case(folder):
    row = json.loads((folder / "row.json").read_bytes())
    report = json.loads((folder / "measure.json").read_bytes())
    run = folder.parent / row["run"]
    trips = {t["vehicle_id"]: t for t in json.loads((run / "trips.json").read_bytes())}
    jobs = []
    for stage in ("formation", "transform"):
        m = report.get(stage + "_moves")
        if m is None:
            continue
        a, b = m["start_time_range_s"], m["end_time_range_s"]
        assert a[0] == a[1] and b[0] == b[1]
        jobs.append((stage, a[0], b[0], m))
    wanted = {t for _, a, b, _ in jobs for t in (a, b)}
    snapshots = {}
    if wanted:
        with gzip.open(run / "positions.jsonl.gz", "rt") as src:
            for record in map(json.loads, src):
                t = record["time_s"]
                if t in wanted:
                    snapshots[t] = {k: lane_of(v[1]) for k, v in record["states"].items()}
                    wanted.remove(t)
                    if not wanted:
                        break
    assert not wanted
    output = []
    for stage, a, b, m in jobs:
        s, e = snapshots[a], snapshots[b]
        assert s.keys() == e.keys() == trips.keys()
        crossed, endpoints = (Counter(), Counter()), (Counter(), Counter())
        burdens, direct, multiple, returns = [], [], [], []
        for key in trips:
            lane = s[key]
            hops = 0
            for event in trips[key]["lane_events"]:
                if a < event["time_s"] <= b:
                    nxt = event["to_lane"]
                    assert event["from_lane"] == lane and abs(nxt-lane) == 1
                    cut_counts(lane, nxt, *crossed)
                    lane = nxt
                    hops += 1
            assert lane == e[key]
            cut_counts(s[key], e[key], *endpoints)
            burdens.append(hops)
            direct.append(abs(e[key] - s[key]))
            if hops > 1:
                multiple.append(key)
            if hops > direct[-1]:
                returns.append(key)
        cuts = range(max(max(s.values()), max(e.values()), max((*crossed[0], *crossed[1]), default=0) + 1))
        total = sum(burdens)
        lower = sum(abs(crossed[0][k] - crossed[1][k]) for k in cuts)
        back = total - sum(direct)
        swap = sum(direct) - lower
        assert total - lower == 2 * sum(min(crossed[0][k], crossed[1][k]) for k in cuts)
        assert swap == 2 * sum(min(endpoints[0][k], endpoints[1][k]) for k in cuts)
        assert back >= 0 and back % 2 == 0
        assert lower == m["min_total_crossings"] and total == m["midpoint"]["total"]
        assert sum(direct) == m["assigned_net_crossings"] and max(burdens) == m["midpoint"]["max_per_car"]
        output.append(dict(model=row["model"], road=row["road"], n=row["n"], seed=row["seed"],
            spacing=row["spacing"], stage=stage, whole_both=row["whole_both"], start_s=a, end_s=b,
            actual=total, min_crossings=lower, direct=sum(direct), returns_excess=back,
            opposite_endpoint_excess=swap, max_per_vehicle=max(burdens), min_max=m["min_max_crossings"],
            multiple_ids=" ".join(sorted(multiple)), returning_ids=" ".join(sorted(returns))))
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("batches", nargs="+", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    cases = {}
    for batch in args.batches:
        for f in sorted(batch.glob("*/row.json")):
            row = json.loads(f.read_bytes())
            key = tuple(row[k] for k in ("model", "road", "seed", "n", "spacing"))
            if key in cases:
                original = json.loads((cases[key] / "row.json").read_bytes())
                assert all(original[k] == row[k] for k in (
                    "first_frame_sha256", "upstream_whole_hold_s", "downstream_whole_hold_s", "transform_actual_total"))
            cases[key] = f.parent
    with ProcessPoolExecutor(args.workers) as pool:
        rows = [r for group in pool.map(case, cases.values()) for r in group]
    with args.output.open("w", encoding="utf8", newline="") as dest:
        writer = csv.DictWriter(dest, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(cases)} runs, {len(rows)} formed stage intervals checked")


if __name__ == "__main__":
    main()
