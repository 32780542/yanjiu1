"""Recheck component-wide join flags against concurrent local lane changes."""

from itertools import combinations
import json
from pathlib import Path
import sys


LAYER_RADIUS_M = 90.0
PHYSICAL_HAZARDS = {
    "collision_detected", "road_departure_detected", "teleport_detected",
    "nonphysical_jump_detected",
}


def overlapping_pairs(joiners, positions):
    return [
        [left, right]
        for left, right in combinations(sorted(joiners), 2)
        if abs(positions[left] - positions[right])
        <= LAYER_RADIUS_M + 1e-9
    ]


def _event_maneuvers(trace_path, times):
    events = {}
    with trace_path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            states = record["initial"]
            time = round(next(iter(states.values()))["time_s"], 10)
            if time in times:
                positions = {key: state["x_m"] for key, state in states.items()}
                changing = {
                    key for key, decision in record["decisions"].items()
                    if decision["memory"]["plan"] is not None
                }
                events[time] = (positions, changing)
                if len(events) == len(times):
                    break
    if set(events) != times:
        raise ValueError(f"missing conflict frames: {sorted(times - set(events))}")
    return events


def audit_case(row):
    source = Path(row["source"])
    detection = json.loads((source / "case" / "detection.json").read_text(
        encoding="utf-8"))["default"]
    events = detection["admission_conflicts"]
    times = {round(event["time_s"], 10) for event in events}
    frames = (_event_maneuvers(source / "case" / "trace.jsonl", times)
              if times else {})
    witnesses = []
    for event in events:
        time = round(event["time_s"], 10)
        positions, changing = frames[time]
        pair_rows = overlapping_pairs(event["joining_actors"], positions)
        active_pairs = [pair for pair in pair_rows
                        if all(actor in changing for actor in pair)]
        witnesses.append({
            "time_s": event["time_s"],
            "joining_actors": event["joining_actors"],
            "minimum_joiner_separation_m": min(
                abs(positions[left] - positions[right])
                for left, right in combinations(event["joining_actors"], 2)),
            "overlapping_pairs": pair_rows,
            "active_lane_change_pairs": active_pairs,
        })
    local_conflicts = sum(bool(event["overlapping_pairs"]) for event in witnesses)
    active_conflicts = sum(bool(event["active_lane_change_pairs"])
                           for event in witnesses)
    reasons = set(row["failure_reasons"])
    corrected_safe = (row["safety_passed"] or bool(events)
                      and not active_conflicts
                      and not (reasons & PHYSICAL_HAZARDS))
    return {
        "name": row["name"], "source": row["source"],
        "original_safety_passed": row["safety_passed"],
        "component_conflict_frames": len(events),
        "overlapping_window_conflict_frames": local_conflicts,
        "active_lane_change_conflict_frames": active_conflicts,
        "active_lane_change_window_safety_passed": bool(corrected_safe),
        "witnesses": witnesses,
    }


def audit_matrix(root):
    root = Path(root).resolve()
    rows = [json.loads(line) for line in
            (root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(rows) != 39 or any(row["status"] != "completed" for row in rows):
        raise ValueError("audit requires 39 completed matrix cases")
    cases = [audit_case(row) for row in rows]
    report = {
        "schema": "phase5g_local_admission_audit_v3",
        "window_radius_m": LAYER_RADIUS_M,
        "criterion": "two active lane-change plans within 90 m",
        "original_safe_runs": sum(row["original_safety_passed"] for row in cases),
        "active_lane_change_window_safe_runs": sum(
            row["active_lane_change_window_safety_passed"] for row in cases),
        "cases": cases,
    }
    with (root / "local_admission_audit_v3.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2,
                  allow_nan=False)
        stream.write("\n")
    return report


if __name__ == "__main__":
    report = audit_matrix(sys.argv[1])
    print(json.dumps({key: report[key] for key in
                      ("original_safe_runs", "active_lane_change_window_safe_runs")}))
