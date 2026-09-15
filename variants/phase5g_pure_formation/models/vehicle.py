"""Small-slip dynamic bicycle with explicit actuators and low-speed blending.

CG world pose is authoritative. a_drive is actuator-equivalent acceleration;
a_long in diagnostics is the constrained derivative of vx. No traffic policy.
Low-speed relaxation and linear tires share one axle-force friction projection.
"""
from dataclasses import dataclass, astuple, replace
import math
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class VehicleState:
    time_s: float=0.
    x_m: float=0.
    y_m: float=0.
    heading_rad: float=0.
    vx_mps: float=0.
    vy_mps: float=0.
    yaw_rate_radps: float=0.
    a_drive_mps2: float=0.
    steering_rad: float=0.


@dataclass(frozen=True, slots=True)
class Actuation:
    acceleration_mps2: float
    steering_rad: float


@dataclass(frozen=True, slots=True)
class IntegratedStep:
    initial: VehicleState
    final: VehicleState
    command: Actuation
    samples: tuple[VehicleState,...]
    dt_s: float


def clip(x, lo, hi):
    return min(hi,max(lo,x))


class VehicleModel:
    def __init__(self, parameters):
        self.p=MappingProxyType(dict(parameters))
        for k in ('mass_kg','yaw_inertia_kgm2','wheelbase_m','cg_to_front_axle_m','cg_to_rear_axle_m',
                  'front_cornering_stiffness_N_per_rad','rear_cornering_stiffness_N_per_rad',
                  'acceleration_lag_s','steering_lag_s','low_speed_relaxation_s','road_friction_coefficient'):
            if not math.isfinite(self.p[k]) or self.p[k]<=0:
                raise ValueError(f'Invalid physical parameter {k}')
        if not math.isclose(self.p['cg_to_front_axle_m']+self.p['cg_to_rear_axle_m'],self.p['wheelbase_m']):
            raise ValueError('Inconsistent wheelbase/CG geometry')

    @classmethod
    def from_config(cls):
        from research.common import settings
        return cls({**settings('no_comm_main'),**settings('paper_reference'),**settings('phase2')})

    def observe(self,s):
        p=self.p
        vx=max(0.,s.vx_mps)
        m,iz,lf,lr=p['mass_kg'],p['yaw_inertia_kgm2'],p['cg_to_front_axle_m'],p['cg_to_rear_axle_m']
        mu_g=p['road_friction_coefficient']*p['gravity_mps2']
        ax=clip(s.a_drive_mps2,max(p['min_accel_mps2'],-mu_g),min(p['max_accel_mps2'],mu_g))
        if vx<=0 and ax<0 or vx>=p['max_speed_mps'] and ax>0:
            ax=0.
        zf=m*p['gravity_mps2']*lr/(lf+lr)
        zr=m*p['gravity_mps2']*lf/(lf+lr)
        fx_f=m*ax*lr/(lf+lr)
        fx_r=m*ax*lf/(lf+lr)
        cf=math.sqrt(max(0,(p['road_friction_coefficient']*zf)**2-fx_f**2))
        cr=math.sqrt(max(0,(p['road_friction_coefficient']*zr)**2-fx_r**2))
        denominator=max(vx,p['low_speed_blend_start_mps'])
        af=s.steering_rad-(s.vy_mps+lf*s.yaw_rate_radps)/denominator
        ar=-(s.vy_mps-lr*s.yaw_rate_radps)/denominator
        rawf=p['front_cornering_stiffness_N_per_rad']*af
        rawr=p['rear_cornering_stiffness_N_per_rad']*ar
        ratio=clip((vx-p['low_speed_blend_start_mps'])/(p['low_speed_blend_end_mps']-p['low_speed_blend_start_mps']),0,1)
        weight=ratio*ratio*(3-2*ratio)
        rk=vx*math.tan(s.steering_rad)/(lf+lr)
        vyk=lr*rk
        dv_requested=weight*((rawf+rawr)/m-vx*s.yaw_rate_radps)+(1-weight)*(vyk-s.vy_mps)/p['low_speed_relaxation_s']
        dr_requested=weight*(lf*rawf-lr*rawr)/iz+(1-weight)*(rk-s.yaw_rate_radps)/p['low_speed_relaxation_s']
        ay_requested=dv_requested+vx*s.yaw_rate_radps
        # Convert both branches to required axle forces before limiting them.
        # No kinematic relaxation acceleration may bypass the friction budget.
        requested_f=(m*ay_requested*lr+iz*dr_requested)/(lf+lr)
        requested_r=(m*ay_requested*lf-iz*dr_requested)/(lf+lr)
        fyf,fyr=clip(requested_f,-cf,cf),clip(requested_r,-cr,cr)
        ay=(fyf+fyr)/m
        dv=ay-vx*s.yaw_rate_radps
        dr=(lf*fyf-lr*fyr)/iz
        lateral_available=min(p['steering_lateral_envelope_mps2'],math.sqrt(max(0,mu_g**2-ax**2)))
        steering_bound=min(p['max_steering_rad'],math.atan2((lf+lr)*lateral_available,max(vx**2,1e-12)))
        return {'a_long_mps2':ax,'vy_dot_mps2':dv,'yaw_accel_radps2':dr,'a_lateral_mps2':ay,
                'speed_mps':math.hypot(vx,s.vy_mps),'dynamic_weight':weight,'steering_target_bound_rad':steering_bound,
                'slip_front_rad':af,'slip_rear_rad':ar,'fx_front_N':fx_f,'fx_rear_N':fx_r,
                'fy_front_N':fyf,'fy_rear_N':fyr,'fz_front_N':zf,'fz_rear_N':zr,
                'fy_front_requested_N':requested_f,'fy_rear_requested_N':requested_r,
                'tire_saturated':abs(requested_f)>cf+1e-7 or abs(requested_r)>cr+1e-7,
                'outside_linear_tire_regime':weight>0 and max(abs(af),abs(ar))>p['linear_tire_slip_limit_rad']}

    def _derivative(self,s,command):
        p=self.p
        d=self.observe(s)
        mu_g=p['road_friction_coefficient']*p['gravity_mps2']
        a_target=clip(command.acceleration_mps2,max(p['min_accel_mps2'],-mu_g),min(p['max_accel_mps2'],mu_g))
        delta_target=clip(command.steering_rad,-d['steering_target_bound_rad'],d['steering_target_bound_rad'])
        da=clip((a_target-s.a_drive_mps2)/p['acceleration_lag_s'],-p['actuator_jerk_limit_mps3'],p['actuator_jerk_limit_mps3'])
        dd=clip((delta_target-s.steering_rad)/p['steering_lag_s'],-p['max_steering_rate_radps'],p['max_steering_rate_radps'])
        vx=max(0.,s.vx_mps)
        return (1.,vx*math.cos(s.heading_rad)-s.vy_mps*math.sin(s.heading_rad),
                vx*math.sin(s.heading_rad)+s.vy_mps*math.cos(s.heading_rad),s.yaw_rate_radps,
                d['a_long_mps2'],d['vy_dot_mps2'],d['yaw_accel_radps2'],da,dd)

    def advance(self,initial,command,duration_s,dt_s):
        if not all(math.isfinite(v) for v in astuple(initial)+astuple(command)+(duration_s,dt_s)):
            raise ValueError('Nonfinite state, actuation or step')
        if dt_s<=0 or duration_s<=0 or dt_s>self.p['max_dynamics_dt_s']:
            raise ValueError('Invalid dynamics integration step')
        n=round(duration_s/dt_s)
        if n<1 or not math.isclose(n*dt_s,duration_s,abs_tol=1e-10,rel_tol=0):
            raise ValueError('Interval must contain an integer number of integration steps')
        if initial.vx_mps<0 or initial.vx_mps>self.p['max_speed_mps'] or abs(initial.steering_rad)>self.p['max_steering_rad']:
            raise ValueError('Initial state outside supported speed/steering range')
        s=initial
        samples=[]
        for i in range(n):
            values=astuple(s)
            k1=self._derivative(s,command)
            k2=self._derivative(VehicleState(*(a+dt_s*b/2 for a,b in zip(values,k1))),command)
            k3=self._derivative(VehicleState(*(a+dt_s*b/2 for a,b in zip(values,k2))),command)
            k4=self._derivative(VehicleState(*(a+dt_s*b for a,b in zip(values,k3))),command)
            result=[v+dt_s*(a+2*b+2*c+d)/6 for v,a,b,c,d in zip(values,k1,k2,k3,k4)]
            result[0]=initial.time_s+(i+1)*dt_s
            result[4]=clip(result[4],0,self.p['max_speed_mps'])
            result[8]=clip(result[8],-self.p['max_steering_rad'],self.p['max_steering_rad'])
            s=VehicleState(*result)
            samples.append(s)
        return IntegratedStep(initial,s,command,tuple(samples),dt_s)
