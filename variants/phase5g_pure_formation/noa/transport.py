"""Anonymous bijections between one observed group and one fixed slot geometry."""
from collections import Counter, deque
from dataclasses import dataclass
from functools import lru_cache
from math import fsum, gcd, inf, isfinite
from operator import index

from scipy.optimize import linear_sum_assignment


@dataclass(frozen=True, slots=True)
class TransportResult:
    assignment: tuple[int, ...]
    max_crossings: int
    total_crossings: int
    squared_displacement: float
    ego_gap: float | None
    action_lane: int | None = None
    action_gap: float | None = None
    action_lower_bound: float | None = None


def lane_bounds(source_lanes, target_lanes):
    """Return the simultaneous bottleneck and total minima on an integer lane path.

    Pairing the kth ordered source lane with the kth ordered destination
    attains both. For any radius r, this pairing stays within r exactly when a
    perfect matching within r exists (uncrossing cannot increase the maximum).
    In particular, max_crossings <= 1 characterizes a static one-hop allocation.
    """
    if len(source_lanes) != len(target_lanes):
        raise ValueError("lane populations must have equal size")
    distances = [abs(a - b) for a, b in zip(sorted(map(index, source_lanes)),
                                            sorted(map(index, target_lanes)))]
    return max(distances, default=0), sum(distances)


@lru_cache(maxsize=256)
def _lane_constraints(source, target, history=()):
    """Cache only lane counts/order geometry, never another observer's assignment."""
    bottleneck, total = lane_bounds(source, target)
    imbalance = Counter(source)
    imbalance.subtract(target)
    # Across each cut, the prefix imbalance fixes the net crossing flow.
    # Minimum total distance allows only that direction, and none at zero flow.
    # Summing the signed cut lengths gives a potential. Its increase on
    # an edge equals the edge length iff every traversed cut is admissible.
    potential = {}
    level = flow = 0
    previous = min(imbalance)
    for lane in sorted(imbalance):
        level += (lane - previous) * ((flow > 0) - (flow < 0))
        potential[lane] = level
        flow += imbalance[lane]
        previous = lane
    direction_ok = [[abs(a-b) == potential[b]-potential[a] for b in target] for a in source]
    def excluded(radius):
        return [[not allowed or abs(a-b)+(history[i] if history else 0)>radius
                 for b, allowed in zip(target,directions)]
                for i,(a,directions) in enumerate(zip(source,direction_ok))]
    if history:
        low, high = max(bottleneck,max(history)), bottleneck+max(history)
        while low < high:
            trial = (low+high)//2
            banned = excluded(trial)
            order = linear_sum_assignment(banned)[1]
            if any(banned[i][j] for i,j in enumerate(order)):
                low = trial+1
            else:
                high = trial
        bottleneck = low
    forbidden = excluded(bottleneck)
    return bottleneck, total, forbidden


