"""Distributed formation, shape projection, visibility and physical lane clearance."""
from dataclasses import replace
import random
import unittest

from noa import native_rules as r


def car(track, x, lane=0, speed=28.8, **fields):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **fields)


class NativeRulesTests(unittest.TestCase):
    def command(self, ego, rows=(), mode='transform', drop=1000., memory=None):
        return r.decide(ego, tuple(rows), memory or r.Memory(), mode, drop)

    def slot_scene(self):
        return car(0, 810, 1, 20), (
            car(1, 835, 1, 20), car(2, 860, 0, 20), car(3, 760, 0, 20))

    def test_an_unbalanced_three_lane_group_can_fill_before_seeing_the_drop(self):
        group = [car(i, x, lane) for i, (x, lane) in enumerate(
            ((135, 0), (103, 0), (73, 0), (44, 0), (121, 1), (96, 2)))]
        for mode in ('formation', 'transform', 'noa'):
            moves = []
            for ego in group:
                rows = [other for other in group if other is not ego]
                command, _ = self.command(ego, rows, mode=mode, drop=None)
                if command.lane is not None:
                    moves.append((ego.lane, command.lane, command.reason))
            self.assertEqual(moves, [] if mode == 'noa' else [(0, 1, 'formation_fill')])

    def test_balanced_staggered_group_stays_in_its_lanes(self):
        group = [car(i, x, lane) for i, (x, lane) in enumerate(
            ((135, 0), (105, 0), (120, 1), (90, 1), (135, 2), (105, 2)))]
        for ego in group:
            command, _ = self.command(ego, [c for c in group if c is not ego], drop=None)
            self.assertIsNone(command.lane)

    def test_layer_counting_needs_one_visible_end_of_the_group(self):
        ego = car(0, 300)
        for rear, head, can_count in ((220, 460, False), (220, 450, True), (250, 460, True)):
            positions = (rear, 260, 340, 380, 420, head)
            neighbors = [car(i + 1, x) for i, x in enumerate(positions)]
            for mode in ('formation', 'transform'):
                with self.subTest(rear=rear, head=head, mode=mode):
                    command, _ = self.command(ego, neighbors, mode=mode, drop=None)
                    self.assertEqual(command.reason in ('formation_fill', 'formation_align'), can_count)
                    if not can_count:
                        self.assertIsNone(command.lane)
                        self.assertEqual(command.reference, neighbors[2].track)

    def test_same_lane_counts_do_not_prove_the_middle_layer_is_vacant(self):
        ego = car(0, 117, 0)
        neighbors = [car(1, 135, 0), car(2, 85, 0), car(3, 136, 2)]
        vacant = [*neighbors, car(4, 87, 1)]
        occupied = [*neighbors, car(4, 107.5, 1)]
        for scene in (vacant, occupied):
            self.assertTrue(r._clear(ego, scene, 1))
        self.assertEqual(self.command(ego, vacant, drop=None)[0].lane, 1)
        self.assertIsNone(self.command(ego, occupied, drop=None)[0].lane)

    def test_a_head_using_visible_outer_lane_references_reports_participation(self):
        ego = car(0, 135, 0)
        command, _ = self.command(ego, (car(1, 108, 2), car(2, 78, 2)), drop=None)
        self.assertEqual((command.reason, command.formation_state), ('formation_align', 1))

    def test_formation_fill_uses_geometry_not_track_numbers_or_other_groups(self):
        ego = car(0, 103)
        group = [car(1, 135), car(2, 73), car(3, 44), car(4, 121, 1), car(5, 96, 2)]
        cmd, _ = self.command(ego, group, drop=None)
        self.assertEqual((cmd.lane, cmd.reason), (1, 'formation_fill'))
        remapped = [replace(c, track=100 - c.track, pending_lane=0) for c in reversed(group)]
        remote = [car(99, 199, 1), car(98, 222, 1), car(97, 248, 2)]
        other, _ = self.command(replace(ego, track=50), remapped + remote, drop=None)
        self.assertEqual((other.speed, other.lane, other.reason), (cmd.speed, cmd.lane, cmd.reason))
        occupied = [*group, car(6, ego.x + 4, 1)]
        self.assertIsNone(self.command(ego, occupied, drop=None)[0].lane)

    def test_all_modes_ignore_a_road_boundary_outside_two_hundred_metres(self):
        ego = car(0, 799.999, 2)
        for mode in ('noa', 'formation', 'transform'):
            with self.subTest(mode=mode):
                self.assertEqual(self.command(ego, mode=mode), self.command(ego, mode=mode, drop=None))

    def test_exact_road_visibility_boundary_enables_necessary_merge(self):
        for mode in ('noa', 'formation', 'transform'):
            with self.subTest(mode=mode):
                command, memory = self.command(car(0, 800, 2), mode=mode)
                self.assertEqual((command.lane, memory.lane_target), (1, 1))

    def test_noa_overtaking_uses_only_lanes_present_downstream(self):
        ego = car(0, 1020, 1, 10)
        rows = (car(1, 1040, 1, 10), car(2, 1020, 0, 10))
        self.assertEqual(self.command(ego, rows, mode='noa', drop=None)[0].lane, 2)
        command, _ = r.decide(ego, rows, r.Memory(), 'noa', None, lane_count=2)
        self.assertIsNone(command.lane)

    def test_transform_continues_slot_moves_on_observed_two_lane_road(self):
        ego, rows = self.slot_scene()
        ego = replace(ego, x=ego.x + 250)
        rows = tuple(replace(peer, x=peer.x + 250) for peer in rows)
        decision = r.decide(ego, rows, r.Memory(), 'transform', None, lane_count=2)
        self.assertEqual(decision[0].lane, 0)
        self.assertEqual(decision, self.command(ego, rows))

    def test_outside_front_and_rear_observations_do_not_change_the_action(self):
        ego, rows = self.slot_scene()
        outside = (car(91, ego.x + 200.001, 0, 0), car(92, ego.x - 100.001, 1, 33.3))
        self.assertEqual(self.command(ego, rows), self.command(ego, rows + outside))

    def test_neighbor_pending_is_not_communication_or_road_knowledge(self):
        ego, front = car(0, 700, 2), car(1, 730, 2)
        expected = self.command(ego, (front,), drop=None)
        actual = self.command(ego, (replace(front, pending_lane=1),), drop=None)
        self.assertEqual(actual, expected)
        self.assertEqual(actual[0].reason, "formation_fill")

    def test_a_front_changing_lane_does_not_trigger_the_followers_transformation(self):
        ego = car(0, 700, 2)
        front = replace(car(1, 730, 2), y=7.92, vy=-3.3)
        self.assertIsNone(self.command(ego, (front,), drop=None)[0].lane)
        self.assertIsNone(self.command(ego, (front,), mode='formation', drop=None)[0].lane)
        self.assertIsNone(self.command(ego, (replace(front, x=670),), drop=None)[0].lane)

    def test_a_neighbor_near_the_bottleneck_does_not_publish_its_road_knowledge(self):
        ego, far = car(0, 700, 2), car(1, 900, 2)
        self.assertEqual(self.command(ego, (far,)), self.command(ego, (far,), drop=None))
        self.assertIsNone(self.command(ego, (far,))[0].lane)

    def test_ordinary_formation_does_not_make_a_discretionary_slot_move(self):
        ego, rows = self.slot_scene()
        self.assertIsNone(self.command(ego, rows, mode='formation')[0].lane)
        self.assertEqual(self.command(ego, rows)[0].lane, 0)

    def test_each_vehicle_projects_visible_centres_to_its_own_half_gap_position(self):
        ego, rows = self.slot_scene()
        command, memory = self.command(ego, rows)
        h = r.desired_spacing(20) / 2
        expected = (860 - 2*h + 835 - h + 810 + 760 + h) / 4
        self.assertAlmostEqual(command.target_x, expected)
        self.assertEqual((command.lane, command.reference, memory.front), (0, rows[0].track, rows[0].track))
        shift = 34.
        moved = replace(ego, x=ego.x + shift)
        shifted, _ = self.command(moved, [replace(c, x=c.x + shift) for c in rows], drop=1000 + shift)
        self.assertAlmostEqual(shifted.target_x, expected + shift)
        self.assertEqual((shifted.speed, shifted.lane), (command.speed, command.lane))

    def test_isolated_tail_rejoins_only_within_reciprocal_sight(self):
        ego = car(0, 810, 1)
        for distance, joins in ((81., True), (100., True), (100.1, False)):
            front = car(1, ego.x + distance, 1)
            command, _ = self.command(ego, (front,))
            self.assertEqual(bool(command.formation_state), joins)
            self.assertEqual(command.lane, 0 if joins else None)
            self.assertEqual(command.speed > ego.speed, joins)

    def test_both_mirror_shapes_and_an_incomplete_last_pair_are_equilibria(self):
        half = r.desired_spacing(r.CRUISE) / 2
        for n in (5, 6):
            for first in (0, 1):
                group = [car(i, 930 - i*half, (first+i) % 2) for i in range(n)]
                for ego in group:
                    cmd, _ = self.command(ego, [other for other in group if other is not ego])
                    self.assertAlmostEqual(cmd.target_x, ego.x)
                    self.assertAlmostEqual(cmd.speed, r.CRUISE)
                    self.assertIsNone(cmd.lane)
                    self.assertEqual(cmd.formation_state, 1)

    def test_a_blocked_lateral_target_waits_and_a_pending_move_finishes(self):
        ego = car(0, 850, 2, 20)
        blocker = car(1, 853, 1, 20)
        self.assertIsNone(self.command(ego, (blocker,))[0].lane)
        self.assertEqual(self.command(ego, (replace(blocker, x=880),))[0].lane, 1)
        pending = replace(ego, lane=1, pending_lane=1)
        self.assertEqual(self.command(pending, (replace(blocker, x=880),))[0].lane, 1)

    def test_noa_matches_the_visible_target_front_while_its_merge_is_blocked(self):
        ego = car(0, 850, 2, 20)
        current = car(1, 879, 2, 18)
        target = car(2, 870, 1, 12)
        blocker = car(3, 847, 1, 22)
        command, _ = self.command(ego, (current, target, blocker), mode='noa')
        self.assertIsNone(command.lane)
        self.assertEqual((command.reason, command.reference, command.formation_state),
                         ('merge_wait', target.track, 0))
        self.assertAlmostEqual(command.target_x, target.x - r.desired_spacing(ego.speed))

    def test_either_surviving_lane_can_receive_a_missing_alternating_position(self):
        for first in (0, 1):
            front = car(1, 880, first)
            follower = car(2, 850, first)
            self.assertEqual(self.command(follower, (front,))[0].lane, 1 - first)
            self.assertIsNone(self.command(follower, (front,), mode='formation')[0].lane)
        solo, _ = self.command(car(0, 850, 1))
        self.assertEqual((solo.lane, solo.formation_state), (None, 0))

    def test_unwarned_middle_car_does_not_start_a_static_preemptive_left_fill(self):
        ego, rows = self.slot_scene()
        ego = replace(ego, x=700)
        rows = tuple(replace(c, x=c.x - 110) for c in rows)
        cmd, _ = self.command(ego, rows, drop=None)
        self.assertEqual((cmd.lane, cmd.reason), (2, 'formation_fill'))

    def test_transform_moves_are_adjacent_and_target_a_surviving_lane(self):
        rng = random.Random(20261104)
        for lane in range(3):
            for case in range(25):
                ego = car(0, 850, lane, rng.uniform(0, 33.3))
                rows = tuple(car(i + 1, ego.x + rng.uniform(-100, 200),
                                 rng.randrange(3), rng.uniform(0, 33.3)) for i in range(6))
                with self.subTest(lane=lane, case=case):
                    cmd = self.command(ego, rows)[0]
                    if cmd.lane is not None:
                        self.assertIn(cmd.lane, (0, 1))
                        self.assertEqual(abs(cmd.lane - lane), 1)

    def test_merged_car_keeps_the_near_lane_while_a_surviving_car_can_fill_lane_zero(self):
        rows = (car(1, 885, 1, 20), car(2, 900, 0, 20))
        first, memory = self.command(car(0, 850, 2, 20), rows)
        self.assertEqual(first.lane, 1)
        second, memory = self.command(car(0, 850, 1, 20), rows, memory=memory)
        self.assertIsNone(second.lane)
        self.assertIn(0, memory.from_ending)
        _, released = self.command(car(0, 850), (), memory=r.Memory(from_ending=frozenset({55})))
        self.assertFalse(released.from_ending)

    def test_outer_lanes_take_an_incomplete_row_before_the_middle(self):
        group = [car(i, x, lane) for i, (x, lane) in enumerate(
            [(160, 0), (145, 1), (160, 2), (130, 0), (115, 1)])]
        tail = group[-1]
        cmd, _ = self.command(tail, group[:-1], drop=None)
        self.assertEqual((cmd.lane, cmd.reason), (2, 'formation_fill'))
        for ego in group[:-1]:
            self.assertIsNone(self.command(ego, [c for c in group if c is not ego], drop=None)[0].lane)

    def test_four_lane_end_is_local_and_lane_two_continues(self):
        for lane in (2, 3):
            ego = car(0, 999, lane)
            cmd, _ = r.decide(ego, (), r.Memory(), 'transform', 1000., lane_count=4)
            if lane == 3:
                self.assertEqual(cmd.lane, 2)
                self.assertEqual(cmd.speed, 0.)
            else:
                self.assertIsNone(cmd.lane)
                self.assertAlmostEqual(cmd.speed, r.CRUISE)
        ego = car(0, 790, 3)
        self.assertEqual(r.decide(ego, (), r.Memory(), 'transform', 1000., lane_count=4),
                         r.decide(ego, (), r.Memory(), 'transform', None, lane_count=4))

    def test_labels_and_observation_order_do_not_assign_priority(self):
        ego, rows = self.slot_scene()
        expected, _ = self.command(ego, rows)
        remap = {0: 900, 1: 73, 2: 4, 3: 600}
        changed = tuple(replace(c, track=remap[c.track]) for c in reversed(rows))
        actual, _ = self.command(replace(ego, track=remap[0]), changed)
        self.assertEqual((actual.speed, actual.lane, actual.target_x, actual.formation_state),
                         (expected.speed, expected.lane, expected.target_x, expected.formation_state))
        self.assertEqual(actual.reference, remap[expected.reference])

    def test_neighbor_private_actuation_does_not_change_a_real_slot_choice(self):
        ego, rows = self.slot_scene()
        expected = self.command(ego, rows)
        changed = tuple(replace(c, pending_lane=(c.lane + 1) % 3) for c in rows)
        self.assertEqual(self.command(ego, changed), expected)

    def test_phase_uses_physical_lateral_position_not_the_midpoint_lane_index(self):
        crossing = replace(car(0, 100, 1, 20), y=6.6, vy=3.3)
        peer = car(1, 120, 0, 25)
        self.assertEqual(r._pair_error(crossing, peer),
                         r._pair_error(replace(crossing, lane=2), peer))

    def test_free_head_has_no_private_group_or_old_front_speed_dependency(self):
        ego, rear = car(0, 100, 0, 10), car(1, 80, 0, 0)
        command, memory = self.command(ego, (rear,), drop=None, memory=r.Memory(front=rear.track))
        self.assertIsNone(command.reference)
        self.assertGreater(command.speed, ego.speed)
        self.assertIsNone(memory.front)

    def test_an_ordinary_chain_starts_with_a_real_front_within_fifty_metres(self):
        ego = car(0, 100, speed=20)
        for mode in ('formation', 'transform'):
            with self.subTest(mode=mode):
                near, memory = self.command(ego, (car(1, 150, speed=20),), mode, None)
                self.assertEqual((near.reference, memory.front, near.formation_state), (1, 1, 1))
                self.assertAlmostEqual(near.target_x, 150 - (5.5 + .85 * 20))
                for distance in (50.01, 80., 200.):
                    with self.subTest(distance=distance):
                        fresh, own = self.command(
                            ego, (car(1, ego.x + distance, speed=20),), mode, None)
                        self.assertIsNone(fresh.reference)
                        self.assertIsNone(own.front)
                        self.assertEqual(fresh.formation_state, 0)
                        self.assertAlmostEqual(fresh.target_x, ego.x)
                        self.assertAlmostEqual(fresh.speed, 20 + .2 * (28.8 - 20))

    def test_an_existing_chain_tracks_the_current_front_then_releases_on_loss(self):
        ego = car(0, 100, speed=20)
        for mode in ('formation', 'transform'):
            with self.subTest(mode=mode):
                _, memory = self.command(ego, (car(1, 122.5, speed=20),), mode, None)
                self.assertEqual(memory.front, 1)
                for distance in (80., 200.):
                    with self.subTest(distance=distance):
                        replacement = car(2, ego.x + distance, speed=20)
                        # The old front is still sensed on another lane, outside the phase graph.
                        old = car(1, 195, lane=1, speed=20)
                        command, own = self.command(
                            ego, (replacement, old), mode, None, memory)
                        target = replacement.x - (5.5 + .85 * ego.speed)
                        expected = min(33.3, 20 + .2 * (.3 * (target - ego.x)))
                        self.assertEqual((command.reference, own.front, command.formation_state), (2, 2, 1))
                        self.assertAlmostEqual(command.target_x, target)
                        self.assertAlmostEqual(command.speed, expected)
                for rows in ((), (car(2, 300.01, speed=20),)):
                    with self.subTest(rows=rows):
                        lost, released = self.command(ego, rows, mode, None, memory)
                        self.assertEqual((lost.reference, released.front, lost.formation_state), (None, None, 0))
                        returned, own = self.command(
                            ego, (car(2, 180, speed=20),), mode, None, released)
                        self.assertIsNone(returned.reference)
                        self.assertIsNone(own.front)
                        self.assertAlmostEqual(returned.speed, 20 + .2 * (28.8 - 20))


if __name__ == '__main__':
    unittest.main()
