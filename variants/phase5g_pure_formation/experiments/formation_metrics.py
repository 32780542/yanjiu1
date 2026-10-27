"""只根据保存的物理轨迹评价编队；评价结果不参与车辆决策。"""

import gzip
import json
import math
from pathlib import Path
from statistics import mean, pstdev

from experiments.phase5_detection import (
    _component_measurement, _expected_lane_counts, _physical_rows, detect_frames,
)


def final_errors(states, lane_count, gap, target_speed=10.0):
    """分别量化同车道层距、同相位对齐、相邻相位偏移及速度。"""
    rows = _physical_rows(states, 3.3, lane_count)
    geometry = _component_measurement(list(rows.values()),
        middle_offset_m=15.0, same_lane_gap_m=gap,
        position_tolerance_m=2.0, speed_tolerance_mps=1.0,
        lane_count=lane_count)
    errors = {name: geometry[name] for name in (
        "max_same_lane_gap_error_m", "max_outer_alignment_error_m",
        "max_middle_offset_error_m")}
    counts = geometry["lane_counts"]
    complete = counts == _expected_lane_counts(len(rows), lane_count)
    if max(counts) < 2:
        errors["max_same_lane_gap_error_m"] = None
    if not all(counts):
        errors["max_middle_offset_error_m"] = None
        if lane_count > 2:
            errors["max_outer_alignment_error_m"] = None
    speeds = [math.hypot(s["vx_mps"], s.get("vy_mps", 0.0))
              for s in states.values()]
    return {**errors, "max_geometry_error_m":
            max(errors.values()) if complete and all(v is not None for v in errors.values()) else None,
            "complete_lane_occupancy": complete,
            "speed_std_mps": pstdev(speeds), "mean_speed_mps": mean(speeds),
            "speed_spread_mps": max(speeds)-min(speeds),
            "max_target_speed_error_mps": max(abs(v-target_speed) for v in speeds),
            "lane_counts": geometry["lane_counts"]}


def evaluate_run(directory):
    """从压缩轨迹重新计算形成时间和终态误差，支持独立复算。"""
    directory = Path(directory)
    inputs = json.loads((directory / "input.json").read_text(encoding="utf-8"))
    incidents = json.loads((directory / "incidents.json").read_text(encoding="utf-8"))
    with gzip.open(directory / "trajectory.jsonl.gz", "rt", encoding="utf-8") as f:
        frames = [json.loads(line) for line in f]
    frames[-1]["departures"] = inputs["departures"]
    case = inputs["case"]
    detection = detect_frames(frames, d=15.0, lane_count=case["lane_count"],
        same_lane_gap_m=case["same_lane_gap_m"], formation_deadline_s=None,
        hold_s=None, incidents=incidents)
    last = detection["last_actual_departure_s"]
    formed = detection["formed_time_s"]
    final = final_errors(frames[-1]["states"], case["lane_count"],
                         case["same_lane_gap_m"], case["target_speed_mps"])
    return {**case, "status": "completed", "frame_count": len(frames),
        "recording_end_s": frames[-1]["time_s"],
        "last_actual_departure_s": last,
        "formation_success": detection["formation_success"],
        "formation_time_s": formed,
        "formation_delay_s": None if formed is None else round(formed-last, 8),
        "recording_valid": detection["recording_valid"],
        "safety_passed": detection["safety_passed"],
        "collision_pairs": len({tuple(row["actors"]) for row in detection["collision_events"]}),
        "road_departure_actors": len({row["actor"] for row in detection["road_departure_events"]}),
        "completed_lane_changes": inputs["completed_lane_changes"],
        "max_entry_delay_s": max(row["actual_departure_s"]-row["scheduled_departure_s"]
                                 for row in inputs["departures"].values()),
        "failure_reasons": detection["failure_reasons"],
        **final}
