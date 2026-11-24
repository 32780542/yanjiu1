"""Follow closed, full-layer groups across a real lane-count change in continuous SUMO traffic."""

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import csv
import gzip
import hashlib
import itertools
import json
from math import lcm
from pathlib import Path

from measure import centered, lane_of, moves, road_layout, sample, whole_shape


def classify_gate(states, lanes, shaped, totals):
    """Separate position fit from speed fit, retaining the observed mean spacing in both."""
    totals["closed"] += 1
    if not centered(states, lanes):
        return
    totals["centered"] += 1
    counts = Counter(lane_of(s[1]) for s in states.values())
    if any(counts[lane] * lanes != len(states) for lane in range(lanes)):
        return
    totals["balanced"] += 1
    speeds = [s[2] for s in states.values()]
    equal_speed = max(speeds) - min(speeds) <= 0.5
    totals["speed_fit"] += equal_speed
    mean = sum(speeds) / len(speeds)
    positions_only = {key: (s[0], s[1], mean) for key, s in states.items()}
    totals["origin_fit"] += whole_shape(positions_only, lanes)
    totals["both"] += shaped
    if equal_speed and not shaped:
        # For complete equal-length columns, reversing longitudinal order exchanges leading parity.
        reflected = {key: (-s[0], s[1], s[2]) for key, s in states.items()}
        totals["opposite_only"] += whole_shape(reflected, lanes)


def opposite_shape(states, lanes):
    # Each audited group has full, equal-length columns. Longitudinal reversal
    # swaps the two possible leading half-layers without altering lane labels.
    return whole_shape({k: (-s[0], s[1], s[2]) for k, s in states.items()}, lanes)


def eligible_windows(
    previous, current, crossing, gate, count, lanes, diagnostics=None, either_phase=False
):
    """Order simultaneous candidates by interpolated front passage, then physical position."""
    progress = {}
    for key in crossing:
        x0, x1 = previous[key][0], current[key][0]
        fraction = (gate - x0) / (x1 - x0)
        progress[x0] = min(fraction, progress.get(x0, 1.0))
    # Exact longitudinal ties are indivisible; ordering among tied IDs never chooses members.
    order = sorted(previous, key=lambda k: -previous[k][0])
    xs = [-previous[k][0] for k in order]
    for head in sorted(progress, key=lambda x: (progress[x], -x)):
        i = bisect_left(xs, -head)
        j = i + count
        if j > len(order) or j < len(order) and xs[j - 1] == xs[j]:
            continue
        keys = order[i:j]
        obs = {k: previous[k] for k in keys}
        shaped = whole_shape(obs, lanes)
        if diagnostics is not None:
            classify_gate(obs, lanes, shaped, diagnostics)
        if shaped or (either_phase and lanes > 2 and opposite_shape(obs, lanes)):
            yield frozenset(keys), obs


def write_csv(path, rows, fields=()):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(dict.fromkeys([*fields, *(k for r in rows for k in r)]))
        )
        writer.writeheader()
        writer.writerows(rows)


def strata_rows(runs):
    """Pool numerators and denominators only within a controller, duration, road and gate period."""
    strata = {}
    for run in runs:
        key = (run["model"], run["road"], run["demand_s"], run["period"])
        strata.setdefault(key, []).append(run)
    out = []
    for (model, road, duration, period), cells in sorted(strata.items()):
        row = dict(model=model, road=road, demand_s=duration, period=period, runs=len(cells))
        fields = [
            "crossing_vehicles",
            "eligible_windows",
            "excluded_shared",
            "groups",
            "censored",
            "open_shape",
            "foreign_before_first",
            "foreign_down",
            "foreign_ever",
        ]
        for seconds in (0, 1, 3):
            fields.extend(
                f"d{seconds}_{k}"
                for k in ("exposed", "groups", "moves", "lb", "total_opt", "max_opt", "joint_opt")
            )
        for field in fields:
            row[field] = sum(int(cell[field]) for cell in cells)
        for seconds in (0, 1, 3):
            row[f"d{seconds}_pct"] = (
                round(100 * row[f"d{seconds}_groups"] / row["groups"], 2) if row["groups"] else None
            )
            row[f"d{seconds}_joint_pct"] = (
                round(100 * row[f"d{seconds}_joint_opt"] / row["groups"], 2) if row["groups"] else None
            )
        out.append(row)
    return out


def compact_cost(start, end, trips, width):
    result = moves(start, end, trips, width)
    mid = result["midpoint"]
    if mid["mismatch_ids"]:
        raise ValueError(f"Invalid lane-index event chain: {mid['mismatch_ids']}")
    return (
        mid["total"],
        result["min_total_crossings"],
        mid["max_per_car"],
        result["min_max_crossings"],
    )


