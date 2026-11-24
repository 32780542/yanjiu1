"""Build a balanced staggered target from one vehicle's visible segment."""
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

from noa.transport import lane_bounds, solve_transport


# A 5 cm relative longitudinal measurement perturbation, for fixed members,
# lane observations and spacing. A common change of origin cancels.
POSITION_ERROR_M = 0.05


@dataclass(frozen=True, slots=True)
class Target:
    lane: int
    x: float
    gap: float
    certified: bool
    step_gap: float
    step_certified: bool
    refined: bool


@lru_cache(maxsize=256)
def _tail_lanes(source, lanes, lead_phase, omitted, strict_tail):
    """Choose the occupied lanes of the last, incomplete staggered layer."""
    layers, tail = divmod(len(source) + len(omitted), lanes)
    profiles = combinations(range(lanes), tail)
    def key(extra):
        outside = sum(k % 2 == lead_phase for k in extra)
        targets = list(range(lanes)) * layers + list(extra)
        for lane in omitted:
            if lane not in targets:
                return (1, 0, 0, 0, extra)
            targets.remove(lane)
        # A three-lane tail fills the two outer positions first. Elsewhere
        # either phase can end the layer, so preserve occupied lanes first.
        return (-outside if strict_tail else 0, *lane_bounds(source, targets), -outside, extra)
    return min(profiles, key=key)


def _observed_offsets(group, lanes, spacing, lead_phase, bounds):
    """Can these occupied cells be the visible part of a legal staggered lattice?"""
    rear, front = bounds
    anchor = group[0]
    anchor_phase = .5 * (anchor.lane % 2 != lead_phase)
    cells, offsets = set(), []
    for car in group:
        if car.lane >= lanes:
            return None
        phase = .5 * (car.lane % 2 != lead_phase)
        layer = round((anchor.x - car.x) / spacing + anchor_phase - phase)
        if (layer, car.lane) in cells:
            return None
        cells.add((layer, car.lane))
        offsets.append((car.lane, spacing * (layer + phase)))
    origins = [c.x + offset for c, (_, offset) in zip(group, offsets)]
    error = POSITION_ERROR_M
    low, high = max(origins) - error, min(origins) + error
    if low > high or front - rear <= 4 * error:
        return None
    first, last = min(r for r, _ in cells), max(r for r, _ in cells)
    if last - first < 2:
        return None
    # Only a real last layer may be incomplete. In a complete layer a
    # missing car is compatible with this view only at/over a sensor edge.
    lower_open, upper_open = float("-inf"), float("inf")
    for layer in range(first, last + 1):
        for lane in range(lanes):
            if (layer, lane) in cells:
                continue
            if layer == last and not (lanes == 3 and (last, 1) in cells and lane != 1):
                continue
            offset = spacing * (layer + .5 * (lane % 2 != lead_phase))
            if high > front + offset - error:
                lower_open = max(lower_open, front + offset - error)
            elif low < rear + offset + error:
                upper_open = min(upper_open, rear + offset + error)
            else:
                return None
    if high <= lower_open or low >= upper_open or lower_open >= upper_open:
        return None
    return offsets


def _balanced_offsets(group, lanes, spacing, head_clipped, tail_clipped):
    source = tuple(sorted(c.lane for c in group))
    first = min(group[0].lane, lanes - 1) % 2
    lead_phase = first if lanes == 2 else 0
    if lanes == 2 and head_clipped and abs(source.count(0) - source.count(1)) >= 2:
        lead_phase = 1 - first
    # A sensor may first intersect the second half of a layer. Remove only
    # that missing band from the template; no virtual car enters the matching.
    omitted = tuple(range(lead_phase, lanes, 2)) if head_clipped and first != lead_phase else ()
    tail = _tail_lanes(source, lanes, lead_phase, omitted, lanes == 3 and not tail_clipped)
    layers = (len(group) + len(omitted)) // lanes
    return [(lane, spacing * (layer + .5 * (lane % 2 != lead_phase)))
               for layer in range(layers + 1)
               for lane in (range(lanes) if layer < layers else tail)
               if layer or lane not in omitted]


def anchored_x(x, head_x, spacing, forward_anchor):
    """Fit the segment and the visible preceding tail with equal total weight."""
    return x + .5 * max(0., forward_anchor - spacing - head_x)


def choose_target(rank, group, lanes, spacing, *, head_clipped=False, tail_clipped=False,
                  sensor_bounds=None, forward_anchor=None):
    offsets = None
    if (head_clipped or tail_clipped) and sensor_bounds is not None:
        offsets = _observed_offsets(group, lanes, spacing, 0, sensor_bounds)
        if lanes == 2 and offsets is None:
            offsets = _observed_offsets(group, lanes, spacing, 1, sensor_bounds)
    if offsets is None:
        offsets = _balanced_offsets(group, lanes, spacing, head_clipped, tail_clipped)
    origin = sum(c.x + d for c, (_, d) in zip(group, offsets)) / len(group)
    slots = [(lane, origin - d) for lane, d in offsets]
    fit = solve_transport([(c.lane, c.x) for c in group], slots,
                          ego_index=rank, action="next_lane", position_error=POSITION_ERROR_M)
    lane, x = slots[fit.assignment[rank]]
    front_offset = min(d for _, d in offsets)
    if forward_anchor is not None:
        x = anchored_x(x, origin - front_offset, spacing, forward_anchor)
    extent = max(d for _, d in offsets) - front_offset
    margin = 2 * len(group) * POSITION_ERROR_M * extent
    confirmed = fit.action_lower_bound > 0
    return Target(lane, x, fit.ego_gap, fit.ego_gap > margin,
                  fit.action_gap, confirmed, confirmed and fit.action_gap <= margin)
