"""Small deterministic formation rules over one ego vehicle's local observations.

Track labels in this module are local sensor labels.  They are used only to
hold a still-visible reference in one vehicle's private memory; they never
provide identity, priority, communication, global counts, or slot assignment.
Lane-change safety remains the responsibility of the unchanged NOA controller.
"""
from dataclasses import dataclass, fields
import math

from noa.contracts import NoaMemory, memory_from_dict as noa_memory_from_dict


PARAMETERS = (
    "simple_formation_local_range_m",
    "simple_formation_adjacent_gap_m",
    "simple_formation_same_gap_m",
    "simple_formation_position_tolerance_m",
    "simple_formation_accel_limit_mps2",
    "simple_formation_max_lane_changes",
)


@dataclass(frozen=True, slots=True)
class SimpleFormationMemory(NoaMemory):
    reference_track_id: int | None = None
    formation_lane_change_done: bool = False


@dataclass(frozen=True, slots=True)
class LocalVehicle:
    track_id: int
    x_m: float
    y_m: float
    vx_mps: float
    lane_index: int | None


@dataclass(frozen=True, slots=True)
class LaneDecision:
    target_lane_index: int | None
    reason: str
    counts: tuple[int, ...]


def validate_parameters(p):
    """Reject anything except the six complete, fixed simple-rule parameters."""
    for key in PARAMETERS[:-1]:
        value = p.get(key)
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and value > 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("Invalid positive finite simple-formation parameter: " + key)
    key = PARAMETERS[-1]
    if type(p.get(key)) is not int or p[key] != 1:
        raise ValueError("Simple formation permits exactly one lane change")


def memory_from_dict(data):
    """Restore the NOA schema plus the two private simple-rule memory fields."""
    value = dict(data)
    reference = value.pop("reference_track_id", None)
    done = value.pop("formation_lane_change_done", False)
    if reference is not None and (type(reference) is not int or reference < 0):
        raise ValueError("Invalid local reference track")
    if type(done) is not bool:
        raise ValueError("Invalid simple-formation lane-change completion flag")
    base_names = {field.name for field in fields(NoaMemory)}
    base = noa_memory_from_dict({key: item for key, item in value.items() if key in base_names})
    return SimpleFormationMemory(
        **{field.name: getattr(base, field.name) for field in fields(NoaMemory)},
        reference_track_id=reference,
        formation_lane_change_done=done,
    )


def choose_reference(ego_x_m, vehicles, remembered_track_id, tolerance_m):
    """Hold one visible local track, otherwise select one unambiguous nearest front row."""
    ahead = tuple(
        row
        for row in vehicles
        if row.lane_index is not None and row.x_m > ego_x_m + tolerance_m
    )
    remembered = tuple(row for row in ahead if row.track_id == remembered_track_id)
    if len(remembered) == 1:
        return remembered[0]
    if not ahead:
        return None
    nearest_distance = min(row.x_m - ego_x_m for row in ahead)
    nearest = tuple(
        row for row in ahead if abs((row.x_m - ego_x_m) - nearest_distance) <= tolerance_m
    )
    return nearest[0] if len(nearest) == 1 else None


def desired_gap_m(ego_lane_index, reference_lane_index, p):
    """Use 15 m for adjacent lanes and 30 m for same/two-outer-lane geometry."""
    if abs(reference_lane_index - ego_lane_index) == 1:
        return p["simple_formation_adjacent_gap_m"]
    return p["simple_formation_same_gap_m"]


def longitudinal_increment(ego_x_m, ego_vx_mps, ego_lane_index, reference, p):
    """Return the fixed if/else acceleration increment for one local reference."""
    desired = desired_gap_m(ego_lane_index, reference.lane_index, p)
    error = reference.x_m - desired - ego_x_m
    tolerance = p["simple_formation_position_tolerance_m"]
    limit = p["simple_formation_accel_limit_mps2"]
    if error > tolerance:
        return limit
    if error < -tolerance:
        return -limit
    return max(-limit, min(limit, reference.vx_mps - ego_vx_mps))


def _local_rows(ego_x_m, vehicles, lane_count, local_range_m):
    return tuple(
        row
        for row in vehicles
        if row.lane_index is not None
        and 0 <= row.lane_index < lane_count
        and abs(row.x_m - ego_x_m) <= local_range_m
    )


def choose_lane(
    ego_x_m,
    ego_lane_index,
    vehicles,
    lane_centers_m,
    formation_lane_change_done,
    p,
):
    """Request an adjacent lane only for the local rear-most excess vehicle."""
    lane_count = len(lane_centers_m)
    if not 0 <= ego_lane_index < lane_count:
        raise ValueError("Ego lane is outside the locally visible road")
    rows = _local_rows(
        ego_x_m, vehicles, lane_count, p["simple_formation_local_range_m"]
    )
    counts_list = [0] * lane_count
    counts_list[ego_lane_index] = 1
    for row in rows:
        counts_list[row.lane_index] += 1
    counts = tuple(counts_list)

    if formation_lane_change_done:
        return LaneDecision(None, "formation_lane_change_done", counts)
    if any(row.lane_index == ego_lane_index and row.x_m < ego_x_m for row in rows):
        return LaneDecision(None, "not_local_rear_most", counts)

    adjacent = tuple(
        lane for lane in (ego_lane_index - 1, ego_lane_index + 1) if 0 <= lane < lane_count
    )
    if not adjacent:
        return LaneDecision(None, "no_adjacent_lane", counts)
    minimum = min(counts[lane] for lane in adjacent)
    targets = tuple(lane for lane in adjacent if counts[lane] == minimum)
    if len(targets) != 1:
        return LaneDecision(None, "adjacent_lane_tie", counts)
    target = targets[0]
    if counts[target] >= counts[ego_lane_index]:
        return LaneDecision(None, "no_less_populated_adjacent_lane", counts)
    return LaneDecision(target, "simple_formation_balance", counts)
