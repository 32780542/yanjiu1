"""Build a balanced staggered target from one vehicle's visible segment."""
from dataclasses import dataclass
from functools import lru_cache
from itertools import accumulate, combinations

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
    released: bool = True
    incoming_front: int | None = None


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
    leading = first if lanes == 2 else 0
    if lanes == 2 and head_clipped and abs(source.count(0) - source.count(1)) >= 2:
        leading = 1 - first
    # A sensor may first intersect the second half of a layer. Remove only
    # that missing band from the template; no virtual car enters the matching.
    omitted = tuple(range(leading, lanes, 2)) if head_clipped and first != leading else ()
    tail = _tail_lanes(source, lanes, leading, omitted, lanes == 3 and not tail_clipped)
    layers = (len(group) + len(omitted)) // lanes
    return [(lane, spacing * (layer + .5 * (lane % 2 != leading)))
               for layer in range(layers + 1)
               for lane in (range(lanes) if layer < layers else tail)
               if layer or lane not in omitted]


def anchored_x(x, head_x, spacing, forward_anchor):
    """Fit the segment and the visible preceding tail with equal total weight."""
    return x + .5 * max(0., forward_anchor - spacing - head_x)


def _leading_lane(group):
    """Choose the mirror of a two-lane alternating sequence in this view."""
    n = len(group)
    lane0_count = sum(c.lane == 0 for c in group)
    if n % 2:
        # Put the extra slot on the more populated side to minimize crossings.
        return int(lane0_count <= n // 2)
    if 2 * lane0_count == n:
        # With neither lane changing its population, J1-J0 is spacing times
        # this first moment. A common origin cancels between the equal counts.
        head = group[0].x
        moment = sum((c.x - head) * (1 if c.lane == 0 else -1) for c in group)
        if abs(moment) > n * POSITION_ERROR_M:
            return int(moment < 0)
    return group[0].lane


def _open_road_allows(rank, group, slots, fit, opened, lanes):
    """Largest one-hop batch that fits the open part of an expanding road."""
    origin = group[rank].lane
    destination = slots[fit.assignment[rank]][0]
    if opened is None or destination == origin:
        return True
    if destination >= opened:
        return False
    if fit.max_crossings != 1:
        return True
    counts, goals = [0]*lanes, [0]*lanes
    for car, (lane, _) in zip(group, slots):
        counts[car.lane] += 1
        goals[lane] += 1
    flows = list(accumulate(current-goal for current,goal in zip(counts, goals)))[:-1]
    allowed = [abs(f) if k+1 < opened else 0 for k,f in enumerate(flows)]
    # Incoming moves on a through lane can use an existing target vacancy
    # or one freed by a permitted outgoing move in the same local plan.
    for k in reversed(range(len(flows)-1)):
        if flows[k] > 0 and flows[k+1] > 0:
            allowed[k] = min(allowed[k], max(0, goals[k+1]-counts[k+1]) + allowed[k+1])
    for k in range(1, len(flows)):
        if flows[k] < 0 and flows[k-1] < 0:
            allowed[k] = min(allowed[k], max(0, goals[k]-counts[k]) + allowed[k-1])
    edge = min(origin, destination)
    if allowed[edge] == abs(flows[edge]):
        return True
    pool = [i for i,j in enumerate(fit.assignment)
            if group[i].lane == origin and slots[j][0] == destination]
    pool.sort(key=lambda i: (abs(group[i].x - slots[fit.assignment[i]][1]), -group[i].x))
    return rank in pool[:allowed[edge]]


def _incoming_front(rank, group, assigned):
    """Index of the adjacent car that should fill the slot directly ahead of ego."""
    lane, x = assigned[rank]
    if lane != group[rank].lane:
        return None
    front = min((i for i, (column, position) in enumerate(assigned) if column == lane and position > x),
                key=lambda i: assigned[i][1], default=None)
    if front is not None and abs(group[front].lane - lane) == 1 and group[front].x >= group[rank].x:
        return front
    return None


def choose_target(rank, group, lanes, spacing, *, head_clipped=False, tail_clipped=False,
                  sensor_bounds=None, forward_anchor=None, opened_lanes=None, moved=(), receiving=False):
    offsets = None
    if lanes == 2 and all(c.lane < lanes for c in group):
        first = _leading_lane(group)
        offsets = [(first ^ (k % 2), spacing * (.5 * k)) for k in range(len(group))]
    elif (head_clipped or tail_clipped) and sensor_bounds is not None:
        offsets = _observed_offsets(group, lanes, spacing, 0, sensor_bounds)
    if offsets is None:
        offsets = _balanced_offsets(group, lanes, spacing, head_clipped, tail_clipped)
    origin = sum(c.x + d for c, (_, d) in zip(group, offsets)) / len(group)
    slots = [(lane, origin - d) for lane, d in offsets]
    fit = solve_transport([(c.lane, c.x) for c in group], slots,
                          ego_index=rank, action="next_lane", position_error=POSITION_ERROR_M, moved=moved)
    lane, x = slots[fit.assignment[rank]]
    front_offset = min(d for _, d in offsets)
    if forward_anchor is not None:
        x = anchored_x(x, origin - front_offset, spacing, forward_anchor)
    extent = max(d for _, d in offsets) - front_offset
    margin = 2 * len(group) * POSITION_ERROR_M * extent
    confirmed = fit.action_lower_bound > 0
    front = _incoming_front(rank, group, [slots[j] for j in fit.assignment]) if receiving else None
    return Target(lane, x, fit.ego_gap, fit.ego_gap > margin,
                  fit.action_gap, confirmed, confirmed and fit.action_gap <= margin,
                  _open_road_allows(rank, group, slots, fit, opened_lanes, lanes), front)