def _integer_positions(values):
    """Express the supplied binary floats as origin + integer * step / denominator."""
    ratios = [v.as_integer_ratio() for v in values]
    denominator = max(d for _, d in ratios)  # all denominators are powers of two
    coords = [a * (denominator // d) for a, d in ratios]
    origin = min(coords)
    coords = [a - origin for a in coords]
    step = gcd(*coords) or 1
    return [a // step for a in coords], step, denominator


def _assignment(cost, penalty):
    n = len(cost)
    shift = max(0, (n * penalty).bit_length() - 49)
    approximate = [[value >> shift for value in row] for row in cost] if shift else cost
    chosen = linear_sum_assignment(approximate)[1].tolist()
    # All reduced costs and path-length updates fit exactly in a double if no
    # bits were discarded. Otherwise verify the candidate with integer prices.
    if not shift or _certified(cost, chosen):
        return chosen
    # Shortest augmenting path Hungarian algorithm in exact integer arithmetic.
    # Index 0 is the dummy column attached to the next unmatched row.
    row_dual = [0] * (n + 1)
    col_dual = [0] * (n + 1)
    matched = [0] * (n + 1)
    parent = [0] * (n + 1)
    for row in range(1, n + 1):
        matched[0] = row
        col = 0
        used = [False] * (n + 1)
        slack = [None] * (n + 1)
        while matched[col]:
            used[col] = True
            i = matched[col]
            delta = None
            for j, value in enumerate(cost[i-1], 1):
                if used[j]:
                    continue
                reduced = value - row_dual[i] - col_dual[j]
                if slack[j] is None or reduced < slack[j]:
                    slack[j], parent[j] = reduced, col
                if delta is None or slack[j] < delta:
                    delta, next_col = slack[j], j
            for j in range(n + 1):
                if used[j]:
                    row_dual[matched[j]] += delta
                    col_dual[j] -= delta
                else:
                    slack[j] -= delta
            col = next_col
        while col:
            previous = parent[col]
            matched[col] = matched[previous]
            col = previous
    result = [0] * n
    for j, row in enumerate(matched[1:]):
        result[row-1] = j
    return result


def _certified(cost, chosen):
    """A matching is optimal iff its alternating residual graph has no negative cycle."""
    n = len(chosen)
    owner = [0] * n
    for row, col in enumerate(chosen):
        owner[col] = row
    queue = deque(range(n))
    queued = [True] * n
    price, hops = [0] * n, [0] * n
    while queue:
        col = queue.popleft()
        queued[col] = False
        row = cost[owner[col]]
        base = price[col] - row[col]
        for j, value in enumerate(row):
            updated = base + value
            if updated < price[j]:
                price[j] = updated
                hops[j] = hops[col] + 1
                if hops[j] >= n:
                    return False
                if not queued[j]:
                    queue.append(j)
                    queued[j] = True
    return True


def _box_difference(chosen, allowed, xx, yy, x_unit, error):
    """Minimum adversarial cost difference to a different action in integer units."""
    # The two permutations cancel the x^2 and y^2 terms. Relative to a fixed
    # witness edge, minimizing over each car's perturbation contributes
    # -error*abs(dy). Forbid all ego slots sharing the witness's action.
    weights = []
    for i, a in enumerate(chosen):
        delta = (yy[a] - y for y in yy)
        weights.append([xx[i]*x_unit*d - error*abs(d) for d in delta])
    low = min(map(min, weights))
    penalty = len(chosen)*(max(map(max, weights))-low) + 1
    costs = [[v-low if ok else penalty for v,ok in zip(row,mask)] for row,mask in zip(weights,allowed)]
    alternative = _assignment(costs, penalty)
    return sum(weights[i][j] for i,j in enumerate(alternative))


def solve_transport(vehicles, slots, *, ego_index=None, action=None, position_error=None, history=()):
    """Minimize (max crossings, total crossings, sum squared longitudinal moves).

    Each row is (lane, x) in the same longitudinal frame. Assignment entries
    refer to caller slot indices. The optional gap forbids only the selected
    ego edge and keeps both lateral minima fixed. Its unit is squared metres,
    with zero for an equally good alternative and infinity for no alternative.
    With action="target_lane", action_gap forbids every ego slot on its chosen
    final lane. With action="next_lane", it forbids every slot requiring the
    same first adjacent lane (including staying). action_lane gives the
    corresponding physical lane index. ego_gap always retains its slot meaning.
    For independent vehicle-position errors bounded by position_error metres
    and fixed slots, a positive action_lower_bound certifies the action. A
    proposed lane move with a nonpositive coarse bound gets one extra solve
    for the worst competing action against the selected nominal permutation.
    The certificate is conditional on this specific observed group and slot set.
    """
    n = len(vehicles)
    if not n or n != len(slots):
        raise ValueError("expected equally many nonempty vehicle and slot rows")
    if ego_index is not None and not 0 <= index(ego_index) < n:
        raise IndexError("ego_index outside vehicles")
    if action is not None and (action not in ("target_lane", "next_lane") or ego_index is None):
        raise ValueError("an action certificate requires an ego_index and target_lane or next_lane")
    if position_error is not None:
        position_error = float(position_error)
        if action is None or not isfinite(position_error) or position_error < 0:
            raise ValueError("position_error requires an action and a finite nonnegative error bound")
    car_order = sorted(range(n), key=vehicles.__getitem__)
    slot_order = sorted(range(n), key=slots.__getitem__)
    source = tuple(index(vehicles[i][0]) for i in car_order)
    target = tuple(index(slots[j][0]) for j in slot_order)
    used = tuple(history[i] for i in car_order) if any(history) else ()
    x = [float(vehicles[i][1]) for i in car_order]
    y = [float(slots[j][1]) for j in slot_order]
    if not all(map(isfinite, x)) or not all(map(isfinite, y)):
        raise ValueError("positions must be finite")
    if source == target:
        # With zero crossings each lane is independent. An ordered pairing
        # minimizes squared travel. The cheapest way to displace the ego is
        # to swap it with an adjacent rank on the same lane.
        assignment = [0] * n
        for i, j in zip(car_order, slot_order):
            assignment[i] = j
        squared = fsum((a - b) ** 2 for a, b in zip(x, y))
        gap = action_lane = action_gap = None
        if ego_index is not None:
            row = car_order.index(ego_index)
            gap = min((2 * (x[j] - x[row]) * (y[j] - y[row]) for j in (row - 1, row + 1)
                       if 0 <= j < n and source[j] == source[row]), default=inf)
            if action is not None:
                action_lane, action_gap = source[row], inf
        return TransportResult(tuple(assignment), max(used, default=0), 0, squared, gap, action_lane, action_gap,
                               inf if position_error is not None else None)
    bottleneck, total, forbidden = _lane_constraints(source, target, used)

    # In a bijection, sum(x^2 + y^2) is constant. Centering x and y separately
    # also adds only a constant, avoiding cancellation from a distant road origin.
    xx, xstep, xden = _integer_positions(x)
    yy, ystep, yden = _integer_positions(y)
    xmax = max(xx)
    # The cost of any permissible perfect matching is strictly below penalty.
    penalty = n * xmax * max(yy) + 1
    costs = [[penalty if blocked else (xmax - a) * b for b, blocked in zip(yy, mask)]
             for a, mask in zip(xx, forbidden)]
    chosen = _assignment(costs, penalty)
    assignment = [0] * n
    for i, j in enumerate(chosen):
        assignment[car_order[i]] = slot_order[j]
    squared = fsum((x[i] - y[j]) ** 2 for i, j in enumerate(chosen))

    gap = action_gap = action_lane = lower = None
    if ego_index is not None:
        row = car_order.index(ego_index)

        def alternative_difference():
            if all(cost == penalty for cost in costs[row]):
                return None, None
            alternative = _assignment(costs, penalty)
            if any(costs[i][j] == penalty for i, j in enumerate(alternative)):
                return None, None
            diff = sum(xx[i] * (yy[a] - yy[b]) for i, (a, b) in enumerate(zip(chosen, alternative)))
            return diff, alternative[row]

        costs[row][chosen[row]] = penalty
        diff, other_slot = alternative_difference()
        gap = inf if diff is None else (2 * diff * xstep * ystep) / (xden * yden)
        if action is not None:
            origin = source[row]
            lanes = target if action == "target_lane" else [
                origin + (lane > origin) - (lane < origin) for lane in target]
            action_lane = lanes[chosen[row]]
            action_gap = gap
            # If the cheapest alternative already changes the action, its gap
            # is exact for both questions. Otherwise exclude the rest of the
            # same-action slots and solve only for this ego again.
            if other_slot is not None and lanes[other_slot] == action_lane:
                for j, lane in enumerate(lanes):
                    if lane == action_lane:
                        costs[row][j] = penalty
                diff, _ = alternative_difference()
                action_gap = inf if diff is None else (2 * diff * xstep * ystep) / (xden * yden)
            if position_error is not None:
                lower = inf
                if diff is not None:
                    numerator, denominator = position_error.as_integer_ratio()
                    scale = max(xden,denominator)
                    x_unit = xstep*(scale//xden)
                    error = numerator*(scale//denominator)
                    difference = diff*x_unit - n*error*max(yy)
                    if action_lane != origin and difference <= 0 and error:
                        allowed = [[not block for block in mask] for mask in forbidden]
                        allowed[row] = [ok and lane != action_lane for ok,lane in zip(allowed[row],lanes)]
                        difference = _box_difference(chosen,allowed,xx,yy,x_unit,error)
                    lower = (2*difference*ystep)/(scale*yden)
    return TransportResult(tuple(assignment), bottleneck, total, squared, gap, action_lane, action_gap, lower)
