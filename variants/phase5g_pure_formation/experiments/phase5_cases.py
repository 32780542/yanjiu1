"""Predeclared continuous random initial conditions and exogenous own-speed events.

No fitted phase, slot allocation, or event schedule reaches an online controller.
The random rejection rule checks only initial physical spacing and lane coverage.
"""
from dataclasses import asdict
import random
from models.kinematic import kinematic_state
from research.common import settings


def cases(p):
    development=settings('phase5_experiments')
    def state(x,lane,v):
        return asdict(kinematic_state(p,x_m=x,y_m=(lane+.5)*3.3,vx_mps=v))
    result=[]
    seeds=development['phase5_random_seeds']
    if len(seeds)!=6 or len(set(seeds))!=6:
        raise ValueError('Require six distinct predeclared seeds')
    for count,seeds in zip((3,6,12),(seeds[:2],seeds[2:4],seeds[4:])):
        for seed in seeds:
            rng=random.Random(seed)
            initial={}
            attempts=0
            while len(initial)<count:
                attempts+=1
                if attempts>100000:
                    raise RuntimeError('Frozen initial feasibility rejection exhausted')
                lane=rng.randrange(3)
                x=rng.uniform(180,180+max(70,count*22))
                if any(s['y_m']==(lane+.5)*3.3 and abs(s['x_m']-x)<development['phase5_min_initial_same_lane_center_gap_m'] for s in initial.values()):
                    continue
                if len(initial)==count-1 and len({s['y_m'] for s in initial.values()}|{(lane+.5)*3.3})<2:
                    continue
                initial['v'+str(len(initial))]=state(x,lane,rng.uniform(4.5,5.5))
            result.append(dict(name=f'random_{count}_seed{seed}',kind='random',seed=seed,
                duration_s=development['phase5_random_duration_s'],initial=initial,controlled=list(initial),scripts={},requirements={},
                purpose='Continuous uniform rejection sample, no lattice initialization or successful-seed filtering',
                sampling=dict(x_min_m=180,x_max_m=180+max(70,count*22),same_lane_min_centers_m=development['phase5_min_initial_same_lane_center_gap_m'],
                    speed_range_mps=[4.5,5.5],attempts=attempts)))
    # Separate illustrative event fixtures, never counted as random initial evidence.
    for kind,duration,schedule,positions in (
        ('disturbance',80.,[[0,5],[20,8],[27,5]],[(250,0),(266,1),(280,0)]),
        ('visibility',80.,[[0,8],[25,2],[65,5]],[(250,0),(265,1),(460,0)]),
        ('nonrecovery',60.,[[0,5],[20,10]],[(250,0),(266,1),(280,0)])):
        initial={k:state(x,lane,5. if k!='event' else schedule[0][1])
                 for k,(x,lane) in zip(('rear','middle','event'),positions)}
        result.append(dict(name=kind,kind=kind,seed=5401,duration_s=duration,
            initial=initial,controlled=['rear','middle'],scripts={'event':{'speed_steps':schedule}},
            requirements={},purpose='Exogenous vehicle follows only its own frozen speed schedule; no coordination',
            event_start_s=20. if kind!='visibility' else 0.,event_release_s=27. if kind=='disturbance' else None,
            illustrative_initial_condition=True))
    perturbed=next(c for c in result if c['name']=='disturbance')
    result.append({**perturbed,'name':'disturbance_control','kind':'disturbance_control',
        'scripts':{'event':{'speed_steps':[[0,5],[20,5]]}},
        'purpose':'Matched own-speed no-pulse control for actual paired disturbance response'})
    return result
