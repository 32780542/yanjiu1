"""Original phase4 failure cases, evaluated against unchanged driving gates."""
import unittest
from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.road import VisibleRoad
from simulation.noa_clock import NoaClock
from experiments.phase4_cases import cases
from experiments.phase4_audit import driving_metrics
from experiments.phase3 import NET
from research.common import settings


def simulate_case(name, sample_dt=.1, integration_dt=.01):
    model = KinematicModel.from_config()
    p = {**model.p, **settings('phase3'), **settings('phase4_experiments'),
         'control_sync_dt_s':sample_dt, 'perception_dt_s':sample_dt, 'dynamics_dt_s':integration_dt}
    policy = {**model.p, **settings('phase4'), 'control_sync_dt_s':sample_dt, 'perception_dt_s':sample_dt}
    case = next(c for c in cases(model.p) if c['name'] == name)
    clock = NoaClock({k:VehicleState(**s) for k,s in case['initial'].items()},
                     model, VisibleRoad.from_net(NET), p, policy, case['controlled'], case['scripts'])
    records = [clock.tick() for _ in range(round(case['duration_s']/sample_dt))]
    return records, driving_metrics(records, model, p, case)


class Phase4CompletionTests(unittest.TestCase):
    def test_signed_braking_distance_bounds_model_stopping(self):
        from noa.controller import _stop_distance
        from models.vehicle import Actuation
        model=KinematicModel.from_config()
        p={**model.p, **settings('phase4')}
        for speed in (1.,15.,30.):
            for acceleration in (-4.5,-1.,0.,2.):
                for braking in (3.,10.):
                    with self.subTest(speed=speed,acceleration=acceleration,braking=braking):
                        state=VehicleState(vx_mps=speed,a_drive_mps2=acceleration)
                        bound=_stop_distance(speed,acceleration,braking,p)
                        for _ in range(200):
                            state=model.advance(state,Actuation(-braking,0.),.1,.01).final
                            if state.vx_mps==0: break
                        self.assertEqual(state.vx_mps,0.)
                        self.assertGreaterEqual(bound+1e-6,state.x_m)

    def test_stop_actual_jerk_with_refined_integration(self):
        _,metrics=simulate_case('stop_restart',integration_dt=.005)
        self.assertTrue(metrics['comfort_passed'])
        self.assertEqual(metrics['actors']['ego']['min_speed_mps'],0.)

    def test_noa_reference_join_uses_same_physical_time(self):
        from models.bezier import QuadraticLaneChange
        from noa.prediction import reference_target
        plan = QuadraticLaneChange(.5, 1.65, 4.95, 5., 20.)
        a = reference_target(plan, 3.-5e-15)
        b = reference_target(plan, 3.+5e-15)
        self.assertEqual(a, b)
        self.assertLess(a['ay_mps2'], 0.)
    def test_original_stop_restart_actual_jerk_and_finite_stop(self):
        records, metrics = simulate_case('stop_restart')
        ego = metrics['actors']['ego']
        self.assertLessEqual(ego['max_actual_jerk_mps3'], 2.000001)
        self.assertEqual(ego['min_speed_mps'], 0.)
        self.assertTrue(metrics['requirements_passed'])
        self.assertTrue(metrics['comfort_passed'])

    def test_original_no_gap_stops_within_sixteen_seconds(self):
        records, metrics = simulate_case('merge_no_gap')
        self.assertTrue(metrics['requirements_passed'], metrics['actors']['ego']['final'])
        self.assertTrue(metrics['comfort_passed'])

    def test_original_no_gap_half_sampling_is_comfortable(self):
        _,metrics=simulate_case('merge_no_gap',.05)
        self.assertTrue(metrics['requirements_passed'])
        self.assertTrue(metrics['comfort_passed'],metrics['actors']['ego']['max_actual_jerk_mps3'])

    def test_scripted_bezier_uses_same_physical_event_time(self):
        from simulation.noa_clock import script_action
        script={'speed_steps':[[0,12]],'lane_change':{'start_s':1.,'y_start_m':4.95,'y_target_m':1.65,'duration_s':5.,'speed_mps':12.}}
        p=KinematicModel.from_config().p
        a=script_action(VehicleState(time_s=1.-1e-15,x_m=315,y_m=4.95,vx_mps=12),script,p)
        b=script_action(VehicleState(time_s=1.+1e-15,x_m=315,y_m=4.95,vx_mps=12),script,p)
        self.assertEqual(a,b)

    def test_cut_in_half_sampling_positions_are_consistent(self):
        from experiments.phase3_audit import compare_records
        a,ma=simulate_case('observed_cut_in')
        b,mb=simulate_case('observed_cut_in',.05)
        self.assertTrue(ma['comfort_passed'] and mb['comfort_passed'])
        self.assertLessEqual(compare_records(a,b)['max_position_error_m'],.15)

    def test_original_cut_in_is_comfortable(self):
        _, metrics = simulate_case('observed_cut_in')
        self.assertTrue(metrics['comfort_passed'], metrics['actors']['ego']['min_actual_acceleration_mps2'])

    def test_original_normal_lane_change_sampling(self):
        from experiments.phase3_audit import compare_records
        a, ma = simulate_case('normal_lane_change')
        b, mb = simulate_case('normal_lane_change', .05)
        comparison = compare_records(a,b)
        self.assertTrue(ma['requirements_passed'] and mb['requirements_passed'])
        self.assertLessEqual(comparison['max_position_error_m'], .15)
        self.assertLessEqual(comparison['max_heading_error_rad'], .02)

    def test_original_sparse_queue_merge_completes_and_tracks(self):
        records, metrics = simulate_case('merge_gap_after_queue')
        self.assertTrue(metrics['requirements_passed'], metrics['actors']['ego']['final'])
        self.assertTrue(metrics['tracking_passed'])
        self.assertTrue(metrics['comfort_passed'])
        rejected = [r['initial']['ego']['time_s'] for r in records
                    if 'fallback_prediction' in r['decisions']['ego']['diagnostics']
                    and not r['decisions']['ego']['diagnostics']['fallback_prediction']['safe']]
        self.assertEqual(rejected, [], 'Original ordinary merge must not rely on a rejected fallback')


if __name__ == '__main__':
    unittest.main()
