"""Small exact boundary-certificate experiment. Each box uses one integer length unit.

A completion specifies anonymous (lane, lower_x, upper_x) rows and (lane, y)
slots expressed relative to the same identified template anchor. Slot identity
is (lane, y). The example has a visible head and at most one hidden rear car.
That bound is an explicit experimental assumption, not inferred from visibility.
"""
from functools import lru_cache
from itertools import permutations, product
import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path
from random import Random
from statistics import median
import sys
from time import perf_counter_ns
import xml.etree.ElementTree as ET

from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"))
from noa.transport import solve_transport


@lru_cache(maxsize=256)
def lateral_optima(lanes, targets):
    """Exhaustively construct the common optimum set for both lateral criteria."""
    candidates = []
    for p in permutations(range(len(lanes))):
        d = [abs(lane - targets[j]) for lane, j in zip(lanes, p)]
        candidates.append(((max(d), sum(d)), p))
    best = min(c for c, _ in candidates)
    return tuple(p for c, p in candidates if c == best)


def label(slot, origin, action):
    if action is None:
        return slot
    if action == "target_lane":
        return slot[0]
    if action == "next_lane":
        return max(origin-1, min(origin+1, slot[0]))
    raise ValueError("unknown action")


def large_completion(rows, slots, ego, action=None):
    """Two assignments for the same robust bound on larger trace windows."""
    nominal = solve_transport([(lane,(lo+hi)/2) for lane,lo,hi in rows], slots)
    witness = nominal.assignment
    labels = [label(s, rows[ego][0], action) for s in slots]
    target = labels[witness[ego]]
    costs = []
    for i, (_, lo, hi) in enumerate(rows):
        diffs = (slots[witness[i]][1] - y for _, y in slots)
        costs.append([2*d*(lo if d >= 0 else hi) for d in diffs])
    # Exact bounded integer priorities. An extra lane step costs more than
    # any possible difference in longitudinal cost; a banned edge costs more
    # than every assignment using only permitted edges.
    n = len(rows)
    minimum = min(map(min, costs))
    step = n*(max(map(max, costs)) - minimum) + 1
    forbidden = (n*nominal.max_crossings + 1)*step
    if n*forbidden >= 2**49:
        raise ValueError("integer cost bounds exceed this trace check's precision")
    weights = []
    for i, (lane, _, _) in enumerate(rows):
        row = []
        for j, (dst, _) in enumerate(slots):
            d = abs(lane-dst)
            row.append(forbidden if d > nominal.max_crossings or (i == ego and labels[j] == target)
                       else d*step + costs[i][j] - minimum)
        weights.append(row)
    _, p = linear_sum_assignment(weights)
    valid = all(weights[i][j] < forbidden for i, j in enumerate(p))
    hops = sum(abs(rows[i][0]-slots[j][0]) for i, j in enumerate(p))
    margin = sum(costs[i][j] for i, j in enumerate(p)) if valid and hops == nominal.total_crossings else math.inf
    return target, margin


def boundary_certificate(completions, ego=0, action=None):
    """Return (physical slot or action lane, lower margin) or (None, None).

    Each continuous position box uses its own nominal witness. All discrete
    completions must preserve the same ego slot. Exhaustive search here is
    intended for small experiments; the separable robust costs also form a
    usual assignment problem on the lateral-optimal graph.
    """
    if not completions:
        raise ValueError("empty family of boundary completions")
    shared = None
    weakest = math.inf
    for rows, slots in completions:
        if len(rows) != len(slots) or not rows or any(lo > hi for _, lo, hi in rows):
            raise ValueError("invalid completion")
        if len(set(slots)) != len(slots):
            raise ValueError("duplicate physical slot")
        if len(rows) > 6:
            target, lower = large_completion(rows, slots, ego, action)
            if lower <= 0 or (shared is not None and target != shared):
                return None, None
            shared, weakest = target, min(weakest, lower)
            continue
        allowed = lateral_optima(tuple(lane for lane, _, _ in rows),
                                 tuple(lane for lane, _ in slots))
        y = [pos for _, pos in slots]
        witness = max(allowed, key=lambda p: sum((lo + hi) * y[j]
                                                for (_, lo, hi), j in zip(rows, p)))
        labels = [label(s, rows[ego][0], action) for s in slots]
        target = labels[witness[ego]]
        if shared is not None and target != shared:
            return None, None
        shared = target
        for p in allowed:
            if labels[p[ego]] == target:
                continue
            # min of 2*x_i*(y_w-y_p) on the physical position interval.
            diffs = (y[j] - y[k] for j, k in zip(witness, p))
            lower = sum(2 * d * (lo if d >= 0 else hi)
                        for (_, lo, hi), d in zip(rows, diffs))
            if lower <= 0:
                return None, None
            weakest = min(weakest, lower)
    return shared, weakest


