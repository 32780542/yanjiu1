"""常规跟驰与编队共用响应保护，等速车流保持巡航。"""

from dataclasses import replace
import unittest

from models.vehicle import VehicleState
from noa.controller import decide
from noa.simple_formation import FormationTarget, LocalVehicle, formation_acceleration
from tests.test_phase4_controller import NoaControllerTests
from tests.test_simple_formation_controller import SimpleFormationControllerTests


class RealisticNoaTests(unittest.TestCase):
    def test_equal_speed_at_time_headway_does_not_brake(self):
        fixture = NoaControllerTests()
        fixture.setUp()
        p = dict(fixture.p,noa_target_speed_mps=28.8)
        ego = VehicleState(x_m=100.,y_m=1.65,vx_mps=28.8)
        gap = p['noa_standstill_gap_m']+p['noa_headway_s']*28.8
        lead = replace(ego,x_m=ego.x_m+p['length_m']+gap)
        result = decide(fixture.control(ego,(lead,),fixture.road(lane_count=1)),p)
        self.assertNotEqual(result.memory.own_behavior,'EMERGENCY')
        self.assertAlmostEqual(result.action.acceleration_mps2,0.,places=8)

    def test_formation_catchup_respects_common_cruise_setting(self):
        fixture = SimpleFormationControllerTests()
        fixture.setUp()
        p = dict(fixture.p,noa_target_speed_mps=28.8)
        ego = LocalVehicle(0,100.,1.65,28.8,0)
        target = FormationTarget('follower',140.,1,30.,0,0,'reference')
        self.assertLessEqual(formation_acceleration(ego,target,p),0.)

    def test_closing_speed_braking_is_shared_in_both_modes(self):
        fixture = SimpleFormationControllerTests()
        fixture.setUp()
        # 净距大于TTC阈值触发点，但含jerk的闭合停车距离已经不足。
        control = fixture.control(speed=28.8,neighbors=(
            fixture.neighbor(7,100.,0,speed=0.,ego_speed=28.8),))
        for on in (False,True):
            result = decide(control,dict(fixture.p,simple_formation_enabled=on,
                formation_enabled=on,formation_lane_change_enabled=False,noa_target_speed_mps=28.8))
            self.assertEqual(result.action.acceleration_mps2,fixture.p['min_accel_mps2'])
            self.assertEqual(result.memory.own_behavior,'EMERGENCY')

    def test_same_position_body_is_an_emergency_in_both_modes(self):
        fixture = SimpleFormationControllerTests()
        fixture.setUp()
        control = fixture.control(neighbors=(fixture.neighbor(7,0.,0),))
        for on in (False,True):
            result = decide(control,dict(fixture.p,simple_formation_enabled=on,
                formation_enabled=on,formation_lane_change_enabled=False))
            self.assertEqual(result.memory.own_behavior,'EMERGENCY')
            self.assertEqual(result.action.acceleration_mps2,fixture.p['min_accel_mps2'])


if __name__=='__main__':
    unittest.main()
