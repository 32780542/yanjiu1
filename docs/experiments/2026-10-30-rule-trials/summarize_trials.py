"""Publish seed-level and five-seed tables from the independently audited 250 cases."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from statistics import mean

PROFILES = ("base/noa", "base/transform", "TM/noa", "T/transform", "TM/transform")
LABELS = ("原NOA", "原编队", "新NOA", "单前车时距编队", "时距＋补位代价")
METRICS = ("mean_travel_time_s", "mean_system_time_s", "fuel_g_per_km", "mean_entry_wait_s",
           "lane_change_completions", "flag_participation_rate", "flag_mean_participants",
           "flag_peak_participants", "flag_mean_episode_s", "upstream_mean_time_s", "bottleneck_mean_time_s")
COMPARISONS = (("T/transform", "base/transform"), ("TM/transform", "T/transform"),
               ("TM/noa", "base/noa"), ("TM/transform", "TM/noa"), ("TM/transform", "base/transform"))


def average(values):
    return mean(values) if values and all(value is not None for value in values) else None


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    cases = data["cases"]
    expected = {(profile, flow, seed, scenario) for profile in PROFILES
                for flow in (500, 750, 1000, 1250, 1500) for seed in range(11, 16)
                for scenario in ("straight3", "lane_drop")}
    by_key = {(r["candidate"] + "/" + r["mode"], r["flow"], r["seed"], r["scenario"]): r for r in cases}
    assert len(cases) == len(by_key) == 250 and set(by_key) == expected
    args.output.mkdir(parents=True, exist_ok=False)
    grouped, profiles = defaultdict(list), []
    observed = defaultdict(dict)
    for row in data["segment_vehicles"]:
        if row["eligible"] and row["case_eligible"]:
            observed[row["run_dir"], row["segment"]][row["vehicle_id"]] = row["time_s"]
    for key, case in by_key.items():
        grouped[key[0], key[1], key[3]].append(case)
    for (profile, flow, scenario), rows in sorted(grouped.items()):
        valid = all(r["eligible"] for r in rows)
        item = dict(profile=profile, flow=flow, scenario=scenario, seeds=len(rows), eligible=valid)
        item.update({key: average([r.get(key) for r in rows]) if valid else None for key in METRICS})
        profiles.append(item)
    differences = []
    for target, reference in COMPARISONS:
        for flow in (500, 750, 1000, 1250, 1500):
            for scenario in ("straight3", "lane_drop"):
                for seed in range(11, 16):
                    left, right = by_key[target, flow, seed, scenario], by_key[reference, flow, seed, scenario]
                    valid = left["eligible"] and right["eligible"]
                    row = dict(target=target, reference=reference, flow=flow, scenario=scenario, seed=seed,
                               eligible=valid, target_run=left["run_dir"], reference_run=right["run_dir"])
                    row.update({key: left[key] - right[key] if valid and left.get(key) is not None
                                and right.get(key) is not None else None for key in METRICS})
                    for segment in ("upstream", "bottleneck"):
                        a, b = observed[left["run_dir"], segment], observed[right["run_dir"], segment]
                        common = sorted(set(a) & set(b))
                        row[segment + "_mean_time_s"] = average([a[key] - b[key] for key in common]) if valid else None
                        row[segment + "_matched_vehicles"] = len(common)
                    differences.append(row)
    aggregate = []
    groups = defaultdict(list)
    for row in differences:
        groups[row["target"], row["reference"], row["flow"], row["scenario"]].append(row)
    for (target, reference, flow, scenario), rows in sorted(groups.items()):
        valid = len(rows) == 5 and all(r["eligible"] for r in rows)
        item = dict(target=target, reference=reference, flow=flow, scenario=scenario, seeds=len(rows), eligible=valid)
        item.update({key: average([r[key] for r in rows]) if valid else None for key in METRICS})
        item["TT_lower_seeds"] = sum(r["mean_travel_time_s"] < 0 for r in rows) if valid else None
        item["fuel_lower_seeds"] = sum(r["fuel_g_per_km"] < 0 for r in rows) if valid else None
        aggregate.append(item)
    summary = dict(cases=250, eligible=sum(r["eligible"] for r in cases), source_analysis=str(args.analysis.resolve()),
                   profiles=profiles, differences=aggregate,
                   conventions="Five equally weighted seeds. Deltas are target minus reference. Counts are total road participants.")
    for name, rows in (("profiles", profiles), ("seed_differences", differences), ("differences", aggregate)):
        write_csv(args.output / (name + ".csv"), rows)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    table = ["# 五流量独立验证数据表", "", "每个单元为种子11–15的等权平均；时间为秒，燃油为g/km。", ""]
    lookup = {(r["profile"], r["flow"], r["scenario"]): r for r in profiles}
    for scenario in ("lane_drop", "straight3"):
        table += ["## " + ("3→2" if scenario == "lane_drop" else "三道直路"), ""]
        for metric, title, scale in (("mean_travel_time_s", "全程行程时间", 1), ("fuel_g_per_km", "燃油", 1),
                                     ("flag_participation_rate", "0/1参与率（%）", 100),
                                     ("flag_mean_episode_s", "平均连续1时长", 1)):
            table += ["### " + title, "", "| 流量 | " + " | ".join(LABELS) + " |",
                      "| ---: | " + " | ".join(["---:"] * len(PROFILES)) + " |"]
            for flow in (500, 750, 1000, 1250, 1500):
                values = [lookup[profile, flow, scenario][metric] for profile in PROFILES]
                table.append("| " + str(flow) + " | " + " | ".join("—" if v is None else f"{v*scale:.4f}" for v in values) + " |")
            table.append("")
    (args.output / "results_tables.md").write_text("\n".join(table).rstrip() + "\n", encoding="utf-8")
    print(json.dumps(dict(cases=250, eligible=summary["eligible"], profiles=len(profiles), paired_seeds=len(differences))))


if __name__ == "__main__":
    main()
