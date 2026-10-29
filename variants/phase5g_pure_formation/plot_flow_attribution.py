"""Plot the verified, five-seed tables without reopening raw trajectories."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_table(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="Portable study directory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="D baseline")
    args = parser.parse_args()
    traffic_path = args.data / "tables/traffic_and_attribution.csv"
    quality_path = args.data / "tables/formation_quality.csv"
    traffic, quality = read_table(traffic_path), read_table(quality_path)
    flows = sorted({float(row["flow_veh_h_lane"]) for row in traffic})
    lookup = {(float(row["flow_veh_h_lane"]), row["mode"]): row for row in traffic}
    formed = {(float(row["flow_veh_h_lane"]), row["mode"]): row for row in quality}
    plt.rcParams.update({"font.family": "Microsoft YaHei", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none"})
    figure, axes = plt.subplots(2, 2, figsize=(11, 7.3), layout="constrained")
    labels = {"noa": "纯 NOA", "formation": "形成＋普通合流", "transform": "形成＋编队变换"}
    colors = {"noa": "#3C5488", "formation": "#00A087", "transform": "#E64B35"}
    for mode in labels:
        for axis, field in ((axes[0, 0], "drop_TT_s"), (axes[1, 1], "drop_fuel_g_km")):
            axis.plot(flows, [float(lookup[flow, mode][field]) for flow in flows],
                      "o-", color=colors[mode], label=labels[mode])
    reductions = [float(lookup[flow, "transform"]["main_NOA_minus_transform_reduction_s"])
                  for flow in flows]
    axes[0, 1].bar([str(int(flow)) for flow in flows], reductions, color=colors["transform"], width=.6)
    axes[0, 1].axhline(0, color="#555555", linewidth=.8)
    for index, value in enumerate(reductions):
        axes[0, 1].annotate(f"{value:+.3f}", (index, value), xytext=(0, -14 if value < 0 else 5),
                            textcoords="offset points", ha="center", fontsize=9)
    axes[0, 1].margins(y=.25)
    for region, label, style in (("upstream", "上游三道", "o--"), ("downstream", "下游两道", "s-")):
        values = [100 * float(formed[flow, "transform"][f"{region}_formation_participation_rate_mean"])
                  for flow in flows]
        axes[1, 0].plot(flows, values, style, label=label, color=colors["transform"])
    titles = (("(a) 3→2 道路平均行程时间", "行程时间 / s"),
              ("(b) 主要瓶颈段附加时间的减少量", "NOA 附加时间 − 编队附加时间 / s"),
              ("(c) 编队变换方案的完整多层参与率", "形成车辆时间 / 全体车辆时间 / %"),
              ("(d) 3→2 道路单位里程燃油", "SUMO 燃油估计 / (g/km)"))
    for axis, (title, ylabel) in zip(axes.flat, titles):
        axis.set(title=title, xlabel="请求流量 / [辆/(h·车道)]", ylabel=ylabel)
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)
    for axis in (axes[0, 0], axes[1, 0], axes[1, 1]):
        axis.legend(frameon=False, fontsize=9)
        axis.set_xticks(flows)
    figure.suptitle(f"{args.label}：600 s 随机来车，5 个配对种子等权均值\n"
                   "瓶颈段 640–1100 m；附加时间＝3→2 道路 − 三道直路；正值表示疏解收益", fontsize=11)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    outputs = [args.output.with_suffix(suffix) for suffix in (".png", ".svg")]
    for path in outputs:
        figure.savefig(path, dpi=300)
    plt.close(figure)
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    args.output.with_suffix(".json").write_text(json.dumps({
        "label": args.label, "aggregation": "Five paired seeds, equal run weight",
        "input_sha256": {str(path): digest(path) for path in (traffic_path, quality_path)},
        "source_sha256": digest(Path(__file__)),
        "output_sha256": {path.name: digest(path) for path in outputs},
        "dpi": 300,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outputs": [str(path) for path in outputs]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