class Group:
    def __init__(self, keys, start, time, tick, dt, crossing, either_phase=False):
        self.keys, self.start, self.dt = keys, sample(time, start), dt
        self.either_phase = either_phase
        self.gate_tick = tick
        head_x = max(s[0] for s in start.values())
        front = {k for k, s in start.items() if s[0] == head_x}
        self.front_size = len(front)
        self.front_crossed = len(front.intersection(crossing))
        self.censored = False
        self.down_seen = self.open_shape = self.foreign_before_first = self.foreign_down = (
            self.foreign_ever
        ) = False
        self.max_foreign = 0
        self.episode = None
        self.episodes = 0
        self.best_steps = 0
        self.all_down_since = None
        self.max_down_steps = 0
        self.first = {}

    def observe(self, tick, t, states, positions, cut, end, lanes):
        inside = {k: states[k] for k in self.keys}
        xs = [s[0] for s in inside.values()]
        lo, hi = min(xs), max(xs)
        others = bisect_right(positions, hi) - bisect_left(positions, lo) - len(xs)
        self.max_foreign = max(self.max_foreign, others)
        self.foreign_ever |= bool(others)
        if 0 not in self.first:
            self.foreign_before_first |= bool(others)
        down = cut <= lo and hi < end
        self.down_seen |= down
        if down:
            if self.all_down_since is None:
                self.all_down_since = tick
            self.max_down_steps = max(self.max_down_steps, tick - self.all_down_since)
        else:
            self.all_down_since = None
        self.foreign_down |= down and bool(others)
        shaped = down and (
            whole_shape(inside, lanes)
            or (self.either_phase and lanes > 2 and opposite_shape(inside, lanes))
        )
        self.open_shape |= shaped
        if not shaped or others:
            self.episode = None
            return
        if self.episode is None:
            self.episode = (tick, sample(t, inside))
            self.episodes += 1
        since, first = self.episode
        steps = tick - since
        self.best_steps = max(self.best_steps, steps)
        for seconds in (0, 1, 3):
            if seconds not in self.first and steps >= round(seconds / self.dt):
                self.first[seconds] = first

    def row(self, trips, width, stop):
        start_time = next(iter(self.start.values()))[0]
        gate_time = round(self.gate_tick * self.dt, 6)
        row = dict(
            gate_t=gate_time,
            up_t=start_time,
            period="demand" if gate_time <= stop else "drain",
            ids=" ".join(sorted(self.keys)),
            down_all_seen=int(self.down_seen),
            all_down_longest_s=round(self.max_down_steps * self.dt, 6) if self.down_seen else None,
            head_tied=self.front_size,
            head_crossed=self.front_crossed,
            censored=int(self.censored),
            open_shape=int(self.open_shape),
            foreign_before_first=int(self.foreign_before_first),
            foreign_down=int(self.foreign_down),
            foreign_ever=int(self.foreign_ever),
            max_foreign=self.max_foreign,
            episodes=self.episodes,
            longest_s=round(self.best_steps * self.dt, 6),
        )
        for seconds in (0, 1, 3):
            first = self.first.get(seconds)
            prefix = f"d{seconds}_"
            row[prefix + "t"] = next(iter(first.values()))[0] if first else None
            for key, val in zip(
                ("moves", "lb", "max", "max_lb"),
                compact_cost(self.start, first, trips, width) if first else (None,) * 4,
            ):
                row[prefix + key] = val
        return row


def summarize(groups):
    row = dict(groups=len(groups))
    for k in (
        "down_all_seen",
        "open_shape",
        "foreign_before_first",
        "foreign_down",
        "foreign_ever",
        "censored",
    ):
        row[k] = sum(g[k] for g in groups)
    for seconds in (0, 1, 3):
        p = f"d{seconds}_"
        complete = [g for g in groups if g[p + "t"] is not None]
        row[p + "exposed"] = sum(
            g["all_down_longest_s"] is not None and g["all_down_longest_s"] >= seconds for g in groups
        )
        row[p + "groups"] = len(complete)
        row[p + "moves"] = sum(g[p + "moves"] for g in complete)
        row[p + "lb"] = sum(g[p + "lb"] for g in complete)
        row[p + "total_opt"] = sum(g[p + "moves"] == g[p + "lb"] for g in complete)
        row[p + "max_opt"] = sum(g[p + "max"] == g[p + "max_lb"] for g in complete)
        row[p + "joint_opt"] = sum(
            g[p + "moves"] == g[p + "lb"] and g[p + "max"] == g[p + "max_lb"] for g in complete
        )
    return row


