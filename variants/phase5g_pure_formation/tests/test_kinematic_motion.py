from dataclasses import replace
import importlib.util
import math
import unittest


class SimplifiedMotionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('models.kinematic'), 'Simplified motion model missing')
        from models.kinematic import KinematicModel
        from models.vehicle import VehicleState, Actuation
        self.model,self.State,self.Action = KinematicModel.from_config(),VehicleState,Actuation

    def test_active_model_requires_no_mass_inertia_stiffness_or_tire_coefficients(self):
        for name in self.model.p:
            self.assertFalse(any(word in name for word in ('mass','inertia','stiffness','friction','tire')))
        s = self.State(x_m=100,y_m=1.65,vx_mps=20)
        step = self.model.advance(s,self.Action(0,0),1,.01)
        self.assertAlmostEqual(step.final.x_m,120,places=9)
        self.assertEqual(step.final.y_m,1.65)
        self.assertEqual(step.final.vy_mps,0)

    def test_circle_matches_analytic_path_and_rate_limited_steering_is_continuous(self):
        from models.kinematic import kinematic_state
        speed,delta,duration = 10,.01,2
        initial = kinematic_state(self.model.p,x_m=100,y_m=4.95,vx_mps=speed,steering_rad=delta)
        step = self.model.advance(initial,self.Action(0,delta),duration,.01)
        rate = speed*math.tan(delta)/self.model.p['wheelbase_m']
        self.assertAlmostEqual(step.final.x_m,100+speed/rate*math.sin(rate*duration),places=8)
        self.assertAlmostEqual(step.final.y_m,4.95+speed/rate*(1-math.cos(rate*duration)),places=8)
        for a,b in zip((initial,)+step.samples,step.samples):
            self.assertLessEqual(abs(b.steering_rad-a.steering_rad)/.01,self.model.p['max_steering_rate_radps']+1e-9)
            self.assertLessEqual(math.hypot(b.x_m-a.x_m,b.y_m-a.y_m),.11)

    def test_stop_restart_no_reverse_and_inconsistent_lateral_state_rejected(self):
        s = self.State(vx_mps=1)
        stopped = self.model.advance(s,self.Action(-3,0),3,.01)
        self.assertEqual(stopped.final.vx_mps,0)
        self.assertTrue(all(x.vx_mps>=0 for x in stopped.samples))
        restarted = self.model.advance(stopped.final,self.Action(2,0),4,.01)
        self.assertGreater(restarted.final.vx_mps,1)
        with self.assertRaises(ValueError):
            self.model.advance(replace(s,vy_mps=.5),self.Action(0,0),.1,.01)

    def test_rk_stages_do_not_integrate_reverse_or_above_limit_speed(self):
        s = self.State(vx_mps=.001,a_drive_mps2=-3)
        step = self.model.advance(s,self.Action(-3,0),.01,.01)
        self.assertGreaterEqual(step.final.x_m,0)
        self.assertLessEqual(step.final.x_m,.001*.01)
        vmax = self.model.p['max_speed_mps']
        s = self.State(vx_mps=vmax-.001,a_drive_mps2=5)
        step = self.model.advance(s,self.Action(5,0),.01,.01)
        self.assertLessEqual(step.final.x_m,vmax*.01)

    def test_unknown_model_and_nonfinite_bezier_parameters_are_rejected(self):
        from models.kinematic import model_from_parameters
        from models.bezier import QuadraticLaneChange
        with self.assertRaises(ValueError):
            model_from_parameters({**self.model.p,'motion_model':'unknown'})
        for value in (math.nan,math.inf):
            with self.assertRaises(ValueError):
                QuadraticLaneChange(0,1.65,4.95,value,20)

    def test_two_quadratic_bezier_segments_have_parallel_end_tangents_and_c1_join(self):
        from models.bezier import QuadraticLaneChange
        ref = QuadraticLaneChange(0,1.65,4.95,5,20)
        for t,y in ((0,1.65),(5,4.95)):
            r = ref.at(t)
            self.assertAlmostEqual(r['y_m'],y)
            self.assertEqual(r['vy_mps'],0)
        left,right = ref.at(2.5-1e-7),ref.at(2.5+1e-7)
        self.assertAlmostEqual(left['vy_mps'],right['vy_mps'],places=6)
        self.assertLess(abs(left['y_m']-right['y_m']),1e-6)
        self.assertGreater(left['ay_mps2'],0)
        self.assertLess(right['ay_mps2'],0)  # C1, deliberately no C2 claim

    def test_bezier_following_is_integrated_and_meets_existing_small_case_position_gate(self):
        from models.bezier import QuadraticLaneChange,bezier_command
        ref = QuadraticLaneChange(0,1.65,4.95,5,20)
        s = self.State(x_m=100,y_m=1.65,vx_mps=20)
        peak = 0
        for _ in range(100):
            command = bezier_command(s,ref,self.model.p)
            step = self.model.advance(s,command,.1,.01)
            for state in step.samples:
                peak = max(peak,abs(state.y_m-ref.at(state.time_s)['y_m']))
            s = step.final
        self.assertLess(peak,self.model.p['max_lane_change_error_m'])
        self.assertLess(abs(s.y_m-4.95),self.model.p['terminal_lane_error_m'])

    def test_saved_motion_bench_is_replayable_in_both_step_sizes(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.kinematic_bench'),'Saved motion bench missing')
        from experiments.kinematic_bench import run_bench
        from research.common import ROOT
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            result,dirs = run_bench(Path(tmp)/'motion',self.model,live=False)
            self.assertTrue(result['passed'],result)
            self.assertEqual(len(dirs),3)
