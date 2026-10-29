from dataclasses import asdict,replace
import importlib.util
from pathlib import Path
import random
import sys
import unittest

PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from noa import native_rules as r
spec=importlib.util.spec_from_file_location('R_P_reference',PACKAGE.parent/'common_pair_P_release/noa/native_rules.py')
P=importlib.util.module_from_spec(spec);sys.modules[spec.name]=P;spec.loader.exec_module(P)


class LeaderFollowingTests(unittest.TestCase):
    def car(self,x,lane,track=0,speed=28.8):return r.Vehicle(track,x,(lane+.5)*3.3,speed,lane)

    def test_forward_projected_head_keeps_cruise_and_rear_head_accelerates(self):
        a,b=self.car(100,0),self.car(100,1,1)
        rear=r._following(a,(b,),3)
        leader=r._following(b,(a,),3)
        self.assertGreater(rear[0],r.CRUISE)
        self.assertEqual(leader,(r.CRUISE,b.x,None))

    def test_only_nearest_positive_projected_actual_head_is_selected(self):
        ego=self.car(100,1);a,b=self.car(120,0,1),self.car(130,2,2)
        speed,target,_=r._following(ego,(a,b),3)
        self.assertAlmostEqual(target,102.5)
        self.assertAlmostEqual(speed,28.95)

    def test_phase_anchor_must_be_centered_and_laterally_stable(self):
        ego=self.car(100,0);peer=self.car(100,1,1)
        for invalid in [replace(peer,y=peer.y+.151),replace(peer,vy=.101)]:
            self.assertEqual(r._following(ego,(invalid,),3),(r.CRUISE,ego.x,None))

    def test_moving_same_corridor_front_still_controls_following_and_safety(self):
        ego=self.car(100,0,speed=20)
        front=replace(self.car(120,1,1,0),y=3.3,vy=-3.3)
        actual=r._following(ego,(front,),3)
        expected=P._following(P.Vehicle(**asdict(ego)),(P.Vehicle(**asdict(front)),),3)
        self.assertEqual(actual,expected);self.assertEqual(actual[2],front.track)
        self.assertLess(r.safe_speed(ego,(front,)),ego.speed)
        self.assertEqual(r.safe_speed(ego,(front,)),P.safe_speed(ego,(front,)))

    def test_free_fill_does_not_relocate_a_head_but_body_can_fill(self):
        ego=self.car(285,0)
        head_rows=tuple(self.car(x,lane,i+1) for i,(x,lane) in enumerate([(300,2),(270,2),(255,1),(270,0),(240,0)]))
        self.assertEqual(P._fill(P.Vehicle(**asdict(ego)),tuple(P.Vehicle(**asdict(c)) for c in head_rows),3),1)
        self.assertIsNone(r._fill(ego,head_rows,3))
        body_rows=tuple(self.car(x,lane,i+1) for i,(x,lane) in enumerate([(300,2),(270,2),(255,1),(300,0),(270,0)]))
        self.assertEqual(r._fill(ego,body_rows,3),1)

    def test_necessary_helper_and_merge_remain_available_to_heads(self):
        cars=[self.car(x,lane,i) for i,(x,lane) in enumerate([(700,2),(670,2),(685,1),(655,1),(700,0),(670,0)])]
        ego=replace(cars[2],track=0);rows=tuple(replace(c,track=i+1) for i,c in enumerate(c for j,c in enumerate(cars) if j!=2))
        helper=r.decide(ego,rows,r.Memory(),'transform',1000.)[0]
        self.assertEqual((helper.reason,helper.lane),('make_room',0))
        merge=r.decide(self.car(700,2),(),r.Memory(),'transform',1000.)[0]
        self.assertEqual((merge.reason,merge.lane),('merge',1))

    def test_front_following_body_and_NOA_stay_P_equivalent(self):
        rng=random.Random(1515)
        for _ in range(600):
            ego=self.car(rng.uniform(0,1100),rng.randrange(3),speed=rng.uniform(0,33.3))
            front=self.car(ego.x+rng.uniform(8,45),ego.lane,1,rng.uniform(0,33.3))
            rows=(front,)+tuple(self.car(ego.x+rng.uniform(-100,200),rng.randrange(3),i+2) for i in range(6))
            a=r._following(ego,rows,3)
            b=P._following(P.Vehicle(**asdict(ego)),tuple(P.Vehicle(**asdict(c)) for c in rows),3)
            self.assertEqual(a,b)
            c,m=r.decide(ego,rows,r.Memory(),'noa',1000.)
            d,n=P.decide(P.Vehicle(**asdict(ego)),tuple(P.Vehicle(**asdict(c)) for c in rows),P.Memory(),'noa',1000.)
            self.assertEqual((asdict(c),asdict(m)),(asdict(d),asdict(n)))

    def test_common_frame_and_actual_ending_lane_pair_geometry_are_retained(self):
        for lane,x in [(0,630),(2,700)]:
            a,b=self.car(x,lane),self.car(x+20 if lane==0 else x,1,1)
            forward,count=r._pair_error(a,b,3,640.)
            backward,other=r._pair_error(b,a,2,640.)
            self.assertEqual(count,other);self.assertEqual(forward,-backward)
            self.assertEqual(count,3)
        ego,front,peer=self.car(700,2),self.car(770,2,1),self.car(700,1,2)
        action=r.decide(ego,(front,peer),r.Memory(),'transform',1000.)[0]
        self.assertEqual(action.reason,'ending_follower')
        self.assertGreater(action.speed,r.CRUISE)


if __name__=='__main__':unittest.main()
