"""Summarize fresh fixed squads. The 11.24 tag has two shrinking road networks."""
import argparse
import csv
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ROADS = ("3to2", "4to3", "2to3", "3to4")
SEEDS = range(10151, 10155)
COLS = ("model", "road", "n", "spacing", "seed", "span_m", "entry_counts",
        "first_frame_sha256", "tape_sha256", "completed", "whole_both",
        "upstream_whole_hold_s", "downstream_whole_hold_s", "formation_end_counts",
        "formation_actual_total", "formation_bound_total", "formation_actual_max",
        "formation_bound_max", "transform_end_counts", "transform_actual_total",
        "transform_bound_total", "transform_actual_max", "transform_bound_max",
        "collisions", "teleports")


def load_cases(shrink, expand):
    rows = []
    for road, n, density, seed in product(ROADS, (12, 24), ("compact", "long"), SEEDS):
        methods = ("baseline", "candidate") if road in ROADS[:2] else ("candidate",)
        root = shrink if len(methods) == 2 else expand
        case = f"{road}_{n}_{density}_{seed}"
        initial = (root / "tapes" / f"{case}.json").read_bytes()
        pair = []
        for method in methods:
            row = json.loads((root / f"{method}_{case}" / "row.json").read_bytes())
            result = json.loads((root / row["run"] / "result.json").read_bytes())
            assert row["status"] == "drained" and row["completed"] == row["first_frame_n"] == n
            assert row["initial_matches_request"] and row["first_frame_s"] == .1
            assert row["tape_sha256"] == sha256(initial).hexdigest()
            assert (row["collisions"], row["teleports"]) == (0, 0)
            for field, value in result["source_sha256"].items():
                path = root / "frozen" / method / field
                if path.is_file():
                    assert value == sha256(path.read_bytes()).hexdigest()
            if row["whole_both"]:
                assert row["formation_actual_chain_ok"] and row["transform_actual_chain_ok"]
                assert row["same_ids_peak"] == n
            pair.append(row)
        if len(pair) == 2:
            for key in ("first_frame_sha256", "request_sha256"):
                assert pair[0][key] == pair[1][key]
        rows.extend(pair)
    tag = subprocess.check_output(["git", "show", "11.24版:variants/phase5g_pure_formation/noa/native_rules.py"], cwd=ROOT)
    clean = lambda b: b.replace(b"\r\n", b"\n")
    assert clean(tag) == clean((shrink / "frozen/baseline/noa/native_rules.py").read_bytes())
    for root in (shrink, expand):
        for path in (root / "frozen/candidate/noa").glob("*.py"):
            assert clean(path.read_bytes()) == clean((ROOT / "variants/phase5g_pure_formation/noa" / path.name).read_bytes())
    return rows


def both_min(row, stage):
    return (row[stage + "_actual_total"] == row[stage + "_bound_total"] and
            row[stage + "_actual_max"] == row[stage + "_bound_max"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shrink", type=Path)
    parser.add_argument("expand", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = load_cases(args.shrink, args.expand)
    with args.output.open("w", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    for method, road in product(("baseline", "candidate"), ROADS):
        group = [r for r in rows if r["model"] == method and r["road"] == road]
        if not group:
            continue
        formed = [r for r in group if r["whole_both"]]
        hold10 = sum(min(r["upstream_whole_hold_s"], r["downstream_whole_hold_s"]) >= 10 for r in formed)
        counts = [sum(both_min(r, stage) for r in formed) for stage in ("formation", "transform")]
        print(method, road, len(group), len(formed), hold10, *counts, sum(r["completed"] for r in group))


if __name__ == "__main__":
    main()
