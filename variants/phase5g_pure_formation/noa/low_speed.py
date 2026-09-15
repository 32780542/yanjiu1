"""Finite Phase 5F lane-change duration candidates from local parameters."""

import math


def validated_durations(parameters):
    values = parameters.get("phase5f_duration_candidates_s")
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("Phase 5F duration candidates must be a nonempty sequence")
    durations = tuple(values)
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0.0
           for value in durations):
        raise ValueError("Phase 5F durations must be positive finite numbers")
    if any(right <= left for left, right in zip(durations, durations[1:])):
        raise ValueError("Phase 5F durations must be strictly increasing")
    if durations[0] != parameters["noa_lane_change_duration_s"]:
        raise ValueError("Phase 5F must retain the inherited duration as its first control")
    return durations


def peak_reference_lateral_accel(duration_s, parameters):
    if type(duration_s) not in (int, float) or not math.isfinite(duration_s) or duration_s <= 0.0:
        raise ValueError("Lane-change duration must be positive and finite")
    return 4.0 * parameters["lane_width_m"] / duration_s**2


def steering_speed_floor(duration_s, parameters):
    peak = peak_reference_lateral_accel(duration_s, parameters)
    tangent = math.tan(parameters["max_steering_rad"])
    if not math.isfinite(tangent) or tangent <= 0.0:
        raise ValueError("Positive finite maximum steering is required")
    return math.sqrt(peak * parameters["wheelbase_m"] / tangent)


def candidate_profiles(speed_mps, parameters):
    if type(speed_mps) not in (int, float) or not math.isfinite(speed_mps):
        raise ValueError("Measured speed must be finite")
    if speed_mps <= 0.0:
        return []
    profiles = []
    for duration in validated_durations(parameters):
        peak = peak_reference_lateral_accel(duration, parameters)
        floor = steering_speed_floor(duration, parameters)
        if peak <= parameters["comfort_lateral_accel_mps2"] and speed_mps >= floor:
            profiles.append({
                "duration_s": float(duration),
                "speed_floor_mps": floor,
                "peak_reference_lateral_accel_mps2": peak,
            })
    return profiles
