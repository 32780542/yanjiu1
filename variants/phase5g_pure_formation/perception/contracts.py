"""Controller-facing immutable records in ego-centred physical coordinates.

No simulator IDs, NOA/HDV labels, global lanes/slots, other plans, or shared
leader state. Track IDs are local sensor labels and cannot set priority.
Truth-to-observation conversion is isolated in ideal.py; probe.py has no truth access.
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EgoState:
    time_s: float
    x_m: float
    y_m: float
    heading_rad: float
    vx_mps: float
    vy_mps: float
    yaw_rate_radps: float
    acceleration_mps2: float
    steering_rad: float


@dataclass(frozen=True, slots=True)
class NeighborDetection:
    track_id: int
    relative_x_m: float
    relative_y_m: float
    relative_vx_mps: float
    relative_vy_mps: float
    relative_heading_rad: float
    length_m: float
    width_m: float
    measurement_time_s: float


@dataclass(frozen=True, slots=True)
class RoadObservation:
    measurement_time_s: float
    # Only actually observed portions in ego frame, never complete map edges.
    boundary_polylines_m: tuple[tuple[tuple[float, float], ...], ...]
    marking_polylines_m: tuple[tuple[tuple[float, float], ...], ...]


@dataclass(frozen=True, slots=True)
class LocalObservation:
    time_s: float
    neighbors: tuple[NeighborDetection, ...]
    road: RoadObservation


@dataclass(frozen=True, slots=True)
class LocalMemory:
    observation_history: tuple[LocalObservation, ...]
    own_behavior: str


@dataclass(frozen=True, slots=True)
class ControlInput:
    ego: EgoState
    observation: LocalObservation
    memory: LocalMemory
