"""Pure, deterministic geometry primitives for Phase 5G lane candidates."""

from dataclasses import asdict, dataclass, replace
from collections.abc import Iterable, Mapping
import math

from noa.prediction import measured_bodies


_FORMATION_PHASE_D_M = 15.0
MASK64 = (1 << 64) - 1


def _finite_number(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be finite and representable") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _exact_int(name, value):
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact int")
    return value


def _finite_computation(name, value):
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} is not representable") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} is not representable")
    return number


def _finite_product(name, left, right):
    try:
        value = left * right
    except OverflowError as error:
        raise ValueError(f"{name} is not representable") from error
    return _finite_computation(name, value)


def _finite_difference(name, left, right):
    try:
        value = left - right
    except OverflowError as error:
        raise ValueError(f"{name} is not representable") from error
    return _finite_computation(name, value)


@dataclass(frozen=True, slots=True)
class LaneCandidate:
    lane_index: int
    target_y_m: float
    target_x_m: float
    reference_signature: tuple[float, ...] | None
    satisfied_relations: int
    max_residual_m: float
    residual_sum_m: float
    changes_lane: bool

    def __post_init__(self):
        lane_index = _exact_int("lane_index", self.lane_index)
        if lane_index < 0:
            raise ValueError("lane_index must be nonnegative")
        satisfied_relations = _exact_int("satisfied_relations", self.satisfied_relations)
        if satisfied_relations < 0:
            raise ValueError("satisfied_relations must be nonnegative")
        if type(self.changes_lane) is not bool:
            raise TypeError("changes_lane must be an exact bool")

        target_y_m = _finite_number("target_y_m", self.target_y_m)
        target_x_m = _finite_number("target_x_m", self.target_x_m)
        max_residual_m = _finite_number("max_residual_m", self.max_residual_m)
        residual_sum_m = _finite_number("residual_sum_m", self.residual_sum_m)
        if max_residual_m < 0 or residual_sum_m < 0:
            raise ValueError("residual values must be nonnegative")

        signature = self.reference_signature
        if signature is not None:
            if type(signature) is not tuple:
                raise TypeError("reference_signature must be a tuple or None")
            if len(signature) != 7:
                raise ValueError("reference_signature must contain exactly seven fields")
            signature = tuple(
                _finite_number(f"reference_signature[{index}]", value)
                for index, value in enumerate(signature)
            )
            if signature[-2] <= 0 or signature[-1] <= 0:
                raise ValueError("reference_signature length and width must be positive")

        object.__setattr__(self, "target_y_m", target_y_m)
        object.__setattr__(self, "target_x_m", target_x_m)
        object.__setattr__(self, "max_residual_m", max_residual_m)
        object.__setattr__(self, "residual_sum_m", residual_sum_m)
        object.__setattr__(self, "reference_signature", signature)


def phase_residual_m(
    ego_x_m: float,
    ego_lane: int,
    other_x_m: float,
    other_lane: int,
    d_m: float,
) -> float:
    """Return distance to the nearest point of the staggered phase lattice."""
    ego_x_m = _finite_number("ego_x_m", ego_x_m)
    other_x_m = _finite_number("other_x_m", other_x_m)
    ego_lane = _exact_int("ego_lane", ego_lane)
    other_lane = _exact_int("other_lane", other_lane)
    d_m = _finite_number("d_m", d_m)
    if d_m <= 0:
        raise ValueError("d_m must be positive")
    period = _finite_product("phase period", 2.0, d_m)
    ego_lane_offset = _finite_product("ego lane offset", ego_lane, d_m)
    other_lane_offset = _finite_product("other lane offset", other_lane, d_m)
    ego_position = _finite_difference("ego corrected position", ego_x_m, ego_lane_offset)
    other_position = _finite_difference("other corrected position", other_x_m, other_lane_offset)
    delta = _finite_difference("phase delta", ego_position, other_position)
    try:
        remainder = math.remainder(delta, period)
    except (OverflowError, ValueError) as error:
        raise ValueError("phase residual is not representable") from error
    return abs(_finite_computation("phase residual", remainder))


