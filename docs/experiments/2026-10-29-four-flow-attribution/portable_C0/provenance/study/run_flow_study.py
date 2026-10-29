"""Cooperative merge-only ablation: 20 lane-drop cases, four process jobs."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from experiments.native_sumo import ROOT, _source_snapshot, run_case, write_json


def read_record(path):
    result = json.loads((path / "result.json").read_text(encoding="utf-8"))
    record = dict(
        flow=result["flow_veh_h_lane"],
        seed=result["seed"],
        scenario=result["scenario"],
        mode=result["mode"],
        run_dir=str(path),
        **{
            key: result.get(key)
            for key in (
                "status",
                "requested",
                "completed",
                "mean_travel_time_s",
                "collisions",
                "teleports",
                "safe",
                "all_completed",
            )
        },
    )
    return record, result["source_sha256"]


def run_task(task):
    parameters, source = task
    path = run_case(**parameters)
    record, actual_source = read_record(path)
    if actual_source != source:
        raise RuntimeError(f"Case source differs from frozen study: {path}")
    result = json.loads((path / "result.json").read_text(encoding="utf-8"))
    if not result.get("safe") or not result.get("all_completed"):
        raise RuntimeError(f"Unsafe or incomplete cooperative case retained: {path}")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flows", type=float, nargs="+", default=[500, 750, 1000, 1500])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--output-base", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--equivalence-report", type=Path, default=ROOT / "straight_equivalence_report.json")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    equivalent = json.loads(args.equivalence_report.read_text(encoding="utf-8"))["reuse_H_noa_straight"]
    roads = [("lane_drop", ("cooperative",))]
    if not equivalent:
        roads.append(("straight3", ("cooperative",)))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = (args.output_base or ROOT / "results/flow_attribution") / stamp
    base.mkdir(parents=True, exist_ok=False)
    wrapper = Path(__file__).read_bytes()
    (base / "run_flow_study.py").write_bytes(wrapper)
    source = _source_snapshot(base)
    protocol = dict(
        flows=args.flows,
        seeds=args.seeds,
        duration_s=args.duration,
        max_time_s=args.duration + 300,
        source_sha256=source,
        wrapper_sha256=hashlib.sha256(wrapper).hexdigest(),
        jobs=args.jobs,
        case_order="seed, flow, lane_drop:cooperative; optional straight3:cooperative if actual short equivalence failed",
        case_count=len(roads) * len(args.flows) * len(args.seeds),
        cases_per_seed_flow="lane_drop:cooperative" if equivalent else "lane_drop:cooperative;straight3:cooperative",
        policy="cooperative_merge_only",
        group_following=False,
        layer_fill=False,
        straight_delegation="complete current NOA decision",
        reuse_H_noa_straight=equivalent,
        equivalence_report=str(args.equivalence_report.resolve()),
    )
    write_json(base / "protocol.json", protocol)
    tasks = [
        (
            dict(
                mode=mode,
                seed=seed,
                flow=flow,
                duration=args.duration,
                max_time=args.duration + 300,
                scenario=road,
                output_base=base / f"flow_{flow:g}",
            ),
            source,
        )
        for seed in args.seeds
        for flow in args.flows
        for road, modes in roads
        for mode in modes
    ]
    records = []

    def save_records():
        write_json(base / "run_status.json", records)
        for rate in args.flows:
            write_json(
                base / f"flow_{rate:g}_manifest.json",
                dict(cases=[r["run_dir"] for r in records if r["flow"] == rate]),
            )
        write_json(base / "manifest.json", dict(cases=[r["run_dir"] for r in records]))

    save_records()
    try:
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            for record in executor.map(run_task, tasks):
                records.append(record)
                save_records()
                print(json.dumps(record), flush=True)
    except BaseException as error:
        write_json(base / "study_failure.json", dict(type=type(error).__name__, message=str(error)))
        # run_case preserves a failed result before re-raising; retain it too.
        known = {record["run_dir"] for record in records}
        for result in base.glob("flow_*/*/result.json"):
            if str(result.parent) not in known:
                records.append(read_record(result.parent)[0])
        order = {
            (p["flow"], p["seed"], p["scenario"], p["mode"]): i for i, (p, _) in enumerate(tasks)
        }
        records.sort(key=lambda r: order[(r["flow"], r["seed"], r["scenario"], r["mode"])])
        save_records()
        raise
    print(json.dumps(dict(study_dir=str(base), cases=len(records))), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
