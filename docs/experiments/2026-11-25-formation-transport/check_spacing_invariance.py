"""Check which ego decisions change when a fixed staggered grid is translated or scaled."""
from itertools import permutations
from math import isclose, isfinite
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]/"variants/phase5g_pure_formation"))
from noa.transport import solve_transport


def minimum_and_gap(records):
    best_lateral = min(r[:2] for r in records)
    records = [r for r in records if r[:2] == best_lateral]
    low = min(r[2] for r in records)
    choices = frozenset((r[3],r[4]) for r in records if r[2] == low)
    selected = min(choices)[1]
    different = [r[2] for r in records if r[4] != selected]
    return choices, (min(different)-low if different else None)


def check():
    rng = random.Random(25110355)
    scenarios = permutations_tested = scales = physical_solves = 0
    # Integer centimetres represent common headway spacing divided by two.
    half_gaps_cm = (275, 700, 1125, 1499, 1690)  # 0, 10, 20, 28.8 and just under 33.3 m/s
    for n in range(2,7):
        for _ in range(36):
            lanes = rng.randrange(2,5)
            cars = [(rng.randrange(lanes+1),rng.randrange(-25,40)) for i in range(n)]
            slot_lanes = [k%lanes for k in range(n)]
            half_layers = [2*(j//lanes)+(l%2) for j,l in enumerate(slot_lanes)]
            ego = rng.randrange(n)
            outcomes = []
            for p in permutations(range(n)):
                distances = [abs(a-slot_lanes[j]) for (a,_),j in zip(cars,p)]
                step = cars[ego][0]+(slot_lanes[p[ego]]>cars[ego][0])-(slot_lanes[p[ego]]<cars[ego][0])
                outcomes.append((max(distances),sum(distances),p,step))
            reference = None
            for h in half_gaps_cm:
                origin = rng.randrange(-100000,100001)
                slots = [(l,origin-h*m) for l,m in zip(slot_lanes,half_layers)]
                records = [(m,s,sum((100*cars[i][1]-slots[j][1])**2 for i,j in enumerate(p)),p[ego],step)
                           for m,s,p,step in outcomes]
                choices, gap_cm2 = minimum_and_gap(records)
                if reference is None:
                    reference = (choices,gap_cm2,h)
                old_choices,old_gap,old_h = reference
                assert choices == old_choices
                assert gap_cm2 is None and old_gap is None or gap_cm2*old_h == old_gap*h
                fit = solve_transport(cars,[(l,y/100) for l,y in slots],ego_index=ego,
                                      action="next_lane",position_error=.05)
                # Floating positioning may reorder ties. Check the returned role/action
                # belongs to the exact set and compare finite gap only for that action.
                assert (fit.assignment[ego],fit.action_lane) in choices
                if len({step for _,step in choices})>1:
                    assert abs(fit.action_gap) < 1e-8
                elif gap_cm2 is not None:
                    assert isclose(fit.action_gap,gap_cm2/10000,rel_tol=1e-8,abs_tol=1e-8)
                else:
                    assert not isfinite(fit.action_gap)
                physical_solves += 1
                permutations_tested += len(outcomes)
                scales += 1
            scenarios += 1
    print(f"{scenarios} local problems, {scales} measured grids, {permutations_tested} integer "
          f"permutation evaluations, {physical_solves} matching calls")


if __name__=="__main__":
    check()
