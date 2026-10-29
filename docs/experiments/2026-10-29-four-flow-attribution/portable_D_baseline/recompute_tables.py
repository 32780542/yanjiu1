"""Regenerate compact D100 tables from losslessly preserved evaluator outputs.

No SUMO or evaluator run is performed. The existing frozen measures and original
five-seed aggregation are reused; recovery numerators/denominators are summed.
"""
import csv
import gzip
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
FLOWS = (500, 750, 1000, 1500)
MODES = ("noa", "formation", "transform")


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()} for row in rows)


def build_tables(base=BASE):
    attr = read_gz(base / "data/attribution_summary.json.gz")
    natives = {flow: read_gz(base / f"data/native_flow_{flow}.json.gz") for flow in FLOWS}
    recoveries = {flow: read_gz(base / f"data/recovery_flow_{flow}.json.gz") for flow in FLOWS}
    traffic, structure, recovery, straight = [], [], [], []
    for flow in FLOWS:
        n = natives[flow]
        reduction = next(r for r in attr["attribution_means"] if r["flow_veh_h_lane"] == flow)
        for mode in MODES:
            a = next(r for r in attr["run_means"] if r["flow_veh_h_lane"] == flow and r["scenario"] == "lane_drop" and r["mode"] == mode)
            layer = next(r for r in n["run_means"] if r["scenario"] == "lane_drop" and r["mode"] == mode)
            control = next((r for r in attr["run_means"] if r["flow_veh_h_lane"] == flow and r["scenario"] == "straight3" and r["mode"] == mode), None)
            effect = next((r for r in attr["scenario_effect_means"] if r["flow_veh_h_lane"] == flow and r["mode"] == mode), None)
            if a["attempted_n"] != 5 or a["eligible_n"] != 5 or not a["group_eligible"]:
                raise ValueError("D100 row is not a complete eligible five-seed group")
            traffic.append(dict(
                flow_veh_h_lane=flow, mode=mode, attempted_seeds=5, eligible_seeds=5,
                drop_TT_s=a["mean_travel_time_s_mean"],
                region_window_speed_mps=a["region_mean_speed_mps_mean"],
                drop_fuel_g_km=layer["fuel_g_per_km_mean"],
                drop_main_640_1100_s=a["mean_segment_640_1100_s_mean"],
                same_mode_straight_TT_s=control["mean_travel_time_s_mean"] if control else None,
                same_mode_straight_main_640_1100_s=control["mean_segment_640_1100_s_mean"] if control else None,
                main_drop_minus_straight_s=effect["additional_mean_segment_640_1100_s_mean"] if effect else None,
                main_NOA_minus_transform_reduction_s=reduction["reduction_mean_segment_640_1100_s_mean"] if mode == "transform" else None,
                region_low_speed_vehicle_s=a["region_low_speed_vehicle_s_mean"],
                region_low_speed_fraction=a["region_low_speed_fraction_mean"],
                flow_1000m_veh_h=a["flow_1000m_veh_h_mean"],
            ))
            row = dict(flow_veh_h_lane=flow, mode=mode, attempted_seeds=5, eligible_seeds=5)
            members = sorted((r for r in n["runs"] if r["scenario"] == "lane_drop" and r["mode"] == mode), key=lambda r: r["seed"])
            if [r["seed"] for r in members] != [1, 2, 3, 4, 5]:
                raise ValueError("Unexpected physical seed group")
            for region in ("upstream", "downstream"):
                for field in ("formation_participation_rate", "stable_participation_rate", "mean_multilayer_size", "peak_multilayer_size"):
                    row[region + "_" + field + "_mean"] = layer[region + "_" + field + "_mean"]
                    row[region + "_" + field + "_n"] = layer[region + "_" + field + "_n"]
                row[region + "_peak_by_seed"] = [r.get(region + "_peak_multilayer_size") for r in members]
            structure.append(row)
            events = [r for r in recoveries[flow]["runs"] if r["scenario"] == "lane_drop" and r["mode"] == mode]
            row = dict(flow_veh_h_lane=flow, mode=mode, seeds=5)
            for key in ("subjects", "recovered", "censored"):
                row["all_adjusting_" + key] = sum(r[key] for r in events)
                row["upstream_formed_" + key] = sum(r["upstream_formed"][key] for r in events)
            recovery.append(row)
        for mode in ("noa", "transform"):
            a = next(r for r in attr["run_means"] if r["flow_veh_h_lane"] == flow and r["scenario"] == "straight3" and r["mode"] == mode)
            nrow = next(r for r in n["run_means"] if r["scenario"] == "straight3" and r["mode"] == mode)
            members = sorted((r for r in n["runs"] if r["scenario"] == "straight3" and r["mode"] == mode), key=lambda r: r["seed"])
            row = dict(flow_veh_h_lane=flow, mode=mode, seeds=5,
                       TT_s=a["mean_travel_time_s_mean"], region_window_speed_mps=a["region_mean_speed_mps_mean"],
                       fuel_g_km=nrow["fuel_g_per_km_mean"], main_640_1100_s=a["mean_segment_640_1100_s_mean"])
            for field in ("formation_participation_rate", "stable_participation_rate", "mean_multilayer_size", "peak_multilayer_size"):
                row["whole_" + field + "_mean"] = nrow["whole_" + field + "_mean"]
                row["whole_" + field + "_n"] = nrow["whole_" + field + "_n"]
            row["whole_peak_by_seed"] = [r.get("whole_peak_multilayer_size") for r in members]
            straight.append(row)
    return dict(traffic_and_attribution=traffic, formation_quality=structure,
                recovery_counts=recovery, straight_controls=straight)


