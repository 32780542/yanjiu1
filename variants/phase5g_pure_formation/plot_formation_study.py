"""从复算结果生成中文论文图，输出 300 DPI PNG 与 SVG。"""

import argparse
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np


def plot(directory):
    directory = Path(directory)
    rows = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    data = json.loads((directory / "formation_rate_figure.json").read_text(encoding="utf-8"))
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                         "axes.unicode_minus": False, "font.size": 10,
                         "svg.fonttype": "none"})
    def save(fig, name):
        fig.tight_layout()
        for suffix in ("png", "svg"):
            target = directory / f"{name}.{suffix}"
            fig.savefig(target, dpi=300, bbox_inches="tight", facecolor="white")
            if suffix == "svg":
                target.write_text("\n".join(line.rstrip() for line in
                    target.read_text(encoding="utf-8").splitlines())+"\n", encoding="utf-8")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.3, 3.9))
    matrix = np.array(data["matrix"])
    image = ax.imshow(matrix, vmin=0, vmax=100, cmap="Blues", aspect="auto")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{matrix[i,j]:.0f}%\n({matrix[i,j]/20:.0f}/5)",
                    ha="center", va="center", color="white" if matrix[i,j] >= 60 else "black")
    ax.set_xticks(range(3), data["col_labels"])
    ax.set_yticks(range(3), data["row_labels"])
    ax.set_xlabel("每车道需求率（辆/小时）")
    ax.set_title("不同车道数与需求率下的整队形成率", pad=12)
    fig.colorbar(image, ax=ax, label="整队形成率（%）", shrink=.85)
    save(fig, "formation_rate")

    names = ("L3_q756", "speed8", "speed12", "gap24", "gap36")
    labels = ("基准\nv=10, D=30", "速度8\nD=30", "速度12\nD=30",
              "层距24\nv=10", "层距36\nv=10")
    lookup = {row["name"]: row for row in rows}
    colors = ("#3C5488", "#00A087", "#E64B35", "#4DBBD5", "#8491B4")
    fig, ax = plt.subplots(figsize=(7.3, 4.3))
    for seed, color in zip(range(1, 6), colors):
        xs = np.arange(5)+(seed-3)*.055
        ys = [lookup[f"{name}_s{seed}"]["formation_delay_s"] for name in names]
        ax.plot(xs, [np.nan if y is None else y for y in ys], color=color,
                marker="o", markersize=4, linewidth=.8, alpha=.8, label=f"seed {seed}")
        for x, y in zip(xs, ys):
            if y is None:
                ax.plot(x, 200, marker="x", color=color, markersize=7, markeredgewidth=1.5)
    ax.axhline(200, color="#aaaaaa", linewidth=.7, linestyle=":")
    ax.text(4.35, 204, "×：观察结束尚未形成", ha="right", fontsize=9)
    ax.set_xticks(range(5), labels)
    ax.set_ylabel("末车实际入场后的形成延迟（s）")
    ax.set_ylim(0, 225)
    ax.set_title("参数变化的配对种子实验（3车道，756辆/小时/车道）", pad=12)
    ax.legend(ncol=5, loc="upper center", frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.15)
    save(fig, "parameter_delay")

    source = Path(json.loads((directory / "verification.json").read_text(encoding="utf-8"))["source_directory"])
    fig, axes = plt.subplots(2, 1, figsize=(8, 4.9))
    for ax, name, title in zip(axes, ("L3_q1512_s1", "L3_q252_s1"),
            ("1512辆/小时/车道：形成整队", "252辆/小时/车道：终态车道数均衡，车群仍分离")):
        with gzip.open(source / name / "trajectory.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                final = json.loads(line)
        states = final["states"]
        head = max(s["x_m"] for s in states.values())
        for state in states.values():
            lane = min(2, max(0, int(state["y_m"] / 3.3)))
            ax.add_patch(Rectangle((state["x_m"]-head-2, state["y_m"]-.9),
                                  4, 1.8, facecolor=colors[lane], edgecolor="white", linewidth=.3))
        for y in (0, 3.3, 6.6, 9.9):
            ax.axhline(y, color="#999999", linewidth=.6, linestyle="--")
        ax.set_xlim(min(s["x_m"] for s in states.values())-head-20, 15)
        ax.set_ylim(-.4, 10.3)
        ax.set_yticks((1.65, 4.95, 8.25), ("车道1", "车道2", "车道3"))
        ax.set_title(title+"（seed 1）", fontsize=10, loc="left")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.set_xlabel("相对最前方车辆的纵向位置（m）")
    save(fig, "formation_examples")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    plot(parser.parse_args().directory)