def _lane_index(name: str, value: int) -> int:
    lane = _exact_int(name, value)
    if lane < 0:
        raise ValueError(f"{name} must be nonnegative")
    return lane


def target_spacing_m(
    candidate_lane: int, reference_lane: int, d_m: float
) -> float | None:
    """Return the registered gap behind a same or adjacent-lane reference."""
    candidate_lane = _lane_index("candidate_lane", candidate_lane)
    reference_lane = _lane_index("reference_lane", reference_lane)
    d_m = _finite_number("d_m", d_m)
    if d_m <= 0:
        raise ValueError("d_m must be positive")
    lane_distance = abs(candidate_lane - reference_lane)
    if lane_distance == 0:
        return _finite_product("same-lane target spacing", 2.0, d_m)
    if lane_distance == 1:
        return d_m
    return None


def priority_relation(
    ego_x_m: float,
    ego_lane: int,
    peer_x_m: float,
    peer_lane: int,
    peer_entered: bool,
    peer_inward: bool,
    front_margin_m: float,
) -> str:
    """Resolve one visible pair using the fixed Phase 5G precedence."""
    ego_x_m = _finite_number("ego_x_m", ego_x_m)
    peer_x_m = _finite_number("peer_x_m", peer_x_m)
    ego_lane = _lane_index("ego_lane", ego_lane)
    peer_lane = _lane_index("peer_lane", peer_lane)
    if type(peer_entered) is not bool:
        raise TypeError("peer_entered must be an exact bool")
    if type(peer_inward) is not bool:
        raise TypeError("peer_inward must be an exact bool")
    front_margin_m = _finite_number("front_margin_m", front_margin_m)
    if front_margin_m <= 0:
        raise ValueError("front_margin_m must be positive")
    if peer_entered:
        return "yield_entered"
    if peer_inward:
        return "yield_visible_inward_motion"
    longitudinal_offset = _finite_difference(
        "priority longitudinal offset", peer_x_m, ego_x_m
    )
    if longitudinal_offset > front_margin_m:
        return "yield_visible_front"
    if longitudinal_offset < -front_margin_m:
        return "ego_visible_front"
    if peer_lane > ego_lane:
        return "yield_upper_lane"
    if ego_lane > peer_lane:
        return "ego_upper_lane"
    return "ambiguous"


def _positive_parameter(parameters: Mapping[str, object], name: str) -> float:
    if name not in parameters:
        raise ValueError(f"missing required parameter: {name}")
    value = _finite_number(name, parameters[name])
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _visible_centers(road: object, tolerance_m: float) -> tuple[tuple[float, ...], int]:
    try:
        raw_centers = road.centers_m
        raw_current = road.current_center_m
    except AttributeError as error:
        raise TypeError("road must expose centers_m and current_center_m") from error
    if type(raw_centers) is not tuple or not raw_centers:
        raise ValueError("road.centers_m must be a nonempty tuple")
    centers = tuple(
        _finite_number(f"road.centers_m[{index}]", center)
        for index, center in enumerate(raw_centers)
    )
    if any(after - before <= tolerance_m for before, after in zip(centers, centers[1:])):
        raise ValueError("road.centers_m must be uniquely ordered physical centers")
    current = _finite_number("road.current_center_m", raw_current)
    matches = tuple(
        index for index, center in enumerate(centers) if abs(center - current) <= tolerance_m
    )
    if len(matches) != 1:
        raise ValueError("road.current_center_m has ambiguous visible lane association")
    return centers, matches[0]


def _physical_lane(
    y_m: float,
    centers_m: tuple[float, ...],
    stability_m: float,
    tolerance_m: float,
) -> int:
    y_m = _finite_number("visible body y_m", y_m)
    distances = tuple(abs(y_m - center) for center in centers_m)
    nearest = min(distances)
    matches = tuple(
        index for index, distance in enumerate(distances)
        if distance <= nearest + tolerance_m
    )
    if len(matches) != 1:
        raise ValueError("visible body has ambiguous physical lane association")
    if nearest > stability_m + tolerance_m:
        raise ValueError("visible body has unstable physical lane association")
    return matches[0]


