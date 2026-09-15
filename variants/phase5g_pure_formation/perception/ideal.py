"""Trusted sensor adapter; truth keys/hidden experiment metadata stop here.

Range selection uses CG reference points. Velocities are relative world
velocity vectors expressed along ego heading, not rotating-frame derivatives.
Each instance belongs to one ego. Only visible keys are retained for identity
association; neither global ordering nor key spelling allocates local tracks.
"""
from dataclasses import dataclass, astuple
import math
from types import MappingProxyType
from models.vehicle import VehicleState
from perception.contracts import (EgoState, NeighborDetection, LocalObservation,
                                  LocalMemory, ControlInput)
from perception.road import ego_point, in_box


@dataclass(frozen=True, slots=True)
class TruthVehicle:
    key: str
    state: VehicleState
    length_m: float
    width_m: float
    acceleration_mps2: float = 0.
    hidden_type: str = ''
    future_plan: tuple = ()


@dataclass(frozen=True, slots=True)
class WorldFrame:
    vehicles: tuple[TruthVehicle, ...]

    def __post_init__(self):
        if not self.vehicles or len({v.key for v in self.vehicles}) != len(self.vehicles):
            raise ValueError('Empty frame or duplicate simulator key')
        time = self.vehicles[0].state.time_s
        for v in self.vehicles:
            if v.state.time_s != time:
                raise ValueError('Mixed physical times in frozen frame')
            if not all(math.isfinite(x) for x in astuple(v.state)+(v.length_m, v.width_m, v.acceleration_mps2)):
                raise ValueError('Nonfinite physical truth')
            if min(v.length_m, v.width_m) <= 0:
                raise ValueError('Invalid body dimensions')


def world_velocity(s):
    c, sn = math.cos(s.heading_rad), math.sin(s.heading_rad)
    return (s.vx_mps*c-s.vy_mps*sn, s.vx_mps*sn+s.vy_mps*c)


class IdealSensor:
    def __init__(self, parameters, road):
        self.p, self.road = MappingProxyType(dict(parameters)), road
        for key in ('rear_range_m', 'front_range_m', 'side_range_m', 'perception_dt_s', 'memory_horizon_s', 'sensor_roundoff_ulps'):
            if not math.isfinite(self.p[key]) or self.p[key] <= 0:
                raise ValueError(f'Invalid sensor parameter: {key}')
        if (self.p['perception_mode'] != 'ideal_range_limited' or self.p['sensor_delay_s'] != 0
                or any(self.p[k] for k in ('static_map_enabled', 'occlusion_enabled', 'communication_enabled'))):
            raise ValueError('This adapter only supports the approved finite ideal observation mode')
        self._tracks, self._history = {}, ()
        self._next_track, self._last_time = 1, None

    def sample(self, ego_key, frame):
        own = next((v for v in frame.vehicles if v.key == ego_key), None)
        if own is None:
            raise ValueError('Ego absent from frame')
        s = own.state
        if self._last_time is not None and not math.isclose(
                s.time_s-self._last_time, self.p['perception_dt_s'], abs_tol=1e-9, rel_tol=0):
            raise ValueError('Sensor must sample once per declared update interval')
        c, sn = math.cos(s.heading_rad), math.sin(s.heading_rad)
        evx, evy = world_velocity(s)
        visible = []
        for v in frame.vehicles:
            if v.key == ego_key:
                continue
            x, y = ego_point(v.state.x_m, v.state.y_m, s)
            if not in_box((x,y),self.p):
                continue
            vx, vy = world_velocity(v.state)
            heading = math.atan2(math.sin(v.state.heading_rad-s.heading_rad), math.cos(v.state.heading_rad-s.heading_rad))
            fields = (x, y, c*(vx-evx)+sn*(vy-evy), -sn*(vx-evx)+c*(vy-evy),
                      heading, v.length_m, v.width_m, s.time_s)
            visible.append((fields, v.key))
        # Sort by allowed measured values only. For exactly indistinguishable
        # duplicates, forget association for that group. This avoids claiming
        # persistent identity that the allowed measurements cannot distinguish.
        counts = {}
        for signature, key in visible:
            counts[signature] = counts.get(signature, 0)+1
        active, detections = {}, []
        for signature, key in sorted(visible, key=lambda item: item[0]):
            token = self._tracks.get(key) if counts[signature] == 1 else None
            if token is None:
                token, self._next_track = self._next_track, self._next_track+1
            if counts[signature] == 1:
                active[key] = token
            detections.append(NeighborDetection(token, *signature))
        self._tracks = active  # exits leave no current truth association
        observation = LocalObservation(s.time_s, tuple(sorted(detections, key=lambda n: astuple(n)[1:]+(n.track_id,))),
                                       self.road.observe(s, self.p))
        history = tuple(o for o in self._history if s.time_s-o.time_s <= self.p['memory_horizon_s']+1e-9)
        ego = EgoState(s.time_s, s.x_m, s.y_m, s.heading_rad, s.vx_mps, s.vy_mps,
                       s.yaw_rate_radps, own.acceleration_mps2, s.steering_rad)
        result = ControlInput(ego, observation, LocalMemory(history, 'PROBE'))
        self._history, self._last_time = history+(observation,), s.time_s
        return result
