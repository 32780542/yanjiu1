"""Measure the shortest downstream observation window for one unchanged moving group."""
import argparse
from collections import deque
import csv
import gzip
import json
from pathlib import Path

from measure import road_layout, whole_shape

HERE = Path(__file__).resolve().parent
DURATIONS = (0, 1, 3, 5, 10, 20, 25)


def observation(run, ref, lengths=DURATIONS):
    ids = set(ref["ids"].split())
    (_, cut), (lanes, length) = road_layout(run)
    assert len(ids) % lanes == 0 and length == 1000
    q = len(ids) / lanes - .5
    previous = {}
    segment = deque(maxlen=round(10 * max(lengths)) + 1)
    witnesses = {}
    best, since = 0, None
    gate = float(ref["long1000_up_t"])
    with gzip.open(run / "positions.jsonl.gz", "rt") as stream:
        for frame in map(json.loads, stream):
            t, all_cars = frame["time_s"], frame["states"]
            if t < gate:
                continue
            if not ids.issubset(all_cars):
                if previous:
                    break
                continue
            group = {k: all_cars[k] for k in ids}
            if previous:
                assert all(group[k][0] >= previous[k][0] - 1e-8 for k in ids)
            previous = group
            xs = [s[0] for s in group.values()]
            head, tail = max(xs), min(xs)
            fits = (tail >= cut and head < cut + length and whole_shape(group, lanes)
                    and all(not tail <= s[0] <= head for k, s in all_cars.items() if k not in ids))
            if not fits:
                since = None
                segment.clear()
                continue
            tick = round(t * 10)
            since = tick if since is None else since
            best = max(best, tick - since)
            mean_speed = sum(s[2] for s in group.values()) / len(group)
            ideal = q * (5.5 + .85 * mean_speed)
            assert abs((head - tail) - ideal) <= 2.0 + 1e-7
            segment.append((tick, tail, head, ideal))
            for hold in lengths:
                steps = round(hold * 10)
                if tick - since < steps or hold in witnesses:
                    continue
                start, rear0, front0, span = segment[-steps-1]
                assert start + steps == tick
                witnesses[hold] = dict(
                    road=ref["road"], seed=ref["seed"], n=len(ids), hold_s=hold,
                    start_s=start/10, end_s=t, start_rear_m=round(rear0-cut,3),
                    start_head_m=round(front0-cut,3), start_ideal_span_m=round(span,3),
                    start_actual_span_m=round(front0-rear0,3), minimum_from_boundary_m=round(head-cut,3),
                    swept_envelope_m=round(head-rear0,3))
    assert best / 10 == float(ref["long1000_longest_s"])
    for h in (0,3):
        assert abs(witnesses[h]["start_s"] - float(ref[f"long1000_d{h}_t"])) < 1e-7
    return [witnesses.get(h,dict(road=ref["road"],seed=ref["seed"],n=len(ids),hold_s=h)) for h in lengths]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with (HERE / "boundary_length_members.csv").open(encoding="utf8") as stream:
        refs = [row for row in csv.DictReader(stream) if row["phase"] == "standard"]
    rows = []
    for row in refs:
        matches = list((args.batch / f"{row['road']}_{row['seed']}_1000").glob("*/positions.jsonl.gz"))
        assert len(matches) == 1
        rows.extend(observation(matches[0].parent, row))
    with args.output.open("w", newline="", encoding="utf8") as stream:
        out = csv.DictWriter(stream, fieldnames=list(rows[0]))
        out.writeheader()
        out.writerows(rows)
    print(f"{len(refs)} unchanged groups, {len(rows)} duration tests")


if __name__ == "__main__":
    main()
