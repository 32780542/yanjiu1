"""Offline sensitivity of the ego's next lane to relative longitudinal measurement errors.

The nominal lateral objectives, observed members and slot geometry are fixed.
Distances are in metres. An equally good changing action counts as a loss of uniqueness.
"""
from dataclasses import dataclass
from math import inf
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linear_sum_assignment, linprog, milp
from scipy.sparse import coo_array

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "variants/phase5g_pure_formation"))
from noa.transport import lane_bounds, solve_transport


def action_graph(vehicles, slots, ego):
    fit = solve_transport(vehicles, slots, ego_index=ego, action="next_lane")
    source = np.array([lane for lane, _ in vehicles])
    target = np.array([lane for lane, _ in slots])
    x = np.array([pos for _, pos in vehicles], dtype=float)
    y = np.array([pos for _, pos in slots], dtype=float)
    radius, _ = lane_bounds(source, target)
    distance = abs(source[:, None] - target)
    mask = distance <= radius
    for boundary in range(min(source.min(), target.min()), max(source.max(), target.max())):
        left = source <= boundary
        need = np.sum(left) - np.sum(target <= boundary)
        if need >= 0:
            mask &= ~(~left[:, None] & (target <= boundary))
        if need <= 0:
            mask &= ~(left[:, None] & (target > boundary))
    same = mask.copy()
    other = mask.copy()
    action = source[ego] + np.sign(target - source[ego])
    same[ego] &= action == fit.action_lane
    other[ego] &= action != fit.action_lane
    return x, y, np.array(fit.assignment), same, other, fit.action_gap


def best(cost, allowed):
    try:
        return linear_sum_assignment(np.where(allowed, cost, np.inf))[1]
    except ValueError:  # no perfect matching on this subgraph
        return None


def witness_competitor(x, y, chosen, other):
    """Smallest box in which a rival ties the particular nominal matching."""
    rows = np.arange(len(x))
    separation = y[chosen, None] - y
    change = (x - x.mean())[:, None] * separation
    slope = abs(separation)
    candidate = best(change, other)
    if candidate is None:
        return inf, None
    def ratio(p):
        denom = slope[rows,p].sum()
        return max(0., change[rows,p].sum() / denom) if denom else 0.
    value = ratio(candidate)
    active = candidate
    while value > 0:
        candidate = best(change - value*slope, other)
        improved = ratio(candidate)
        if improved >= value - 1e-11:
            break
        value, active = improved, candidate
    return value, active


def tie_radius(x, y, same, rival):
    """Distance to this rival beating the best same-action match, by LP separation."""
    n = len(x)
    d = np.zeros(n)
    cuts, rhs = [], []
    upper = np.ptp(x)/2
    while True:
        keeper = best(-(x+d)[:,None]*y, same)
        slope = y[keeper] - y[rival]
        gap = np.dot(x+d, slope)
        if gap <= 1e-8:
            return max(abs(d)), d
        cuts.append([*slope, 0.])
        rhs.append(-np.dot(x, slope))
        bounds = [[-upper,upper]]*n + [[0.,upper]]
        limits = np.column_stack((np.vstack((np.eye(n), -np.eye(n))), -np.ones(2*n)))
        res = linprog([0.]*n+[1.], A_ub=np.vstack((limits,cuts)),
                      b_ub=np.r_[np.zeros(2*n),rhs], bounds=bounds, method="highs")
        if not res.success:
            raise RuntimeError(res.message)
        d = res.x[:n]


@dataclass(frozen=True)
class Radius:
    lower_m: float
    upper_m: float
    perturbation: tuple
    converged: bool


