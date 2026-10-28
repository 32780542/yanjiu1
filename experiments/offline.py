"""Offline integration, independent saved-command replay and fixed acceptance."""
from dataclasses import astuple
import math

from models.vehicle import Actuation, VehicleState
from experiments.phase2_cases import bench_command, reference_at


def _integer_count(duration, interval):
    if not all(math.isfinite(v) and v > 0 for v in (duration, interval)):
        raise ValueError('Duration and interval must be positive and finite')
    n = round(duration/interval)
    if n < 1 or not math.isclose(n*interval, duration, rel_tol=0, abs_tol=1e-10):
        raise ValueError('Duration must contain an integer number of intervals')
    return n


def run_case(model, case, control_dt_s=.1, dynamics_dt_s=.01, commands=None):
    """Integrate one interval per command; supplied commands completely bypass tracking.

    Explicit intervals and a complete saved Actuation list are sufficient for
    deterministic independent replay with the supplied model parameter snapshot.
    """
    count = _integer_count(case['duration_s'], control_dt_s)
    _integer_count(control_dt_s, dynamics_dt_s)
    if dynamics_dt_s > model.p['max_dynamics_dt_s']:
        raise ValueError('Dynamics interval exceeds registered model limit')
    if commands is not None:
        commands = list(commands)
        if len(commands) != count or not all(isinstance(c, Actuation) for c in commands):
            raise ValueError(f'Replay requires exactly {count} Actuation commands')
    state = VehicleState(**case['initial'])
    steps = []
    for index in range(count):
        command = commands[index] if commands is not None else bench_command(state, case, model.p)
        step = model.advance(state, command, control_dt_s, dynamics_dt_s)
        steps.append(step)
        state = step.final
    return steps


def _states(steps):
    if not steps:
        raise ValueError('Trajectory cannot be empty')
    result = [steps[0].initial]
    if not all(math.isfinite(v) for v in astuple(result[0])):
        raise ValueError('Trajectory contains a nonfinite initial state')
    for step in steps:
        if step.initial != result[-1] or not step.samples or step.final != step.samples[-1]:
            raise ValueError('Trajectory contains discontinuous or incomplete steps')
        if not math.isfinite(step.dt_s) or step.dt_s <= 0:
            raise ValueError('Trajectory has invalid integration interval')
        for index, state in enumerate(step.samples, 1):
            if not all(math.isfinite(v) for v in astuple(state)):
                raise ValueError('Trajectory contains a nonfinite state')
            if not math.isclose(state.time_s, step.initial.time_s+index*step.dt_s,
                                rel_tol=0, abs_tol=1e-9):
                raise ValueError('Trajectory contains missing or mistimed integration samples')
            result.append(state)
    return result


def _heading_error(a, b):
    return abs(math.atan2(math.sin(a-b), math.cos(a-b)))


def compare_trajectories(base_steps, refined_steps):
    """Compare all coarser-grid states at identical times, without interpolation."""
    base, refined = _states(base_steps), _states(refined_steps)
    if any(not math.isclose(a.time_s, b.time_s, rel_tol=0, abs_tol=1e-9)
           for a, b in ((base[0], refined[0]), (base[-1], refined[-1]))):
        raise ValueError('Trajectories must cover the same time interval')
    coarse, fine = (base, refined) if len(base) <= len(refined) else (refined, base)
    by_time = {round(state.time_s, 9): state for state in fine}
    position, heading = [], []
    for state in coarse:
        other = by_time.get(round(state.time_s, 9))
        if other is None or abs(state.time_s-other.time_s) > 1e-9:
            raise ValueError('Refinement does not contain every coarser sample time')
        position.append(math.hypot(state.x_m-other.x_m, state.y_m-other.y_m))
        heading.append(_heading_error(state.heading_rad, other.heading_rad))
    return {'max_position_error_m': max(position), 'max_heading_error_rad': max(heading),
            'compared_time_points': len(coarse)}


def _body_inside_road(state, parameters):
    """Independent sample audit; road position is never passed to the bench law."""
    c, s = math.cos(state.heading_rad), math.sin(state.heading_rad)
    corners = [(state.x_m+dx*c-dy*s, state.y_m+dx*s+dy*c)
               for dx in (-parameters['length_m']/2, parameters['length_m']/2)
               for dy in (-parameters['width_m']/2, parameters['width_m']/2)]
    # The road is a union of the two declared straight rectangles. For a body
    # straddling their seam, also constrain its intersection with x=1000.
    for x, y in corners:
        if not (0 <= x <= 1200 and 0 <= y <= (9.9 if x <= 1000 else 6.6)):
            return False
    if min(x for x, _ in corners) < 1000 < max(x for x, _ in corners):
        for x1, y1 in corners:
            for x2, y2 in corners:
                if x1 < 1000 < x2 and y1+(y2-y1)*(1000-x1)/(x2-x1) > 6.6:
                    return False
    return True


