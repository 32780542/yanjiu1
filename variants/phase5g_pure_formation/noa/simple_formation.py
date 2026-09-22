"""Small deterministic formation rules over one ego vehicle's local observations.

Track labels in this module are local sensor labels.  They are used only to
hold a still-visible reference in one vehicle's private memory; they never
provide identity, priority, communication, global counts, or slot assignment.
Formation lane admission uses current local geometry and measured bodies.
"""
from dataclasses import dataclass, fields
from collections.abc import Mapping
import math

from noa.contracts import NoaMemory, memory_from_dict as noa_memory_from_dict


PARAMETERS = (
    "simple_formation_component_gap_m",
    "simple_formation_middle_offset_m",
    "simple_formation_same_lane_gap_m",
    "simple_formation_position_tolerance_m",
    "simple_formation_speed_tolerance_mps",
    "simple_formation_stable_time_s",
    "simple_formation_reference_switch_gain_m",
    "simple_formation_min_lane_change_speed_mps",
    "simple_formation_target_lane_clearance_m",
)


@dataclass(frozen=True, slots=True)
class SimpleFormationMemory(NoaMemory):
    reference_track_id: int | None = None
    join_anchor_track_id: int | None = None
    desired_lane_index: int | None = None
    join_phase: str = "FREE"
    stable_since_s: float | None = None


@dataclass(frozen=True, slots=True)
class LocalVehicle:
    track_id: int
    x_m: float
    y_m: float
    vx_mps: float
    lane_index: int | None


@dataclass(frozen=True, slots=True)
class JoinDecision:
    """Final physical lane and longitudinal target; counts are lower, middle, upper."""
    target_lane_index: int | None
    target_x_m: float | None
    anchor_track_id: int | None
    reason: str
    local_counts: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class FormationTarget:
    """One physical longitudinal target selected from ego-local observations."""
    role: str
    target_x_m: float | None
    reference_track_id: int | None
    reference_speed_mps: float | None
    target_lane_index: int | None
    reference_lane_index: int | None
    reason: str


def choose_formation_target(ego, vehicles, lane_centers_m, memory, p):
    """Select a role and reference using physical error, with private hysteresis."""
    rows, _ = _physical_inputs(ego, vehicles, lane_centers_m, p)
    if not isinstance(memory, SimpleFormationMemory):
        raise ValueError("Invalid simple-formation memory")

    def no_target(reason, lane=None):
        return FormationTarget("no_target", None, None, None, lane, None, reason)

    def from_row(role, row, target_x, reason, lane):
        return FormationTarget(role, target_x, row.track_id, row.vx_mps,
                               lane, row.lane_index, reason)

    if memory.join_phase in ("JOINING", "STABILIZING"):
        lane = memory.desired_lane_index
        if lane is None or memory.join_anchor_track_id is None:
            return no_target("join_state_incomplete", lane)
        matches = tuple(row for row in rows if row.track_id == memory.join_anchor_track_id)
        if len(matches) != 1:
            return no_target("join_anchor_lost", lane)
        anchor = matches[0]
        offsets = {(2, 1): p["simple_formation_middle_offset_m"],
                   (0, 2): 0.0,
                   (1, 2): p["simple_formation_middle_offset_m"]}
        offset = offsets.get((lane, anchor.lane_index))
        if offset is None:
            return no_target("join_anchor_invalid", lane)
        return from_row("joiner", anchor, anchor.x_m - offset,
                        "fixed_join_anchor", lane)

    lane = ego.lane_index
    if lane is None:
        return no_target("ego_lane_unresolved")
    if lane == 2:
        role = "upper_follower"
        candidates = tuple((row, row.x_m - p["simple_formation_same_lane_gap_m"])
                           for row in rows if row.lane_index == 2 and row.x_m > ego.x_m)
        if not candidates:
            return FormationTarget("upper_leader", None, None,
                                   p["noa_target_speed_mps"], 2, None,
                                   "frontmost_upper")
    else:
        role = "lower_aligned" if lane == 0 else "middle_offset"
        offset = 0.0 if lane == 0 else p["simple_formation_middle_offset_m"]
        candidates = tuple((row, row.x_m - offset)
                           for row in rows if row.lane_index == 2)
        if not candidates:
            role = "same_lane_follower"
            candidates = tuple((row, row.x_m - p["simple_formation_same_lane_gap_m"])
                               for row in rows if row.lane_index == lane
                               and row.x_m > ego.x_m)
    if not candidates:
        return no_target("no_valid_reference", lane)

    errors = tuple(abs(target_x - ego.x_m) for _, target_x in candidates)
    if role in ("upper_follower", "same_lane_follower"):
        nearest_x = min(row.x_m for row, _ in candidates)
        best = tuple(i for i, (row, _) in enumerate(candidates)
                     if row.x_m == nearest_x)
    else:
        best_error = min(errors)
        best = tuple(i for i, error in enumerate(errors) if error == best_error)
    remembered = tuple(i for i, (row, _) in enumerate(candidates)
                       if row.track_id == memory.reference_track_id)
    held = remembered[0] if len(remembered) == 1 else None
    gain = p["simple_formation_reference_switch_gain_m"]
    if held is not None and (held in best or
                             errors[held] - errors[best[0]] < gain):
        selected, reason = held, "remembered_reference"
    elif len(best) == 1:
        selected = best[0]
        reason = "switch_gain_met" if held is not None else "nearest_physical_target"
    elif held is not None:
        selected, reason = held, "ambiguous_alternative_hold"
    else:
        return no_target("ambiguous_physical_reference", lane)
    row, target_x = candidates[selected]
    return from_row(role, row, target_x, reason, lane)


