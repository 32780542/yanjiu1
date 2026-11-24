"""Check ego-only edge requests against a global physical-order oracle."""
import argparse
import importlib.util
from pathlib import Path
import random
import sys
from types import SimpleNamespace


def load(path):
    spec = importlib.util.spec_from_file_location("endpoint_native", path/"noa/native_rules.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check(source, reach):
    sys.path.insert(0,str(source.resolve()))
    native = load(source)
    request = native._endpoint_shift
    rng = random.Random(471124)
    count = edges = 0
    cases = [[(0,0), (20,0), (90,1), (130,0)], [(0,0),(0,1),(70,0),(70,1)],
             [(0,0),(70,0),(70,0)], [(0,1),(0,1),(69,0)], [(0,1),(0,1),(0,2),(70,1)]]
    for space in (0,50,50.000001,100,100.000001,200,200.000001):
        cases.append([(0,0),(space,1)])
    for _ in range(1200):
        x = rng.uniform(-200,200)
        coordinates = []
        for i in range(rng.randint(1,22)):
            x += rng.choice((0.,3.,48.,49.5,51.,69.,98.,99.5,101.,150.,199.5,201.))
            coordinates.append((x,rng.randrange(4)))
        cases.append(coordinates)
    for coordinates in cases:
        cars = [SimpleNamespace(x=x,lane=j,speed=rng.uniform(0,33.3)) for x,j in coordinates]
        keys = [(c.x,c.lane) for c in cars]
        reference = [0. for c in cars]
        order = sorted(range(len(cars)),key=keys.__getitem__)
        for a,b in zip(order,order[1:]):
            g = cars[b].x-cars[a].x
            if g <= 50 or g > reach or keys.count(keys[a])!=1 or keys.count(keys[b])!=1:
                continue
            change = .5*max(0.,g-5.5-.85*(cars[a].speed+cars[b].speed)/2)
            reference[a]+=change
            if g<=100: reference[b]-=change
            edges+=1
        measured=[]
        for ego in cars:
            rows = [c for c in cars if c is not ego and -100<=c.x-ego.x<=200]
            rng.shuffle(rows)
            measured.append(request(ego,rows,reach))
        assert max(abs(a-b) for a,b in zip(measured,reference))<1e-10
        if reach==100: assert abs(sum(measured))<1e-10
        count+=len(cars)
    print(len(cases),"views,",count,"ego requests,",edges,"eligible edges")
    calls=0
    for gap in (70.,150.):
        locations=(0.,20.,20.+gap,60.+gap)
        cars=[native.Vehicle(i,x,1.65+3.3*(i%2),28.8,i%2) for i,x in enumerate(locations)]
        for ego in cars:
            rows=tuple(c for c in cars if c is not ego and -100<=c.x-ego.x<=200)
            for switching in (False,True):
                params=dict(mode="transform",drop_x=ego.x+100. if switching else None,
                            lane_count=3,upcoming_lanes=2 if switching else None)
                command=native.decide(ego,rows,native.Memory(),**params)[0]
                native._endpoint_shift=lambda *_:0.
                try:
                    unshifted=native.decide(ego,rows,native.Memory(),**params)[0]
                finally:
                    native._endpoint_shift=request
                want=0. if switching else request(ego,rows,reach)
                assert abs(command.target_x-unshifted.target_x-want)<1e-8
                assert command.lane==unshifted.lane
                calls+=1
    print(calls,"native decide() pairs with expected target positions and lane actions")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path)
    p.add_argument("--reach",type=int,choices=(100,200),default=100);a=p.parse_args()
    check(a.source,a.reach)
