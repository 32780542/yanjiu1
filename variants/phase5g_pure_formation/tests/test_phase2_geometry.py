import math
import unittest
from research.common import ROOT


class GeometryTests(unittest.TestCase):
    def test_front_bumper_and_angle_roundtrip(self):
        from models.vehicle import VehicleState
        from models.geometry import to_sumo_pose, from_sumo_pose
        for psi in (0,math.pi/2,-math.pi/2,math.pi,.3):
            s=VehicleState(x_m=34,y_m=5,heading_rad=psi)
            x,y,deg=to_sumo_pose(s,4)
            a,b,c=from_sumo_pose(x,y,deg,4)
            self.assertAlmostEqual(a,s.x_m,places=10)
            self.assertAlmostEqual(b,s.y_m,places=10)
            self.assertAlmostEqual(math.sin(c-psi),0,places=10)
        self.assertEqual(to_sumo_pose(VehicleState(),4),(2.,0.,90.))

    def test_sat_and_sweep_detect_collision_between_clear_endpoints(self):
        from models.geometry import BodyPose
        from safety.geometry import collide, swept_collision
        a0,a1=BodyPose(-10,0,0,4,1.8),BodyPose(10,0,0,4,1.8)
        b0,b1=BodyPose(0,-10,math.pi/2,4,1.8),BodyPose(0,10,math.pi/2,4,1.8)
        self.assertFalse(collide(a0,b0))
        self.assertFalse(collide(a1,b1))
        self.assertTrue(swept_collision(a0,a1,b0,b1))
        self.assertFalse(swept_collision(a0,a1,BodyPose(-10,5,0,4,1.8),BodyPose(10,5,0,4,1.8)))
        self.assertTrue(collide(BodyPose(0,0,.6,4,1.8),BodyPose(1,0,-.6,4,1.8)))

    def test_road_body_not_just_center_and_swept_rotation(self):
        from models.geometry import BodyPose
        from safety.geometry import RoadEnvelope, swept_outside
        road=RoadEnvelope.from_net(ROOT/'scenarios/cai2024/bottleneck.net.xml')
        self.assertTrue(road.contains(BodyPose(999,4.95,0,4,1.8)))
        self.assertFalse(road.contains(BodyPose(999,8.25,0,4,1.8)))
        self.assertFalse(road.contains(BodyPose(1050,6.0,0,4,1.8)))
        # A 180-degree swept rotation leaves the lower road even though endpoints fit.
        a,b=BodyPose(500,1.65,0,4,1.8),BodyPose(500,1.65,math.pi,4,1.8)
        self.assertTrue(road.contains(a) and road.contains(b))
        self.assertTrue(swept_outside(road,a,b))