def _body_signature(body: object) -> tuple[float, ...]:
    signature = tuple(
        _finite_number(name, getattr(body, attribute))
        for name, attribute in (
            ("visible body x_m", "x"),
            ("visible body y_m", "y"),
            ("visible body vx_mps", "vx"),
            ("visible body vy_mps", "vy"),
            ("visible body heading_rad", "heading"),
            ("visible body length_m", "length"),
            ("visible body width_m", "width"),
        )
    )
    if signature[-2] <= 0 or signature[-1] <= 0:
        raise ValueError("visible body length and width must be positive")
    return signature


def visible_lane_candidates(
    control: object, road: object, parameters: Mapping[str, object]
) -> tuple[LaneCandidate, ...]:
    """Build immutable stay/adjacent-lane targets from current visible physics."""
    if not isinstance(parameters, Mapping):
        raise TypeError("parameters must be a mapping")
    geometry_tolerance_m = _positive_parameter(parameters, "noa_geometry_tolerance_m")
    lane_stability_m = _positive_parameter(
        parameters, "noa_completion_lateral_error_m"
    )
    relation_tolerance_m = _positive_parameter(
        parameters, "formation_position_tolerance_m"
    )
    centers_m, current_lane = _visible_centers(road, geometry_tolerance_m)
    try:
        ego_x_m = _finite_number("control.ego.x_m", control.ego.x_m)
    except AttributeError as error:
        raise TypeError("control must expose ego and local observation fields") from error

    bodies = measured_bodies(control)
    rows = tuple(
        (
            body,
            _body_signature(body),
            _physical_lane(
                body.y, centers_m, lane_stability_m, geometry_tolerance_m
            ),
        )
        for body in bodies
    )

    def build_candidate(
        lane_index: int,
        target_x_m: float,
        reference_signature: tuple[float, ...] | None,
    ) -> LaneCandidate:
        residuals = tuple(
            phase_residual_m(
                target_x_m, lane_index, body.x, body_lane, _FORMATION_PHASE_D_M
            )
            for body, _, body_lane in rows
        )
        satisfied = sum(
            residual <= relation_tolerance_m + geometry_tolerance_m
            for residual in residuals
        )
        try:
            residual_sum = math.fsum(residuals)
        except (OverflowError, ValueError) as error:
            raise ValueError("candidate residual sum is not representable") from error
        return LaneCandidate(
            lane_index=lane_index,
            target_y_m=centers_m[lane_index],
            target_x_m=target_x_m,
            reference_signature=reference_signature,
            satisfied_relations=satisfied,
            max_residual_m=max(residuals, default=0.0),
            residual_sum_m=_finite_computation("candidate residual sum", residual_sum),
            changes_lane=lane_index != current_lane,
        )

    candidates = [build_candidate(current_lane, ego_x_m, None)]
    adjacent_lanes = tuple(
        lane_index
        for lane_index in range(len(centers_m))
        if abs(lane_index - current_lane) == 1
    )
    for lane_index in adjacent_lanes:
        for body, signature, reference_lane in rows:
            if body.x <= ego_x_m + geometry_tolerance_m:
                continue
            spacing_m = target_spacing_m(
                lane_index, reference_lane, _FORMATION_PHASE_D_M
            )
            if spacing_m is None:
                continue
            target_x_m = _finite_difference(
                "candidate target x_m", body.x, spacing_m
            )
            candidate = build_candidate(lane_index, target_x_m, signature)
            if candidate not in candidates:
                candidates.append(candidate)
    return tuple(candidates)


def candidate_key(candidate: LaneCandidate) -> tuple[int, float, float, bool, int]:
    """Return the fixed lexicographic order used for candidate selection."""
    if not isinstance(candidate, LaneCandidate):
        raise TypeError("candidate must be a LaneCandidate")
    return (
        -candidate.satisfied_relations,
        candidate.max_residual_m,
        candidate.residual_sum_m,
        candidate.changes_lane,
        -candidate.lane_index,
    )