def physical_optimal_targets(rows, slots, ego=0):
    """Separate point oracle on actual physical coordinates, including all ties."""
    best, targets = None, set()
    for p in permutations(range(len(rows))):
        d = [abs(lane - slots[j][0]) for (lane, _), j in zip(rows, p)]
        squared = sum((x - slots[j][1])**2 for (_, x), j in zip(rows, p))
        objective = max(d), sum(d), squared
        if best is None or objective < best:
            best, targets = objective, {slots[p[ego]]}
        elif objective == best:
            targets.add(slots[p[ego]])
    return targets


def slots_for(n):
    return tuple((j % 2, -15*j) for j in range(n))


def check(action=None):
    rng = Random(1125)
    windows = certified = tests = covered_tests = ambiguous = 0
    margins, timings = [], []
    # All two-lane assignments for three observed heads, with +/-2 m range
    # errors per car and a possible unseen tail of either lane in [-123,-104].
    for observed_x, lanes in product(((0,-30,-60,-90), (0,-18,-51,-82), (0,-37,-69,-94)),
                                     product(range(2), repeat=4)):
        observed = [(lane, x-2, x+2) for lane, x in zip(lanes, observed_x)]
        completions = [(observed, slots_for(4))] + [
            (observed + [(lane,-123,-104)], slots_for(5)) for lane in range(2)]
        start = perf_counter_ns()
        target, margin = boundary_certificate(completions, action=action)
        timings.append((perf_counter_ns()-start)/1000)
        windows += 1
        certified += int(target is not None)
        if margin is not None and math.isfinite(margin):
            margins.append(margin)
        seen = set()
        for rows, slots in completions:
            points = list(product(*[(lo, hi) for _, lo, hi in rows]))
            points += [tuple(rng.randint(lo, hi) for _, lo, hi in rows) for _ in range(8)]
            for point in points:
                actual_slots = physical_optimal_targets([(lane, x) for (lane, _, _), x in zip(rows, point)], slots)
                actual = {label(s, rows[0][0], action) for s in actual_slots}
                seen.update(actual)
                if target is not None:
                    assert actual == {target}, (rows, slots, point, target, actual)
                    covered_tests += 1
                tests += 1
            # Cross-check the scalable integer-weight implementation on these
            # smaller boxes independently of the full physical point oracle.
            # Distinct nominal permutations can protect the same ego edge with
            # different margins. Compare using the very same witness.
            witness = solve_transport([(k,(lo+hi)/2) for k,lo,hi in rows], slots).assignment
            allowed = lateral_optima(tuple(row[0] for row in rows), tuple(slot[0] for slot in slots))
            lowest = math.inf
            labels = [label(s, rows[0][0], action) for s in slots]
            for p in allowed:
                if labels[p[0]] != labels[witness[0]]:
                    d = [slots[a][1] - slots[b][1] for a,b in zip(witness,p)]
                    lowest = min(lowest, sum(min(2*lo*z, 2*hi*z) for (_,lo,hi),z in zip(rows,d)))
            fast_target, fast_margin = large_completion(rows, slots, 0, action)
            assert (fast_target, fast_margin) == (labels[witness[0]], lowest)
        ambiguous += int(len(seen) > 1)
    observed = [(1,0),(1,-30),(0,-60),(0,-90)]
    assert physical_optimal_targets(observed, slots_for(4)) == {(1,-15)}
    assert physical_optimal_targets(observed + [(1,-115)], slots_for(5)) == {(0,0)}
    # Two admissible shapes make distinct destinations optimal, both one step right.
    rows = [(0,-1,1),(0,9,11)]
    shapes = [(rows, [(1,0),(2,10)]), (rows, [(1,10),(2,0)])]
    assert boundary_certificate(shapes) == (None, None)
    assert boundary_certificate(shapes, action="target_lane") == (None, None)
    assert boundary_certificate(shapes, action="next_lane") == (1, math.inf)
    return dict(action=action or "slot", windows=windows, certified=certified, rejected=windows-certified,
                ambiguity_observed=ambiguous, unclassified=windows-certified-ambiguous,
                physical_point_checks=tests, checks_on_certified_windows=covered_tests,
                certified_point_disagreements=0, smallest_finite_margin_m2=min(margins),
                median_certificate_microseconds=round(median(timings), 1))


