"""Conditional finite-horizon candidate verification from local measurements.

Neighbor longitudinal reachability spans inherited hard acceleration limits,
with nonnegative speed and inherited maximum speed. Lateral velocity remains
the measured inertial value plus the explicitly configured acceleration bound.
No neighbor is assumed to yield. Own prediction holds this tick's acceleration
request and follows its own reference with the actual actuator/model limits.
All checks are conditional on these stated motion assumptions.
"""
from dataclasses import dataclass
import math

from models.geometry import BodyPose, body_from_state
from models.kinematic import KinematicModel
from models.bezier import QuadraticLaneChange
from models.vehicle import Actuation, VehicleState, clip
from safety.geometry import swept_collision, swept_outside


@dataclass(frozen=True, slots=True)
class MeasuredBody:
    x: float
    y: float
    vx: float
    vy: float
    heading: float
    length: float
    width: float


def measured_bodies(control):
    e = control.ego
    c, s = math.cos(e.heading_rad), math.sin(e.heading_rad)
    evx, evy = e.vx_mps*c-e.vy_mps*s, e.vx_mps*s+e.vy_mps*c
    bodies = []
    for n in control.observation.neighbors:
        bodies.append(MeasuredBody(e.x_m+c*n.relative_x_m-s*n.relative_y_m,
                                   e.y_m+s*n.relative_x_m+c*n.relative_y_m,
                                   evx+c*n.relative_vx_mps-s*n.relative_vy_mps,
                                   evy+s*n.relative_vx_mps+c*n.relative_vy_mps,
                                   e.heading_rad+n.relative_heading_rad, n.length_m, n.width_m))
    # The complete permitted physical signature, never an ID, sets arithmetic order.
    return tuple(sorted(bodies, key=lambda b: (b.x, b.y, b.vx, b.vy, b.heading, b.length, b.width)))


def actuator_acceleration_upper(ego, parameters):
    """At speed saturation, zero actual acceleration hides a positive drive.

    For initial actuators inside inherited hard bounds (the approved model
    domain), max_accel is the conservative upper bound of this own state.
    """
    if ego.vx_mps == parameters['max_speed_mps'] and ego.acceleration_mps2 == 0.:
        return parameters['max_accel_mps2']
    return ego.acceleration_mps2


def reference_target(plan, time_s):
    """Right-continuous C1 acceleration events despite clock roundoff.

    This only canonicalizes 1e-9s equality at the existing three events;
    it does not delay a reference, change its curve, or alter stage3 replay.
    """
    elapsed = time_s-plan.start_s
    for event in (0., plan.duration_s/2, plan.duration_s):
        if math.isclose(elapsed, event, abs_tol=1e-9, rel_tol=0.):
            elapsed = event
    return QuadraticLaneChange(0., plan.y_start_m, plan.y_target_m, plan.duration_s, plan.speed_mps).at(elapsed)


def lateral_command(ego, target, parameters):
    p = parameters
    actual_vy = ego.vx_mps*math.sin(ego.heading_rad)+ego.vy_mps*math.cos(ego.heading_rad)
    ay = target['ay_mps2']+p['noa_lateral_kp_per_s2']*(target['y_m']-ego.y_m)
    ay += p['noa_lateral_kd_per_s']*(target['vy_mps']-actual_vy)
    # y_ddot = a_long*sin(heading) + a_normal*cos(heading).
    # The predictor has a VehicleState; the policy has the observed EgoState.
    along = ego.acceleration_mps2 if hasattr(ego, 'acceleration_mps2') else KinematicModel(p).observe(ego)['a_long_mps2']
    cosine = math.cos(ego.heading_rad)
    if cosine <= 0:
        raise ValueError('Forward straight-road heading required')
    ay = (ay-along*math.sin(ego.heading_rad))/cosine
    ay = clip(ay, -p['comfort_lateral_accel_mps2'], p['comfort_lateral_accel_mps2'])
    return clip(math.atan2(p['wheelbase_m']*ay, max(ego.vx_mps**2, 1e-12)),
                -p['max_steering_rad'], p['max_steering_rad'])