def rank_candidates(
    candidates: Iterable[LaneCandidate], minimum_gain: int
) -> tuple[LaneCandidate, ...]:
    """Return eligible candidates sorted by the fixed Phase 5G order."""
    minimum_gain = _exact_int("minimum_gain", minimum_gain)
    if minimum_gain < 1:
        raise ValueError("minimum_gain must be at least one")
    try:
        rows = tuple(candidates)
    except TypeError as error:
        raise TypeError("candidates must be iterable") from error
    if not rows:
        raise ValueError("candidates must be nonempty")
    for candidate in rows:
        if not isinstance(candidate, LaneCandidate):
            raise TypeError("candidates must contain only LaneCandidate values")

    stays = tuple(candidate for candidate in rows if not candidate.changes_lane)
    if not stays:
        raise ValueError("candidates must include at least one stay candidate")
    stay = min(stays, key=candidate_key)
    eligible = tuple(
        candidate
        for candidate in rows
        if not candidate.changes_lane
        or candidate.satisfied_relations >= stay.satisfied_relations + minimum_gain
    )
    return tuple(sorted(eligible, key=candidate_key))


def draw_uniform(state: int) -> tuple[int, int, float]:
    """Advance one private SplitMix64 stream without external identity input."""
    if type(state) is not int or not 0 <= state <= MASK64:
        raise ValueError("private Phase 5G RNG state must be an exact uint64")
    state = (state + 0x9E3779B97F4A7C15) & MASK64
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    word = z ^ (z >> 31)
    return state, word, word / float(1 << 64)


def validate_lane_change_parameters(parameters: Mapping[str, object]) -> None:
    """Validate only the registered Phase 5G controller parameters."""
    for name in (
        "formation_lane_stable_s",
        "formation_lane_lock_s",
        "formation_lane_front_margin_m",
        "formation_lane_backoff_min_s",
        "formation_lane_backoff_max_s",
    ):
        _positive_parameter(parameters, name)
    if (
        parameters["formation_lane_backoff_max_s"]
        <= parameters["formation_lane_backoff_min_s"]
    ):
        raise ValueError("formation lane backoff maximum must exceed minimum")
    durations = parameters.get("formation_lane_duration_candidates_s")
    if type(durations) not in (list, tuple) or tuple(durations) != (5.0, 7.5, 10.0):
        raise ValueError("formation lane durations must be exactly 5.0, 7.5, 10.0 s")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in durations):
        raise ValueError("formation lane durations must be finite numbers")
    gain = parameters.get("formation_lane_min_relation_gain")
    if type(gain) is not int or gain < 1:
        raise ValueError("formation lane minimum relation gain must be a positive exact int")


def lane_candidate_signature(candidate: LaneCandidate) -> tuple:
    """Return permitted physical state for bounded cross-frame association."""
    if not isinstance(candidate, LaneCandidate) or candidate.reference_signature is None:
        raise ValueError("formation lane candidate must have a visible physical reference")
    return (candidate.lane_index,) + candidate.reference_signature


def _compatible_reference(
    previous: tuple[float, ...],
    current: tuple[float, ...],
    elapsed_s: float,
    parameters: Mapping[str, object],
) -> bool:
    """Conservative physical compatibility, never an identity certificate."""
    tolerance_m = _positive_parameter(parameters, "noa_geometry_tolerance_m")
    if elapsed_s < 0 or not math.isfinite(elapsed_s):
        return False
    if elapsed_s == 0:
        return previous == current
    acceleration_bound = max(
        abs(_finite_number("min_accel_mps2", parameters["min_accel_mps2"])),
        _finite_number("max_accel_mps2", parameters["max_accel_mps2"]),
    )
    maximum_speed = _positive_parameter(parameters, "max_speed_mps")
    maximum_steering = _positive_parameter(parameters, "max_steering_rad")
    wheelbase = _positive_parameter(parameters, "wheelbase_m")
    yaw_bound = maximum_speed * abs(math.tan(maximum_steering)) / wheelbase
    lateral_acceleration_bound = acceleration_bound + maximum_speed * yaw_bound
    x_bound = 0.5 * acceleration_bound * elapsed_s * elapsed_s + tolerance_m
    y_bound = 0.5 * lateral_acceleration_bound * elapsed_s * elapsed_s + tolerance_m
    velocity_bound = lateral_acceleration_bound * elapsed_s + tolerance_m
    heading_error = abs(
        math.atan2(
            math.sin(current[4] - previous[4]),
            math.cos(current[4] - previous[4]),
        )
    )
    return (
        abs(current[0] - previous[0] - previous[2] * elapsed_s) <= x_bound
        and abs(current[1] - previous[1] - previous[3] * elapsed_s) <= y_bound
        and abs(current[2] - previous[2]) <= velocity_bound
        and abs(current[3] - previous[3]) <= velocity_bound
        and heading_error <= yaw_bound * elapsed_s + tolerance_m
        and abs(current[5] - previous[5]) <= tolerance_m
        and abs(current[6] - previous[6]) <= tolerance_m
    )


