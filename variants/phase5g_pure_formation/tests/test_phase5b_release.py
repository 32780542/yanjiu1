"""Conservative expiry gate; sampling-grid coincidence is not visible priority."""
import math
import unittest
from unittest.mock import patch

import test_phase5_r5_controller as fixtures
from noa.controller import decide
from noa.prediction import verify_candidate


class ConservativeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.R5Tests()
        self.f.setUp()
        self.p = self.f.p

    def step(self, memory, now, neighbors=((0., 8.25, 8., 0.),), allow_draw=True):
        control = self.f.control(t=now, memory=memory, neighbors=neighbors)
        assessment = self.f.assess(control)
        result, diagnostic = self.f.r5.advance_backoff(
            assessment, memory, now, self.p, allow_draw=allow_draw)
        return result, diagnostic

    def expired(self, dt, dx=0.):
        self.p['control_sync_dt_s'] = dt
        neighbors = ((dx, 8.25, 8., 0.),)
        memory, _ = self.step(self.f.memory(), 0., neighbors)
        index = math.ceil(memory.r5_deadline_s / dt)
        for tick in range(1, index + 1):
            memory, diagnostic = self.step(memory, tick * dt, neighbors)
        return memory, diagnostic, index * dt

    def test_same_and_distinct_private_states_wait_after_shared_behavior_cell(self):
        # Keep the inherited 1/2 counterexample: no search for favorable states.
        for dt in (.1, .05):
            self.p['control_sync_dt_s'] = dt
            for states in ((1, 1), (1, 2)):
                deadlines = []
                for actor, state in enumerate(states):
                    with self.subTest(dt=dt, states=states, actor=actor):
                        memory, first = self.step(self.f.memory(state), 0.)
                        deadline, rng = memory.r5_deadline_s, memory.r5_rng_state
                        deadlines.append(deadline)
                        self.assertEqual(first['draws_this_tick'], 1)
                        for index in range(1, round(3. / dt) + 1):
                            now = index * dt
                            memory, diagnostic = self.step(memory, now)
                            self.assertEqual((memory.r5_deadline_s, memory.r5_rng_state,
                                              memory.r5_draw_count), (deadline, rng, 1))
                            self.assertEqual(memory.r5_episode_signature,
                                             diagnostic['assessment']['episode_signature'])
                            self.assertEqual(diagnostic['draws_this_tick'], 0)
                            self.assertTrue(diagnostic['blocking'])
                            self.assertEqual(memory.r5_phase, 'BACKOFF' if now < deadline - 1e-9 else 'YIELD')
                            self.assertEqual(diagnostic['reason'], 'private_backoff_wait' if now < deadline - 1e-9
                                             else 'expired_ambiguous_wait')
                self.assertEqual(len(deadlines), 2)
                self.assertEqual(math.ceil(deadlines[0] / self.p['behavior_dt_s']),
                                 math.ceil(deadlines[1] / self.p['behavior_dt_s']))
                self.assertEqual(deadlines[0] == deadlines[1], states[0] == states[1])

    def test_exact_expiry_and_repeated_same_tick_keep_the_latched_state(self):
        for dt in (.1, .05):
            with self.subTest(dt=dt):
                self.p['control_sync_dt_s'] = dt
                memory, _ = self.step(self.f.memory(), 0.)
                deadline, rng = memory.r5_deadline_s, memory.r5_rng_state
                for index in range(1, math.floor(deadline / dt) + 1):
                    memory, _ = self.step(memory, index * dt)
                memory, diagnostic = self.step(memory, deadline)
                self.assertEqual((memory.r5_phase, diagnostic['reason'], diagnostic['blocking']),
                                 ('YIELD', 'expired_ambiguous_wait', True))
                for allow_draw in (False, True, False):
                    repeated, gate = self.step(memory, deadline, allow_draw=allow_draw)
                    self.assertEqual((repeated, gate), (memory, diagnostic))
                self.assertEqual((memory.r5_deadline_s, memory.r5_rng_state, memory.r5_draw_count),
                                 (deadline, rng, 1))

    def test_visible_ego_front_cannot_shorten_an_unexpired_private_wait(self):
        for dt in (.1, .05):
            with self.subTest(dt=dt):
                self.p['control_sync_dt_s'] = dt
                memory, _ = self.step(self.f.memory(), 0., ((-1.99, 8.25, 8., 0.),))
                deadline = memory.r5_deadline_s
                for index in range(1, math.floor(deadline / dt) + 1):
                    memory, diagnostic = self.step(memory, index * dt, ((-2.01, 8.25, 8., 0.),))
                    self.assertEqual(diagnostic['assessment']['reason'], 'ego_visible_front')
                    self.assertEqual((memory.r5_phase, diagnostic['blocking']), ('BACKOFF', True))
                    self.assertEqual(memory.r5_deadline_s, deadline)
                    self.assertEqual((memory.r5_draw_count, diagnostic['draws_this_tick']), (1, 0))

    def test_expired_visible_ego_front_unlocks_and_renewed_ambiguity_blocks_again(self):
        for dt in (.1, .05):
            with self.subTest(dt=dt):
                memory, _, now = self.expired(dt, dx=-1.99)
                deadline, rng = memory.r5_deadline_s, memory.r5_rng_state
                for index, dx in enumerate((-2.01, -1.99, -2.01), 1):
                    memory, diagnostic = self.step(memory, now + index * dt, ((dx, 8.25, 8., 0.),))
                    front = dx < -2.
                    self.assertEqual(diagnostic['assessment']['reason'], 'ego_visible_front' if front else 'ambiguous')
                    self.assertEqual((memory.r5_phase, diagnostic['blocking']),
                                     ('ELIGIBLE', False) if front else ('YIELD', True))
                    self.assertEqual(diagnostic['reason'], 'private_backoff_expired' if front else 'expired_ambiguous_wait')
                    self.assertEqual((memory.r5_deadline_s, memory.r5_rng_state, memory.r5_draw_count),
                                     (deadline, rng, 1))
                    self.assertEqual(diagnostic['draws_this_tick'], 0)

    def test_every_hard_yield_reason_overrides_an_expired_deadline(self):
        # Gate contract: all assessed HARD_YIELD values must retain precedence.
        # Real geometric classification of these cues is covered in R5Tests.
        for dt in (.1, .05):
            memory, _, now = self.expired(dt)
            for reason in self.f.r5.HARD_YIELD:
                with self.subTest(dt=dt, reason=reason):
                    control = self.f.control(t=now + dt, memory=memory)
                    assessment = {**self.f.assess(control), 'reason': reason}
                    after, diagnostic = self.f.r5.advance_backoff(assessment, memory, now + dt, self.p)
                    self.assertEqual((after.r5_phase, diagnostic['blocking'], diagnostic['reason']),
                                     ('YIELD', True, reason))
                    self.assertEqual((after.r5_deadline_s, after.r5_rng_state, after.r5_draw_count),
                                     (memory.r5_deadline_s, memory.r5_rng_state, 1))
                    self.assertEqual(diagnostic['draws_this_tick'], 0)

    def test_expired_unknown_cannot_be_revived_by_visible_front(self):
        for dt in (.1, .05):
            with self.subTest(dt=dt):
                memory, _, now = self.expired(dt, dx=-1.99)
                deadline, rng = memory.r5_deadline_s, memory.r5_rng_state
                for index in (2, 3, 4):
                    memory, diagnostic = self.step(memory, now + index * dt, ((-2.01, 8.25, 8., 0.),))
                    self.assertEqual(diagnostic['assessment']['reason'], 'ego_visible_front')
                    self.assertEqual((memory.r5_phase, diagnostic['blocking'], diagnostic['reason']),
                                     ('UNKNOWN', True, 'episode_association_unknown'))
                    self.assertEqual((memory.r5_deadline_s, memory.r5_rng_state, memory.r5_draw_count),
                                     (deadline, rng, 1))
                    self.assertEqual(diagnostic['draws_this_tick'], 0)

    def test_expired_wait_requires_stable_clear_before_one_new_reentry_draw(self):
        for dt in (.1, .05):
            with self.subTest(dt=dt):
                memory, _, now = self.expired(dt)
                deadline, rng = memory.r5_deadline_s, memory.r5_rng_state
                count = round(self.p['r5_clear_stable_s'] / dt)
                for index in range(1, count + 2):
                    memory, diagnostic = self.step(memory, now + index * dt, ())
                    self.assertEqual((memory.r5_rng_state, memory.r5_draw_count), (rng, 1))
                    self.assertEqual(diagnostic['draws_this_tick'], 0)
                    self.assertEqual(diagnostic['blocking'], index < count + 1)
                    if index < count + 1:
                        self.assertEqual(memory.r5_deadline_s, deadline)
                    else:
                        self.assertEqual(memory.r5_phase, 'IDLE')
                        self.assertIsNone(memory.r5_episode_signature)
                        self.assertIsNone(memory.r5_deadline_s)
                memory, diagnostic = self.step(memory, now + (count + 2) * dt)
                self.assertEqual((memory.r5_phase, memory.r5_draw_count, diagnostic['draws_this_tick']),
                                 ('BACKOFF', 2, 1))
                self.assertEqual(memory.r5_rng_state, self.f.r5.draw_uniform(rng)[0])
                memory, diagnostic = self.step(memory, now + (count + 3) * dt)
                self.assertEqual((memory.r5_draw_count, diagnostic['draws_this_tick']), (2, 0))

    def test_controller_never_prepares_or_commits_for_persistent_expired_ambiguity(self):
        # A permissive guard isolates whether the real controller honors the gate.
        accept = dict(safe=True, reason='unit_gate_stub', at_s=None, checked_s=5.5)
        for dt in (.1, .05):
            self.p['control_sync_dt_s'] = dt
            for state in (1, 2):
                with self.subTest(dt=dt, state=state):
                    memory = self.f.memory(state)
                    with patch('noa.controller.verify_candidate', return_value=accept) as guard:
                        for index in range(round(3. / dt) + 1):
                            now = index * dt
                            control = self.f.control(t=now, memory=memory,
                                neighbors=((35., 1.65, 3., 0.), (0., 8.25, 8., 0.)))
                            decision = decide(control, self.p)
                            memory = decision.memory
                            self.assertIsNone(memory.plan)
                            self.assertIsNone(memory.prepare_since_s)
                            self.assertEqual(memory.r5_draw_count, 1)
                            self.assertLessEqual(decision.action.acceleration_mps2, -.5)
                            if now >= memory.r5_deadline_s - 1e-9:
                                self.assertEqual(decision.diagnostics['r5']['reason'], 'expired_ambiguous_wait')
                                self.assertEqual(memory.own_behavior, 'R5_YIELD')
                                self.assertTrue(decision.diagnostics['r5']['blocking'])
                    self.assertGreater(guard.call_count, 0)
                    self.assertTrue(all(call.args[1].y_start_m == call.args[1].y_target_m
                                        for call in guard.call_args_list))

    def test_expired_ambiguity_retains_the_real_yield_guard(self):
        for dt in (.1, .05):
            with self.subTest(dt=dt):
                memory, _, now = self.expired(dt)
                control = self.f.control(t=now + dt, memory=memory,
                    neighbors=((35., 1.65, 3., 0.), (0., 8.25, 8., 0.)))
                with patch('noa.controller.verify_candidate', wraps=verify_candidate) as guard:
                    decision = decide(control, self.p)
                self.assertTrue(decision.diagnostics['r5']['blocking'])
                self.assertIsNone(decision.memory.plan)
                self.assertEqual(guard.call_count, 1)
                self.assertEqual(guard.call_args.args[1].y_start_m, guard.call_args.args[1].y_target_m)
                self.assertIsNotNone(decision.diagnostics['r5']['guard'])
                self.assertIn('safe', decision.diagnostics['r5']['guard'])


if __name__ == '__main__':
    unittest.main()
