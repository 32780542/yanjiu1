"""D static physical contracts; fixed frozen oracles, no traffic."""
from dataclasses import asdict,replace
import ast
import hashlib
import importlib.util
import itertools
import os
from pathlib import Path
import random
import subprocess
import sys
import types
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
BLOB='1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py'
RAW=subprocess.check_output(['git','show',BLOB],cwd=ROOT)
assert hashlib.sha256(RAW).hexdigest()=='8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'


def load(name,path=None,text=None):
    if path:
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec)
    else:module=types.ModuleType(name)
    sys.modules[name]=module
    if text is not None:exec(compile(text,name,'exec'),module.__dict__)
    else:spec.loader.exec_module(module)
    return module


s=load('D_frozen_S',text=RAW.decode('utf-8'))
r=load('D_candidate',os.environ.get('RULES_D'),None if os.environ.get('RULES_D') else RAW.decode('utf-8'))
F2=ROOT/'tmp/staggered_bottleneck/candidates/midflow_future_resources_v2/native_rules.py'
assert hashlib.sha256(F2.read_bytes()).hexdigest()=='d07c82501e3e86ce06529779b9c0bacd9469fd9654cc43c6dcd1c81bb21f8be4'
f2=load('D_frozen_F2',F2)


def car(i,x,l,v=28.8):return r.Vehicle(i,x,(l+.5)*r.LANE_WIDTH,v,l)


def exact(v):
    if hasattr(v,'__dataclass_fields__'):return exact(asdict(v))
    if isinstance(v,float):return v.hex()
    if isinstance(v,dict):return {k:exact(w) for k,w in v.items()}
    if isinstance(v,(tuple,list)):return [exact(w) for w in v]
    return v


def full_scene():
    ego=car(0,685.,1)
    points=[(x,l) for x in (640.,670.,700.) for l in (0,2)]
    points += [(625.,1),(655.,1),(730.,0),(610.,0),(610.,2)]
    return ego,tuple(car(i+1,x,l) for i,(x,l) in enumerate(points))


def receiving_scene():
    return car(0,625.,1),(car(1,640.,0),car(2,640.,2),car(3,670.,2))


