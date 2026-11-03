"""10k reproducible local snapshots; classify D0/D1 self-member differences."""
from dataclasses import asdict,replace
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
DOC=ROOT/'docs/experiments/2026-11-03-midflow-staggered/candidates/real_gap_balance_D1'


def load(name,path,expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


d0=load('compare_D0',ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance/native_rules.py',
        'afb3ecbe5a432bd2c93e16a21ac88690171266fd37e0c420bc74ea7e6146047e')
d1=load('compare_D1',ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py',
        '2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a')


def exact(value):
    if hasattr(value,'__dataclass_fields__'):return exact(asdict(value))
    if isinstance(value,float):return value.hex()
    if isinstance(value,dict):return {k:exact(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [exact(v) for v in value]
    return value


def car(i,x,l,v=28.8):return d1.Vehicle(i,x,(l+.5)*d1.LANE_WIDTH,v,l)


real=d0._merge_target
events=[]
def instrument(car,visible,lane,held=None):
    visible=tuple(visible)
    result=real(car,visible,lane,held)
    if any(c.track==car.track and d0._occupies(c,lane) for c in visible):
        excluded=real(car,tuple(c for c in visible if c.track!=car.track),lane,held)
        if exact(result)!=exact(excluded):
            events.append(dict(candidate_track=car.track,lane=lane,x=car.x,y=car.y,vy=car.vy,
                               with_self=result,without_self=excluded))
    return result
d0._merge_target=instrument
rng=random.Random(202611032102)
totals=dict(normal_equal=0,normal_different=0,boundary_equal=0,boundary_different=0,
            boundary_with_self_pollution=0,NOA_cases=0,NOA_different=0)
examples=[]
for i in range(10000):
    boundary=i>=5000
    ego=car(0,rng.uniform(350.,950.),rng.randrange(3),rng.uniform(15.,31.))
    # Distinct longitudinal lattice points; these are snapshots, not collision-free trajectories.
    points=rng.sample([(dx,l) for dx in (-90.,-60.,-30.,15.,45.,75.,120.,180.) for l in range(3)],rng.randrange(3,12))
    rows=tuple(car(j+1,ego.x+dx,l,rng.uniform(15.,31.)) for j,(dx,l) in enumerate(points))
    if boundary:
        ego=replace(ego,y=ego.y+rng.choice((0.,-.9,.9,-1.5,1.5)),vy=rng.choice((0.,0.,-.05,.05,-.2,.2)))
        rows=tuple(replace(c,y=c.y+rng.choice((0.,0.,-.9,.9,-1.5,1.5)),
                           vy=rng.choice((0.,0.,-.05,.05,-.2,.2))) for c in rows)
    mode=rng.choice(('transform','transform','formation','noa'))
    drop=rng.choice((None,1000.))
    memory=d1.Memory()
    if i==5000:
        ego=replace(car(0,625.,1),y=3.3)
        rows=(car(1,640.,0),car(2,640.,2),car(3,670.,2))
        mode,drop='transform',1000.
    events.clear()
    original=d0.decide(ego,rows,memory,mode,drop)
    corrected=d1.decide(ego,rows,memory,mode,drop)
    differs=exact(original)!=exact(corrected)
    prefix='boundary' if boundary else 'normal'
    totals[prefix+('_different' if differs else '_equal')]+=1
    if boundary and events:totals['boundary_with_self_pollution']+=1
    if mode=='noa':
        totals['NOA_cases']+=1
        totals['NOA_different']+=int(differs)
    if differs:
        assert boundary and events,('Non-self-member difference',i,original,corrected)
        if len(examples)<8:
            examples.append(dict(index=i,mode=mode,drop_x=drop,ego=asdict(ego),rows=[asdict(c) for c in rows],
                                 D0=exact(original),D1=exact(corrected),self_member_events=list(events)))
assert totals['normal_different']==0
assert totals['normal_equal']==5000
assert totals['boundary_different']>0
assert totals['NOA_different']==0
result=dict(seed=202611032102,snapshots=10000,totals=totals,
            assertion='Every changed command/memory snapshot had a measured off-center candidate included as its own target-gap member in D0; no all-state equality claim.',
            qualification='Local state samples only; not traffic rollouts or collision-free trajectory proof.',examples=examples)
(DOC/'D0_D1_10000_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='examples'},ensure_ascii=False))