def formation_acceleration(ego, target, p):
    """Return the final longitudinal request, independent of NOA cruise."""
    if target.role == "upper_leader":
        desired_speed = p["noa_target_speed_mps"]
    elif target.target_x_m is not None and target.reference_speed_mps is not None:
        error = target.target_x_m - ego.x_m
        desired_speed = target.reference_speed_mps + max(-2.0, min(2.0, error / 5.0))
    else:
        return None
    return max(-3.0, min(2.0, desired_speed - ego.vx_mps))


def target_lane_clear(ego, vehicles, target_lane_index, p):
    """Strict center-distance exclusion for lane-associated visible vehicles."""
    return all(row.lane_index != target_lane_index
               or abs(row.x_m - ego.x_m) >= p["simple_formation_target_lane_clearance_m"]
               for row in vehicles)


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _lane_centers(lane_centers_m):
    try:
        centers = tuple(lane_centers_m)
    except TypeError as exc:
        raise ValueError("Invalid visible three-lane geometry") from exc
    if (len(centers) != 3
            or any(not _finite_number(center) for center in centers)
            or any(right <= left for left, right in zip(centers, centers[1:]))):
        raise ValueError("Invalid visible three-lane geometry")
    return centers


def _vehicle_rows(vehicles):
    try:
        rows = tuple(vehicles)
    except TypeError as exc:
        raise ValueError("Invalid local vehicle rows") from exc
    for row in rows:
        _validate_vehicle(row)
    return rows


def _validate_vehicle(row, *, ego=False):
    if (type(row) is not LocalVehicle
            or type(row.track_id) is not int or row.track_id < 0
            or any(not _finite_number(value) for value in (row.x_m, row.y_m, row.vx_mps))
            or (row.lane_index is not None
                and (type(row.lane_index) is not int or row.lane_index not in (0, 1, 2)))):
        raise ValueError("Invalid local ego vehicle" if ego else "Invalid local vehicle row")


def _physical_inputs(ego, vehicles, lane_centers_m, p):
    centers = _lane_centers(lane_centers_m)
    validate_parameters(p)
    _validate_vehicle(ego, ego=True)
    return _vehicle_rows(vehicles), centers


def connected_tail_neighborhood(ego, vehicles, lane_centers_m, p):
    """Return lane-resolved rows in ego's x-connected visible component."""
    rows, centers = _physical_inputs(ego, vehicles, lane_centers_m, p)
    return _connected_tail_neighborhood(ego, rows, centers, p)


def _connected_tail_neighborhood(ego, vehicles, lane_centers_m, p):
    lane_count = len(lane_centers_m)
    rows = (row for row in vehicles if row.lane_index is not None
            and 0 <= row.lane_index < lane_count)
    nodes = sorted((*rows, ego), key=lambda row: row.x_m)
    ego_at = next(i for i, row in enumerate(nodes) if row is ego)
    first = last = ego_at
    gap = p["simple_formation_component_gap_m"]
    while first > 0 and nodes[first].x_m - nodes[first - 1].x_m <= gap:
        first -= 1
    while last + 1 < len(nodes) and nodes[last + 1].x_m - nodes[last].x_m <= gap:
        last += 1
    return tuple(row for row in nodes[first:last + 1] if row is not ego)


def lane_counts(vehicles, lane_centers_m):
    """Count only resolved physical lanes, indexed lower=0 to upper=2."""
    centers = _lane_centers(lane_centers_m)
    rows = _vehicle_rows(vehicles)
    return _lane_counts(rows, centers)


def _lane_counts(vehicles, lane_centers_m):
    counts = [0] * len(lane_centers_m)
    for row in vehicles:
        if row.lane_index is not None and 0 <= row.lane_index < len(counts):
            counts[row.lane_index] += 1
    return tuple(counts)


