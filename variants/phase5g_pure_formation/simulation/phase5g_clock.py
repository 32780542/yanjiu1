"""Restore exact per-actor Phase 5G memory before the first frozen view."""

from dataclasses import fields
import hashlib
import json
import math
from types import MappingProxyType
from typing import Mapping

from noa.contracts import NoaMemory, memory_from_dict as noa_memory_from_dict
from noa.controller import decide as noa_decide
from noa.formation import FormationMemory, memory_from_dict as formation_memory_from_dict
from noa.simple_formation import (
    SimpleFormationMemory,
    memory_from_dict as simple_memory_from_dict,
)
from simulation.formation_clock import FormationClock


CLOCK_SCHEMA = "phase5g_pure_formation_v1"
PHASE5G_FIELDS = (
    "formation_lane_signature",
    "formation_lane_since_s",
    "formation_lane_lock_until_s",
    "formation_lane_rng_state",
    "formation_lane_draw_count",
    "formation_lane_backoff_until_s",
)
_NEUTRAL = {
    "formation_lane_signature": None,
    "formation_lane_since_s": None,
    "formation_lane_lock_until_s": None,
    "formation_lane_rng_state": None,
    "formation_lane_draw_count": 0,
    "formation_lane_backoff_until_s": None,
}
_OWN_BEHAVIORS = frozenset((
    "CRUISE", "FOLLOW", "EMERGENCY", "PREPARE_LC", "EXECUTE_LC", "MERGE",
    "R5_BACKOFF", "R5_YIELD",
))
_LANE_CHANGE_REASONS = frozenset((
    "", "observed_lane_end", "slower_visible_lead", "formation_geometry",
    "simple_formation_balance", "simple_formation_join",
))
_FORMATION_STATES = frozenset((
    "NOA_ONLY", "FALLBACK", "FORMING", "MAINTAINING", "RECONFIGURING",
))


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def initial_memory_hash(memories: object) -> str:
    return hashlib.sha256(_canonical_bytes(memories)).hexdigest()


