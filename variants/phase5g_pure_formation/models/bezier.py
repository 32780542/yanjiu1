"""Two actual quadratic Bezier segments with a C1 lane-change reference."""
from dataclasses import dataclass,astuple
import math
from models.vehicle import Actuation


@dataclass(frozen=True, slots=True)
class QuadraticLaneChange:
    start_s: float
    y_start_m: float
    y_target_m: float
    duration_s: float
    speed_mps: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in astuple(self)) or self.duration_s <= 0 or self.speed_mps <= 0:
            raise ValueError('Positive duration and speed required')

    def at(self,time_s):
        if not math.isfinite(time_s):
            raise ValueError('Nonfinite reference time')
        t = min(self.duration_s,max(0.,time_s-self.start_s))
        u = t/self.duration_s
        width = self.y_target_m-self.y_start_m
        # P0=(0,y0), P1=(vT/4,y0), P2=(vT/2,(y0+y1)/2)
        # Q0=P2, Q1=(3vT/4,y1), Q2=(vT,y1). Equal half durations.
        if u < .5:
            y,vy,ay = self.y_start_m+2*width*u*u,4*width*u/self.duration_s,4*width/self.duration_s**2
        else:
            y,vy,ay = self.y_target_m-2*width*(1-u)**2,4*width*(1-u)/self.duration_s,-4*width/self.duration_s**2
        if time_s < self.start_s or time_s >= self.start_s+self.duration_s:
            vy,ay = 0.,0.
        return {'x_relative_m':self.speed_mps*t,'y_m':y,'vy_mps':vy,'ay_mps2':ay}


def bezier_command(ego,reference,p):
    target = reference.at(ego.time_s)
    actual_vy = ego.vx_mps*math.sin(ego.heading_rad)
    ay = (target['ay_mps2']+p['tracking_kp_per_s2']*(target['y_m']-ego.y_m)
          +p['tracking_kd_per_s']*(target['vy_mps']-actual_vy))
    delta = math.atan2(p['wheelbase_m']*ay,max(ego.vx_mps**2,1e-12))
    return Actuation(p['speed_tracking_gain_per_s']*(reference.speed_mps-ego.vx_mps),delta)
