"""Test actual anchor routing and the geometric sufficiency of the hard-window test."""
import argparse
from pathlib import Path
import random
import sys
from unittest.mock import patch


def run(source):
    sys.path.insert(0,str(source.resolve()))
    from noa import native_rules as native,staggered
    for rear,expected in ((50.001,None),(50.,100.),(49.999,100.)):
        cars=[native.Vehicle(j,x,1.65+3.3*(j%2),28.8,j%2)
              for j,x in enumerate((0.,-25.,-rear,15.,100.))]
        with patch.object(staggered,"choose_target",wraps=staggered.choose_target) as choose:
            native.decide(cars[0],cars[1:],native.Memory(),mode="transform",drop_x=None)
        assert choose.call_args.kwargs["forward_anchor"]==expected,(rear,choose.call_args.kwargs)
    ego=native.Vehicle(0,0.,1.65,28.8,0);other=native.Vehicle(1,80.,4.95,28.8,1)
    solo=native.decide(ego,[other],native.Memory(),mode="transform",drop_x=None)[0]
    assert solo.target_x==staggered.anchored_x(ego.x,ego.x,native.desired_spacing(ego.speed),other.x)
    rng=random.Random(442511)
    passed=rejected_complete=with_anchor=0
    for _ in range(1800):
        n=rng.randrange(2,28);xs=[];x=-250.
        for _ in range(n):
            x+=rng.choice((0.,8.,25.,49.99,50.,50.01,59.,89.,120.))
            xs.append(x)
        cs=[native.Vehicle(i,x,1.65,28.8,i%3) for i,x in enumerate(xs)]
        for ego in cs:
            rows=[c for c in cs if c is not ego and -100<=c.x-ego.x<=200]
            group=native._local_group(ego,rows);full=native._local_group(ego,[c for c in cs if c is not ego])
            head=ego.x+200-group[-1].x;tail=group[0].x-(ego.x-100)
            ok=head>=50 and tail>=50
            if ok:
                assert group==full
                passed+=1
            else:rejected_complete+=group==full
            if any(c.x>group[-1].x for c in rows):
                assert head>=50
                with_anchor+=1
    print("3 boundary decisions and singleton pass; certified complete",passed,
          "uncertified but complete",rejected_complete,"visible anchors",with_anchor)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path)
    run(p.parse_args().source)
