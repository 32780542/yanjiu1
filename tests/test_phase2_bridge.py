from dataclasses import replace
import math
import unittest


class BridgeInvariantTests(unittest.TestCase):
    def test_rejects_teleport_duplicate_and_incomplete_integration(self):
        from models.vehicle import VehicleModel,VehicleState,Actuation
        from simulation.external_bridge import validate_integrated_step
        m=VehicleModel.from_config()
        s=VehicleState(vx_mps=20,x_m=100,y_m=1.65)
        step=m.advance(s,Actuation(0,0),.1,.01)
        validate_integrated_step(step,s,.1)
        bad=replace(step.final,x_m=step.final.x_m+15)
        altered=replace(step,final=bad,samples=step.samples[:-1]+(bad,))
        with self.assertRaises(ValueError):
            validate_integrated_step(altered,s,.1)
        with self.assertRaises(ValueError):
            validate_integrated_step(step,step.final,.1)
        with self.assertRaises(ValueError):
            validate_integrated_step(replace(step,samples=step.samples[:-1]),s,.1)

    def test_bench_reference_consumes_only_own_state(self):
        from models.vehicle import VehicleState
        from experiments.phase2_cases import cases,bench_command
        from research.common import settings
        case=next(c for c in cases() if c['name']=='lane_change')
        a=bench_command(VehicleState(vx_mps=28.8,x_m=100,y_m=1.65),case,settings('phase2'))
        b=bench_command(VehicleState(vx_mps=28.8,x_m=900,y_m=1.65),case,settings('phase2'))
        self.assertEqual(a,b,'No global bottleneck x trigger belongs in the tracking bench')

    def test_rejects_subtle_corruption_even_with_plausible_endpoint(self):
        from models.vehicle import VehicleModel,VehicleState,Actuation
        from simulation.external_bridge import validate_integrated_step
        m=VehicleModel.from_config()
        s=VehicleState(vx_mps=20,x_m=100,y_m=1.65)
        step=m.advance(s,Actuation(0,0),.1,.01)
        samples=list(step.samples)
        samples[3]=replace(samples[3],y_m=samples[3].y_m+.0001)
        with self.assertRaises(ValueError):
            validate_integrated_step(replace(step,samples=tuple(samples)),s,.1,m)
        with self.assertRaises(ValueError):
            validate_integrated_step(replace(step,command=Actuation(1,0)),s,.1,m)
        with self.assertRaises(ValueError):
            validate_integrated_step(replace(step,final=replace(step.final,x_m=math.nan)),s,.1,m)

    def test_sync_audit_separates_instantaneous_and_interval_acceleration(self):
        from models.vehicle import VehicleModel,VehicleState,Actuation
        from simulation.external_bridge import audit_readback
        from models.geometry import to_sumo_pose
        m=VehicleModel.from_config()
        s=VehicleState(vx_mps=10,x_m=100,y_m=1.65)
        step=m.advance(s,Actuation(.2,0),.1,.01)
        x,y,angle=to_sumo_pose(step.final,4)
        secant=(m.observe(step.final)['speed_mps']-m.observe(s)['speed_mps'])/.1
        raw=dict(sumo_time_s=.3,front_x_m=x,front_y_m=y,angle_deg=angle,
                 speed_mps=m.observe(step.final)['speed_mps'],acceleration_mps2=secant)
        report=audit_readback(raw,step.final,m,.2,secant)
        self.assertTrue(report['passed'])
        self.assertGreater(abs(report['model_a_long_mps2']-secant),.001)
        for key,delta in [('sumo_time_s',.1),('front_x_m',.01),('angle_deg',1),('speed_mps',.01),('acceleration_mps2',.1)]:
            with self.subTest(key=key):
                self.assertFalse(audit_readback({**raw,key:raw[key]+delta},step.final,m,.2,secant)['passed'])
