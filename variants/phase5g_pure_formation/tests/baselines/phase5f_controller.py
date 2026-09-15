"""Independent local NOA: pure immutable input -> action and own memory.

No map, simulator, file IO, hidden vehicle labels, local IDs, shared state or
other agents' plans are consulted. See notes for conditional safety limits.
"""
from dataclasses import asdict, replace
import math

from models.bezier import QuadraticLaneChange
from models.vehicle import Actuation, clip
from noa.contracts import NoaDecision, NoaMemory
from noa.low_speed import (candidate_profiles, peak_reference_lateral_accel,
                           steering_speed_floor, validated_durations)
from noa.prediction import actuator_acceleration_upper, lateral_command, measured_bodies, reference_target, verify_candidate
from noa.road import reconstruct
from noa import r5, waiting_game


def _finite(value):
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return not isinstance(value, (int, float)) or math.isfinite(value)


def _validate(control, parameters):
    if not _finite(asdict(control)):
        raise ValueError('Nonfinite local controller input or own memory')
    if not all(_finite(v) and isinstance(v, (int, float)) and v >= 0
               for k, v in parameters.items() if k.startswith('noa_')):
        raise ValueError('Invalid nonnegative finite NOA parameter')
    for name in ('length_m', 'width_m', 'wheelbase_m', 'max_speed_mps',
                 'comfort_braking_mps2', 'comfort_accel_mps2', 'comfort_lateral_accel_mps2',
                 'actuator_jerk_limit_mps3', 'acceleration_lag_s', 'steering_lag_s',
                 'max_accel_mps2', 'max_steering_rad', 'max_steering_rate_radps',
                 'steering_lateral_envelope_mps2', 'max_dynamics_dt_s', 'control_sync_dt_s',
                 'noa_prediction_dt_s', 'noa_lane_change_duration_s', 'noa_headway_s',
                 'noa_geometry_tolerance_m', 'noa_prediction_settle_s',
                 'noa_speed_gain_per_s', 'noa_stop_speed_gain_per_s', 'noa_response_time_s', 'behavior_dt_s'):
        if not math.isfinite(parameters[name]) or parameters[name] <= 0:
            raise ValueError('Invalid positive controller parameter: '+name)
    if not math.isfinite(parameters['min_accel_mps2']) or parameters['min_accel_mps2'] >= 0:
        raise ValueError('Invalid negative braking bound')
    if parameters['noa_response_time_s']+1e-12 < parameters['control_sync_dt_s']+parameters['acceleration_lag_s']:
        raise ValueError('Planning response must cover control and actuator lag')
    ratio=parameters['behavior_dt_s']/parameters['control_sync_dt_s']
    if ratio < 1 or not math.isclose(ratio,round(ratio),abs_tol=1e-9,rel_tol=0.):
        raise ValueError('Behavior period must contain whole control intervals')
    if not (0 <= control.ego.vx_mps <= parameters['max_speed_mps']):
        raise ValueError('Ego speed outside supported model interval')
    if control.observation.time_s != control.ego.time_s or control.observation.road.measurement_time_s != control.ego.time_s:
        raise ValueError('Controller requires same-time ideal observations')
    if any(n.measurement_time_s != control.ego.time_s or min(n.length_m, n.width_m) <= 0
           for n in control.observation.neighbors):
        raise ValueError('Invalid neighbor measurement timestamp or body')


def _stop_distance(speed, acceleration, braking, parameters):
    """Integrate a conservative jerk ramp followed by a braking tail.

    Reserve control + lag delay, then use full jerk until one lag-width short
    of desired deceleration and retain that weaker deceleration for the tail.
    This is a screening approximation, not an invariant-set safety proof.
    """
    p = parameters
    response = p['noa_response_time_s']
    positive = max(0., acceleration)
    distance = speed*response+positive*response**2/2
    speed += positive*response
    jerk = p['actuator_jerk_limit_mps3']
    weaker = max(braking/2, braking-jerk*p['acceleration_lag_s'])
    initial = max(acceleration, -weaker)
    ramp = max(0., (initial+weaker)/jerk)
    stop_during_ramp = (initial+math.sqrt(initial**2+2*jerk*speed))/jerk
    t = min(ramp, stop_during_ramp)
    distance += speed*t+initial*t*t/2-jerk*t*t*t/6
    remaining_speed = max(0., speed+initial*t-jerk*t*t/2)
    return distance+remaining_speed**2/(2*weaker)


