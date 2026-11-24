"""Verify two-lane path cropping using the actual frozen target selector."""
import argparse
import importlib.util
import math
from pathlib import Path
import random
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--frozen",type=Path,default=ROOT/"tmp/path-holdout-9800/frozen")
frozen=parser.parse_args().frozen.resolve()
PATH=frozen/"path"
BASE=frozen/"retained"
sys.path.insert(0,str(PATH))
from noa import staggered as path
from noa.native_rules import Vehicle
assert Path(path.__file__).resolve().is_relative_to(PATH)


def cars(indices,phase,spacing,errors):
    return [Vehicle(i,221.-i*spacing/2+e,((phase^(i%2))+.5)*3.3,28.8,phase^(i%2))
            for i,e in zip(indices,errors)]


def test_window(group,spacing,ranks,flags,bounds,eps):
    # The origin for a legal cropped path is the mean residual, in local ranks.
    origins=[c.x+k*spacing/2 for k,c in enumerate(group)]
    assert max(origins)-min(origins)<=2*eps+1e-10
    reference=sum(origins)/len(group)
    for k in ranks:
        target=path.choose_target(k,group,2,spacing,head_clipped=flags[0],tail_clipped=flags[1],
                                  sensor_bounds=bounds)
        assert target.lane==group[k].lane and math.isinf(target.step_gap)
        assert abs(target.x-(reference-k*spacing/2))<1e-8
        assert abs(target.x-group[k].x)<=2*eps*(1-1/len(group))+1e-8


def main():
    spacing=29.98
    ideal=checks=single=0
    for n in range(1,25):
        for phase in (0,1):
            full=cars(range(n),phase,spacing,[0.]*n)
            for i in range(n):
                for j in range(i+1,n+1):
                    group=full[i:j]
                    ranks=range(len(group)) if len(group)<=6 else sorted({0,len(group)//2,len(group)-1})
                    test_window(group,spacing,ranks,(i>0,j<n),
                                (group[-1].x-.01,group[0].x+.01),0.)
                    ideal+=1;checks+=len(ranks);single+=len(group)==1
    rng=random.Random(98009801)
    noisy=outside=0
    for _ in range(4000):
        n=rng.randint(1,48);phase=rng.randrange(2);step=rng.uniform(5.5,33.805)
        errors=[rng.choice((-.05,.05,rng.uniform(-.05,.05))) for _ in range(n)]
        full=cars(range(n),phase,step,errors)
        # Put each hard sensor edge at/on either side of a measured member.
        u,v=sorted(rng.sample(range(n),2)) if n>1 else (0,0)
        front=full[u].x+rng.choice((-.025,0.,.025))
        rear=full[v].x+rng.choice((-.025,0.,.025))
        group=[c for c in full if rear<=c.x<=front]
        if not group:
            outside+=1
            continue
        keys=[c.track for c in group]
        assert keys==list(range(keys[0],keys[-1]+1))
        k=rng.randrange(len(group))
        test_window(group,step,{0,k,len(group)-1},(keys[0]>0,keys[-1]<n-1),(rear,front),.05)
        noisy+=1
    # A former legal odd physical tail leaves a half-layer hole before its end.
    spec=importlib.util.spec_from_file_location("retained_tail_geometry",BASE/"noa/staggered.py")
    old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
    group=cars((0,1,2,3,5),0,spacing,[0.]*5)
    displacement=[]
    for k,c in enumerate(group):
        a=old.choose_target(k,group,2,spacing);b=path.choose_target(k,group,2,spacing)
        assert a.lane==b.lane==c.lane and abs(a.x-c.x)<1e-8
        displacement.append(round(b.x-c.x,4))
    assert max(map(abs,displacement))>spacing/4
    print("ideal windows, ego solves, singletons:",ideal,checks,single)
    print("occupied and empty noisy hard windows:",noisy,outside)
    print("legacy true tail indexed 0,1,2,3,5; new signed displacements:",displacement)


if __name__=="__main__":
    main()