def distance_at(speed, acceleration, duration, maximum_speed):
    """Exact 1D constant acceleration displacement with clipped speed."""
    v = clip(speed, 0., maximum_speed)
    if acceleration == 0:
        return v*duration
    limit = maximum_speed if acceleration > 0 else 0.
    until_limit = max(0., (limit-v)/acceleration)
    t = min(duration, until_limit)
    return v*t+acceleration*t*t/2+limit*(duration-t)


def reachable_body(body, duration, parameters):
    p = parameters
    lower = body.x+distance_at(body.vx, p['min_accel_mps2'], duration, p['max_speed_mps'])
    upper = body.x+distance_at(body.vx, p['max_accel_mps2'], duration, p['max_speed_mps'])
    c, s = abs(math.cos(body.heading)), abs(math.sin(body.heading))
    margin = p['noa_body_margin_m']
    lateral_growth = p['noa_prediction_lateral_accel_bound_mps2']*duration**2
    return BodyPose((lower+upper)/2, body.y+body.vy*duration, 0.,
                    c*body.length+s*body.width+upper-lower+2*margin,
                    s*body.length+c*body.width+2*margin+lateral_growth)


def verify_candidate(control, plan, road, acceleration, parameters):
    """Check every swept interval; unresolved sweep leaves reject candidates."""
    p, e = parameters, control.ego
    if actuator_acceleration_upper(e, p) != e.acceleration_mps2:
        return {'safe':False, 'reason':'own_actuator_unobservable_at_speed_cap', 'at_s':0., 'checked_s':0.}
    if e.vx_mps == 0. and e.acceleration_mps2 == 0.:
        return {'safe':False, 'reason':'own_actuator_unobservable_at_stop', 'at_s':0., 'checked_s':0.}
    bodies = measured_bodies(control)
    state = VehicleState(e.time_s, e.x_m, e.y_m, e.heading_rad, e.vx_mps, 0.,
                         e.vx_mps*math.tan(e.steering_rad)/p['wheelbase_m'],
                         e.acceleration_mps2, e.steering_rad)
    remaining = max(0., plan.start_s+plan.duration_s-e.time_s)+p['noa_prediction_settle_s']
    count = max(1, math.ceil(remaining/p['noa_prediction_dt_s']))
    interval = remaining/count
    inner_count = max(1, math.ceil(interval/p['max_dynamics_dt_s']))
    dt = interval/inner_count
    model = KinematicModel(p)
    elapsed = 0.
    for index in range(count):
        target = reference_target(plan, state.time_s)
        command = Actuation(acceleration, lateral_command(state, target, p))
        step = model.advance(state, command, interval, dt)
        # Each physical integration segment gets a swept-body check, not only
        # the reference endpoint or the nominal centerline.
        previous = state
        for sample_index, sample in enumerate(step.samples):
            t0, t1 = elapsed+sample_index*dt, elapsed+(sample_index+1)*dt
            ego0, ego1 = body_from_state(previous, p), body_from_state(sample, p)
            margin = p['noa_body_margin_m']
            ego0 = BodyPose(ego0.x, ego0.y, ego0.heading, ego0.length+2*margin, ego0.width+2*margin)
            ego1 = BodyPose(ego1.x, ego1.y, ego1.heading, ego1.length+2*margin, ego1.width+2*margin)
            if swept_outside(road.envelope, ego0, ego1, p['sweep_max_depth']):
                return {'safe':False, 'reason':'predicted_body_outside_observed_road', 'at_s':t1, 'checked_s':t1}
            for body in bodies:
                a, b = reachable_body(body, t0, p), reachable_body(body, t1, p)
                # Both endpoints use the union size, so linear interpolation
                # encloses growth between samples. The 1D extreme is quadratic;
                # additional sag bound encloses acceleration between endpoints.
                sag = max(abs(p['min_accel_mps2']), abs(p['max_accel_mps2']))*dt*dt/8
                length, width = max(a.length, b.length)+2*sag, max(a.width, b.width)
                a = BodyPose(a.x, a.y, 0., length, width)
                b = BodyPose(b.x, b.y, 0., length, width)
                if swept_collision(ego0, ego1, a, b, p['sweep_max_depth']):
                    return {'safe':False, 'reason':'neighbor_reachable_occupancy', 'at_s':t1, 'checked_s':t1}
            previous = sample
        state, elapsed = step.final, (index+1)*interval
    return {'safe':True, 'reason':'conditional_swept_prediction_clear', 'at_s':None, 'checked_s':remaining}
