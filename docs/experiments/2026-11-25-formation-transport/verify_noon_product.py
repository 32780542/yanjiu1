"""Verify that the cleaned-up product reproduces the frozen receiving algorithm."""
import csv
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TMP = ROOT / "tmp"


def load(path):
    return json.loads(path.read_bytes())


def digest(folder):
    with gzip.open(folder / "positions.jsonl.gz", "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compare(case, a, b):
    before, after = (load(p/"result.json") for p in (a,b))
    assert all(r["status"] == "drained" and r["completed"] == r["requested"]
               and not r["collisions"] and not r["teleports"] for r in (before,after))
    x, y = digest(a), digest(b)
    return dict(case=case, completed=after["completed"], identical_positions=x==y,
                frozen_sha256=x, product_sha256=y, original=a.relative_to(ROOT), product=b.relative_to(ROOT))


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum", action="store_true", help="Check the exact minimum-reuse product")
    parser.add_argument("--policies", action="store_true", help="Compare both policies over all completed pairs")
    args = parser.parse_args()
    rows = []
    if args.policies:
        fixed = (("hold-first","reuse-first"),("hold-last","reuse-last"))
        traffic = ("noon_hold_1200","noon_minimum_1200")
        output = "noon_reuse_policy_trajectories.csv"
    elif args.minimum:
        fixed = (("reuse-first","product-minimum-replay"),)
        traffic = ("noon_minimum_1200","noon_minimum_product_replay")
        output = "noon_exact_product_equivalence.csv"
    else:
        fixed = (("hold-matched","product-replay"),)
        traffic = ("noon_hold_1200","noon_product_replay_1200")
        output = "noon_product_equivalence.csv"
    for pair in fixed:
        base, replay = (TMP / ("nov25-noon-" + label) for label in pair)
        for path in sorted(replay.glob("candidate_*/row.json")):
            old, new = load(base/path.parent.name/"row.json"), load(path)
            assert old["first_frame_sha256"] == new["first_frame_sha256"] and old["tape_sha256"] == new["tape_sha256"]
            rows.append(compare(path.parent.name, base/old["run"], replay/new["run"]))
    print("fixed cohorts", len(rows))
    flow = TMP/"nov25study"
    for path in sorted((flow/traffic[1]).glob("*/row.json")):
        a, b = load(flow/traffic[0]/path.parent.name/"row.json"), load(path)
        assert a["completed"] == b["completed"]
        rows.append(compare(path.parent.name, ROOT/a["run_dir"], ROOT/b["run_dir"]))
    if rows:
        with (HERE/output).open("w",encoding="utf8",newline="") as out:
            w=csv.DictWriter(out,list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(len(rows), "runs;", sum(r["identical_positions"] for r in rows), "exact trajectory matches")
    assert rows and (args.policies or all(r["identical_positions"] for r in rows))


if __name__ == "__main__":
    main()
