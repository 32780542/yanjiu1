"""Run paired frozen SUMO cases and seal each before optional bounded raw cleanup.

Unqualified candidate names use the pinned TM rules. NAME=rules.py replaces only
native_rules.py. Outputs must be new directories below tmp/staggered_bottleneck.
Unsafe, incomplete and archive-failed cases remain in the manifest.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback

import seal_case

REPO = Path(__file__).resolve().parents[4]
SAFE_ROOT = REPO / "tmp/staggered_bottleneck"
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
VARIANT = "variants/phase5g_pure_formation/"
FILES = ("experiments/native_sumo.py", "experiments/global_reference.py",
         "experiments/complete_layers.py", "noa/native_rules.py", "run_native_flow.py",
         "research/common.py", "configs/tools.json", "experiments/__init__.py",
         "noa/__init__.py", "research/__init__.py")
write = seal_case.write


def case_name(name, flow, seed, scenario, mode):
    return f"{name}_{flow:g}_{seed}_{scenario}_{mode}"


def validate_output(path):
    path = Path(path).resolve()
    if path.exists() or not path.is_relative_to(SAFE_ROOT.resolve()) or path == SAFE_ROOT.resolve():
        raise ValueError("output must be a new directory below " + str(SAFE_ROOT))
    return path


def freeze(destination, rules=None):
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in FILES:
        raw = (Path(rules).read_bytes() if rules and name == "noa/native_rules.py" else
               subprocess.check_output(["git", "show", BASE + ":" + VARIANT + name], cwd=REPO))
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    (destination / "tmp").mkdir()
    write(destination / "freeze.json", {"base_commit": BASE, "sha256": hashes})
    return hashes


def run_one(task):
    source, output = Path(task["source"]), Path(task["output"])
    output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-X", "utf8", "-B", str(source / "run_native_flow.py"),
               "--flow", str(task["flow"]), "--seed", str(task["seed"]),
               "--duration", str(task["duration"]), "--max-time", str(task["max_time"]),
               "--scenario", task["scenario"], "--mode", task["mode"], "--output-base", str(output)]
    wrapper = [sys.executable, "-B", str(REPO / "scripts/run_logged.py"), "--label",
               "staggered-case-" + hashlib.sha256(str(output).encode()).hexdigest()[:10],
               "--timeout", str(task["worker_timeout"]), "--", *command]
    row = {key: task[key] for key in ("candidate", "stage", "flow", "seed", "scenario", "mode")}
    row.update(base_commit=BASE, case_output=str(output), worker_log=str(output / "worker.log"))
    try:
        with (output / "worker.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(wrapper, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        row["returncode"] = completed.returncode
        try:
            row["operation"] = json.loads((output / "worker.log").read_text(encoding="utf-8").splitlines()[-1])
        except (ValueError, IndexError):
            row["operation"] = None
        result_paths = list(output.glob("*/result.json"))
        row["run_dir"] = str(result_paths[0].parent) if len(result_paths) == 1 else None
        row["status"] = "worker_failed"
        if row["run_dir"]:
            result = seal_case.read(result_paths[0])
            row.update({key: result.get(key) for key in ("status", "safe", "all_completed", "requested", "completed",
                "collisions", "teleports", "error", "mean_travel_time_s", "fuel_g_per_km")})
            try:
                row.update(seal_case.seal(row.copy(), Path(task["batch"]), task["prune_raw"]))
            except Exception as error:
                row.update(seal_status="failed_raw_retained", seal_error=f"{type(error).__name__}: {error}")
                (output / "seal_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        else:
            row.update(seal_status="not_available_raw_retained")
    except Exception as error:
        row.update(returncode=1, status="worker_exception", seal_status="not_available_raw_retained",
                   error=f"{type(error).__name__}: {error}")
        (output / "worker_error.log").write_text(traceback.format_exc(), encoding="utf-8")
    write(output / "case_record.json", row)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", nargs="+", required=True, help="TM or NAME=rules.py")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--flows", type=float, nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--scenarios", nargs="+", choices=("straight3", "lane_drop"), default=["straight3", "lane_drop"])
    parser.add_argument("--modes", nargs="+", choices=("noa", "transform", "formation"), default=["noa", "transform"])
    parser.add_argument("--duration", type=float, default=600.)
    parser.add_argument("--max-time", type=float, default=900.)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--worker-timeout", type=float, default=600.)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prune-raw", action="store_true")
    args = parser.parse_args()
    try:
        batch = validate_output(args.output)
        if (not 1 <= args.jobs <= 8 or not 0 < args.worker_timeout <= 7200
                or not all(math.isfinite(x) and x > 0 for x in (*args.flows, args.duration, args.max_time))
                or args.max_time < args.duration):
            raise ValueError("require positive finite flow/duration, max-time >= duration, jobs 1..8, timeout 0..7200")
        candidates = []
        for item in args.candidate:
            name, sep, location = item.partition("=")
            if not name or not all(c.isalnum() or c == "_" for c in name) or sep and not location:
                raise ValueError("invalid candidate: " + item)
            candidates.append((name, Path(location).resolve() if sep else None))
        if len({name for name, _ in candidates}) != len(candidates):
            raise ValueError("duplicate candidate names")
        if any(len(set(values)) != len(values) for values in (args.flows, args.seeds, args.scenarios, args.modes)):
            raise ValueError("duplicate case dimensions")
        outputs = [os.path.normcase(str(batch / "cases" / case_name(name, flow, seed, scenario, mode)))
                   for name, _ in candidates for flow in args.flows for seed in args.seeds
                   for scenario in args.scenarios for mode in args.modes]
        if len(outputs) != len(set(outputs)):
            raise ValueError("case output names collide after flow formatting; use distinct case paths/flows")
    except ValueError as error:
        parser.error(str(error))
    batch.mkdir(parents=True, exist_ok=False)
    (batch / ".staggered-runner-owned").write_text(str(batch), encoding="utf-8")
    sources, tasks = {}, []
    for filename in ("runner.py", "seal_case.py"):
        (batch / filename).write_bytes(Path(__file__).with_name(filename).read_bytes())
    for name, rules in candidates:
        source = batch / "sources" / name
        sources[name] = freeze(source, rules)
        for flow in args.flows:
            for seed in args.seeds:
                for scenario in args.scenarios:
                    for mode in args.modes:
                        tasks.append(dict(candidate=name, stage=args.stage, flow=flow, seed=seed, scenario=scenario,
                            mode=mode, source=str(source), duration=args.duration, max_time=args.max_time,
                            worker_timeout=args.worker_timeout, prune_raw=args.prune_raw, batch=str(batch),
                            output=str(batch / "cases" / case_name(name, flow, seed, scenario, mode))))
    arguments = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    write(batch / "protocol.json", dict(arguments=arguments, base_commit=BASE, sources=sources, tasks=tasks,
          fixed_traffic_window_s=[100, 600], region_m=[800, 1000], region_lanes=3,
          metric_policy="Unchanged published evaluator; incomplete fixed windows/segments remain ineligible.",
          driver_sha256=seal_case.sha(__file__), seal_tool_sha256=seal_case.sha(Path(seal_case.__file__))))
    print(json.dumps(dict(batch=str(batch), cases=len(tasks))), flush=True)
    rows = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_one, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            write(batch / "manifest.json", rows)
            print(json.dumps(dict(finished=len(rows), total=len(tasks), **row)), flush=True)
    rows.sort(key=lambda row: (row["candidate"], row["flow"], row["seed"], row["scenario"], row["mode"]))
    write(batch / "manifest.json", rows)
    return 0 if all(row["returncode"] == 0 and row["status"] == "drained" and row.get("safe") is True
                    and row.get("all_completed") is True and row["seal_status"] == "verified" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
