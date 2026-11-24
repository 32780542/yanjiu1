"""Numerically check the common-acceleration projection with step speed bounds."""
import argparse
from pathlib import Path
import random
import sys


def verify(source):
    sys.path.insert(0,str(source.resolve()))
    from noa import native_rules as rule
    assert Path(rule.__file__).resolve().is_relative_to(source.resolve())
    rng=random.Random(8721907)
    h=rule.CONTROL_STEP;w=rule.SHAPE_FREQUENCY
    worst=0.;zero=partial=full=0
    for _ in range(6000):
        n=rng.randrange(1,21)
        cars=[];slots=[];bounds=[];base=[]
        for i in range(n):
            v=rng.choice((0.,rule.MAX_SPEED,rng.uniform(0.,rule.MAX_SPEED),
                          rng.uniform(26.,31.),rng.uniform(28.5,29.1)))
            x=rng.uniform(-300.,300.)
            car=rule.Vehicle(i,x,1.65,v,0);cars.append(car)
            slots.append(x+rng.uniform(-1.5,2.5))
            bounds.append((max(-rule.SHAPE_ACCEL_LIMIT,-v/h),min(rule.SHAPE_ACCEL_LIMIT,(rule.MAX_SPEED-v)/h)))
            base.append((rule._shape_speed(car,slots[-1])-v)/h)
        shift=rng.uniform(0.,2.)
        demand=w*w*shift
        speed=[rule._shared_anchor_speed(j,cars,slots,shift)[0] for j in range(n)]
        actual=[(s-c.speed)/h for s,c in zip(speed,cars)]
        delta=[a-b for a,b in zip(actual,base)]
        assert all(lo-1e-10<=a<=hi+1e-10 for a,(lo,hi) in zip(actual,bounds))
        worst=max(worst,max(delta)-min(delta))
        assert max(delta)-min(delta)<1e-10
        feasible_lo=max(lo-b for (lo,hi),b in zip(bounds,base))
        feasible_hi=min(hi-b for (lo,hi),b in zip(bounds,base))
        t=sum(delta)/n
        assert feasible_lo-1e-10<=t<=feasible_hi+1e-10
        for alternative in (feasible_lo,feasible_hi,rng.uniform(feasible_lo,feasible_hi)):
            assert (t-demand)**2<=(alternative-demand)**2+1e-10
        if t<1e-9: zero+=1
        elif t<demand-1e-9: partial+=1
        else: full+=1
    print("6000 cases, maximum pairwise acceleration-difference change",worst)
    print("zero, partial, full unsigned anchor increments",zero,partial,full)
    cars=[rule.Vehicle(i,0.,1.65,rule.CRUISE,0) for i in range(2)]
    slots=(-.25,1.)
    def accel(s):return round((s-rule.CRUISE)/h,8)
    print("example unclipped anchor position vs common:",
          [accel(rule._shape_speed(c,x+1.)) for c,x in zip(cars,slots)],
          [accel(rule._shared_anchor_speed(i,cars,slots,1.)[0]) for i in range(2)])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    verify(parser.parse_args().source)
