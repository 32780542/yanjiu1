"""Run directly with Python. Enumerate small static problems without a simulator."""
import itertools as it
import json
import math
from collections import Counter
from pathlib import Path
from random import Random
from statistics import median
import sys
from time import perf_counter_ns

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"))
from noa.transport import lane_bounds, solve_transport


def check_paths():
    scenes = permutations = one_hop = 0
    for lanes in (2, 3, 4):
        for size in range(1, 6):
            orders = list(it.permutations(range(size)))
            populations = list(it.combinations_with_replacement(range(lanes), size))
            for a, b in it.product(populations, repeat=2):
                actual = []
                for order in orders:
                    moves = [abs(x - b[j]) for x, j in zip(a, order)]
                    actual.append((max(moves), sum(moves)))
                feasible = any(maximum <= 1 for maximum, _ in actual)
                best = min(actual)
                # Compute the independent earth mover cut lower bound.
                cuts = sum(abs(sum(x <= k for x in a) - sum(x <= k for x in b))
                           for k in range(lanes - 1))
                # The prefix inequalities are equivalent to sorted distance <= 1.
                prefix_ok = all(sum(x <= k for x in left) <= sum(x <= k + 1 for x in right)
                                for k in range(lanes) for left, right in ((a, b), (b, a)))
                assert best == lane_bounds(a, b), (a, b, best)
                assert best[1] == cuts == min(total for _, total in actual), (a, b, cuts)
                assert feasible == prefix_ok == (best[0] <= 1), (a, b)
                scenes += 1
                permutations += len(orders)
                one_hop += int(feasible)
    return dict(population_pairs=scenes, permutations=permutations, one_hop_feasible=one_hop)


def check_local_geometry():
    types = list(it.product(range(2), (0., 1.)))
    scenes = permutations = finite = equal = forced = 0
    for n in range(1, 5):
        orders = list(it.permutations(range(n)))
        geometries = list(it.combinations_with_replacement(types, n))
        for cars, slots in it.product(geometries, repeat=2):
            enumerated = []
            for p in orders:
                moves = [abs(lane - slots[j][0]) for (lane, _), j in zip(cars, p)]
                dx2 = sum((x - slots[j][1])**2 for (_, x), j in zip(cars, p))
                enumerated.append(((max(moves), sum(moves), dx2), p))
            optimum = min(cost for cost, _ in enumerated)
            optimal_permutations = {p for cost, p in enumerated if cost == optimum}
            for i in range(n):
                result = solve_transport(cars, slots, ego_index=i)
                assert result.assignment in optimal_permutations
                assert (result.max_crossings, result.total_crossings,
                        result.squared_displacement) == optimum
                alternative = min((cost[2] for cost, p in enumerated
                                   if p[i] != result.assignment[i] and cost[:2] == optimum[:2]),
                                  default=math.inf)
                gap = alternative - optimum[2]
                assert result.ego_gap == gap, (cars, slots, i, gap, result)
                equal += int(gap == 0)
                finite += int(0 < gap < math.inf)
                forced += int(gap == math.inf)
            permutations += len(orders)
            scenes += 1
    return dict(geometry_pairs=scenes, permutations=permutations,
                ego_tied=equal, ego_finite_positive=finite, ego_forced=forced)


def check_perturbations():
    # Every sign corner of separate car and slot perturbations in three scenes.
    eps = 1/32
    tested = preserved = 0
    for cars, slots in (
        ([(0, 1), (0, 7), (0, 16)], [(0, 0), (0, 6), (0, 15)]),
        ([(0, 2), (0, 7), (1, 17)], [(0, 4), (1, 6), (2, 15)]),
        ([(0, 1), (1, 8), (1, 19)], [(1, 3), (1, 7), (0, 18)]),
    ):
        n = len(cars)
        x, y = [v[1] for v in cars], [s[1] for s in slots]
        span = max(x) - min(x) + max(y) - min(y)
        bound = 2*n*(eps*span + 2*eps**2)
        certs = [solve_transport(cars, slots, ego_index=i) for i in range(n)]
        for ds in it.product((-eps, eps), repeat=2*n):
            perturbed = [(lane, pos + d) for (lane, pos), d in zip(cars, ds)]
            shifted = [(lane, pos + d) for (lane, pos), d in zip(slots, ds[n:])]
            new = solve_transport(perturbed, shifted)
            for i, certificate in enumerate(certs):
                if certificate.ego_gap > bound:
                    assert new.assignment[i] == certificate.assignment[i]
                    preserved += 1
            tested += 1
    return dict(noise_corners=tested, certified_ego_checks=preserved)


