"""Enumerate small assignments including all ego alternatives and ties."""
from itertools import permutations
from math import inf
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(sys.argv[1]).resolve()))
from noa.transport import solve_transport

rng = random.Random(251109)
cases = options = 0
for n in range(2,8):
    for _ in range(40):
        a,b = [[rng.randrange(4) for i in range(n)] for j in range(2)]
        x,y = [[rng.randrange(-6,7) for i in range(n)] for j in range(2)]
        e,h = rng.randrange(n), rng.randrange(4)
        visible = len(sys.argv)>2
        hist = [rng.randrange(4) for i in range(n)] if visible else [h if i==e else 0 for i in range(n)]
        def score(p):
            ds = [abs(a[i]-b[j]) for i,j in enumerate(p)]
            known = [z+v for z,v in zip(hist,ds)]
            load = sum(z*z for z in known) if visible and sys.argv[2]=="square" else max(known)
            return max(ds),sum(ds),load,sum((x[i]-y[j])**2 for i,j in enumerate(p))
        scores = [(score(p),p) for p in permutations(range(n))]
        best = min(v for v,p in scores)
        fit = solve_transport(list(zip(a,x)),list(zip(b,y)),ego_index=e, **({"history":hist} if visible else {"ego_history":h}),
                              action="next_lane",position_error=0.)
        assert score(fit.assignment) == best
        step = lambda lane: a[e] + (lane>a[e])-(lane<a[e])
        for slot in (False,True):
            comp = [v[-1] for v,p in scores if v[:3]==best[:3] and
                    (p[e]!=fit.assignment[e] if slot else step(b[p[e]])!=fit.action_lane)]
            gap = min(comp,default=inf)-best[-1]
            assert gap == (fit.ego_gap if slot else fit.action_gap)
        cases += 1
        options += len(scores)
print(cases, "cases;", options, "assignments; all costs and ego gaps exact")
