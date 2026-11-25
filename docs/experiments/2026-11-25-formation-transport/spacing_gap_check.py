"""Check the dependence of the ego gap on headway spacing for fixed local slot topology."""
from fractions import Fraction
from math import inf, isclose, isinf
from pathlib import Path
from random import Random
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/"variants/phase5g_pure_formation"))
from noa.transport import solve_transport


def same(x, y):
    return x==y if isinf(x) or isinf(y) else isclose(x,y,abs_tol=1e-11,rel_tol=1e-12)


def main():
    rng = Random(2511253)
    cases = comparisons = positive = ties = unique = 0
    for n in range(2,8):
        for _ in range(40):
            lanes = rng.randint(2,5)
            vehicles = [(rng.randrange(lanes),rng.randrange(-5,20)) for _ in range(n)]
            rng.shuffle(vehicles)
            target = [j%lanes for j in range(n)]
            offsets = [Fraction(j//lanes) + Fraction(target[j]%2,2) for j in range(n)]
            ego = rng.randrange(n)
            moved = [rng.choice((False,True)) for _ in range(n)]
            baseline = None
            for spacing in (Fraction(11,2),Fraction(14),Fraction(45,2),Fraction(31)):
                origin = 128 + spacing/2
                slots = [(l,float(origin-spacing*a)) for l,a in zip(target,offsets)]
                fit = solve_transport(vehicles,slots,ego_index=ego,action="next_lane",
                                      moved=moved,position_error=0.0625)
                normalized = [v/float(spacing) for v in (fit.ego_gap,fit.action_gap,fit.action_lower_bound)]
                if baseline is None:
                    baseline=(fit.action_lane, normalized)
                    ties += fit.action_gap==0
                    unique += isinf(fit.action_gap)
                    positive += 0<fit.action_gap<inf
                else:
                    assert fit.action_lane==baseline[0] and all(same(a,b) for a,b in zip(normalized,baseline[1]))
                    comparisons+=1
            # Direct expansion of the squared cost, for assignments not produced by the solver, too.
            identity=tuple(range(n))
            def objective(p, spacing):
                return sum((vehicles[i][1] - (128-spacing*offsets[j]))**2 for i,j in enumerate(p))
            for _ in range(4):
                p=rng.sample(identity,n)
                coefficient=2*sum(v[1]*(offsets[b]-offsets[a]) for v,a,b in zip(vehicles,identity,p))
                assert objective(p,spacing)-objective(identity,spacing)==spacing*coefficient
            cases+=1
    print(cases,"templates;",comparisons,"rescalings; actions with finite positive/tied/structural gaps:",
          positive,ties,unique)


if __name__=="__main__":
    main()