def associate_lane_candidate(
    previous_signature: tuple | None,
    candidates: Iterable[LaneCandidate],
    elapsed_s: float,
    parameters: Mapping[str, object],
) -> tuple[LaneCandidate | None, str]:
    """Uniquely associate a moving intent by lane plus bounded reference physics."""
    rows = tuple(candidates)
    if previous_signature is None:
        return None, "new"
    if type(previous_signature) is not tuple or len(previous_signature) != 8:
        return None, "unknown"
    if type(previous_signature[0]) is not int:
        return None, "unknown"
    if (
        not math.isfinite(elapsed_s)
        or elapsed_s < 0
        or elapsed_s > parameters["control_sync_dt_s"] + 1e-9
    ):
        return None, "new"
    matches = tuple(
        candidate
        for candidate in rows
        if candidate.reference_signature is not None
        and candidate.lane_index == previous_signature[0]
        and _compatible_reference(
            previous_signature[1:],
            candidate.reference_signature,
            elapsed_s,
            parameters,
        )
    )
    if len(matches) == 1:
        return matches[0], "same"
    return (None, "new") if not matches else (None, "unknown")


def _half_extents(body: object) -> tuple[float, float]:
    cosine, sine = abs(math.cos(body.heading)), abs(math.sin(body.heading))
    return (
        (body.length * cosine + body.width * sine) / 2.0,
        (body.length * sine + body.width * cosine) / 2.0,
    )


def physical_priority(
    control: object,
    road: object,
    candidate: LaneCandidate,
    parameters: Mapping[str, object],
) -> dict:
    """Assess only visible physical competitors for one target corridor.

    A normally centred vehicle in the target lane is a gap anchor handled by
    the unchanged swept guard, not a competing lane entrant. Potential entrants
    come from an adjacent source lane and are close enough to seek the same
    local longitudinal space. Results do not use observation order or labels.
    """
    tolerance_m = _positive_parameter(parameters, "noa_geometry_tolerance_m")
    front_margin_m = _positive_parameter(parameters, "formation_lane_front_margin_m")
    centers_m, ego_lane = _visible_centers(road, tolerance_m)
    if candidate.lane_index >= len(centers_m):
        raise ValueError("candidate lane is outside visible physical centers")
    target_lane = candidate.lane_index
    target_center = centers_m[target_lane]
    if len(centers_m) == 1:
        half_strip = _positive_parameter(parameters, "lane_width_m") / 2.0
    elif target_lane == 0:
        half_strip = (centers_m[1] - centers_m[0]) / 2.0
    elif target_lane == len(centers_m) - 1:
        half_strip = (centers_m[-1] - centers_m[-2]) / 2.0
    else:
        half_strip = min(
            centers_m[target_lane] - centers_m[target_lane - 1],
            centers_m[target_lane + 1] - centers_m[target_lane],
        ) / 2.0
    reference = candidate.reference_signature
    ego_half_length = _positive_parameter(parameters, "length_m") / 2.0
    relations = []
    participants = []
    for body in measured_bodies(control):
        signature = _body_signature(body)
        peer_lane = _physical_lane(
            body.y,
            centers_m,
            _positive_parameter(parameters, "noa_completion_lateral_error_m"),
            tolerance_m,
        )
        # The selected reference is merely a swept-guard gap anchor when its
        # visible geometry places it normally in the target lane.  A reference
        # still in an adjacent source lane has no identity-based exemption: its
        # current overlap/inward motion competes for the same physical corridor.
        if reference is not None and signature == reference and peer_lane == target_lane:
            continue
        if peer_lane == target_lane or abs(peer_lane - target_lane) != 1:
            continue
        half_length, half_width = _half_extents(body)
        entered = (
            body.y + half_width > target_center - half_strip + tolerance_m
            and body.y - half_width < target_center + half_strip - tolerance_m
        )
        inward = (target_center - body.y) * body.vy > tolerance_m
        conflict_radius = ego_half_length + half_length + front_margin_m
        if not entered and not inward and abs(body.x - control.ego.x_m) > conflict_radius:
            continue
        relation = priority_relation(
            control.ego.x_m,
            ego_lane,
            body.x,
            peer_lane,
            entered,
            inward,
            front_margin_m,
        )
        relations.append(relation)
        participants.append(signature)
    if not relations:
        reason = "no_potential_competition"
        blocking = False
    elif (
        any(relation.startswith("yield_") for relation in relations)
        and any(relation.startswith("ego_") for relation in relations)
    ):
        reason = "ambiguous"
        blocking = True
    elif any(relation.startswith("yield_") for relation in relations):
        precedence = (
            "yield_entered",
            "yield_visible_inward_motion",
            "yield_visible_front",
            "yield_upper_lane",
        )
        reason = next(value for value in precedence if value in relations)
        blocking = True
    elif all(relation.startswith("ego_") for relation in relations):
        reason = "ego_priority"
        blocking = False
    else:
        reason = "ambiguous"
        blocking = True
    return {
        "reason": reason,
        "blocking": blocking,
        "participant_signatures": tuple(sorted(participants)),
        "pair_relations": tuple(sorted(relations)),
        "target_lane_index": target_lane,
        "target_y_m": candidate.target_y_m,
    }


