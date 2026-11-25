"""Check partial-vehicle assignments over all legal targets and all slot permutations."""
from itertools import combinations,permutations
from pathlib import Path
from random import Random
import sys
sys.path.insert(0,str(Path(sys.argv[1]).resolve()))
from noa.native_rules import _extendible

rng=Random(251125)
problems=perms=0
for n in range(2,8):
    for _ in range(40):
        K=rng.randint(2,4)
        source=[rng.randrange(K) for i in range(n)]
        ego=rng.randrange(n);origin=source[ego]
        counts=tuple(source.count(k) for k in range(K))
        depth,tail=divmod(n,K)
        best=(n*K,n*K);action_set=set()
        for more in combinations(range(K),tail):
            if K==3 and 1 in more and not {0,2}.issubset(more):
                continue
            goal=list(range(K))*depth+list(more)
            for p in permutations(goal):
                ds=[abs(a-b) for a,b in zip(source,p)]
                val=max(ds),sum(ds)
                act=origin+(p[ego]>origin)-(p[ego]<origin)
                if val<best:best=val;action_set={act}
                elif val==best:action_set.add(act)
                perms+=1
        for act in (origin-1,origin,origin+1):
            assert _extendible(counts,origin,act)==(act in action_set)
        problems+=1
print(problems,"problems;",perms,"permutations; all stay, left and right decisions exact")
