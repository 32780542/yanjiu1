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


def read_report_rows(path):
    def decode(value):
        if not value:
            return None
        if value in ("True", "False"):
            return value == "True"
        try:
            return json.loads(value)
        except ValueError:
            return value
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [{key: decode(value) for key, value in row.items()} for row in csv.DictReader(stream)]


def reuse_report(path):
    """Reuse the already-consumed immutable A rows, including their raw observations."""
    rows = read_report_rows(path / "per_case.csv")
    for row in rows:
        row["_run"] = {**row, "case_dir": row["run_dir"]}
        row["evidence_reused_from"] = str(path)
    return rows


def road_effect(pairs, drop_report, output, straight_aliases=None):
    """DID consumes existing within-road pairs; it does not reevaluate old cases."""
    _, traffic = seal_case.tools()
    drop_source = read_report_rows(drop_report / "paired_seeds.csv") if drop_report else pairs
    drop = {(p["candidate"], p["mode"], p["reference_mode"], p["flow"], p["seed"]): p
            for p in drop_source if p["scenario"] == "lane_drop"}
    aliases = dict(value.split("=", 1) for value in (straight_aliases or []))
    straight_pairs = [pair for pair in pairs if pair["scenario"] == "straight3"]
    requested = [(pair, pair["candidate"]) for pair in straight_pairs]
    requested.extend((pair, candidate) for pair in straight_pairs for candidate, source in aliases.items()
                     if pair["candidate"] == source and candidate != source)
    rows = []
    for straight, candidate in requested:
        key = (candidate, straight["mode"], straight["reference_mode"],
               straight["flow"], straight["seed"])
        lane_drop = drop.get(key)
        valid = bool(lane_drop and lane_drop["pair_eligible"] and straight["pair_eligible"])
        row = dict(candidate=key[0], mode=key[1], reference_mode=key[2], flow=key[3], seed=key[4],
                   comparison=lane_drop["comparison"] if lane_drop else straight["comparison"], eligible=valid,
                   straight_target_candidate=straight["candidate"], straight_comparison=straight["comparison"],
                   drop_reference_candidate=lane_drop.get("reference_candidate") if lane_drop else None,
                   straight_reference_candidate=straight.get("reference_candidate"))
        for metric in METRICS:
            a, b = lane_drop.get("delta_" + metric) if lane_drop else None, straight.get("delta_" + metric)
            row["drop_delta_" + metric], row["straight_delta_" + metric] = a, b
            row["did_" + metric] = a - b if valid and a is not None and b is not None else None
        rows.append(row)
    traffic.write_rows(output / "road_did_seeds.csv", rows)
    means = []
    identities = sorted({(row["candidate"], row["mode"], row["reference_mode"], row["flow"]) for row in rows})
    for candidate, mode, reference_mode, flow in identities:
        members = [row for row in rows if (row["candidate"], row["mode"], row["reference_mode"], row["flow"])
                   == (candidate, mode, reference_mode, flow)]
        row = dict(candidate=candidate, mode=mode, reference_mode=reference_mode, flow=flow,
                   comparison=members[0]["comparison"], seeds=len(members), eligible=all(r["eligible"] for r in members))
        for prefix in ("drop_delta_", "straight_delta_", "did_"):
            for metric in METRICS:
                values = [r[prefix + metric] for r in members]
                row[prefix + metric] = mean(values) if row["eligible"] and all(v is not None for v in values) else None
        denominator = row["drop_delta_mean_system_time_s"]
        row["straight_share_of_drop_system_gain"] = row["straight_delta_mean_system_time_s"] / denominator if denominator else None
        means.append(row)
    traffic.write_rows(output / "road_did_means.csv", means)
    seal_case.write(output / "road_did_summary.json", dict(eligible_seeds=sum(r["eligible"] for r in rows), means=means,
        drop_report_reused=str(drop_report) if drop_report else None,
        formula="DID=(target mode-reference mode)_drop-(target mode-reference mode)_straight; within seed, equal seed means",
        reference_identity="Per-seed reference candidates recorded in road_did_seeds.csv; common NOA definitions confirmed before execution",
        straight_aliases=aliases,
        scope="Matching candidate or explicitly named straight alias, target/reference mode, flow and seed; no automatic candidate alias",
        share_definition="ratio of equal-seed mean straight system delta to mean drop system delta; not mean per-seed percentages"))