def advance_private_backoff(
    memory: object,
    candidate_signature: tuple,
    same_episode: bool,
    priority_reason: str,
    now_s: float,
    parameters: Mapping[str, object],
) -> tuple[object, dict]:
    """Apply at most one private draw to one bounded physical episode."""
    if type(same_episode) is not bool:
        raise TypeError("same_episode must be an exact bool")
    now_s = _finite_number("now_s", now_s)
    drawn = []
    updated = memory
    deadline = memory.formation_lane_backoff_until_s if same_episode else None
    if priority_reason == "ambiguous":
        if deadline is None:
            if memory.formation_lane_rng_state is None:
                return memory, {
                    "blocking": True,
                    "reason": "missing_private_rng_state",
                    "deadline_s": None,
                    "draw_count": memory.formation_lane_draw_count,
                    "draws_this_tick": 0,
                    "draws": (),
                }
            state, word, unit = draw_uniform(memory.formation_lane_rng_state)
            delay = parameters["formation_lane_backoff_min_s"] + unit * (
                parameters["formation_lane_backoff_max_s"]
                - parameters["formation_lane_backoff_min_s"]
            )
            deadline = now_s + delay
            updated = replace(
                memory,
                formation_lane_signature=candidate_signature,
                formation_lane_rng_state=state,
                formation_lane_draw_count=memory.formation_lane_draw_count + 1,
                formation_lane_backoff_until_s=deadline,
            )
            drawn.append({"word_u64": word, "unit_interval": unit, "delay_s": delay})
        blocking = now_s < deadline - 1e-9
        reason = "private_backoff_wait" if blocking else "private_backoff_expired"
    else:
        updated = replace(updated, formation_lane_backoff_until_s=None)
        blocking = priority_reason.startswith("yield_")
        reason = priority_reason
    return updated, {
        "blocking": blocking,
        "reason": reason,
        "deadline_s": updated.formation_lane_backoff_until_s,
        "draw_count": updated.formation_lane_draw_count,
        "draws_this_tick": len(drawn),
        "draws": tuple(drawn),
        "association_scope": (
            "target physical lane plus unique bounded reference motion; "
            "no simulator identity"
        ),
    }


def candidate_diagnostic(candidate: LaneCandidate) -> dict:
    """JSON-ready immutable candidate evidence without sensor labels."""
    return asdict(candidate)
