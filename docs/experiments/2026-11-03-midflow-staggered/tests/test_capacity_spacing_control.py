"""BC: same capacity references without active staggered organization."""
from dataclasses import asdict,replace
import ast
import importlib.util
import itertools
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
BPATH=ROOT/'tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py'


def load(name,path=None,text=None):
    if path is not None:
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec)
    else:
        import types
        module=types.ModuleType(name)
    sys.modules[name]=module
    if text is not None:exec(compile(text,name,'exec'),module.__dict__)
    else:spec.loader.exec_module(module)
    return module


frozen=subprocess.run(['git','show','1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py'],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
import hashlib
assert hashlib.sha256(frozen).hexdigest()=='8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'
assert hashlib.sha256(BPATH.read_bytes()).hexdigest()=='7d749ba8919efbf06efc0abd43846dee4c13b886e81019ae89c0f0116a1553d2'
s=load('BC_frozen_S',text=frozen.decode('utf-8'))
b=load('BC_frozen_B',BPATH)
r=load('BC_candidate',Path(os.environ.get('RULES_BC',BPATH)))


def car(i,x,l,v=28.8):return r.Vehicle(i,x,(l+.5)*r.LANE_WIDTH,v,l)


def exact(value):
    if hasattr(value,'__dataclass_fields__'):return exact(asdict(value))
    if isinstance(value,float):return value.hex()
    if isinstance(value,dict):return {k:exact(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [exact(v) for v in value]
    return value


class CapacityControlTests(unittest.TestCase):
    def test_no_phase_speed_with_same_capacity_CTH(self):
        ego,rows=car(0,400.,0),(car(1,390.,1),)
        for drop in (None,1000.):
            self.assertGreater(b.decide(ego,rows,b.Memory(),'transform',drop)[0].speed,ego.speed)
            command,_=r.decide(ego,rows,r.Memory(),'transform',drop)
            self.assertEqual(command.speed,28.8)
            self.assertEqual(command.formation_state,0)

    def test_no_free_fill_but_keep_normal_following(self):
        ego=car(0,400.,1)
        for drop,front_x,scale in ((1000.,422.5,1.5),(None,415.,1.)):
            rows=(car(1,355.,0),car(2,front_x,1))
            self.assertEqual(b.decide(ego,rows,b.Memory(),'transform',drop)[0].reason,'fill_layer')
            command,_=r.decide(ego,rows,r.Memory(),'transform',drop)
            self.assertIsNone(command.lane)
            self.assertNotEqual(command.reason,'fill_layer')
            self.assertEqual(command.speed,r._front_following(ego,rows,scale=scale)[0])
            self.assertEqual(command.formation_state,0)

    def test_normal_NOA_overtake_is_enabled_in_transform(self):
        ego=car(0,400.,1,20.)
        rows=(car(1,420.,1,20.),car(2,600.,0),car(3,450.,2))
        for drop,scale in ((None,1.),(1000.,1.5)):
            self.assertNotEqual(b.decide(ego,rows,b.Memory(),'transform',drop)[0].reason,'normal_overtake')
            command,_=r.decide(ego,rows,r.Memory(),'transform',drop)
            self.assertEqual(command.reason,'normal_overtake')
            self.assertEqual(command.lane,0)
            self.assertEqual(command.formation_state,0)
            self.assertEqual(command.speed,r._front_following(ego,rows,scale=scale)[0])

    def test_mandatory_merge_and_existing_own_action_keep_real_gap_execution(self):
        rows=(car(1,690.,1),car(2,770.,1))
        cases=((car(0,705.,2),r.Memory()),
               (replace(car(0,705.,2),vy=-.2),r.Memory(lane_target=1,gap=(2,1),joining=True)),
               (replace(car(0,705.,2),pending_lane=1),r.Memory(lane_target=1,gap=(2,1),joining=True)))
        for ego,memory in cases:
            original,old_memory=b.decide(ego,rows,memory,'transform')
            command,new_memory=r.decide(ego,rows,memory,'transform')
            self.assertEqual(exact(command),exact(replace(original,formation_state=0)))
            self.assertEqual(exact(new_memory),exact(old_memory))

    def test_same_45m_base_CTH_and_90m_sidewitness_association(self):
        ego=car(0,400.,0)
        for rows,distance in (((car(1,445.,0),car(2,377.5,1)),50.),
                              ((car(1,490.,0),car(2,422.5,1)),90.)):
            command,_=r.decide(ego,rows,r.Memory(joining=True),'transform')
            base=b._front_following(ego,rows,distance,1.5)
            self.assertEqual(command.speed,base[0])
            self.assertEqual(command.target_x,base[1])
            self.assertEqual(command.reference,base[2])
        without,_=r.decide(ego,(car(1,490.,0),),r.Memory(joining=True),'transform')
        self.assertIsNone(without.reference)

    def test_NOA_and_physical_safe_are_hex_exact_1000_states_and_all_states_zero(self):
        rng=random.Random(11031)
        for i in range(1000):
            ego=replace(car(0,rng.uniform(200,1100),rng.randrange(3),rng.uniform(0,33.3)),
                        vy=rng.choice((0.,0.,-.2,.2)),pending_lane=rng.choice((None,None,1)))
            rows=tuple(car(j+1,ego.x+rng.uniform(-130,230),rng.randrange(3),rng.uniform(0,33.3)) for j in range(rng.randrange(9)))
            memory=r.Memory(rng.choice((None,0,1,2)),rng.choice((None,(1,None),(2,1))),rng.choice((False,True)))
            for drop in (None,1000.):
                self.assertEqual(exact(r.decide(ego,rows,memory,'noa',drop)),exact(s.decide(ego,rows,memory,'noa',drop)))
                for mode in ('noa','formation','transform'):
                    self.assertEqual(r.decide(ego,rows,memory,mode,drop)[0].formation_state,0)
            self.assertEqual(r.safe_speed(ego,rows).hex(),s.safe_speed(ego,rows).hex())
            self.assertEqual(r.cf_speed(ego,rows).hex(),s.cf_speed(ego,rows).hex())

    def test_labels_permutations_and_observation_boundary(self):
        ego=car(0,400.,1,20.)
        rows=(car(1,420.,1,20.),car(2,600.,0),car(3,450.,2))
        baseline=r.decide(ego,rows,r.Memory(),'transform')
        for order in itertools.permutations(rows):
            self.assertEqual(exact(r.decide(ego,order,r.Memory(),'transform')),exact(baseline))
        mapping={0:912,1:33,2:8,3:400}
        renamed=r.decide(replace(ego,track=mapping[0]),tuple(replace(c,track=mapping[c.track]) for c in rows),r.Memory(),'transform')
        expected=replace(baseline[0],reference=mapping[baseline[0].reference] if baseline[0].reference is not None else None)
        self.assertEqual(exact(renamed[0]),exact(expected))
        invisible=(car(100,299.99,2),car(101,600.01,1))
        self.assertEqual(exact(r.decide(ego,rows+invisible,r.Memory(),'transform')),exact(baseline))

    def test_ordinary_gap_and_physical_execution_functions_literal_B(self):
        before={n.name:ast.dump(n) for n in ast.parse(BPATH.read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        path=Path(os.environ.get('RULES_BC',BPATH))
        after={n.name:ast.dump(n) for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name in ('Vehicle','Memory','Command','_occupies','_clear','_request','_merge_target','_join_speed','cf_speed','safe_speed','decide','_mandatory_priority','_front_following'):
            self.assertEqual(before[name],after[name],name)


if __name__=='__main__':unittest.main()
