"""Plot the same vehicles from a native SUMO run: plot_trajectories.py RUN OUTPUT.svg."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import numpy as np

from measure import lane_of, road_layout, whole_shape


COLORS = ("#006D77", "#B54F22", "#3C64A3", "#8263A3")
CRUISE = 28.8


def representative(frames, members, lanes, lo, hi):
    """Midpoint of the longest consecutive whole-group geometrical hold."""
    best = []
    current = []
    for t, states in frames:
        if (states.keys() == members and all(lo <= s[0] < hi for s in states.values())
                and whole_shape(states, lanes)):
            current.append((t, states))
        else:
            if len(current) > len(best):
                best = current
            current = []
    best = max((best, current), key=len)
    if not best:
        raise ValueError(f"No whole-cohort {lanes}-lane frame within [{lo}, {hi}) m")
    return best[len(best) // 2]


def reference_slots(states, lanes):
    """Fit a translation of the balanced 12-slot template with the audit spacing."""
    if len(states) % lanes:
        raise ValueError("This figure requires equal numbers of slots on each active lane")
    gap = 5.5 + .85 * np.mean([s[2] for s in states.values()])
    columns = [sorted((s[0] for s in states.values() if lane_of(s[1]) == lane), reverse=True)
               for lane in range(lanes)]
    fits = []
    for phase in (range(2) if lanes == 2 else (0,)):
        offsets = [(x, lane, (rank + ((lane + phase) % 2) / 2) * gap)
                   for lane, column in enumerate(columns) for rank, x in enumerate(column)]
        center = np.mean([x + offset for x, _, offset in offsets])
        error = sum((x + offset - center)**2 for x, _, offset in offsets)
        fits.append((error, [(center - off, (lane + .5) * 3.3) for _, lane, off in offsets]))
    return np.asarray(min(fits, key=lambda fit: fit[0])[1])


def plot(folder, output, preview_png=None):
    config = json.loads((folder / "input.json").read_bytes())
    members = {row["vehicle_id"] for row in config["arrivals"]}
    if len(members) != 12:
        raise ValueError("Use a fixed 12-vehicle demonstration run")
    (incoming, cut), (outgoing, length) = road_layout(folder)
    trace = folder / "positions.jsonl.gz"
    with gzip.open(trace, "rt", encoding="utf-8") as stream:
        frames = [(frame["time_s"], frame["states"]) for frame in map(json.loads, stream)]
    preview = config["case"]["road_observation_m"]
    snapshots = (representative(frames, members, incoming, 0., cut-preview),
                 representative(frames, members, outgoing, cut, cut+length))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.edgecolor": "#687580", "svg.fonttype": "none",
                         "svg.hashsalt": "staggered-transport"})
    fig = plt.figure(figsize=(9.8, 8.1))
    grid = fig.add_gridspec(3, 2, height_ratios=(1.35, .62, 1), left=.1, right=.975, top=.88,
                            bottom=.154, hspace=.68, wspace=.17)
    ax = fig.add_subplot(grid[0, :])
    lateral = fig.add_subplot(grid[1, :], sharex=ax)
    tracks = {key: [] for key in members}
    for t, states in frames:
        for key, (x, y, *_rest) in states.items():
            tracks[key].append((t, x, y))
    first_preview = min(t for track in tracks.values() for t, x, _ in track if x >= cut-preview)
    last_crossing = max(next(t for t, x, _ in track if x >= cut) for track in tracks.values())
    for axis in (ax, lateral):
        axis.axvspan(first_preview, last_crossing, color="#E6E9EB", zorder=0)
        for t, _ in snapshots:
            axis.axvline(t, ls=":", color="#525C62", lw=.9)
        axis.grid(axis="y", color="#E1E5E7", lw=.55)
    # Split only on a lane change. Each line retains all native samples.
    for key in sorted(tracks):
        table = np.asarray(tracks[key])
        lane = np.array([lane_of(y) for y in table[:, 2]])
        points = np.column_stack((table[:, 0], table[:, 1] - CRUISE * table[:, 0]))
        breaks = np.flatnonzero(np.diff(lane)) + 1
        for start, end in zip([0, *breaks], [*breaks, len(points)-1]):
            ax.plot(*points[start:end+1].T, color=COLORS[lane[start]], lw=1.2)
            lateral.plot(table[start:end+1, 0], table[start:end+1, 2], color=COLORS[lane[start]], lw=1.2)
        ax.scatter(*points[breaks].T, s=12, facecolors="white", edgecolors="#31383C", lw=.7, zorder=3)
    ax.set_ylabel("Longitudinal position in\nmoving frame  (m)")
    ax.set_title("A    Longitudinal trajectories", loc="left", fontweight="bold")
    ax.tick_params(labelbottom=False)
    lateral.set_title("B    Lateral trajectories", loc="left", fontweight="bold")
    lateral.set(xlabel="Simulation time  (s)", ylabel="Lateral position  (m)")
    lateral.set_yticks([(k+.5)*3.3 for k in range(max(incoming, outgoing))])
    lateral.set_ylim(0, max(incoming, outgoing)*3.3)
    handles = [Line2D([], [], color=COLORS[lane], lw=2, label=f"Lane {lane+1}")
               for lane in range(max(incoming, outgoing))]
    fig.legend(handles=handles, ncol=len(handles), frameon=False, loc="upper right",
               bbox_to_anchor=(.985,.977), handlelength=1.5, columnspacing=1)
    axes = [fig.add_subplot(grid[2, i]) for i in range(2)]
    front_extent = max(max(s[0] for s in states.values())-min(s[0] for s in states.values())
                       for _, states in snapshots)
    for axis, (t, states), lanes, where in zip(axes, snapshots, (incoming, outgoing),
                                              ("C    Upstream", "D    Downstream")):
        front = max(s[0] for s in states.values())
        slots = reference_slots(states, lanes)
        for lane in range(lanes):
            axis.axhline((lane+.5)*3.3, color="#D9DFE2", lw=.7, zorder=0)
        axis.scatter(slots[:,0]-front, slots[:,1], s=220, marker="s", facecolors="none",
                     edgecolors="#394951", lw=.85, zorder=1)
        for key, (x, y, *_rest) in states.items():
            label = key.removeprefix("initial_")
            axis.scatter(x-front, y, s=117, color=COLORS[lane_of(y)], zorder=2)
            axis.text(x-front, y, label, ha="center", va="center", color="white", fontsize=7.4)
        axis.set_title(f"{where}   ·   {t:.1f} s", loc="left", fontweight="bold")
        axis.set_title(f"Front at {front:.0f} m", loc="right", fontsize=8)
        axis.set(xlim=(-front_extent-12, 12), ylim=(0, (max(incoming, outgoing)+.1)*3.3),
                 xlabel="Distance from cohort front  (m)")
        axis.xaxis.set_major_locator(MaxNLocator(5))
        axis.set_yticks([(k+.5)*3.3 for k in range(lanes)], [f"L{k+1}" for k in range(lanes)])
        axis.tick_params(length=3)
    axes[0].set_ylabel("Measured lane")
    fig.suptitle(f"{incoming} to {outgoing} lanes    |    Twelve-vehicle cohort",
                 x=.10, y=.963, ha="left", fontsize=15, fontweight="bold")
    fig.text(.1, .082, "A–B   Vehicle fronts sampled on the road. A uses x − 28.8 t. Circles mark crossings. "
             "Shading spans the first preview to the last boundary crossing.", fontsize=8)
    fig.text(.1, .054, "C–D   Each square is one fitted staggered slot. Numbered dots are the measured "
             "vehicle fronts at the two dotted times. Lane centers are 3.3 m apart.", fontsize=8)
    fig.text(.1, .027, f"SUMO   /   {config['case']['scenario']}   /   road boundary {cut:.0f} m   /   "
             f"sample {config['positions_step_s']:.1f} s   /   trace SHA-256 {hashlib.sha256(trace.read_bytes()).hexdigest()[:16]}",
             fontsize=7, color="#495761")
    fig.savefig(output, format="svg", metadata={"Date": None})
    if preview_png:
        fig.savefig(preview_png, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("svg", type=Path)
    parser.add_argument("--preview-png", type=Path)
    args = parser.parse_args()
    plot(args.run, args.svg, args.preview_png)
