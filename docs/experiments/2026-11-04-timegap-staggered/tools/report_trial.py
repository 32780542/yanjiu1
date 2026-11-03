"""Consume the existing sealed-case evaluator and report within-preview pairs."""
import argparse
from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path
from statistics import mean
import sys

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "docs/experiments/2026-11-03-staggered-bottleneck/tools"))
import summarize
import seal_case

METRICS = ("mean_system_time_s", "mean_travel_time_s", "mean_entry_wait_s", "fuel_g_per_km")


def reuse_report(path):
    """Reuse the already-consumed immutable A rows, including their raw observations."""
    def decode(value):
        if not value:
            return None
        if value in ("True", "False"):
            return value == "True"
        try:
            return json.loads(value)
        except ValueError:
            return value
    with (path / "per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = [{key: decode(value) for key, value in row.items()} for row in csv.DictReader(stream)]
    for row in rows:
        row["_run"] = {**row, "case_dir": row["run_dir"]}
        row["evidence_reused_from"] = str(path)
    return rows


def cross_pairs(cases, mappings):
    _, traffic = seal_case.tools()
    index = summarize.unique(cases)
    pairs = []
    for target, reference in (mapping.split("=", 1) for mapping in mappings):
        for case in cases:
            if case["candidate"] != target or case["mode"] != "transform":
                continue
            for mode in ("noa", "transform"):
                other = index.get((reference, case["flow"], case["seed"], case["scenario"], mode))
                a, b = other.get("_run") if other else None, case["_run"]
                pair = traffic.pair(a, b, target + "-minus-" + reference + "_" + mode,
                                    "same_following_complete_strategy" if mode == "noa" else "shape_mechanism_comparison")
                pair.update(candidate=target, reference_candidate=reference, reference_mode=mode, mode="transform")
                for metric in (*traffic.METRICS, *("flag_" + key for key in seal_case.tools()[0].FLAGS)):
                    pair["reference_" + metric] = a.get(metric) if a else None
                    pair["candidate_" + metric] = b.get(metric)
                    pair["delta_" + metric] = traffic.existing._difference(a, b, metric, pair["pair_eligible"])
                pairs.append(pair)
    return pairs


def stop_and_merge(run):
    """Describe raw physical samples; these criteria do not change eligibility."""
    stopped, slow = set(), set()
    stop_samples = slow_samples = 0
    minimum = None
    with gzip.open(Path(run) / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            for key, (x, y, speed, _) in json.loads(line)["states"].items():
                if 900 <= x < 1000 and abs(y - 8.25) <= .15:
                    minimum = speed if minimum is None else min(minimum, speed)
                    if speed < 1:
                        slow.add(key)
                        slow_samples += 1
                    if speed < .1:
                        stopped.add(key)
                        stop_samples += 1
    trips = seal_case.read(Path(run) / "trips.json")
    positions = [event["x"] for trip in trips for event in trip.get("lane_completion_events", [])
                 if event["from_lane"] == 2 and event["to_lane"] == 1]
    return dict(stop_vehicles=len(stopped), stop_sample_vehicle_s=.1 * stop_samples,
                slow_vehicles=len(slow), slow_sample_vehicle_s=.1 * slow_samples,
                ending_lane_min_speed_mps=minimum, merge_2to1_completions=len(positions),
                merge_2to1_mean_x_m=mean(positions) if positions else None,
                merge_2to1_min_x_m=min(positions) if positions else None,
                merge_2to1_max_x_m=max(positions) if positions else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reuse-report", type=Path)
    parser.add_argument("--compare", nargs="+", help="explicit target=reference candidates, e.g. B200=A200")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = summarize.protocol_records(args.batch)
    cases = []
    for record in records:
        case = summarize.load_case(record)
        if case.get("run_dir"):
            case.update(stop_and_merge(case["run_dir"]))
        cases.append(case)
        print(json.dumps(dict(consumed=len(cases), planned=len(records), candidate=case["candidate"],
                              flow=case["flow"], seed=case["seed"], mode=case["mode"])), flush=True)
    if args.reuse_report:
        cases.extend(reuse_report(args.reuse_report))
    pairs = cross_pairs(cases, args.compare) if args.compare else [
        pair for name in sorted({case["candidate"] for case in cases})
        for pair in summarize.build_pairs([case for case in cases if case["candidate"] == name], name)]
    _, traffic = seal_case.tools()
    traffic.write_rows(args.output / "per_case.csv", [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases])
    traffic.write_rows(args.output / "paired_seeds.csv", pairs)
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair["candidate"], pair["flow"], pair["comparison"]].append(pair)
    rows = []
    for (candidate, flow, comparison), group in sorted(groups.items()):
        item = dict(candidate=candidate, flow=flow, comparison=comparison, seeds=len(group), eligible=all(p["pair_eligible"] for p in group))
        for metric in METRICS:
            for prefix in ("reference_", "candidate_", "delta_"):
                values = [p.get(prefix + metric) for p in group]
                item[prefix + metric] = mean(values) if item["eligible"] and all(v is not None for v in values) else None
        rows.append(item)
    traffic.write_rows(args.output / "flow_means.csv", rows)
    bad = [c for c in cases if not c.get("safe") or not c.get("all_completed") or not c.get("protocol_verified")
           or not c.get("evidence_verified") or c.get("returncode") != 0 or c.get("status") != "drained"]
    seal_case.write(args.output / "summary.json", dict(case_count=len(cases), eligible_pairs=sum(p["pair_eligible"] for p in pairs),
        failed_cases=[{k: c.get(k) for k in ("candidate", "flow", "seed", "mode", "status", "safe", "all_completed", "completed", "requested",
                                             "returncode", "seal_status", "error", "protocol_issues")} for c in bad],
        means=rows, pair_definition="transform minus explicitly named reference NOA/transform" if args.compare else "transform minus same-source NOA",
        reference_report_reused=str(args.reuse_report) if args.reuse_report else None,
        raw_observation="x in [900,1000), |y-8.25|<=.15 m; stop v<.1, slow v<1 m/s; sampled .1-s exposure; actual 2->1 completion events"))
    return 0 if all(c.get("protocol_verified") and c.get("evidence_verified") for c in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