class RealGapBalanceTests(unittest.TestCase):
    def test_complete_actual_layers_no_longer_freeze_future_balance(self):
        ego,rows=full_scene()
        self.assertIsNone(s.decide(ego,rows,s.Memory(),'transform')[0].lane)
        self.assertIsNone(f2.decide(ego,rows,f2.Memory(),'transform')[0].lane)
        command,memory=r.decide(ego,rows,r.Memory(),'transform')
        self.assertEqual(command.lane,0)
        self.assertEqual(command.reason,'fill_layer')
        self.assertTrue(r._clear(ego,rows,0))
        target,speed,gap=r._merge_target(ego,rows,0)
        self.assertEqual(command.target_x,target)
        self.assertEqual(memory.gap,gap)
        self.assertEqual(target,685.)
        self.assertEqual(sum(x*x for x in (5,7)),74)
        self.assertEqual(sum(x*x for x in (6,6)),72)

    def test_formation_keeps_original_prepare_navigation_out_of_ending_lane(self):
        ego,rows=car(0,730.,1),(car(1,700.,1),)
        command,_=r.decide(ego,rows,r.Memory(),'formation')
        self.assertEqual(command.lane,0)

    def test_visible_ending_vehicle_triggers_receiving_before_ego_preparation(self):
        ego,rows=receiving_scene()
        self.assertLess(ego.x,640.)
        self.assertIsNone(s.decide(ego,rows,s.Memory(),'transform')[0].lane)
        self.assertIsNone(f2.decide(ego,rows,f2.Memory(),'transform')[0].lane)
        command,_=r.decide(ego,rows,r.Memory(),'transform')
        self.assertEqual(command.lane,0)
        ending=car(9,625.,2)
        self.assertNotEqual(r.decide(ending,rows,r.Memory(),'transform')[0].reason,'merge')

    def test_receiving_cancels_only_not_started_entry_to_ending_lane(self):
        ego,rows=receiving_scene()
        memory=r.Memory(lane_target=2,joining=True)
        command,changed=r.decide(ego,rows,memory,'transform')
        self.assertEqual(command.lane,0)
        self.assertEqual(changed.lane_target,0)
        for active in (replace(ego,vy=.2),replace(ego,pending_lane=2)):
            command,changed=r.decide(active,rows,memory,'transform')
            self.assertEqual(command.lane,2)
            self.assertEqual(changed.lane_target,2)

    def test_measured_motion_counts_once_in_destination_and_prevents_next_transfer(self):
        ego,rows=receiving_scene()
        moving=replace(car(4,580.,1),y=4.75,vy=-.2)
        stationary=replace(moving,vy=0.)
        self.assertEqual(r.decide(ego,rows+(stationary,),r.Memory(),'transform')[0].lane,0)
        self.assertIsNone(r.decide(ego,rows+(moving,),r.Memory(),'transform')[0].lane)
        self.assertTrue(r._clear(ego,rows+(moving,),0))
        # Neighbors' pending state cannot stand in for measured y/vy.
        fake=tuple(replace(c,pending_lane=0) for c in rows+(moving,))
        self.assertEqual(exact(r.decide(ego,fake,r.Memory(),'transform')),
                         exact(r.decide(ego,rows+(moving,),r.Memory(),'transform')))

    def test_balanced_actual_groups_do_not_move_at_45_or_24m_spacing(self):
        for spacing in (45.,24.):
            ego=car(0,500.,1)
            points=((500.+spacing/2,0),(500.+spacing/2,2),(500.-spacing/2,0),
                    (500.-spacing/2,2),(500.-spacing,1))
            rows=tuple(car(i+1,x,l) for i,(x,l) in enumerate(points))
            for mode in ('formation','transform'):
                self.assertIsNone(r.decide(ego,rows,r.Memory(),mode,None)[0].lane)

    def test_physical_obstruction_still_blocks_chosen_transfer(self):
        ego,rows=receiving_scene()
        command,_=r.decide(ego,rows+(car(90,629.,0),),r.Memory(),'transform')
        self.assertIsNone(command.lane)

    def test_NOA_safe_and_public_CF_are_exact_1000_states(self):
        rng=random.Random(11032)
        for i in range(1000):
            ego=replace(car(0,rng.uniform(200,1100),rng.randrange(3),rng.uniform(0,33.3)),
                        vy=rng.choice((0.,0.,-.2,.2)),pending_lane=rng.choice((None,None,1)))
            rows=tuple(car(j+1,ego.x+rng.uniform(-130,230),rng.randrange(3),rng.uniform(0,33.3)) for j in range(rng.randrange(9)))
            memory=r.Memory(rng.choice((None,0,1,2)),rng.choice((None,(1,None),(2,1))),rng.choice((False,True)))
            for drop in (None,1000.):
                self.assertEqual(exact(r.decide(ego,rows,memory,'noa',drop)),exact(s.decide(ego,rows,memory,'noa',drop)))
            self.assertEqual(r.safe_speed(ego,rows).hex(),s.safe_speed(ego,rows).hex())
            self.assertEqual(r.cf_speed(ego,rows).hex(),s.cf_speed(ego,rows).hex())

    def test_labels_permutations_and_outside_observation_do_not_interfere(self):
        ego,rows=receiving_scene()
        expected,memory=r.decide(ego,rows,r.Memory(),'transform')
        mapping={0:915,1:22,2:144,3:8}
        for order in itertools.permutations(rows):
            command,changed=r.decide(replace(ego,track=mapping[0]),tuple(replace(c,track=mapping[c.track]) for c in order),r.Memory(),'transform')
            self.assertEqual(exact(command),exact(replace(expected,reference=mapping[expected.reference] if expected.reference is not None else None)))
            gap=tuple(None if k is None else mapping[k] for k in memory.gap) if memory.gap is not None else None
            self.assertEqual(changed.gap,gap)
        outside=(car(99,ego.x-100.01,2),car(100,ego.x+200.01,0))
        self.assertEqual(exact(r.decide(ego,rows+outside,r.Memory(),'transform')),exact((expected,memory)))

    def test_core_functions_and_public_response_cost_are_literal_S(self):
        before=ast.parse(RAW.decode('utf-8'))
        text=Path(os.environ['RULES_D']).read_text(encoding='utf-8') if os.environ.get('RULES_D') else RAW.decode('utf-8')
        after=ast.parse(text)
        old={n.name:ast.dump(n) for n in before.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        new={n.name:ast.dump(n) for n in after.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name in old.keys()-{'_fill','_decide'}:self.assertEqual(old[name],new[name],name)
        for tree in (before,after):
            fill=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_fill')
            nested={n.name:ast.dump(n) for n in fill.body if isinstance(n,ast.FunctionDef)}
            if tree is before:cost=nested
            else:
                self.assertEqual(nested['response_cost'],cost['response_cost'])
                self.assertEqual(nested['cf_cached'],cost['cf_cached'])


if __name__=='__main__':unittest.main()
