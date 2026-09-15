"""Pure own-observation R1--R5 longitudinal increment over unchanged NOA.

Consecutive visible physical signatures associate observations across time;
ambiguous associations are rejected. No sensor label, simulator identifier,
type, other plan or shared slot participates in a decision.
Cached commands may fade after loss; disappeared targets are never extrapolated.
"""
from dataclasses import dataclass, fields, replace
import math

from models.bezier import QuadraticLaneChange
from models.vehicle import Actuation, clip
from noa.contracts import NoaDecision, NoaMemory, memory_from_dict as noa_memory_from_dict
from noa.controller import decide as noa_decide
from noa.prediction import measured_bodies, verify_candidate
from noa.road import reconstruct
from noa.formation_rules import classify, rank


@dataclass(frozen=True, slots=True)
class FormationMemory(NoaMemory):
    reference_signature: tuple[float, ...] | None = None
    candidate_signature: tuple[float, ...] | None = None
    candidate_since_s: float | None = None
    formation_weight: float = 0.
    cached_increment_mps2: float = 0.
    formation_state: str = 'NOA_ONLY'
    formation_last_time_s: float | None = None
    formation_lane_signature: tuple | None = None
    formation_lane_since_s: float | None = None
    formation_lane_lock_until_s: float | None = None
    formation_lane_rng_state: int | None = None
    formation_lane_draw_count: int = 0
    formation_lane_backoff_until_s: float | None = None

    def __post_init__(self):
        _validate_phase5g_memory(self)


def _base_memory(memory):
    return NoaMemory(**{f.name:getattr(memory, f.name) for f in fields(NoaMemory)}) if isinstance(
        memory, NoaMemory) else NoaMemory(memory.observation_history, 'CRUISE')


def memory_from_dict(data):
    """Restore JSON/asdict with the same nested observation/NOA plan schema."""
    base_names = {f.name for f in fields(NoaMemory)}
    base = noa_memory_from_dict({k:v for k, v in data.items() if k in base_names})
    extras = {k:v for k, v in data.items() if k not in base_names}
    for key in ('reference_signature', 'candidate_signature', 'formation_lane_signature'):
        if extras.get(key) is not None:
            extras[key] = tuple(extras[key])
    return FormationMemory(**{f.name:getattr(base, f.name) for f in fields(NoaMemory)}, **extras)


def _validate_phase5g_memory(memory, time=None):
    for name in (
        'formation_lane_since_s',
        'formation_lane_lock_until_s',
        'formation_lane_backoff_until_s',
    ):
        value = getattr(memory, name)
        if value is not None and (
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
        ):
            raise ValueError('Invalid Phase 5G own timestamp: '+name)
    if (
        time is not None
        and (type(time) not in (int, float) or not math.isfinite(time) or time < 0)
    ):
        raise ValueError('Invalid Phase 5G current time')
    if (
        time is not None
        and memory.formation_lane_since_s is not None
        and memory.formation_lane_since_s > time + 1e-9
    ):
        raise ValueError('Phase 5G candidate memory is from the future')
    state = memory.formation_lane_rng_state
    if state is not None and (type(state) is not int or not 0 <= state < 2**64):
        raise ValueError('Invalid private Phase 5G uint64 state')
    if type(memory.formation_lane_draw_count) is not int or memory.formation_lane_draw_count < 0:
        raise ValueError('Invalid private Phase 5G draw count')
    signature = memory.formation_lane_signature
    if signature is not None:
        if (
            type(signature) is not tuple
            or len(signature) != 8
            or type(signature[0]) is not int
            or signature[0] < 0
        ):
            raise ValueError('Invalid Phase 5G candidate physical signature')
        physical = signature[1:]
        if (
            any(type(value) not in (int, float) or not math.isfinite(value) for value in physical)
            or min(physical[5:]) <= 0
        ):
            raise ValueError('Invalid Phase 5G candidate physical signature')
    has_signature = signature is not None
    has_since = memory.formation_lane_since_s is not None
    if has_signature != has_since:
        raise ValueError('Phase 5G candidate signature and since timestamp must coexist')
    deadline = memory.formation_lane_backoff_until_s
    if deadline is not None:
        if not has_signature:
            raise ValueError('Phase 5G backoff deadline requires a candidate episode')
        if deadline <= memory.formation_lane_since_s:
            raise ValueError('Phase 5G backoff deadline must be later than episode start')
        if memory.formation_lane_draw_count < 1:
            raise ValueError('Phase 5G backoff deadline requires a private draw')


