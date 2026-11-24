"""Compare the local action-radius formulation with independent enumeration and LPs."""
import argparse
from itertools import permutations
import json
from math import inf, isfinite
from pathlib import Path
import random

import numpy as np
from scipy.optimize import linprog

from action_radius import action_graph, action_radius, witness_competitor


def enumerate_radius(vehicles, slots, ego, action):
    n = len(vehicles)
    x = np.array([p for _,p in vehicles])
    y = np.array([p for _,p in slots])
    candidates = []
    for p in permutations(range(n)):
        dis = [abs(lane-slots[j][0]) for (lane,_),j in zip(vehicles,p)]
        lane = vehicles[ego][0]
        step = lane + int(np.sign(slots[p[ego]][0]-lane))
        candidates.append((max(dis),sum(dis),step,y[list(p)]))
    objective = min(item[:2] for item in candidates)
    keep = [a[3] for a in candidates if a[:2] == objective and a[2] == action]
    change = [a[3] for a in candidates if a[:2] == objective and a[2] != action]
    best_radius = inf
    identity = np.eye(n)
    for opponent in {tuple(v) for v in change}:
        slopes = np.unique(np.array(keep)-opponent, axis=0)
        rows = np.vstack((np.column_stack((slopes,np.zeros(len(slopes)))),
                          np.column_stack((identity,-np.ones(n))),
                          np.column_stack((-identity,-np.ones(n)))))
        rhs = np.r_[-slopes@x,np.zeros(2*n)]
        res = linprog([0.]*n+[1.], A_ub=rows, b_ub=rhs,
                      bounds=[(None,None)]*n+[(0,None)],method="highs")
        assert res.success
        best_radius = min(best_radius, res.fun)
    return best_radius


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases",type=int,default=180)
    ap.add_argument("--example",type=Path)
    args=ap.parse_args()
    rng = random.Random(25110316)
    stats = dict(cases=0, zero=0, structural=0, positive=0, strict_witness=0)
    strict = None
    for t in range(args.cases):
        n = 3+t%4
        vehicles = [(rng.randrange(3),rng.randrange(-12,13)) for _ in range(n)]
        slots = [(rng.randrange(3),rng.randrange(-8,9)) for _ in range(n)]
        ego = rng.randrange(n)
        x,y,p,same,other,gap = action_graph(vehicles,slots,ego)
        action = vehicles[ego][0] + int(np.sign(slots[p[ego]][0]-vehicles[ego][0]))
        oracle = enumerate_radius(vehicles,slots,ego,action)
        ans = action_radius(x,y,p,same,other,gap)
        w,_ = witness_competitor(x,y,p,other)
        if not ans.converged or isfinite(oracle) != isfinite(ans.upper_m):
            raise AssertionError((vehicles,slots,ego,oracle,ans))
        if isfinite(oracle):
            assert abs(oracle-ans.lower_m)<1e-6 and abs(oracle-ans.upper_m)<1e-6
            assert w <= oracle + 1e-6
            stats["zero" if oracle<1e-8 else "positive"] += 1
            if oracle>w+1e-6:
                stats["strict_witness"] += 1
                if strict is None:
                    strict = dict(vehicles=vehicles,slots=slots,ego=ego,action=action,
                                  witness_m=float(w),exact_m=float(oracle))
        else:
            stats["structural"] += 1
        stats["cases"] += 1
    print(json.dumps(dict(**stats,example=strict), ensure_ascii=False),flush=True)
    if args.example:
        sample=json.loads(args.example.read_bytes())
        graph=action_graph(sample["vehicles"],sample["slots"],sample["ego_index"])
        ans=action_radius(*graph,seconds=90.)
        w,_=witness_competitor(*graph[:3],graph[4])
        print(json.dumps(dict(witness_m=w,lower_m=ans.lower_m,upper_m=ans.upper_m,
                              converged=ans.converged,perturbation_m=ans.perturbation)),flush=True)


if __name__ == "__main__":
    main()