def definitions():
    return dict(
        scope="D baseline: 4 flows x 5 seeds x (straight NOA/transform + lane-drop NOA/formation/transform), 100 cases. Main tables describe lane_drop.",
        modes=dict(noa="NOA; detected geometry is not controlled formation", formation="Formation plus ordinary merge ablation", transform="Distributed formation plus lane-drop transform"),
        averaging="Traffic, fuel and participation rows reuse the original arithmetic mean of five per-seed values. Every run is safe/completed/audit eligible. Geometry means retain original per-metric n; undefined geometry is not zero.",
        speed="region_window_speed_mps is measured vehicle-time-weighted speed in 800<=x<1000 m over [100,600) s, averaged across seeds. It is not whole-route mean speed.",
        TT="drop_TT_s / TT_s: entered-to-exited travel time; excludes entry waiting. Seconds, averaged across five run means.",
        fuel="drop_fuel_g_km / fuel_g_km: original SUMO fuel_abs mg / actual route distance m, numerically g/km. Five run ratios averaged; no aerodynamic fuel assumption.",
        main_segment="640–1100 m duration from measured first crossings interpolated only across normal adjacent 0.1s frames. main_drop_minus_straight_s is same-mode drop minus straight, positive is added delay.",
        reduction="main_NOA_minus_transform_reduction_s appears only on transform rows: (NOA drop-straight) minus (transform drop-straight). Positive is reduction; negative is worse. Reuses existing attribution metric.",
        formation_missing_straight="The D100 design has no formation straight cases; same-mode straight time and main difference are undefined for formation and remain blank/null.",
        low_speed="region_low_speed_vehicle_s: integral of count(v<5m/s) in 800<=x<1000 m over [100,600) s; mean of five runs. region_low_speed_fraction divides by regional vehicle-seconds.",
        flow="flow_1000m_veh_h: first measured 1000m crossings in inclusive [100,600] s / 500 s * 3600. An observed count, not saturation capacity.",
        regions="Lane-drop upstream: 3 lanes, [0,640) m; downstream: 2 lanes, [1000,1200) m. Straight whole: 3 lanes, [0,1200) m. No fixed lane-count whole-road metric spans the lane drop.",
        participation="formation_participation_rate_mean is mean confirmed multilayer vehicle-seconds / all region vehicle-seconds; confirmed >=2 full layers. Fractions 0–1 (multiply by 100 for percent). Stable participation adds the frozen 5s stability hold.",
        mean_size="mean_multilayer_size_mean is the original mean of defined per-run group-time conditional mean sizes. It conditions on actual confirmed multilayer group seconds; n reports seeds with a defined group mean.",
        peak="peak_multilayer_size_mean is the original mean of defined per-run peaks; n is its number of defined seeds. peak_by_seed preserves the actual original peaks in seed order 1–5; null means no qualifying structure, not zero-sized formation.",
        recovery="Counts sum the existing five per-run records. all_adjusting_subjects is the denominator; recovered is observed two-lane confirmed membership; censored remains explicit. upstream_formed_* restricts to previously confirmed three-lane membership before adjustment; it distinguishes recovery from new formation. NOA remains detected geometry only.",
        recomputation="recompute_tables.py reproduces the compact tables from exact compressed original evaluator JSON. The raw case archive also preserves exact input/result/trips JSON for independent travel/fuel/request checks. Recomputing gates/layers from positions requires the original 0.1s position files bound by hashes in case_index.json and audits; those 374.5MB traces are not duplicated here.",
    )


def main():
    tables = build_tables()
    dest = BASE / "tables"
    dest.mkdir(exist_ok=True)
    for name, rows in tables.items():
        write_csv(dest / (name + ".csv"), rows)
    write_json(dest / "results.json", tables)
    write_json(dest / "column_definitions.json", definitions())
    lines = ["D100 lane-drop travel time (s); arithmetic mean of 5 seed means", "flow\tNOA\tformation\ttransform"]
    for flow in FLOWS:
        values = [next(r["drop_TT_s"] for r in tables["traffic_and_attribution"] if r["flow_veh_h_lane"] == flow and r["mode"] == mode) for mode in MODES]
        lines.append(str(flow) + "\t" + "\t".join(f"{v:.9f}" for v in values))
    (dest / "TT.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(dict(tables=str(dest), traffic_rows=len(tables["traffic_and_attribution"]), structure_rows=len(tables["formation_quality"]), recovery_rows=len(tables["recovery_counts"]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