def cross_pairs(cases, mappings):
    _, traffic = seal_case.tools()
    index = summarize.unique(cases)
    pairs = []
    for target_specification, specification in (mapping.split("=", 1) for mapping in mappings):
        target, target_separator, target_mode = target_specification.partition("/")
        target_mode = target_mode if target_separator else "transform"
        reference, separator, reference_mode = specification.partition("/")
        for case in cases:
            if case["candidate"] != target or case["mode"] != target_mode:
                continue
            for mode in ((reference_mode,) if separator else ("noa", "transform")):
                other = index.get((reference, case["flow"], case["seed"], case["scenario"], mode))
                a, b = other.get("_run") if other else None, case["_run"]
                pair = traffic.pair(a, b, target + "/" + target_mode + "=" + reference + "/" + mode,
                                    "explicit_same_input_mode_contrast" if target == reference else "explicit_same_input_rule_contrast")
                pair.update(candidate=target, reference_candidate=reference, reference_mode=mode, mode=target_mode)
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
    completion_counts = [len(trip.get("lane_completion_events", [])) for trip in trips]
    positions = [event["x"] for trip in trips for event in trip.get("lane_completion_events", [])
                 if event["from_lane"] == 2 and event["to_lane"] == 1]
    return dict(stop_vehicles=len(stopped), stop_sample_vehicle_s=.1 * stop_samples,
                slow_vehicles=len(slow), slow_sample_vehicle_s=.1 * slow_samples,
                ending_lane_min_speed_mps=minimum, merge_2to1_completions=len(positions),
                max_lane_completions_per_vehicle=max(completion_counts, default=0),
                vehicles_more_than_two_lane_completions=sum(count > 2 for count in completion_counts),
                merge_2to1_mean_x_m=mean(positions) if positions else None,
                merge_2to1_min_x_m=min(positions) if positions else None,
                merge_2to1_max_x_m=max(positions) if positions else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reuse-report", type=Path)
    parser.add_argument("--compare", nargs="+", help="explicit TARGET/MODE=REFERENCE/MODE; omitted target mode defaults to transform")
    parser.add_argument("--road-drop-report", type=Path, help="already-consumed drop pairs for a straight-road DID")
    parser.add_argument("--road-straight-alias", nargs="+", help="explicit DROP_CANDIDATE=STRAIGHT_CANDIDATE, e.g. C8_300=C8_200")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = [record for batch in args.batch for record in summarize.protocol_records(batch)]
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
        groups[pair["candidate"], pair["mode"], pair["flow"], pair["scenario"], pair["comparison"]].append(pair)
    rows = []
    for (candidate, mode, flow, scenario, comparison), group in sorted(groups.items()):
        item = dict(candidate=candidate, mode=mode, flow=flow, scenario=scenario, comparison=comparison,
                    reference_candidate=group[0].get("reference_candidate"), reference_mode=group[0].get("reference_mode"),
                    seeds=len(group), eligible=all(p["pair_eligible"] for p in group))
        for metric in METRICS:
            for prefix in ("reference_", "candidate_", "delta_"):
                values = [p.get(prefix + metric) for p in group]
                item[prefix + metric] = mean(values) if item["eligible"] and all(v is not None for v in values) else None
        rows.append(item)
    traffic.write_rows(args.output / "flow_means.csv", rows)
    if args.road_drop_report or {pair["scenario"] for pair in pairs} >= {"lane_drop", "straight3"}:
        road_effect(pairs, args.road_drop_report, args.output, args.road_straight_alias)
    bad = [c for c in cases if not c.get("safe") or not c.get("all_completed") or not c.get("protocol_verified")
           or not c.get("evidence_verified") or c.get("returncode") != 0 or c.get("status") != "drained"]
    seal_case.write(args.output / "summary.json", dict(batches=[str(batch) for batch in args.batch],
        case_count=len(cases), eligible_pairs=sum(p["pair_eligible"] for p in pairs),
        failed_cases=[{k: c.get(k) for k in ("candidate", "flow", "seed", "mode", "status", "safe", "all_completed", "completed", "requested",
                                             "returncode", "seal_status", "error", "protocol_issues")} for c in bad],
        means=rows, pair_definition="Explicit target/mode minus reference/mode; scenario and target mode grouped separately" if args.compare else "transform minus same-source NOA",
        reference_report_reused=str(args.reuse_report) if args.reuse_report else None,
        raw_observation="x in [900,1000), |y-8.25|<=.15 m; stop v<.1, slow v<1 m/s; sampled .1-s exposure; actual 2->1 completion events"))
    return 0 if all(c.get("protocol_verified") and c.get("evidence_verified") for c in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
