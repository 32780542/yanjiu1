"""Run shared IDM type sensitivity on independent frozen native sources."""

import argparse
import hashlib
import itertools
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = next(path for path in Path(__file__).resolve().parents if (path / "scripts/run_logged.py").is_file())
SOURCE = ROOT / "variants/phase5g_pure_formation"
NATIVE = "experiments/native_sumo.py"
FILES = (
    NATIVE, "experiments/global_reference.py", "experiments/complete_layers.py",
    "noa/native_rules.py", "run_native_flow.py", "research/common.py",
    "configs/tools.json", "experiments/__init__.py", "noa/__init__.py",
    "research/__init__.py",
)
ORIGINAL = {"minGap": "1.5", "tau": "0.2", "accel": "5.0"}
PROFILES = {
    "transfer": {"minGap": "2.0", "tau": "0.65", "accel": "3.0"},
    "control": ORIGINAL,
    "tau_only": {**ORIGINAL, "tau": "0.65"},
}


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def freeze(batch, source):
    originals = {name: (source / name).read_bytes() for name in FILES}
    hashes = {}
    for label, expected in PROFILES.items():
        frozen = batch / "src" / label
        (frozen / "tmp").mkdir(parents=True)
        hashes[label] = {}
        for name, raw in originals.items():
            if name == NATIVE:
                for key, original in ORIGINAL.items():
                    old = f"    {key}={original},".encode()
                    new = f"    {key}={expected[key]},".encode()
                    assert raw.count(old) == 1, (name, old)
                    raw = raw.replace(old, new, 1)
            file = frozen / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
            hashes[label][name] = digest(raw)
    assert hashes["control"] == {name: digest(raw) for name, raw in originals.items()}
    return hashes


def execute(batch, task, hashes):
    profile, flow, seed, mode = (task[k] for k in ("profile", "flow", "seed", "mode"))
    ident = f"{profile}_{flow}_{seed}_{mode}"
    folder = batch / "case" / ident
    folder.mkdir(parents=True)
    cli = batch / "src" / profile / "run_native_flow.py"
    command = [sys.executable, "-B", str(ROOT / "scripts/run_logged.py"),
               "--label", "n18-phys-" + ident, "--timeout", "1800", "--",
               sys.executable, "-X", "utf8", "-B", str(cli),
               "--flow", str(flow), "--seed", str(seed), "--scenario", "lane_drop",
               "--mode", mode, "--duration", "600", "--max-time", "1200",
               "--output-base", str(folder)]
    with (folder / "worker.log").open("wb") as log:
        worker = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    task.update(worker_exit=worker.returncode, worker_log=str(folder / "worker.log"))
    results = list(folder.glob("*/result.json"))
    if len(results) != 1:
        return {**task, "verified": False, "error": f"found {len(results)} result files"}
    run = results[0].parent
    task["run"] = str(run)
    result = read_json(results[0])
    task.update({name: result.get(name) for name in (
        "status", "safe", "all_completed", "requested", "completed", "collisions", "teleports",
        "mean_system_time_s", "mean_entry_wait_s", "mean_travel_time_s", "fuel_g_per_km",
        "lane_changes", "lane_change_completions", "ending_lane_completion_before_drop_rate",
        "execution", "action_reasons", "formation_state", "actual_end_s", "error",
    )})
    try:
        inp = read_json(run / "input.json")
        recorded = inp["source_sha256"]
        assert result["source_sha256"] == recorded
        assert recorded and all(expected == hashes[name] == digest((run / "source" / name).read_bytes())
                                for name, expected in recorded.items())
        assert all(float(inp["physical"][key]) == float(val) for key, val in PROFILES[profile].items())
        vehicle_type = ET.parse(run / "native.rou.xml").getroot().find("vType")
        assert vehicle_type is not None
        assert vehicle_type.attrib == {"id": "CAV_ICV", **{k: str(v) for k, v in inp["physical"].items()}}
        assert {(name, inp["case"][name]) for name in ("seed", "mode", "scenario", "flow_veh_h_lane",
                                                     "demand_duration_s", "max_time_s")} == {
            ("seed", seed), ("mode", mode), ("scenario", "lane_drop"), ("flow_veh_h_lane", flow),
            ("demand_duration_s", 600), ("max_time_s", 1200),
        }
        assert inp["speed_mode"] == 31 and inp["lane_change_mode"] == 512
        task["physical"] = inp["physical"]
        task["demand_sha256"] = digest(json.dumps(inp["arrivals"], sort_keys=True).encode())
        task["verified"] = all((run / name).stat().st_size > 0 for name in (
            "positions.jsonl.gz", "events.jsonl.gz", "trips.json", "sumo_tripinfo.xml"))
    except (AssertionError, KeyError, OSError, ET.ParseError) as error:
        task.update(verified=False, verification_error=f"{type(error).__name__}: {error}")
    return task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jobs", type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument("--profiles", nargs="+", choices=tuple(PROFILES), default=["transfer"])
    parser.add_argument("--flows", nargs="+", type=int, choices=(1500, 1750, 2000), default=[1500, 1750, 2000])
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args()
    batch = args.output.resolve()
    assert batch.parent == ROOT / "tmp/staggered_bottleneck" and not batch.exists()
    assert len(set(args.flows)) == len(args.flows) and len(set(args.profiles)) == len(args.profiles)
    batch.mkdir()
    hashes = freeze(batch, args.source.resolve())
    (batch / "run.py").write_bytes(Path(__file__).read_bytes())
    tasks = [dict(profile=profile, flow=flow, seed=seed, mode=mode)
             for flow, profile, seed, mode in itertools.product(args.flows, args.profiles, (211, 212),
                                                               ("noa", "transform"))]
    write_json(batch / "protocol.json", dict(tasks=tasks, hashes=hashes, jobs=args.jobs,
                                            frozen_from=str(args.source.resolve())))
    print(json.dumps(dict(batch=str(batch), planned=len(tasks))), flush=True)
    rows = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(execute, batch, task.copy(), hashes[task["profile"]]) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            write_json(batch / "manifest.json", rows)
            print(json.dumps({k: row.get(k) for k in ("profile", "flow", "seed", "mode", "status",
                  "safe", "all_completed", "worker_exit", "verified", "error")}), flush=True)
    demand_tapes = {}
    for row in rows:
        demand_tapes.setdefault((row["flow"], row["seed"]), set()).add(row.get("demand_sha256"))
    return int(not (all(len(hashes) == 1 and None not in hashes for hashes in demand_tapes.values())
                    and all(row["verified"] and row["safe"] and row["all_completed"]
                            and row["worker_exit"] == 0 for row in rows)))


if __name__ == "__main__":
    raise SystemExit(main())
