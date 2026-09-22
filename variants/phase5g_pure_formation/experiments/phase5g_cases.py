"""Deterministic, replayable pure-formation departure inputs for Phase 5G.

This offline registry never reaches a controller.  Private states are derived
from the registered case seed and a stable physical-row ordinal, never from an
actor key or simulator identifier.
"""

from dataclasses import asdict, fields, replace
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
import random
import sys
from typing import Iterable, Mapping, Sequence
from uuid import uuid4

from experiments.phase5_detection import detect_frames
from models.geometry import body_from_state
from models.kinematic import kinematic_state
from models.vehicle import VehicleState
from noa.formation import FormationMemory
from safety.geometry import collide, swept_collision


SCHEMA = "phase5g_pure_formation_cases_v1"
SOURCE_PATH = "experiments/phase5g_cases.py"
SUPPORTED_COUNTS = (3, 4, 5, 6, 7, 8, 12)
DEV_SEEDS = (101, 102, 103)
HOLDOUT_SEEDS = (5101, 5102, 5103, 5104, 5105)
LANE_CENTERS_M = (1.65, 4.95, 8.25)
DURATION_S = 45.0
CONTROL_DT_S = 0.1
DEPART_INTERVAL_MIN_S = 2.5
DEPART_INTERVAL_MAX_S = 4.0
FORMATION_DEADLINE_S = 30.0
FORMATION_HOLD_S = 10.0
SPAWN_X_M = 100.0
MAIN_SIX = (
    ("v0", 100.0, 1.65, 10.0),
    ("v1", 145.0, 1.65, 9.5),
    ("v2", 190.0, 1.65, 10.5),
    ("v3", 122.0, 4.95, 10.5),
    ("v4", 167.0, 4.95, 9.5),
    ("v5", 108.0, 8.25, 10.0),
)

_STATE_FIELDS = tuple(field.name for field in fields(VehicleState))


