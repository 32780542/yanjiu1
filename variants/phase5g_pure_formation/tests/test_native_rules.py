"""Installed C8 contracts: local information, monotone moves and actual slots."""
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

    def test_outside_front_and_rear_observations_do_not_change_the_action(self):
        ego, rows = self.slot_scene()
        outside = (car(91, ego.x + 200.001, 0, 0), car(92, ego.x - 100.001, 1, 33.3))
        self.assertEqual(self.command(ego, rows), self.command(ego, rows + outside))

    def test_neighbor_pending_is_not_communication_or_road_knowledge(self):
        ego, front = car(0, 700, 2), car(1, 730, 2)
        expected = self.command(ego, (front,), drop=None)
        actual = self.command(ego, (replace(front, pending_lane=1),), drop=None)
        self.assertEqual(actual, expected)
        self.assertIsNone(actual[0].lane)

    def test_only_actual_front_folding_guides_an_unwarned_ending_follower(self):
        ego = car(0, 700, 2)
        front = replace(car(1, 730, 2), y=7.92, vy=-3.3)
        self.assertEqual(self.command(ego, (front,), drop=None)[0].lane, 1)
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

    def test_left_fill_uses_the_actual_front_minus_dynamic_entry_spacing(self):
        ego, rows = self.slot_scene()
        command, memory = self.command(ego, rows)
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reference, rows[1].track)
        self.assertAlmostEqual(command.target_x, 860 - (5.5 + .85 * 20))
        self.assertEqual(memory.front, rows[1].track)

    def test_a_current_eight_metre_corridor_is_not_a_full_rear_entry_slot(self):
        ego, rows = self.slot_scene()
        rows = (rows[0], rows[1], car(3, 820, 0, 20))
        self.assertTrue(r._clear(ego, rows, 0))
        self.assertIsNone(self.command(ego, rows)[0].lane)

    def test_fill_rejects_a_slot_that_increases_original_front_half_spacing_error(self):
        ego, rows = self.slot_scene()
        rows = (rows[0], car(2, 900, 0, 20), rows[2])
        self.assertTrue(r._clear(ego, rows, 0))
        self.assertIsNone(self.command(ego, rows)[0].lane)

    def test_an_empty_target_lane_does_not_create_a_synthetic_slot(self):
        ego, rows = self.slot_scene()
        self.assertIsNone(self.command(ego, (rows[0],))[0].lane)

    def test_unwarned_middle_car_does_not_start_a_static_preemptive_left_fill(self):
        ego, rows = self.slot_scene()
        ego = replace(ego, x=700)
        rows = tuple(replace(c, x=c.x - 110) for c in rows)
        self.assertIsNone(self.command(ego, rows, drop=None)[0].lane)

    def test_transform_moves_are_only_toward_retained_lanes(self):
        rng = random.Random(20261104)
        for lane in range(3):
            for case in range(25):
                ego = car(0, 850, lane, rng.uniform(0, 33.3))
                rows = tuple(car(i + 1, ego.x + rng.uniform(-100, 200),
                                 rng.randrange(3), rng.uniform(0, 33.3)) for i in range(6))
                with self.subTest(lane=lane, case=case):
                    self.assertIn(self.command(ego, rows)[0].lane, (None, lane - 1) if lane else (None,))

    def test_ending_car_can_take_two_adjacent_left_moves_without_a_permanent_role(self):
        rows = (car(1, 885, 1, 20), car(2, 900, 0, 20))
        first, memory = self.command(car(0, 850, 2, 20), rows)
        self.assertEqual(first.lane, 1)
        second, memory = self.command(car(0, 850, 1, 20), rows, memory=memory)
        self.assertEqual(second.lane, 0)
        third, _ = self.command(car(0, 850, 0, 20), rows, memory=memory)
        self.assertIsNone(third.lane)

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
        self.assertEqual(r._pair_error(crossing, peer, 3),
                         r._pair_error(replace(crossing, lane=2), peer, 3))

    def test_free_head_has_no_private_group_or_old_front_speed_dependency(self):
        ego, rear = car(0, 100, 0, 10), car(1, 80, 0, 0)
        command, memory = self.command(ego, (rear,), drop=None, memory=r.Memory(front=rear.track))
        self.assertIsNone(command.reference)
        self.assertGreater(command.speed, ego.speed)
        self.assertIsNone(memory.front)


if __name__ == '__main__':
    unittest.main()
