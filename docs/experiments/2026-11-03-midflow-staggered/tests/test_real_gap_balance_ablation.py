"""Single-line D1 ablations DR/DP, with frozen local and S oracles."""
from dataclasses import replace
import ast
import hashlib
import itertools
import os
from pathlib import Path
import random
import sys
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
PARENT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py'
assert hashlib.sha256(PARENT.read_bytes()).hexdigest()=='2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a'
os.environ['RULES_D']=str(PARENT)
from test_real_gap_balance import r as d1,s,load,exact,car,full_scene,receiving_scene

KIND=os.environ.get('ABLATION_KIND','DR')
assert KIND in ('DR','DP')
r=load('D1_ablation_'+KIND,os.environ.get('RULES_ABLATION',str(PARENT)))


class RealGapAblationTests(unittest.TestCase):
    def test_single_intended_source_line_only(self):
        parent=PARENT.read_text(encoding='utf-8')
        source=Path(os.environ.get('RULES_ABLATION',str(PARENT))).read_text(encoding='utf-8')
        if KIND=='DR':
            expected=parent.replace('        resource = min(resource, 1) if future else resource\n','')
        else:
            expected=parent.replace('    phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))','    phase_speed = 0.0')
        self.assertEqual(source,expected)

    @unittest.skipUnless(KIND=='DR','DR future mapping contract')
    def test_reactive_removes_only_anticipatory_ending_resource_load(self):
        for ego,rows in (receiving_scene(),full_scene()):
            self.assertEqual(d1.decide(ego,rows,d1.Memory(),'transform')[0].lane,0)
            self.assertIsNone(r.decide(ego,rows,r.Memory(),'transform')[0].lane)
        # Before measured movement starts, actual surviving loads are still balanced.
        ego,rows=receiving_scene()
        moving=replace(car(4,580.,1),y=4.75,vy=-.2)
        self.assertIsNone(r.decide(ego,rows+(moving,),r.Memory(),'transform')[0].lane)

    @unittest.skipUnless(KIND=='DP','DP longitudinal phase contract')
    def test_phase_speed_off_keeps_relationship_flag_and_active_lateral_organization(self):
        ego,rows=car(0,400.,0),(car(1,390.,1),)
        old,_=d1.decide(ego,rows,d1.Memory(),'transform')
        command,_=r.decide(ego,rows,r.Memory(),'transform')
        self.assertGreater(old.speed,28.8)
        self.assertEqual(command.speed,28.8)
        self.assertEqual(command.formation_state,old.formation_state)
        self.assertEqual(command.formation_state,1)
        for ego,rows in (receiving_scene(),full_scene()):
            self.assertEqual(exact(r.decide(ego,rows,r.Memory(),'transform')),
                             exact(d1.decide(ego,rows,d1.Memory(),'transform')))
        ego,rows=car(0,400.,1,20.),(car(1,420.,1,20.),car(2,600.,0),car(3,450.,2))
        self.assertNotEqual(r.decide(ego,rows,r.Memory(),'transform')[0].reason,'normal_overtake')

    def test_NOA_safe_and_public_CF_are_exact_1000_states(self):
        rng=random.Random(11039)
        for i in range(1000):
            ego=replace(car(0,rng.uniform(200,1100),rng.randrange(3),rng.uniform(0,33.3)),
                        vy=rng.choice((0.,0.,-.2,.2)),pending_lane=rng.choice((None,None,1)))
            rows=tuple(car(j+1,ego.x+rng.uniform(-130,230),rng.randrange(3),rng.uniform(0,33.3)) for j in range(rng.randrange(9)))
            memory=r.Memory(rng.choice((None,0,1,2)),rng.choice((None,(1,None),(2,1))),rng.choice((False,True)))
            for drop in (None,1000.):
                self.assertEqual(exact(r.decide(ego,rows,memory,'noa',drop)),exact(s.decide(ego,rows,memory,'noa',drop)))
            self.assertEqual(r.safe_speed(ego,rows).hex(),s.safe_speed(ego,rows).hex())
            self.assertEqual(r.cf_speed(ego,rows).hex(),s.cf_speed(ego,rows).hex())
            if KIND=='DR':
                for mode in ('formation','transform'):
                    self.assertEqual(exact(r.decide(ego,rows,memory,mode,None)),exact(d1.decide(ego,rows,memory,mode,None)))

    def test_ids_and_row_order_do_not_supply_priority(self):
        ego,rows=full_scene()
        expected,memory=r.decide(ego,rows,r.Memory(),'transform')
        rng=random.Random(3)
        for _ in range(24):
            order=list(rows);rng.shuffle(order)
            mapping={c.track:2000-13*c.track for c in (ego,*rows)}
            command,changed=r.decide(replace(ego,track=mapping[0]),tuple(replace(c,track=mapping[c.track]) for c in order),r.Memory(),'transform')
            expected_command=replace(expected,reference=mapping[expected.reference] if expected.reference is not None else None)
            self.assertEqual(exact(command),exact(expected_command))
            gap=tuple(None if x is None else mapping[x] for x in memory.gap) if memory.gap is not None else None
            self.assertEqual(changed.gap,gap)


if __name__=='__main__':unittest.main()
