from dataclasses import asdict, replace
import importlib.util
import hashlib
from pathlib import Path
import random
import sys
import unittest
from archived_rules_source import load_state_enabled_base

P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from noa import native_rules as r
H_SOURCE=P.parents[1]/'docs/experiments/2026-10-29-four-flow-attribution/portable_H/source/noa/native_rules.py'
assert hashlib.sha256(H_SOURCE.read_bytes()).hexdigest()=='77c0111530560db30e97dc466bcdaf276a78cb7dd7192767e9a2d51b97eab2d2'
spec=importlib.util.spec_from_file_location('P_H_reference',H_SOURCE)
H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)


class CommonPairHeadTests(unittest.TestCase):
    def car(self,x,lane,track=0,speed=28.8):return r.Vehicle(track,x,(lane+.5)*3.3,speed,lane)

    def pair(self,a,b,lanes,boundary):
        self.assertTrue(hasattr(r,'_pair_error'),'missing common pair configuration')
        return r._pair_error(a,b,lanes,boundary)

    def test_cross_boundary_pair_uses_same_raw_and_normalized_geometry_both_ways(self):
        for boundary in [640.,1000.]:
            a,b=self.car(boundary-10,1),self.car(boundary+10,0,1)
            ab,na=self.pair(a,b,3,boundary);ba,nb=self.pair(b,a,2,boundary)
            self.assertEqual((na,nb),(3,3));self.assertEqual(ab,-ba)
            self.assertEqual(ab/(na-1),-ba/(nb-1))
            a=replace(a,x=boundary+1)
            self.assertEqual(self.pair(a,b,3,boundary)[1],2)

    def test_straight_and_outside_phase_geometry_matches_H(self):
        for x,lanes,boundary in [(400.,3,None),(400.,3,640.),(1100.,2,640.)]:
            a,b=self.car(x,0),self.car(x+12,1,1)
            error,count=self.pair(a,b,lanes,boundary)
            expected=(b.x+H._physical_phase(b,lanes))-(a.x+H._physical_phase(a,lanes))
            self.assertEqual(count,lanes);self.assertAlmostEqual(error,expected)

    def test_mode_dispatch_uses_640_for_transform_and_1000_for_formation(self):
        self.pair(self.car(650,1),self.car(670,0,1),2,640.)
        a,b=self.car(650,1),self.car(670,0,1)
        formation=r.decide(a,(b,),r.Memory(),'formation',1000.)[0]
        transform=r.decide(a,(b,),r.Memory(),'transform',1000.)[0]
        self.assertAlmostEqual(formation.speed,28.95)
        self.assertAlmostEqual(transform.speed,29.2)
        a,b=self.car(630,1),self.car(650,0,1)
        ca=r.decide(a,(b,),r.Memory(),'transform',1000.)[0]
        cb=r.decide(b,(a,),r.Memory(),'transform',1000.)[0]
        self.assertAlmostEqual(ca.speed-r.CRUISE,-(cb.speed-r.CRUISE))
        self.assertAlmostEqual(ca.speed-r.CRUISE,.15)

    def test_near_rear_never_adds_free_head_speed_without_a_peer(self):
        ego=self.car(100,0)
        for gap in [15.,30.,45.,70.]:
            speed,target,reference,_=r._following(ego,(self.car(100-gap,0,1),),3)
            self.assertEqual(target,ego.x);self.assertIsNone(reference)
            self.assertAlmostEqual(speed,r.CRUISE)
        self.assertEqual(r._following(ego,(),3),(r.CRUISE,ego.x,None,0))

    def test_compressed_rear_does_not_change_the_head_phase_action(self):
        ego,peer,rear=self.car(100,0),self.car(100,1,1),self.car(85,0,2)
        speed,target,_,_=r._following(ego,(peer,rear),3)
        without,old_target,_,_=r._following(ego,(peer,),3)
        self.assertEqual(target,old_target)
        self.assertLessEqual(abs(r.POSITION_GAIN*(target-ego.x)),2.+1e-9)
        self.assertAlmostEqual(speed,without)

    def test_nearest_search_and_head_action_use_the_same_common_pair_configuration(self):
        self.pair(self.car(650,0),self.car(630,1,1),2,640.)
        ego=self.car(650,0)
        behind=self.car(630,1,99)
        ahead=self.car(681,1,1)
        # Both are actual heads,51m apart. Common geometry selects the630m head.
        speed,target,reference,state=r._following(ego,(behind,ahead),2,phase_boundary=640.)
        self.assertAlmostEqual(target,647.5)
        self.assertAlmostEqual(speed,28.65)
        self.assertIsNone(reference)
        changed=(replace(ahead,track=99),replace(behind,track=1))
        self.assertEqual((speed,target,reference,state),r._following(ego,changed,2,phase_boundary=640.))

    def test_all_actual_front_body_actions_remain_H_exact(self):
        """Historical P/state-only refactor contract, before time-headway trials."""
        archived=load_state_enabled_base('common_pair_body')
        car=lambda x,lane,track=0,speed=28.8: archived.Vehicle(track,x,(lane+.5)*3.3,speed,lane)
        rng=random.Random(600)
        for mode in ['formation','transform']:
            for _ in range(80):
                ego=car(rng.uniform(100,1100),rng.randrange(3),speed=rng.uniform(10,32))
                front=car(ego.x+rng.uniform(8,45),ego.lane,1,speed=rng.uniform(10,32))
                rear=car(ego.x-15,ego.lane,2)
                peers=[car(ego.x+rng.uniform(-40,40),rng.randrange(3),i+3) for i in range(3)]
                rows=(front,rear,*peers)
                a,m=archived.decide(ego,rows,archived.Memory(),mode,1000.)
                b,n=H.decide(H.Vehicle(**asdict(ego)),tuple(H.Vehicle(**asdict(c)) for c in rows),H.Memory(),mode,1000.)
                control=asdict(a);control.pop('formation_state')
                self.assertEqual((control,asdict(m)),(asdict(b),asdict(n)))

    def test_NOA_is_unchanged_even_with_compressed_rears(self):
        """Historical P/state-only NOA contract, not a claim about new following."""
        archived=load_state_enabled_base('common_pair_noa')
        car=lambda x,lane,track=0,speed=28.8: archived.Vehicle(track,x,(lane+.5)*3.3,speed,lane)
        rng=random.Random(800)
        for _ in range(160):
            ego=car(rng.uniform(0,1100),rng.randrange(3),speed=rng.uniform(0,33.3))
            rows=(car(ego.x-15,ego.lane,1),)+tuple(car(ego.x+rng.uniform(-100,200),rng.randrange(3),i+2) for i in range(5))
            a,m=archived.decide(ego,rows,archived.Memory(),'noa',1000.)
            b,n=H.decide(H.Vehicle(**asdict(ego)),tuple(H.Vehicle(**asdict(c)) for c in rows),H.Memory(),'noa',1000.)
            control=asdict(a);control.pop('formation_state')
            self.assertEqual((control,asdict(m)),(asdict(b),asdict(n)))

    def test_compressed_free_head_still_obeys_visible_stopped_front_safety_cap(self):
        ego=self.car(100,0,speed=33.3)
        rows=(self.car(85,0,1,33.3),self.car(160.48,0,2,0.))
        action=r.decide(ego,rows,r.Memory(),'formation',None)[0]
        self.assertLess(r.safe_speed(ego,rows),r.MAX_SPEED)
        self.assertLessEqual(action.speed,r.safe_speed(ego,rows))


if __name__=='__main__':unittest.main()
