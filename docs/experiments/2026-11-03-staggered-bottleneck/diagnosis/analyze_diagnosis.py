"""Read sealed public evidence only; no simulator/controller imports or execution."""
import csv
import gzip
import hashlib
import json
import math
import statistics
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
OLD = ROOT / "docs/experiments/2026-10-30-rule-trials"
CRUISE = 28.8
T_CRUISE = 1200 / CRUISE
T_PHYSICAL = 1200 / 33.3
CAPACITY_REFERENCE = 2 * 3600 * CRUISE / 30
PROFILES = {"TM_noa": "heldout_tm_noa50", "TM_transform": "heldout_tm_transform50"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b):
    assert math.isclose(a, b, abs_tol=1e-7, rel_tol=1e-10), (a, b)


def quantile(values, p):
    """Linear interpolation at index (n-1)*p; quantiles are descriptive only."""
    ordered = sorted(values)
    x = (len(ordered) - 1) * p
    lo = int(x)
    hi = min(len(ordered) - 1, lo + 1)
    return ordered[lo] + (x - lo) * (ordered[hi] - ordered[lo])


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def evidence_blobs(path):
    """Stream the small public package; ignore flags/full-position indices."""
    blobs = {}
    with tarfile.open(path, "r|gz") as t:
        first = next(iter(t))
        assert first.name == "index.json"
        index = json.load(t.extractfile(first))
        wanted = {c["files"][n] for c in index["cases"]
                  for n in ("input.json", "result.json", "trips.json")}
        for m in t:
            h = m.name.removeprefix("blobs/")
            if h in wanted:
                raw = t.extractfile(m).read()
                assert hashlib.sha256(raw).hexdigest() == h
                blobs[h] = json.loads(raw)
    assert set(blobs) == wanted
    return index, blobs


source_paths = [OLD / "traffic_evidence/per_case.csv", OLD / "traffic_evidence/case_index.json"]
traffic = list(csv.DictReader(source_paths[0].open(encoding="utf-8-sig")))
traffic = [r for r in traffic if r["profile"] in PROFILES]
lookup = {r["case_dir"]: r for r in traffic}
assert len(traffic) == len(lookup) == 100
records = []
arrivals = {}
for profile, folder in PROFILES.items():
    package = OLD / "evidence" / folder / "bundle.tar.gz"
    source_paths.append(package)
    index, blobs = evidence_blobs(package)
    for c in index["cases"]:
        r = lookup[c["run_dir"]]
        inp, result, trips = [blobs[c["files"][n]] for n in ("input.json", "result.json", "trips.json")]
        assert result["safe"] and result["all_completed"] and result["collisions"] == result["teleports"] == 0
        assert c["files"]["source/noa/native_rules.py"] == "65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317"
        assert c["files"]["source/experiments/native_sumo.py"] == "bc22273fa224206e03dd896fb7b386a5d28ce3526fddebfa6bf7d7c93caaa1d1"
        n = len(trips)
        assert n == len(inp["arrivals"]) == result["requested"] == result["departed"] == result["completed"]
        key = (result["flow_veh_h_lane"], result["seed"], result["scenario"])
        if key in arrivals:
            assert arrivals[key] == inp["arrivals"]
        else:
            arrivals[key] = inp["arrivals"]
        tt = [x["exited_s"] - x["entered_s"] for x in trips]
        system = [x["exited_s"] - x["requested_s"] for x in trips]
        wait = [x["entered_s"] - x["requested_s"] for x in trips]
        for k, values in (("mean_travel_time_s", tt), ("mean_system_time_s", system), ("mean_entry_wait_s", wait)):
            close(statistics.mean(values), result[k])
            close(result[k], float(r[k]))
        actual_entries = sum(0 <= x["entered_s"] < 600 for x in trips)
        row = dict(profile=profile, flow_veh_h_lane=result["flow_veh_h_lane"], seed=result["seed"], scenario=result["scenario"],
                   requested=n, departed_total=result["departed"], completed=n, entered_before_600=actual_entries,
                   actual_request_total_veh_h=n * 6, actual_request_per_upstream_lane_veh_h=n * 2,
                   actual_entry_total_veh_h=actual_entries * 6,
                   actual_request_over_equilibrium_reference_pct=n * 6 / CAPACITY_REFERENCE * 100,
                   mean_travel_time_s=statistics.mean(tt), mean_system_time_s=statistics.mean(system),
                   mean_entry_wait_s=statistics.mean(wait), total_entry_wait_vehicle_s=sum(wait),
                   mean_net_road_excess_vs_cruise_s=statistics.mean(tt) - T_CRUISE,
                   total_net_road_excess_vs_cruise_vehicle_s=sum(tt) - n * T_CRUISE,
                   total_net_system_excess_vs_cruise_vehicle_s=sum(system) - n * T_CRUISE,
                   total_positive_road_excess_vs_cruise_vehicle_s=sum(max(0.0, x - T_CRUISE) for x in tt),
                   total_negative_road_excess_vs_cruise_vehicle_s=sum(min(0.0, x - T_CRUISE) for x in tt),
                   mean_net_road_excess_vs_observed_isolated_41_7_s=statistics.mean(tt) - 41.7,
                   sum_sumo_time_loss_vehicle_s=sum(x["time_loss_s"] for x in trips),
                   sum_sumo_waiting_vehicle_s=sum(x["waiting_s"] for x in trips),
                   min_vehicle_tt_s=min(tt), max_vehicle_tt_s=max(tt),
                   p95_vehicle_tt_s=quantile(tt, .95), p99_vehicle_tt_s=quantile(tt, .99),
                   vehicles_tt_strictly_above_60_s=sum(x > 60.0 for x in tt),
                   actual_end_s=result["actual_end_s"],
                   region_density_veh_km_lane=float(r["region_density_veh_km_lane"]),
                   region_mean_speed_mps=float(r["region_mean_speed_mps"]),
                   region_low_speed_vehicle_s=float(r["region_low_speed_vehicle_s"]),
                   region_low_speed_fraction_pct=float(r["region_low_speed_fraction"]) * 100,
                   region_max_simultaneous_low_speed=int(r["region_max_simultaneous_low_speed"]),
                   flow_1000m_veh_h=float(r["flow_1000m_veh_h"]),
                   mean_segment_100_600_s=float(r["mean_segment_100_600_s"]),
                   mean_segment_640_1100_s=float(r["mean_segment_640_1100_s"]),
                   fuel_g_per_km=float(r["fuel_g_per_km"]),
                   case_dir=r["case_dir"], source_trips_sha256=c["files"]["trips.json"])
        records.append(row)

