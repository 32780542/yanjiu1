"""Exact checks for the exploratory path-cost extension after local lane changes."""
import argparse
from itertools import permutations
import json
from math import factorial
from pathlib import Path
import random
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", type=Path, help="Frozen cumulative-cost experimental source")
    args = parser.parse_args()
    sys.path.insert(0, str(args.variant.resolve()))
    from noa.transport import solve_transport
    rng = random.Random(112506)
    count = schedules = ticks = permutations_checked = 0
    for n in range(2, 7):
        for _ in range(50):
            vehicles = [(rng.randrange(4), rng.randrange(14)) for _ in range(n)]
            slots = [(rng.randrange(4), rng.randrange(14)) for _ in range(n)]
            work = [rng.randrange(3) for _ in range(n)]
            candidate = solve_transport(vehicles, slots, history=work)
            def cost(p):
                distances = [abs(lane - slots[j][0]) for (lane, _), j in zip(vehicles,p)]
                return (sum(distances), max(h+d for h,d in zip(work, distances)),
                        sum((x-slots[j][1])**2 for (_,x),j in zip(vehicles,p)))
            optimum = min(map(cost, permutations(range(n))))
            assert cost(candidate.assignment) == optimum
            assert (candidate.total_crossings, candidate.max_crossings) == optimum[:2]
            permutations_checked += factorial(n)
            count += 1
            while candidate.total_crossings:
                next_cars = list(vehicles)
                movers = [i for i,j in enumerate(candidate.assignment) if vehicles[i][0] != slots[j][0]]
                chosen = rng.sample(movers, rng.randint(1,len(movers)))
                for i in chosen:
                    lane, x = vehicles[i]
                    dest = slots[candidate.assignment[i]][0]
                    next_cars[i] = (lane + (1 if dest > lane else -1), x)
                    work[i] += 1
                updated = solve_transport(next_cars, slots, history=work)
                assert updated.total_crossings == candidate.total_crossings - len(chosen)
                assert updated.max_crossings <= candidate.max_crossings
                candidate, vehicles = updated, next_cars
                ticks += 1
            assert max(work) == optimum[1]
            schedules += 1
    print(json.dumps(dict(snapshots=count, permutations=permutations_checked,
                          completed_schedules=schedules, reassignments=ticks), indent=2))


if __name__ == "__main__":
    main()
