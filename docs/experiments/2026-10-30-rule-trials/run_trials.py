"""Freeze small source sets and run paired real SUMO cases without editing production."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
VARIANT = "variants/phase5g_pure_formation/"
BASE = "8ed11d90ac457269b2175e20aec5ba1bbba8a318"
FILES = (
    "experiments/native_sumo.py", "experiments/global_reference.py",
    "experiments/complete_layers.py", "noa/native_rules.py", "run_native_flow.py",
    "research/common.py", "configs/tools.json",
    "experiments/__init__.py", "noa/__init__.py", "research/__init__.py",
)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def freeze(destination, rules=None):
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in FILES:
        raw = (rules.read_bytes() if rules and name == "noa/native_rules.py" else
               subprocess.check_output(["git", "show", BASE + ":" + VARIANT + name], cwd=REPO))
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    (destination / "tmp").mkdir()
    write(destination / "freeze.json", dict(base_commit=BASE, sha256=hashes))
    return hashes


def run_one(task):
    source, output = Path(task["source"]), Path(task["output"])
    output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-X", "utf8", "-B", str(source / "run_native_flow.py"),
               "--flow", str(task["flow"]), "--seed", str(task["seed"]),
               "--duration", str(task["duration"]), "--max-time", str(task["max_time"]),
               "--scenario", task["scenario"], "--mode", task["mode"],
               "--output-base", str(output)]
    with (output / "worker.log").open("w", encoding="utf-8") as log:
        try:
            completed = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT,
                                       timeout=600, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            returncode = 124
    result_paths = list(output.glob("*/result.json"))
    row = {k: task[k] for k in ("candidate", "stage", "flow", "seed", "scenario", "mode")}
    row.update(returncode=returncode, run_dir=str(result_paths[0].parent) if len(result_paths) == 1 else None,
               worker_log=str(output / "worker.log"))
    if row["run_dir"]:
        result = json.loads(result_paths[0].read_text(encoding="utf-8"))
        row.update({key: result.get(key) for key in (
            "status", "requested", "completed", "mean_travel_time_s", "fuel_g_per_km")})
    else:
        row["status"] = "worker_failed"
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", nargs="+", required=True, help="base or NAME=rules.py")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--flows", type=float, nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--duration", type=float, default=600.)
    parser.add_argument("--max-time", type=float, default=900.)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--all-modes", action="store_true", help="also run unchanged NOA for M/R")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    batch = REPO / "tmp/literature_trials/batches" / (stamp + "_" + args.stage)
    batch.mkdir(parents=True, exist_ok=False)
    tasks, sources = [], {}
    for item in args.candidate:
        name, _, location = item.partition("=")
        assert name and all(c.isalnum() or c == "_" for c in name)
        source = batch / "sources" / name
        sources[name] = freeze(source, Path(location).resolve() if location else None)
        modes = ("noa", "transform") if name in ("base", "T") or args.all_modes else ("transform",)
        for flow in args.flows:
            for seed in args.seeds:
                for scenario in ("straight3", "lane_drop"):
                    for mode in modes:
                        tasks.append(dict(candidate=name, stage=args.stage, flow=flow, seed=seed,
                                          scenario=scenario, mode=mode, source=str(source),
                                          duration=args.duration, max_time=args.max_time,
                                          output=str(batch / "cases" / f"{name}_{flow:g}_{seed}_{scenario}_{mode}")))
    write(batch / "protocol.json", dict(arguments=vars(args), base_commit=BASE, sources=sources, tasks=tasks))
    rows = []
    print(json.dumps(dict(batch=str(batch), cases=len(tasks))), flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_one, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            write(batch / "manifest.json", rows)
            print(json.dumps(dict(finished=len(rows), total=len(tasks), **row)), flush=True)
    rows.sort(key=lambda r: (r["candidate"], r["flow"], r["seed"], r["scenario"], r["mode"]))
    write(batch / "manifest.json", rows)
    return 0 if all(r["returncode"] == 0 and r["status"] == "drained" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
