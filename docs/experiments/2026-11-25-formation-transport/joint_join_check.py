"""Verify the simultaneous overlap theorem against every one-hop allocation of a larger group."""
from itertools import combinations,permutations
from pathlib import Path
from random import Random
import sys
sys.path.insert(0,str(Path(sys.argv[1]).resolve()))
from noa.staggered import _shared_quota
from noa.transport import lane_bounds

r=Random(2511251)
cases=checked=0
for n in range(3,9):
    for _ in range(35):
        k=r.randrange(2,5)
        src=tuple(r.randrange(k) for i in range(n))
        m=r.randrange(2,n)
        g=src[:m]
        goal=tuple(r.randrange(k) for i in range(m))
        bg,cg=lane_bounds(g,goal)
        if bg!=1:continue
        orig=sorted(range(m),key=g.__getitem__)
        plan=dict(zip(orig,sorted(goal)))
        proposed={i for i in range(m) if plan[i]!=g[i]}
        counts=tuple(src.count(i) for i in range(k))
        net=tuple(sum(1 for v in g if v<=j)-sum(1 for v in goal if v<=j) for j in range(k-1))
        quota=_shared_quota(counts,net)
        if quota is None:continue
        pool=[]
        for tail in combinations(range(k),n%k):
            if k==3 and 1 in tail:continue
            t=tuple(range(k))*(n//k)+tail
            pool.append((lane_bounds(src,t),t))
        best=min(v for v,t in pool)
        best_sub=-1
        for v,t in pool:
            if v!=best:continue
            for p in set(permutations(t)):
                ds=[abs(a-b) for a,b in zip(src,p)]
                checked+=1
                if (max(ds),sum(ds))!=best:continue
                best_sub=max(best_sub,sum(p[i]==plan[i] for i in proposed))
        assert best_sub==sum(quota)
        cases+=1
print(cases,"one-hop problems;",checked,"larger assignments tested")
