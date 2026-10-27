"""核验随机车流实验并从物理轨迹复算、导出汇总表。"""

import argparse
import csv
import hashlib
import gzip
import json
from pathlib import Path
from statistics import median

from experiments.formation_metrics import evaluate_run
from experiments.phase5_detection import _physical_components, _physical_rows
from experiments.formation_study import write_json


def aggregate(rows):
    groups = {}
    for row in rows:
        key = (row["kind"], row["lane_count"], row["flow_veh_h_lane"],
               row["target_speed_mps"], row["same_lane_gap_m"])
        groups.setdefault(key, []).append(row)
    output = []
    for key, group in sorted(groups.items()):
        delays = [row["formation_delay_s"] for row in group if row["formation_success"]]
        geometries = [row["max_geometry_error_m"] for row in group
                      if row["max_geometry_error_m"] is not None]
        output.append(dict(kind=key[0], lane_count=key[1], flow_veh_h_lane=key[2],
            target_speed_mps=key[3], same_lane_gap_m=key[4], attempts=len(group),
            formed=len(delays), formation_rate_pct=100*len(delays)/len(group),
            median_delay_s=median(delays) if delays else None,
            min_delay_s=min(delays) if delays else None,
            max_delay_s=max(delays) if delays else None,
            median_final_geometry_error_m=median(geometries) if geometries else None,
            geometry_evaluable_runs=len(geometries),
            median_final_speed_spread_mps=median(row["speed_spread_mps"] for row in group),
            median_final_target_speed_error_mps=median(row["max_target_speed_error_mps"] for row in group),
            collision_pairs=sum(row["collision_pairs"] for row in group)))
    return output


def export_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False)
                             if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})


def summarize(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    original = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    original_rows = {row["name"]: row for row in original["results"]}
    if len(original_rows) != len(protocol["cases"]):
        raise ValueError("结果数量与预定协议不一致")
    rows, checked, corrected, failures = [], 0, 0, []
    for case in protocol["cases"]:
        directory = root / case["name"]
        hashes = json.loads((directory / "hashes.json").read_text(encoding="utf-8"))
        for name, expected in hashes.items():
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"文件摘要不符：{case['name']}/{name}")
            checked += 1
        result = evaluate_run(directory)
        old = original_rows[case["name"]]
        for key in ("formation_success", "formation_delay_s", "recording_valid", "safety_passed",
                    "collision_pairs", "lane_counts", "max_target_speed_error_mps"):
            if result[key] != old[key]:
                raise ValueError(f"物理指标复算不符：{case['name']}/{key}")
        corrected += result["max_geometry_error_m"] != old["max_geometry_error_m"]
        rows.append(result)
        if not result["formation_success"]:
            with gzip.open(directory / "trajectory.jsonl.gz", "rt", encoding="utf-8") as stream:
                final = None
                for line in stream:
                    final = json.loads(line)
            physical = _physical_rows(final["states"], 3.3, case["lane_count"])
            components = _physical_components(physical, 50.)
            xs = sorted(row["x_m"] for row in physical.values())
            failures.append(dict(name=case["name"], lane_counts=result["lane_counts"],
                component_sizes=[len(group) for group in components],
                largest_longitudinal_gap_m=max(b-a for a, b in zip(xs, xs[1:])),
                final_states=final["states"], failure_reasons=result["failure_reasons"]))
        print(f"verified {len(rows)}/{len(protocol['cases'])}: {case['name']}", flush=True)
    output.mkdir(parents=True, exist_ok=False)
    groups = aggregate(rows)
    write_json(output / "results.json", rows)
    write_json(output / "protocol.json", protocol)
    write_json(output / "aggregates.json", groups)
    write_json(output / "unformed_cases.json", failures)
    export_csv(output / "cases.csv", rows)
    export_csv(output / "groups.csv", groups)
    write_json(output / "verification.json", dict(cases=len(rows), files_checked=checked,
        physical_metrics_recomputed=len(rows), missing_geometry_corrected_cases=corrected,
        source_directory=str(root), evaluation_sha256=hashlib.sha256(
            (Path(__file__).parent / "experiments/formation_metrics.py").read_bytes()).hexdigest()))
    flow_groups = {(r["lane_count"], r["flow_veh_h_lane"]): r for r in groups if r["kind"] == "lane_flow"}
    write_json(output / "formation_rate_figure.json", dict(
        matrix=[[flow_groups[(lanes, flow)]["formation_rate_pct"]
                 for flow in (252, 756, 1512)] for lanes in (2, 3, 4)],
        row_labels=["2 车道", "3 车道", "4 车道"],
        col_labels=["252", "756", "1512"], cbar_label="整队形成率（%）"))
    lines = ["| 车道 | 每车道需求（辆/h） | 目标速度（m/s） | 同车道层距（m） | 形成 | 形成延迟中位数 [范围]（s） | 终态几何误差中位数（m） | 几何可评价数 | 终态速差中位数（m/s） | 终态目标速度偏差中位数（m/s） |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    def number(value):
        return "—" if value is None else f"{value:.2f}"
    for row in groups:
        delay = ("—" if row["median_delay_s"] is None else
                 f"{row['median_delay_s']:.1f} [{row['min_delay_s']:.1f}, {row['max_delay_s']:.1f}]")
        lines.append(f"| {row['lane_count']} | {row['flow_veh_h_lane']} | {row['target_speed_mps']:g} | {row['same_lane_gap_m']:g} | {row['formed']}/{row['attempts']} | {delay} | {number(row['median_final_geometry_error_m'])} | {row['geometry_evaluable_runs']}/5 | {number(row['median_final_speed_spread_mps'])} | {number(row['median_final_target_speed_error_mps'])} |")
    (output / "tables.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "cases": len(rows), "files_verified": checked,
                      "missing_geometry_corrected": corrected}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summarize(args.root, args.output)
