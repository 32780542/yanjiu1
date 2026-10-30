"""Plot observed SUMO string responses; export the exact plotted values and provenance."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True, help="base/T string summary.json")
    parser.add_argument("--second", type=Path, required=True, help="T/T2 string summary.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = [*json.loads(args.first.read_text(encoding="utf-8")),
               *json.loads(args.second.read_text(encoding="utf-8"))]
    unique, provenance = {}, []
    for record in records:
        key = record["candidate"], record["signal"]
        path = Path(record["run_dir"]) / "trajectory.jsonl.gz"
        with gzip.open(path, "rb") as stream:
            raw = stream.read()
        if key in unique:
            assert unique[key][2] == raw, "Repeated T physical trajectories differ"
        unique[key] = record, path, raw
        provenance.append(dict(candidate=key[0], signal=key[1], source_sha256=record["source_sha256"],
                               trajectory_sha256=digest(path), decoded_sha256=hashlib.sha256(raw).hexdigest()))
    for record, _, _ in unique.values():
        assert record["safe"] and record["vehicles"] == 12
    colors = {"base": "#E64B35", "T": "#4DBBD5", "T2": "#00A087"}
    labels = {"base": "Fixed 30 m", "T": "Single-front CTH", "T2": "Two-front CTH"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "axes.unicode_minus": True})
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    table = []
    for column, signal in enumerate(("sine", "brake")):
        ax, amplitude = axes[0, column], axes[1, column]
        low, high = (60, 120) if signal == "sine" else (20, 100)
        for candidate in ("base", "T", "T2"):
            record, _, raw = unique[candidate, signal]
            rows = [json.loads(line) for line in raw.splitlines()]
            times = [r["time_s"] for r in rows]
            leader = [r["states"]["v00"][1] for r in rows]
            tail = [r["states"]["v11"][1] for r in rows]
            if candidate == "base":
                ax.plot(times, leader, color="#444444", linestyle="--", linewidth=1.3, label="Leader")
            ax.plot(times, tail, color=colors[candidate], linewidth=1.6, label=labels[candidate] + " tail")
            values = [r["half_speed_range_mps"] for r in record["measures"]]
            amplitude.plot(range(12), values, color=colors[candidate], marker="o", markersize=4,
                           linewidth=1.6, label=labels[candidate])
            for row, v_lead, v_tail in zip(rows, leader, tail):
                table.append(dict(signal=signal, candidate=candidate, time_s=row["time_s"],
                                  leader_speed_mps=v_lead, tail_speed_mps=v_tail))
        ax.set(xlim=(low, high), xlabel="Time (s)", ylabel="Observed speed (m/s)",
               title="(a) Periodic input" if column == 0 else "(b) Brake and recovery")
        amplitude.set(xlabel="Vehicle index (0 = leader)", ylabel="Speed half-range (m/s)",
                      title="(c) Periodic: 60-180 s" if column == 0 else "(d) Brake: 20-100 s")
        for item in (ax, amplitude):
            item.grid(axis="y", color="#D7D7D7", linewidth=.6, alpha=.7)
            item.xaxis.set_major_locator(MaxNLocator(integer=bool(item is amplitude), nbins=6))
            item.legend(frameon=False, fontsize=8, loc="best")
    for suffix in ("png", "svg"):
        fig.savefig(args.output / ("string_response." + suffix), dpi=300)
    plt.close(fig)
    with (args.output / "string_values.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    outputs = {p.name: digest(p) for p in args.output.iterdir() if p.is_file()}
    (args.output / "string_provenance.json").write_text(
        json.dumps(dict(source_records=provenance, repeated_T_byte_identical=True,
                        script_sha256=digest(Path(__file__)), outputs=outputs), indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), plotted_rows=len(table), png_svg=True)))


if __name__ == "__main__":
    main()
