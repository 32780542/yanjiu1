"""Measured diagnostic plots only; native performance tables remain authoritative."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
from statistics import mean
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from audit_raw_midflow import read, sha

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SKILL = Path("C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py")


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("academic_figure_engine", SKILL)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    theme = engine.THEMES["nature"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none", "axes.axisbelow": True})
    colors = {"S": "#3C5488", "B": "#E64B35", "BC": "#00A087"}
    sources = {}
    def tracked(path):
        sources[str(path.resolve())] = sha(path)
        return path
    def load_json(path):
        return read(tracked(path))
    def load_csv(path):
        with tracked(path).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    def style(ax):
        engine.apply_base_style(ax, theme)
    def save(fig, name):
        fig.savefig(output / (name + ".png"), dpi=300, bbox_inches="tight", facecolor="white")
        fig.savefig(output / (name + ".svg"), bbox_inches="tight", facecolor="white")
        plt.close(fig)

    transition = load_json(HERE / "transition_B_BC_S73_summary_v1/transition_summary.json")
    fig, axes = plt.subplots(2, 3, figsize=(12.4, 7.2), constrained_layout=True)
    for col, flow in enumerate((1500, 1750, 2000)):
        for candidate in ("S", "B", "BC"):
            case = next(c for c in transition["cases"] if c["metadata"]["candidate"] == candidate and c["metadata"]["seed"] == 73 and c["metadata"]["flow"] == flow)
            rows = [r for r in case["profile_all_lanes"] if 400 <= int(r["x0_m"]) < 800 and r["gap_p50_m"]]
            axes[0, col].plot([int(r["x0_m"]) + 10 for r in rows], [float(r["gap_p50_m"]) for r in rows],
                              marker="o", markersize=3, lw=1.6, color=colors[candidate], label=candidate)
            cohort = next(g for g in case["cohorts"] if g["anchor_lane"] == "0")
            assert case["continuous_front_monitor_available"]
            axes[1, col].plot([s["relative_s"] for s in cohort["samples"]], [s["persistent_gap_p50_m"] for s in cohort["samples"]],
                              marker="o", markersize=4, lw=1.6, color=colors[candidate],
                              label=f"{candidate}: {cohort['persistent_front_n']}/{cohort['crossing_n']}")
        axes[0, col].axvline(640, color="0.35", linestyle="--", lw=1)
        axes[0, col].set(title=f"{flow} veh/h/lane", xlabel="x (m), measured 20 m bins", ylim=(15, 85))
        axes[1, col].set(xlabel="Seconds after first measured x >= 640 m", ylim=(20, 75))
        axes[0, col].legend(frameon=False, ncol=3, fontsize=8)
        axes[1, col].legend(title="Fixed-front cohort / all lane-0 crossings", frameon=False, fontsize=7, title_fontsize=7)
        for row in range(2):
            style(axes[row, col])
    axes[0, 0].set_ylabel("Median actual front-to-front gap (m)")
    axes[1, 0].set_ylabel("Median gap with same front every 0.1 s (m)")
    fig.suptitle("Recorded headway expansion and the 640 m transition | seed 73 | crossing cohort [30,180) s", fontsize=12)
    save(fig, "headway_transition_seed73")

    rows = load_csv(HERE / "Bscreen18_summary_v1/seed_equal_means.csv")
    means = {(r["candidate"], int(float(r["flow"]))): r for r in rows if r["candidate"] == "S"}
    means.update({(r["candidate"], int(float(r["flow"]))): r for r in load_csv(HERE / "B_BC_12_summary_v1/seed_equal_means.csv")})
    waits = {}
    for candidate, batch in (("S", "20261103_midflow_V1_screen73_12"), ("B", "20261103_midflow_B_screen73_6"), ("BC", "20261103_midflow_BC_screen73_6")):
        manifest = load_json(ROOT / "tmp/staggered_bottleneck" / batch / "manifest.json")
        for record in manifest:
            if record["candidate"] != candidate:
                continue
            result = load_json(Path(record["run_dir"]) / "result.json")
            assert result["safe"] and result["all_completed"]
            waits[candidate, int(record["flow"]), record["seed"]] = result["mean_entry_wait_s"]
    fig, axes = plt.subplots(2, 3, figsize=(11.8, 7.2), constrained_layout=True)
    loss_data = []
    for col, flow in enumerate((1500, 1750, 2000)):
        for j, candidate in enumerate(("S", "B", "BC")):
            r = means[candidate, flow]
            values = [float(r["region_100_600_positive_speed_deficit_s"]), float(r["region_600_800_positive_speed_deficit_s"]),
                      float(r["region_800_1000_positive_speed_deficit_s"]) + float(r["region_1000_1100_positive_speed_deficit_s"])]
            assert abs(sum(values) - float(r["region_100_1100_positive_speed_deficit_s"])) < 1e-6
            bottom = 0
            for i, (value, label) in enumerate(zip(values, ("100-600 m", "600-800 m", "800-1100 m"))):
                axes[0, col].bar(j, value, bottom=bottom, width=.65, color=("#8491B4", "#F39B7F", "#91D1C2")[i], label=label if j == 0 else None)
                bottom += value
            values_wait = [waits[candidate, flow, seed] for seed in (73, 74)]
            axes[1, col].bar(j, mean(values_wait), color=colors[candidate], width=.65, alpha=.75)
            axes[1, col].scatter([j - .07, j + .07], values_wait, color="0.12", s=17, zorder=4)
            loss_data.append(dict(candidate=candidate, flow=flow, zone_values=values, entry_wait_s=values_wait))
        axes[0, col].set(title=f"{flow} veh/h/lane", xticks=range(3), xticklabels=("S", "B", "BC"), ylim=(0, 820))
        axes[1, col].set(xticks=range(3), xticklabels=("S", "B", "BC"), ylim=(0, 1.0))
        for row in range(2):
            style(axes[row, col])
    axes[0, 0].set_ylabel("Positive speed-deficit integral (vehicle s)")
    axes[1, 0].set_ylabel("Actual entry waiting per requested vehicle (s)")
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("A wider upstream organization gap moves part of the cost upstream | [30,180) s\nTop: seed-equal regional integrals; bottom: two seed values and their mean", fontsize=11)
    save(fig, "capacity_spacing_cost_transfer")

    admission = []
    fig, ax = plt.subplots(figsize=(9.2, 5.3), constrained_layout=True)
    for j, (label, folder) in enumerate((("GP1", "GP_gap_availability_v3"), ("GP2", "GP2_states_GP1_gap_queries_v1"), ("G0", "G0_gap_availability_v1"))):
        stages = [r for path in (HERE / folder).glob("*_stages.csv") for r in load_csv(path) if r["stage"] == "request"]
        n = len(stages)
        planned = sum(r["plan_exists"] == "True" for r in stages)
        good_planned = sum(r["plan_exists"] == "True" and r["current_cth_with_2m_band"] == "True" for r in stages)
        good_fallback = sum(r["plan_exists"] == "False" and r["current_cth_with_2m_band"] == "True" for r in stages)
        strict = sum(r["current_cth_exact_window"] == "True" for r in stages)
        values = [good_planned, planned - good_planned, good_fallback, n - planned - good_fallback]
        bottom = 0
        for i, (value, color, title) in enumerate(zip(values, ("#00A087", "#E64B35", "#91D1C2", "#B7BCC4"),
                 ("Plan exists, inside current 2 m band", "Plan exists, outside current 2 m band", "Fallback, inside current 2 m band", "Fallback, outside current 2 m band"))):
            ax.bar(j, 100 * value / n, bottom=bottom, color=color, width=.65, label=title if j == 0 else None)
            bottom += 100 * value / n
        ax.text(j, 101, f"n={n}\nStrict zero-band: {100*strict/n:.1f}%", ha="center", va="bottom", fontsize=8)
        admission.append(dict(method=label, n=n, planned=planned, strict=strict, category_counts=values))
    ax.set(xticks=range(3), xticklabels=("GP1", "GP2", "G0 (matched control)"), ylabel="Completed-merge latest submissions (%)", ylim=(0, 116))
    style(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), frameon=False, fontsize=8, ncol=2)
    ax.set_title("Plan eligibility and actual current CTH band are different | seeds 73-74", pad=32, fontsize=11)
    save(fig, "planner_coverage_and_fallback")
    (output / "plot_data.json").write_text(json.dumps(dict(loss_and_waiting=loss_data, admission=admission), indent=2) + "\n", encoding="utf-8")
    sources[str(SKILL)] = sha(SKILL)
    (output / "provenance.json").write_text(json.dumps(dict(sources_sha256=sources, skill="academic-figures", theme="nature", dpi=300,
          limitations=["No smoothing, fitted curves, confidence intervals, significance tests or invented data.", "Headway figure uses fixed seed73 across all three methods; persistent-front subset sizes are printed.",
                       "Positive speed deficit does not compensate overspeed and is not net system delay.", "Admission denominator is completed 2-to-1 after640 events' latest native submission; gap availability is a held=None recorded-state query, not private choice replay.",
                       "Inside a current CTH band is not a claim of collision safety; all native safety outcomes remain separate."]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "make_mechanism_figures_source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(figures=3, formats=["PNG300dpi", "SVG"], output=str(output.resolve()))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)
