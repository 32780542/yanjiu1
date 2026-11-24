"""Compare the local formed-pair predicate with independent subset enumeration."""
from itertools import combinations
from pathlib import Path
import random
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
source=ROOT/"tmp/nov25-formed-pair-anchor/frozen/formed_pair"
sys.path.insert(0,str(source))
from noa import staggered as st
from noa.native_rules import Vehicle,desired_spacing


def reference(group,lanes,d):
    found=set()
    for ids in combinations(range(len(group)),2*lanes):
        cars=[group[i] for i in ids]
        low=min(c.x for c in cars);hi=max(c.x for c in cars)
        if sum(low<=c.x<=hi for c in group)!=len(cars):
            continue
        if max(c.speed for c in cars)-min(c.speed for c in cars)>.5+1e-9:
            continue
        columns=[sorted([c.x for c in cars if c.lane==j and abs(c.y-3.3*(j+.5))<=.3+1e-9],reverse=True)
                 for j in range(lanes)]
        if any(len(col)!=2 or not d-2-1e-9<=col[0]-col[1]<=d+2+1e-9 for col in columns):
            continue
        for lead in ((0,1) if lanes==2 else (0,)):
            if all(abs(columns[i][rank]-columns[j][rank]-
                       d*.5*(((j+lead)%2)-((i+lead)%2)))<=2+1e-9
                   for i,j in combinations(range(lanes),2) for rank in (0,1)):
                found.update(ids)
    return found


def main():
    rng=random.Random(880041);total=accepted=0
    for lanes in (2,3,4):
        for _ in range(240):
            v=rng.uniform(12,33);d=desired_spacing(v);phase=rng.randrange(2)
            group=[Vehicle(j+lane*10,320.-d*(j+((lane+phase)%2)*.5)+rng.uniform(-.7,.7),
                           3.3*(lane+.5),v+rng.uniform(-.16,.16),lane)
                   for j in range(2) for lane in range(lanes)]
            if rng.randrange(2):
                idx=rng.randrange(len(group));c=group[idx]
                group[idx]=Vehicle(c.track,c.x+rng.choice((0.,d/2)),c.y+rng.choice((0.,.4)),
                                   c.speed+rng.choice((0.,.65)),c.lane)
            if rng.randrange(2):
                j=rng.randrange(lanes);group.append(Vehicle(40,rng.uniform(260,330),3.3*(j+.5),v,j))
            group.sort(key=lambda c:(-c.x,c.lane))
            local=desired_spacing(sum(c.speed for c in group)/len(group))
            expected=reference(group,lanes,local)
            got={rank for rank in range(len(group)) if st._inside_formed_pair(rank,group,lanes,local)}
            assert expected==got
            total+=len(group);accepted+=len(got)
    print("720 random views,",total,"ego predicates,",accepted,"qualifications, zero discrepancies")


if __name__=="__main__":
    main()
