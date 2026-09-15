"""Own finite-duration maneuver state, without changing phase 3 records."""
from dataclasses import dataclass
import math

from models.bezier import QuadraticLaneChange
from models.vehicle import Actuation
from perception.contracts import LocalMemory, LocalObservation, NeighborDetection, RoadObservation


@dataclass(frozen=True, slots=True)
class NoaMemory(LocalMemory):
    plan: QuadraticLaneChange | None = None
    target_y_m: float | None = None
    prepare_since_s: float | None = None
    lane_change_reason: str = ''
    last_lc_end_s: float | None = None
    completed_lane_changes: int = 0
    r5_rng_state: int | None = None
    r5_draw_count: int = 0
    r5_phase: str = 'IDLE'
    r5_deadline_s: float | None = None
    r5_episode_signature: tuple | None = None
    r5_clear_since_s: float | None = None
    r5_last_time_s: float | None = None


@dataclass(frozen=True, slots=True)
class NoaDecision:
    action: Actuation
    memory: NoaMemory
    diagnostics: dict


def memory_from_dict(data):
    """Restore exactly the JSON/asdict schema recorded by the stage 4 clock."""
    value = dict(data)
    observations = []
    for item in value.pop('observation_history'):
        road = dict(item['road'])
        for key in ('boundary_polylines_m', 'marking_polylines_m'):
            road[key] = tuple(tuple(tuple(p) for p in line) for line in road[key])
        observations.append(LocalObservation(item['time_s'], tuple(
            NeighborDetection(**neighbor) for neighbor in item['neighbors']), RoadObservation(**road)))
    plan = value.pop('plan', None)
    if value.get('r5_episode_signature') is not None:
        value['r5_episode_signature'] = _tuples(value['r5_episode_signature'])
    result = NoaMemory(tuple(observations), plan=QuadraticLaneChange(**plan) if plan else None, **value)
    validate_r5_memory(result)
    return result


def _tuples(value):
    return tuple(_tuples(v) for v in value) if isinstance(value,(tuple,list)) else value


def validate_r5_memory(memory):
    if memory.r5_rng_state is not None and (type(memory.r5_rng_state) is not int or not 0 <= memory.r5_rng_state < 2**64):
        raise ValueError('Invalid private R5 uint64 state')
    if type(memory.r5_draw_count) is not int or memory.r5_draw_count < 0:
        raise ValueError('Invalid private R5 draw count')
    if memory.r5_phase not in ('IDLE','YIELD','BACKOFF','ELIGIBLE','UNKNOWN'):
        raise ValueError('Invalid R5 phase')
    for value in (memory.r5_deadline_s,memory.r5_clear_since_s,memory.r5_last_time_s):
        if value is not None and (type(value) not in (float,int) or not math.isfinite(value)):
            raise ValueError('Invalid R5 own timestamp')
    episode=memory.r5_episode_signature
    if episode is not None:
        if not isinstance(episode,tuple) or len(episode)!=4 or not isinstance(episode[3],tuple):
            raise ValueError('Invalid R5 physical episode schema')
        if type(episode[0]) not in (float,int) or not math.isfinite(episode[0]):
            raise ValueError('Invalid R5 target geometry')
        for signature in tuple(s for s in episode[1:3] if s is not None)+episode[3]:
            if (not isinstance(signature,tuple) or len(signature)!=7 or
                any(type(v) not in (float,int) or not math.isfinite(v) for v in signature) or min(signature[5:])<=0):
                raise ValueError('Invalid R5 permitted physical signature')
    if memory.r5_phase=='IDLE' and (episode is not None or memory.r5_deadline_s is not None):
        raise ValueError('Idle R5 has an active episode')
    if memory.r5_phase!='IDLE' and episode is None:
        raise ValueError('Active R5 phase requires its physical episode')
    if memory.r5_phase in ('BACKOFF','ELIGIBLE') and memory.r5_deadline_s is None:
        raise ValueError('Timed R5 phase requires a deadline')
    if memory.r5_phase!='IDLE' and memory.r5_last_time_s is None:
        raise ValueError('Active R5 episode requires its stored observation time')
    if memory.r5_phase=='BACKOFF' and memory.r5_deadline_s<=memory.r5_last_time_s+1e-9:
        raise ValueError('Stored BACKOFF was already expired at its own timestamp')
    if memory.r5_phase=='ELIGIBLE' and memory.r5_deadline_s>memory.r5_last_time_s+1e-9:
        raise ValueError('Stored ELIGIBLE had not expired at its own timestamp')
    if memory.r5_clear_since_s is not None and (episode is None or memory.r5_last_time_s is None or
                                              memory.r5_clear_since_s>memory.r5_last_time_s+1e-9):
        raise ValueError('Invalid R5 clearing interval at stored observation time')
