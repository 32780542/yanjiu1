"""B capacity matched organization references; static snapshots, no traffic."""
from dataclasses import asdict, replace
import ast
import importlib.util
import inspect
import itertools
import os
from pathlib import Path
import random
import sys
import subprocess
import types
import hashlib
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py'
FROZEN = subprocess.run(['git','show','1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py'],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
assert hashlib.sha256(FROZEN).hexdigest() == '8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


s = types.ModuleType('capacity_frozen_S')
sys.modules[s.__name__] = s
exec(compile(FROZEN.decode('utf-8'),'frozen_S', 'exec'),s.__dict__)
r = load('capacity_candidate', os.environ.get('RULES_B', BASE))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane+.5)*r.LANE_WIDTH, speed, lane)


def exact(value):
    if hasattr(value, '__dataclass_fields__'):
        return exact(asdict(value))
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {k: exact(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)):
        return [exact(v) for v in value]
    return value


def phase(car):
    options = {'transition':640.} if 'transition' in inspect.signature(r._physical_phase).parameters else {}
    return r._physical_phase(car, 3, **options)


class CapacitySpacingTests(unittest.TestCase):
    def test_upstream_45_and_22point5_are_cruise_equilibrium(self):
        ego,rows=car(0,400.,0),(car(1,445.,0),car(2,377.5,1))
        old,_=s.decide(ego,rows,s.Memory(joining=True),'transform')
        self.assertGreater(old.speed,ego.speed)
        command,_=r.decide(ego,rows,r.Memory(joining=True),'transform')
        self.assertEqual(command.speed,28.8)
        self.assertEqual(command.target_x,400.)
        self.assertEqual(command.reference,1)

    def test_after_transition_original_30_and_15_equilibrium(self):
        ego,rows=car(0,700.,0),(car(1,730.,0),car(2,685.,1))
        self.assertEqual(exact(r.decide(ego,rows,r.Memory(joining=True),'transform')),
                         exact(s.decide(ego,rows,s.Memory(joining=True),'transform')))
        self.assertEqual(r.decide(ego,rows,r.Memory(joining=True),'transform')[0].speed,28.8)

    def test_phase_is_own_actual_position_and_jumps_7point5_at_640(self):
        upstream=car(1,639.999999,1)
        downstream=replace(upstream,x=640.)
        self.assertAlmostEqual(phase(upstream),22.5)
        self.assertAlmostEqual(phase(downstream),15.)
        self.assertAlmostEqual(phase(upstream)-phase(downstream),7.5)
        other=car(2,650.,0)
        options={'transition':640.} if 'transition' in inspect.signature(r._pair_error).parameters else {}
        a=r._pair_error(other,upstream,3,640.,**options)[0]
        b=r._pair_error(upstream,other,3,640.,**options)[0]
        self.assertAlmostEqual(a,upstream.x-other.x+22.5)
        self.assertEqual(a,-b)

    def test_single_missing_layer_bridge_uses_90m_and_actual_witness(self):
        ego,front,witness=car(0,400.,0),car(1,490.,0),car(2,422.5,1)
        command,_=r.decide(ego,(front,witness),r.Memory(joining=True),'transform')
        self.assertEqual(command.reference,1)
        self.assertEqual(command.target_x,445.)
        without,_=r.decide(ego,(front,),r.Memory(joining=True),'transform')
        self.assertIsNone(without.reference)
        farther=replace(front,x=490.01)
        self.assertIsNone(r.decide(ego,(farther,witness),r.Memory(joining=True),'transform')[0].reference)

    def test_capacity_full_layer_is_protected_by_fill_at_ego_scale(self):
        ego=car(0,400.,1)
        rows=(car(1,422.5,0),car(2,422.5,2),car(3,332.5,0),car(4,377.5,1))
        self.assertEqual(s.decide(ego,rows,s.Memory(),'transform')[0].lane,2)
        command,_=r.decide(ego,rows,r.Memory(),'transform')
        self.assertIsNone(command.lane)
        self.assertEqual(command.speed,28.8)

    def test_transition_comes_from_public_map_not_fixed_640(self):
        ego,rows=car(0,750.,0),(car(1,795.,0),car(2,727.5,1))
        command,_=r.decide(ego,rows,r.Memory(joining=True),'transform',1200.)
        self.assertEqual(command.speed,28.8)
        self.assertEqual(command.target_x,750.)

    def test_noa_formation_straight_are_bit_exact_for_1000_states(self):
        rng=random.Random(1103)
        for i in range(1000):
            ego=replace(car(0,rng.uniform(200,1100),rng.randrange(3),rng.uniform(0,33.3)),
                        vy=rng.choice((0.,0.,-.2,.2)),pending_lane=rng.choice((None,None,1)))
            rows=tuple(car(j+1,ego.x+rng.uniform(-130,230),rng.randrange(3),rng.uniform(0,33.3)) for j in range(rng.randrange(9)))
            memory=r.Memory(rng.choice((None,0,1,2)),rng.choice((None,(1,None),(2,1))),rng.choice((False,True)))
            for mode,drop in (('noa',1000.),('formation',1000.),('transform',None),('noa',None),('formation',None)):
                with self.subTest(i=i,mode=mode,drop=drop):
                    self.assertEqual(exact(r.decide(ego,rows,memory,mode,drop)),exact(s.decide(ego,rows,memory,mode,drop)))
            self.assertEqual(r.safe_speed(ego,rows).hex(),s.safe_speed(ego,rows).hex())
            self.assertEqual(r.cf_speed(ego,rows).hex(),s.cf_speed(ego,rows).hex())

    def test_labels_permutations_and_outside_observation_do_not_interfere(self):
        ego=car(0,400.,0)
        rows=(car(1,445.,0),car(2,377.5,1),car(3,422.5,2),car(4,355.,0))
        baseline=r.decide(ego,rows,r.Memory(joining=True),'transform')
        for order in itertools.permutations(rows):
            self.assertEqual(exact(r.decide(ego,order,r.Memory(joining=True),'transform')),exact(baseline))
        mapping={0:91,1:22,2:333,3:7,4:81}
        renamed=r.decide(replace(ego,track=mapping[0]),tuple(replace(c,track=mapping[c.track]) for c in rows),r.Memory(joining=True),'transform')
        self.assertEqual(renamed[0].speed.hex(),baseline[0].speed.hex())
        self.assertEqual(renamed[0].target_x,baseline[0].target_x)
        self.assertEqual(renamed[0].reference,mapping[baseline[0].reference])
        invisible=(car(100,ego.x-100.01,1),car(101,ego.x+200.01,2))
        self.assertEqual(exact(r.decide(ego,rows+invisible,r.Memory(joining=True),'transform')),exact(baseline))

    def test_physical_and_gap_execution_functions_remain_literal_S(self):
        before={n.name:ast.dump(n) for n in ast.parse(FROZEN.decode('utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        path=Path(os.environ.get('RULES_B',BASE))
        after={n.name:ast.dump(n) for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name in ('Vehicle','Memory','Command','_occupies','_clear','_request','_merge_target','_join_speed','cf_speed','safe_speed','decide','_mandatory_priority'):
            self.assertEqual(before[name],after[name],name)


if __name__=='__main__':
    unittest.main()