def check_near_ties():
    # Coordinates are exact integer multiples of 2^-33 m. Evaluate every
    # permutation in those units, independently of the solver's arithmetic.
    rng = Random(1125)
    unit = 2**33
    grid = [0, 1, 100*unit, 100*unit + 1, 100*unit + 2]
    n = 4
    orders = list(it.permutations(range(n)))
    for _ in range(512):
        cars, slots = [[(rng.randrange(3), rng.choice(grid)) for _ in range(n)]
                       for _ in range(2)]
        costs = {}
        for p in orders:
            d = [abs(lane - slots[j][0]) for (lane, _), j in zip(cars, p)]
            c = sum((x - slots[j][1])**2 for (_, x), j in zip(cars, p))
            costs[p] = max(d), sum(d), c
        optimum = min(costs.values())
        ego = rng.randrange(n)
        result = solve_transport([(k, x/unit) for k, x in cars],
                                 [(k, x/unit) for k, x in slots], ego_index=ego)
        assert costs[result.assignment] == optimum
        alt = min((c[2] for p, c in costs.items()
                   if c[:2] == optimum[:2] and p[ego] != result.assignment[ego]),
                  default=math.inf)
        assert result.ego_gap == (alt - optimum[2]) / unit**2
    return dict(snapshot_pairs=512, permutations=512*len(orders))


def check_actions():
    """All distinct geometries on three lanes x two coordinates, with 1..5 cars."""
    grid = list(it.product(range(3), (-1, 1)))
    hist = {key: [0, 0, 0] for key in ("slot", "target_lane", "next_lane")}
    scenes = permutations = ego_checks = slot_tie_lane_unique = lane_tie_step_unique = 0
    for n in range(1, 6):
        orders = list(it.permutations(range(n)))
        geometries = list(it.combinations(grid, n))
        for cars, slots in it.product(geometries, repeat=2):
            sums = {}
            for p in orders:
                d = [abs(a - slots[j][0]) for (a, _), j in zip(cars, p)]
                sums[p] = (max(d), sum(d), sum((x-slots[j][1])**2 for (_, x), j in zip(cars, p)))
            best = min(sums.values())
            for i, (origin, _) in enumerate(cars):
                gaps = []
                for action in ("target_lane", "next_lane"):
                    r = solve_transport(cars, slots, ego_index=i, action=action)
                    # Explicit physical lane sequence for each destination.
                    destinations = [lane if action == "target_lane" else
                                    max(origin-1, min(origin+1, lane)) for lane, _ in slots]
                    lane = destinations[r.assignment[i]]
                    second = min((c[2] for p,c in sums.items()
                                  if c[:2] == best[:2] and destinations[p[i]] != lane), default=math.inf)
                    assert r.action_lane == lane and r.action_gap == second - best[2]
                    assert r.ego_gap <= r.action_gap and sums[r.assignment] == best
                    gaps.append(r.action_gap)
                assert gaps[0] <= gaps[1]
                for name, gap in zip(hist, (r.ego_gap, *gaps)):
                    hist[name][2 if math.isinf(gap) else int(gap > 0)] += 1
                slot_tie_lane_unique += int(r.ego_gap == 0 < gaps[0])
                lane_tie_step_unique += int(gaps[0] == 0 < gaps[1])
                ego_checks += 1
            scenes += 1
            permutations += len(orders)
    return dict(geometry_pairs=scenes, permutations=permutations, ego_checks=ego_checks,
                counts_zero_finite_positive_infinite=hist, slot_tie_lane_unique=slot_tie_lane_unique,
                lane_tie_step_unique=lane_tie_step_unique)