# Reconstruct low-speed clock duration and published exposure from compressed ledgers.
case_index = json.loads((OLD / "traffic_evidence/case_index.json").read_text(encoding="utf-8"))
selected = {r["case_dir"]: r for r in records if r["scenario"] == "lane_drop"}
for profile in PROFILES:
    package = OLD / "traffic_evidence" / ("traffic_" + profile + ".tar.gz")
    source_paths.append(package)
    cases = {c["case_id"]: selected[c["case_dir"]] for c in case_index
             if c["profile"] == profile and c["scenario"] == "lane_drop"}
    with tarfile.open(package, "r|gz") as t:
        for m in t:
            if not m.name.endswith("/region_steps.jsonl.gz"):
                continue
            case_id = m.name.split("/")[1]
            if case_id not in cases:
                continue
            low_seconds = exposure = speed_sum = vehicle_s = longest = streak = 0.0
            with gzip.GzipFile(fileobj=t.extractfile(m)) as f:
                assert json.loads(f.readline()) == ["time_s", "end_s", "n", "low_speed_n", "speed_sum_mps"]
                for line in f:
                    start, end, n, low, speed = json.loads(line)
                    dt = max(0.0, min(end, 600.0) - max(start, 100.0))
                    if not dt:
                        continue
                    exposure += dt * low
                    vehicle_s += dt * n
                    speed_sum += dt * speed
                    if low:
                        low_seconds += dt
                        streak += dt
                        longest = max(longest, streak)
                    else:
                        streak = 0.0
            row = cases[case_id]
            close(exposure, row["region_low_speed_vehicle_s"])
            close(speed_sum / vehicle_s, row["region_mean_speed_mps"])
            close(vehicle_s / 500 / .6, row["region_density_veh_km_lane"])
            row["region_any_low_speed_clock_s"] = low_seconds
            row["region_longest_any_low_speed_spell_s"] = longest