def trace_check(path, action=None):
    """Offline comparator with a common visible head and fixed stagger phase."""
    net = ET.parse(path.parent / "native.net.xml")
    upstream = net.findall("./edge[@id='upstream']/lane")
    downstream = net.findall("./edge[@id='downstream']/lane")
    cut = float(upstream[0].get("length"))
    counts = Counter(dict.fromkeys(("head_visible_tail_truncated", "both_unique",
                                    "both_unique_but_disagree", "tail_inside_model",
                                    "certified", "rejected_known_disagreement"), 0))
    timings = []
    with gzip.open(path, "rt") as stream:
        for line in stream:
            frame = json.loads(line)
            states = list(frame["states"].values())
            if abs(frame["time_s"] - round(frame["time_s"])) > 1e-6 or len(states) != 12:
                continue
            region = [s[0] >= cut for s in states]
            if len(set(region)) != 1:
                continue
            lanes = len(downstream if region[0] else upstream)
            if any(abs(s[1] - (round(s[1]/3.3-.5)+.5)*3.3) > .3 for s in states):
                continue
            cars = sorted(((round(s[1]/3.3-.5), s[0]) for s in states), key=lambda v: -v[1])
            if any(x-y > 50 for (_, x), (_, y) in zip(cars, cars[1:])):
                continue
            # Coordinates in centimetres. For a fixed positive lattice spacing,
            # a common fitted origin has no effect on assignment ranking.
            order = sorted(range(lanes), key=lambda k: (k % 2, k))
            slots = [(order[j % lanes], -3000*(j//lanes)-1500*(order[j % lanes] % 2)) for j in range(12)]
            for i, (_, x) in enumerate(cars):
                world = [(lane, (pos-x)*100) for lane, pos in cars]
                visible = [(k,pos) for k,pos in world if -10000 <= pos <= 20000]
                if len(visible) == 12 or world[0][1] > 20000:
                    continue
                counts["head_visible_tail_truncated"] += 1
                m = len(visible)
                full = solve_transport(world, slots, ego_index=i, action=action)
                local = solve_transport(visible, slots[:m], ego_index=i, action=action)
                true_target = label(slots[full.assignment[i]], world[i][0], action)
                local_target = label(slots[local.assignment[i]], world[i][0], action)
                both_unique = ((full.ego_gap > 0 and local.ego_gap > 0) if action is None else
                               (full.action_gap > 0 and local.action_gap > 0))
                if both_unique:
                    counts["both_unique"] += 1
                    if true_target != local_target:
                        counts["both_unique_but_disagree"] += 1
                if m != 11 or world[-1][1] < -15000:
                    continue
                counts["tail_inside_model"] += 1
                rows = [(lane,math.floor(pos)-25,math.ceil(pos)+25) for lane,pos in visible]
                family = [(rows, slots[:m])] + [(rows + [(k,-15000,-10000)], slots) for k in range(lanes)]
                start = perf_counter_ns()
                target, _ = boundary_certificate(family, i, action)
                timings.append((perf_counter_ns()-start)/1000)
                if target is not None:
                    counts["certified"] += 1
                    assert both_unique and target == true_target
                elif both_unique and true_target != local_target:
                    counts["rejected_known_disagreement"] += 1
    return dict(trace=str(path), action=action or "slot", **counts,
                median_certificate_us=round(median(timings), 1) if timings else None)


def action_windows():
    """All lane patterns for an interior observer approaching a 3->2 or 4->3 drop."""
    results = []
    rng = Random(1125)
    ego = 1
    centers = (42,0,-43,-89)
    for before, after in ((3,2),(4,3)):
        phases = sorted(range(after), key=lambda k: (k%2,k))
        slots = [(phases[j%after], -30*(j//after)-15*(phases[j%after]%2)) for j in range(5)]
        counts = Counter()
        for lanes in product(range(before), repeat=4):
            rows = [(l,x-2,x+2) for l,x in zip(lanes,centers)]
            family = [(rows,slots[:4])] + [(rows+[(l,-125,-101)],slots) for l in range(before)]
            certificates = {}
            for action in (None, "target_lane", "next_lane"):
                target, _ = boundary_certificate(family, ego, action)
                if target is not None:
                    counts[action or "slot"] += 1
                    certificates[action] = target
            for case, geometry in family:
                # Independently evaluate the original physical quadratic objective
                # over every permutation at these five predeclared point types.
                points = [[lo for _,lo,hi in case], [hi for _,lo,hi in case],
                          [(lo+hi)//2 for _,lo,hi in case]]
                points += [[rng.randint(lo,hi) for _,lo,hi in case] for _ in range(2)]
                for point in points:
                    all_slots = physical_optimal_targets([(l,x) for (l,_,_),x in zip(case,point)], geometry, ego)
                    for action, target in certificates.items():
                        assert {label(s,lanes[ego],action) for s in all_slots} == {target}
                        counts["certified_point_comparisons"] += 1
                    counts["physical_points"] += 1
            counts["windows"] += 1
        results.append(dict(before=before, after=after, **counts))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, nargs="+", help="fixed 12-car positions.jsonl.gz files")
    parser.add_argument("--action", choices=("target_lane", "next_lane"), help="group physical slots by lane action")
    parser.add_argument("--action-windows", action="store_true", help="compare all three certificates for lane drops")
    args = parser.parse_args()
    if args.action_windows:
        result = action_windows()
    elif args.trace:
        result = [trace_check(path, args.action) for path in args.trace]
    else:
        result = check(args.action)
    print(json.dumps(result, indent=2))