def _deep_freeze(value: object) -> object:
    """Make an immutable recursive snapshot without sharing caller containers."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


def _own_nonnegative_time(name: str, value: object) -> None:
    if value is not None and (
        type(value) not in (int, float) or not math.isfinite(value) or value < 0
    ):
        raise ValueError(f"Invalid nonnegative own timestamp: {name}")


def _physical_signature(name: str, value: object) -> None:
    if value is None:
        return
    if (
        type(value) is not tuple
        or len(value) != 7
        or any(type(item) not in (int, float) or not math.isfinite(item) for item in value)
        or min(value[5:]) <= 0
    ):
        raise ValueError(f"Invalid {name} physical signature")


def _validate_noa_memory(memory: NoaMemory) -> None:
    if type(memory.own_behavior) is not str or memory.own_behavior not in _OWN_BEHAVIORS:
        raise ValueError("Unknown own_behavior in initial NOA memory")
    if (type(memory.lane_change_reason) is not str
            or memory.lane_change_reason not in _LANE_CHANGE_REASONS):
        raise ValueError("Unknown lane_change_reason in initial NOA memory")
    if type(memory.completed_lane_changes) is not int or memory.completed_lane_changes < 0:
        raise ValueError("completed_lane_changes must be a nonnegative exact integer")
    for name in (
        "prepare_since_s", "last_lc_end_s", "r5_deadline_s", "r5_clear_since_s",
        "r5_last_time_s",
    ):
        _own_nonnegative_time(name, getattr(memory, name))
    if memory.target_y_m is not None and (
        type(memory.target_y_m) not in (int, float) or not math.isfinite(memory.target_y_m)
    ):
        raise ValueError("target_y_m must be a finite number")
    if memory.plan is not None and memory.plan.start_s < 0:
        raise ValueError("lane-change plan start_s must be nonnegative")


def _validate_complete_memory(memory: FormationMemory) -> None:
    """Validate fields not covered by the canonical NOA/R5/Phase5G codecs.

    ``formation_memory_from_dict`` is the single canonical round-trip for
    nested observations, plans, R5 state and the six Phase 5G lane fields.
    This post-round-trip layer only supplies the legacy Formation/NOA domains
    that those canonical constructors intentionally do not constrain.
    """
    _validate_noa_memory(memory)
    for name in ("candidate_since_s", "formation_last_time_s"):
        _own_nonnegative_time(name, getattr(memory, name))
    _physical_signature("reference_signature", memory.reference_signature)
    _physical_signature("candidate_signature", memory.candidate_signature)
    if ((memory.candidate_signature is None)
            != (memory.candidate_since_s is None)):
        raise ValueError("formation candidate signature and timestamp must coexist")
    if (type(memory.formation_weight) not in (int, float)
            or not math.isfinite(memory.formation_weight)
            or not 0 <= memory.formation_weight <= 1):
        raise ValueError("formation_weight must be finite and inside [0,1]")
    if (type(memory.cached_increment_mps2) not in (int, float)
            or not math.isfinite(memory.cached_increment_mps2)):
        raise ValueError("cached_increment_mps2 must be finite")
    if (type(memory.formation_state) is not str
            or memory.formation_state not in _FORMATION_STATES):
        raise ValueError("Unknown formation_state in initial FormationMemory")


def neutral_phase5g_memories(raw: Mapping[str, Mapping[str, object]]) -> dict:
    """Return independent full FormationMemory rows with six neutral lane fields."""
    expected = {field.name for field in fields(FormationMemory)}
    if not isinstance(raw, dict):
        raise ValueError("initial memories must be an actor dictionary")
    result = {}
    for key, value in raw.items():
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError(f"{key}: full FormationMemory schema required")
        copied = json.loads(json.dumps(value, allow_nan=False))
        copied.update(_NEUTRAL)
        result[key] = copied
    return result


def restore_initial_memories(raw: object, controlled: tuple[str, ...], *,
                             formation_enabled: bool,
                             lane_priority_enabled: bool,
                             simple_enabled: bool = False) -> dict:
    """Validate exact frozen rows and restore a new immutable object per actor."""
    if not isinstance(raw, dict) or set(raw) != set(controlled):
        raise ValueError("initial memory actor keys must exactly match controlled actors")
    values = [raw[key] for key in controlled]
    if any(not isinstance(value, dict) for value in values):
        raise ValueError("every controlled actor requires one memory dictionary")
    if len({id(value) for value in values}) != len(values):
        raise ValueError("controlled actors must not share initial memory object identity")
    expected = {field.name for field in fields(FormationMemory)}
    base_names = {field.name for field in fields(NoaMemory)}
    simple_names = {field.name for field in fields(SimpleFormationMemory)}
    restored = {}
    for key in controlled:
        value = raw[key]
        if simple_enabled:
            if set(value) not in (base_names, simple_names, expected):
                raise ValueError(
                    f"{key}: exact old or SimpleFormationMemory fields required"
                )
            try:
                copied = json.loads(json.dumps(value, allow_nan=False))
                complete = simple_memory_from_dict(copied)
                _validate_noa_memory(complete)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"{key}: invalid SimpleFormationMemory semantics") from error
            if type(complete) is not SimpleFormationMemory:
                raise ValueError(f"{key}: SimpleFormationMemory subtype restoration failed")
            restored[key] = complete
            continue
        if set(value) != expected:
            raise ValueError(f"{key}: exact full FormationMemory fields required")
        seed = value["formation_lane_rng_state"]
        if seed is not None and (type(seed) is not int or not 0 <= seed < 2**64):
            raise ValueError(f"{key}: Phase 5G private seed must be an exact uint64, not bool")
        if lane_priority_enabled and seed is None:
            raise ValueError(f"{key}: lane_priority mode requires a frozen private seed")
        try:
            copied = json.loads(json.dumps(value, allow_nan=False))
            complete = formation_memory_from_dict(copied)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{key}: invalid full FormationMemory semantics") from error
        if type(complete) is not FormationMemory:
            raise ValueError(f"{key}: FormationMemory subtype restoration failed")
        try:
            _validate_complete_memory(complete)
        except ValueError as error:
            raise ValueError(f"{key}: {error}") from error
        if not formation_enabled:
            if any(value[name] != neutral for name, neutral in _NEUTRAL.items()):
                raise ValueError(f"{key}: off mode requires neutral Phase 5G memory fields")
            complete = noa_memory_from_dict({name: copied[name] for name in base_names})
            if type(complete) is not NoaMemory:
                raise ValueError(f"{key}: off mode must restore NoaMemory")
        restored[key] = complete
    if len({id(value) for value in restored.values()}) != len(restored):
        raise RuntimeError("private memory restoration unexpectedly shared an object")
    return restored


class Phase5GClock(FormationClock):
    """Formation clock with sealed per-instance Phase 5G initial memory."""

    def __init__(self, initial, model, road, parameters, policy_parameters,
                 controlled, scripts, initial_memories, *, clock_schema,
                 initial_memories_sha256):
        if clock_schema != CLOCK_SCHEMA:
            raise ValueError("an explicit phase5g_pure_formation_v1 clock schema is required")
        if initial_memories_sha256 != initial_memory_hash(initial_memories):
            raise ValueError("Phase 5G initial memory hash differs from supplied frozen rows")
        parameters_snapshot = _deep_freeze(parameters)
        policy_snapshot = _deep_freeze(policy_parameters)
        super().__init__(initial, model, road, parameters_snapshot, policy_snapshot,
                         controlled, scripts)
        lane_priority = self.p["formation_lane_change_enabled"]
        simple = self.p["simple_formation_enabled"]
        self.memories = restore_initial_memories(
            initial_memories, self.controlled,
            formation_enabled=self.p["formation_enabled"],
            lane_priority_enabled=lane_priority,
            simple_enabled=simple,
        )
        self.clock_schema = CLOCK_SCHEMA
        self.initial_memories_sha256 = initial_memories_sha256

    def _check_features(self):
        super()._check_features()
        switch_names = (
            "formation_enabled", "communication_enabled", "phase5g_enabled",
            "formation_lane_change_enabled", "simple_formation_enabled", "r5_enabled",
        )
        for name in switch_names:
            if type(self.p.get(name)) is not bool or type(self.policy.get(name)) is not bool:
                raise ValueError(f"{name} must be an explicit boolean in clock and policy")
            if self.p[name] is not self.policy[name]:
                raise ValueError(f"{name} clock and policy switches must agree")
        if self.p["phase5g_enabled"] is not True:
            raise ValueError("Phase5GClock requires phase5g_enabled")
        if self.p["r5_enabled"] is not False:
            raise ValueError("Phase 5G pure formation requires R5 disabled")
        if self.p["formation_lane_change_enabled"] and not self.p["formation_enabled"]:
            raise ValueError("lane_priority mode requires longitudinal formation enabled")
        if self.p["simple_formation_enabled"] and not self.p["formation_enabled"]:
            raise ValueError("simple formation requires longitudinal formation enabled")

    def _decide(self, control):
        if self.policy["simple_formation_enabled"] is True:
            return noa_decide(control, self.policy)
        return super()._decide(control)