# Keep columns uniform across both roads (straight3 has zero slow exposure here).
for row in records:
    row.setdefault("region_any_low_speed_clock_s", 0.0)
    row.setdefault("region_longest_any_low_speed_spell_s", 0.0)
    assert row["scenario"] == "lane_drop" or row["region_low_speed_vehicle_s"] == 0.0
records.sort(key=lambda r: (r["flow_veh_h_lane"], r["profile"], r["scenario"], r["seed"]))
write_csv("per_case.csv", records)

means = []
for flow in [500, 750, 1000, 1250, 1500]:
    for profile in PROFILES:
        rows = [r for r in records if r["flow_veh_h_lane"] == flow and r["profile"] == profile and r["scenario"] == "lane_drop"]
        straight = [r for r in records if r["flow_veh_h_lane"] == flow and r["profile"] == profile and r["scenario"] == "straight3"]
        assert len(rows) == len(straight) == 5
        row = dict(profile=profile, flow_veh_h_lane=flow, seeds=5)
        for k in rows[0]:
            if k not in {"profile", "flow_veh_h_lane", "seed", "scenario", "case_dir", "source_trips_sha256"}:
                row[k] = statistics.mean(r[k] for r in rows)
        row["drop_minus_straight_mean_tt_s"] = row["mean_travel_time_s"] - statistics.mean(r["mean_travel_time_s"] for r in straight)
        row["road_excess_over_tt_pct"] = row["mean_net_road_excess_vs_cruise_s"] / row["mean_travel_time_s"] * 100
        row["max_seed_region_low_speed_vehicle_s"] = max(r["region_low_speed_vehicle_s"] for r in rows)
        row["max_seed_mean_tt_s"] = max(r["mean_travel_time_s"] for r in rows)
        row["min_seed_mean_tt_s"] = min(r["mean_travel_time_s"] for r in rows)
        row["total_low_speed_vehicle_s_all_five_seeds"] = sum(r["region_low_speed_vehicle_s"] for r in rows)
        row["total_net_road_excess_all_five_seeds_vehicle_s"] = sum(r["total_net_road_excess_vs_cruise_vehicle_s"] for r in rows)
        means.append(row)
write_csv("flow_means.csv", means)

load_curve = []
for flow in [500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2304, 2500]:
    load_curve.append(dict(flow_veh_h_upstream_lane=flow, expected_total_demand_veh_h=3 * flow,
                           downstream_per_lane_if_balanced_veh_h=3 * flow / 2,
                           two_lane_equilibrium_reference_veh_h=CAPACITY_REFERENCE,
                           expected_load_vs_equilibrium_reference_pct=3 * flow / CAPACITY_REFERENCE * 100,
                           existing_five_seed_evidence=flow <= 1500))
write_csv("demand_reference_curve.csv", load_curve)
source_paths.extend([Path(__file__).resolve(), ROOT / "variants/phase5g_pure_formation/experiments/native_sumo.py",
                     ROOT / "variants/phase5g_pure_formation/noa/native_rules.py",
                     ROOT / "variants/phase5g_pure_formation/run_native_flow.py",
                     Path("D:/matlab_huipu_2000/mainmain.m"), Path("D:/matlab_huipu_2000/mainmain_REF.m"),
                     Path("D:/matlab_huipu_2000/RUN_result_draw_1.m")])
audit = dict(repository_head_observed_before_analysis="177f7a32088fb69efcc94d9acb72863e7e00e787",
             case_count=len(records), lane_drop_case_count=len(selected), paired_shared_arrivals=len(arrivals),
             safe_completed_cases=100, ledger_reconstructions=50,
             note="No simulator, controller, network or original run-directory reads. All delay totals are signed net excess, not positive-part delay.",
             constants=dict(cruise_mps=CRUISE, route_length_m=1200, cruise_reference_s=T_CRUISE,
                            absolute_speed_ceiling_lower_bound_s=T_PHYSICAL,
                            two_lane_equilibrium_reference_veh_h=CAPACITY_REFERENCE,
                            upstream_per_lane_equilibrium_reference_veh_h=CAPACITY_REFERENCE / 3),
             source_sha256={str(p): digest(p) for p in source_paths})
(OUT / "verification.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(cases=len(records), ledgers=len(selected), shared_inputs=len(arrivals), output=str(OUT)), ensure_ascii=False))
