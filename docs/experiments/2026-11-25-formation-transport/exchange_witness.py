"""Explain an ego gap by the cheapest alternating reassignment cycle in its local window."""
from fractions import Fraction
from itertools import permutations
from math import inf
from pathlib import Path
from random import Random
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "variants/phase5g_pure_formation"))
from noa.transport import lane_bounds, solve_transport


def exchange_paths(vehicles, slots, chosen, ego):
    """Return the exact extra cost and cycle of owners for each alternative ego slot.

    Positions use the precise binary values supplied by the caller. The graph contains
    only exchanges that respect the two optimal lateral objectives. A closed exchange
    cycle preserves the assignment of every vehicle outside that cycle.
    """
    n = len(vehicles)
    source = [v[0] for v in vehicles]
    lanes = [s[0] for s in slots]
    radius, _ = lane_bounds(source, lanes)
    flow = {k: sum(a <= k for a in source) - sum(b <= k for b in lanes)
            for k in range(min(source + lanes), max(source + lanes))}
    x = [Fraction(v[1]) for v in vehicles]
    y = [Fraction(slots[j][1]) for j in chosen]
    weights = [{} for _ in vehicles]
    for i, a in enumerate(source):
        for j, col in enumerate(chosen):
            b = lanes[col]
            if i == j or abs(a-b) > radius:
                continue
            if any((b-a)*flow[k] <= 0 for k in range(min(a,b), max(a,b))):
                continue
            weights[i][j] = 2*(x[i]-x[ego])*(y[i]-y[j])

    # Work backwards to the ego. On a cost tie prefer fewer exchanges.
    distance = {ego: (Fraction(0), 0)}
    next_owner = {}
    for _ in range(n-1):
        updated = False
        for i in range(n):
            if i == ego:
                continue
            for j, w in weights[i].items():
                if j not in distance:
                    continue
                key = (w + distance[j][0], 1 + distance[j][1])
                if i not in distance or key < distance[i]:
                    distance[i], next_owner[i], updated = key, j, True
        if not updated:
            break
    choices = {}
    for v, w in weights[ego].items():
        if v not in distance:
            continue
        owners = [ego, v]
        while owners[-1] != ego:
            owners.append(next_owner[owners[-1]])
        assert len(set(owners[:-1])) == len(owners)-1
        extra = w + distance[v][0]
        assert extra >= 0
        choices[chosen[v]] = (extra, tuple(owners[:-1]))
    return choices


def best_alternative(choices, predicate):
    candidates = [(gap, len(cycle), col, cycle) for col, (gap,cycle) in choices.items()
                  if predicate(col)]
    if not candidates:
        return inf, None, ()
    gap, _, col, cycle = min(candidates)
    return gap, col, cycle


def check():
    rng = Random(112504)
    examples = tested = 0
    for n in range(2,8):
        for _ in range(20):
            k = rng.randrange(2,6)
            vehicles = [(rng.randrange(k), rng.randrange(-6,7)) for _ in range(n)]
            slots = [(rng.randrange(k), rng.randrange(-6,7)) for _ in range(n)]
            fit = solve_transport(vehicles, slots)
            p = fit.assignment
            eligible = []
            for alt in permutations(range(n)):
                moves = [abs(v[0]-slots[j][0]) for v,j in zip(vehicles,alt)]
                if (max(moves),sum(moves)) == (fit.max_crossings,fit.total_crossings):
                    cost = sum((v[1]-slots[j][1])**2 for v,j in zip(vehicles,alt))
                    eligible.append((cost-int(fit.squared_displacement),alt))
            for ego in range(n):
                choices = exchange_paths(vehicles,slots,p,ego)
                for col in range(n):
                    if col == p[ego]:
                        continue
                    expected = min((cost for cost,a in eligible if a[ego]==col), default=inf)
                    got, _, cycle = best_alternative(choices,lambda j:j==col)
                    assert expected == got
                    if cycle:
                        alt = list(p)
                        for a,b in zip(cycle,cycle[1:]+cycle[:1]):
                            alt[a] = p[b]
                        assert (got,tuple(alt)) in eligible
                    tested += 1
            examples += 1
    return examples, tested


def hidden_tail():
    """Identical finite views which require different unique globally optimal ego actions."""
    ego = 1
    for count in (12, 24, 48):
        for spacing in (28., 29.98, 32.):
            slots = [(k%2, (1-k)*spacing/2) for k in range(count)]
            a = list(slots)
            a[ego] = (0, slots[ego][1])
            b = a.copy()
            a[10] = (1, slots[10][1])
            visible = lambda cars: [car for car in cars if -100 <= car[1] <= 200]
            assert visible(a) == visible(b) and len(visible(a)) < count
            def fit(cars):
                return solve_transport(cars,slots[:len(cars)],ego_index=ego,action="next_lane")
            left, right, observed = fit(a), fit(b), fit(visible(a))
            assert (left.total_crossings, left.action_lane, left.action_gap) == (0, 0, inf)
            assert (right.total_crossings, right.action_lane, right.squared_displacement) == (1, 1, 0)
            assert abs(right.action_gap-spacing**2/2) < 1e-8
            if count == 12 and spacing == 29.98:
                print("Identical views:", len(visible(a)), "cars; local action",observed.action_lane,
                      "global actions",left.action_lane,right.action_lane,"gap",right.action_gap)


def main():
    sample = json.loads((HERE / "ego_gap_example.json").read_bytes())
    vehicles, slots, ego = sample["vehicles"],sample["slots"],sample["ego_index"]
    fit = solve_transport(vehicles, slots, ego_index=ego, action="next_lane")
    p = fit.assignment
    choices = exchange_paths(vehicles, slots, p, ego)
    orig = vehicles[ego][0]
    step = lambda j: orig + (slots[j][0]>orig) - (slots[j][0]<orig)
    for name, rule, expected in (
        ("slot", lambda j:j!=p[ego], fit.ego_gap),
        ("next lane", lambda j:step(j)!=step(p[ego]), fit.action_gap),
    ):
        extra, col, cycle = best_alternative(choices,rule)
        assert abs(float(extra)-expected) < 1e-9
        print(name, float(extra), "m^2; ego rank",ego,"alternative slot",col)
        for i,j in zip(cycle,cycle[1:]+cycle[:1]):
            print("  rank",i, "x",round(vehicles[i][1],3), "assigned",p[i],"alternative",p[j],
                  "new lane",slots[p[j]][0])
    print("Enumerated examples and exact rival slots:", *check())
    hidden_tail()


if __name__ == "__main__":
    main()
