"""Finite-cohort, paired-seed Phase5G formation and parameter sensitivity study."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
from uuid import uuid4

from experiments.phase5g import run_phase5g_demo
from experiments.phase5g_schedule import last_scheduled_departure_s
from research.common import ROOT


LANES = (2, 3, 4)
OFFERED_PER_LANE_VEH_H = (300, 600, 900)
SEEDS = (1, 2, 3)
OBSERVATION_AFTER_FINAL_DEPARTURE_S = 200.0


def _case(name, kind, lane_count, offered, seed, *, target_speed=10.0,
          same_lane_gap=30.0):
    interval = round(3600.0 / (offered * lane_count), 1)
    count = 4 * lane_count
    last = last_scheduled_departure_s(
        count, seed, depart_interval_min_s=interval,
        depart_interval_max_s=interval, speed_min_mps=8.0,
        speed_max_mps=12.0, lane_count=lane_count)
    return {
        "name": name, "kind": kind, "lane_count": lane_count,
        "offered_per_lane_veh_h": offered,
        "effective_offered_per_lane_veh_h": 3600.0 / (interval * lane_count),
        "seed": seed, "vehicle_count": count,
        "departure_interval_s": interval,
        "last_scheduled_departure_s": last,
        "duration_s": round(last + OBSERVATION_AFTER_FINAL_DEPARTURE_S, 1),
        "target_speed_mps": target_speed,
        "middle_lane_offset_m": 15.0,
        "same_lane_gap_m": same_lane_gap,
    }


def planned_cases():
    cases = [
        _case(f"lanes{lanes}_q{flow}_seed{seed}", "lane_flow", lanes,
              flow, seed)
        for lanes in LANES for flow in OFFERED_PER_LANE_VEH_H
        for seed in SEEDS
    ]
    cases.extend(
        _case(f"sensitivity_{name}_seed{seed}", "parameter", 3, 600,
              seed, target_speed=speed, same_lane_gap=gap)
        for name, speed, gap in (("speed8", 8.0, 30.0),
                                 ("speed12", 12.0, 30.0),
                                 ("gap24", 10.0, 24.0),
                                 ("gap36", 10.0, 36.0))
        for seed in SEEDS
    )
    return cases


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _observed(case, outer):
    validation = _read_json(outer / "validation.json")
    detection = _read_json(outer / "case" / "detection.json")["default"]
    variant = validation["variant"]
    summary = variant["summary"]
    formed = detection["formed_time_s"]
    last_actual = detection["last_actual_departure_s"]
    return {
        **case, "status": validation["status"], "source": str(outer),
        "formation_success": detection["formation_success"],
        "formation_time_s": formed,
        "formation_delay_after_last_departure_s": (
            None if formed is None or last_actual is None else
            round(formed - last_actual, 10)),
        "censored_at_recording_end": not detection["formation_success"],
        "last_actual_departure_s": last_actual,
        "safety_passed": detection["safety_passed"],
        "recording_valid": detection["recording_valid"],
        "collision_count": summary["collision_count"],
        "completed_lane_changes": summary["completed_lane_changes"],
        "formation_lane_changes": summary["formation_lane_changes"],
        "final_lane_counts": summary["final_lane_counts"],
        "max_lattice_error_m": max(
            detection["max_outer_alignment_error_m"],
            detection["max_middle_offset_error_m"],
            detection["max_same_lane_gap_error_m"]),
        "max_component_speed_spread_mps":
            detection["max_component_speed_spread_mps"],
        "failure_reasons": detection["failure_reasons"],
    }


def _run_case(case, root):
    try:
        outer = run_phase5g_demo(
            vehicle_count=case["vehicle_count"], seed=case["seed"],
            target_speed_mps=case["target_speed_mps"],
            duration_s=case["duration_s"],
            output_base=root / case["name"], live=False,
            lane_count=case["lane_count"], straight_road=True,
            depart_interval_min_s=case["departure_interval_s"],
            depart_interval_max_s=case["departure_interval_s"],
            middle_lane_offset_m=case["middle_lane_offset_m"],
            same_lane_gap_m=case["same_lane_gap_m"],
        )
        return _observed(case, outer)
    except Exception as error:
        return {**case, "status": "error",
                "error": f"{type(error).__name__}: {error}"}


def run_matrix(output_base=None, *, cases=None, workers=3):
    base = (ROOT / "results" / "phase5g" / "formation_matrix"
            if output_base is None else Path(output_base))
    root = base / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                   + "_" + uuid4().hex[:8])
    root.mkdir(parents=True, exist_ok=False)
    cases = planned_cases() if cases is None else list(cases)
    protocol = {
        "schema": "phase5g_formation_matrix_v1",
        "cases": cases,
        "formation_criterion": "ordered physical geometry for >=1 s",
        "observation_after_final_scheduled_departure_s":
            OBSERVATION_AFTER_FINAL_DEPARTURE_S,
        "nominal_flow_scope": "finite-cohort offered arrivals; no exits or throughput estimate",
    }
    (root / "protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool, (root / "results.jsonl").open(
            "a", encoding="utf-8") as stream:
        futures = {pool.submit(_run_case, case, root): case for case in cases}
        for future in as_completed(futures):
            case = futures[future]
            try:
                row = future.result()
            except Exception as error:
                row = {**case, "status": "error",
                       "error": f"{type(error).__name__}: {error}"}
            results.append(row)
            stream.write(json.dumps(row, ensure_ascii=False,
                                    allow_nan=False) + "\n")
            stream.flush()
    groups = {}
    for row in results:
        key = (row["kind"], row["lane_count"],
               row["offered_per_lane_veh_h"], row["target_speed_mps"],
               row["same_lane_gap_m"])
        groups.setdefault(key, []).append(row)
    aggregates = []
    for key, rows in sorted(groups.items()):
        delays = [row["formation_delay_after_last_departure_s"]
                  for row in rows if row.get("formation_success")]
        aggregates.append({
            "kind": key[0], "lane_count": key[1],
            "offered_per_lane_veh_h": key[2],
            "target_speed_mps": key[3], "same_lane_gap_m": key[4],
            "attempts": len(rows),
            "formation_successes": sum(row.get("formation_success") is True
                                       for row in rows),
            "safe_runs": sum(row.get("safety_passed") is True for row in rows),
            "valid_recordings": sum(row.get("recording_valid") is True
                                    for row in rows),
            "median_formation_delay_s": median(delays) if delays else None,
        })
    summary = {"schema": "phase5g_formation_matrix_summary_v1",
               "root": str(root), "case_count": len(cases),
               "completed_count": sum(row["status"] == "completed"
                                      for row in results),
               "aggregates": aggregates}
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"matrix_root": str(root),
                      "completed_count": summary["completed_count"],
                      "case_count": len(cases)}, ensure_ascii=False), flush=True)
    return root


if __name__ == "__main__":
    run_matrix()
