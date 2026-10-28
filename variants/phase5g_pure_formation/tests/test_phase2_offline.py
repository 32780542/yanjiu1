"""Executable offline bench acceptance, replay and refinement contracts."""
from dataclasses import asdict, replace
import json
import math
import unittest


class OfflineCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.vehicle import VehicleModel
        cls.model = VehicleModel.from_config()

    def test_cases_have_full_serializable_initial_state_and_time_reference(self):
        from experiments.phase2_cases import cases
        from models.vehicle import VehicleState
        suite = cases()
        self.assertEqual(len(suite), 5)
        self.assertEqual(len({c['name'] for c in suite}), 5)
        json.dumps(suite, allow_nan=False)
        for case in suite:
            self.assertEqual(set(case['initial']), set(asdict(VehicleState())))
            self.assertEqual(case['initial']['time_s'], 0)
            self.assertGreaterEqual(case['initial']['x_m'], 50)
            self.assertIn(case['initial']['y_m'], (1.65, 4.95))
            self.assertIn('reference', case)

    def test_command_is_invariant_to_global_road_coordinate(self):
        from experiments.phase2_cases import cases, bench_command
        from models.vehicle import VehicleState
        from research.common import settings
        for case in cases():
            for time in (0, 1, 3, 5, 7, 9):
                s = VehicleState(**{**case['initial'], 'time_s': time})
                self.assertEqual(bench_command(replace(s, x_m=100), case, settings('phase2')),
                                 bench_command(replace(s, x_m=1100), case, settings('phase2')))

    def test_quintic_reference_has_registered_duration_and_smooth_endpoints(self):
        from experiments.phase2_cases import cases, reference_at
        case = next(c for c in cases() if c['name'] == 'lane_change')
        self.assertEqual(case['reference']['maneuver_duration_s'], 5)
        for time, y in ((0, 1.65), (5, 4.95), (10, 4.95)):
            ref = reference_at(time, case)
            self.assertAlmostEqual(ref['y_m'], y)
            self.assertAlmostEqual(ref['lateral_velocity_mps'], 0)
            self.assertAlmostEqual(ref['lateral_acceleration_mps2'], 0)
        self.assertEqual(reference_at(5-1e-14, case), reference_at(5, case),
                         'Integrator roundoff must not delay the reference endpoint')

    def test_replay_requires_exact_count_and_uses_saved_commands(self):
        from experiments.phase2_cases import cases
        from experiments.offline import run_case
        case = next(c for c in cases() if c['name'] == 'constant_steering')
        steps = run_case(self.model, case)
        commands = [step.command for step in steps]
        self.assertEqual(steps, run_case(self.model, case, commands=commands))
        for wrong in (commands[:-1], commands + commands[:1]):
            with self.assertRaises(ValueError):
                run_case(self.model, case, commands=wrong)
        with self.assertRaises(ValueError):
            run_case(self.model, case, control_dt_s=.11)
        with self.assertRaises(ValueError):
            run_case(self.model, case, dynamics_dt_s=.03)

    def test_comparison_uses_matching_times_and_wraps_heading(self):
        from models.vehicle import VehicleState, Actuation, IntegratedStep
        from experiments.offline import compare_trajectories
        def step(start, finish):
            return IntegratedStep(start, finish, Actuation(0, 0), (finish,), .1)
        a = VehicleState()
        b = replace(a, time_s=.1, x_m=1, heading_rad=math.pi-.01)
        c = replace(b, x_m=1.03, heading_rad=-math.pi+.01)
        metrics = compare_trajectories([step(a, b)], [step(a, c)])
        self.assertAlmostEqual(metrics['max_position_error_m'], .03)
        self.assertAlmostEqual(metrics['max_heading_error_rad'], .02)
        with self.assertRaises(ValueError):
            compare_trajectories([step(a, b)], [step(a, replace(c, time_s=.2))])

    def test_all_declared_cases_and_both_refinements_meet_fixed_thresholds(self):
        from experiments.phase2_cases import cases
        from experiments.offline import run_case, evaluate_case, compare_trajectories
        for case in cases():
            with self.subTest(case=case['name']):
                base = run_case(self.model, case)
                verdict = evaluate_case(self.model, case, base)
                self.assertTrue(verdict['passed'], verdict)
                integration = run_case(self.model, case, dynamics_dt_s=.005,
                                       commands=[s.command for s in base])
                convergence = compare_trajectories(base, integration)
                self.assertLessEqual(convergence['max_position_error_m'], .02)
                self.assertLessEqual(convergence['max_heading_error_rad'], .002)
                control = run_case(self.model, case, control_dt_s=.05)
                convergence = compare_trajectories(base, control)
                self.assertLessEqual(convergence['max_position_error_m'], .15)
                self.assertLessEqual(convergence['max_heading_error_rad'], .02)

    def test_evaluation_catches_broken_lane_tracking_and_truncated_history(self):
        from experiments.phase2_cases import cases
        from experiments.offline import run_case, evaluate_case
        from models.vehicle import Actuation
        case = next(c for c in cases() if c['name'] == 'lane_change')
        straight = run_case(self.model, case, commands=[Actuation(0, 0)] * 100)
        verdict = evaluate_case(self.model, case, straight)
        self.assertFalse(verdict['passed'])
        self.assertGreater(verdict['metrics']['max_reference_error_m'], .35)
        self.assertGreater(verdict['metrics']['terminal_lane_error_m'], .1)
        self.assertFalse(evaluate_case(self.model, case, straight[:-1])['passed'])

    def test_frozen_model_run_does_not_reread_configuration(self):
        from unittest.mock import patch
        from experiments.phase2_cases import cases
        from experiments.offline import run_case, evaluate_case
        case = next(c for c in cases() if c['name'] == 'lane_change')
        with patch('experiments.phase2_cases.settings', side_effect=AssertionError('Unexpected config reread')):
            steps = run_case(self.model, case)
            self.assertTrue(evaluate_case(self.model, case, steps)['passed'])

    def test_truncated_stop_case_still_has_json_serializable_failure(self):
        from experiments.phase2_cases import cases
        from experiments.offline import run_case, evaluate_case
        case = next(c for c in cases() if c['name'] == 'acceleration_stop_restart')
        verdict = evaluate_case(self.model, case, run_case(self.model, case)[:2])
        self.assertFalse(verdict['passed'])
        json.dumps(verdict, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