def _comfortable_speed(distance, parameters, acceleration=0.):
    """Invert the same conservative stopping envelope continuously in gap.

    Nonnegative current acceleration reserves continuing drive response; the
    hard screen separately retains the signed observed actuator acceleration.
    """
    p = parameters
    lower, upper = 0., min(p['noa_target_speed_mps'], p['max_speed_mps'])
    available = max(0., distance)

    def required(speed):
        stopping = _stop_distance(speed, max(0., acceleration), p['comfort_braking_mps2'], p)
        return stopping + speed/p['noa_speed_gain_per_s']

    if required(upper) <= available:
        return upper
    while upper-lower > p['noa_geometry_tolerance_m']:
        middle = (lower+upper)/2
        # A speed-feedback controller does not attain its cap instantly.
        # Reserve its 1/gain settling distance as well as braking response.
        if required(middle) <= available:
            lower = middle
        else:
            upper = middle
    return lower


def _longitudinal(ego, bodies, center_y, lane_end_x, parameters):
    p, speed = parameters, ego.vx_mps
    half_dt = p['control_sync_dt_s']/2
    feedback_speed = clip(speed+ego.acceleration_mps2*half_dt,0.,p['max_speed_mps'])
    actuator_upper = actuator_acceleration_upper(ego, p)
    acceleration = p['noa_speed_gain_per_s']*(min(p['noa_target_speed_mps'], p['max_speed_mps'])-feedback_speed)
    closest, closest_gap, emergency = None, None, False
    for body in bodies:
        lateral_half = (p['width_m']+abs(math.cos(body.heading))*body.width+abs(math.sin(body.heading))*body.length)/2
        # Observed lateral motion projects cut-ins over the near response time.
        lateral_now, lateral_future = body.y-ego.y_m, body.y+body.vy*p['noa_emergency_ttc_s']-ego.y_m
        crosses = min(lateral_now, lateral_future) <= lateral_half and max(lateral_now, lateral_future) >= -lateral_half
        overlaps_lane = abs(body.y-center_y) <= lateral_half
        if body.x <= ego.x_m or not (crosses or overlaps_lane):
            continue
        body_half = (abs(math.cos(body.heading))*body.length+abs(math.sin(body.heading))*body.width)/2
        gap = body.x-ego.x_m-p['length_m']/2-body_half
        if closest_gap is None or gap < closest_gap:
            closest, closest_gap = body, gap
    reason = 'cruise'
    if closest is not None:
        gap, lead_speed = closest_gap, max(0., closest.vx)
        closing = speed-lead_speed
        feedback_gap = gap+(lead_speed-speed)*half_dt
        desired = p['noa_standstill_gap_m']+p['noa_headway_s']*feedback_speed
        follow = p['noa_gap_gain_per_s2']*(feedback_gap-desired)-p['noa_relative_speed_gain_per_s']*(feedback_speed-lead_speed)
        acceleration, reason = min(acceleration, follow), 'visible_lead'
        # Assume immediate full-hard braking of the lead. Own stopping includes
        # control/actuator/jerk allowance. A negative margin is an emergency.
        lead_stop = lead_speed**2/(2*abs(p['min_accel_mps2']))
        required_hard = p['noa_standstill_gap_m']+_stop_distance(speed, actuator_upper,
                                                              abs(p['min_accel_mps2']), p)-lead_stop
        safe_speed = _comfortable_speed(feedback_gap+lead_stop-p['noa_standstill_gap_m'], p, actuator_upper)
        acceleration = min(acceleration, p['noa_speed_gain_per_s']*(safe_speed-feedback_speed))
        emergency = gap < required_hard or (closing > 0 and gap/closing < p['noa_emergency_ttc_s'])
        if speed <= p['noa_stop_release_speed_mps'] and lead_speed <= p['noa_stop_release_speed_mps'] and gap <= p['noa_standstill_gap_m']:
            acceleration = min(acceleration, 0.)
        if (lead_speed <= p['noa_stop_release_speed_mps'] and speed <= p['noa_stop_capture_speed_mps']
                and gap <= p['noa_stop_capture_gap_m']+p['noa_headway_s']*p['noa_stop_capture_speed_mps']):
            # Initiate the terminal speed-feedback profile in a fixed local
            # capture region, then hold until the observed lead moves/leaves.
            acceleration = min(acceleration, -p['noa_stop_speed_gain_per_s']*speed-p['noa_stop_terminal_braking_mps2'])
    if lane_end_x is not None:
        gap = lane_end_x-ego.x_m-p['length_m']/2-p['noa_body_margin_m']-p['noa_standstill_gap_m']
        # A visible physical lane end is a stationary virtual target. Merely
        # releasing a braking-distance trigger at low speed causes repeated
        # restarts into a blocked endpoint; continuous gap feedback avoids it.
        # The comfortable stop target stays upstream of the hard screening
        # boundary, leaving a spatial reserve for terminal tracking error.
        virtual_follow = p['noa_speed_gain_per_s']*(_comfortable_speed(gap-speed*half_dt-p['noa_stop_position_reserve_m'],p,actuator_upper)-feedback_speed)
        acceleration = min(acceleration, virtual_follow)
        reason = 'observed_lane_end_approach'
        if virtual_follow < 0:
            reason = 'observed_lane_end_braking'
        if speed <= p['noa_stop_capture_speed_mps'] and gap <= p['noa_stop_capture_gap_m']+p['noa_headway_s']*p['noa_stop_capture_speed_mps']:
            acceleration = min(acceleration, -p['noa_stop_speed_gain_per_s']*speed-p['noa_stop_terminal_braking_mps2'])
            reason = 'observed_lane_end_hold'
        if gap <= _stop_distance(speed, actuator_upper, abs(p['min_accel_mps2']), p):
            emergency = True
    if emergency:
        acceleration = min(acceleration, p['min_accel_mps2'])
    else:
        # Taper before the speed boundary: a finite weak tail eventually stops
        # through the unchanged integrator, without zeroing actuator or speed.
        acceleration = max(acceleration, -p['noa_stop_speed_gain_per_s']*speed-p['noa_stop_terminal_braking_mps2'])
        acceleration = clip(acceleration, -p['comfort_braking_mps2'], p['comfort_accel_mps2'])
    return clip(acceleration, p['min_accel_mps2'], p['max_accel_mps2']), closest, closest_gap, emergency, reason


