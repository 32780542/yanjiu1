"""Time-based single-vehicle references, independent of road/traffic knowledge.

These commands are a model-validation bench, not a NOA controller. The road
coordinates in initial conditions select physical test locations only. Neither
reference evaluation nor command generation consumes global longitudinal x.
"""
from dataclasses import asdict
import math

from models.vehicle import Actuation, VehicleState
from research.common import settings


def cases():
    """Return fresh, JSON-serializable records with complete replay initial states."""
    vehicle = settings('no_comm_main')
    phase2 = settings('phase2')
    speed = settings('paper_reference')['desired_speed_mps']

    def case(name, x, y, vx, duration, reference):
        return {'name': name, 'initial': asdict(VehicleState(x_m=x, y_m=y, vx_mps=vx)),
                'duration_s': duration, 'reference': reference,
                'scope': 'prescribed_single_vehicle_validation_not_NOA'}

    return [
        case('constant_speed', 100., 1.65, speed, 10.,
             {'kind': 'constant_actuation', 'acceleration_mps2': 0., 'steering_rad': 0.}),
        case('acceleration_stop_restart', 100., 1.65, 5., 14.,
             {'kind': 'time_schedule', 'steering_rad': 0., 'segments': [
                 {'start_s': 0., 'end_s': 2., 'acceleration_mps2': 2.},
                 {'start_s': 2., 'end_s': 7., 'acceleration_mps2': -3.},
                 {'start_s': 7., 'end_s': 9., 'acceleration_mps2': 0.},
                 {'start_s': 9., 'end_s': 14., 'acceleration_mps2': 2.}],
              'stop_hold_start_s': 7., 'restart_s': 9.}),
        case('constant_steering', 100., 1.65, 10., 3.,
             {'kind': 'constant_actuation', 'acceleration_mps2': 0., 'steering_rad': .01}),
        case('lane_change', 100., 1.65, speed, 10.,
             {'kind': 'quintic_lane_change', 'start_s': 0.,
              'maneuver_duration_s': phase2['maneuver_duration_s'],
              'y_start_m': 1.65, 'y_target_m': 4.95, 'speed_mps': speed,
              'wheelbase_m': vehicle['wheelbase_m'],
              'tracking_law': 'linear_bicycle_low_frequency_lead_plus_world_lateral_PD',
              'model_reference': {key: vehicle[key] for key in (
                  'mass_kg', 'yaw_inertia_kgm2', 'cg_to_front_axle_m', 'cg_to_rear_axle_m',
                  'front_cornering_stiffness_N_per_rad', 'rear_cornering_stiffness_N_per_rad',
                  'steering_lag_s')},
              'gain_source': 'configs/phase2.json'}),
        case('edge_crossing', 900., 1.65, speed, 7.,
             {'kind': 'constant_actuation', 'acceleration_mps2': 0., 'steering_rad': 0.})]


def reference_at(time_s, case):
    """Quintic y(t), dy/dt and d2y/dt2 with stationary endpoint extensions."""
    ref = case['reference']
    if ref['kind'] != 'quintic_lane_change':
        raise ValueError('A lateral reference is defined only for quintic_lane_change')
    duration = ref['maneuver_duration_s']
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid maneuver duration')
    elapsed = round(time_s - case['initial']['time_s'] - ref['start_s'], 12)
    u = min(1., max(0., elapsed / duration))
    displacement = ref['y_target_m'] - ref['y_start_m']
    return {'y_m': ref['y_start_m'] + displacement * (10*u**3-15*u**4+6*u**5),
            'lateral_velocity_mps': displacement * (30*u**2-60*u**3+30*u**4) / duration,
            'lateral_acceleration_mps2': displacement * (60*u-180*u**2+120*u**3) / duration**2,
            'lateral_jerk_mps3': (displacement * (60-360*u+360*u**2) / duration**3
                                  if 0 <= elapsed < duration else 0.)}


def _linear_bicycle_reference_response(speed, physical):
    """DC lateral-acceleration gain and first-order phase lag of the 2-DOF plant.

    H(s) = (n2*s^2+n1*s+n0)/(s^2+d1*s+d0), from steering to ay.
    H(0)=n0/d0 and H(s)/H(0)=1-(d1/d0-n1/n0)*s+O(s^2).
    Using the inverse first-order term is model-based reference feedforward,
    not a fitted tracking gain. Actuator lag is compensated in the same way.
    """
    m, iz = physical['mass_kg'], physical['yaw_inertia_kgm2']
    lf, lr = physical['cg_to_front_axle_m'], physical['cg_to_rear_axle_m']
    cf, cr = physical['front_cornering_stiffness_N_per_rad'], physical['rear_cornering_stiffness_N_per_rad']
    a11 = -(cf+cr)/(m*speed)
    a12 = (cr*lr-cf*lf)/(m*speed)-speed
    a21 = (cr*lr-cf*lf)/(iz*speed)
    a22 = -(cf*lf**2+cr*lr**2)/(iz*speed)
    b1, b2 = cf/m, cf*lf/iz
    d0, d1 = a11*a22-a12*a21, -(a11+a22)
    n0 = speed*(a21*b1-a11*b2)
    n1 = -a22*b1+(a12+speed)*b2
    return n0/d0, d1/d0-n1/n0


def bench_command(state, case, settings_phase2):
    """Use only ego state and the prespecified clock/reference; no road triggers."""
    ref = case['reference']
    if ref['kind'] == 'constant_actuation':
        return Actuation(ref['acceleration_mps2'], ref['steering_rad'])
    if ref['kind'] == 'time_schedule':
        # Numerical clock roundoff must not shift a declared segment boundary.
        elapsed = round(state.time_s-case['initial']['time_s'], 12)
        for segment in ref['segments']:
            if segment['start_s'] <= elapsed < segment['end_s']:
                return Actuation(segment['acceleration_mps2'], ref['steering_rad'])
        if math.isclose(elapsed, case['duration_s'], abs_tol=1e-10):
            return Actuation(ref['segments'][-1]['acceleration_mps2'], ref['steering_rad'])
        raise ValueError('Time schedule does not cover the current ego timestamp')
    if ref['kind'] == 'quintic_lane_change':
        target = reference_at(state.time_s, case)
        lateral_velocity = (state.vx_mps*math.sin(state.heading_rad)
                            + state.vy_mps*math.cos(state.heading_rad))
        acceleration = (target['lateral_acceleration_mps2']
                        + settings_phase2['tracking_kp_per_s2']*(target['y_m']-state.y_m)
                        + settings_phase2['tracking_kd_per_s']*(target['lateral_velocity_mps']-lateral_velocity))
        # This bench reference is at a fixed high-speed operating point. Its
        # physical constants are explicit in the case; a complete frozen model
        # snapshot takes precedence when supplied by offline/replay execution.
        physical = {key: settings_phase2.get(key, value)
                    for key, value in ref['model_reference'].items()}
        gain, lag = _linear_bicycle_reference_response(ref['speed_mps'], physical)
        steering = (acceleration+(lag+physical['steering_lag_s'])*target['lateral_jerk_mps3'])/gain
        drive = settings_phase2['speed_tracking_gain_per_s']*(ref['speed_mps']-state.vx_mps)
        return Actuation(drive, steering)
    raise ValueError(f"Unknown bench reference kind: {ref['kind']}")