def action_radius(x, y, chosen, same, other, gap, seconds=60.):
    """Closest perturbation at which any rival can equal or beat the *best* same-action match.

    An assignment dual bounds the best unchanged-action cost. Binary variables select
    a single changing-action assignment. Its products with position errors use the
    exact binary-product inequalities. An unfinished solve returns an interval.
    """
    n = len(x)
    if np.isinf(gap):
        return Radius(inf, inf, (), True)
    if gap == 0:
        return Radius(0., 0., (0.,) * n, True)
    x, y = x-x.mean(), y-y.mean()
    witness, rival_assignment = witness_competitor(x, y, chosen, other)
    rival_upper, rival_d = tie_radius(x, y, same, rival_assignment)
    if rival_upper <= witness + 1e-8:
        return Radius(min(witness,rival_upper), rival_upper, tuple(rival_d), True)
    scale = np.ptp(x) / 2
    x = (x - (x.max()+x.min())/2) / scale
    y = (y - (y.max()+y.min())/2) / (np.ptp(y)/2)
    # With every position at the midpoint, all lateral-feasible matches tie.
    edges = list(zip(*np.nonzero(other)))
    m = len(edges)
    delta = 0
    row_price, col_price = n, 2*n
    choice, product = 3*n, 3*n+m
    radius = 3*n+2*m
    nv = radius+1
    c = np.zeros(nv)
    c[radius] = 1.
    integrality = np.zeros(nv)
    integrality[choice:product] = 1
    lo, hi = np.full(nv, -np.inf), np.full(nv, np.inf)
    cap = min(1., rival_upper/scale + 1e-8)
    lo[:n], hi[:n] = -cap, cap
    lo[choice:product], hi[choice:product] = 0., 1.
    lo[product:radius], hi[product:radius] = -cap, cap
    lo[radius], hi[radius] = max(0.,witness/scale-1e-8), cap
    row_index, col_index, values, lhs, rhs = [], [], [], [], []
    def constraint(coeff, upper, lower=-inf):
        for col, value in coeff:
            row_index.append(len(rhs))
            col_index.append(col)
            values.append(value)
        lhs.append(lower)
        rhs.append(upper)
    for i in range(n):
        constraint([(delta+i, 1.), (radius, -1.)], 0.)
        constraint([(delta+i, -1.), (radius, -1.)], 0.)
        constraint([(choice+k, 1.) for k,(r,_) in enumerate(edges) if r == i], 1., 1.)
        constraint([(choice+k, 1.) for k,(_,t) in enumerate(edges) if t == i], 1., 1.)
        constraint([(product+k, 1.) for k,(r,_) in enumerate(edges) if r == i] +
                   [(delta+i,-1.)], 0., 0.)
    # If two admissibility rows coincide and their position intervals cannot
    # cross, an optimal rival assigns them slots in the same longitudinal order.
    for i in range(n):
        for j in range(n):
            if x[i]+2*cap < x[j] and np.array_equal(other[i], other[j]):
                ordered = [(choice+k, y[t]*(1. if r==i else -1.)) for k,(r,t) in enumerate(edges)
                           if r==i or r==j]
                constraint(ordered, 0.)
    for i, j in zip(*np.nonzero(same)):
        constraint([(row_price+i, 1.), (col_price+j, 1.), (delta+i, y[j])], -x[i]*y[j])
    rival = [(row_price+i,-1.) for i in range(n)] + [(col_price+j,-1.) for j in range(n)]
    for k, (i,j) in enumerate(edges):
        z, w = choice+k, product+k
        constraint([(w,1.),(z,-cap)], 0.)
        constraint([(w,-1.),(z,-cap)], 0.)
        constraint([(w,1.), (delta+i,-1.), (z,cap)], cap)
        constraint([(w,-1.), (delta+i,1.), (z,cap)], cap)
        rival.extend(((z,-x[i]*y[j]), (w,-y[j])))
    constraint(rival, 0.)
    matrix = coo_array((values, (row_index,col_index)), shape=(len(rhs),nv)).tocsc()
    res = milp(c, integrality=integrality, bounds=Bounds(lo, hi),
               constraints=LinearConstraint(matrix, lhs, rhs),
               options={"time_limit":seconds, "mip_rel_gap":1e-9})
    if res.status not in (0, 1):
        raise RuntimeError(res.message)
    lower = max(witness, scale * (getattr(res, "mip_dual_bound", None) or 0.))
    perturbation = rival_d/scale if res.x is None else res.x[:n]
    if max(abs(perturbation))*scale > rival_upper:
        perturbation = rival_d/scale
    upper = scale * max(abs(perturbation))
    # Independently check the solver's proposed adversarial example with two assignments.
    adverse = -(x+perturbation)[:, None] * y
    rows = np.arange(n)
    difference = adverse[rows,best(adverse,other)].sum() - adverse[rows,best(adverse,same)].sum()
    if difference > 2e-6:
        raise ArithmeticError(f"unverified adversarial example: normalized cost difference {difference}")
    return Radius(min(lower,upper), upper, tuple(scale*perturbation), res.status == 0)
