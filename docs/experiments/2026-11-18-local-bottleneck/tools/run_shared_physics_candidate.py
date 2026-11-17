"""Test an exact rule variant under the frozen transferred IDM physics."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

from run_shared_physics import ROOT, digest, execute, freeze, read_json, write_json


RUNS = ROOT / "tmp/staggered_bottleneck"
TRANSFER = RUNS / "n18_phys_r01"
RULES = "noa/native_rules.py"


def remove_cascade(source):
    lines = source.splitlines(keepends=True)
    start, = (i for i, line in enumerate(lines) if b"cascade = (known and ego.lane == 0" in line)
    assert b"ending.lane == 2" in lines[start + 1] and b"_clear(ending" in lines[start + 2]
    modified = b"".join(lines[:start] + lines[start + 3:])
    assert modified.count(b"direct or cascade or observed") == 1
    return modified.replace(b"direct or cascade or observed", b"direct or observed", 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--flows", nargs="+", type=int, choices=(1500, 1750, 2000), default=[2000, 1750])
    parser.add_argument("--seeds", nargs="+", type=int, default=[211, 212])
    parser.add_argument("--mode", choices=("noa", "transform"), default="transform")
    parser.add_argument("--profile", choices=("transfer", "tau_only"), default="transfer")
    parser.add_argument("--jobs", type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument("--rules", type=Path, help="An exact candidate file. Default removes the lane-0 speculative cue.")
    args = parser.parse_args()
    batch = args.output.resolve()
    assert batch.parent == RUNS and not batch.exists()
    assert all(len(set(values)) == len(values) for values in (args.flows, args.seeds))
    batch.mkdir()
    hashes = freeze(batch, TRANSFER / "src/control")[args.profile]
    assert hashes == read_json(TRANSFER / "protocol.json")["hashes"][args.profile]
    rules = batch / "src" / args.profile / RULES
    source = rules.read_bytes()
    modified = args.rules.read_bytes() if args.rules else remove_cascade(source)
    assert modified != source
    compile(modified, str(rules), "exec")
    rules.write_bytes(modified)
    hashes[RULES] = digest(modified)
    tasks = [dict(profile=args.profile, flow=flow, seed=seed, mode=args.mode)
             for flow in args.flows for seed in args.seeds]
    (batch / "run.py").write_bytes(Path(__file__).read_bytes())
    write_json(batch / "protocol.json", dict(tasks=tasks, hashes=hashes, jobs=args.jobs,
                                            treatment=str(args.rules.resolve()) if args.rules else
                                            "Remove speculative lane-0 cascade only"))
    rows = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(execute, batch, task.copy(), hashes) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            write_json(batch / "manifest.json", rows)
            print(json.dumps({k: row.get(k) for k in ("flow", "seed", "status", "safe", "all_completed",
                  "verified", "mean_system_time_s", "mean_entry_wait_s", "error")}), flush=True)
    return int(not all(r["worker_exit"] == 0 and r["verified"] and r["safe"] and r["all_completed"] for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
