from dataclasses import asdict,replace
import importlib.util
from pathlib import Path
import random
import sys
import unittest

PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from noa import native_rules as r
spec=importlib.util.spec_from_file_location('S_R_reference',PACKAGE.parent/'R_leader_following/noa/native_rules.py')
R=importlib.util.module_from_spec(spec);sys.modules[spec.name]=R;spec.loader.exec_module(R)


class LayerAnchorTests(unittest.TestCase):
    def car(self,x,lane,track=0,speed=28.8):return r.Vehicle(track,x,(lane+.5)*3.3,speed,lane)

    def test_body_uses_real_same_layer_root_anchor_without_dropping_front_reference(self):
        ego,front,root=self.car(100,0),self.car(130,0,1),self.car(110,2,2)
        speed,target,reference=r._following(ego,(front,root),3)
        self.assertEqual(reference,front.track)
        self.assertAlmostEqual(target,front.x-r.GAP+2/r.POSITION_GAIN)
        self.assertAlmostEqual(speed,r._request(ego,target,front.speed))
        self.assertGreater(speed,r.CRUISE)

    def test_root_vehicle_one_layer_away_is_not_a_same_layer_anchor(self):
        ego,front,root=self.car(100,0),self.car(130,0,1),self.car(130,2,2)
        self.assertEqual(r._following(ego,(front,root),3),(r.CRUISE,ego.x,front.track))

    def test_extra_rear_counts_never_invent_an_observed_same_layer(self):
        ego,front,root=self.car(100,0),self.car(130,0,1),self.car(130,2,2)
        rows=(front,root)+tuple(self.car(x,lane,i+3) for i,(x,lane) in enumerate([(70,0),(40,0),(10,0),(70,2),(40,2),(55,1),(25,1)]))
        self.assertEqual(r._following(ego,rows,3),(r.CRUISE,ego.x,front.track))

    def test_root_lane_body_receives_no_other_body_phase_feedback(self):
        ego,front=self.car(100,2),self.car(130,2,1)
        rows=(front,self.car(110,0,2),self.car(140,0,3))
        self.assertEqual(r._following(ego,rows,3),(r.CRUISE,ego.x,front.track))

    def test_unsettled_root_is_not_an_anchor_but_moving_actual_front_is_followed(self):
        ego,front,root=self.car(100,0),self.car(130,0,1),self.car(110,2,2)
        for peer in [replace(root,vy=.101),replace(root,y=root.y+.151)]:
            self.assertEqual(r._following(ego,(front,peer),3),(r.CRUISE,ego.x,front.track))
        moving=replace(self.car(120,1,1,0),y=3.3,vy=-3.3)
        ego=replace(ego,speed=20)
        actual=r._following(ego,(moving,),3)
        expected=R._following(R.Vehicle(**asdict(ego)),(R.Vehicle(**asdict(moving)),),3)
        self.assertEqual(actual,expected)
        self.assertLess(r.safe_speed(ego,(moving,)),ego.speed)

    def test_head_can_see_a_forward_actual_head_in_a_nonadjacent_lane(self):
        ego,root=self.car(100,0),self.car(110,2,1)
        speed,target,_=r._following(ego,(root,),3)
        self.assertAlmostEqual(target,105)
        self.assertAlmostEqual(speed,29.1)
        self.assertEqual(r._following(root,(ego,),3),(r.CRUISE,root.x,None))

    def test_perfect_lattices_remain_steady_in_three_and_two_lanes(self):
        for lanes,positions in [(3,[(100,2),(70,2),(85,1),(55,1),(100,0),(70,0)]),
                                (2,[(100,0),(70,0),(40,0),(115,1),(85,1),(55,1)])]:
            cars=[self.car(x,lane,i) for i,(x,lane) in enumerate(positions)]
            for ego in cars:
                speed,target,_=r._following(ego,tuple(c for c in cars if c.track!=ego.track),lanes)
                self.assertAlmostEqual(speed,r.CRUISE);self.assertAlmostEqual(target,ego.x)

    def test_NOA_600_general_local_states_keep_R_actions_and_memory(self):
        rng=random.Random(15151)
        for _ in range(600):
            ego=self.car(rng.uniform(0,1199),rng.randrange(3),speed=rng.uniform(0,33.3))
            ego=replace(ego,vy=rng.choice([0.,-3.3,3.3]),pending_lane=rng.choice([None,None,0,1,2]))
            rows=tuple(self.car(ego.x+rng.uniform(-100,200),rng.randrange(3),i+1,rng.uniform(0,33.3)) for i in range(rng.randrange(12)))
            memory=r.Memory(lane_target=rng.choice([None,0,1,2]),joining=bool(rng.randrange(2)))
            drop=rng.choice([None,1000.])
            c,m=r.decide(ego,rows,memory,'noa',drop)
            d,n=R.decide(R.Vehicle(**asdict(ego)),tuple(R.Vehicle(**asdict(car)) for car in rows),R.Memory(**asdict(memory)),'noa',drop)
            self.assertEqual((asdict(c),asdict(m)),(asdict(d),asdict(n)))


if __name__=='__main__':unittest.main()
