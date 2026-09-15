"""Finite local waiting preferences, subordinate to the unchanged R5 guard.

The peer leader and ego follower exist only in this ego's internal model.
The peer target and utility are proxy assumptions, never observed intent or
a joint equilibrium. Signed forward separation is a preference, not safety.
"""
from dataclasses import astuple
import math

from models.vehicle import clip
from noa.prediction import distance_at, measured_bodies


MODES = ('fixed', 'minimax', 'stackelberg')
_REASONS = ('yield_visible_upper_lane', 'yield_visible_front', 'yield_entered',
            'yield_visible_inward_motion', 'yield_occupied_corridor')
_DEFAULTS = dict(r5_game_horizon_s=5., r5_game_peer_accel_mps2=.5,
                 r5_game_gap_weight=1., r5_game_speed_weight=1.,
                 r5_game_effort_weight=.05)
_ASSUMPTIONS = ('ego-local finite model; peer=leader and ego=follower only inside this model; '
                'peer target speed and utility are proxy assumptions, not known intent; '
                'constant world-longitudinal requests with clipped speed; '
                'signed peer-ahead gap is a preference, not a safety guarantee or joint equilibrium; '
                'only ego request may be executed after the unchanged all-neighbor guard')


def _mode(mode):
    if type(mode) is not str or mode not in MODES:
        raise ValueError('Invalid r5_waiting_policy')
    return mode


def waiting_parameters(mode='fixed'):
    """Return only the registered opt-in additions; fixed preserves parent p."""
    _mode(mode)
    return {} if mode == 'fixed' else {'r5_waiting_policy': mode, **_DEFAULTS}


def _number(value, name):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError('Invalid finite waiting-model number: '+name)
    return value


def validate_parameters(p):
    mode = _mode(p.get('r5_waiting_policy', 'fixed'))
    if mode == 'fixed':
        return mode
    for key in (*_DEFAULTS, 'min_accel_mps2', 'max_accel_mps2', 'max_speed_mps',
                'noa_target_speed_mps'):
        _number(p.get(key), key)
    if p['r5_game_horizon_s'] <= 0 or p['r5_game_peer_accel_mps2'] <= 0:
        raise ValueError('Waiting horizon and peer acceleration must be positive')
    if not p['min_accel_mps2'] < 0 < p['max_accel_mps2']:
        raise ValueError('Invalid inherited hard acceleration bounds')
    if p['r5_game_peer_accel_mps2'] > min(p['max_accel_mps2'], abs(p['min_accel_mps2'])):
        raise ValueError('Peer acceleration exceeds inherited hard bounds')
    weights = [p[key] for key in ('r5_game_gap_weight', 'r5_game_speed_weight', 'r5_game_effort_weight')]
    if min(weights) < 0 or (weights[0] == 0 and weights[1] == 0):
        raise ValueError('Waiting weights must be nonnegative with a gap or speed objective')
    if p['noa_target_speed_mps'] <= 0 or p['max_speed_mps'] <= 0:
        raise ValueError('Waiting target and maximum speeds must be positive')
    return mode


def solve_matrix(mode, ego_actions, peer_actions, ego_costs, peer_costs):
    """Exact finite minimax or pessimistic peer-leader Stackelberg solution.

    Matrices use ego rows and peer columns. All ties are exact comparisons;
    action order cannot supply an implicit rank. In minimax, reported peer is
    the worst ego-cost witness, with the smaller peer action breaking ties.
    """
    if _mode(mode) == 'fixed':
        raise ValueError('Fixed waiting has no matrix solver')
    ea, pa = list(ego_actions), list(peer_actions)
    if not ea or not pa:
        raise ValueError('Waiting matrix requires both action sets')
    for a in ea+pa:
        _number(a, 'action')
    if len(set(ea)) != len(ea) or len(set(pa)) != len(pa):
        raise ValueError('Waiting matrix action sets must be unique')
    for costs in (ego_costs, peer_costs):
        if len(costs) != len(ea) or any(len(row) != len(pa) for row in costs):
            raise ValueError('Waiting matrix shape mismatch')
        for row in costs:
            for cost in row:
                _number(cost, 'cost')
    rows, cols = sorted(range(len(ea)), key=ea.__getitem__), sorted(range(len(pa)), key=pa.__getitem__)
    ec = [[ego_costs[i][j] for j in cols] for i in rows]
    pc = [[peer_costs[i][j] for j in cols] for i in rows]
    ea, pa = [ea[i] for i in rows], [pa[j] for j in cols]
    responses = [[i for i in range(len(ea)) if ec[i][j] == min(row[j] for row in ec)]
                 for j in range(len(pa))]
    if mode == 'minimax':
        i = min(range(len(ea)), key=lambda i: (max(ec[i]), ea[i]))
        j = min(range(len(pa)), key=lambda j: (-ec[i][j], pa[j]))
    else:
        j = min(range(len(pa)), key=lambda j: (max(pc[i][j] for i in responses[j]), pa[j]))
        i = min(responses[j], key=lambda i: (-pc[i][j], ea[i]))
    return dict(solver_mode=mode, ego_actions_mps2=ea, peer_actions_mps2=pa,
                ego_costs=ec, peer_costs=pc,
                ego_best_responses=[[ea[i] for i in indices] for indices in responses],
                model_selected_ego_mps2=ea[i], model_selected_peer_mps2=pa[j])


