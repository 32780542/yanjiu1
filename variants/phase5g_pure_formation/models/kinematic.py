"""Geometric-center equivalent bicycle, no tire forces, mass or inertia.

The heading is the center path tangent; lateral slip is ignored. Steering is
an equivalent curvature command using the declared wheelbase. This is a
trajectory simulation approximation, not a calibrated physical vehicle model.
"""
from dataclasses import astuple, replace
import math
from types import MappingProxyType
from models.vehicle import VehicleState, Actuation, IntegratedStep, clip


def kinematic_state(p, **kwargs):
    s = VehicleState(**kwargs)
    return replace(s,vy_mps=0.,yaw_rate_radps=s.vx_mps*math.tan(s.steering_rad)/p['wheelbase_m'])


class KinematicModel:
    def __init__(self,parameters):
        self.p = MappingProxyType(dict(parameters))
        for key in ('length_m','width_m','wheelbase_m','acceleration_lag_s','steering_lag_s',
                    'max_steering_rate_radps','actuator_jerk_limit_mps3'):
            if not math.isfinite(self.p[key]) or self.p[key] <= 0:
                raise ValueError(f'Invalid kinematic parameter {key}')

    @classmethod
    def from_config(cls):
        from research.common import settings
        main,paper,old = settings('no_comm_main'),settings('paper_reference'),settings('phase2')
        # Retain the approved sensing/runtime settings and simple geometric
        # limits. Explicitly exclude all former tire-force/dynamic parameters.
        excluded = ('mass','inertia','stiffness','friction','low_speed','cornering','gravity',
                    'cg_to_','overhang','emission','legacy_vsp','energy')
        p = {k:v for k,v in main.items() if not any(word in k for word in excluded)}
        keep = ('actuator_jerk_limit_mps3','steering_lateral_envelope_mps2','max_dynamics_dt_s',
                'tracking_kp_per_s2','tracking_kd_per_s','speed_tracking_gain_per_s','maneuver_duration_s',
                'max_lane_change_error_m','terminal_lane_error_m','integration_position_tolerance_m',
                'integration_heading_tolerance_rad','control_position_tolerance_m','control_heading_tolerance_rad',
                'replay_absolute_tolerance','sweep_max_depth','sumo_speed_mode','sumo_lane_change_mode','sumo_move_keep_route')
        p.update({k:v for k,v in old.items() if k in keep or k.startswith('sync_')})
        p['max_speed_mps'] = paper['max_speed_mps']
        p.update(settings('kinematic'))
        return cls(p)

    def observe(self,s):
        ax = clip(s.a_drive_mps2,self.p['min_accel_mps2'],self.p['max_accel_mps2'])
        if (s.vx_mps <= 0 and ax < 0) or (s.vx_mps >= self.p['max_speed_mps'] and ax > 0):
            ax = 0.
        rate = s.vx_mps*math.tan(s.steering_rad)/self.p['wheelbase_m']
        return {'speed_mps':s.vx_mps,'a_long_mps2':ax,'a_lateral_mps2':s.vx_mps*rate,
                'curvature_per_m':math.tan(s.steering_rad)/self.p['wheelbase_m'],
                'kinematic_yaw_rate_radps':rate,
                'outside_kinematic_lateral_envelope':abs(s.vx_mps*rate)>self.p['steering_lateral_envelope_mps2']+1e-8}

    def _derivative(self,s,command):
        # RK internal stages can cross a speed boundary before the saved
        # endpoint is projected. Their pose derivatives must obey it too.
        s = replace(s,vx_mps=clip(s.vx_mps,0,self.p['max_speed_mps']))
        p,d = self.p,self.observe(s)
        bound = min(p['max_steering_rad'],math.atan2(p['wheelbase_m']*p['steering_lateral_envelope_mps2'],max(s.vx_mps**2,1e-12)))
        a = clip(command.acceleration_mps2,p['min_accel_mps2'],p['max_accel_mps2'])
        delta = clip(command.steering_rad,-bound,bound)
        da = clip((a-s.a_drive_mps2)/p['acceleration_lag_s'],-p['actuator_jerk_limit_mps3'],p['actuator_jerk_limit_mps3'])
        dd = clip((delta-s.steering_rad)/p['steering_lag_s'],-p['max_steering_rate_radps'],p['max_steering_rate_radps'])
        return (1.,s.vx_mps*math.cos(s.heading_rad),s.vx_mps*math.sin(s.heading_rad),
                d['kinematic_yaw_rate_radps'],d['a_long_mps2'],0.,0.,da,dd)

    def advance(self,initial,command,duration_s,dt_s):
        if not all(math.isfinite(x) for x in astuple(initial)+astuple(command)+(duration_s,dt_s)):
            raise ValueError('Nonfinite state, command or interval')
        if dt_s <= 0 or duration_s <= 0 or dt_s > self.p['max_dynamics_dt_s']:
            raise ValueError('Invalid integration step')
        count = round(duration_s/dt_s)
        if count < 1 or not math.isclose(count*dt_s,duration_s,abs_tol=1e-10,rel_tol=0):
            raise ValueError('Interval must contain complete substeps')
        if (initial.vx_mps < 0 or initial.vx_mps > self.p['max_speed_mps'] or abs(initial.steering_rad)>self.p['max_steering_rad']
            or initial.vy_mps != 0 or abs(initial.yaw_rate_radps-self.observe(initial)['kinematic_yaw_rate_radps'])>1e-9):
            raise ValueError('Initial state incompatible with the simplified kinematic model')
        state,samples = initial,[]
        for i in range(count):
            values = astuple(state)
            k1 = self._derivative(state,command)
            k2 = self._derivative(VehicleState(*(a+dt_s*b/2 for a,b in zip(values,k1))),command)
            k3 = self._derivative(VehicleState(*(a+dt_s*b/2 for a,b in zip(values,k2))),command)
            k4 = self._derivative(VehicleState(*(a+dt_s*b for a,b in zip(values,k3))),command)
            result = [v+dt_s*(a+2*b+2*c+d)/6 for v,a,b,c,d in zip(values,k1,k2,k3,k4)]
            result[0] = initial.time_s+(i+1)*dt_s
            result[4] = clip(result[4],0,self.p['max_speed_mps'])
            result[8] = clip(result[8],-self.p['max_steering_rad'],self.p['max_steering_rad'])
            state = VehicleState(*result)
            state = replace(state,vy_mps=0.,yaw_rate_radps=self.observe(state)['kinematic_yaw_rate_radps'])
            samples.append(state)
        return IntegratedStep(initial,state,command,tuple(samples),dt_s)


def model_from_parameters(parameters):
    if parameters.get('motion_model') == 'kinematic_bicycle':
        return KinematicModel(parameters)
    if 'motion_model' in parameters:
        raise ValueError(f'Unknown explicit motion model: {parameters["motion_model"]}')
    from models.vehicle import VehicleModel
    return VehicleModel(parameters)  # Explicit compatibility for frozen legacy evidence.
