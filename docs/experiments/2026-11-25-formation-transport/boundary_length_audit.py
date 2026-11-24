"""Audit whole-group opportunity, equal arrivals and observed upstream changes in a road-length pair."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import itertools
import json
from pathlib import Path

from boundary_cohorts import evaluate, write_csv
from measure import road_layout


def record_entry(frame, entries, gates):
    if frame is None:
        return
    t = frame["time_s"]
    for key, state in frame["states"].items():
        entries.setdefault(key, (t, *state))
        if state[0] >= 800:
            gates.setdefault(key, t)


def observations(folder, rows, fields):
    wanted = {}
    for ids, r in rows.items():
        for k in fields:
            if r[k] is not None:
                wanted.setdefault(r[k], []).append((ids, k))
    result = {}
    if wanted:
        with gzip.open(folder / "positions.jsonl.gz", "rt") as stream:
            for frame in map(json.loads, stream):
                if frame["time_s"] not in wanted:
                    continue
                for ids, k in wanted.pop(frame["time_s"]):
                    result[ids, k] = [frame["states"][i] for i in ids.split()]
                if not wanted:
                    break
    assert not wanted
    return result


def input_comparison(short, long):
    cfg = [json.loads((d / "input.json").read_bytes()) for d in (short, long)]
    assert cfg[0]["arrivals"] == cfg[1]["arrivals"]
    assert cfg[0]["source_sha256"] == cfg[1]["source_sha256"]
    n = len(cfg[0]["arrivals"])
    stop = cfg[0]["case"]["demand_duration_s"]
    entries = [{}, {}]
    gates = [{}, {}]
    tested = exact = same_ids = 0
    first_diff = None
    maxdiff = [0.0, 0.0, 0.0, 0.0]
    with gzip.open(short / "positions.jsonl.gz", "rt") as a, gzip.open(
        long / "positions.jsonl.gz", "rt"
    ) as b:
        for fa, fb in itertools.zip_longest(map(json.loads, a), map(json.loads, b)):
            record_entry(fa, entries[0], gates[0])
            record_entry(fb, entries[1], gates[1])
            if fa is None or fb is None:
                continue
            t = fa["time_s"]
            assert t == fb["time_s"]
            if t > stop:
                continue
            left = {k: s for k, s in fa["states"].items() if s[0] < 800}
            right = {k: s for k, s in fb["states"].items() if s[0] < 800}
            tested += 1
            same_ids += left.keys() == right.keys()
            if left == right:
                exact += 1
            else:
                if first_diff is None:
                    first_diff = t
                for key in left.keys() & right.keys():
                    for i, (v, w) in enumerate(zip(left[key], right[key])):
                        maxdiff[i] = max(maxdiff[i], abs(v - w))
    assert (
        entries[0].keys() == entries[1].keys() == gates[0].keys() == gates[1].keys()
        and len(entries[0]) == n
    )
    return dict(
        arrivals=n,
        identical_physical_entries=sum(entries[0][i] == entries[1][i] for i in entries[0]),
        identical_entry_times=sum(entries[0][i][0] == entries[1][i][0] for i in entries[0]),
        max_entry_time_delta_s=max(abs(entries[0][i][0] - entries[1][i][0]) for i in entries[0]),
        identical_gate_times=sum(gates[0][i] == gates[1][i] for i in gates[0]),
        max_gate_time_delta_s=max(abs(gates[0][i] - gates[1][i]) for i in gates[0]),
        up_frames=tested,
        up_same_ids_frames=same_ids,
        up_identical_frames=exact,
        up_first_difference_s=first_diff,
        up_max_common_x_delta_m=maxdiff[0],
        up_max_common_y_delta_m=maxdiff[1],
        up_max_common_speed_delta_m_s=maxdiff[2],
        up_max_common_accel_delta_m_s2=maxdiff[3],
    )


def audit_case(pair):
    out, road, seed = pair
    paths = []
    for length in (200, 1000):
        home = out / f"{road}_{seed}_{length}"
        done = json.loads((home / "complete.json").read_bytes())
        if done["status"] != "drained":
            raise ValueError(f"Group observation could be censored: {home}")
        folder = home / done["folder"]
        assert road_layout(folder) == [(int(road[0]), 1000.0), (int(road[-1]), float(length))]
        paths.append(folder)
    checks = input_comparison(*paths)
    summary = []
    groups = []
    comparison = []
    per_id = []
    for either in (False, True):
        context = dict(road=road, seed=seed, phase="both" if either else "standard")
        samples = {}
        for folder, length, lo, hi in (
            (paths[0], 200, 0, 200),
            (paths[1], 1000, 0, 200),
            (paths[1], 1000, 0, 1000),
            (paths[1], 1000, 200, 1000),
        ):
            counts, rows = evaluate(
                ("moment", folder), downstream_window=(lo, hi), either_phase=either
            )
            window = dict(
                physical_down_m=length, down_start_m=lo, down_end_m=hi, phase=context["phase"]
            )
            summary.extend(dict(r, **window) for r in counts)
            groups.extend(dict(r, **window) for r in rows)
            samples[length, lo, hi] = {r["ids"]: r for r in rows if r["period"] == "demand"}
        s = samples[200, 0, 200]
        front = samples[1000, 0, 200]
        whole = samples[1000, 0, 1000]
        tail = samples[1000, 200, 1000]
        assert front.keys() == whole.keys() == tail.keys()
        common = s.keys() & whole.keys()
        short_states = observations(paths[0], s, ("up_t",))
        long_states = observations(paths[1], whole, ("up_t", "d0_t", "d3_t"))
        result = dict(
            **context,
            **checks,
            up_groups_short=len(s),
            up_groups_long=len(whole),
            shared_groups=len(common),
            shared_same_gate_time=sum(s[k]["up_t"] == whole[k]["up_t"] for k in common),
            shared_same_member_state=sum(
                short_states[k, "up_t"] == long_states[k, "up_t"] for k in common
            ),
        )
        for prefix, group in (
            ("short200", s),
            ("long_first200", front),
            ("long1000", whole),
            ("long_last800", tail),
        ):
            for seconds in (0, 1, 3):
                result[f"{prefix}_d{seconds}"] = sum(
                    r[f"d{seconds}_t"] is not None for r in group.values()
                )
                result[f"{prefix}_shared_d{seconds}"] = sum(
                    group[k][f"d{seconds}_t"] is not None for k in common
                )
                result[f"{prefix}_exposed{seconds}"] = sum(
                    r["all_down_longest_s"] is not None and r["all_down_longest_s"] >= seconds
                    for r in group.values()
                )
        result["long_new_first_after_200"] = sum(
            whole[k]["d0_t"] is not None and front[k]["d0_t"] is None for k in whole
        )
        result["long_new_3s_after_200"] = sum(
            whole[k]["d3_t"] is not None and front[k]["d3_t"] is None for k in whole
        )
        comparison.append(result)
        for ids in sorted(s.keys() | whole.keys()):
            match = dict(**context, ids=ids)
            if ids in common:
                delta = [
                    max(
                        abs(a[i] - b[i])
                        for a, b in zip(short_states[ids, "up_t"], long_states[ids, "up_t"])
                    )
                    for i in range(4)
                ]
                for name, value in zip(("x_m", "y_m", "speed_m_s", "accel_m_s2"), delta):
                    match["up_member_delta_" + name] = value
            for endpoint in ("d0_t", "d3_t"):
                x = [state[0] - 1000 for state in long_states.get((ids, endpoint), [])]
                match["long_" + endpoint + "_rear_beyond_cut_m"] = round(min(x), 2) if x else None
                match["long_" + endpoint + "_head_beyond_cut_m"] = round(max(x), 2) if x else None
            for prefix, group in (
                ("short200", s),
                ("long_first200", front),
                ("long1000", whole),
                ("long_last800", tail),
            ):
                member = group.get(ids, {})
                for k in (
                    "up_t",
                    "d0_t",
                    "d3_t",
                    "longest_s",
                    "all_down_longest_s",
                    "d0_moves",
                    "d0_lb",
                    "d0_max",
                    "d0_max_lb",
                ):
                    match[prefix + "_" + k] = member.get(k)
            per_id.append(match)
    return summary, groups, comparison, per_id


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--workers", type=int, default=3)
    args = p.parse_args()
    batch = args.batch.resolve()
    seeds = json.loads((batch / "manifest.json").read_bytes())["seeds"]
    jobs = [(batch, road, int(seed)) for road, seed in itertools.product(("3to4", "4to3"), seeds)]
    args.out.mkdir(parents=True, exist_ok=False)
    allrows = [[], [], [], []]
    with ProcessPoolExecutor(args.workers) as pool:
        for result in pool.map(audit_case, jobs):
            for target, rows in zip(allrows, result):
                target.extend(rows)
    for name, rows in zip(("runs", "groups", "pairs", "members"), allrows):
        write_csv(args.out / (name + ".csv"), rows)
    print(len(jobs), "matched physical-length pairs")


if __name__ == "__main__":
    main()
