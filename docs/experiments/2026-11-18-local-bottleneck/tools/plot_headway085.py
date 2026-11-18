"""读取逐种子和汇总 CSV，输出两张 300 dpi PNG 和对应的矢量 SVG。"""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

METHODS = ("hdv", "noa", "transform")
LABELS = ("普通车", "纯 NOA", "交错编队")
COLORS = ("#AB6236", "#355E8B", "#087D69")
MARKERS = ("s", "o", "D")
FLOWS = np.array([1500, 1750, 2000])


def read_table(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def axes_style(ax, title, unit):
    ax.set_title(title, loc="left", fontweight="bold", pad=9)
    ax.set_ylabel(unit)
    ax.set_xticks(FLOWS)
    ax.set_xlim(1440, 2060)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#D9DFE3", linewidth=.65)
    ax.spines[["right", "top"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#8D989F")
    ax.tick_params(length=3, color="#8D989F")


def plot_methods(ax, summary, cases, limit, key):
    for i, method in enumerate(METHODS):
        selected = [r for r in summary if float(r["road_limit"]) == limit and r["method"] == method]
        means = [float(r[key]) for r in selected]
        offset = (i - 1) * 12
        for x, flow in zip(FLOWS, selected):
            values = [float(r[key]) for r in cases if (r["road_limit"], r["flow"], r["method"])
                      == (flow["road_limit"], flow["flow"], method)]
            ax.vlines(x + offset, min(values), max(values), color=COLORS[i], alpha=.55, lw=1.6)
        ax.plot(FLOWS + offset, means, marker=MARKERS[i], color=COLORS[i], linewidth=1.9,
                markersize=6.5, markeredgecolor="white", markeredgewidth=.6, label=LABELS[i])


def finish(fig, name, folder, caption):
    handles, labels = fig.axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(.5, .998))
    fig.supxlabel("入口需求（辆 / 小时 / 车道）", y=.065, fontsize=10)
    fig.text(.5, .018, caption, ha="center", color="#47565D", fontsize=9)
    fig.subplots_adjust(left=.09, bottom=.16, right=.98, top=.89, wspace=.28, hspace=.43)
    for ext in ("png", "svg"):
        fig.savefig(folder / f"{name}.{ext}", dpi=300, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    folder = parser.parse_args().folder
    summary, cases = (read_table(folder / name) for name in ("summary.csv", "cases.csv"))
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    font = next(f for f in ("Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "PingFang SC") if f in fonts)
    plt.rcParams.update({"font.family": font, "font.size": 10, "axes.unicode_minus": False,
                         "axes.titlecolor": "#182C37", "axes.titlesize": 11, "svg.fonttype": "path"})
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 6.6), sharey="row")
    for j, limit in enumerate((33.3, 28.8)):
        ax = axes[0, j]
        axes_style(ax, f"({'ab'[j]})   路段限速 {limit} m/s", "平均路内行程（秒/车）")
        plot_methods(ax, summary, cases, limit, "mean_s")
        ax = axes[1, j]
        axes_style(ax, f"({'cd'[j]})   同批车辆采用编队后节省的时间", "纯 NOA 用时 − 编队用时（秒/车）")
        for x in FLOWS:
            seeds = {m: {r["seed"]: float(r["mean_s"]) for r in cases if r["method"] == m
                         and float(r["road_limit"]) == limit and int(r["flow"]) == x}
                     for m in ("noa", "transform")}
            differences = [seeds["noa"][s] - seeds["transform"][s] for s in sorted(seeds["noa"])]
            means = {r["method"]: float(r["mean_s"]) for r in summary
                     if float(r["road_limit"]) == limit and int(r["flow"]) == x}
            gain = means["noa"] - means["transform"]
            ax.scatter(x + np.linspace(-17, 17, len(differences)), differences, color="#76AD9F", s=18)
            ax.plot([x-26, x+26], [gain, gain], color="#104F44", lw=2.5)
        ax.axhline(0, color="#626F73", lw=.8, linestyle="--")
    finish(fig, "travel_time", folder, "上排符号为合并车辆均值，竖线为五次运行的范围。下排每个点是一对种子，短横线为合并车辆的差值。")
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 6.6))
    for ax, (key, title, unit) in zip(axes.flat, [
        ("exit_veh_h", "(a)   前 600 秒的实际出口流率", "辆/小时（全路）"),
        ("p95_s", "(b)   第 95 百分位行程时间", "秒/车"),
        ("fuel_g_km", "(c)   单位里程燃油消耗", "克/车公里"),
        ("early_pct", "(d)   最后 200 米之前已跨入中道", "终止道出发车辆占比（%）")]):
        axes_style(ax, title, unit)
        plot_methods(ax, summary, cases, 33.3, key)
        if key == "early_pct":
            ax.set_ylim(0, 102)
    finish(fig, "traffic_metrics", folder, "项目默认限速 33.3 m/s。符号为五个种子合并后的指标，竖线为各次运行的最小值至最大值。")


if __name__ == "__main__":
    main()