def _validate(parameters, memory, time):
    if parameters.get('formation_reference_rule') not in ('front_first', 'corner_first'):
        raise ValueError('Unknown predeclared formation reference rule')
    names = ('formation_d_ref_m', 'formation_kp_per_s2', 'formation_kv_per_s',
             'formation_accel_limit_mps2', 'formation_fade_s', 'formation_reference_stable_s',
             'formation_max_relative_speed_mps', 'formation_max_lateral_speed_mps',
             'formation_lane_change_cooldown_s', 'formation_position_tolerance_m',
             'formation_maintaining_speed_tolerance_mps', 'formation_switch_cost')
    for name in names:
        value = parameters[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid positive formation parameter: '+name)
    if not 0 <= memory.formation_weight <= 1:
        raise ValueError('Formation weight outside [0,1]')
    if memory.formation_last_time_s is not None and time < memory.formation_last_time_s-1e-9:
        raise ValueError('Formation memory is from the future')
    if memory.candidate_since_s is not None and memory.candidate_since_s > time+1e-9:
        raise ValueError('Formation candidate is from the future')
    for signature in (memory.reference_signature, memory.candidate_signature):
        if signature is not None and (len(signature) != 7 or not all(math.isfinite(v) for v in signature)):
            raise ValueError('Invalid own reference physical signature')
    _validate_phase5g_memory(memory, time)


def _associate(signature, candidates, elapsed, p):
    """Match current visible bodies inside inherited physical motion bounds.

    The previous signature has no authority if zero or multiple current bodies
    could be the same object. It is never used as an invisible target position.
    """
    if signature is None:
        return None
    x, y, vx, vy, heading, length, width = signature
    tolerance = p['noa_geometry_tolerance_m']
    bound = max(abs(p['min_accel_mps2']), p['max_accel_mps2'])
    matches = []
    for candidate in candidates:
        nx, ny, nvx, nvy, nh, nl, nw = candidate['signature']
        if (abs(nx-x-vx*elapsed) <= bound*elapsed*elapsed/2+tolerance
                and abs(ny-y-vy*elapsed) <= 2*p['formation_max_lateral_speed_mps']*elapsed+tolerance
                and abs(nvx-vx) <= bound*elapsed+tolerance
                and abs(nl-length) <= tolerance and abs(nw-width) <= tolerance):
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def _references(control, road, memory, p, neighborhood):
    """Local candidate phase and residuals; absolute world origin cancels out."""
    ego = control.ego
    if neighborhood['ego_lane_overlap']:
        return [], 'own_lane_occupied'
    items = [(item['body'], abs(item['lane_offset']), item['region'])
             for item in neighborhood['items'] if item['region'] != 'X']
    candidates = []
    for body, delta_lane, region in items:
        dx = body.x-ego.x_m
        relative_speed = body.vx-(ego.vx_mps*math.cos(ego.heading_rad)-ego.vy_mps*math.sin(ego.heading_rad))
        if (region not in ('F', 'FL', 'FR') or dx <= 0 or abs(relative_speed) > p['formation_max_relative_speed_mps']
                or abs(body.vy) > p['formation_max_lateral_speed_mps']):
            continue
        spacing = p['formation_d_ref_m']*(1 if delta_lane else 2)
        error = dx-spacing
        residuals = []
        for other_body, other_lane, _ in items:
            if other_body is body:
                continue
            offset = other_body.x-(body.x-spacing)-other_lane*p['formation_d_ref_m']
            period = 2*p['formation_d_ref_m']
            residuals.append(abs((offset+period/2)%period-period/2))
        residual = math.fsum(sorted(residuals))/len(residuals) if residuals else 0.
        physical = (body.x, body.y, body.vx, body.vy, body.heading, body.length, body.width)
        candidates.append({'signature':physical, 'error_m':error, 'relative_speed_mps':relative_speed,
                           'residual_m':residual, 'region':region, 'dx_m':dx})
    elapsed = 0. if memory.formation_last_time_s is None else max(0., ego.time_s-memory.formation_last_time_s)
    held = _associate(memory.reference_signature, candidates, elapsed, p)
    return rank(candidates, held, p)


def decide(control, parameters):
    """One immutable local input -> action, own memory, explicit safety evidence."""
    phase5g_lane_active = (
        parameters.get('phase5g_enabled') is True
        and parameters.get('formation_lane_change_enabled') is True
    )
    if phase5g_lane_active and isinstance(control.memory, FormationMemory):
        _validate_phase5g_memory(control.memory, control.ego.time_s)
    base_memory = (
        control.memory
        if phase5g_lane_active and isinstance(control.memory, FormationMemory)
        else _base_memory(control.memory)
    )
    base_control = replace(control, memory=base_memory)
    base = noa_decide(base_control, parameters)
    if not parameters.get('formation_enabled', False):
        return base
    p, e = parameters, control.ego
    memory = control.memory if isinstance(control.memory, FormationMemory) else FormationMemory(
        **{f.name:getattr(base_control.memory, f.name) for f in fields(NoaMemory)})
    _validate(p, memory, e.time_s)
    # noa_decide has validated the entire original NOA input. Include extra own
    # formation fields in finite checks without accepting hidden data channels.
    for f in fields(FormationMemory):
        value = getattr(memory, f.name)
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError('Nonfinite own formation memory')
    dt = 0. if memory.formation_last_time_s is None else e.time_s-memory.formation_last_time_s
    if dt < 0 and dt > -1e-9:
        dt = 0.
    if dt > p['control_sync_dt_s']+1e-9:
        # Missing observations do not count as evidence of continuous stability.
        # The old cache has no authority after a discontinuous replay/input gap.
        memory = replace(memory, reference_signature=None, candidate_signature=None,
                         candidate_since_s=None, formation_weight=0., cached_increment_mps2=0.)
    # The finite cache advances once per supplied observation; no elapsed-gap
    # catch-up can instantly authorize a newly seen reference.
    ramp = min(dt, p['control_sync_dt_s'])/p['formation_fade_s']
    lane_updates = ({
        f.name:getattr(base.memory, f.name)
        for f in fields(FormationMemory)
        if f.name.startswith('formation_lane_')
    } if phase5g_lane_active and isinstance(base.memory, FormationMemory) else {})
    new = replace(memory, **{f.name:getattr(base.memory, f.name) for f in fields(NoaMemory)},
                  **lane_updates, formation_last_time_s=e.time_s)
    diag = {'reason':'no_reference', 'base_acceleration_mps2':base.action.acceleration_mps2,
            'raw_increment_mps2':0., 'applied_increment_mps2':0., 'target_error_m':None,
            'relative_speed_mps':None, 'conflict_residual_m':0., 'prediction':None,
            'reference_signature':None, 'candidate_signature':None, 'weight':0., 'state':'NOA_ONLY'}
    road = reconstruct(e, control.observation.road, p)
    neighborhood = classify(control, road, p)
    diag.update(reference_rule=p['formation_reference_rule'], region_counts=neighborhood['region_counts'],
                selection_rule='base_noa_or_visible_risk_priority',
                classified_neighbors=[{'region':item['region'],
                    'relative_x_m':item['body'].x-e.x_m, 'relative_y_m':item['body'].y-e.y_m,
                    'side_band_half_length_m':item['side_band_half_length_m']} for item in neighborhood['items']])
    own_vy = e.vx_mps*math.sin(e.heading_rad)+e.vy_mps*math.cos(e.heading_rad)
    cooldown = base.memory.last_lc_end_s is not None and e.time_s-base.memory.last_lc_end_s < p['formation_lane_change_cooldown_s']
    risk = (base.memory.own_behavior not in ('CRUISE', 'FOLLOW') or base.memory.plan is not None
            or (p.get('r5_enabled',False) and base.memory.r5_episode_signature is not None)
            or base.diagnostics['lane_end_distance_m'] is not None or cooldown
            or abs(own_vy) > p['formation_max_lateral_speed_mps']
            or abs(e.y_m-road.current_center_m) > p['noa_completion_lateral_error_m'])
    if risk:
        new = replace(new, reference_signature=None, candidate_signature=None, candidate_since_s=None,
                      formation_weight=0., cached_increment_mps2=0., formation_state='FALLBACK')
        diag['reason'] = 'base_noa_or_visible_risk_priority'
    else:
        candidates, diag['selection_rule'] = _references(control, road, memory, p, neighborhood)
        selected = _associate(memory.reference_signature, candidates, dt, p)
        best = candidates[0] if candidates else None
        if best is not None and best is not selected:
            pending = _associate(memory.candidate_signature, candidates, dt, p)
            since = memory.candidate_since_s if pending is best else e.time_s
            new = replace(new, candidate_signature=best['signature'], candidate_since_s=since)
            if e.time_s-since >= p['formation_reference_stable_s']-1e-9:
                selected = best
                new = replace(new, reference_signature=best['signature'], candidate_signature=None, candidate_since_s=None)
        else:
            new = replace(new, candidate_signature=None, candidate_since_s=None)
        if selected is not None:
            raw = clip(p['formation_kp_per_s2']*selected['error_m']+p['formation_kv_per_s']*selected['relative_speed_mps'],
                       -p['formation_accel_limit_mps2'], p['formation_accel_limit_mps2'])
            confidence = 1./(1.+selected['residual_m']/p['formation_position_tolerance_m'])
            weight = clip(confidence, max(0., memory.formation_weight-ramp), min(1., memory.formation_weight+ramp))
            state = 'MAINTAINING' if (abs(selected['error_m']) <= p['formation_position_tolerance_m']
                     and abs(selected['relative_speed_mps']) <= p['formation_maintaining_speed_tolerance_mps']) else 'FORMING'
            new = replace(new, reference_signature=selected['signature'], formation_weight=weight,
                          cached_increment_mps2=raw, formation_state=state)
            diag.update(reason='visible_reference', target_error_m=selected['error_m'],
                        relative_speed_mps=selected['relative_speed_mps'], conflict_residual_m=selected['residual_m'])
        else:
            weight = max(0., memory.formation_weight-ramp)
            new = replace(new, reference_signature=None, formation_weight=weight,
                          cached_increment_mps2=memory.cached_increment_mps2 if weight > 1e-12 else 0.,
                          formation_state='RECONFIGURING' if memory.formation_weight > 0 else 'NOA_ONLY')
            diag['reason'] = 'lost_reference_decay' if memory.formation_weight > 0 else 'reference_stabilizing' if best else 'no_reference'
    increment = new.formation_weight*new.cached_increment_mps2
    action = base.action
    diag['raw_increment_mps2'] = new.cached_increment_mps2
    if abs(increment) > 1e-12:
        proposed = clip(base.action.acceleration_mps2+increment,
                        max(p['min_accel_mps2'], -p['comfort_braking_mps2']),
                        min(p['max_accel_mps2'], p['comfort_accel_mps2']))
        # Full inherited 5s maneuver horizon + settling, same acceleration,
        # jerk, actuator, observed road and hard neighbor reachability limits.
        hold = QuadraticLaneChange(e.time_s, road.current_center_m, road.current_center_m,
                                   p['noa_lane_change_duration_s'], max(e.vx_mps, p['noa_min_lane_change_speed_mps']))
        prediction = verify_candidate(base_control, hold, road, proposed, p)
        diag['prediction'] = prediction
        if prediction['safe']:
            action = Actuation(proposed, base.action.steering_rad)
            diag['applied_increment_mps2'] = proposed-base.action.acceleration_mps2
        else:
            diag['reason'] = 'safety_rejected'
            new = replace(new, formation_state='FALLBACK')
    diag.update(weight=new.formation_weight, state=new.formation_state,
                reference_signature=new.reference_signature, candidate_signature=new.candidate_signature)
    return NoaDecision(action, new, {**base.diagnostics, 'formation':diag})