def _ordered_tail(rows, p):
    """Order x layers front to rear, with aligned outer lanes upper first."""
    remaining = list(rows)
    ordered = []
    tolerance = p["simple_formation_position_tolerance_m"]
    lane_order = {1: 0, 2: 1, 0: 2}
    while remaining:
        front_x = max(row.x_m for row in remaining)
        layer = [row for row in remaining if front_x - row.x_m <= tolerance]
        remaining = [row for row in remaining if front_x - row.x_m > tolerance]
        ordered.extend(sorted(layer, key=lambda row: lane_order[row.lane_index]))
    return tuple(ordered)


def _follows_tail(front, rear, p):
    offset = p["simple_formation_middle_offset_m"]
    tolerance = p["simple_formation_position_tolerance_m"]
    expected = {(1, 2): offset, (2, 0): 0.0, (0, 1): offset}
    distance = expected.get((front.lane_index, rear.lane_index))
    return distance is not None and abs(front.x_m - rear.x_m - distance) <= tolerance


def _stable_tail_prefix(rows, p):
    """Take the frontmost geometrically coherent sequence; later rows are waiters."""
    return _coherent_prefix(_ordered_tail(rows, p), p)


def _coherent_prefix(ordered, p):
    if not ordered:
        return ()
    last = 1
    while last < len(ordered) and _follows_tail(ordered[last - 1], ordered[last], p):
        last += 1
    return ordered[:last]


def infer_tail_join(ego, vehicles, lane_centers_m, p):
    """Infer the next cycle slot, falling back to local resolved-lane counts."""
    rows, centers = _physical_inputs(ego, vehicles, lane_centers_m, p)
    return _infer_tail_join(ego, rows, centers, p)


def _infer_tail_join(ego, vehicles, lane_centers_m, p, ordered_rows=None):
    rows = tuple(row for row in vehicles if row.lane_index in (0, 1, 2))
    counts = _lane_counts(rows, lane_centers_m)
    ordered = _ordered_tail(rows, p) if ordered_rows is None else ordered_rows
    coherent = len(_coherent_prefix(ordered, p)) == len(rows)
    offset = p["simple_formation_middle_offset_m"]
    if coherent and ordered:
        rear = ordered[-1]
        if rear.lane_index == 1:
            return JoinDecision(2, rear.x_m - offset, rear.track_id, "middle_tail", counts)
        if rear.lane_index == 2:
            return JoinDecision(0, rear.x_m, rear.track_id, "upper_tail", counts)
        if rear.lane_index == 0 and len(ordered) >= 2 and ordered[-2].lane_index == 2:
            upper = ordered[-2]
            return JoinDecision(1, upper.x_m - offset, upper.track_id, "outer_tail", counts)

    target = min((2, 0, 1), key=lambda lane: counts[lane])
    if not rows:
        return JoinDecision(target, None, None, "counts_empty", counts)
    rear_x = min(row.x_m for row in rows)
    tolerance = p["simple_formation_position_tolerance_m"]
    anchors = tuple(row for row in rows if abs(row.x_m - rear_x) <= tolerance)
    if len(anchors) != 1:
        return JoinDecision(None, None, None, "wait_ambiguous_anchor", counts)
    anchor = anchors[0]
    if target == anchor.lane_index:
        target_x = anchor.x_m - p["simple_formation_same_lane_gap_m"]
    elif target == 0 and anchor.lane_index == 2:
        target_x = anchor.x_m
    else:
        target_x = anchor.x_m - offset
    return JoinDecision(target, target_x, anchor.track_id, "counts_recovery", counts)


def is_next_waiting_vehicle(ego, vehicles, lane_centers_m, p):
    """Admit the nearest rear waiter, with physical upper-lane tie priority."""
    rows, centers = _physical_inputs(ego, vehicles, lane_centers_m, p)
    return _is_next_waiting_vehicle(ego, rows, centers, p)


def _is_next_waiting_vehicle(ego, vehicles, lane_centers_m, p, stable_tail=None):
    rows = tuple(row for row in vehicles if row is not ego)
    tolerance = p["simple_formation_position_tolerance_m"]
    if stable_tail is None:
        resolved = tuple(row for row in rows if row.lane_index in (0, 1, 2)
                         and row.x_m > ego.x_m + tolerance)
        stable = _stable_tail_prefix(resolved, p)
    else:
        stable = stable_tail
    if not stable:
        peers = tuple(row for row in rows if abs(row.x_m - ego.x_m) <= tolerance)
        return ego.lane_index in (0, 1, 2) and all(
            row.lane_index is not None and ego.lane_index > row.lane_index
            for row in peers
        )
    tail_rear_x = min(row.x_m for row in stable)
    if ego.x_m >= tail_rear_x - tolerance:
        return False
    waiters = tuple(row for row in rows if all(row is not part for part in stable)
                    and row.x_m < tail_rear_x - tolerance
                    and row.x_m >= ego.x_m - tolerance)
    if any(row.x_m > ego.x_m + tolerance for row in waiters):
        return False
    peers = tuple(row for row in waiters if abs(row.x_m - ego.x_m) <= tolerance)
    if any(row.lane_index is None or row.lane_index == ego.lane_index for row in peers):
        return False
    if ego.lane_index is None:
        return False
    return all(ego.lane_index > row.lane_index for row in peers)


