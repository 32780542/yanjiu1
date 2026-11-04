"""Read the existing report CSVs and write a Markdown table of matched contrasts."""

import argparse
import csv
from pathlib import Path
from statistics import mean


TIMING = (
    ("Δ系统 s", "mean_system_time_s"),
    ("Δ路内 s", "mean_travel_time_s"),
    ("Δ入口 s", "mean_entry_wait_s"),
    ("Δ油耗 g/km", "fuel_g_per_km"),
)
MECHANISM = (
    ("Δ区域均速 m/s", "region_mean_speed_mps"),
    ("Δ末道停车车辆", "stop_vehicles"),
    ("Δ末道停车车辆秒", "stop_sample_vehicle_s"),
    ("Δ2→1完成位置 m", "merge_2to1_mean_x_m"),
    ("Δ状态1占比 pp", "flag_participation_rate"),
    ("平均连续1 s，基准→目标", "flag_mean_episode_s"),
)


def index(path, sides):
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = tuple(f"{row[candidate]}/{row[mode]}" for candidate, mode in sides)
            key += (row["scenario"], float(row["flow"]), int(row["seed"]))
            if key in rows:
                raise ValueError(f"Duplicate row in {path}: {key}")
            rows[key] = row
    return rows


def case_state(row):
    if row is None:
        return "缺逐工况行"
    if row["status"] != "drained" or row["safe"] != "True" or row["all_completed"] != "True":
        return (f"{row['status']}，安全 {row['safe']}，完成 {row['completed']}/{row['requested']}，"
                f"碰撞 {row['collisions']}，传送 {row['teleports']}")
    return ""


def collect(cases, pairs, contrast, scenario, flow, seeds):
    target, reference = contrast.split("=")
    members, missing = [], []
    for seed in seeds:
        match = (scenario, flow, seed)
        a, b = cases.get((target, *match)), cases.get((reference, *match))
        pair = pairs.get((target, reference, *match))
        issues = [f"{side} {state}" for side, row in ((target, a), (reference, b))
                  if (state := case_state(row))]
        if pair is None:
            issues.append("缺配对行")
        elif pair["pair_eligible"] != "True":
            issues.append(f"配对未通过 {pair['rejection_reasons']}")
        if issues:
            missing.append(f"- `{target} − {reference}`，{flow:g}，seed {seed}。" + "。".join(issues) + "。")
        else:
            members.append((a, b))
    return members, missing


def numbers(members, metric):
    return [float(a[metric]) - float(b[metric]) for a, b in members if a[metric] and b[metric]]


def cell(values, denominator, pattern):
    if not values:
        return "—"
    display = format(mean(values), pattern)
    return display if len(values) == denominator else f"{display} ({len(values)}/{denominator})"


def value(members, metric):
    if metric == "flag_mean_episode_s":
        sides = [[float(pair[side][metric]) for pair in members if pair[side][metric]] for side in (1, 0)]
        return " → ".join(cell(values, len(members), ".2f") for values in sides) if members else "—"
    values = numbers(members, metric)
    if metric == "flag_participation_rate":
        values = [delta * 100 for delta in values]
    return cell(values, len(members), "+.4f" if metric in dict(TIMING).values() else "+.2f")


def table(lines, heading, metrics, groups, seeds, timing=False):
    columns = ["目标 − 基准", "流量", "合格/计划"] + [label for label, _ in metrics]
    if timing:
        columns.append("系统缩短/有值")
    lines.extend(["", f"## {heading}", "", "| " + " | ".join(columns) + " |",
                  "| " + " | ".join(["---"] + ["---:"] * (len(columns) - 1)) + " |"])
    for contrast, flow, members in groups:
        row = [f"`{contrast.replace('=', ' − ')}`", f"{flow:g}", f"{len(members)}/{len(seeds)}"]
        row.extend(value(members, metric) for _, metric in metrics)
        if timing:
            changes = numbers(members, "mean_system_time_s")
            row.append(f"{sum(change < 0 for change in changes)}/{len(changes)}" if changes else "—")
        lines.append("| " + " | ".join(row) + " |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Directory with per_case.csv and paired_seeds.csv")
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="公共预警距离配对汇总")
    parser.add_argument("--scenario", default="lane_drop")
    parser.add_argument("--flows", type=float, nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--compare", nargs="+", required=True, metavar="TARGET/MODE=REFERENCE/MODE")
    args = parser.parse_args()

    cases = index(args.report / "per_case.csv", [("candidate", "mode")])
    pairs = index(args.report / "paired_seeds.csv", [("candidate", "mode"), ("reference_candidate", "reference_mode")])
    groups, missing = [], []
    for contrast in args.compare:
        for flow in args.flows:
            members, issues = collect(cases, pairs, contrast, args.scenario, flow, args.seeds)
            groups.append((contrast, flow, members))
            missing.extend(issues)

    seeds = "、".join(map(str, args.seeds))
    eligible = sum(len(members) for _, _, members in groups)
    total = len(groups) * len(args.seeds)
    lines = [f"# {args.title}", "",
             f"场景 `{args.scenario}`，seed {seeds}，流量单位为辆/h/道。{eligible}/{total} 个计划配对合格。",
             f"数据取自 `{args.report.as_posix()}` 的 `per_case.csv` 和 `paired_seeds.csv`。",
             "", "同场景、流量、seed 匹配，差值为目标减基准，再逐 seed 等权平均。"
             "括号表示该指标实际有值数/合格配对数，`—` 表示无值。"]
    table(lines, "系统时间与油耗", TIMING, groups, args.seeds, timing=True)
    table(lines, "瓶颈过程与直接 0/1 状态", MECHANISM, groups, args.seeds)
    lines.extend(["", "区域均速使用 800–1000 m、100–600 s 的固定窗。末道停车在全工况采样，"
                  "范围为 x∈[900,1000) m、距车道2中心 ≤0.15 m、v<0.1 m/s。"
                  "2→1位置使用实际换道完成点，包含早期换道。0/1占比为状态1车辆时间比例，"
                  "连续1时长为逐车 episode 均值。"])
    if missing:
        lines.extend(["", "## 缺配与未合格配对", "", *missing])
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