def decide(control, parameters):
    _validate(control, parameters)
    if 'r5_waiting_policy' in parameters:
        waiting_game.validate_parameters(parameters)
    p, ego = parameters, control.ego
    memory = control.memory if isinstance(control.memory, NoaMemory) else NoaMemory(
        control.memory.observation_history, 'CRUISE')
    r5_enabled = p.get('r5_enabled',False)
    adaptive = (p.get('phase5f_enabled',False) and r5_enabled
                and p.get('r5_lane_priority_enabled',False))
    if r5_enabled:
        r5.validate(memory,ego.time_s,p)
    road = reconstruct(ego, control.observation.road, p)
    bodies = measured_bodies(control)
    end_x = road.lane_end(road.current_center_m, p['width_m'], p['noa_geometry_tolerance_m'])
    if end_x is not None and end_x < ego.x_m:
        end_x = None
    active = memory.plan is not None
    center = memory.target_y_m if active else road.current_center_m
    # Source lane ending is a stop constraint until the maneuver is feasible.
    accel, lead, gap, emergency, reason = _longitudinal(ego, bodies, center, end_x, p)
    diagnostics = {'reason':reason, 'lead_gap_m':gap,
                   'own_actuator_acceleration_upper_mps2':actuator_acceleration_upper(ego, p),
                   'lane_center_y_m':road.current_center_m,
                   'lane_end_distance_m':None if end_x is None else end_x-ego.x_m,
                   'candidate_rejections':[], 'prediction':None,
                   'prediction_assumptions':'ego current acceleration request held; neighbor hard-bounded longitudinal acceleration and speed; measured inertial lateral velocity plus configured bound; no cooperative intent'}
    if adaptive:
        diagnostics.update(candidate_evaluations=[], selected_candidate_duration_s=None)
    if active:
        plan = memory.plan
        reached = ego.time_s >= plan.start_s+plan.duration_s and abs(ego.y_m-plan.y_target_m) <= p['noa_completion_lateral_error_m'] and abs(ego.heading_rad) <= p['noa_completion_heading_rad']
        if reached:
            memory = replace(memory, plan=None, target_y_m=None, prepare_since_s=None,
                             last_lc_end_s=ego.time_s, completed_lane_changes=memory.completed_lane_changes+1,
                             lane_change_reason='')
            if r5_enabled:
                memory=replace(memory,r5_phase='IDLE',r5_deadline_s=None,r5_episode_signature=None,
                               r5_clear_since_s=None,r5_last_time_s=ego.time_s)
            active = False
        else:
            # Release the source-end stop constraint only for the actual action
            # whose full remaining body sweep clears the observed road/traffic.
            maneuver_accel, _, _, maneuver_emergency, _ = _longitudinal(ego, bodies, ego.y_m, None, p)
            prediction = verify_candidate(control, plan, road, maneuver_accel, p)
            diagnostics['prediction'] = prediction
            state = 'MERGE' if memory.lane_change_reason == 'observed_lane_end' else 'EXECUTE_LC'
            if prediction['safe'] and not maneuver_emergency:
                accel = maneuver_accel
            else:
                accel, state = min(accel, -p['comfort_braking_mps2']), 'EMERGENCY'
                diagnostics['reason'] = 'active_plan_prediction_unavailable' if not prediction['safe'] else reason
                diagnostics['fallback_prediction'] = verify_candidate(control, plan, road, accel, p)
            action = Actuation(accel, lateral_command(ego, reference_target(plan, ego.time_s), p))
            if r5_enabled:
                memory=replace(memory,r5_last_time_s=ego.time_s)
                diagnostics['r5']=r5.diagnostic(memory,None,[],False,'active_plan_bypass')
            return NoaDecision(action, replace(memory, own_behavior=state), diagnostics)
    if r5_enabled:
        # Existing private time and visible clearing progress even below the
        # unchanged lane-change minimum speed or without a current motivation.
        if memory.r5_episode_signature is not None:
            target_y=memory.r5_episode_signature[0]
            if target_y in road.centers_m:
                prior_candidate=QuadraticLaneChange(ego.time_s,road.current_center_m,target_y,
                    p['noa_lane_change_duration_s'],max(ego.vx_mps,p['noa_min_lane_change_speed_mps']))
                assessment=r5.assess_candidate(control,road,prior_candidate,memory,p)
                memory,diagnostics['r5']=r5.advance_backoff(assessment,memory,ego.time_s,p,allow_draw=False)
            else:
                memory=replace(memory,r5_phase='UNKNOWN',r5_last_time_s=ego.time_s)
                diagnostics['r5']=r5.diagnostic(memory,None,[],True,'target_strip_no_longer_visible')
        else:
            memory=replace(memory,r5_last_time_s=ego.time_s)
            diagnostics['r5']=r5.diagnostic(memory,None,[],False,'no_active_episode')
    motivation = None
    if end_x is not None and end_x-ego.x_m <= max(ego.vx_mps*p['noa_merge_lookahead_s'],
                                                _stop_distance(ego.vx_mps, actuator_acceleration_upper(ego, p), p['comfort_braking_mps2'], p)):
        motivation = 'observed_lane_end'
    elif lead is not None and p['noa_target_speed_mps']-lead.vx >= p['noa_overtake_speed_deficit_mps']:
        if gap <= p['noa_standstill_gap_m']+p['noa_headway_s']*ego.vx_mps+max(0., ego.vx_mps-lead.vx)*p['noa_overtake_horizon_s']:
            motivation = 'slower_visible_lead'
    cooldown = memory.last_lc_end_s is not None and ego.time_s-memory.last_lc_end_s < p['noa_lane_change_cooldown_s']
    state = 'EMERGENCY' if emergency else ('FOLLOW' if lead is not None else 'CRUISE')
    r5_pending=[]
    if adaptive and motivation and not cooldown and not emergency:
        centers = road.centers_m
        index = centers.index(road.current_center_m)
        adjacent = [centers[i] for i in (index-1, index+1) if 0 <= i < len(centers)]
        adjacent.sort(reverse=True)
        admissible = {item['duration_s']: item for item in candidate_profiles(ego.vx_mps, p)}
        for target_y in adjacent:
            target_end = road.lane_end(target_y, p['width_m'], p['noa_geometry_tolerance_m'])
            if motivation == 'observed_lane_end' and target_end is not None and target_end <= end_x:
                diagnostics['candidate_rejections'].append({'target_y_m':target_y, 'reason':'target_also_terminates'})
                continue
            selected = None
            candidate_accel = _longitudinal(ego, bodies, road.current_center_m, None, p)[0]
            for duration in validated_durations(p):
                profile = admissible.get(float(duration))
                evaluation = {
                    'target_y_m':target_y, 'duration_s':float(duration),
                    'measured_speed_mps':ego.vx_mps,
                    'speed_floor_mps':steering_speed_floor(duration,p),
                    'peak_reference_lateral_accel_mps2':peak_reference_lateral_accel(duration,p),
                    'model_admissible':profile is not None, 'longitudinal_request_mps2':candidate_accel,
                    'r5_reason':None, 'r5_blocking':None, 'guard':None,
                }
                if profile is None:
                    diagnostics['candidate_evaluations'].append(evaluation)
                    diagnostics['candidate_rejections'].append({
                        'target_y_m':target_y, 'duration_s':float(duration),
                        'reason':'phase5f_model_speed_or_comfort_floor'})
                    continue
                candidate = QuadraticLaneChange(ego.time_s, ego.y_m, target_y,
                                                float(duration), ego.vx_mps)
                assessment = r5.assess_candidate(control,road,candidate,memory,p)
                preview,gate = r5.advance_backoff(assessment,memory,ego.time_s,p,allow_draw=False)
                evaluation.update(r5_reason=assessment['reason'], r5_blocking=gate['blocking'])
                if gate['blocking']:
                    r5_pending.append(assessment)
                    diagnostics['candidate_evaluations'].append(evaluation)
                    diagnostics['candidate_rejections'].append({
                        'target_y_m':target_y, 'duration_s':float(duration), 'reason':'r5_gate',
                        'r5_reason':gate['reason']})
                    continue
                prediction = verify_candidate(control,candidate,road,candidate_accel,p)
                evaluation['guard']=prediction
                diagnostics['candidate_evaluations'].append(evaluation)
                if not prediction['safe']:
                    diagnostics['candidate_rejections'].append({
                        'target_y_m':target_y, 'duration_s':float(duration), **prediction})
                    diagnostics['r5']=gate
                    if preview.r5_phase=='ELIGIBLE':
                        diagnostics['r5']['reason']='expired_but_guard_blocked'
                    diagnostics['r5']['candidate_guard']=prediction
                    continue
                selected=(candidate,preview,gate,prediction,candidate_accel)
                break
            if selected is None:
                continue
            candidate,preview,gate,prediction,candidate_accel=selected
            memory,diagnostics['r5']=preview,gate
            diagnostics['r5']['candidate_guard']=prediction
            diagnostics['selected_candidate_duration_s']=candidate.duration_s
            same = (memory.prepare_since_s is not None and memory.lane_change_reason == motivation
                    and memory.target_y_m is not None
                    and abs(memory.target_y_m-target_y) <= p['noa_geometry_tolerance_m'])
            since = memory.prepare_since_s if same else ego.time_s
            memory = replace(memory,target_y_m=target_y,prepare_since_s=since,lane_change_reason=motivation)
            diagnostics['reason'],diagnostics['prediction']=motivation,prediction
            state='PREPARE_LC'
            behavior_index=round(ego.time_s/p['behavior_dt_s'])
            behavior_event=math.isclose(ego.time_s,behavior_index*p['behavior_dt_s'],abs_tol=1e-9,rel_tol=0.)
            if ego.time_s-since >= p['noa_prepare_duration_s']-p['noa_geometry_tolerance_m'] and behavior_event:
                memory=replace(memory,plan=candidate)
                state='MERGE' if motivation=='observed_lane_end' else 'EXECUTE_LC'
                accel=candidate_accel
                action=Actuation(accel,lateral_command(ego,reference_target(candidate,ego.time_s),p))
                return NoaDecision(action,replace(memory,own_behavior=state),diagnostics)
            break
    if (not adaptive and motivation and not cooldown and not emergency
            and ego.vx_mps >= p['noa_min_lane_change_speed_mps']):
        centers = road.centers_m
        index = centers.index(road.current_center_m)
        adjacent = [centers[i] for i in (index-1, index+1) if 0 <= i < len(centers)]
        # Geometric preference for positive-y passing; no IDs, random or hidden rank.
        adjacent.sort(reverse=True)
        for target_y in adjacent:
            target_end = road.lane_end(target_y, p['width_m'], p['noa_geometry_tolerance_m'])
            if motivation == 'observed_lane_end' and target_end is not None and target_end <= end_x:
                diagnostics['candidate_rejections'].append({'target_y_m':target_y, 'reason':'target_also_terminates'})
                continue
            candidate = QuadraticLaneChange(ego.time_s, ego.y_m, target_y, p['noa_lane_change_duration_s'], max(ego.vx_mps, p['noa_min_lane_change_speed_mps']))
            if r5_enabled:
                assessment=r5.assess_candidate(control,road,candidate,memory,p)
                preview,gate=r5.advance_backoff(assessment,memory,ego.time_s,p,allow_draw=False)
                if gate['blocking']:
                    r5_pending.append(assessment)
                    diagnostics['candidate_rejections'].append({'target_y_m':target_y,'reason':'r5_gate',
                                                               'r5_reason':gate['reason']})
                    continue
            # A feasible merge is allowed to proceed before braking for its source
            # endpoint, but current lead constraints remain in force.
            candidate_accel = _longitudinal(ego, bodies, road.current_center_m, None, p)[0]
            prediction = verify_candidate(control, candidate, road, candidate_accel, p)
            if not prediction['safe']:
                diagnostics['candidate_rejections'].append({'target_y_m':target_y, **prediction})
                if r5_enabled:
                    diagnostics['r5']=gate
                    if preview.r5_phase=='ELIGIBLE':
                        diagnostics['r5']['reason']='expired_but_guard_blocked'
                    diagnostics['r5']['candidate_guard']=prediction
                continue
            if r5_enabled:
                memory,diagnostics['r5']=preview,gate
                diagnostics['r5']['candidate_guard']=prediction
            same = memory.prepare_since_s is not None and memory.lane_change_reason == motivation and memory.target_y_m is not None and abs(memory.target_y_m-target_y) <= p['noa_geometry_tolerance_m']
            since = memory.prepare_since_s if same else ego.time_s
            memory = replace(memory, target_y_m=target_y, prepare_since_s=since, lane_change_reason=motivation)
            diagnostics['reason'], diagnostics['prediction'] = motivation, prediction
            state = 'PREPARE_LC'
            behavior_index=round(ego.time_s/p['behavior_dt_s'])
            behavior_event=math.isclose(ego.time_s,behavior_index*p['behavior_dt_s'],abs_tol=1e-9,rel_tol=0.)
            if ego.time_s-since >= p['noa_prepare_duration_s']-p['noa_geometry_tolerance_m'] and behavior_event:
                memory = replace(memory, plan=candidate)
                state = 'MERGE' if motivation == 'observed_lane_end' else 'EXECUTE_LC'
                accel = candidate_accel
                action = Actuation(accel, lateral_command(ego, reference_target(candidate, ego.time_s), p))
                return NoaDecision(action, replace(memory, own_behavior=state), diagnostics)
            break
    if r5_enabled and state!='PREPARE_LC':
        if r5_pending:
            assessment=next((a for a in r5_pending if a['reason']=='ambiguous'),r5_pending[0])
            memory,diagnostics['r5']=r5.advance_backoff(assessment,memory,ego.time_s,p,allow_draw=True)
        if diagnostics['r5']['blocking'] and not emergency:
            proposed=min(accel,-p['r5_yield_deceleration_mps2'])
            proposed=max(proposed,-p['noa_stop_speed_gain_per_s']*ego.vx_mps-p['noa_stop_terminal_braking_mps2'])
            proposed=clip(proposed,-p['comfort_braking_mps2'],p['comfort_accel_mps2'])
            proposed=clip(proposed,p['min_accel_mps2'],p['max_accel_mps2'])
            hold=QuadraticLaneChange(ego.time_s,road.current_center_m,road.current_center_m,
                p['noa_lane_change_duration_s'],max(ego.vx_mps,p['noa_min_lane_change_speed_mps']))
            game=None
            checked=None
            if p.get('r5_waiting_policy','fixed')!='fixed':
                game=waiting_game.select_waiting(control,diagnostics['r5']['assessment'],
                    diagnostics['r5'],memory.r5_phase,accel,proposed,p)
                game.update(model_guard=None,fixed_guard=None,changed_from_fixed=False)
                selected=game['selected_request_mps2']
                if selected!=proposed:
                    game['model_guard']=verify_candidate(control,hold,road,selected,p)
                    if game['model_guard']['safe']:
                        proposed=selected
                        checked=game['model_guard']
                    else:
                        game.update(fallback=True,fallback_reason='model_guard_rejected')
            if checked is None:
                checked=verify_candidate(control,hold,road,proposed,p)
                if game is not None:
                    game['fixed_guard']=checked
                    if game['model_selected_ego_mps2']==proposed:
                        game['model_guard']=checked
                    if not checked['safe']:
                        game.update(fallback=True,fallback_reason=(
                            'model_and_fixed_guard_rejected' if game['fallback_reason']=='model_guard_rejected'
                            else 'fixed_guard_rejected'))
            diagnostics['r5']['proposed_yield_mps2']=proposed
            diagnostics['r5']['guard']=checked
            if checked['safe']:
                accel=proposed
            else:
                diagnostics['r5']['reason']='yield_not_certified'
            if game is not None:
                game.update(applied_request_mps2=accel,
                    executed=game['model_selected_ego_mps2'] is not None and checked['safe'] and not game['fallback'],
                    changed_from_fixed=checked['safe'] and proposed!=game['fixed_request_mps2'])
                diagnostics['r5']['waiting_game']=game
            state='R5_BACKOFF' if memory.r5_phase=='BACKOFF' else 'R5_YIELD'
    if state != 'PREPARE_LC':
        memory = replace(memory, target_y_m=None, prepare_since_s=None, lane_change_reason='')
    target = {'y_m':road.current_center_m, 'vy_mps':0., 'ay_mps2':0.}
    action = Actuation(accel, lateral_command(ego, target, p))
    return NoaDecision(action, replace(memory, own_behavior=state), diagnostics)
