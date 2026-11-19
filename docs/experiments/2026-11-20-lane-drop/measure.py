"""Offline geometry and completed lane changes, using SUMO observations only."""
import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"))
from experiments.complete_layers import groups_at
from experiments.native_sumo import ROAD_LAYOUT, upstream_lanes


def whole_shape(states, lanes):
    """Check every vehicle, including an incomplete last row, in a fixed cohort."""
    columns = [[] for _ in range(lanes)]
    for x, y, speed, *_ in states.values():
        lane = round(y / 3.3 - .5)
        if lane not in range(lanes) or abs(y - (lane + .5) * 3.3) > .3:
            return False
        columns[lane].append((x, speed))
    counts = [len(c) for c in columns]
    speeds = [s for cars in columns for _, s in cars]
    if not speeds or max(speeds) - min(speeds) > .5 or max(counts) - min(counts) > 1:
        return False
    if lanes == 3 and counts[1] > min(counts[0], counts[2]):
        return False
    gap = 5.5 + .85 * sum(speeds) / len(speeds)
    for phase in (range(2) if lanes == 2 else (0,)):
        origins = [x + (k + ((lane + phase) % 2) / 2) * gap for lane, cars in enumerate(columns)
                   for k, (x, _) in enumerate(sorted(cars, reverse=True))]
        if max(origins) - min(origins) <= 2.:
            return True
    return False


def measure(folder, cohort=False):
    result = json.loads((folder / "result.json").read_bytes())
    scenario = result["scenario"]
    incoming = upstream_lanes(scenario)
    boundary, length, retained = ROAD_LAYOUT[scenario]
    trips = json.loads((folder / "trips.json").read_bytes())
    merges = doubles = 0
    for trip in trips:
        events = [(e["from_lane"], e["to_lane"]) for e in trip["lane_completion_events"]
                  if e["x"] >= boundary - 200.]
        merges += (incoming - 1, retained - 1) in events
        doubles += any(a == (incoming - 1, retained - 1) and b == (retained - 1, retained - 2)
                       for a, b in zip(events, events[1:]))
    peaks = [0., 0.]
    starts = [None, None]
    crossings = {}
    samples = formed = 0
    with gzip.open(folder / "positions.jsonl.gz", "rt") as stream:
        for line in stream:
            frame = json.loads(line)
            t, states = frame["time_s"], frame["states"]
            down = {k: v for k, v in states.items() if boundary <= v[0] < boundary + length}
            for k, v in down.items():
                crossings.setdefault(k, round(v[1] / 3.3 - .5))
            if abs(t - round(t)) < 1e-6:
                samples += len(down)
                members = {k for g in groups_at(down, retained) if g["layer_count"] >= 2 for k in g["vehicle_ids"]}
                if retained == 2:
                    reflected = {k: [v[0], 6.6-v[1], *v[2:]] for k,v in down.items()}
                    members.update(k for g in groups_at(reflected, 2) if g["layer_count"] >= 2 for k in g["vehicle_ids"])
                formed += len(members)
            if cohort:
                up = {k: v for k, v in states.items() if v[0] < boundary - 200.}
                for i, (region, lanes) in enumerate(((up, incoming), (down, retained))):
                    if len(region) == result["requested"] and whole_shape(region, lanes):
                        if starts[i] is None:
                            starts[i] = t
                        peaks[i] = max(peaks[i], t - starts[i])
                    else:
                        starts[i] = None
    return dict(status=result["status"], completed=result["completed"], requested=result["requested"],
                collisions=result["collisions"], teleports=result["teleports"], merges=merges, doubles=doubles,
                crossing="/".join(str(list(crossings.values()).count(l)) for l in range(retained)),
                up_s=round(peaks[0],1) if cohort else None, down_s=round(peaks[1],1) if cohort else None,
                downstream_formed_pct=round(100*formed/samples,2) if samples else None,
                travel_s=round(result["mean_travel_time_s"],3) if trips else None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--cohort", action="store_true")
    args = parser.parse_args()
    print(json.dumps(measure(args.folder, args.cohort), indent=2))