def evaluate(job, gate_criteria=False, downstream_window=None, either_phase=False):
    name, path = job
    settings = json.loads((path / "input.json").read_bytes())
    config = settings["case"]
    stop = config["demand_duration_s"]
    dt = settings["positions_step_s"]
    if dt != 0.1:
        raise ValueError("The protocol requires native 0.1 s samples")
    trips = {r["vehicle_id"]: r for r in json.loads((path / "trips.json").read_bytes())}
    result = json.loads((path / "result.json").read_bytes())
    (k, cut), (l, down_length) = road_layout(path)
    down_start, down_stop = downstream_window or (0.0, down_length)
    if not 0 <= down_start < down_stop <= down_length:
        raise ValueError("Downstream observation window is outside the real road")
    size = lcm(k, l)
    gate = cut - 200.0
    used, passed = set(), set()
    previous = {}
    active, all_groups = [], []
    eligible, overlap, crossings = Counter(), Counter(), Counter()
    diagnostics = {period: Counter() for period in ("demand", "drain")}
    previous_tick = None
    with gzip.open(path / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            states, t = frame["states"], frame["time_s"]
            tick = round(t / dt)
            if abs(t - tick * dt) > 1.0e-6 or previous_tick is not None and tick != previous_tick + 1:
                raise ValueError(f"Missing/off-grid frame at {t}")
            new = [
                v
                for v, s in states.items()
                if s[0] >= gate and v in previous and previous[v][0] < gate and v not in passed
            ]
            if new:
                period = "demand" if t <= stop else "drain"
                crossings[period] += len(new)
                passed.update(new)
                funnel = diagnostics[period] if gate_criteria else None
                for keys, obs in eligible_windows(
                    previous, states, new, gate, size, k, funnel, either_phase
                ):
                    eligible[period] += 1
                    if not used.isdisjoint(keys):
                        overlap[period] += 1
                        continue
                    used.update(keys)
                    group = Group(keys, obs, round(previous_tick * dt, 6), tick, dt, new, either_phase)
                    active.append(group)
                    all_groups.append(group)
            if active:
                positions = sorted(s[0] for s in states.values())
                active = [g for g in active if g.keys.issubset(states)]
                if down_stop < down_length:
                    # Once the first original member leaves this observation window the group
                    # can never again be observed in full. Ignore later traffic outside it.
                    active = [
                        g for g in active if all(states[key][0] < cut + down_stop for key in g.keys)
                    ]
                for g in active:
                    g.observe(tick, t, states, positions, cut + down_start, cut + down_stop, l)
            previous, previous_tick = states, tick
    if active and result["status"] == "drained":
        raise ValueError("A drained trace ended before its last selected group exited")
    for group in active:
        group.censored = True
    ident = dict(
        model=name,
        road=f"{k}to{l}",
        flow=config["flow_veh_h_lane"],
        seed=config["seed"],
        demand_s=stop,
        n=size,
    )
    common = dict(
        status=result["status"],
        completed=result["completed"],
        requested=result["requested"],
        collisions=result["collisions"],
        teleports=result["teleports"],
        demand_sha=hashlib.sha256(
            json.dumps(settings["arrivals"], sort_keys=True).encode()
        ).hexdigest(),
        rules_sha=result["source_sha256"]["noa/native_rules.py"],
        staggered_sha=result["source_sha256"].get("noa/staggered.py", ""),
    )
    rows = [dict(**ident, **g.row(trips, max(k, l), stop)) for g in all_groups]
    totals = [
        dict(
            **ident,
            period=period,
            crossing_vehicles=crossings[period],
            eligible_windows=eligible[period],
            excluded_shared=overlap[period],
            **summarize([r for r in rows if r["period"] == period]),
            **common,
        )
        for period in ("demand", "drain")
    ]
    for r in totals:
        assert r["groups"] == r["eligible_windows"] - r["excluded_shared"]
        if gate_criteria:
            counts = diagnostics[r["period"]]
            for key in (
                "closed",
                "centered",
                "balanced",
                "speed_fit",
                "origin_fit",
                "both",
                "opposite_only",
            ):
                r["gate_" + key] = counts[key]
            assert r["eligible_windows"] == counts["both"] + (
                counts["opposite_only"] if either_phase else 0
            )
    return totals, rows


def self_test():
    dt = 0.1
    gap = 30.0
    speed = (gap - 5.5) / 0.85

    def v(x, lane):
        return [x, 3.3 * (lane + 0.5), speed, 0]

    a = dict(A=v(99, 0), B=v(99, 2), C=v(84, 1), D=v(69, 0), E=v(69, 2), F=v(54, 1))
    mirrored = {key: (-s[0], *s[1:]) for key, s in a.items()}
    assert not whole_shape(mirrored, 3) and opposite_shape(mirrored, 3)
    b = {key: [x + 3, y, s, ac] for key, (x, y, s, ac) in a.items()}
    assert len(list(eligible_windows(a, b, ["A", "B"], 100, 6, 3))) == 1
    rev = dict(reversed(list(a.items())))
    assert next(eligible_windows(rev, b, ["B", "A"], 100, 6, 3))[0] == frozenset(a)
    assert not list(eligible_windows(dict(a, G=v(54, 1)), b, ["A", "B"], 100, 6, 3))
    assert not list(eligible_windows(dict(a, G=v(75, 2)), b, ["A", "B"], 100, 6, 3))
    g = Group(frozenset(a), a, 0.0, 1, dt, ["B"])
    assert (g.front_size, g.front_crossed) == (2, 1)
    down = {key: v(300 - i * 15, i % 2) for i, key in enumerate(a)}
    for tick in range(1, 33):
        frame = dict(down, X=v(260, 1)) if tick == 1 else down
        g.observe(tick, tick * dt, frame, sorted(s[0] for s in frame.values()), 200.0, 1000.0, 2)
        if tick == 11:
            assert 1 not in g.first
        if tick == 31:
            assert 3 not in g.first
    assert g.foreign_before_first and g.open_shape and g.first.keys() == {0, 1, 3}
    assert g.best_steps == 30 and g.episodes == 1
    print("Exact ties, geometric closure, foreign intrusion and 0/1/3 s thresholds passed.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", action="append", default=[], metavar="LABEL=DIR")
    p.add_argument("--roads", nargs="+", default=["3to2", "4to3"])
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", type=Path)
    p.add_argument("--self-test", action="store_true")
    p.add_argument(
        "--either-phase",
        action="store_true",
        help="Accept either leading half-layer for all lane counts.",
    )
    p.add_argument(
        "--gate-criteria",
        action="store_true",
        help="Also count closed gate windows passing the lane, speed and position criteria.",
    )
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if not a.batch or a.out is None:
        p.error("Both --batch and --out are required")
    planned = set()
    finished = {}
    fingerprints = {}
    for item in a.batch:
        label, dirname = item.split("=", 1)
        home = Path(dirname)
        manifest = home / "manifest.json"
        if manifest.is_file():
            spec = json.loads(manifest.read_bytes())["arguments"]
            planned.update(
                (label, road, int(seed), float(flow), float(spec["duration"]))
                for road, seed, flow in itertools.product(spec["roads"], spec["seeds"], spec["flows"])
                if road in a.roads
            )
        for path in sorted(home.glob("*/*/result.json")):
            road = path.parent.parent.name.split("_")[0]
            if road not in a.roads:
                continue
            config = json.loads((path.parent / "input.json").read_bytes())
            controls = config["case"]
            key = (
                label,
                road,
                controls["seed"],
                controls["flow_veh_h_lane"],
                controls["demand_duration_s"],
            )
            planned.add(key)
            # An explicitly supplied recovery may replace an unfinished copy only when
            # the actual source snapshot and requested physical arrivals agree.
            fingerprint = hashlib.sha256(
                json.dumps([config["source_sha256"], config["arrivals"]], sort_keys=True).encode()
            ).hexdigest()
            if fingerprints.setdefault(key, fingerprint) != fingerprint:
                raise ValueError(f"Source or demand differs between repeated inputs: {key}")
            status = json.loads(path.read_bytes()).get("status")
            if status == "starting":
                continue
            if status not in ("drained", "time_limit", "unsafe") or key in finished:
                raise ValueError(f"Ambiguous or invalid completed run: {key}, {path}, {status}")
            finished[key] = (label, path.parent)
    if planned != finished.keys():
        raise ValueError(f"Missing completed planned inputs: {sorted(planned - finished.keys())}")
    jobs = list(finished.values())
    if not jobs:
        raise ValueError("No finished records matched")
    a.out.mkdir(parents=True, exist_ok=False)
    results = []
    cohorts = []
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for counts, groups in pool.map(
            partial(evaluate, gate_criteria=a.gate_criteria, either_phase=a.either_phase), jobs
        ):
            results.extend(counts)
            cohorts.extend(groups)
    write_csv(a.out / "runs.csv", results)
    write_csv(a.out / "strata.csv", strata_rows(results))
    write_csv(
        a.out / "groups.csv",
        cohorts,
        fields=("model", "road", "flow", "seed", "demand_s", "period", "ids"),
    )
    print(len(jobs), "runs,", len(cohorts), "disjoint upstream groups")


if __name__ == "__main__":
    main()
