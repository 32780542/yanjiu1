"""Enumerate one-hop matchings independently of either policy's optimizer."""
import argparse
from collections import Counter
from itertools import permutations
from math import inf
from pathlib import Path
from random import Random
import sys


def verify(folder, policy):
    sys.path.insert(0, str(folder.resolve()))
    from noa.transport import solve_transport

    rng = Random(112542)
    checked = forced_cases = choices = 0
    for n in range(2, 8):
        for _ in range(60):
            k = rng.randrange(2, 8)
            source = [rng.randrange(k) for _ in range(n)]
            target = [min(k - 1, max(0, s + rng.choice((-1, 0, 1)))) for s in source]
            if sorted(source) == sorted(target):
                continue
            used = [rng.choice((False, True)) for _ in source]
            x, y = [[rng.randrange(20) for _ in source] for _ in range(2)]
            ego = rng.randrange(n)
            cases = []
            for p in permutations(range(n)):
                distance = [abs(source[i] - target[j]) for i, j in enumerate(p)]
                repeated = sum(bool(d and u) for d, u in zip(distance, used))
                cost = sum((x[i] - y[j]) ** 2 for i, j in enumerate(p))
                cases.append((max(distance), sum(distance), repeated, cost, p))
            radius, total, repetitions, _, _ = min(cases)
            assert radius == 1
            fresh = Counter(s for s, h in zip(source, used) if not h)
            population, goals = Counter(source), Counter(target)
            flow = minimum = 0
            for lane in range(k):
                right = flow + population[lane] - goals[lane]
                outgoing = max(0, -flow) + max(0, right)
                minimum += max(0, outgoing - fresh[lane])
                flow = right
            assert repetitions == minimum
            admissible = [(cost, p) for b, c, r, cost, p in cases if (b, c) == (radius, total)
                          and (r == minimum or (policy == "feasible" and minimum > 0))]
            flags = {"moved" if policy == "feasible" else "history": used}
            result = solve_transport(list(zip(source, x)), list(zip(target, y)), ego_index=ego,
                                     action="next_lane", position_error=0., **flags)
            optimum = min(cost for cost, _ in admissible)
            assert (optimum, result.assignment) in admissible
            for kind in ("slot", "action"):
                def changes_ego(p):
                    return (p[ego] != result.assignment[ego] if kind == "slot"
                            else target[p[ego]] != result.action_lane)
                alternative = min((c for c, p in admissible if changes_ego(p)), default=inf)
                assert alternative - optimum == (result.ego_gap if kind == "slot" else result.action_gap)
            checked += 1
            choices += len(cases)
            forced_cases += minimum > 0
    print(policy, checked, "cases,", choices, "permutations,", forced_cases, "require reuse")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", type=Path)
    parser.add_argument("policy", choices=("feasible", "minimum"))
    args = parser.parse_args()
    verify(args.variant, args.policy)