def action_timing():
    rng = Random(1125)
    timings = {}
    for n in (6,12,24):
        vehicles = [(rng.randrange(4), rng.uniform(-100,200)) for _ in range(n)]
        slots = [(k % 3, (k//3 + (k%3%2)/2)*19.75) for k in range(n)]
        times = {}
        for action in (None, "target_lane", "next_lane"):
            solve_transport(vehicles, slots, ego_index=0, action=action)
            runs = []
            for _ in range(3):
                start = perf_counter_ns()
                for _ in range(100):
                    solve_transport(vehicles, slots, ego_index=0, action=action)
                runs.append((perf_counter_ns()-start)/100000)
            times[action or "slot_only"] = round(median(runs),1)
        timings[n] = times
    return timings


def check_box_actions():
    """Exact corner oracle from the original physical squares, without robust edge weights."""
    grid = list(it.product(range(3),(-1.,1.)))
    stats = Counter()
    for n in range(1,5):
        geometries = list(it.combinations(grid,n))
        orders = list(it.permutations(range(n)))
        for cars,slots in it.product(geometries, repeat=2):
            hops = {}
            for p in orders:
                d = [abs(a-slots[j][0]) for (a,_),j in zip(cars,p)]
                hops[p] = max(d),sum(d)
            best = min(hops.values())
            allowed = [p for p in orders if hops[p]==best]
            span = max(y for _,y in slots)-min(y for _,y in slots)
            stats["scenes"] += 1
            for eps in (.25,.75,1.,1.25):
                vertices = []
                for shifts in it.product((-eps,eps),repeat=n):
                    vertices.append({p:sum((x+e-slots[j][1])**2 for (_,x),e,j in zip(cars,shifts,p))
                                     for p in allowed})
                stats["scene_noise_vertices"] += len(vertices)
                for i,(lane,_) in enumerate(cars):
                    for action in ("next_lane","target_lane"):
                        r = solve_transport(cars,slots,ego_index=i,action=action,position_error=eps)
                        other = [p for p in allowed if (slots[p[i]][0] if action=="target_lane" else
                                   min(lane+1,max(lane-1,slots[p[i]][0]))) != r.action_lane]
                        worst = min((cost[p]-cost[r.assignment] for cost in vertices for p in other),
                                    default=math.inf)
                        coarse = r.action_gap - 2*n*eps*span
                        refine = r.action_lane!=lane and coarse<=0
                        assert r.action_lower_bound == (worst if refine else coarse)
                        assert r.action_lower_bound <= worst
                        stats["ego_action_checks"] += 1
                        if refine:
                            stats["refinements"] += 1
                            category = ("rescued" if worst>0 else "exact_tie" if worst==0 else "negative")
                            stats[category] += 1
    return dict(stats)


def box_timing():
    """Time the same actual move, with and without its required refinement."""
    rng = Random(1125)
    timings = {}
    for n in (6,12,24):
        anchor = [(3,20+150*j/(n-2)) for j in range(n-2)]
        slots = [(1,0.),(0,10.),*anchor]
        cars = [(0,0.),(0,.2),*((lane,y+rng.uniform(-.25,.25)) for lane,y in anchor)]
        for eps in (None,.05):
            r = solve_transport(cars,slots,ego_index=0,action="next_lane",position_error=eps)
            assert r.action_lane==1 and abs(r.action_gap-4)<1e-12
            if eps is not None:
                assert abs(r.action_lower_bound-2)<1e-12
            runs = []
            for _ in range(3):
                start = perf_counter_ns()
                for _ in range(100):
                    solve_transport(cars,slots,ego_index=0,action="next_lane",position_error=eps)
                runs.append((perf_counter_ns()-start)/100000)
            timings.setdefault(n,{})["refined" if eps else "nominal"] = round(median(runs),1)
    return timings


if __name__ == "__main__":
    print(json.dumps(dict(path=check_paths(), local=check_local_geometry(),
                          disturbance=check_perturbations(), near_tie=check_near_ties(),
                          action=check_actions(), action_microseconds=action_timing(),
                          independent_box=check_box_actions(), box_microseconds=box_timing()), indent=2))
