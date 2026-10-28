"""Plot audited native_comparison summary.json without rerunning any simulation.

Example (always use a fresh output directory)::

    python experiments/plot_native_comparison.py report/summary.json \
        --output results/figures_new --six-case path/to/six_vehicle_case

Dependencies: Python 3.10+, matplotlib, numpy, and a Chinese font (Microsoft
YaHei/SimHei/Noto CJK). The evaluator's saved `runs` are the only comparison
data source. Each seed remains visible. Black bars are arithmetic means only
when every scenario seed is present, audited/complete/safe and comparable, and
the metric is defined in every seed. Failed or missing runs are marked below
the data axis. Undefined group sizes are never filled with zero. There are no
significance tests, error bars, smoothing, extrapolated frames or rankings.

NOA structures are detected geometry, not evidence of controlled formation.
`global` is labelled Cai式集中参考, not full reproduction of the paper.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np


MODES = ("noa", "formation", "transform", "global")
LABELS = {
    "noa": "NOA",
    "formation": "编队 +\n普通合流",
    "transform": "分布式编队 +\n车道缩减变换",
    "global": "Cai式\n集中参考",
}
SCENARIOS = {"lane_drop": "3→2车道缩减", "straight3": "三车道直路"}
# Okabe–Ito palette: colour blind friendly, with seed shapes as a second cue.
COLORS = {"noa": "#737373", "formation": "#0072B2", "transform": "#009E73", "global": "#D55E00"}
VEHICLE_COLORS = ("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9")
MARKERS = ("o", "s", "^", "D", "v", "P", "X", "<", ">", "h")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def configure_style(font_path=None):
    if font_path:
        fm.fontManager.addfont(str(font_path))
        family = fm.FontProperties(fname=str(font_path)).get_name()
    else:
        installed = {font.name for font in fm.fontManager.ttflist}
        family = next(
            (
                name
                for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC")
                if name in installed
            ),
            None,
        )
        if family is None:
            raise ValueError(
                "No Chinese font found; install Microsoft YaHei/SimHei/Noto CJK or pass --font /path/to/font.ttf"
            )
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [family, "DejaVu Sans"],
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.5,
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.7,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
            "grid.color": "#D9DDE1",
            "grid.linewidth": 0.55,
            "xtick.direction": "out",
            "ytick.direction": "out",
        }
    )
    return family


def load_summary(path):
    report = read_json(path)
    if not isinstance(report, dict) or not isinstance(report.get("runs"), list) or not report["runs"]:
        raise ValueError(
            "Expected native_comparison summary object with a nonempty runs list; probe arrays are not comparison reports"
        )
    seen = set()
    for row in report["runs"]:
        for key in (
            "scenario",
            "mode",
            "seed",
            "performance_eligible",
            "safe",
            "all_completed",
            "audit_issues",
        ):
            if key not in row:
                raise ValueError(f"Run is missing required audit field: {key}")
        if row["mode"] not in MODES or row["scenario"] not in SCENARIOS:
            raise ValueError(f"Unsupported scenario/mode: {row['scenario']}/{row['mode']}")
        key = row["scenario"], row["mode"], row["seed"]
        if key in seen:
            raise ValueError(f"Duplicate scenario/mode/seed {key}; separate reports from different versions")
        seen.add(key)
        if not isinstance(row["performance_eligible"], bool):
            raise ValueError(f"performance_eligible must be a boolean: {key}")
        if row["performance_eligible"] and not eligible(row):
            raise ValueError(f"Inconsistent eligible flag versus safety/completion/audit: {key}")
        for metric, value in row.items():
            if (
                metric.endswith("_rate")
                and value is not None
                and (not number(value) or not 0 <= value <= 1 + 1e-9)
            ):
                raise ValueError(f"Ratio must be in [0,1], not already a percentage: {key}/{metric}")
    return report


def eligible(row):
    return bool(
        row.get("performance_eligible") is True
        and row.get("safe") is True
        and row.get("all_completed") is True
        and not row.get("audit_issues")
        and not row.get("error")
        and not row.get("collisions")
        and not row.get("teleports")
    )


def seed_sort(seeds):
    return sorted(
        seeds,
        key=lambda value: (
            not isinstance(value, (int, float)),
            value if isinstance(value, (int, float)) else str(value),
        ),
    )


def comparison_issues(rows, scenario):
    """Check the saved row-level provenance before pooling seeds or modes."""
    issues = []
    grouped = defaultdict(list)
    scenario_rows = [r for r in rows if r["scenario"] == scenario]
    for key in ("parameters_sha256", "source_version_sha256"):
        values = [r.get(key) for r in scenario_rows]
        if any(value is None for value in values) or len(set(values)) != 1:
            issues.append(f"scenario:{key}_missing_or_mixed_cohort")
    for row in rows:
        if row["scenario"] == scenario:
            grouped[row["seed"]].append(row)
    for seed, members in grouped.items():
        if len(members) < 2:
            continue
        for key in ("demand_sha256", "parameters_sha256", "source_version_sha256"):
            values = [r.get(key) for r in members]
            if any(value is None for value in values) or len(set(values)) != 1:
                issues.append(f"seed={seed}:{key}_missing_or_mismatch")
    return issues


def mean_decision(rows, scenario, mode, metric, expected_seeds, provenance_issues):
    group = [r for r in rows if r["scenario"] == scenario and r["mode"] == mode]
    reasons = []
    if {r["seed"] for r in group} != set(expected_seeds):
        reasons.append("missing_scenario_seed")
    if any(not eligible(r) for r in group):
        reasons.append("ineligible_attempt")
    if any(not number(r.get(metric)) for r in group):
        reasons.append("undefined_metric")
    reasons.extend(provenance_issues)
    values = [r[metric] for r in group if number(r.get(metric))]
    return dict(
        scenario=scenario,
        mode=mode,
        metric=metric,
        attempted_n=len(group),
        expected_n=len(expected_seeds),
        defined_n=len(values),
        mean=float(np.mean(values)) if values and not reasons else None,
        suppressed_reasons=sorted(set(reasons)),
    )


def save_figure(fig, output, stem, manifest, dpi):
    files = []
    for extension in ("png", "svg"):
        destination = output / f"{stem}.{extension}"
        fig.savefig(destination, dpi=dpi, bbox_inches="tight", pad_inches=0.12)
        files.append(destination.name)
    plt.close(fig)
    manifest["figures"].append({"name": stem, "files": files})


def annotate_absent(ax, x, text, order=0, color="#737373"):
    # An axis-relative mark cannot be mistaken for a measured zero.
    ax.text(
        x,
        0.025 + order * 0.052,
        text,
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="bottom",
        fontsize=7,
        color=color,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 0.4},
    )


def metric_panel(
    ax, rows, scenario, metric, title, ylabel, seeds, manifest, factor=1, geometry=False, marker_seeds=None
):
    prov = comparison_issues(rows, scenario)
    seed_indices = {seed: i for i, seed in enumerate(seeds)}
    marker_indices = {seed: i for i, seed in enumerate(marker_seeds if marker_seeds is not None else seeds)}
    offsets = np.linspace(-0.20, 0.20, len(seeds)) if len(seeds) > 1 else [0.0]
    drawn = []
    for x, mode in enumerate(MODES):
        members = sorted(
            [r for r in rows if r["scenario"] == scenario and r["mode"] == mode],
            key=lambda r: seed_indices[r["seed"]],
        )
        if not members:
            annotate_absent(ax, x, "未提供")
        absence = 0
        for row in members:
            index = seed_indices[row["seed"]]
            value = row.get(metric)
            if not eligible(row):
                annotate_absent(ax, x, f"× s{row['seed']}失败/未通过", absence, "#A00000")
                absence += 1
                if not geometry:
                    continue
            if number(value):
                y = value * factor
                drawn.append(y)
                ax.scatter(
                    x + offsets[index],
                    y,
                    s=38,
                    marker=MARKERS[marker_indices[row["seed"]] % len(MARKERS)],
                    facecolor=COLORS[mode] if eligible(row) else "none",
                    edgecolor=COLORS[mode],
                    linewidth=0.9,
                    zorder=5,
                )
            else:
                no_group = (
                    geometry
                    and "multilayer_size" in metric
                    and row.get("downstream_formed_vehicle_seconds") == 0
                )
                annotate_absent(ax, x, f"s{row['seed']} {'无组' if no_group else '未定义'}", absence)
                absence += 1
        decision = mean_decision(rows, scenario, mode, metric, seeds, prov)
        manifest["mean_decisions"].append(decision)
        if decision["mean"] is not None:
            ax.plot(
                [x - 0.27, x + 0.27],
                [decision["mean"] * factor] * 2,
                color="#222222",
                linewidth=1.7,
                zorder=4,
                solid_capstyle="butt",
            )
    ax.set_title(title, loc="left", pad=10, fontweight="medium")
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(MODES)), [LABELS[m] for m in MODES])
    ax.set_xlim(-0.5, len(MODES) - 0.5)
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    if factor == 100:
        ax.set_ylim(-3, 105)
    elif drawn:
        low, high = min(drawn), max(drawn)
        margin = max((high - low) * 0.20, abs(high) * 0.04, 0.1)
        ax.set_ylim(max(0, low - margin), high + margin)
    else:
        ax.set_ylim(0, 1)
        ax.set_yticks([])
    ax.tick_params(axis="x", length=0, pad=7)


def figure_legend(fig, seeds, geometry=False):
    handles = [
        Line2D(
            [],
            [],
            linestyle="none",
            marker=MARKERS[i % len(MARKERS)],
            markersize=5,
            color="#555555",
            label=f"seed {seed}",
        )
        for i, seed in enumerate(seeds)
    ]
    handles.append(
        Line2D([], [], color="#222222", linewidth=1.7, label="五种子均值" if len(seeds) == 5 else "全部种子算术均值")
    )
    if geometry:
        handles.append(
            Line2D(
                [],
                [],
                color="#777777",
                marker="o",
                markerfacecolor="none",
                linestyle="none",
                label="空心点：未通过审计的几何观测",
            )
        )
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.943),
        ncol=min(4, len(handles)),
        frameon=False,
        columnspacing=1.4,
        handletextpad=0.55,
    )


def plot_performance(report, output, manifest, dpi, label):
    rows = report["runs"]
    scenarios = [s for s in SCENARIOS if any(r["scenario"] == s for r in rows)]
    seeds = seed_sort({r["seed"] for r in rows})
    decision_start = len(manifest["mean_decisions"])
    fig, axes = plt.subplots(len(scenarios), 2, figsize=(12.0, 3.2 * len(scenarios) + 1.5), squeeze=False)
    for index, scenario in enumerate(scenarios):
        scenario_seeds = seed_sort({r["seed"] for r in rows if r["scenario"] == scenario})
        for column, (metric, name, unit) in enumerate(
            (
                ("mean_travel_time_s", "平均行程时间", "平均行程时间 (s)"),
                ("fuel_g_per_km", "单位里程油耗", "油耗 (g/km)"),
            )
        ):
            metric_panel(
                axes[index, column],
                rows,
                scenario,
                metric,
                f"({chr(97 + index * 2 + column)}) {SCENARIOS[scenario]} · {name}",
                unit,
                scenario_seeds,
                manifest,
                marker_seeds=seeds,
            )
    fig.suptitle(label or "原生SUMO · 通行与油耗", y=0.995, fontsize=13, fontweight="medium")
    figure_legend(fig, seeds)
    mean_text = "五种子均值" if len(seeds) == 5 else "全部种子算术均值"
    caption = (f"点：各随机种子；横线：{mean_text}。油耗=总fuel_abs (mg) / 实际总里程 (m)，数值单位为g/km。\n"
               "Cai式集中参考：采用共同执行模型。")
    if any(d["mean"] is None for d in manifest["mean_decisions"][decision_start:]):
        caption += "  存在失败、缺测、未定义或不可比种子时不显示该组均值；状态原因见各面板标记。"
    fig.text(
        0.5,
        0.015,
        caption,
        ha="center",
        va="bottom",
        fontsize=8,
        color="#555555",
        linespacing=1.6,
    )
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.16, top=0.82, hspace=0.48, wspace=0.25)
    save_figure(fig, output, "performance_by_seed", manifest, dpi)


def plot_geometry(report, output, manifest, dpi, label):
    rows = report["runs"]
    if not any(r["scenario"] == "lane_drop" for r in rows):
        manifest["skipped"].append("downstream_geometry: no lane_drop rows")
        return
    seeds = seed_sort({r["seed"] for r in rows if r["scenario"] == "lane_drop"})
    metrics = (
        ("formation_participation_rate", "完整组参与率（确认≥1 s）", "车辆秒占比 (%)", 100),
        ("mean_multilayer_size", "完整组平均规模", "平均规模 (辆)", 1),
        ("stable_participation_rate", "5s稳定参与率", "车辆秒占比 (%)", 100),
        ("peak_multilayer_size", "完整组峰值规模", "峰值规模 (辆)", 1),
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.0))
    for index, (field, title, unit, factor) in enumerate(metrics):
        metric_panel(
            axes.flat[index],
            rows,
            "lane_drop",
            "downstream_" + field,
            f"({chr(97 + index)}) {title}",
            unit,
            seeds,
            manifest,
            factor,
            geometry=True,
        )
    fig.suptitle(
        (label + " · " if label else "") + "3→2下游完整组几何（1000≤x<1200 m）", y=0.995, fontsize=13
    )
    figure_legend(fig, seeds, geometry=any(not eligible(r) for r in rows if r["scenario"] == "lane_drop"))
    fig.text(
        0.5,
        0.014,
        "完整组：至少2个完整层；参与率分母为下游全部车辆秒。NOA仅为几何检测。\n"
        "平均规模按组持续时间加权；峰值为各种子内最大组规模。无组时规模未定义。\n"
        "点为各随机种子，横线为全部种子均值；5s稳定参与率并非条件保持概率。",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#555555",
        linespacing=1.5,
    )
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.185, top=0.80, hspace=0.48, wspace=0.25)
    save_figure(fig, output, "downstream_geometry_by_seed", manifest, dpi)


def road(ax, xmin, xmax, landmarks=True):
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(0, 9.9)
    for boundary in (0, 3.3, 6.6, 9.9):
        ax.plot(
            [xmin, xmax],
            [boundary] * 2,
            color="#B4BAC0",
            linewidth=0.7,
            linestyle="--" if boundary in (3.3, 6.6) else "-",
            zorder=0,
        )
    if xmax > 1000:
        ax.add_patch(
            Rectangle(
                (max(1000, xmin), 6.6),
                xmax - max(1000, xmin),
                3.3,
                facecolor="#E8E8E8",
                edgecolor="none",
                zorder=0,
            )
        )
    if landmarks:
        for x, text, color in ((640, "640 m · 准备区", "#A66A00"), (1000, "1000 m · 车道缩减", "#555555")):
            if xmin <= x <= xmax:
                ax.axvline(x, color=color, linestyle=":", linewidth=1.0, zorder=1)
                ax.text(x + 7, 9.48, text, color=color, fontsize=8, ha="left", va="top")
    ax.set_yticks((1.65, 4.95, 8.25), ("0 (1.65 m)", "1 (4.95 m)", "2 (8.25 m)"))
    ax.set_ylabel("车道中心 / 实际 y")
    ax.set_xlabel("纵向位置 x (m，车头)")
    ax.tick_params(axis="y", length=0)


def load_six_case(path):
    path = Path(path).resolve()
    if not path.is_dir():
        raise ValueError(
            "--six-case must be a native case directory containing input.json, result.json and positions.jsonl.gz"
        )
    source, result = read_json(path / "input.json"), read_json(path / "result.json")
    if source.get("case", {}).get("scenario") != "lane_drop":
        raise ValueError("Six-vehicle trace must be a lane_drop case")
    arrivals = source.get("arrivals", [])
    ids = sorted({row["vehicle_id"] for row in arrivals})
    if len(ids) != 6 or len(arrivals) != 6:
        raise ValueError(f"Expected exactly six requested vehicles, got {len(arrivals)}")
    frames = []
    previous = -math.inf
    with gzip.open(path / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            if not number(frame["time_s"]) or frame["time_s"] <= previous:
                raise ValueError("Position timestamps must be finite and strictly increasing")
            previous = frame["time_s"]
            if set(frame["states"]) - set(ids):
                raise ValueError("Trace contains vehicles outside the six requested vehicles")
            if any(len(s) < 2 or not all(number(v) for v in s[:2]) for s in frame["states"].values()):
                raise ValueError("Invalid actual position sample")
            frames.append(frame)
    if not frames or set().union(*(set(f["states"]) for f in frames)) != set(ids):
        raise ValueError("Six-vehicle trace is empty or does not observe all six vehicles")
    return path, source, result, ids, frames


def plot_six_case(path, output, manifest, dpi):
    path, source, result, ids, frames = load_six_case(path)
    is_safe = bool(
        result.get("safe")
        and result.get("all_completed")
        and not result.get("collisions")
        and not result.get("teleports")
        and not result.get("error")
    )
    manifest["six_case"] = dict(
        case_dir=str(path),
        input_sha256=sha256(path / "input.json"),
        positions_sha256=sha256(path / "positions.jsonl.gz"),
        result_sha256=sha256(path / "result.json"),
        safe_complete=is_safe,
        frame_count=len(frames),
        first_time_s=frames[0]["time_s"],
        last_time_s=frames[-1]["time_s"],
        vehicle_ids=ids,
    )
    mode = source["case"].get("mode")
    mode_text = LABELS.get(mode, str(mode)).replace("\n", "")
    fig, ax = plt.subplots(figsize=(12, 3.8))
    xmax = max(1200, max(s[0] for f in frames for s in f["states"].values()))
    road(ax, 0, xmax)
    for index, vehicle in enumerate(ids):
        # Separate segments at disappearances; never connect across unobserved frames.
        coordinates = np.asarray([f["states"].get(vehicle, [np.nan, np.nan])[:2] for f in frames])
        ax.plot(
            coordinates[:, 0],
            coordinates[:, 1],
            color=VEHICLE_COLORS[index],
            linewidth=1.55,
            linestyle="-" if index % 2 == 0 else "--",
            label=vehicle,
        )
    fig.suptitle(
        f"真实六车 · {mode_text} · 实际轨迹" + ("" if is_safe else "（未通过安全/完成检查）"),
        y=0.985,
        fontsize=12,
    )
    fig.legend(
        *ax.get_legend_handles_labels(),
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=6,
        frameon=False,
        handlelength=2.5,
    )
    fig.text(
        0.5,
        0.015,
        f"仅连接相邻实际采样帧；t={frames[0]['time_s']:g}–{frames[-1]['time_s']:g} s。灰色区域为缩减后消失的车道。",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    fig.subplots_adjust(left=0.12, right=0.985, bottom=0.22, top=0.76)
    save_figure(fig, output, "six_vehicle_trajectories", manifest, dpi)

    complete = [f for f in frames if set(f["states"]) == set(ids)]
    before = [f for f in complete if max(s[0] for s in f["states"].values()) < 640]
    after = [f for f in complete if min(s[0] for s in f["states"].values()) >= 1000]
    if not before or not after:
        manifest["skipped"].append(
            "six_vehicle_snapshots: no actual all-six frame before 640 m and/or after 1000 m"
        )
        return
    selected = (before[-1], after[0])
    physical = source.get("physical", {})
    length, width = physical.get("length"), physical.get("width")
    if not number(length) or not number(width):
        raise ValueError(
            "Snapshot rectangles require actual physical.length and physical.width in input.json"
        )
    manifest["six_case"]["snapshot_times_s"] = [f["time_s"] for f in selected]
    fig, axes = plt.subplots(1, 2, figsize=(12, 2.3))
    span = (
        max(
            max(s[0] for s in f["states"].values()) - min(s[0] for s in f["states"].values())
            for f in selected
        )
        + 30
    )
    for panel, (ax, frame) in enumerate(zip(axes, selected)):
        xmin = min(s[0] for s in frame["states"].values()) - 15
        road(ax, xmin, xmin + span, landmarks=False)
        ax.set_aspect("equal", adjustable="box")
        ax.set_yticks((1.65, 4.95, 8.25), ("0", "1", "2"))
        ax.set_ylabel("车道")
        ax.tick_params(axis="both", labelsize=7.5)
        for index, vehicle in enumerate(ids):
            x, y = frame["states"][vehicle][:2]
            ax.add_patch(
                Rectangle(
                    (x - length, y - width / 2),
                    length,
                    width,
                    facecolor=VEHICLE_COLORS[index],
                    edgecolor="white",
                    linewidth=0.55,
                    zorder=3,
                )
            )
            ax.text(
                x - length / 2,
                y + width / 2 + 0.14,
                vehicle,
                ha="center",
                va="bottom",
                fontsize=7,
                color=VEHICLE_COLORS[index],
            )
        name = "准备区前：全部车头<640 m" if panel == 0 else "缩减后：全部车头≥1000 m"
        ax.set_title(
            f"({chr(97 + panel)}) {name}\nt={frame['time_s']:g} s（实际帧）",
            loc="left",
            pad=12,
            linespacing=1.6,
        )
        if panel == 1:
            ax.set_ylabel("")
            ax.tick_params(axis="y", labelleft=False)
    fig.text(
        0.5,
        0.015,
        f"横纵轴等比例；车体使用实际尺寸 {length:g}×{width:g} m。两面板均取实际采样帧，位置均为车头坐标。",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.29, top=0.64, wspace=0.14)
    save_figure(fig, output, "six_vehicle_snapshots", manifest, dpi)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "summary", type=Path, help="Audited native_comparison summary.json, not a probe result array"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="New directory; existing paths are refused"
    )
    parser.add_argument("--six-case", type=Path, help="Optional actual six-vehicle native case directory")
    parser.add_argument("--font", type=Path, help="Optional Chinese .ttf/.ttc font file")
    parser.add_argument("--dpi", type=int, default=300, help="PNG resolution, at least 300 (default: 300)")
    parser.add_argument("--label", default="", help="Optional figure label, e.g. 旧v6探针（非正式600s矩阵）")
    args = parser.parse_args(argv)
    if args.dpi < 300:
        parser.error("--dpi must be at least 300")
    if args.output.exists():
        parser.error("--output already exists; choose a fresh directory to preserve previous evidence")
    try:
        report = load_summary(args.summary)
        font = configure_style(args.font)
        # Validate optional trace before creating output or emitting partial figures.
        if args.six_case:
            load_six_case(args.six_case)
        args.output.mkdir(parents=True, exist_ok=False)
        manifest = dict(
            summary_path=str(args.summary.resolve()),
            summary_sha256=sha256(args.summary),
            plot_script_sha256=sha256(__file__),
            font=font,
            dpi=args.dpi,
            run_count=len(report["runs"]),
            label=args.label,
            figures=[],
            skipped=[],
            mean_decisions=[],
            interpretation="NOA: detected geometry only; global: Cai-style centralized reference, not full paper reproduction",
            mean_policy="All scenario seeds must exist, pass audit/safety/completion, have matching per-seed provenance, and have defined metrics; otherwise no mean",
            ratio_policy="Rates in [0,1] are multiplied by 100 only on percentage axes",
        )
        plot_performance(report, args.output, manifest, args.dpi, args.label)
        plot_geometry(report, args.output, manifest, args.dpi, args.label)
        if args.six_case:
            plot_six_case(args.six_case, args.output, manifest, args.dpi)
        (args.output / "figure_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"plot_native_comparison: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            dict(
                output=str(args.output.resolve()),
                figures=[f["name"] for f in manifest["figures"]],
                font=font,
                suppressed_means=sum(d["mean"] is None for d in manifest["mean_decisions"]),
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
