"""Predeclared R5 mechanism fixtures; private entropy exists only at freeze time.

These cases are separate from the old method selection and heldout experiment.
The controller never receives this case registry, another actor's memory, or a
script. Adversarial duplicate/quantized streams are labelled, never re-sampled.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import secrets

from models.kinematic import KinematicModel, kinematic_state
from noa.formation import FormationMemory, memory_from_dict


SCHEMA = 'phase5_r5_cases_v1'


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                     allow_nan=False).encode('utf-8')).hexdigest()


def physical_cases(p):
    """Eight fixed physical fixtures; no performance query or random selection."""
    def state(x,lane,v,y=None):
        return asdict(kinematic_state(p,x_m=x,y_m=(lane+.5)*3.3 if y is None else y,vx_mps=v))
    def lead(x,lane):
        return state(x,lane,2.)
    def case(name,duration,initial,controlled,scripts,checks,purpose):
        return dict(name=name,kind='r5_mechanism',duration_s=float(duration),
                    initial=initial,controlled=controlled,scripts=scripts,requirements={},
                    r5_requirements=checks,purpose=purpose,illustrative_initial_condition=True)
    slow={'speed_steps':[[0.,2.]]}
    single=case('r5_single_clear',20,{'ego':state(250,0,8.),'lead':lead(310,0)},
                ['ego'],{'lead':slow},['no_random_draw','paired_disabled_actions_equal'],
                'One candidate with no nearby competing actor; old NOA thresholds remain active.')
    def pair(name,duration=20,speed=8.,offset=0.,lead_gap=60.,checks=None,purpose=''):
        initial={'left':state(250,0,speed),'right':state(250+offset,2,speed),
                 'lead_left':lead(250+lead_gap,0),'lead_right':lead(250+offset+lead_gap,2)}
        return case(name,duration,initial,['left','right'],
                    {'lead_left':{'speed_steps':[[0.,2.]]},'lead_right':{'speed_steps':[[0.,2.]]}},
                    checks or [],purpose)
    competing=pair('r5_competing',30,checks=['potential_competition','private_backoff',
                  'expiry_distinct_from_plan_start'],purpose='Two outer-lane actors can target the middle; no winner is prescribed.')
    floor=pair('r5_speed_floor',30,speed=5.,lead_gap=35.,checks=['private_backoff',
               'eligible_below_minimum_lane_change_speed'],purpose='Initial and target speed 5 m/s; deceleration may prevent a finite-window restart.')
    entered=case('r5_entered_priority',20,
                 {'ego':state(250,0,8.),'lead':lead(310,0),'peer':state(250,2,8.,y=6.7)},
                 ['ego'],{'lead':{'speed_steps':[[0.,2.]]},'peer':{'speed_steps':[[0.,8.]],
                     'lane_change':dict(start_s=0.,y_start_m=6.7,y_target_m=4.95,duration_s=5.,speed_mps=8.)}},
                 ['yield_entered'], 'A physically partly-entered actor follows only its own fixed lateral reference.')
    front=pair('r5_front_priority',20,offset=4.,checks=['yield_visible_front'],
               purpose='A visible 4 m longitudinal advantage exceeds the fixed 2 m priority margin.')
    reentry=case('r5_reentry',40,
                 {'ego':state(250,0,8.),'lead':lead(310,0),'peer':state(250,2,8.)},['ego'],
                 {'lead':{'speed_steps':[[0.,2.]]},'peer':{'speed_steps':[[0.,8.],[3.,14.],[12.,2.],[25.,8.]]}},
                 ['episode_clear_and_new_draw'],
                 'An exogenous own-speed excursion attempts exit and reentry; absence of a second episode is retained.')
    same=pair('r5_same_private_state',checks=['equal_initial_private_state','symmetry_boundary'],
              purpose='Adversarial identical private states; no forced uniqueness or ID tie break.')
    quantized=pair('r5_quantized_private_states',checks=['unequal_delays_same_behavior_tick'],
                  purpose='Adversarial initial states 1 and 2 give distinct delays in one initial 0.5 s event bin; later execution is observed.')
    return [single,competing,floor,entered,front,reentry,same,quantized]


def _valid_state(value):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError('Private state must be a uint64 integer, not bool')
    return value


def _physical(case):
    return {k:v for k,v in case.items() if k not in ('initial_memories','private_rng_provenance')}


def freeze_cases(path,p=None,entropy_draw=None):
    """Create one new JSON file, drawing once per ordinary controlled actor.

    entropy_draw is a no-argument test seam; production uses secrets.randbits(64).
    No uniqueness rejection is allowed. Existence is checked before any entropy.
    """
    path=Path(path)
    if path.exists():
        raise FileExistsError(path)
    p=dict(KinematicModel.from_config().p) if p is None else p
    draw=(lambda:secrets.randbits(64)) if entropy_draw is None else entropy_draw
    matrix=physical_cases(p)
    for case in matrix:
        special=case['name'] in ('r5_same_private_state','r5_quantized_private_states')
        states={}
        for index,actor in enumerate(case['controlled']):
            value=(1 if case['name']=='r5_same_private_state' else index+1) if special else draw()
            states[actor]=_valid_state(value)
        case['initial_memories']={actor:asdict(FormationMemory((),'CRUISE',r5_rng_state=value))
                                  for actor,value in states.items()}
        case['private_rng_provenance']={
            'algorithm':'SplitMix64','version':1,
            'source':'adversarial_fixed_private_state' if special else 'system_entropy_64bit',
            'states_by_actor':states,
            'independent_draws_requested':not special,
            'uniqueness_enforced':False,
            'online_initialization':False,
        }
    data=dict(schema=SCHEMA,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              model_parameters_sha256=_digest(p),physical_sha256=_digest([_physical(c) for c in matrix]),
              initial_state_sha256=_digest(matrix),cases=matrix)
    # Normalize immutable dataclass tuples to their actual persisted JSON schema.
    serialized=json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(serialized)
    return load_frozen_cases(path,p)


def load_frozen_cases(path,p=None):
    """Validate against this fixed generator, not only a self-reported hash."""
    p=dict(KinematicModel.from_config().p) if p is None else p
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema')!=SCHEMA:
        raise ValueError('Wrong R5 case schema')
    if data.get('generator_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('R5 case generator source changed')
    if data.get('model_parameters_sha256')!=_digest(p):
        raise ValueError('R5 initial model parameters changed')
    matrix=data.get('cases')
    if not isinstance(matrix,list) or len(matrix)!=8:
        raise ValueError('R5 complete fixed matrix required')
    physical=[_physical(c) for c in matrix]
    if _digest(physical)!=_digest(physical_cases(p)) or data.get('physical_sha256')!=_digest(physical):
        raise ValueError('R5 physical case or script changed')
    if data.get('initial_state_sha256')!=_digest(matrix):
        raise ValueError('R5 full initial state changed')
    for case in matrix:
        memories=case.get('initial_memories',{})
        if set(memories)!=set(case['controlled']):
            raise ValueError('Every controlled actor needs exactly its own memory')
        provenance=case.get('private_rng_provenance',{})
        special=case['name'] in ('r5_same_private_state','r5_quantized_private_states')
        if provenance.get('algorithm')!='SplitMix64' or type(provenance.get('version')) is not int or provenance.get('version')!=1 or \
           provenance.get('source')!=('adversarial_fixed_private_state' if special else 'system_entropy_64bit') or \
           provenance.get('independent_draws_requested') is not (not special) or \
           provenance.get('uniqueness_enforced') is not False or provenance.get('online_initialization') is not False:
            raise ValueError('Invalid private initialization provenance')
        states={}
        for index,actor in enumerate(case['controlled']):
            value=memories[actor]
            state=_valid_state(value.get('r5_rng_state'))
            if special and state!=(1 if case['name']=='r5_same_private_state' else index+1):
                raise ValueError('Adversarial private states changed')
            expected=asdict(FormationMemory((),'CRUISE',r5_rng_state=state))
            # Check persisted fields before a codec can fill missing defaults.
            if _digest(value)!=_digest(expected) or _digest(asdict(memory_from_dict(value)))!=_digest(expected):
                raise ValueError('R5 memory must start in the fixed unobserved idle state')
            states[actor]=state
        if provenance.get('states_by_actor')!=states:
            raise ValueError('Private state provenance mismatch')
    return matrix
