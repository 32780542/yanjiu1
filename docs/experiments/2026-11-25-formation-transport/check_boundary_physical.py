"""Rebuild upstream ID sets and verify the first downstream crossing cost from actual lateral positions."""

from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict, Counter
import argparse, csv, gzip, io, json, math, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


def shape(data, L):
    D = 5.5 + 0.85 * sum(v[2] for v in data.values()) / len(data)
    if max(v[2] for v in data.values()) - min(v[2] for v in data.values()) > 0.5:
        return False
    cols = [[] for _ in range(L)]
    for x, y, *_ in data.values():
        lane = int(round(y / 3.3 - 0.5))
        if lane < 0 or lane >= L or abs((lane + 0.5) * 3.3 - y) > 0.3:
            return False
        cols[lane].append(x)
    if any(len(col) * L != len(data) for col in cols):
        return False
    for phase in range(2) if L == 2 else [0]:
        orig = []
        for j, col in enumerate(cols):
            for row, x in enumerate(sorted(col, reverse=True)):
                orig.append(x + (row + 0.5 * ((phase + j) % 2)) * D)
        if max(orig) - min(orig) <= 2:
            return True
    return False


def check(job):
    path, expected = job
    root = ET.parse(path / "native.net.xml")
    a = root.findall("./edge[@id='upstream']/lane")
    b = root.findall("./edge[@id='downstream']/lane")
    K, L = len(a), len(b)
    cut = float(a[0].get("length"))
    end = cut + float(b[0].get("length"))
    gate = cut - 200
    N = math.lcm(K, L)
    prev = {}
    used = set()
    done = []
    active = []
    nmatch = 0
    expected = {frozenset(v["ids"].split()): v for v in expected}
    with gzip.open(path / "positions.jsonl.gz", "rt") as f:
        for fr in map(json.loads, f):
            states = fr["states"]
            t = fr["time_s"]
            new = [k for k in states.keys() & prev.keys() if prev[k][0] < gate <= states[k][0]]
            new.sort(key=lambda k: ((gate - prev[k][0]) / (states[k][0] - prev[k][0]), -prev[k][0]))
            for k in new:
                hi = prev[k][0]
                behind = sorted([v[0] for v in prev.values() if v[0] <= hi], reverse=True)
                if len(behind) < N:
                    continue
                lo = behind[N - 1]
                obs = {i: v for i, v in prev.items() if lo <= v[0] <= hi}
                ids = frozenset(obs)
                if len(obs) != N or ids & used or not shape(obs, K):
                    continue
                used.update(ids)
                done.append(ids)
                r = expected[ids]
                assert abs(float(r["up_t"]) - (t - 0.1)) < 1.0e-6
                active.append([ids, Counter(), None])
            active = [g for g in active if not g[0] - states.keys()]
            for g in list(active):
                ids, cnt, _ = g
                for k in ids:
                    cnt[k] += abs(round(states[k][1] / 3.3 - 0.5) - round(prev[k][1] / 3.3 - 0.5))
                obs = {k: states[k] for k in ids}
                lo = min(v[0] for v in obs.values())
                hi = max(v[0] for v in obs.values())
                if (
                    lo < cut
                    or hi >= end
                    or any(lo <= v[0] <= hi for k, v in states.items() if k not in ids)
                ):
                    continue
                if shape(obs, L):
                    r = expected[ids]
                    assert float(r["d0_t"]) == t
                    assert (sum(cnt.values()), max(cnt.values())) == (
                        int(r["d0_moves"]),
                        int(r["d0_max"]),
                    )
                    active.remove(g)
                    nmatch += 1
            prev = states
    assert set(done) == set(expected)
    assert nmatch == sum(bool(r["d0_t"]) for r in expected.values())
    return len(done), nmatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", action="append", required=True, metavar="MODEL=DIR")
    parser.add_argument(
        "--evidence", type=Path, default=Path(__file__).with_name("boundary_evidence.zip")
    )
    parser.add_argument("--roads", nargs="+", default=["3to2", "4to3"])
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    def key(row):
        return (
            row["model"],
            row["road"],
            float(row["demand_s"]),
            int(row["seed"]),
            float(row["flow"]),
        )

    groups = defaultdict(list)
    with zipfile.ZipFile(args.evidence) as archive:
        with archive.open("groups.csv") as inp:
            for row in csv.DictReader(io.TextIOWrapper(inp, encoding="utf-8")):
                groups[key(row)].append(row)
        with archive.open("runs.csv") as inp:
            runs = {key(row): row for row in csv.DictReader(io.TextIOWrapper(inp, encoding="utf-8"))}
    jobs = []
    for item in args.batch:
        label, dirname = item.split("=", 1)
        for trace in sorted(Path(dirname).glob("*/*/positions.jsonl.gz")):
            road = trace.parent.parent.name.split("_")[0]
            if road not in args.roads:
                continue
            cfg = json.loads((trace.parent / "input.json").read_bytes())["case"]
            k = (label, road, cfg["demand_duration_s"], cfg["seed"], cfg["flow_veh_h_lane"])
            if k not in runs:
                raise ValueError(f"Missing case in evidence: {k}")
            res = json.loads((trace.parent / "result.json").read_bytes())
            assert res["source_sha256"]["noa/native_rules.py"] == runs[k]["rules_sha"]
            assert res["source_sha256"].get("noa/staggered.py", "") == runs[k]["staggered_sha"]
            jobs.append((trace.parent, groups[k]))
    if not jobs:
        raise ValueError("No physical traces")
    with ProcessPoolExecutor(args.workers) as pool:
        result = list(pool.map(check, jobs))
    print(
        len(jobs),
        "runs,",
        sum(x[0] for x in result),
        "disjoint groups,",
        sum(x[1] for x in result),
        "first downstream endpoints and crossing costs independently verified",
    )


if __name__ == "__main__":
    main()
