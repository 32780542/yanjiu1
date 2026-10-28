"""Own finite-duration maneuver state, without changing phase 3 records."""
from dataclasses import dataclass

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
    return NoaMemory(tuple(observations), plan=QuadraticLaneChange(**plan) if plan else None, **value)