def choose_join(ego, vehicles, lane_centers_m, p):
    """Choose from ego's connected, geometrically formed local tail only."""
    rows, centers = _physical_inputs(ego, vehicles, lane_centers_m, p)
    local = _connected_tail_neighborhood(ego, rows, centers, p)
    tolerance = p["simple_formation_position_tolerance_m"]
    ahead = tuple(row for row in local if row.x_m > ego.x_m + tolerance)
    by_lane = sorted(ahead, key=lambda row: (row.lane_index, row.x_m))
    if any(left.lane_index == right.lane_index
           and right.x_m - left.x_m <= tolerance
           for left, right in zip(by_lane, by_lane[1:])):
        return JoinDecision(None, None, None, "wait_ambiguous_tail",
                            _lane_counts(ahead, centers))
    ordered_ahead = _ordered_tail(ahead, p)
    stable = _coherent_prefix(ordered_ahead, p)
    # A discarded row in the terminal layer is anomalous tail geometry, not a
    # waiter. Preserve it for count recovery and anchor ambiguity detection.
    overlaps_tail = stable and any(
        all(row is not part for part in stable)
        and row.x_m >= stable[-1].x_m - tolerance
        for row in ahead
    )
    inferred_rows = ordered_ahead if overlaps_tail else stable
    inferred = _infer_tail_join(ego, inferred_rows, centers, p,
                                ordered_rows=inferred_rows)
    local_max_x = max((ego.x_m + tolerance, *(row.x_m for row in local)))
    unresolved = tuple(row for row in rows if row.lane_index is None
                       and ego.x_m - tolerance <= row.x_m <= local_max_x)
    if not _is_next_waiting_vehicle(ego, local + unresolved, centers, p,
                                    stable_tail=stable):
        return JoinDecision(None, None, None, "wait_not_next", inferred.local_counts)
    return inferred


def validate_parameters(p):
    """Require the complete positive finite local-tail parameter contract."""
    if not isinstance(p, Mapping):
        raise ValueError("Invalid simple-formation parameter mapping")
    for key in PARAMETERS:
        value = p.get(key)
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and value > 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("Invalid positive finite simple-formation parameter: " + key)


def memory_from_dict(data):
    """Restore exact NOA or local-tail memory schemas with neutral defaults."""
    value = dict(data)
    base_names = {field.name for field in fields(NoaMemory)}
    private_names = {
        "reference_track_id",
        "join_anchor_track_id",
        "desired_lane_index",
        "join_phase",
        "stable_since_s",
    }
    unknown = set(value) - base_names - private_names
    if unknown:
        raise ValueError("Unexpected SimpleFormationMemory fields")
    reference = value.pop("reference_track_id", None)
    anchor = value.pop("join_anchor_track_id", None)
    desired_lane = value.pop("desired_lane_index", None)
    join_phase = value.pop("join_phase", "FREE")
    stable_since = value.pop("stable_since_s", None)
    for name, track_id in (("reference", reference), ("join anchor", anchor)):
        if track_id is not None and (type(track_id) is not int or track_id < 0):
            raise ValueError("Invalid local " + name + " track")
    if desired_lane is not None and (
        type(desired_lane) is not int or desired_lane not in (0, 1, 2)
    ):
        raise ValueError("Invalid desired local lane")
    if type(join_phase) is not str or join_phase not in (
        "FREE", "JOINING", "STABILIZING", "FORMED"
    ):
        raise ValueError("Invalid local-tail join phase")
    if stable_since is not None:
        try:
            valid_stable_since = (
                type(stable_since) in (int, float)
                and math.isfinite(stable_since)
                and stable_since >= 0
            )
        except OverflowError:
            valid_stable_since = False
        if not valid_stable_since:
            raise ValueError("Invalid local-tail stability timestamp")
    base = noa_memory_from_dict(value)
    return SimpleFormationMemory(
        **{field.name: getattr(base, field.name) for field in fields(NoaMemory)},
        reference_track_id=reference,
        join_anchor_track_id=anchor,
        desired_lane_index=desired_lane,
        join_phase=join_phase,
        stable_since_s=stable_since,
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
