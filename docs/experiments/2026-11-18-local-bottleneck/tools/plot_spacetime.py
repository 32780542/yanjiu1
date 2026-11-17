"""Plot matched SUMO speed fields from the completed experiment manifest."""

import argparse
import csv
import gzip
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def speed_bins(run, limit_s=600):
    total = np.zeros((60, limit_s // 5))
    samples = np.zeros_like(total, dtype=int)
    with gzip.open(run / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            time = frame["time_s"]
            if time >= limit_s:
                break
            column = int(time // 5)
            for x, _, speed, _ in frame["states"].values():
                if 0 <= x < 1200:
                    row = int(x // 20)
                    total[row, column] += speed
                    samples[row, column] += 1
    speed = np.divide(total, samples, out=np.full_like(total, np.nan), where=samples > 0)
    return speed, samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    runs = {}
    for row in json.loads(args.manifest.read_bytes()):
        if row["scenario"] == "lane_drop" and row["seed"] == args.seed:
            if row["status"] != "drained" or not row["safe"]:
                raise ValueError(f"Unsuccessful trajectory: {row['case_output']}")
            runs[int(row["flow"]), row["mode"]] = Path(row["run_dir"])
    flows, modes = (1500, 1750, 2000), ("noa", "transform")
    assert set(runs) == {(flow, mode) for flow in flows for mode in modes}
    args.output.mkdir(parents=True, exist_ok=False)
    figure, axes = plt.subplots(3, 2, figsize=(8.5, 7), sharex=True, sharey=True, layout="constrained")
    options = dict(origin="lower", extent=(0, 600, 0, 1200), aspect="auto", vmin=0, vmax=33.3,
                   cmap=matplotlib.colormaps["turbo_r"].with_extremes(bad="#efefef"), interpolation="none")
    with (args.output / "speed_bins.csv").open("w", newline="", encoding="utf-8") as stream:
        table = csv.writer(stream)
        table.writerow(("flow_veh_h_lane", "mode", "seed", "time_start_s", "x_start_m", "mean_speed_m_s", "vehicle_samples"))
        for i, flow in enumerate(flows):
            for j, mode in enumerate(modes):
                ax = axes[i, j]
                speed, samples = speed_bins(runs[flow, mode])
                picture = ax.imshow(speed, **options)
                ax.axhline(1000, color="black", linestyle="--", linewidth=.7)
                if i == 0:
                    ax.set_title(("Reactive NOA", "Local staggered formation")[j], fontsize=11)
                if j == 0:
                    ax.set_ylabel(f"{flow:,} veh/h/lane\nPosition (m)")
                for row, column in zip(*np.nonzero(samples)):
                    table.writerow((flow, mode, args.seed, column * 5, row * 20,
                                    round(speed[row, column], 6), samples[row, column]))
    for ax in axes[-1]:
        ax.set_xlabel("Time (s)")
    figure.colorbar(picture, ax=axes, label="Mean speed (m/s)", shrink=.84)
    for extension in ("png", "svg"):
        figure.savefig(args.output / f"speed_spacetime.{extension}", dpi=300)
    plt.close(figure)


if __name__ == "__main__":
    main()
