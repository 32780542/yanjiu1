"""Trace-only decomposition of the official two-lane persistent geometry metric."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
from pathlib import Path
import statistics

from persistent_flow import links
from measure import road_layout

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDY = ROOT / "tmp/nov25study"


def flags(ids, states):
    cars = [states[k] for k in ids]
    lanes = [round(s[1] / 3.3 - .5) for s in cars]
    centered = all(j in (0, 1) and abs(s[1] - (j + .5)*3.3) <= .300000001
                   for j, s in zip(lanes, cars))
    alternating = (lanes in ([0, 1, 0, 1], [1, 0, 1, 0]))
    phase = all(abs(cars[k][0] - cars[k+1][0] - 15) <= 2.000000001 for k in (0, 2))
    spacing = all(abs(cars[k][0] - cars[k+2][0] - 30) <= 2.000000001 for k in (0, 1))
    speed = max(s[2] for s in cars) - min(s[2] for s in cars) <= .500000001
    return dict(center=centered, lanes=alternating, phase=phase, spacing=spacing, speed=speed)


def audit(job):
    name, run = job
    (_, cut), (lanes, length) = road_layout(run)
    assert lanes == 2 and length == 200
    result = json.loads((run / "result.json").read_bytes())
    data = Counter()
    active = {}
    born, departed = {}, {}
    episodes = []
    old_states = {}
    old_t = None
    with gzip.open(run / "positions.jsonl.gz", "rt") as f:
        for line in f:
            frame = json.loads(line)
            t = frame["time_s"]
            states = {k:s for k,s in frame["states"].items() if cut <= s[0] < cut + length}
            for k in old_states.keys() - states.keys():
                departed[k] = old_t
            new_ids = states.keys() - born.keys()
            born.update(dict.fromkeys(new_ids,t))
            if new_ids:
                order = sorted(states, key=lambda k: -states[k][0])
                for i in range(3, len(order)):
                    if order[i] in new_ids:
                        checks = flags(order[i-3:i+1], states)
                        data["gate_windows"] += 1
                        for label, ok in checks.items():
                            data["gate_"+label] += ok
                        shape = all(checks[k] for k in ("center","lanes","phase","spacing"))
                        data["gate_geometry"] += shape
                        data["gate_geometry_and_speed"] += shape and checks["speed"]
            if old_t is not None:
                dt = t - old_t
                assert abs(dt - .1) < 1e-8
                earliest = {}
                for pair, (onset, gate) in active.items():
                    for row in pair:
                        for k in row:
                            key = (onset, not gate)
                            if k not in earliest or key < earliest[k]:
                                earliest[k] = key
                for k, s in old_states.items():
                    band = min(3, int((s[0]-cut)//50))
                    data["vehicle_s"] += dt
                    data[f"band{band}_s"] += dt
                    if k in earliest:
                        onset, late = earliest[k]
                        mature = max(0., t-max(old_t, onset+3))
                        data["held0_s"] += dt
                        data["held3_s"] += mature
                        data["held3_late_s" if late else "held3_gate_s"] += mature
                        data[f"band{band}_held0_s"] += dt
                        data[f"band{band}_held3_s"] += mature
            current = links(states, lanes) if len(states) >= 4 else set()
            for pair in active.keys() - current:
                onset, gate = active[pair]
                ids = pair[0] + pair[1]
                duration = t - onset
                if all(k in states for k in ids):
                    checks = flags(ids, states)
                    data["ends_inside"] += 1
                    for label, ok in checks.items():
                        data["loss_"+label] += not ok
                    data["loss_geometry_only"] += checks["speed"] and not all(checks.values())
                    data["loss_speed_only"] += not checks["speed"] and all(checks[k] for k in ("center","lanes","phase","spacing"))
                    data["loss_other"] += all(checks.values())
                else:
                    data["exit_censored"] += 1
                episodes.append((ids,onset,duration,gate))
            updated = {}
            for pair in current:
                ids = pair[0] + pair[1]
                updated[pair] = active.get(pair, (t, max(born[k] for k in ids)==t))
            active = updated
            old_states, old_t = states, t
    assert not active and not old_states
    assert born.keys()==departed.keys()
    times = [departed[k] - t for k,t in born.items()]
    data["residence_mean_s"] = statistics.mean(times)
    data["episodes"] = len(episodes)
    for ids,onset,duration,gate in episodes:
        remaining = min(departed[k] for k in ids) + .1 - onset
        data["gate_episodes"] += gate
        data["room_for3"] += remaining >= 3-1e-8
        data["lasted3"] += duration >= 3-1e-8
    columns = ("gate_windows", "gate_center", "gate_lanes", "gate_phase", "gate_spacing", "gate_speed",
               "gate_geometry", "gate_geometry_and_speed", "vehicle_s","held0_s","held3_s","held3_gate_s","held3_late_s",
               "episodes","gate_episodes","room_for3","lasted3","ends_inside","exit_censored","loss_center","loss_lanes",
               "loss_phase","loss_spacing","loss_speed","loss_speed_only","loss_geometry_only","loss_other","residence_mean_s")
    columns += tuple(f"band{i}_{suffix}" for i in range(4) for suffix in ("s","held0_s","held3_s"))
    row = dict(batch=name, seed=result["seed"],flow=result["flow_veh_h_lane"],completed=result["completed"],
               collisions=result["collisions"],teleports=result["teleports"])
    row.update({k:round(data[k],6) for k in columns})
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    jobs = [(batch, path.parent) for batch in args.batches
            for path in sorted((STUDY / batch).glob("3to2_s*_q*/*/result.json"))
            if args.seeds is None or int(path.parent.parent.name.split("_")[1][1:]) in args.seeds]
    assert jobs
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(audit,jobs))
    with args.output.open("x",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,rows[0]); writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {len(rows)} runs to {args.output}")