def canonical_json_bytes(value: object) -> bytes:
    """Return the one accepted UTF-8 JSON representation."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def digest_json(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _source_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _config_hash() -> str:
    return hashlib.sha256((Path(__file__).resolve().parents[1] / "configs" / "phase5g.json").read_bytes()).hexdigest()


def _finite(name: str, value: object) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not bool")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number, not bool") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number, not bool")
    return number


def _seed(value: object) -> int:
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError("case seed must be an exact uint64 integer, not bool")
    return value


def _speed_bounds(parameters: Mapping[str, object], low: object,
                  high: object) -> tuple[float, float]:
    low = _finite("speed_min_mps", low)
    high = _finite("speed_max_mps", high)
    if low < 0 or high <= low:
        raise ValueError("initial speed bounds must satisfy 0 <= minimum < maximum")
    maximum = _finite("max_speed_mps", parameters["max_speed_mps"])
    if maximum <= 0:
        raise ValueError("max_speed_mps must be positive")
    if high > maximum:
        raise ValueError("speed_max_mps must not exceed model max_speed_mps")
    return low, high


def _interval_bounds(low: object, high: object) -> tuple[float, float]:
    low = _finite("depart_interval_min_s", low)
    high = _finite("depart_interval_max_s", high)
    if low <= 0 or high < low:
        raise ValueError("departure interval bounds must satisfy 0 < minimum <= maximum")
    scaled_low = low / CONTROL_DT_S
    scaled_high = high / CONTROL_DT_S
    if not math.isfinite(scaled_low) or not math.isfinite(scaled_high):
        raise ValueError("departure interval is too large for a 0.1 s control tick")
    first_tick = math.ceil(scaled_low - 1e-12)
    last_tick = math.floor(scaled_high + 1e-12)
    if first_tick > last_tick:
        raise ValueError("departure interval bounds contain no 0.1 s control tick")
    return low, high


def _actor_keys(count: int, actor_keys: Sequence[str] | None) -> tuple[str, ...]:
    keys = tuple(f"v{index}" for index in range(count)) if actor_keys is None else tuple(actor_keys)
    if len(keys) != count or len(set(keys)) != count:
        raise ValueError("actor keys must be unique and exactly match the vehicle count")
    if any(type(key) is not str or not key for key in keys):
        raise ValueError("actor keys must be nonempty strings")
    return keys


def _private_state(case_seed: int, vehicle_count: int, ordinal: int) -> int:
    material = f"phase5g-private-v1:{case_seed}:{vehicle_count}:{ordinal}".encode("ascii")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _memories(keys: tuple[str, ...], case_seed: int, vehicle_count: int) -> tuple[dict, dict]:
    states = {
        key: _private_state(case_seed, vehicle_count, ordinal)
        for ordinal, key in enumerate(keys)
    }
    if len(set(states.values())) != len(states):
        raise RuntimeError("deterministic private uint64 derivation collided")
    memories = {
        key: asdict(FormationMemory((), "CRUISE", formation_lane_rng_state=states[key]))
        for key in keys
    }
    provenance = {
        "algorithm": "SplitMix64",
        "version": 1,
        "source": "sha256_case_seed_vehicle_count_and_stable_physical_ordinal_v1",
        "case_seed": case_seed,
        "vehicle_count": vehicle_count,
        "states_by_actor": states,
        "stable_ordinal_by_actor": {key: ordinal for ordinal, key in enumerate(keys)},
        "actor_identity_used": False,
        "online_initialization": False,
    }
    return memories, provenance


def _lane_index(y_m: float, tolerance_m: float = 1e-9) -> int | None:
    matches = [index for index, center in enumerate(LANE_CENTERS_M)
               if abs(y_m - center) <= tolerance_m]
    return matches[0] if len(matches) == 1 else None


def _future_body(state: VehicleState, parameters: Mapping[str, object], horizon_s: float):
    body = body_from_state(state, parameters)
    world_vx = state.vx_mps * math.cos(state.heading_rad) - state.vy_mps * math.sin(state.heading_rad)
    world_vy = state.vx_mps * math.sin(state.heading_rad) + state.vy_mps * math.cos(state.heading_rad)
    return replace(body, x=body.x + world_vx * horizon_s, y=body.y + world_vy * horizon_s,
                   heading=body.heading + state.yaw_rate_radps * horizon_s)


def dynamic_minimum_gap_ok(initial: Mapping[str, Mapping[str, object]],
                           parameters: Mapping[str, object]) -> bool:
    """Check the inherited standstill-plus-time-headway initial gap."""
    standstill = _finite("noa_standstill_gap_m", parameters["noa_standstill_gap_m"])
    headway = _finite("noa_headway_s", parameters["noa_headway_s"])
    length = _finite("length_m", parameters["length_m"])
    margin = _finite("noa_body_margin_m", parameters.get("noa_body_margin_m", 0.0))
    by_lane: dict[int, list[VehicleState]] = {lane: [] for lane in range(3)}
    for raw in initial.values():
        state = VehicleState(**raw)
        lane = _lane_index(state.y_m)
        if lane is None:
            return False
        by_lane[lane].append(state)
    for rows in by_lane.values():
        rows.sort(key=lambda state: state.x_m)
        for rear, front in zip(rows, rows[1:]):
            bumper_gap = front.x_m - rear.x_m - length - 2.0 * margin
            rear_speed = math.hypot(rear.vx_mps, rear.vy_mps)
            required = standstill + headway * rear_speed
            if bumper_gap < required - 1e-9:
                return False
    return True


def validate_initial(initial: Mapping[str, Mapping[str, object]],
                     parameters: Mapping[str, object]) -> dict:
    """Independently reject overlap, near-term swept overlap and unsafe gaps."""
    if not isinstance(initial, dict) or not initial:
        raise ValueError("initial states must be a nonempty actor dictionary")
    maximum_speed = _finite("max_speed_mps", parameters["max_speed_mps"])
    if maximum_speed <= 0:
        raise ValueError("max_speed_mps must be positive")
    states = {}
    speed_outside_model = False
    for key, raw in initial.items():
        if type(key) is not str or not isinstance(raw, dict) or set(raw) != set(_STATE_FIELDS):
            raise ValueError("every initial actor requires the exact VehicleState schema")
        if any(type(raw[name]) not in (int, float) or not math.isfinite(raw[name])
               for name in _STATE_FIELDS):
            raise ValueError("initial vehicle states must be finite and numeric")
        state = VehicleState(**raw)
        speed = math.hypot(state.vx_mps, state.vy_mps)
        speed_outside_model |= state.vx_mps < 0 or speed > maximum_speed + 1e-12
        states[key] = state
    horizon = _finite("noa_response_time_s", parameters["noa_response_time_s"])
    if horizon <= 0:
        raise ValueError("noa_response_time_s must be positive")
    bodies = {key: body_from_state(state, parameters) for key, state in states.items()}
    future = {key: _future_body(state, parameters, horizon) for key, state in states.items()}
    reasons = ["initial_speed_outside_model"] if speed_outside_model else []
    for left, right in combinations(states, 2):
        if collide(bodies[left], bodies[right]):
            reasons.append("initial_body_overlap")
        elif swept_collision(bodies[left], future[left], bodies[right], future[right]):
            reasons.append("response_horizon_swept_overlap")
    if not dynamic_minimum_gap_ok(initial, parameters):
        reasons.append("dynamic_minimum_gap_failed")
    detection = detect_frames([{"time_s": 0.0, "states": json.loads(json.dumps(initial))}])
    if not detection["frames"][0]["fleet_failure_reasons"]:
        reasons.append("initial_whole_formation_detected")
    return {"passed": not reasons, "failure_reasons": sorted(set(reasons)),
            "detector": detection}


def _case(name: str, initial: dict, keys: tuple[str, ...], case_seed: int,
          purpose: str, expected_lane_changes: dict, sampling: dict | None = None,
          *, duration_s: float = DURATION_S, departures: dict | None = None) -> dict:
    memories, provenance = _memories(keys, case_seed, len(keys))
    result = {
        "name": name,
        "duration_s": duration_s,
        "initial": initial,
        "controlled": list(keys),
        "scripts": {},
        "initial_memories": memories,
        "private_rng_provenance": provenance,
        "purpose": purpose,
        "expected_lane_changes": expected_lane_changes,
    }
    if sampling is not None:
        result["sampling"] = sampling
    if departures is not None:
        result["departures"] = departures
    return result


def main_six_case(parameters: Mapping[str, object],
                  actor_keys: Sequence[str] | None = None) -> dict:
    """Return the preregistered 3/2/1 six-car demonstration input."""
    keys = _actor_keys(6, actor_keys)
    initial = {
        target_key: asdict(kinematic_state(parameters, x_m=x, y_m=y, vx_mps=speed))
        for target_key, (_, x, y, speed) in zip(keys, MAIN_SIX)
    }
    audit = validate_initial(initial, parameters)
    if not audit["passed"]:
        raise RuntimeError("registered MAIN_SIX failed its pre-trajectory feasibility audit: "
                           + ",".join(audit["failure_reasons"]))
    return _case(
        "main_6_3_2_1", initial, keys, 0,
        "Fixed pure-formation 3/2/1 main case; every physical actor is controlled.",
        {"minimum": 1, "target_lane_counts": [2, 2, 2]},
    )


def seeded_case(parameters: Mapping[str, object], count: int, seed: int,
                *, speed_min_mps: float = 8.0, speed_max_mps: float = 12.0,
                depart_interval_min_s: float = DEPART_INTERVAL_MIN_S,
                depart_interval_max_s: float = DEPART_INTERVAL_MAX_S,
                actor_keys: Sequence[str] | None = None) -> dict:
    """Generate one deterministic sequential departure schedule.

    Only rows due at time zero are physical initial state.  Later rows remain
    offline experiment truth until the Phase 5G clock activates them.
    """
    if type(count) is not int or count not in SUPPORTED_COUNTS:
        raise ValueError("supported vehicle counts are exactly 3, 4, 5, 6, 7, 8, and 12")
    seed = _seed(seed)
    low, high = _speed_bounds(parameters, speed_min_mps, speed_max_mps)
    interval_low, interval_high = _interval_bounds(
        depart_interval_min_s, depart_interval_max_s,
    )
    keys = _actor_keys(count, actor_keys)
    rng = random.Random(seed)
    minimum_tick = math.ceil(interval_low / CONTROL_DT_S - 1e-12)
    maximum_tick = math.floor(interval_high / CONTROL_DT_S + 1e-12)
    if maximum_tick * max(1, count - 1) > sys.float_info.max:
        raise ValueError(
            "departure interval schedule is too large for a 0.1 s control tick"
        )
    raw_upper = maximum_tick * CONTROL_DT_S
    scheduled_tick = 0
    departures = {}
    for ordinal, key in enumerate(keys):
        if ordinal:
            raw_interval = rng.uniform(interval_low, raw_upper)
            interval_ticks = max(
                minimum_tick,
                math.ceil(raw_interval / CONTROL_DT_S - 1e-12),
            )
            scheduled_tick += interval_ticks
        lane_center = rng.choice(LANE_CENTERS_M)
        speed = rng.uniform(low, high)
        state = asdict(kinematic_state(
            parameters, x_m=SPAWN_X_M, y_m=lane_center, vx_mps=speed,
        ))
        departures[key] = {
            "scheduled_departure_s": round(scheduled_tick * CONTROL_DT_S, 1),
            "actual_departure_s": None,
            "state": state,
            "physical_ordinal": ordinal,
        }
    initial = {
        key: dict(row["state"])
        for key, row in departures.items()
        if row["scheduled_departure_s"] == 0.0
    }
    audit = validate_initial(initial, parameters)
    if not audit["passed"]:
        raise RuntimeError(
            "Phase 5G time-zero departure failed its pre-trajectory feasibility audit: "
            + ",".join(audit["failure_reasons"])
        )
    duration = round(
        max(row["scheduled_departure_s"] for row in departures.values())
        + FORMATION_DEADLINE_S + FORMATION_HOLD_S,
        1,
    )
    return _case(
        f"seeded_{count}_seed{seed}", initial, keys, seed,
        "Seeded sequential pure-formation departures; no actor is an obstacle or script.",
        {"minimum": 0, "target_lane_counts": None},
        {"seed": seed, "control_dt_s": CONTROL_DT_S,
         "departure_interval_range_s": [interval_low, interval_high],
         "speed_range_mps": [low, high]},
        duration_s=duration, departures=departures,
    )


def _validated_specs(case_specs: Iterable[Sequence[int]]) -> tuple[tuple[int, int], ...]:
    try:
        specs = tuple(tuple(spec) for spec in case_specs)
    except TypeError as error:
        raise ValueError("case_specs must be an iterable of count/seed pairs") from error
    if not specs or any(len(spec) != 2 for spec in specs):
        raise ValueError("case_specs must contain count/seed pairs")
    checked = []
    for count, seed in specs:
        if type(count) is not int or count not in SUPPORTED_COUNTS:
            raise ValueError("supported vehicle counts are exactly 3, 4, 5, 6, 7, 8, and 12")
        checked.append((count, _seed(seed)))
    if len(set(checked)) != len(checked):
        raise ValueError("case_specs must not contain duplicate count/seed pairs")
    return tuple(checked)


def build_cases(parameters: Mapping[str, object], case_specs: Iterable[Sequence[int]],
                *, speed_min_mps: float = 8.0,
                speed_max_mps: float = 12.0) -> list[dict]:
    specs = _validated_specs(case_specs)
    low, high = _speed_bounds(parameters, speed_min_mps, speed_max_mps)
    return [main_six_case(parameters)] + [
        seeded_case(parameters, count, seed, speed_min_mps=low, speed_max_mps=high)
        for count, seed in specs
    ]


def physical_case(case: Mapping[str, object]) -> dict:
    return {key: value for key, value in case.items()
            if key not in ("initial_memories", "private_rng_provenance")}


def build_bundle(parameters: Mapping[str, object], case_specs: Iterable[Sequence[int]],
                 *, speed_min_mps: float = 8.0,
                 speed_max_mps: float = 12.0) -> dict:
    specs = _validated_specs(case_specs)
    low, high = _speed_bounds(parameters, speed_min_mps, speed_max_mps)
    cases = build_cases(parameters, specs, speed_min_mps=low, speed_max_mps=high)
    envelope = {
        "schema": SCHEMA,
        "source_path": SOURCE_PATH,
        "generator_sha256": _source_hash(),
        "config_sha256": _config_hash(),
        "model_parameters_sha256": digest_json(dict(parameters)),
        "development_seeds": list(DEV_SEEDS),
        "holdout_seeds": list(HOLDOUT_SEEDS),
        "case_specs": [list(spec) for spec in specs],
        "speed_range_mps": [low, high],
        "physical_sha256": digest_json([physical_case(case) for case in cases]),
        "initial_state_sha256": digest_json(cases),
        "cases": cases,
    }
    return {**envelope, "bundle_sha256": digest_json(envelope)}


def bundle_bytes(parameters: Mapping[str, object], case_specs: Iterable[Sequence[int]],
                 *, speed_min_mps: float = 8.0,
                 speed_max_mps: float = 12.0) -> bytes:
    return canonical_json_bytes(build_bundle(parameters, case_specs,
                                              speed_min_mps=speed_min_mps,
                                              speed_max_mps=speed_max_mps))


def _strict_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda token: (_ for _ in ()).throw(
                               ValueError(f"nonfinite JSON constant: {token}")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid UTF-8 Phase 5G case bundle") from error
    if not isinstance(value, dict):
        raise ValueError("Phase 5G case bundle must be one JSON object")
    return value


def load_bundle(source: str | Path | bytes | bytearray,
                parameters: Mapping[str, object],
                case_specs: Iterable[Sequence[int]], *,
                speed_min_mps: float = 8.0,
                speed_max_mps: float = 12.0) -> dict:
    """Strictly rebuild the envelope; self-resealed mutations remain invalid."""
    raw = bytes(source) if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
    data = _strict_json(raw)
    if raw != canonical_json_bytes(data):
        raise ValueError("Phase 5G case bundle is not canonical JSON bytes")
    expected = build_bundle(parameters, case_specs, speed_min_mps=speed_min_mps,
                            speed_max_mps=speed_max_mps)
    if canonical_json_bytes(data) != canonical_json_bytes(expected):
        raise ValueError("Phase 5G case source, schema, hash, memory, or physical input changed")
    return data


def freeze_cases(path: str | Path, parameters: Mapping[str, object],
                 case_specs: Iterable[Sequence[int]], *,
                 speed_min_mps: float = 8.0,
                 speed_max_mps: float = 12.0) -> dict:
    """Exclusively write an explicitly requested bundle (Task 9 chooses formal path)."""
    target = Path(path)
    if target.exists():
        raise FileExistsError(target)
    specs = _validated_specs(case_specs)
    low, high = _speed_bounds(parameters, speed_min_mps, speed_max_mps)
    payload = bundle_bytes(parameters, specs, speed_min_mps=low, speed_max_mps=high)
    # Reject malformed generated content before creating any filesystem object.
    load_bundle(payload, parameters, specs, speed_min_mps=low, speed_max_mps=high)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.{uuid4().hex}.staging"
    try:
        with staging.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        result = _validate_staged_bundle(
            staging, parameters, specs, low, high,
        )
    except Exception as error:
        raise RuntimeError(
            f"Phase 5G staging validation failed; staging preserved at {staging}"
        ) from error
    try:
        # Same-directory rename is atomic; on Windows it also refuses overwrite.
        os.rename(staging, target)
    except FileExistsError:
        raise
    except OSError as error:
        if target.exists():
            raise FileExistsError(target) from error
        raise RuntimeError(
            f"Phase 5G publish failed; staging preserved at {staging}"
        ) from error
    return result


def _validate_staged_bundle(path: Path, parameters: Mapping[str, object],
                            specs: tuple[tuple[int, int], ...], low: float,
                            high: float) -> dict:
    """Strict post-write check kept as a fault-injection seam for publishing."""
    return load_bundle(path, parameters, specs, speed_min_mps=low,
                       speed_max_mps=high)
