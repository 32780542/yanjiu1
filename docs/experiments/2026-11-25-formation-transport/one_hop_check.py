"""Check the whole face of optimal assignments and each ego's gap, by exhaustive enumeration."""
from itertools import combinations,permutations
from math import inf
from pathlib import Path
import random
import sys

sys.path.insert(0,str(Path(sys.argv[1]).resolve()))
from noa.transport import solve_transport

rng = random.Random(251125)
points = 0
cases = 0
for n in range(2,8):
    for _ in range(48):
        lanes = rng.randrange(2,5)
        source = [rng.randrange(lanes) for _ in range(n)]
        dest = [rng.randrange(lanes) for _ in range(n)]
        xs,ys = [[rng.randrange(-14,15) for _ in range(n)] for _ in range(2)]
        used = [rng.randrange(2) for _ in range(n)]
        ego = rng.randrange(n)
        opt = []
        for p in permutations(range(n)):
            ds = [abs(a-dest[j]) for a,j in zip(source,p)]
            moving_twice = bool(max(ds)==1 and any(d and h for d,h in zip(ds,used)))
            cost = sum((xs[i]-ys[j])**2 for i,j in enumerate(p))
            opt.append(((max(ds),sum(ds),moving_twice,cost),p))
        best = min(v for v,p in opt)
        fit = solve_transport(list(zip(source,xs)),list(zip(dest,ys)),history=used,ego_index=ego,
                              action="next_lane",position_error=0.)
        assert (best,fit.assignment) in opt
        step = lambda l: source[ego]+(l>source[ego])-(l<source[ego])
        for slot in (True,False):
            comp = [v[-1] for v,p in opt if v[:3]==best[:3] and
                    (p[ego]!=fit.assignment[ego] if slot else step(dest[p[ego]])!=fit.action_lane)]
            assert min(comp,default=inf)-best[-1]==(fit.ego_gap if slot else fit.action_gap)
        points+=len(opt);cases+=1
print(cases,"cases;",points,"assignments; exact one-hop faces and ego gaps")
