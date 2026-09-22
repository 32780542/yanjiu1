"""Independent offline evaluation of dynamic local formation components.

The detector consumes recorded physical states and factual experiment evidence.
It deliberately imports no controller module and never feeds its measurements
back into an online decision.
"""

from itertools import combinations
import math
from typing import Mapping


_EPS = 1e-8
_TIME_EPS = 1e-12
_LANE_COUNT = 3
_BODY_LENGTH_M = 4.0
_BODY_WIDTH_M = 1.8


def _finite(name, value, *, nonnegative=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    invalid_range = value < 0 if nonnegative else value <= 0
    if invalid_range:
        qualifier = "nonnegative" if nonnegative else "positive"
        raise ValueError(f"{name} must be {qualifier}")
    return float(value)


def _lateral_membership(y_m, heading_rad, lane_width_m):
    lateral_half = (0.5 * _BODY_LENGTH_M * abs(math.sin(heading_rad))
                    + 0.5 * _BODY_WIDTH_M * abs(math.cos(heading_rad)))
    body_lower = y_m - lateral_half
    body_upper = y_m + lateral_half
    on_road = body_lower >= 0.0 and body_upper <= _LANE_COUNT * lane_width_m
    lane = next((
        index for index in range(_LANE_COUNT)
        if body_lower >= index * lane_width_m
        and body_upper <= (index + 1) * lane_width_m
    ), None) if on_road else None
    return lane, on_road


def _physical_rows(states, lane_width_m):
    rows = {}
    for key, state in states.items():
        if type(key) is not str or not isinstance(state, Mapping):
            raise ValueError("frame states must map string actors to physical states")
        try:
            x_m = float(state["x_m"])
            y_m = float(state["y_m"])
            vx_mps = float(state["vx_mps"])
            vy_mps = float(state.get("vy_mps", 0.0))
            heading_rad = float(state.get("heading_rad", 0.0))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{key}: invalid physical state") from error
        if not all(math.isfinite(value)
                   for value in (x_m, y_m, vx_mps, vy_mps, heading_rad)):
            raise ValueError(f"{key}: physical state must be finite")
        lane, on_road = _lateral_membership(y_m, heading_rad, lane_width_m)
        rows[key] = {
            "key": key,
            "x_m": x_m,
            "y_m": y_m,
            "lane": lane,
            "on_road": on_road,
            "speed_mps": math.hypot(vx_mps, vy_mps),
        }
    return rows


def _physical_components(rows, component_gap_m):
    ordered = sorted(rows.values(), key=lambda row: (-row["x_m"], row["key"]))
    groups = []
    for row in ordered:
        if not groups or groups[-1][-1]["x_m"] - row["x_m"] > component_gap_m:
            groups.append([row])
        else:
            groups[-1].append(row)
    return groups


def _expected_lane_counts(count):
    complete, remainder = divmod(count, 3)
    return [complete + (remainder >= 2), complete, complete + (remainder >= 1)]


def _maximum(values):
    return max(values, default=0.0)


def _component_measurement(rows, *, middle_offset_m, same_lane_gap_m,
                           position_tolerance_m, speed_tolerance_mps):
    members = sorted(row["key"] for row in rows)
    lane_rows = {
        lane: sorted(
            (row for row in rows if row["lane"] == lane),
            key=lambda row: (-row["x_m"], row["key"]),
        )
        for lane in range(_LANE_COUNT)
    }
    lane_counts = [len(lane_rows[lane]) for lane in range(_LANE_COUNT)]
    off_road = [row["key"] for row in rows if not row["on_road"]]
    unresolved_lane = [
        row["key"] for row in rows
        if row["on_road"] and row["lane"] is None
    ]
    upper, middle, lower = lane_rows[2], lane_rows[1], lane_rows[0]
    outer_error = _maximum(
        abs(upper[index]["x_m"] - lower[index]["x_m"])
        for index in range(min(len(upper), len(lower)))
    )
    middle_error = _maximum(
        abs((upper[index]["x_m"] - middle[index]["x_m"]) - middle_offset_m)
        for index in range(min(len(upper), len(middle)))
    )
    same_lane_error = _maximum(
        abs((front["x_m"] - rear["x_m"]) - same_lane_gap_m)
        for lane in range(_LANE_COUNT)
        for front, rear in zip(lane_rows[lane], lane_rows[lane][1:])
    )
    speeds = [row["speed_mps"] for row in rows]
    speed_spread = max(speeds) - min(speeds) if speeds else 0.0
    reasons = []
    if len(rows) < 3:
        reasons.append("fewer_than_three_vehicles")
    if off_road:
        reasons.append("road_departure_detected")
    if unresolved_lane:
        reasons.append("lane_association_unresolved")
    if lane_counts != _expected_lane_counts(len(rows)):
        reasons.append("lane_distribution_invalid")
    if outer_error > position_tolerance_m:
        reasons.append("outer_alignment_error_exceeded")
    if middle_error > position_tolerance_m:
        reasons.append("middle_offset_error_exceeded")
    if same_lane_error > position_tolerance_m:
        reasons.append("same_lane_gap_error_exceeded")
    if speed_spread > speed_tolerance_mps:
        reasons.append("speed_spread_exceeded")
    max_error = max(outer_error, middle_error, same_lane_error)
    return {
        "members": members,
        "vehicle_count": len(rows),
        "lanes": sorted(lane for lane, items in lane_rows.items() if items),
        "lane_counts": lane_counts,
        "expected_lane_counts": _expected_lane_counts(len(rows)),
        "max_outer_alignment_error_m": outer_error,
        "max_middle_offset_error_m": middle_error,
        "max_same_lane_gap_error_m": same_lane_error,
        "speed_spread_mps": speed_spread,
        "failure_reasons": reasons,
        "valid": not reasons,
        "max_lattice_error_m": max_error,
        "max_adjacent_spacing_error_m": max_error,
        "road_span_m": (
            max(row["x_m"] for row in rows) - min(row["x_m"] for row in rows)
            + _BODY_LENGTH_M if rows else 0.0
        ),
        "center_span_m": (
            max(row["x_m"] for row in rows) - min(row["x_m"] for row in rows)
            if rows else 0.0
        ),
    }


def _departure_facts(frames):
    schedules = {}
    actuals = {}
    declared = False
    for frame in frames:
        raw = frame.get("departures")
        if raw is None:
            continue
        declared = True
        if not isinstance(raw, Mapping):
            raise ValueError("frame departures must be an actor mapping")
        if schedules and set(raw) != set(schedules):
            raise ValueError("departure cohort changed during recording")
        for key, row in raw.items():
            if type(key) is not str or not isinstance(row, Mapping):
                raise ValueError("invalid departure evidence")
            scheduled = row.get("scheduled_departure_s")
            actual = row.get("actual_departure_s")
            if type(scheduled) not in (int, float) or not math.isfinite(scheduled) \
                    or scheduled < 0:
                raise ValueError(f"{key}: invalid scheduled departure")
            if actual is not None and (
                    type(actual) not in (int, float) or not math.isfinite(actual)
                    or actual < scheduled - _EPS):
                raise ValueError(f"{key}: invalid actual departure")
            scheduled = float(scheduled)
            actual = None if actual is None else float(actual)
            if key in schedules and schedules[key] != scheduled:
                raise ValueError("scheduled departure changed during recording")
            if key in actuals and actuals[key] is not None and actuals[key] != actual:
                raise ValueError("actual departure changed after activation")
            schedules[key] = scheduled
            if key not in actuals or actual is not None:
                actuals[key] = actual
    if not declared:
        first_seen = {}
        for frame in frames:
            for key in frame["states"]:
                first_seen.setdefault(key, float(frame["time_s"]))
        schedules = dict(first_seen)
        actuals = dict(first_seen)
    else:
        actuals = {key: actuals.get(key) for key in schedules}
    return schedules, actuals


def _has_collision(rows):
    return any(
        abs(left["x_m"] - right["x_m"]) < _BODY_LENGTH_M - _EPS
        and abs(left["y_m"] - right["y_m"]) < _BODY_WIDTH_M - _EPS
        for left, right in combinations(rows.values(), 2)
    )


def _join_phase(detail):
    if not isinstance(detail, Mapping):
        return None
    nested = detail.get("simple_formation")
    if isinstance(nested, Mapping):
        detail = nested
    return detail.get("join_phase")


def _close_interval(active, candidates, keys, end_time_s, reason):
    item = active.pop(keys)
    item["end_time_s"] = end_time_s
    item["end_reason"] = reason
    candidates.append(item)


def detect_frames(frames, d=15.0, lane_width=3.3, position_tolerance=2.0,
                  speed_tolerance=1.0, persistence_s=1.0,
                  formation_deadline_s=30.0, hold_s=10.0,
                  component_gap_m=50.0, max_sample_gap_s=0.1,
                  incidents=None):
    """Evaluate dynamic physical components without controller-derived roles."""
    d = _finite("d", d)
    lane_width = _finite("lane_width", lane_width)
    position_tolerance = _finite("position_tolerance", position_tolerance)
    speed_tolerance = _finite("speed_tolerance", speed_tolerance)
    persistence_s = _finite("persistence_s", persistence_s, nonnegative=True)
    formation_deadline_s = _finite("formation_deadline_s", formation_deadline_s)
    hold_s = _finite("hold_s", hold_s)
    component_gap_m = _finite("component_gap_m", component_gap_m)
    max_sample_gap_s = _finite("max_sample_gap_s", max_sample_gap_s)
    if position_tolerance >= d / 2:
        raise ValueError("Position tolerance must be smaller than d/2")
    frames = list(frames)
    times = []
    for frame in frames:
        if not isinstance(frame, Mapping) or not isinstance(frame.get("states"), Mapping):
            raise ValueError("each detector frame requires a states mapping")
        time_s = frame.get("time_s")
        if type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError("Frame times must be finite")
        times.append(float(time_s))
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("Frame times must be strictly increasing")
    schedules, actuals = _departure_facts(frames)
    cohort = sorted(schedules)
    last_actual = (max(actuals.values())
                   if actuals and all(value is not None for value in actuals.values())
                   else None)
    incident_rows = incidents or {}
    if not isinstance(incident_rows, Mapping):
        raise ValueError("incidents must be a mapping")

    component_history = []
    admission_conflicts = []
    missing_events = []
    predeparture_events = []
    collision_events = list(incident_rows.get("collision_events", ()))
    road_events = list(incident_rows.get("road_departure_events", ()))
    teleport_events = list(incident_rows.get("teleport_events", ()))
    jump_events = list(incident_rows.get("nonphysical_jump_events", ()))
    active = {}
    candidates = []
    previous_rows = {}
    previous_time = None
    sampling_gaps = 0

    for time_s, frame in zip(times, frames):
        rows = _physical_rows(frame["states"], lane_width)
        expected = {
            key for key, actual in actuals.items()
            if actual is not None and actual <= time_s + _EPS
        }
        for key in sorted(expected - set(rows)):
            missing_events.append({"time_s": time_s, "actor": key})
        for row in rows.values():
            actual = actuals.get(row["key"])
            if row["key"] in schedules \
                    and (actual is None or time_s < actual):
                predeparture_events.append({
                    "time_s": time_s, "actor": row["key"],
                })
            if not row["on_road"]:
                road_events.append({"time_s": time_s, "actor": row["key"]})
        if _has_collision(rows):
            collision_events.append({"time_s": time_s})
        if frame.get("teleport_starts", 0):
            teleport_events.append({"time_s": time_s, "count": frame["teleport_starts"]})
        if previous_time is not None:
            elapsed = time_s - previous_time
            if elapsed > max_sample_gap_s + _TIME_EPS:
                sampling_gaps += 1
            for key in set(previous_rows) & set(rows):
                before, after = previous_rows[key], rows[key]
                distance = math.hypot(
                    after["x_m"] - before["x_m"],
                    after["y_m"] - before["y_m"],
                )
                plausible = (max(before["speed_mps"], after["speed_mps"]) * elapsed
                             + 5.0 * elapsed * elapsed + 2.0)
                if distance > plausible + _EPS:
                    jump_events.append({
                        "time_s": time_s, "actor": key,
                        "distance_m": distance, "plausible_m": plausible,
                    })

        measurements = [
            _component_measurement(
                group, middle_offset_m=d, same_lane_gap_m=2 * d,
                position_tolerance_m=position_tolerance,
                speed_tolerance_mps=speed_tolerance,
            )
            for group in _physical_components(rows, component_gap_m)
        ]
        diagnostics = frame.get("join_diagnostics", {})
        if diagnostics is not None and not isinstance(diagnostics, Mapping):
            raise ValueError("join_diagnostics must be an actor mapping")
        diagnostics = diagnostics or {}
        for measurement in measurements:
            joiners = sorted(
                key for key in measurement["members"]
                if _join_phase(diagnostics.get(key)) in ("JOINING", "STABILIZING")
            )
            if len(joiners) > 1:
                admission_conflicts.append({
                    "time_s": time_s,
                    "component_members": measurement["members"],
                    "joining_actors": joiners,
                })
        current = {
            frozenset(measurement["members"]): measurement
            for measurement in measurements if measurement["valid"]
        }
        gap = (previous_time is not None
               and time_s - previous_time > max_sample_gap_s + _TIME_EPS)
        for keys in list(active):
            if gap or keys not in current:
                _close_interval(
                    active, candidates, keys, previous_time,
                    "sample_gap" if gap else "geometry_or_membership_lost",
                )
        for keys, measurement in current.items():
            if keys not in active:
                active[keys] = {
                    "members": sorted(keys), "start_time_s": time_s,
                    "max_outer_alignment_error_m": 0.0,
                    "max_middle_offset_error_m": 0.0,
                    "max_same_lane_gap_error_m": 0.0,
                    "max_speed_spread_mps": 0.0,
                }
            item = active[keys]
            item["end_time_s"] = time_s
            for target, source in (
                ("max_outer_alignment_error_m", "max_outer_alignment_error_m"),
                ("max_middle_offset_error_m", "max_middle_offset_error_m"),
                ("max_same_lane_gap_error_m", "max_same_lane_gap_error_m"),
                ("max_speed_spread_mps", "speed_spread_mps"),
            ):
                item[target] = max(item[target], measurement[source])
        component_history.append({
            "time_s": time_s,
            "active_members": sorted(rows),
            "components": measurements,
            "missing_departed_members": sorted(expected - set(rows)),
        })
        previous_rows = rows
        previous_time = time_s
    for keys in list(active):
        _close_interval(active, candidates, keys, previous_time, "recording_end")

    expected_component_members = (
        [component["members"]
         for component in component_history[-1]["components"]]
        if component_history else []
    )
    expected_component_sets = {
        frozenset(members) for members in expected_component_members
    }
    for item in candidates:
        physical_start = item["start_time_s"]
        qualification_start = (
            max(physical_start, last_actual)
            if last_actual is not None else physical_start
        )
        duration = max(0.0, item["end_time_s"] - qualification_start)
        confirmed = duration + _EPS >= persistence_s
        formed = qualification_start + persistence_s if confirmed else None
        held = (formed + hold_s
                if confirmed and duration + _EPS >= persistence_s + hold_s else None)
        by_deadline = bool(
            formed is not None and last_actual is not None
            and formed <= last_actual + formation_deadline_s + _EPS
        )
        item.update(
            physical_start_time_s=physical_start,
            start_time_s=round(qualification_start, 10),
            duration_s=round(duration, 10),
            formation_confirmed=confirmed,
            formed_time_s=None if formed is None else round(formed, 10),
            held_time_s=None if held is None else round(held, 10),
            formation_by_deadline=by_deadline,
            whole_cohort=item["members"] == cohort,
        )
        item["success"] = bool(by_deadline and held is not None)
        item["failure_reasons"] = []
        if not confirmed:
            item["failure_reasons"].append("persistence_too_short")
        elif not by_deadline:
            item["failure_reasons"].append("formation_deadline_missed")
        if confirmed and held is None:
            item["failure_reasons"].append("hold_after_confirmation_too_short")
        item["max_lattice_error_m"] = max(
            item["max_outer_alignment_error_m"],
            item["max_middle_offset_error_m"],
            item["max_same_lane_gap_error_m"],
        )
    candidates.sort(
        key=lambda item: (item["start_time_s"], -len(item["members"]), item["members"]),
    )
    intervals = [item for item in candidates if item["formation_confirmed"]]
    successful_component_intervals = []
    for members in expected_component_members:
        successful = [
            item for item in intervals
            if item["members"] == members and item["success"]
        ]
        if successful:
            successful_component_intervals.append(min(
                successful, key=lambda item: item["formed_time_s"],
            ))
    all_components_success = bool(expected_component_members) and (
        len(successful_component_intervals) == len(expected_component_members)
    )
    formed_time = (max(item["formed_time_s"]
                       for item in successful_component_intervals)
                   if all_components_success else None)
    held_time = (max(item["held_time_s"]
                     for item in successful_component_intervals)
                 if all_components_success else None)

    reasons = []
    if not frames:
        reasons.append("empty_recording")
    if schedules and any(value is None for value in actuals.values()):
        reasons.append("partial_departure_cohort")
    if predeparture_events:
        reasons.append("actor_present_before_departure")
    if missing_events:
        reasons.append("member_missing")
    if collision_events:
        reasons.append("collision_detected")
    if road_events:
        reasons.append("road_departure_detected")
    if teleport_events:
        reasons.append("teleport_detected")
    if jump_events:
        reasons.append("nonphysical_jump_detected")
    if admission_conflicts:
        reasons.append("simultaneous_admission_conflict")
    if frames and not intervals:
        reasons.append("no_persistent_local_group")
    expected_intervals = {
        frozenset(members): [
            item for item in intervals if item["members"] == members
        ]
        for members in expected_component_members
    }
    if any(rows and not any(item["formation_by_deadline"] for item in rows)
           for rows in expected_intervals.values()):
        reasons.append("formation_deadline_missed")
    elif any(rows and not any(
            item["formation_by_deadline"] and item["held_time_s"] is not None
            for item in rows) for rows in expected_intervals.values()):
        reasons.append("hold_after_confirmation_too_short")
    if frames and not all_components_success:
        reasons.append("expected_component_milestone_not_met")
    if frames and len(expected_component_members) <= 1 and not all_components_success:
        reasons.append("whole_cohort_milestone_not_met")
    hazards = {
        "partial_departure_cohort", "actor_present_before_departure",
        "member_missing", "collision_detected", "road_departure_detected",
        "teleport_detected",
        "nonphysical_jump_detected", "simultaneous_admission_conflict",
    }
    success = bool(
        last_actual is not None and all_components_success
        and not hazards.intersection(reasons)
    )
    maxima_source = [
        component
        for row in component_history
        for component in row["components"]
        if frozenset(component["members"]) in expected_component_sets
    ]
    final_component_counts = (
        [component["lane_counts"]
         for component in component_history[-1]["components"]]
        if component_history else []
    )
    final_counts = ([sum(counts[lane] for counts in final_component_counts)
                     for lane in range(_LANE_COUNT)]
                    if final_component_counts else None)
    parameters = {
        "d_m": d, "middle_offset_m": d, "same_lane_gap_m": 2 * d,
        "component_gap_m": component_gap_m, "lane_width_m": lane_width,
        "position_tolerance_m": position_tolerance,
        "speed_tolerance_mps": speed_tolerance,
        "persistence_s": persistence_s,
        "formation_deadline_s": formation_deadline_s,
        "hold_after_confirmation_s": hold_s,
        "max_sample_gap_s": max_sample_gap_s,
        "body_length_m": _BODY_LENGTH_M, "body_width_m": _BODY_WIDTH_M,
    }
    return {
        "schema_version": 2, "offline_only": True, "parameters": parameters,
        "cohort_members": cohort, "cohort_size": len(cohort),
        "scheduled_departures": schedules, "actual_departures": actuals,
        "last_actual_departure_s": last_actual,
        "expected_component_members": expected_component_members,
        "all_components_success": all_components_success,
        "successful_component_intervals": successful_component_intervals,
        "frame_count": len(frames), "sampling_gap_count": sampling_gaps,
        "success": success, "whole_cohort_success": success,
        "local_success": any(item["success"] for item in intervals),
        "formed_time_s": formed_time,
        "held_time_s": held_time,
        "final_lane_counts": final_counts,
        "final_component_lane_counts": final_component_counts,
        "max_outer_alignment_error_m": _maximum(
            row["max_outer_alignment_error_m"] for row in maxima_source),
        "max_middle_offset_error_m": _maximum(
            row["max_middle_offset_error_m"] for row in maxima_source),
        "max_same_lane_gap_error_m": _maximum(
            row["max_same_lane_gap_error_m"] for row in maxima_source),
        "max_component_speed_spread_mps": _maximum(
            row["speed_spread_mps"] for row in maxima_source),
        "admission_conflicts": admission_conflicts,
        "missing_events": missing_events,
        "predeparture_actor_events": predeparture_events,
        "collision_events": collision_events,
        "road_departure_events": road_events,
        "teleport_events": teleport_events,
        "nonphysical_jump_events": jump_events,
        "failure_reasons": list(dict.fromkeys(reasons)),
        "intervals": intervals, "candidate_intervals": candidates,
        "component_history": component_history,
        "frames": [
            {
                "time_s": row["time_s"], "groups": row["components"],
                "active_members": row["active_members"],
                "fleet_failure_reasons": sorted({
                    reason for component in row["components"]
                    for reason in component["failure_reasons"]
                }),
            }
            for row in component_history
        ],
    }
