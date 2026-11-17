"""Measure 2000-flow queue propagation and observed lane-change chronology."""

import argparse
import gzip
import json
from pathlib import Path
from statistics import median


BANDS = ((0, 100), (100, 300), (300, 600), (600, 800), (800, 900), (900, 1000))
LANES = range(3)
LOW_SPEED = 5.0
STREAK_TICKS = 30
SIMULTANEOUS = 3


def inspect(run):
    cells = [dict(x0=lo, x1=hi, lane=lane, low_speed_vehicle_s=0.0, speed_sum=0.0,
                  position_samples=0, first_sustained_low_speed_s=None, peak_low_n=0,
                  first_low_speed_s=None) for lo, hi in BANDS for lane in LANES]
    streak = [0] * len(cells)
    position = run / "positions.jsonl.gz"
    previous_tick = None
    previous_states = {}
    crossing_times = {lane: [] for lane in LANES}
    crossed = set()
    with gzip.open(position, "rt", encoding="utf-8") as frames:
        for line in frames:
            row = json.loads(line)
            tick = round(10 * row["time_s"])
            assert previous_tick is None or tick == previous_tick + 1
            previous_tick = tick
            counts = [0] * len(cells)
            for vehicle, (x, y, v, _) in row["states"].items():
                if x >= 1000 and vehicle not in crossed and vehicle in previous_states:
                    old_x, old_y, _, _ = previous_states[vehicle]
                    if old_x < 1000:
                        crossed.add(vehicle)
                        fraction = (1000 - old_x) / (x - old_x)
                        time = (tick - 1 + fraction) / 10
                        lane = min(2, max(0, int((old_y + fraction * (y - old_y)) / 3.3)))
                        if 100 <= time <= 600:
                            crossing_times[lane].append(time)
                if not 0 <= x < 1000:
                    continue
                lane = min(2, max(0, int(y / 3.3)))
                band = sum(x >= hi for _, hi in BANDS)
                index = 3 * band + lane
                cell = cells[index]
                if 1000 <= tick < 6000:
                    cell["position_samples"] += 1
                    cell["speed_sum"] += v
                counts[index] += v < LOW_SPEED
            previous_states = row["states"]
            for i, count in enumerate(counts):
                cell = cells[i]
                if 1000 <= tick < 6000:
                    cell["low_speed_vehicle_s"] += .1 * count
                if count and cell["first_low_speed_s"] is None:
                    cell["first_low_speed_s"] = tick / 10
                cell["peak_low_n"] = max(count, cell["peak_low_n"])
                streak[i] = streak[i] + 1 if count >= SIMULTANEOUS else 0
                if streak[i] == STREAK_TICKS and cell["first_sustained_low_speed_s"] is None:
                    cell["first_sustained_low_speed_s"] = (tick + 1 - STREAK_TICKS) / 10
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    assert previous_tick == round(10 * result["actual_end_s"])
    for cell in cells:
        cell["mean_speed_mps"] = cell.pop("speed_sum") / cell["position_samples"] if cell["position_samples"] else None
        cell["low_speed_vehicle_s"] = round(cell["low_speed_vehicle_s"], 3)
    chronology = []
    for a, b in ((2, 1), (1, 0), (0, 1), (1, 2)):
        events = sorted((e for e in result["lane_completion_events"] if (e["from_lane"], e["to_lane"]) == (a, b)),
                        key=lambda e: (e["time_s"], e["x"]))
        chronology.append(dict(from_lane=a, to_lane=b, completed=len(events), first=events[:5],
                               before_visible=sum(e["x"] < 800 for e in events),
                               before_900=sum(e["x"] < 900 for e in events),
                               median_x_m=median(e["x"] for e in events) if events else None,
                               per_time_window=[dict(t0=t, t1=t + 100, completed=sum(t <= e["time_s"] < t + 100 for e in events))
                                                for t in range(0, 800, 100)]))
    discharge = []
    for lane, times in crossing_times.items():
        times.sort()
        headways = [b - a for a, b in zip(times, times[1:])]
        discharge.append(dict(lane=lane, crossings=len(times), rate_veh_h=len(times) * 3600 / 500,
                              median_headway_s=median(headways) if headways else None))
    return dict(cells=cells, lane_completion_chronology=chronology, lane_discharge=discharge)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--extra-manifest", nargs="+", metavar="LABEL=MANIFEST")
    parser.add_argument("--only-extra", action="store_true")
    args = parser.parse_args()
    existing = [] if args.only_extra else json.loads(args.results.read_text(encoding="utf-8"))["cases"]
    for spec in args.extra_manifest or ():
        label, path = spec.split("=", 1)
        additional = json.loads(Path(path).read_text(encoding="utf-8"))
        existing += [{**row, "profile": label} for row in additional]
    items = []
    for row in existing:
        if row["flow"] != 2000 or not row["safe"] or not row["all_completed"]:
            continue
        identity = {key: row[key] for key in ("profile", "flow", "seed", "mode", "run")}
        items.append({**identity, **inspect(Path(row["run"]))})
        print(identity["profile"], identity["seed"], identity["mode"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(cases=items, low_speed_mps=LOW_SPEED,
                                          sustained=dict(min_vehicles=SIMULTANEOUS, min_duration_s=STREAK_TICKS / 10),
                                          aggregation=[100, 600]), indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
