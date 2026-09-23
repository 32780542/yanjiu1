"""Dependency-light deterministic departure schedule shared with the root demo."""

import math
import random
import sys


CONTROL_DT_S = 0.1
LANE_CENTERS_M = (1.65, 4.95, 8.25)


def _finite(name: str, value: object) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not bool")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number, not bool") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number, not bool")
    return number


def deterministic_schedule_rows(
        count: int, seed: int, *, depart_interval_min_s: float,
        depart_interval_max_s: float, speed_min_mps: float,
        speed_max_mps: float) -> tuple[tuple[float, float, float], ...]:
    """Return `(departure_s, lane_center_m, speed_mps)` in physical order."""
    if type(count) is not int or not 3 <= count <= 60:
        raise ValueError("vehicle count must be an exact integer from 3 to 60")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("case seed must be an exact uint64 integer, not bool")
    interval_low = _finite("depart_interval_min_s", depart_interval_min_s)
    interval_high = _finite("depart_interval_max_s", depart_interval_max_s)
    if interval_low <= 0 or interval_high < interval_low:
        raise ValueError("departure interval bounds must satisfy 0 < minimum <= maximum")
    speed_low = _finite("speed_min_mps", speed_min_mps)
    speed_high = _finite("speed_max_mps", speed_max_mps)
    if speed_low < 0 or speed_high <= speed_low:
        raise ValueError("initial speed bounds must satisfy 0 <= minimum < maximum")

    scaled_low = interval_low / CONTROL_DT_S
    scaled_high = interval_high / CONTROL_DT_S
    if not math.isfinite(scaled_low) or not math.isfinite(scaled_high):
        raise ValueError(
            "depart_interval_min_s/depart_interval_max_s are too large for "
            "a 0.1 s control tick"
        )
    first_tick = math.ceil(scaled_low - 1e-12)
    last_tick = math.floor(scaled_high + 1e-12)
    if first_tick > last_tick:
        raise ValueError("departure interval bounds contain no 0.1 s control tick")
    if last_tick * max(1, count - 1) > sys.float_info.max:
        raise ValueError(
            "departure interval schedule is too large for a 0.1 s control tick"
        )

    rng = random.Random(seed)
    raw_upper = last_tick * CONTROL_DT_S
    scheduled_tick = 0
    rows = []
    for ordinal in range(count):
        if ordinal:
            raw_interval = rng.uniform(interval_low, raw_upper)
            scheduled_tick += max(
                first_tick,
                math.ceil(raw_interval / CONTROL_DT_S - 1e-12),
            )
        departure_s = round(scheduled_tick * CONTROL_DT_S, 1)
        lane_center_m = rng.choice(LANE_CENTERS_M)
        speed_mps = rng.uniform(speed_low, speed_high)
        rows.append((departure_s, lane_center_m, speed_mps))
    return tuple(rows)


def last_scheduled_departure_s(
        count: int, seed: int, *, depart_interval_min_s: float,
        depart_interval_max_s: float, speed_min_mps: float,
        speed_max_mps: float) -> float:
    """Return the exact final scheduled departure for the deterministic case."""
    return deterministic_schedule_rows(
        count, seed,
        depart_interval_min_s=depart_interval_min_s,
        depart_interval_max_s=depart_interval_max_s,
        speed_min_mps=speed_min_mps,
        speed_max_mps=speed_max_mps,
    )[-1][0]
