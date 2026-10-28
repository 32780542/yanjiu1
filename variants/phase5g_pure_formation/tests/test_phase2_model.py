import importlib.util
import math
import unittest
from dataclasses import replace


class VehicleModelTests(unittest.TestCase):
    def test_continuous_model_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('models'), 'Continuous model not implemented')

    def test_constant_speed_has_analytic_displacement(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        model=VehicleModel.from_config()
        s=VehicleState(x_m=100,y_m=1.65,vx_mps=20)
        for _ in range(100):
            s=model.advance(s,Actuation(0,0),.1,.01).final
        self.assertAlmostEqual(s.x_m,300,places=8)
        self.assertAlmostEqual(s.y_m,1.65,places=10)
        self.assertAlmostEqual(s.time_s,10,places=10)
        self.assertEqual(s.vy_mps,0)

    def test_actuator_matches_unclipped_analytic_response(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        model=VehicleModel.from_config()
        s=VehicleState(vx_mps=10)
        duration=1
        s=model.advance(s,Actuation(.2,0),duration,.005).final
        tau=model.p['acceleration_lag_s']
        expected_a=.2*(1-math.exp(-duration/tau))
        expected_v=10+.2*(duration-tau*(1-math.exp(-duration/tau)))
        expected_x=10*duration+.2*(duration**2/2-tau*duration+tau**2*(1-math.exp(-duration/tau)))
        self.assertAlmostEqual(s.a_drive_mps2,expected_a,places=7)
        self.assertAlmostEqual(s.vx_mps,expected_v,places=7)
        self.assertAlmostEqual(s.x_m,expected_x,places=7)

    def test_braking_never_reverses_and_restarts(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        m=VehicleModel.from_config()
        s=VehicleState(vx_mps=3)
        for _ in range(80):
            old=s
            s=m.advance(s,Actuation(-3,0),.1,.01).final
            self.assertGreaterEqual(s.vx_mps,0)
            self.assertGreaterEqual(s.x_m,old.x_m)
        self.assertEqual(s.vx_mps,0)
        self.assertEqual(m.observe(s)['a_long_mps2'],0)
        for _ in range(60):
            s=m.advance(s,Actuation(2,0),.1,.01).final
        self.assertGreater(s.vx_mps,1)

    def test_steering_rate_yaw_and_lateral_response(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        m=VehicleModel.from_config()
        initial=VehicleState(vx_mps=15)
        result=m.advance(initial,Actuation(0,.01),4,.01)
        for a,b in zip((initial,)+result.samples,result.samples):
            self.assertLessEqual(abs(b.steering_rad-a.steering_rad)/(b.time_s-a.time_s),m.p['max_steering_rate_radps']+1e-8)
        self.assertGreater(result.final.yaw_rate_radps,.01)
        self.assertGreater(result.final.y_m,.5)
        self.assertGreater(abs(result.final.vy_mps),1e-5)

    def test_friction_circle_and_speed_dependent_steering_limit(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        m=VehicleModel.from_config()
        s=VehicleState(vx_mps=28.8,vy_mps=5,a_drive_mps2=-5,steering_rad=.5)
        d=m.observe(s)
        for axle in ('front','rear'):
            self.assertLessEqual(math.hypot(d[f'fx_{axle}_N'],d[f'fy_{axle}_N']),m.p['road_friction_coefficient']*d[f'fz_{axle}_N']+1e-7)
        self.assertTrue(d['tire_saturated'])
        self.assertTrue(d['outside_linear_tire_regime'])
        s=VehicleState(vx_mps=28.8)
        r=m.advance(s,Actuation(100,1),1,.01)
        self.assertLess(r.final.steering_rad,.02)
        self.assertLessEqual(r.final.a_drive_mps2,m.p['max_accel_mps2'])

    def test_low_speed_blending_is_finite_continuous_and_rest_stable(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        m=VehicleModel.from_config()
        rest=m.advance(VehicleState(),Actuation(0,.1),1,.01).final
        self.assertEqual((rest.x_m,rest.y_m,rest.heading_rad,rest.vx_mps),(0,0,0,0))
        for threshold in (1,3):
            a=m.observe(VehicleState(vx_mps=threshold-1e-6,vy_mps=.001,yaw_rate_radps=.001,steering_rad=.005))
            b=m.observe(VehicleState(vx_mps=threshold+1e-6,vy_mps=.001,yaw_rate_radps=.001,steering_rad=.005))
            self.assertLess(abs(a['vy_dot_mps2']-b['vy_dot_mps2']),1e-3)
        s=VehicleState(vx_mps=.1)
        r=m.advance(s,Actuation(.3,.03),4,.01)
        self.assertTrue(all(math.isfinite(v) for v in vars_for_state(r.final)))

    def test_full_braking_leaves_no_lateral_acceleration_in_blend(self):
        from models.vehicle import VehicleModel, VehicleState
        m=VehicleModel.from_config()
        mu_g=m.p['road_friction_coefficient']*m.p['gravity_mps2']
        for speed in (.5,1.5,2.5,3.):
            with self.subTest(speed=speed):
                d=m.observe(VehicleState(vx_mps=speed,steering_rad=.08,a_drive_mps2=-mu_g))
                self.assertLessEqual(math.hypot(d['a_long_mps2'],d['a_lateral_mps2']),mu_g+1e-9)

    def test_blended_acceleration_and_yaw_are_supported_by_logged_axle_forces(self):
        from models.vehicle import VehicleModel, VehicleState
        m=VehicleModel.from_config()
        for speed in (.5,1.5,2.5,3.,15.):
            with self.subTest(speed=speed):
                s=VehicleState(vx_mps=speed,vy_mps=.01,yaw_rate_radps=.02,steering_rad=.04,a_drive_mps2=-3)
                d=m.observe(s)
                self.assertAlmostEqual(m.p['mass_kg']*d['a_lateral_mps2'],d['fy_front_N']+d['fy_rear_N'],places=8)
                self.assertAlmostEqual(m.p['yaw_inertia_kgm2']*d['yaw_accel_radps2'],
                    m.p['cg_to_front_axle_m']*d['fy_front_N']-m.p['cg_to_rear_axle_m']*d['fy_rear_N'],places=8)

    def test_braking_and_steering_trajectory_respects_friction_at_both_steps(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        m=VehicleModel.from_config()
        mu_g=m.p['road_friction_coefficient']*m.p['gravity_mps2']
        for dt in (.01,.005):
            with self.subTest(dt=dt):
                r=m.advance(VehicleState(vx_mps=20),Actuation(-10,.698),6,dt)
                for s in r.samples:
                    d=m.observe(s)
                    self.assertLessEqual(math.hypot(d['a_long_mps2'],d['a_lateral_mps2']),mu_g+1e-9,
                        f'Combined acceleration exceeds friction at t={s.time_s}, vx={s.vx_mps}')

    def test_rejects_invalid_steps_and_nonfinite_state(self):
        from models.vehicle import VehicleModel, VehicleState, Actuation
        m=VehicleModel.from_config()
        for duration,dt in [(.1,0),(.1,.03),(-1,.01),(.1,.1)]:
            with self.assertRaises(ValueError):
                m.advance(VehicleState(vx_mps=10),Actuation(0,0),duration,dt)
        with self.assertRaises(ValueError):
            m.advance(VehicleState(vx_mps=float('nan')),Actuation(0,0),.1,.01)


def vars_for_state(state):
    from dataclasses import astuple
    return astuple(state)
