"""Bounded local waiting model; proxy costs are not safety certificates."""
from dataclasses import asdict, astuple, replace
import importlib.util
import itertools
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import test_phase5_r5_controller as fixtures
from noa.controller import decide
from noa.prediction import measured_bodies
from noa.prediction import verify_candidate
from noa.road import reconstruct
from models.bezier import QuadraticLaneChange


class WaitingGameTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('noa.waiting_game'),
                             'Missing bounded local waiting model')
        from noa import waiting_game
        self.game = waiting_game
        self.f = fixtures.R5Tests()
        self.f.setUp()
        self.p = {**self.f.p, 'r5_lane_priority_enabled': True,
                  **waiting_game.waiting_parameters('stackelberg')}

    def selection(self, control=None, assessment=None, gate=None, phase='YIELD',
                  base=.5, fixed=-.5, parameters=None):
        c = control or self.f.control(speed=5., neighbors=((0., 8.25, 5., 0.),))
        a = assessment if assessment is not None else {
            'reason': 'yield_visible_upper_lane',
            'participant_signatures': tuple(astuple(b) for b in measured_bodies(c))}
        return self.game.select_waiting(c, a, {'blocking': True} if gate is None else gate,
                                        phase, base, fixed, self.p if parameters is None else parameters)

    def test_registered_parameters_fixed_and_unknown_modes(self):
        self.assertEqual(self.game.MODES, ('fixed', 'minimax', 'stackelberg'))
        self.assertEqual(self.game.waiting_parameters('fixed'), {})
        expected = dict(r5_waiting_policy='minimax', r5_game_horizon_s=5.,
                        r5_game_peer_accel_mps2=.5, r5_game_gap_weight=1.,
                        r5_game_speed_weight=1., r5_game_effort_weight=.05)
        self.assertEqual(self.game.waiting_parameters('minimax'), expected)
        for bad in ('MINIMAX', '', None, False, 0, [], {}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.game.waiting_parameters(bad)

    def test_validation_rejects_nonfinite_bool_missing_and_outside_ranges(self):
        numeric = ('r5_game_horizon_s', 'r5_game_peer_accel_mps2',
                   'r5_game_gap_weight', 'r5_game_speed_weight', 'r5_game_effort_weight')
        for key in numeric:
            for bad in (True, '1', None, float('nan'), float('inf'), -1.):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    self.game.validate_parameters({**self.p, key: bad})
            with self.subTest(missing=key), self.assertRaises(ValueError):
                self.game.validate_parameters({k: v for k, v in self.p.items() if k != key})
        for extra in ({'r5_game_horizon_s': 0.}, {'r5_game_peer_accel_mps2': 0.},
                      {'r5_game_peer_accel_mps2': self.p['max_accel_mps2']+1.},
                      {'r5_game_gap_weight': 0., 'r5_game_speed_weight': 0.},
                      {'noa_target_speed_mps': 0.}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.game.validate_parameters({**self.p, **extra})
        self.assertEqual(self.game.validate_parameters({}), 'fixed')
        self.assertEqual(self.game.validate_parameters(self.p), 'stackelberg')

    def test_nontrivial_matrix_distinguishes_minimax_and_stackelberg(self):
        ego = [[2., 2., 2.], [0., 3., 4.], [4., 0., 3.]]
        peer = [[5., 5., 5.], [0., 8., 8.], [8., 1., 8.]]
        minimax = self.game.solve_matrix('minimax', [-.5, 0., .2], [-.5, 0., .5], ego, peer)
        stack = self.game.solve_matrix('stackelberg', [-.5, 0., .2], [-.5, 0., .5], ego, peer)
        self.assertEqual((minimax['model_selected_ego_mps2'], minimax['model_selected_peer_mps2']), (-.5, -.5))
        self.assertEqual((stack['model_selected_ego_mps2'], stack['model_selected_peer_mps2']), (0., -.5))
        self.assertEqual(stack['ego_best_responses'], [[0.], [.2], [-.5]])

    def test_stackelberg_uses_entire_best_response_set_pessimistically(self):
        ego = [[0., 1., 3.], [0., 2., 3.], [2., 0., 0.]]
        peer = [[9., 7., 1.], [1., 8., 8.], [0., 5., 5.]]
        result = self.game.solve_matrix('stackelberg', [-.5, 0., .2], [-.5, 0., .5], ego, peer)
        self.assertEqual(result['ego_best_responses'], [[-.5, 0.], [.2], [.2]])
        self.assertEqual((result['model_selected_ego_mps2'], result['model_selected_peer_mps2']), (.2, 0.))
        result = self.game.solve_matrix('stackelberg', [-.5, 0.], [0.], [[1.], [1.]], [[3.], [9.]])
        self.assertEqual(result['model_selected_ego_mps2'], 0.)
        tied = self.game.solve_matrix('stackelberg', [-.5, 0.], [0.], [[1.], [1.]], [[9.], [9.]])
        self.assertEqual(tied['model_selected_ego_mps2'], -.5)

    def test_matrix_solver_order_invariance_and_no_epsilon_ties(self):
        ea, pa = [-.5, 0., .2], [-.5, 0., .5]
        ec, pc = [[2., 2., 2.], [0., 3., 4.], [4., 0., 3.]], [[5., 5., 5.], [0., 8., 8.], [8., 1., 8.]]
        for mode in ('minimax', 'stackelberg'):
            expected = self.game.solve_matrix(mode, ea, pa, ec, pc)
            for rows, cols in itertools.product(itertools.permutations(range(3)), repeat=2):
                actual = self.game.solve_matrix(mode, [ea[i] for i in rows], [pa[j] for j in cols],
                    [[ec[i][j] for j in cols] for i in rows], [[pc[i][j] for j in cols] for i in rows])
                self.assertEqual(actual, expected)
        tiny = self.game.solve_matrix('minimax', [-.5, 0.], [0.], [[1.+1e-14], [1.]], [[0.], [0.]])
        self.assertEqual(tiny['model_selected_ego_mps2'], 0.)

    def test_exact_physical_matrix_uses_signed_gap_and_both_proxy_speed_costs(self):
        result = self.selection()
        self.assertEqual(result['ego_actions_mps2'], [-.5, 0., .5])
        self.assertEqual(result['peer_actions_mps2'], [-.5, 0., .5])
        d = (self.p['length_m']+4.)/2+2*self.p['noa_body_margin_m']+self.p['noa_standstill_gap_m']
        for i, a in enumerate([-.5, 0., .5]):
            for j, b in enumerate([-.5, 0., .5]):
                g = (b-a)*12.5
                q = max(0., (d-g)/d)**2
                self.assertAlmostEqual(result['ego_costs'][i][j], q+(a*5/5)**2+.05*(a/.5)**2)
                self.assertAlmostEqual(result['peer_costs'][i][j], q+(b*5/5)**2+.05*(b/.5)**2)
        self.assertGreater(result['ego_costs'][2][0], result['ego_costs'][0][2])
        self.assertIn('proxy', result['assumptions'])

    def test_speed_stopping_and_saturation_are_integrated_piecewise(self):
        c = self.f.control(speed=.1, neighbors=((0., 8.25, .1, 0.),))
        result = self.selection(control=c)
        a = result['ego_actions_mps2'][0]
        self.assertEqual(a, max(-.5, -self.p['noa_stop_speed_gain_per_s']*.1-self.p['noa_stop_terminal_braking_mps2']))
        # Both stop: equal displacement keeps q=1 and terminal speed is zero.
        self.assertAlmostEqual(result['peer_costs'][0][0],
            max(0., (result['desired_separation_m']-(.1*.1/(2*.5)-.1*.1/(2*abs(a))))/result['desired_separation_m'])**2+1.+.05)
        c = self.f.control(speed=self.p['max_speed_mps'], neighbors=((0., 8.25, self.p['max_speed_mps'], 0.),))
        saturated = self.selection(control=c)
        self.assertAlmostEqual(saturated['ego_costs'][-1][-1],
            1.+((self.p['max_speed_mps']-5.)/5.)**2+.05)

    def test_candidate_taper_clip_deduplicates_and_never_exceeds_base(self):
        for base, fixed in ((-.7, -.7), (0., -.5), (.2, -.5)):
            result = self.selection(base=base, fixed=fixed)
            actions = result['ego_actions_mps2']
            self.assertEqual(actions, sorted(set(actions)))
            self.assertTrue(all(a <= base for a in actions))
            self.assertTrue(all(self.p['min_accel_mps2'] <= a <= self.p['max_accel_mps2'] for a in actions))

    def test_missing_multiple_unknown_and_untrusted_reasons_fall_back(self):
        one = (100., 8.25, 5., 0., 0., 4., 1.8)
        for assessment, gate, phase, expected in (
            ({'reason': 'yield_visible_upper_lane', 'participant_signatures': ()}, {'blocking': True}, 'YIELD', 'participant_count'),
            ({'reason': 'yield_visible_upper_lane', 'participant_signatures': (one, one)}, {'blocking': True}, 'YIELD', 'participant_count'),
            ({'reason': 'yield_visible_upper_lane', 'participant_signatures': (one,)}, {'blocking': True}, 'UNKNOWN', 'unknown_phase'),
            ({'reason': 'ambiguous', 'participant_signatures': (one,)}, {'blocking': True}, 'BACKOFF', 'assessment_reason'),
            ({'reason': 'yield_visible_upper_lane', 'participant_signatures': (one,)}, {'blocking': False}, 'YIELD', 'gate_not_blocking')):
            with self.subTest(expected=expected):
                result = self.selection(assessment=assessment, gate=gate, phase=phase)
                self.assertTrue(result['fallback'])
                self.assertEqual(result['fallback_reason'], expected)
                self.assertEqual(result['selected_request_mps2'], -.5)
                self.assertIsNone(result['model_selected_ego_mps2'])
        c = self.f.control()
        absent = self.game.select_waiting(c, None, {'blocking': True}, 'YIELD', .5, -.5, self.p)
        self.assertEqual(absent['fallback_reason'], 'missing_assessment')

    def test_stale_physical_signature_is_not_a_current_peer(self):
        stale = {'reason': 'yield_visible_upper_lane', 'participant_signatures': ((99., 8.25, 5., 0., 0., 4., 1.8),)}
        self.assertEqual(self.selection(assessment=stale)['fallback_reason'], 'peer_not_current')

    def test_world_velocity_uses_ego_body_heading_and_lateral_velocity(self):
        c = self.f.control(speed=5., neighbors=((0., 8.25, 5., 0.),))
        c = replace(c, ego=replace(c.ego, heading_rad=.5, vy_mps=20.))
        self.assertEqual(self.selection(control=c)['fallback_reason'], 'negative_world_vx')

    def test_derived_nonfinite_values_are_rejected(self):
        with self.assertRaises(ValueError):
            self.selection(parameters={**self.p, 'r5_game_horizon_s': 1e308})

    def test_cost_normalization_is_registered_five_and_half(self):
        result = self.selection(parameters={**self.p, 'r5_game_peer_accel_mps2': .25,
                                             'noa_target_speed_mps': 4.})
        d = result['desired_separation_m']
        # Ego a=0, peer b=.25 gives g=3.125, terminal speeds 5 and 6.25.
        q = max(0., (d-3.125)/d)**2
        self.assertAlmostEqual(result['ego_costs'][1][-1], q+((5.-4.)/5.)**2)
        self.assertAlmostEqual(result['peer_costs'][1][-1], q+((6.25-4.)/5.)**2+.05*(.25/.5)**2)

    def test_label_order_and_private_state_do_not_change_the_model(self):
        c = self.f.control(speed=5., neighbors=((0., 8.25, 5., 0.), (90., 1.65, 5., 0.)))
        peer = astuple(measured_bodies(c)[0])
        a = {'reason': 'yield_visible_upper_lane', 'participant_signatures': (peer,)}
        changed = replace(c, observation=replace(c.observation, neighbors=tuple(
            replace(n, track_id='hidden-label-'+str(i)) for i, n in enumerate(reversed(c.observation.neighbors)))),
            memory=self.f.memory(state=123456))
        self.assertEqual(self.selection(control=c, assessment=a), self.selection(control=changed, assessment=a))
        self.assertEqual(c.memory.r5_draw_count, 0)

    def established(self, front=None, speed=5., peer_dx=4.):
        neighbors = ((peer_dx, 8.25, speed, 0.),)
        if front is not None:
            neighbors += ((front, 1.65, 5., 0.),)
        c = self.f.control(speed=speed, neighbors=neighbors)
        road = reconstruct(c.ego, c.observation.road, self.p)
        candidate = QuadraticLaneChange(0., 1.65, 4.95, 5., max(speed, 5.))
        a = self.f.r5.assess_candidate(c, road, candidate, c.memory, self.p)
        memory, gate = self.f.r5.advance_backoff(a, c.memory, 0., self.p)
        self.assertTrue(gate['blocking'])
        self.assertEqual(memory.r5_draw_count, 0)
        return replace(c, memory=memory)

    def test_controller_rejects_unknown_policy_before_any_bypass(self):
        for enabled in (False, True):
            with self.assertRaisesRegex(ValueError, 'r5_waiting_policy'):
                decide(self.f.control(), {**self.p, 'r5_enabled': enabled, 'r5_waiting_policy': 'mistyped'})

    def test_fixed_default_is_identical_and_endpoint_delta_is_bounded_from_sealed_5c(self):
        source = Path(__file__).resolve().parents[2]/'phase5c_lane_priority'/'noa'/'controller.py'
        spec = importlib.util.spec_from_file_location('sealed_phase5c_controller', source)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        p = {k: v for k, v in self.p.items() if not k.startswith('r5_game_') and k != 'r5_waiting_policy'}
        cases = [self.established(front=front) for front in (None, 20., 25., 35.)]
        cases += [self.f.control(speed=v, neighbors=peers) for v in (0., 4.9, 5., 8.)
                  for peers in ((), ((10., 1.65, 0., 0.),), ((35., 1.65, 3., 0.), (0., 8.25, 8., 0.)))]
        for c in cases:
            for enabled in (True, False):
                with self.subTest(speed=c.ego.vx_mps, enabled=enabled):
                    parent = old.decide(c, {**p, 'r5_enabled': enabled})
                    current = decide(c, {**p, 'r5_enabled': enabled})
                    explicit = decide(c, {**p, 'r5_enabled': enabled, 'r5_waiting_policy': 'fixed'})
                    self.assertEqual(current, explicit)
                    if current != parent:
                        self.assertIn(c.ego.vx_mps, (4.9, 5.))
                        self.assertEqual(current.memory, parent.memory)
                        self.assertEqual(current.diagnostics, parent.diagnostics)
                        self.assertEqual(current.action.steering_rad, parent.action.steering_rad)
                        difference = current.action.acceleration_mps2-parent.action.acceleration_mps2
                        self.assertGreater(difference, 0.)
                        self.assertLessEqual(difference, p['noa_geometry_tolerance_m'])

    def test_controller_accepts_changed_request_only_after_real_full_hold_guard(self):
        c = self.established()
        with patch('noa.controller.verify_candidate', wraps=verify_candidate) as guard:
            decision = decide(c, self.p)
        self.assertIn('waiting_game', decision.diagnostics['r5'])
        info = decision.diagnostics['r5']['waiting_game']
        self.assertEqual(info['model_selected_ego_mps2'], 0.)
        self.assertEqual(info['applied_request_mps2'], decision.action.acceleration_mps2)
        self.assertEqual(decision.action.acceleration_mps2, 0.)
        self.assertTrue(info['executed'])
        self.assertTrue(info['changed_from_fixed'])
        self.assertFalse(info['fallback'])
        self.assertTrue(info['model_guard']['safe'])
        self.assertEqual(guard.call_count, 1)
        for call in guard.call_args_list:
            passed_control, plan, _, _, passed_p = call.args
            self.assertIs(passed_control, c)
            self.assertIs(passed_p, self.p)
            self.assertEqual((plan.y_start_m, plan.y_target_m, plan.duration_s), (1.65, 1.65, 5.))
        self.assertEqual((decision.memory.r5_rng_state, decision.memory.r5_draw_count),
                         (c.memory.r5_rng_state, c.memory.r5_draw_count))

    def test_real_guard_rejects_model_then_accepts_original_fixed(self):
        c = self.established(front=25.)
        with patch('noa.controller.verify_candidate', wraps=verify_candidate) as guard:
            decision = decide(c, self.p)
        self.assertIn('waiting_game', decision.diagnostics['r5'])
        info = decision.diagnostics['r5']['waiting_game']
        self.assertGreater(info['model_selected_ego_mps2'], -.5)
        self.assertFalse(info['model_guard']['safe'])
        self.assertTrue(info['fixed_guard']['safe'])
        self.assertEqual(decision.action.acceleration_mps2, -.5)
        self.assertEqual(info['applied_request_mps2'], -.5)
        self.assertFalse(info['executed'])
        self.assertTrue(info['fallback'])
        self.assertEqual(info['fallback_reason'], 'model_guard_rejected')
        self.assertEqual(guard.call_count, 2)
        self.assertTrue(all(len(call.args[0].observation.neighbors) == 2 for call in guard.call_args_list))

    def test_real_guard_rejects_model_and_fixed_then_retains_parent_base(self):
        c = self.established(front=20.)
        parent = decide(c, {**self.p, 'r5_waiting_policy': 'fixed'})
        decision = decide(c, self.p)
        self.assertIn('waiting_game', decision.diagnostics['r5'])
        info = decision.diagnostics['r5']['waiting_game']
        self.assertFalse(info['model_guard']['safe'])
        self.assertFalse(info['fixed_guard']['safe'])
        self.assertEqual(decision.action, parent.action)
        self.assertEqual(decision.memory, parent.memory)
        self.assertEqual(info['applied_request_mps2'], info['base_request_mps2'])
        self.assertFalse(info['executed'])
        self.assertEqual(info['fallback_reason'], 'model_and_fixed_guard_rejected')
        self.assertEqual(decision.diagnostics['r5']['reason'], 'yield_not_certified')

    def test_r5_off_emergency_and_active_plan_never_call_waiting_model(self):
        c = self.established()
        emergency = self.f.control(speed=5., neighbors=((5., 1.65, 0., 0.),))
        active = replace(c, memory=replace(c.memory, plan=QuadraticLaneChange(0., 1.65, 4.95, 5., 5.),
                                          target_y_m=4.95, lane_change_reason='slower_visible_lead'))
        # The patch asserts the exclusion boundary; real guards still execute.
        self.assertTrue(hasattr(__import__('noa.controller', fromlist=['waiting_game']), 'waiting_game'))
        with patch('noa.controller.waiting_game.select_waiting', side_effect=AssertionError('must bypass')):
            for control, parameters in ((c, {**self.p, 'r5_enabled': False}), (emergency, self.p), (active, self.p)):
                d = decide(control, parameters)
                self.assertNotIn('waiting_game', d.diagnostics.get('r5', {}))

    def test_low_speed_and_unknown_episode_cannot_bypass_lane_change_gate(self):
        low = decide(self.established(speed=4.9), self.p)
        self.assertIn('waiting_game', low.diagnostics['r5'])
        self.assertIsNone(low.memory.plan)
        self.assertIsNone(low.memory.prepare_since_s)
        self.assertEqual(self.p['noa_min_lane_change_speed_mps'], 5.)
        c = self.established()
        unknown = replace(c, memory=replace(c.memory, r5_phase='UNKNOWN'))
        d = decide(unknown, self.p)
        self.assertEqual(d.diagnostics['r5']['waiting_game']['fallback_reason'], 'unknown_phase')
        self.assertFalse(d.diagnostics['r5']['waiting_game']['executed'])
        self.assertIsNone(d.memory.plan)

    def test_controller_label_permutation_and_private_chain_indifference(self):
        c = self.established(front=25.)
        changed = replace(c, observation=replace(c.observation, neighbors=tuple(
            replace(n, track_id='renamed-'+str(i)) for i, n in enumerate(reversed(c.observation.neighbors)))))
        self.assertEqual(decide(c, self.p), decide(changed, self.p))
        changed = replace(c, memory=replace(c.memory, r5_rng_state=123456))
        d, changed_d = decide(c, self.p), decide(changed, self.p)
        self.assertEqual(d.action, changed_d.action)
        self.assertEqual(d.diagnostics, changed_d.diagnostics)
        self.assertEqual((d.memory.r5_draw_count, changed_d.memory.r5_draw_count), (0, 0))

    def test_huge_integer_parameter_reports_value_error(self):
        try:
            self.game.validate_parameters({**self.p, 'r5_game_horizon_s': 10**1000})
        except Exception as exc:
            self.assertIsInstance(exc, ValueError)
        else:
            self.fail('Unrepresentable waiting parameter was accepted')

    def test_nonfinite_transformed_peer_velocity_is_rejected(self):
        c = self.f.control(speed=5., neighbors=((0., 8.25, 5., 0.),))
        c = replace(c, ego=replace(c.ego, heading_rad=math.pi/4), observation=replace(c.observation,
            neighbors=(replace(c.observation.neighbors[0], relative_vx_mps=1.7e308, relative_vy_mps=-1.7e308),)))
        with self.assertRaises(ValueError):
            self.selection(control=c)

    def test_guard_rejection_preserves_unknown_eligibility_reason(self):
        c = self.established(front=20.)
        c = replace(c, memory=replace(c.memory, r5_phase='UNKNOWN'))
        info = decide(c, self.p).diagnostics['r5']['waiting_game']
        self.assertIn('eligibility_reason', info)
        self.assertEqual(info['eligibility_reason'], 'unknown_phase')
        self.assertEqual(info['fallback_reason'], 'fixed_guard_rejected')
        self.assertFalse(info['fixed_guard']['safe'])
        self.assertIsNone(info['model_selected_ego_mps2'])

    def test_all_registered_yield_reasons_and_negative_peer_boundary(self):
        c = self.f.control(speed=5., neighbors=((4., 8.25, 5., 0.),))
        peer = astuple(measured_bodies(c)[0])
        for reason in ('yield_visible_upper_lane', 'yield_visible_front', 'yield_entered',
                       'yield_visible_inward_motion', 'yield_occupied_corridor'):
            result = self.selection(control=c, assessment={'reason': reason, 'participant_signatures': (peer,)})
            self.assertFalse(result['fallback'])
        reversed_peer = replace(c, observation=replace(c.observation, neighbors=(
            replace(c.observation.neighbors[0], relative_vx_mps=-6.),)))
        self.assertEqual(self.selection(control=reversed_peer)['fallback_reason'], 'negative_world_vx')

    def test_no_random_draws_across_repeated_local_waiting_decisions(self):
        memory = self.established().memory
        rng = memory.r5_rng_state
        for tick in range(6):
            c = self.f.control(t=tick*.1, speed=5., memory=memory, neighbors=((4., 8.25, 5., 0.),))
            d = decide(c, self.p)
            memory = d.memory
            self.assertEqual((memory.r5_rng_state, memory.r5_draw_count), (rng, 0))
            self.assertEqual(d.diagnostics['r5']['draws_this_tick'], 0)
            self.assertTrue(d.diagnostics['r5']['waiting_game']['executed'])


if __name__ == '__main__':
    unittest.main()
