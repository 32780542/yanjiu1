"""Verify the exact longitudinal phase margin for a balanced two-lane window."""
from fractions import Fraction as F
from math import isclose
from pathlib import Path
from random import Random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]/"variants/phase5g_pure_formation"))
from noa.transport import solve_transport


def direct(cars, spacing, phase):
    n = len(cars)
    mean_x = sum(x for _,x in cars)/n
    origin = mean_x + (n-1)*spacing/4
    slots = [(phase^(k%2), float(origin-k*spacing/2)) for k in range(n)]
    fit = solve_transport([(l,float(x)) for l,x in cars],slots)
    assert fit.total_crossings == 0
    return fit.squared_displacement


def verify():
    rng=Random(112505)
    count=0
    for size in range(2,26,2):
        for _ in range(45):
            d=F(rng.randrange(20,450),10)
            cars=[(j%2, F(rng.randrange(-4000,4001),16)) for j in range(size)]
            rng.shuffle(cars)
            m=sum(x*(1-2*l) for l,x in cars)
            radius=abs(m)/size
            direction=(m>0)-(m<0)
            for factor in (F(0),F(1,2),F(1),F(3,2)):
                changed=[(l,x-factor*radius*direction*(1-2*l)) for l,x in cars]
                lhs=direct(changed,d,1)-direct(changed,d,0)
                rhs=d*m*(1-factor)
                assert isclose(lhs,float(rhs),abs_tol=1e-8,rel_tol=1e-10), (lhs,rhs)
                count+=1
    return count


if __name__ == "__main__":
    print("Two independently solved mirror costs, including exact ties:",verify())
