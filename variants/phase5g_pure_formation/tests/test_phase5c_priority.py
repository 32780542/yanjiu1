"""Lane-first priority contracts; finite traces do not prove finite passage."""
from dataclasses import asdict, replace
import itertools
import unittest
from unittest.mock import patch

import test_phase5_r5_controller as fixtures
from models.bezier import QuadraticLaneChange
from noa.controller import decide
from noa.formation import FormationMemory, decide as formation_decide
from noa.prediction import verify_candidate
from noa.road import reconstruct


class LanePriorityTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.R5Tests()
        self.f.setUp()
        self.p = self.f.p
        self.p['r5_lane_priority_enabled'] = True
        self.r5 = self.f.r5

    def assess(self, control, target=4.95, parameters=None):
        p = self.p if parameters is None else parameters
        road = reconstruct(control.ego, control.observation.road, p)
        candidate = QuadraticLaneChange(control.ego.time_s, control.ego.y_m, target, 5., 8.)
        return self.r5.assess_candidate(control, road, candidate, control.memory, p)

    def advance(self, control):
        return self.r5.advance_backoff(self.assess(control), control.memory, control.ego.time_s, self.p)

    def with_world_road(self, control, boundaries, markings):
        # Test fixtures use heading zero. Geometry is still passed as observations.
        def local(lines):
            return tuple(tuple((x-control.ego.x_m, y-control.ego.y_m) for x, y in line)
                         for line in lines)
        road = replace(control.observation.road, boundary_polylines_m=local(boundaries),
                       marking_polylines_m=local(markings))
        return replace(control, observation=replace(control.observation, road=road))

    def test_upper_rear_has_lane_priority_for_both_egos_and_all_longitudinal_boundaries(self):
        for dx in (-4., -2., 0., 2., 4.):
            for ego_y, peer_y, expected, blocked in (
                    (1.65, 8.25, 'yield_visible_upper_lane', True),
                    (8.25, 1.65, 'ego_visible_upper_lane', False)):
                with self.subTest(dx=dx, ego_y=ego_y):
                    c = self.f.control(y=ego_y, neighbors=((dx, peer_y, 8., 0.),))
                    assessment = self.assess(c)
                    self.assertEqual(assessment['reason'], expected)
                    memory, gate = self.advance(c)
                    self.assertEqual(gate['blocking'], blocked)
                    self.assertEqual((memory.r5_draw_count, gate['draws_this_tick']), (0, 0))
                    self.assertIsNone(memory.r5_deadline_s)

    def test_same_lane_retains_strict_two_metre_boundary_despite_lateral_offsets(self):
        expected = ('ego_visible_front', 'ambiguous', 'ambiguous', 'ambiguous', 'yield_visible_front')
        for y in (1.55, 1.65, 1.75):
            for dx, reason in zip((-2.0001, -2., 0., 2., 2.0001), expected):
                with self.subTest(y=y, dx=dx):
                    self.assertEqual(self.assess(self.f.control(neighbors=((dx, y, 8., 0.),)))['reason'], reason)

    def test_pair_relation_is_lane_first_and_has_no_strict_cycle(self):
        relation = getattr(self.r5, '_lane_relation', None)
        self.assertIsNotNone(relation, 'Missing independently testable lane-first relation')
        actors = ((8.25, 0.), (4.95, 1.5), (1.65, 3.))
        for a, b, c in itertools.permutations(actors):
            ab, bc, ac = (relation(u[0], v[0], v[1]-u[1], 2.)
                          for u, v in ((a, b), (b, c), (a, c)))
            self.assertEqual(ab, -relation(b[0], a[0], a[1]-b[1], 2.))
            if ab == bc == -1:
                self.assertEqual(ac, -1)
        self.assertEqual(relation(8.25, 1.65, 3., 2.), -1)
        self.assertEqual(relation(1.65, 8.25, -3., 2.), 1)
        self.assertEqual(relation(1.65, 1.65, 1.5, 2.), 0)
        self.assertEqual(relation(1.65, 1.65, 3., 2.), 1)
        self.assertEqual(relation(None, 8.25, 100., 2.), 0)
        self.assertEqual(relation(8.25, None, -100., 2.), 0)

    def test_every_participant_order_has_the_same_pairwise_reduction(self):
        # Higher, lower and unknown peers: a trusted higher peer is decisive.
        peers = ((-4., 8.25, 8., 0.), (-3., 1.65, 8., 0.), (-2., .5, 8., 0.))
        results = [self.assess(self.f.control(neighbors=order)) for order in itertools.permutations(peers)]
        self.assertEqual({a['reason'] for a in results}, {'yield_visible_upper_lane'})
        self.assertTrue(all(a == results[0] for a in results))

    def test_unknown_peer_never_helps_release_but_higher_trusted_peer_still_blocks(self):
        for peers, expected in (
                (((-4., 1.65, 8., 0.), (-3., .5, 8., 0.)), 'ambiguous'),
                (((-4., .5, 8., 0.),), 'ambiguous'),
                (((-4., 8.25, 8., 0.), (-3., .5, 8., 0.)), 'yield_visible_upper_lane')):
            self.assertEqual(self.assess(self.f.control(neighbors=peers))['reason'], expected)

    def test_all_trusted_lower_peers_release_and_same_lane_tie_blocks(self):
        upper = self.f.control(y=8.25, neighbors=((4., 1.65, 8., 0.), (-3., 8.2, 8., 0.)))
        self.assertEqual(self.assess(upper)['reason'], 'ego_visible_upper_lane')
        tied = self.f.control(y=8.25, neighbors=((4., 1.65, 8., 0.), (-2., 8.2, 8., 0.)))
        self.assertEqual(self.assess(tied)['reason'], 'ambiguous')

    def test_entered_inward_and_occupied_retain_precedence(self):
        for y in (2.5, 4.95):
            self.assertEqual(self.assess(self.f.control(y=8.25, neighbors=((-4., y, 8., 0.),)))['reason'], 'yield_entered')
        for vy, expected in ((.051, 'yield_visible_inward_motion'), (.05, 'ego_visible_upper_lane'),
                             (.049, 'ego_visible_upper_lane')):
            self.assertEqual(self.assess(self.f.control(y=8.25, neighbors=((-4., 1.65, 8., vy),)))['reason'], expected)
        # A very long measured body outside the target's adjacent source lanes
        # intersects its corridor, while the existing near filter excludes it.
        c = self.f.control(y=8.25, neighbors=((0., 13.2, 8., 0.),))
        n = replace(c.observation.neighbors[0], width_m=20.)
        c = replace(c, observation=replace(c.observation, neighbors=(n,)))
        c = self.with_world_road(c, (((0., 0.), (200., 0.)), ((0., 16.5), (200., 16.5))),
                                tuple(((0., y), (200., y)) for y in (3.3, 6.6, 9.9, 13.2)))
        self.assertEqual(self.assess(c)['reason'], 'yield_occupied_corridor')

    def test_source_strip_crossing_and_center_equidistance_are_untrusted(self):
        # The source is above the target; ambiguity concerns its other boundary.
        for y in (9.9, 9.2):
            c = self.f.control(y=8.25, neighbors=((-4., y, 8., 0.),))
            c = self.with_world_road(c, (((0., 0.), (200., 0.)), ((0., 13.2), (200., 13.2))),
                                    tuple(((0., v), (200., v)) for v in (3.3, 6.6, 9.9)))
            self.assertEqual(self.assess(c)['reason'], 'ambiguous')
        # Ego cannot use its nearest lower center as a certificate either.
        c = self.f.control(y=.5, neighbors=((-4., 1.65, 8., 0.),))
        self.assertEqual(self.assess(c)['reason'], 'ambiguous')

    def test_missing_source_boundary_is_ambiguous_while_target_is_reconstructable(self):
        c = self.f.control(y=8.25, neighbors=((-4., 1.65, 8., 0.),))
        # Lower road boundary is absent at the peer, but both target edges exist.
        c = self.with_world_road(c, (((98., 0.), (200., 0.)), ((0., 9.9), (200., 9.9))),
                                (((0., 3.3), (200., 3.3)), ((0., 6.6), (200., 6.6))))
        self.assertEqual(self.assess(c)['reason'], 'ambiguous')

    def test_peer_source_lane_not_extrapolated_past_visible_end(self):
        for end in (97., 95.):
            c = self.f.control(y=1.65, neighbors=((-4., 8.25, 8., 0.),))
            # At end=97 the peer center still has its lane, but its full body
            # does not. At end=95 even the center is beyond the visible end.
            c = self.with_world_road(c, (((0., 0.), (200., 0.)),
                                        ((0., 9.9), (end, 9.9)),
                                        ((end, 6.6), (200., 6.6))),
                                    (((0., 3.3), (200., 3.3)), ((0., 6.6), (end, 6.6))))
            self.assertEqual(self.assess(c)['reason'], 'ambiguous')

    def test_source_geometry_gap_inside_body_and_rotated_body_are_untrusted(self):
        c = self.f.control(y=8.25, neighbors=((-4., 1.65, 8., 0.),))
        c = self.with_world_road(c, (((0., -3.3), (200., -3.3)), ((0., 9.9), (200., 9.9))),
                                (((0., 0.), (95., 0.)), ((95.5, 0.), (200., 0.)),
                                 ((0., 3.3), (200., 3.3)), ((0., 6.6), (200., 6.6))))
        self.assertEqual(self.assess(c)['reason'], 'ambiguous')
        c = self.f.control(y=8.25, neighbors=((-4., 8.25, 8., 0.),))
        n = replace(c.observation.neighbors[0], relative_heading_rad=.8)
        c = replace(c, observation=replace(c.observation, neighbors=(n,)))
        # Rotated corners now touch the target: the original entered guard wins.
        self.assertEqual(self.assess(c)['reason'], 'yield_entered')

    def test_missing_target_geometry_still_rejects(self):
        c = self.f.control()
        c = replace(c, observation=replace(c.observation, road=replace(c.observation.road,
                                                                    marking_polylines_m=())))
        with self.assertRaisesRegex(ValueError, 'visible center'):
            self.assess(c, target=1.65)

    def test_lane_priority_switch_requires_exact_bool_in_assessment_and_controller(self):
        for value in (None, 0, 1, 'true', [], float('nan')):
            with self.subTest(value=value):
                p = {**self.p, 'r5_lane_priority_enabled': value}
                with self.assertRaisesRegex(ValueError, 'r5_lane_priority_enabled'):
                    self.assess(self.f.control(), parameters=p)
                with self.assertRaisesRegex(ValueError, 'r5_lane_priority_enabled'):
                    decide(self.f.control(neighbors=(), speed=4.9), p)

    def test_switch_absent_and_false_preserve_original_assessments_actions_and_memory(self):
        absent = {k: v for k, v in self.p.items() if k != 'r5_lane_priority_enabled'}
        disabled = {**self.p, 'r5_lane_priority_enabled': False}
        for dx in (-4., -2., 0., 2., 4.):
            c = self.f.control(neighbors=((35., 1.65, 3., 0.), (dx, 8.25, 8., 0.)))
            self.assertEqual(self.assess(c, parameters=absent), self.assess(c, parameters=disabled))
            self.assertEqual(decide(c, absent), decide(c, disabled))
        c = self.f.control()
        self.assertEqual(decide(c, {**self.p, 'r5_enabled': False}),
                         decide(c, {**disabled, 'r5_enabled': False}))

    def test_new_reason_is_hard_yield_with_an_expired_private_deadline(self):
        self.assertIn('yield_visible_upper_lane', self.r5.HARD_YIELD)
        # Association remains exact: establish a legacy deadline for this same
        # physics, then continue with lane-first and its new hard reason.
        c = self.f.control()
        legacy = {**self.p, 'r5_lane_priority_enabled': False}
        m, _ = self.r5.advance_backoff(self.assess(c, parameters=legacy), c.memory, 0., legacy)
        deadline, rng = m.r5_deadline_s, m.r5_rng_state
        for tick in range(1, 31):
            m, gate = self.advance(self.f.control(t=tick*.1, memory=m))
            self.assertEqual((m.r5_phase, gate['blocking'], gate['reason']),
                             ('YIELD', True, 'yield_visible_upper_lane'))
            self.assertEqual((m.r5_deadline_s, m.r5_rng_state, m.r5_draw_count), (deadline, rng, 1))

    def test_same_lane_expiry_ambiguity_stays_waiting_without_redraw(self):
        m = self.f.memory()
        deadline = None
        for tick in range(31):
            m, gate = self.advance(self.f.control(t=tick*.1, memory=m, neighbors=((0., 1.65, 8., 0.),)))
            deadline = m.r5_deadline_s if deadline is None else deadline
            self.assertEqual(m.r5_deadline_s, deadline)
            self.assertTrue(gate['blocking'])
            self.assertEqual(m.r5_draw_count, 1)
        self.assertEqual(gate['reason'], 'expired_ambiguous_wait')

    def test_new_clear_lane_priority_respects_own_deadline_and_unknown(self):
        c = self.f.control(y=8.25, neighbors=((0., 1.65, 8., 0.),))
        legacy = {**self.p, 'r5_lane_priority_enabled': False}
        old, _ = self.r5.advance_backoff(self.assess(c, parameters=legacy), c.memory, 0., legacy)
        deadline = old.r5_deadline_s
        m, gate = self.advance(self.f.control(t=.1, y=8.25, memory=old, neighbors=((0., 1.65, 8., 0.),)))
        self.assertEqual(gate['assessment']['reason'], 'ego_visible_upper_lane')
        self.assertEqual((gate['reason'], gate['blocking'], m.r5_deadline_s), ('private_backoff_wait', True, deadline))
        continuous = m
        for tick in range(2, 31):
            continuous, gate = self.advance(self.f.control(t=tick*.1, y=8.25, memory=continuous,
                                                          neighbors=((0., 1.65, 8., 0.),)))
            self.assertEqual(gate['blocking'], tick*.1 < deadline-1e-9)
            self.assertEqual((continuous.r5_draw_count, continuous.r5_deadline_s), (1, deadline))
        self.assertEqual(continuous.r5_phase, 'ELIGIBLE')
        m, gate = self.advance(self.f.control(t=.5, y=8.25, memory=m, neighbors=((0., 1.65, 8., 0.),)))
        self.assertEqual((m.r5_phase, gate['reason'], gate['blocking']), ('UNKNOWN', 'episode_association_unknown', True))
        for tick in range(6, 31):
            m, gate = self.advance(self.f.control(t=tick*.1, y=8.25, memory=m, neighbors=((0., 1.65, 8., 0.),)))
            self.assertEqual((m.r5_phase, m.r5_draw_count, m.r5_deadline_s, gate['blocking']), ('UNKNOWN', 1, deadline, True))

    def test_label_line_order_and_translation_do_not_change_priority_or_action(self):
        c = self.f.control(neighbors=((35., 1.65, 3., 0.), (-4., 8.25, 8., 0.)))
        neighbors = tuple(replace(n, track_id=900-i) for i, n in enumerate(reversed(c.observation.neighbors)))
        road = replace(c.observation.road,
                       boundary_polylines_m=tuple(tuple(reversed(line)) for line in reversed(c.observation.road.boundary_polylines_m)),
                       marking_polylines_m=tuple(tuple(reversed(line)) for line in reversed(c.observation.road.marking_polylines_m)))
        renamed = replace(c, observation=replace(c.observation, road=road, neighbors=neighbors))
        self.assertEqual(self.assess(c), self.assess(renamed))
        self.assertEqual(decide(c, self.p), decide(renamed, self.p))
        shifted = replace(renamed, ego=replace(c.ego, x_m=c.ego.x_m+100., y_m=c.ego.y_m+12.))
        a, b = self.assess(c), self.assess(shifted, target=16.95)
        self.assertEqual(a['reason'], b['reason'])
        for before, after in zip(a['participant_signatures'], b['participant_signatures']):
            self.assertAlmostEqual(after[0]-before[0], 100.)
            self.assertAlmostEqual(after[1]-before[1], 12.)
            self.assertEqual(before[2:], after[2:])
        d1, d2 = decide(c, self.p), decide(shifted, self.p)
        self.assertEqual(d1.action, d2.action)
        self.assertEqual((d1.memory.r5_draw_count, d1.memory.r5_deadline_s),
                         (d2.memory.r5_draw_count, d2.memory.r5_deadline_s))

    def test_real_decide_unrequested_upper_rear_stays_cruise_and_blocks_lower(self):
        # A local observation trace, not a driving rollout or a fairness proof.
        # The upper actor has no slow lead and never requests a lane change.
        lower, upper = self.f.memory(), self.f.memory()
        for tick in range(31):
            t = tick*.1
            upper_c = self.f.control(t=t, x=96., y=8.25, memory=upper,
                                    neighbors=((4., 1.65, 8., 0.), (39., 1.65, 3., 0.)))
            upper_d = decide(upper_c, self.p)
            upper = upper_d.memory
            self.assertEqual(upper.own_behavior, 'CRUISE')
            self.assertIsNone(upper.plan)
            lower_d = decide(self.f.control(t=t, memory=lower,
                                neighbors=((35., 1.65, 3., 0.), (-4., 8.25, 8., 0.))), self.p)
            lower = lower_d.memory
            self.assertIsNone(lower.plan)
            self.assertIsNone(lower.prepare_since_s)
            self.assertTrue(lower_d.diagnostics['r5']['blocking'])
            self.assertEqual(lower_d.diagnostics['r5']['assessment']['reason'], 'yield_visible_upper_lane')
            self.assertEqual(lower.r5_draw_count, 0)
        self.assertGreater(t, self.p['r5_backoff_max_s'])

    def test_real_decide_unrequested_same_lane_slow_lead_keeps_blocking(self):
        memory = self.f.memory()
        for tick in range(31):
            t = tick*.1
            lead = decide(self.f.control(t=t, x=130., speed=3., neighbors=()), self.p)
            self.assertIsNone(lead.memory.plan)
            c = self.f.control(t=t, memory=memory, neighbors=((30., 1.65, 3., 0.),))
            d = decide(c, self.p)
            memory = d.memory
            self.assertIsNone(memory.plan)
            self.assertTrue(d.diagnostics['r5']['blocking'])
            self.assertEqual(d.diagnostics['r5']['assessment']['reason'], 'yield_visible_front')
            self.assertEqual(memory.r5_draw_count, 0)

    def test_real_decide_upper_rear_also_blocks_beyond_inherited_private_deadline(self):
        peers = ((35., 1.65, 3., 0.), (-1.99, 8.25, 8., 0.))
        c = self.f.control(neighbors=peers)
        legacy = {**self.p, 'r5_lane_priority_enabled': False}
        memory, _ = self.r5.advance_backoff(self.assess(c, parameters=legacy), c.memory, 0., legacy)
        deadline, rng = memory.r5_deadline_s, memory.r5_rng_state
        for tick in range(1, 31):
            d = decide(self.f.control(t=tick*.1, memory=memory, neighbors=peers), self.p)
            memory = d.memory
            self.assertIsNone(memory.plan)
            self.assertIsNone(memory.prepare_since_s)
            self.assertTrue(d.diagnostics['r5']['blocking'])
            self.assertEqual(d.diagnostics['r5']['assessment']['reason'], 'yield_visible_upper_lane')
            self.assertEqual((memory.r5_deadline_s, memory.r5_rng_state, memory.r5_draw_count), (deadline, rng, 1))
        self.assertGreater(3., deadline)

    def test_prepare_is_rechecked_and_entered_peer_cancels_it(self):
        accept = dict(safe=True, reason='unit_gate_stub', at_s=None, checked_s=5.5)
        with patch('noa.controller.verify_candidate', return_value=accept):
            first = decide(self.f.control(y=8.25, neighbors=((35., 8.25, 3., 0.), (4., 1.65, 8., 0.))), self.p)
            self.assertEqual(first.memory.own_behavior, 'PREPARE_LC')
            self.assertEqual(first.diagnostics['r5']['assessment']['reason'], 'ego_visible_upper_lane')
            second = decide(self.f.control(t=.1, y=8.25, memory=first.memory,
                            neighbors=((35., 8.25, 3., 0.), (4., 2.5, 8., 0.))), self.p)
        self.assertIsNone(second.memory.plan)
        self.assertIsNone(second.memory.prepare_since_s)
        self.assertEqual(second.diagnostics['r5']['assessment']['reason'], 'yield_entered')
        self.assertTrue(second.diagnostics['r5']['blocking'])

    def test_priority_cannot_bypass_original_candidate_guard_or_minimum_speed(self):
        # A visible target-lane front anchor is outside near contention, but
        # its future reachable occupancy still makes the original guard reject.
        c = self.f.control(y=8.25, neighbors=((35., 8.25, 3., 0.), (4., 1.65, 8., 0.), (20., 4.95, 8., 0.)))
        with patch('noa.controller.verify_candidate', wraps=verify_candidate) as guard:
            d = decide(c, self.p)
        self.assertGreater(guard.call_count, 0)
        self.assertEqual(d.diagnostics['r5']['assessment']['reason'], 'ego_visible_upper_lane')
        self.assertFalse(d.diagnostics['r5']['candidate_guard']['safe'])
        self.assertIsNone(d.memory.plan)
        low = decide(self.f.control(y=8.25, speed=4.9, neighbors=((35., 8.25, 3., 0.),)), self.p)
        self.assertIsNone(low.memory.plan)
        self.assertIsNone(low.memory.prepare_since_s)
        self.assertEqual(low.memory.r5_draw_count, 0)

    def test_active_plan_keeps_original_bypass_and_formation_episode_suppression(self):
        plan = QuadraticLaneChange(0., 1.65, 4.95, 5., 8.)
        c = self.f.control(t=1., y=plan.at(1.)['y_m'],
                           memory=self.f.memory(plan=plan, target_y_m=plan.y_target_m))
        d = decide(c, self.p)
        old = decide(c, {**self.p, 'r5_lane_priority_enabled': False})
        self.assertEqual(d, old)
        self.assertEqual(d.diagnostics['r5']['reason'], 'active_plan_bypass')
        c = self.f.control(neighbors=((35., 1.65, 3., 0.), (-4., 8.25, 8., 0.)))
        c = replace(c, memory=FormationMemory(**asdict(c.memory)))
        formed = formation_decide(c, self.p)
        self.assertTrue(formed.diagnostics['r5']['blocking'])
        self.assertEqual(formed.diagnostics['formation']['applied_increment_mps2'], 0.)


if __name__ == '__main__':
    unittest.main()
