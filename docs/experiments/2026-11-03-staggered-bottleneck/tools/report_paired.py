"""Summarize verified paired cases with equal seed weights and unchanged metrics."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean

import seal_case
import summarize

METRICS = ("mean_travel_time_s", "mean_system_time_s", "mean_entry_wait_s", "fuel_g_per_km",
           "mean_segment_100_600_s", "mean_segment_640_1100_s", "region_density_veh_km_lane",
           "region_mean_speed_mps", "region_low_speed_vehicle_s", "flow_1000m_veh_h",
           "lane_change_completions", "flag_participation_rate", "flag_mean_participants",
           "flag_peak_participants", "flag_mean_episode_s")


def average(values):
    return mean(values) if values and all(value is not None for value in values) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", nargs="+", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--baseline", default="TM")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    records = [row for batch in args.batch for row in summarize.protocol_records(batch)]
    summarize.unique(records)
    cases = [summarize.load_case(row) for row in records]
    index = summarize.unique(cases)
    _, traffic = seal_case.tools()
    pairs = []
    for case in cases:
        if case["mode"] != "transform" or case["candidate"] == args.baseline:
            continue
        main_target = case["candidate"] == args.target
        reference = index.get((args.baseline if main_target else args.target,
                               case["flow"], case["seed"], case["scenario"],
                               "noa" if main_target else "transform"))
        a, b = reference.get("_run") if reference else None, case["_run"]
        pair = traffic.pair(a, b, case["candidate"] + ("-NOA" if main_target else "-" + args.target),
                            "same_following_complete_strategy" if main_target else "formation_mechanism_ablation")
        pair.update(candidate=case["candidate"], reference=args.baseline + "/noa" if main_target else args.target,
                    flow=case["flow"], seed=case["seed"], scenario=case["scenario"])
        valid = pair["pair_eligible"]
        for metric in METRICS:
            pair["reference_" + metric] = a.get(metric) if a else None
            pair["target_" + metric] = b.get(metric)
            pair["delta_" + metric] = traffic.existing._difference(a, b, metric, valid)
        pair["system_improvement_percent"] = (
            -100 * pair["delta_mean_system_time_s"] / a["mean_system_time_s"] if valid else None)
        pairs.append(pair)
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair["candidate"], pair["reference"], pair["flow"], pair["scenario"]].append(pair)
    averages = []
    for (candidate, reference, flow, scenario), rows in sorted(groups.items()):
        valid = all(row["pair_eligible"] for row in rows)
        item = dict(candidate=candidate, reference=reference, flow=flow, scenario=scenario,
                    seeds=len(rows), eligible=valid,
                    improved_seeds=sum(row["system_improvement_percent"] > 0 for row in rows) if valid else None)
        for metric in METRICS:
            for prefix in ("reference_", "target_", "delta_"):
                item[prefix + metric] = average([row[prefix + metric] for row in rows]) if valid else None
        item["system_improvement_percent"] = (
            -100 * item["delta_mean_system_time_s"] / item["reference_mean_system_time_s"] if valid else None)
        averages.append(item)
    args.output.mkdir(parents=True, exist_ok=False)
    traffic.write_rows(args.output / "per_case.csv", [{k: v for k, v in row.items() if not k.startswith("_")}
                                                       for row in cases])
    traffic.write_rows(args.output / "paired_seeds.csv", pairs)
    traffic.write_rows(args.output / "flow_means.csv", averages)
    summary = dict(case_count=len(cases), protocol_verified=sum(row["protocol_verified"] for row in cases),
                   evidence_verified=sum(row["evidence_verified"] for row in cases),
                   drained=sum(row.get("all_completed") is True for row in cases),
                   safe=sum(row.get("safe") is True for row in cases), pair_count=len(pairs),
                   eligible_pairs=sum(row["pair_eligible"] for row in pairs), means=averages,
                   batches=[str(path.resolve()) for path in args.batch],
                   conventions="Equal seed weights. Deltas target minus reference. Improvement is minus delta / reference mean; no missing metric imputation.")
    seal_case.write(args.output / "summary.json", summary)
    lines = ["# 配对结果表", "", "同流量、同道路、同输入种子配对；以下为种子等权均值。", "",
             "| 比较 | 每道流量 | 道路 | 系统时间参考/候选(s) | 改善(%) | 改善种子 | 燃油差(g/km) | 瓶颈段差(s) | 低速差(车辆秒) |",
             "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    def show(value):
        return "—" if value is None else f"{value:.4f}"
    for row in averages:
        lines.append("| " + " | ".join((row["candidate"] + "−" + row["reference"], str(row["flow"]), row["scenario"],
            show(row["reference_mean_system_time_s"]) + "/" + show(row["target_mean_system_time_s"]),
            show(row["system_improvement_percent"]), str(row["improved_seeds"]) + "/" + str(row["seeds"]),
            show(row["delta_fuel_g_per_km"]), show(row["delta_mean_segment_640_1100_s"]),
            show(row["delta_region_low_speed_vehicle_s"]))) + " |")
    (args.output / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("means", "batches", "conventions")}))
    return 0 if len(cases) == summary["protocol_verified"] == summary["evidence_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
