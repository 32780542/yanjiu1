"""Compare two observed cars using matched trajectories from the seven-car lane drop."""
import csv
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
FIGURES = HERE / "figures"
CASE = "candidate_4to3_7_long_11254"
METHODS = (("combined-fresh", "Slot tracking", "#73797C", "--"),
           ("conflict-screen", "Yield while blocked", "#D88939", "-."),
           ("hold-matched", "Hold the receiving gap", "#166C77", "-"))


def extract():
    rows = []
    for name, _, _, _ in METHODS:
        parent = HERE.parents[2] / "tmp" / ("nov25-noon-" + name) / CASE
        [path] = parent.glob("*/positions.jsonl.gz")
        with gzip.open(path, "rt", encoding="utf8") as stream:
            for frame in map(json.loads, stream):
                t = frame["time_s"]
                if t > 84:
                    break
                if t >= 71:
                    incoming, resident = (frame["states"][key] for key in ("initial_1", "initial_5"))
                    rows.append(dict(method=name, time_s=t, separation_m=incoming[0]-resident[0],
                                     incoming_y_m=incoming[1], resident_y_m=resident[1],
                                     incoming_speed_m_s=incoming[2], resident_speed_m_s=resident[2]))
    with (FIGURES/"receiving7.csv").open("w", encoding="utf8", newline="") as output:
        writer = csv.DictWriter(output, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def render():
    with (FIGURES/"receiving7.csv").open(encoding="utf8") as stream:
        rows = list(csv.DictReader(stream))
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":9, "svg.fonttype":"none",
                         "svg.hashsalt":"noon-receiving", "axes.spines.top":False, "axes.spines.right":False})
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.4), sharex=True, layout="constrained")
    for name, label, color, style in METHODS:
        series = [r for r in rows if r["method"] == name]
        time = [float(r["time_s"]) for r in series]
        for ax, field in zip(axes, ("separation_m", "incoming_y_m")):
            ax.plot(time, [float(r[field]) for r in series], linestyle=style, color=color,
                    linewidth=1.9, label=label)
    axes[0].axhline(8, color="#AAAAAA", linestyle=":", linewidth=1)
    axes[0].text(83.8, 8.5, "8 m clearance", color="#555555", ha="right", fontsize=8)
    axes[0].set(ylabel="Front-to-front distance (m)", title="a    Longitudinal separation of the incoming and receiving vehicles")
    axes[1].axhline(6.6, color="#AAAAAA", linestyle=":", linewidth=1)
    axes[1].set(yticks=[4.95, 6.6, 8.25], yticklabels=["Lane 1", "Boundary", "Lane 2"],
                xlabel="Simulation time (s)", ylabel="Incoming vehicle",
                title="b    Measured lateral position during the same interval", xlim=(71,84), ylim=(4.5,8.7))
    for ax in axes:
        ax.grid(axis="x", linewidth=.5, color="#E2E6E5")
        ax.title.set_fontsize(10)
    axes[0].legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    fig.savefig(FIGURES/"receiving7.png", dpi=300, facecolor="white")
    fig.savefig(FIGURES/"receiving7.svg", metadata={"Date":None})
    plt.close(fig)


if __name__ == "__main__":
    import sys
    if "--extract" in sys.argv:
        extract()
    render()