def _taper(acceleration, base, ego, p):
    acceleration = max(acceleration, -p['noa_stop_speed_gain_per_s']*ego.vx_mps-p['noa_stop_terminal_braking_mps2'])
    acceleration = clip(acceleration, -p['comfort_braking_mps2'], p['comfort_accel_mps2'])
    return min(base, clip(acceleration, p['min_accel_mps2'], p['max_accel_mps2']))


def select_waiting(control, assessment, gate, phase, base_accel, fixed_accel, parameters):
    """Select a local model request, without changing memory or running a guard."""
    p, e = parameters, control.ego
    mode = validate_parameters(p)
    result = dict(solver_mode=mode, assumptions=_ASSUMPTIONS,
                  selected_request_mps2=fixed_accel, base_request_mps2=base_accel,
                  fixed_request_mps2=fixed_accel, model_selected_ego_mps2=None,
                  model_selected_peer_mps2=None, fallback=True, fallback_reason=None,
                  eligibility_reason=None, executed=False)
    def fallback(reason):
        result['fallback_reason'] = reason
        result['eligibility_reason'] = reason
        return result
    if mode == 'fixed':
        return fallback('fixed_policy')
    if not gate.get('blocking', False):
        return fallback('gate_not_blocking')
    if phase == 'UNKNOWN':
        return fallback('unknown_phase')
    if assessment is None:
        return fallback('missing_assessment')
    if assessment.get('reason') not in _REASONS:
        return fallback('assessment_reason')
    signatures = assessment.get('participant_signatures', ())
    if len(signatures) != 1:
        return fallback('participant_count')
    current = [b for b in measured_bodies(control) if astuple(b) == signatures[0]]
    if len(current) != 1:
        return fallback('peer_not_current')
    peer = current[0]
    evx = e.vx_mps*math.cos(e.heading_rad)-e.vy_mps*math.sin(e.heading_rad)
    _number(evx, 'ego world velocity')
    _number(peer.vx, 'peer world velocity')
    if evx < 0 or peer.vx < 0:
        return fallback('negative_world_vx')
    _number(base_accel, 'base request')
    _number(fixed_accel, 'fixed request')
    actions = sorted({_taper(a, base_accel, e, p) for a in (base_accel, min(base_accel, 0.), fixed_accel)})
    s, horizon, vmax = p['r5_game_peer_accel_mps2'], p['r5_game_horizon_s'], p['max_speed_mps']
    peer_actions = sorted({clip(a, p['min_accel_mps2'], p['max_accel_mps2']) for a in (-s, 0., s)})
    own_half = (abs(math.cos(e.heading_rad))*p['length_m']+abs(math.sin(e.heading_rad))*p['width_m'])/2
    peer_half = (abs(math.cos(peer.heading))*peer.length+abs(math.sin(peer.heading))*peer.width)/2
    d = own_half+peer_half+2*p['noa_body_margin_m']+p['noa_standstill_gap_m']
    _number(d, 'desired separation')
    if d <= 0:
        raise ValueError('Waiting desired separation must be positive')
    target = p['noa_target_speed_mps']
    try:
        ec, pc = [], []
        for a in actions:
            erow, prow = [], []
            for b in peer_actions:
                ex = e.x_m+distance_at(evx, a, horizon, vmax)
                px = peer.x+distance_at(peer.vx, b, horizon, vmax)
                gap = _number(px-ex, 'predicted signed gap')
                q = max(0., (d-gap)/d)**2
                ve = clip(clip(evx, 0., vmax)+a*horizon, 0., vmax)
                vp = clip(clip(peer.vx, 0., vmax)+b*horizon, 0., vmax)
                erow.append(p['r5_game_gap_weight']*q+p['r5_game_speed_weight']*((ve-target)/5.)**2
                            +p['r5_game_effort_weight']*(a/.5)**2)
                prow.append(p['r5_game_gap_weight']*q+p['r5_game_speed_weight']*((vp-target)/5.)**2
                            +p['r5_game_effort_weight']*(b/.5)**2)
            ec.append(erow)
            pc.append(prow)
    except OverflowError as exc:
        raise ValueError('Nonfinite derived waiting-model value') from exc
    result.update(solve_matrix(mode, actions, peer_actions, ec, pc))
    result.update(selected_request_mps2=result['model_selected_ego_mps2'],
                  desired_separation_m=d, peer_signature=astuple(peer),
                  ego_world_vx_mps=evx, peer_world_vx_mps=peer.vx,
                  fallback=False, fallback_reason=None)
    return result
