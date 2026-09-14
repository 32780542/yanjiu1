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


def lane_index(current_y_m, lane_centers_m, tolerance_m):
    """Classify one lateral point only when it is unambiguously in a lane strip."""
    centers = tuple(lane_centers_m)
    if (
        type(current_y_m) not in (int, float)
        or not math.isfinite(current_y_m)
        or type(tolerance_m) not in (int, float)
        or not math.isfinite(tolerance_m)
        or tolerance_m < 0
        or len(centers) < 2
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in centers)
        or any(right <= left for left, right in zip(centers, centers[1:]))
    ):
        raise ValueError("Invalid visible lane geometry")
    midpoints = tuple((left + right) / 2 for left, right in zip(centers, centers[1:]))
    boundaries = (
        centers[0] - (centers[1] - centers[0]) / 2,
        *midpoints,
        centers[-1] + (centers[-1] - centers[-2]) / 2,
    )
    matches = tuple(
        index
        for index, (lower, upper) in enumerate(zip(boundaries, boundaries[1:]))
        if lower + tolerance_m <= current_y_m <= upper - tolerance_m
    )
    return matches[0] if len(matches) == 1 else None


def local_vehicles(control, road, parameters):
    """Convert filtered ego-frame detections into local world-coordinate rows."""
    tolerance = parameters["noa_geometry_tolerance_m"]
    ego = control.ego
    centers = tuple(road.centers_m)
    c, s = math.cos(ego.heading_rad), math.sin(ego.heading_rad)
    ego_vx = ego.vx_mps * c - ego.vy_mps * s
    rows = []
    for detection in control.observation.neighbors:
        if type(detection.track_id) is not int or detection.track_id < 0:
            raise ValueError("Invalid local sensor track")
        x_m = ego.x_m + c * detection.relative_x_m - s * detection.relative_y_m
        y_m = ego.y_m + s * detection.relative_x_m + c * detection.relative_y_m
        vx_mps = (
            ego_vx
            + c * detection.relative_vx_mps
            - s * detection.relative_vy_mps
        )
        heading = ego.heading_rad + detection.relative_heading_rad
        lateral_half = (
            abs(math.cos(heading)) * detection.width_m
            + abs(math.sin(heading)) * detection.length_m
        ) / 2
        lower = lane_index(y_m - lateral_half, centers, tolerance)
        upper = lane_index(y_m + lateral_half, centers, tolerance)
        visible = any(
            x0 - tolerance <= x_m <= x1 + tolerance
            and y0 - tolerance <= y_m - lateral_half
            and y_m + lateral_half <= y1 + tolerance
            for x0, x1, y0, y1 in road.envelope.regions
        )
        associated = lower if visible and lower is not None and lower == upper else None
        rows.append(
            LocalVehicle(detection.track_id, x_m, y_m, vx_mps, associated)
        )
    return tuple(rows)


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
    candidates = tuple(
        lane for lane in adjacent if counts[lane] < counts[ego_lane_index]
    )
    if not candidates:
        return LaneDecision(None, "no_less_populated_adjacent_lane", counts)
    minimum = min(counts[lane] for lane in candidates)
    targets = tuple(lane for lane in candidates if counts[lane] == minimum)
    if len(targets) != 1:
        return LaneDecision(None, "adjacent_lane_tie", counts)
    target = targets[0]
    return LaneDecision(target, "simple_formation_balance", counts)
