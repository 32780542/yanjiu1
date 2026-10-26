"""编队的几何规则：跟驰参考、四层占位和唯一补位车辆。

每次调用只处理一辆车。轨迹标签用于关联本车仍可见的邻车，记忆由本车独立保存。
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
    stable_window_signature: str | None = None


@dataclass(frozen=True, slots=True)
class LocalVehicle:
    track_id: int
    x_m: float
    y_m: float
    vx_mps: float
    lane_index: int | None
    vy_mps: float = 0.0


@dataclass(frozen=True, slots=True)
class JoinDecision:
    """Final physical lane and longitudinal target; counts run lower to upper."""

    target_lane_index: int | None
    target_x_m: float | None
    anchor_track_id: int | None
    reason: str
    local_counts: tuple[int, ...]


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
    """先跟同车道最近前车；车道头车再按交错相位对齐参考车。"""
    rows, centers = _physical_inputs(ego, vehicles, lane_centers_m, p)
    lane_count = len(centers)
    if not isinstance(memory, SimpleFormationMemory):
        raise ValueError("Invalid simple-formation memory")

    def no_target(reason, lane=None):
        return FormationTarget("no_target", None, None, None, lane, None, reason)

    def from_row(role, row, target_x, reason, lane):
        return FormationTarget(
            role, target_x, row.track_id, row.vx_mps, lane, row.lane_index, reason
        )

    if memory.join_phase in ("JOINING", "STABILIZING"):
        lane = memory.desired_lane_index
        if lane is None or memory.join_anchor_track_id is None:
            return no_target("join_state_incomplete", lane)
        matches = tuple(row for row in rows if row.track_id == memory.join_anchor_track_id)
        if len(matches) != 1:
            return no_target("join_anchor_lost", lane)
        anchor = matches[0]
        if anchor.lane_index is None:
            return no_target("join_anchor_invalid", lane)
        outer_base = anchor.x_m + _phase(anchor.lane_index, lane_count, p)
        target_x = outer_base - _phase(lane, lane_count, p)
        return from_row("joiner", anchor, target_x, "fixed_join_anchor", lane)

    component = connected_tail_neighborhood(ego, rows, lane_centers_m, p)
    remote_ahead = tuple(
        row
        for row in rows
        if row not in component and row.lane_index is not None and row.x_m > ego.x_m
    )
    rows = component
    lane = ego.lane_index
    if lane is None:
        return no_target("ego_lane_unresolved")

    def approach_visible_component():
        if not remote_ahead:
            return None
        first_x = min(row.x_m for row in remote_ahead)
        first = tuple(row for row in remote_ahead if row.x_m == first_x)
        highest_lane = max(row.lane_index for row in first)
        selected = tuple(row for row in first if row.lane_index == highest_lane)
        if len(selected) != 1:
            return no_target("ambiguous_remote_reference", lane)
        row = selected[0]
        target_x = (
            row.x_m
            + _phase(row.lane_index, lane_count, p)
            - _phase(lane, lane_count, p)
            - p["simple_formation_same_lane_gap_m"]
        )
        return from_row("component_approach", row, target_x, "visible_component_ahead", lane)

    same_lane = tuple(row for row in rows if row.lane_index == lane and row.x_m > ego.x_m)
    if same_lane:
        role = "upper_follower" if lane == lane_count - 1 else "same_lane_follower"
        nearest_x = min(row.x_m for row in same_lane)
        nearest = tuple(row for row in same_lane if row.x_m == nearest_x)
        if len(nearest) != 1:
            return no_target("ambiguous_physical_reference", lane)
        row = nearest[0]
        return from_row(
            role, row, row.x_m - p["simple_formation_same_lane_gap_m"], "nearest_same_lane", lane
        )
    elif lane == lane_count - 1:
        approach = approach_visible_component()
        if approach is not None:
            return approach
        return FormationTarget(
            "upper_leader", None, None, p["noa_target_speed_mps"], lane, None, "local_upper_head"
        )
    else:
        preferred = lane_count - 1 if any(row.lane_index == lane_count - 1 for row in rows) else 0
        head = tuple(row for row in rows if row.lane_index == preferred)
        if not head or (lane == 0 and preferred == 0):
            approach = approach_visible_component()
            if approach is not None:
                return approach
            return FormationTarget(
                "local_head", None, None, p["noa_target_speed_mps"], lane, None, "no_outer_head"
            )
        role = (
            "lower_aligned" if lane == 0 else "middle_offset" if lane == 1 else "lane_head_offset"
        )
        candidates = tuple(
            (row, row.x_m + _phase(row.lane_index, lane_count, p) - _phase(lane, lane_count, p))
            for row in head
        )
    errors = tuple(abs(target_x - ego.x_m) for _, target_x in candidates)
    front_x = max(row.x_m for row, _ in candidates)
    best = tuple(i for i, (row, _) in enumerate(candidates) if row.x_m == front_x)
    if len(best) != 1:
        return no_target("ambiguous_physical_reference", lane)
    remembered = tuple(
        i for i, (row, _) in enumerate(candidates) if row.track_id == memory.reference_track_id
    )
    held = remembered[0] if len(remembered) == 1 else None
    gain = p["simple_formation_reference_switch_gain_m"]
    if held is not None and (held in best or errors[held] - errors[best[0]] < gain):
        selected, reason = held, "remembered_reference"
    else:
        selected = best[0]
        reason = "switch_gain_met" if held is not None else "nearest_physical_target"
    row, target_x = candidates[selected]
    return from_row(role, row, target_x, reason, lane)


def formation_acceleration(ego, target, p):
    """把位置误差变成目标速度，再生成有界加速度请求。"""
    if target.role in ("upper_leader", "local_head"):
        desired_speed = p["noa_target_speed_mps"]
    elif target.target_x_m is not None and target.reference_speed_mps is not None:
        error = target.target_x_m - ego.x_m
        desired_speed = target.reference_speed_mps + max(-2.0, min(2.0, error / 5.0))
    else:
        return None
    return max(-3.0, min(2.0, desired_speed - ego.vx_mps))


def target_lane_clear(ego, vehicles, target_lane_index, p):
    """Strict center-distance exclusion for lane-associated visible vehicles."""
    return all(
        row.lane_index != target_lane_index
        or abs(row.x_m - ego.x_m) >= p["simple_formation_target_lane_clearance_m"]
        for row in vehicles
    )


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _lane_centers(lane_centers_m):
    try:
        centers = tuple(lane_centers_m)
    except TypeError as exc:
        raise ValueError("Invalid visible lane geometry") from exc
    if (
        len(centers) not in (2, 3, 4)
        or any(not _finite_number(center) for center in centers)
        or any(right <= left for left, right in zip(centers, centers[1:]))
    ):
        raise ValueError("Invalid visible lane geometry")
    return centers


def _phase(lane, lane_count, p):
    return p["simple_formation_middle_offset_m"] if (lane_count - 1 - lane) % 2 else 0.0


def _vehicle_rows(vehicles):
    try:
        rows = tuple(vehicles)
    except TypeError as exc:
        raise ValueError("Invalid local vehicle rows") from exc
    for row in rows:
        _validate_vehicle(row)
    return rows


def _validate_vehicle(row, *, ego=False):
    if (
        type(row) is not LocalVehicle
        or type(row.track_id) is not int
        or row.track_id < 0
        or any(not _finite_number(value) for value in (row.x_m, row.y_m, row.vx_mps, row.vy_mps))
        or (
            row.lane_index is not None
            and (type(row.lane_index) is not int or not 0 <= row.lane_index <= 3)
        )
    ):
        raise ValueError("Invalid local ego vehicle" if ego else "Invalid local vehicle row")


def _physical_inputs(ego, vehicles, lane_centers_m, p):
    centers = _lane_centers(lane_centers_m)
    validate_parameters(p)
    _validate_vehicle(ego, ego=True)
    rows = _vehicle_rows(vehicles)
    if any(row.lane_index is not None and row.lane_index >= len(centers) for row in (*rows, ego)):
        raise ValueError("Local vehicle lane lies outside visible road")
    return rows, centers


LAYER_RANGE_M = 90.0


@dataclass(frozen=True, slots=True)
class LayerWindow:
    # Layers are k-2, k-1, k, k+1; lanes run lower to upper.
    layers: tuple[tuple[LocalVehicle | None, ...], ...]
    consistent: bool
    crossing: bool
    speed_stable: bool
    signature: str


def connected_tail_neighborhood(ego, vehicles, lane_centers_m, p):
    """沿纵向相邻间距不超过 50 m 的车辆链找到本车局部车群。"""
    rows, centers = _physical_inputs(ego, vehicles, lane_centers_m, p)
    nodes = sorted((*rows, ego), key=lambda row: row.x_m)
    at = next(index for index, row in enumerate(nodes) if row is ego)
    first = last = at
    gap = p["simple_formation_component_gap_m"]
    while first and nodes[first].x_m - nodes[first - 1].x_m <= gap:
        first -= 1
    while last + 1 < len(nodes) and nodes[last + 1].x_m - nodes[last].x_m <= gap:
        last += 1
    return tuple(row for row in nodes[first : last + 1] if row is not ego)


def layered_window(ego, vehicles, lane_centers_m, p):
    """以本车为第 k 层，直接匹配各可见车道的 k-2、k-1、k、k+1 层。"""
    _, centers = _physical_inputs(ego, vehicles, lane_centers_m, p)
    rows = connected_tail_neighborhood(ego, vehicles, lane_centers_m, p)
    visible = tuple(row for row in (*rows, ego) if abs(row.x_m - ego.x_m) <= LAYER_RANGE_M)
    crossing = any(
        row.lane_index is None
        or abs(row.vy_mps) > 1e-9
        or abs(row.y_m - centers[row.lane_index]) > p["noa_completion_lateral_error_m"]
        for row in visible
    )
    speeds = tuple(row.vx_mps for row in visible)
    speed_stable = max(speeds) - min(speeds) <= p["simple_formation_speed_tolerance_mps"]
    lane_count = len(centers)
    slots = [[None] * lane_count for _ in range(4)]
    consistent = True
    base = ego.x_m + _phase(ego.lane_index, lane_count, p)
    spacing = p["simple_formation_same_lane_gap_m"]
    tolerance = p["simple_formation_position_tolerance_m"]
    for row in visible:
        if row.lane_index is None:
            continue
        offset = _phase(row.lane_index, lane_count, p)
        nearest = round((base - offset - row.x_m) / spacing)
        if nearest not in (-2, -1, 0, 1):
            continue
        target = base - nearest * spacing - offset
        if abs(row.x_m - target) > tolerance:
            consistent = False
            continue
        layer = slots[nearest + 2]
        if layer[row.lane_index] is not None:
            consistent = False
        else:
            layer[row.lane_index] = row
    for lane in range(lane_count):
        ordered = sorted(
            (row for row in visible if row.lane_index == lane),
            key=lambda row: row.x_m,
            reverse=True,
        )
        if any(
            abs(left.x_m - right.x_m - spacing) > tolerance
            for left, right in zip(ordered, ordered[1:])
        ):
            consistent = False
    signature = repr(
        (
            tuple(
                (index - 2, lane, row.track_id)
                for index, layer in enumerate(slots)
                for lane, row in enumerate(layer)
                if row is not None
            ),
            tuple(
                sorted(
                    (row.track_id, -1 if row.lane_index is None else row.lane_index)
                    for row in visible
                )
            ),
        )
    )
    return LayerWindow(
        tuple(tuple(layer) for layer in slots), consistent, crossing, speed_stable, signature
    )


def choose_layered_fill(ego, vehicles, lane_centers_m, p):
    """按稳定门、前层完整性和物理车道次序选择唯一补位车辆。"""
    window = layered_window(ego, vehicles, lane_centers_m, p)
    lane_count = len(lane_centers_m)
    counts = tuple(
        sum(layer[lane] is not None for layer in window.layers) for lane in range(lane_count)
    )

    def wait(reason):
        return JoinDecision(None, None, None, reason, counts)

    if window.crossing or not window.consistent or not window.speed_stable:
        return wait("layer_not_stable")
    previous, current = window.layers[1:3]
    if not any(previous):
        return wait("head_layer")
    if all(previous):
        return wait("previous_full")
    if any(window.layers[0]) and not all(window.layers[0]):
        return wait("two_previous_incomplete")
    occupied = tuple(lane for lane, row in enumerate(current) if row is not None)
    missing = tuple(lane for lane, row in enumerate(previous) if row is None)
    options = tuple(
        (source, target) for source in occupied for target in missing if source != target
    )
    if not options:
        return wait("current_layer_not_actionable")
    if len(occupied) == 1:
        chosen_lane, target_lane = max(options, key=lambda pair: (abs(pair[0] - pair[1]), pair[1]))
    else:
        chosen_lane, target_lane = min(
            options, key=lambda pair: (abs(pair[0] - pair[1]), -pair[0], -pair[1])
        )
    if current[chosen_lane] is not ego:
        return wait("other_physical_candidate")
    anchor_order = (lane_count - 1, 0, *range(lane_count - 2, 0, -1))
    anchors = tuple(row for row in (previous[lane] for lane in anchor_order) if row is not None)
    if not anchors:
        return wait("previous_anchor_missing")
    anchor = anchors[0]
    outer_base = anchor.x_m + _phase(anchor.lane_index, lane_count, p)
    target_x = outer_base - _phase(target_lane, lane_count, p)
    return JoinDecision(target_lane, target_x, anchor.track_id, "layer_fill", counts)


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
        "stable_window_signature",
    }
    unknown = set(value) - base_names - private_names
    if unknown:
        raise ValueError("Unexpected SimpleFormationMemory fields")
    reference = value.pop("reference_track_id", None)
    anchor = value.pop("join_anchor_track_id", None)
    desired_lane = value.pop("desired_lane_index", None)
    join_phase = value.pop("join_phase", "FREE")
    stable_since = value.pop("stable_since_s", None)
    window_signature = value.pop("stable_window_signature", None)
    if window_signature is not None and (type(window_signature) is not str or not window_signature):
        raise ValueError("Invalid local layer signature")
    for name, track_id in (("reference", reference), ("join anchor", anchor)):
        if track_id is not None and (type(track_id) is not int or track_id < 0):
            raise ValueError("Invalid local " + name + " track")
    if desired_lane is not None and (type(desired_lane) is not int or not 0 <= desired_lane <= 3):
        raise ValueError("Invalid desired local lane")
    if type(join_phase) is not str or join_phase not in (
        "FREE",
        "JOINING",
        "STABILIZING",
        "FORMED",
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
        stable_window_signature=window_signature,
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
    ego_vy = ego.vx_mps * s + ego.vy_mps * c
    rows = []
    for detection in control.observation.neighbors:
        if type(detection.track_id) is not int or detection.track_id < 0:
            raise ValueError("Invalid local sensor track")
        x_m = ego.x_m + c * detection.relative_x_m - s * detection.relative_y_m
        y_m = ego.y_m + s * detection.relative_x_m + c * detection.relative_y_m
        vx_mps = ego_vx + c * detection.relative_vx_mps - s * detection.relative_vy_mps
        vy_mps = ego_vy + s * detection.relative_vx_mps + c * detection.relative_vy_mps
        heading = ego.heading_rad + detection.relative_heading_rad
        lateral_half = (
            abs(math.cos(heading)) * detection.width_m + abs(math.sin(heading)) * detection.length_m
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
        rows.append(LocalVehicle(detection.track_id, x_m, y_m, vx_mps, associated, vy_mps))
    return tuple(rows)