def evaluate_case(model, case, steps):
    """Return transparent errors and measured values against predeclared criteria."""
    errors, metrics = [], {}
    try:
        states = _states(steps)
    except ValueError as exc:
        return {'passed': False, 'errors': [str(exc)], 'metrics': metrics}
    p = model.p
    initial, final = states[0], states[-1]
    if initial != VehicleState(**case['initial']):
        errors.append('Initial state differs from declared case')
    if not math.isclose(final.time_s-initial.time_s, case['duration_s'], rel_tol=0, abs_tol=1e-8):
        errors.append('Trajectory does not span the complete declared duration')
    observations = [model.observe(state) for state in states]
    steering_rates = [abs(b.steering_rad-a.steering_rad)/(b.time_s-a.time_s)
                      for a, b in zip(states, states[1:])]
    actuator_jerks = [abs(b.a_drive_mps2-a.a_drive_mps2)/(b.time_s-a.time_s)
                     for a, b in zip(states, states[1:])]
    actual_jerks = [abs(b['a_long_mps2']-a['a_long_mps2'])/(sb.time_s-sa.time_s)
                   for a, b, sa, sb in zip(observations, observations[1:], states, states[1:])]
    friction_excesses = [math.hypot(d[f'fx_{axle}_N'], d[f'fy_{axle}_N'])
                        -p['road_friction_coefficient']*d[f'fz_{axle}_N']
                        for d in observations for axle in ('front', 'rear')]
    metrics.update(duration_s=final.time_s-initial.time_s,
                   sample_count=len(states), final_state=dict(zip(VehicleState.__dataclass_fields__, astuple(final))),
                   min_speed_mps=min(state.vx_mps for state in states),
                   max_speed_mps=max(state.vx_mps for state in states),
                   max_abs_heading_rad=max(abs(state.heading_rad) for state in states),
                   max_abs_yaw_rate_radps=max(abs(state.yaw_rate_radps) for state in states),
                   max_abs_a_long_mps2=max(abs(d['a_long_mps2']) for d in observations),
                   max_abs_a_lateral_mps2=max(abs(d['a_lateral_mps2']) for d in observations),
                   max_sampled_steering_rate_radps=max(steering_rates),
                   max_sampled_actuator_jerk_mps3=max(actuator_jerks),
                   max_sampled_actual_longitudinal_jerk_mps3=max(actual_jerks),
                   steering_rate_limit_violation_samples=sum(rate > p['max_steering_rate_radps']+p['rate_comparison_tolerance'] for rate in steering_rates),
                   actuator_jerk_limit_violation_samples=sum(jerk > p['actuator_jerk_limit_mps3']+p['rate_comparison_tolerance'] for jerk in actuator_jerks),
                   axle_friction_circle_violation_samples=sum(excess > p['force_comparison_tolerance_N'] for excess in friction_excesses),
                   tire_saturation_samples=sum(d['tire_saturated'] for d in observations),
                   outside_linear_tire_regime_samples=sum(d['outside_linear_tire_regime'] for d in observations),
                   outside_road_samples=sum(not _body_inside_road(state, p) for state in states))
    if metrics['min_speed_mps'] < 0 or metrics['max_speed_mps'] > p['max_speed_mps']+1e-9:
        errors.append('Speed outside physical bounds')
    if metrics['outside_road_samples']:
        errors.append('Vehicle body leaves the declared road rectangles')
    if metrics['outside_linear_tire_regime_samples']:
        errors.append('Small-slip model validity threshold exceeded')
    for field in ('steering_rate_limit_violation_samples', 'actuator_jerk_limit_violation_samples',
                  'axle_friction_circle_violation_samples'):
        if metrics[field]:
            errors.append(f'Physical constraint violation: {field}')
    if metrics['max_abs_a_lateral_mps2'] > p['comfort_lateral_accel_mps2']+p['lateral_acceleration_comparison_tolerance_mps2']:
        errors.append('Measured lateral acceleration exceeds the declared comfort limit')

    name = case['name']
    if name in ('constant_speed', 'edge_crossing'):
        position_errors = [math.hypot(state.x_m-(initial.x_m+initial.vx_mps*(state.time_s-initial.time_s)),
                                      state.y_m-initial.y_m) for state in states]
        metrics['max_analytic_position_error_m'] = max(position_errors)
        metrics['max_speed_error_mps'] = max(abs(state.vx_mps-initial.vx_mps) for state in states)
        if metrics['max_analytic_position_error_m'] > p['analytic_position_tolerance_m'] or metrics['max_speed_error_mps'] > p['analytic_speed_tolerance_mps']:
            errors.append('Constant-speed trajectory differs from analytic displacement')
        if metrics['max_abs_heading_rad'] > p['straight_heading_tolerance_rad'] or metrics['max_abs_yaw_rate_radps'] > p['straight_yaw_rate_tolerance_radps']:
            errors.append('Uncommanded heading or yaw response in straight motion')
        if name == 'edge_crossing':
            metrics['crossed_edge_seam'] = initial.x_m < 1000 < final.x_m
            if not metrics['crossed_edge_seam']:
                errors.append('Declared edge-crossing case did not cross x=1000')
    elif name == 'acceleration_stop_restart':
        ref = case['reference']
        hold = [state.vx_mps for state in states
                if ref['stop_hold_start_s']+initial.time_s <= state.time_s <= ref['restart_s']+initial.time_s]
        metrics['stop_hold_max_speed_mps'] = max(hold) if hold else None
        metrics['restart_final_speed_mps'] = final.vx_mps
        if metrics['max_speed_mps'] < initial.vx_mps+p['minimum_speed_gain_mps']:
            errors.append('Prescribed positive acceleration did not raise speed')
        if not hold or metrics['stop_hold_max_speed_mps'] > p['stopped_speed_tolerance_mps']:
            errors.append('Braking did not produce the declared full stop/hold')
        if final.vx_mps < p['minimum_restart_speed_mps']:
            errors.append('Vehicle failed to restart after the full stop')
    elif name == 'constant_steering':
        target = case['reference']['steering_rad']
        lf, lr = p['cg_to_front_axle_m'], p['cg_to_rear_axle_m']
        cf, cr = p['front_cornering_stiffness_N_per_rad'], p['rear_cornering_stiffness_N_per_rad']
        understeer = p['mass_kg']/(lf+lr)*(lr/cf-lf/cr)
        steady_yaw = initial.vx_mps*target/(lf+lr+understeer*initial.vx_mps**2)
        metrics['expected_steady_yaw_rate_radps'] = steady_yaw
        metrics['terminal_yaw_rate_error_radps'] = abs(final.yaw_rate_radps-steady_yaw)
        metrics['terminal_steering_error_rad'] = abs(final.steering_rad-target)
        if final.heading_rad*target <= 0 or final.yaw_rate_radps*target <= 0:
            errors.append('Constant steering failed to produce the expected turn direction')
        if metrics['terminal_steering_error_rad'] > p['steady_steering_tolerance_rad'] or metrics['terminal_yaw_rate_error_radps'] > p['steady_yaw_relative_tolerance']*abs(steady_yaw):
            errors.append('Constant steering did not settle near the linear bicycle response')
    elif name == 'lane_change':
        metrics['max_reference_error_m'] = max(abs(state.y_m-reference_at(state.time_s, case)['y_m']) for state in states)
        metrics['terminal_lane_error_m'] = abs(final.y_m-case['reference']['y_target_m'])
        metrics['terminal_heading_error_rad'] = _heading_error(final.heading_rad, 0.)
        metrics['terminal_abs_yaw_rate_radps'] = abs(final.yaw_rate_radps)
        if metrics['max_reference_error_m'] > p['max_lane_change_error_m']:
            errors.append('Lane-change peak reference error exceeds registered threshold')
        if metrics['terminal_lane_error_m'] > p['terminal_lane_error_m']:
            errors.append('Lane-change terminal lane error exceeds registered threshold')
        if metrics['terminal_heading_error_rad'] > p['terminal_heading_tolerance_rad'] or abs(final.yaw_rate_radps) > p['terminal_yaw_rate_tolerance_radps']:
            errors.append('Lane-change terminal heading/yaw response has not settled')
    else:
        errors.append(f'No declared acceptance rule for case {name}')
    return {'passed': not errors, 'errors': errors, 'metrics': metrics}
