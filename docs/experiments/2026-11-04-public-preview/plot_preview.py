"""Draw the paired C12 warning-distance experiment from the consumed case table."""
import csv
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
DISTANCES = (300, 500, 600)
FLOWS = (1500, 1750, 2000)
SEEDS = {211, 212, 213, 214, 215}

with (ROOT / "data/distance_confirmation/per_case.csv").open(encoding="utf-8-sig") as stream:
    cases = list(csv.DictReader(stream))

plt.rcParams.update({"font.family": "Microsoft YaHei", "svg.fonttype": "path",
                     "axes.unicode_minus": False, "font.size": 10})
fig, axes = plt.subplots(2, 3, figsize=(10, 6), sharex=True, layout="constrained")
metrics = (("mean_system_time_s", "平均系统时间 (s/车)"),
           ("fuel_g_per_km", "燃油 (g/km)"))
for column, flow in enumerate(FLOWS):
    axes[0, column].set_title(f"{flow} 辆/h/道")
    for row, (metric, units) in enumerate(metrics):
        ax = axes[row, column]
        for mode, label, color in (("noa", "反应式 NOA", "#6B6B6B"),
                                   ("transform", "C12 编队变换", "#27768E")):
            averages = []
            for distance in DISTANCES:
                group = [c for c in cases if c["candidate"] == f"C12_{distance}"
                         and c["mode"] == mode and float(c["flow"]) == flow
                         and c["scenario"] == "lane_drop"]
                assert len(group) == len(SEEDS) and {int(c["seed"]) for c in group} == SEEDS
                assert all(c["performance_comparison_eligible"] == "True" for c in group)
                values = [float(c[metric]) for c in group]
                averages.append(mean(values))
                ax.scatter([distance] * len(values), values, s=13, color=color, alpha=.26)
            ax.plot(DISTANCES, averages, color=color, marker="o", label=label)
        ax.set_xticks(DISTANCES)
        ax.grid(axis="y", alpha=.24)
        ax.spines[["top", "right"]].set_visible(False)
        if column == 0:
            ax.set_ylabel(units)
        if row == 1:
            ax.set_xlabel("公共预警距离 (m)")
axes[0, 0].legend(frameon=False)
fig.savefig(ROOT / "preview_comparison.png", dpi=300)
svg = ROOT / "preview_comparison.svg"
fig.savefig(svg)
svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
               encoding="utf-8")
