"""原生SUMO运行前，本车规则的几何、信息边界与动作反例。"""

import importlib.util
from dataclasses import replace
import unittest


class NativeRulesTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("noa.native_rules"), "缺少原生SUMO的本车规则模块"
        )
        from noa import native_rules

        self.r = native_rules

    def car(self, track, x, lane, speed=28.8):
        return self.r.Vehicle(track, x, (lane + 0.5) * 3.3, speed, lane)

    def command(self, ego, others=(), mode="transform", drop=1000.0):
        return self.r.decide(ego, tuple(others), self.r.Memory(), mode, drop)[0]

    def six(self):
        return [
            self.car(i, x, lane)
            for i, (x, lane) in enumerate(
                ((700.0, 2), (670.0, 2), (685.0, 1), (655.0, 1), (700.0, 0), (670.0, 0))
            )
        ]

    def test_near_front_forms_a_chain_but_far_front_remains_only_safety_observed(self):
        ego = self.car(0, 100.0, 2)
        near = self.car(1, 145.0, 2)
        speed, target, reference, _ = self.r._following(ego, [near], 3)
        self.assertEqual(reference, near.track)
        self.assertAlmostEqual(target, near.x - self.r.GAP)
        self.assertGreater(speed, self.r.CRUISE)
        far = self.car(2, 170.0, 2)
        speed, target, reference, _ = self.r._following(ego, [far], 3)
        self.assertIsNone(reference)
        self.assertEqual(target, ego.x)
        self.assertAlmostEqual(speed, self.r.CRUISE)
        stopped_outside_chain = self.car(3, 160.48, 2, 0.0)
        self.assertIsNone(self.r._following(ego, [stopped_outside_chain], 3)[2])
        self.assertLess(self.r.safe_speed(ego, [stopped_outside_chain]), self.r.MAX_SPEED)

    def test_aligned_car_tracks_temporary_reference_speed_without_extra_acceleration(self):
        ego = self.car(0, 100.0, 2, 31.0)
        distance = 5.5 + (30.0 - 5.5) / 28.8 * ego.speed
        command = self.command(ego, [self.car(1, ego.x + distance, 2, 31.0)], drop=None)
        self.assertAlmostEqual(command.speed, 31.0)

    def test_equal_speed_target_gap_keeps_cruise(self):
        ego = self.car(0, 100.0, 2)
        self.assertAlmostEqual(self.command(ego, [self.car(1, 130.0, 2)], drop=None).speed, 28.8)

    def test_middle_front_car_makes_room_in_the_other_retained_lane(self):
        cars = self.six()
        ego = replace(cars[2], track=0)
        others = [c for i, c in enumerate(cars) if i != 2]
        others = [replace(c, track=i + 1) for i, c in enumerate(others)]
        self.assertEqual(self.command(ego, others).lane, 0)

    def test_ending_front_uses_safe_space_without_waiting_for_other_plans(self):
        cars = self.six()
        self.assertEqual(self.command(cars[0], cars[1:]).lane, 1)

    def test_after_middle_moves_ending_front_can_merge(self):
        cars = self.six()
        cars[2] = replace(cars[2], lane=0, y=1.65)
        self.assertEqual(self.command(cars[0], cars[1:]).lane, 1)

    def test_occupied_target_lane_is_not_overwritten(self):
        ego = self.car(0, 700.0, 2)
        command = self.command(ego, [self.car(1, 700.0, 1)])
        self.assertIsNone(command.lane)

    def test_local_track_permutation_and_remote_cars_do_not_change_action(self):
        cars = self.six()
        ego = replace(cars[2], track=0)
        others = [
            replace(c, track=i + 1) for i, c in enumerate(c for j, c in enumerate(cars) if j != 2)
        ]
        expected = self.command(ego, others)
        changed = [replace(c, track=101 - 3 * i) for i, c in enumerate(reversed(others))]
        changed.append(self.car(999, 10000.0, 0, 0.0))
        actual = self.command(ego, changed)
        self.assertEqual(
            (expected.speed, expected.lane, expected.target_x),
            (actual.speed, actual.lane, actual.target_x),
        )

    def test_noa_is_a_working_mandatory_merge_policy(self):
        ego = self.car(0, 700.0, 2)
        self.assertEqual(
            self.command(ego, [self.car(1, 750.0, 1), self.car(2, 650.0, 1)], mode="noa").lane, 1
        )

    def test_ordinary_merge_tracks_the_safe_gap_already_beside_the_car(self):
        ego = self.car(0, 718.0, 2)
        rows = [self.car(1, 730.0, 1), self.car(2, 706.0, 1)]
        for mode in ("noa", "formation"):
            with self.subTest(mode=mode):
                command = self.command(ego, rows, mode=mode)
                self.assertEqual(command.lane, 1)
                self.assertAlmostEqual(command.target_x, 718.0)
                self.assertAlmostEqual(command.speed, 28.8)

    def test_position_and_relative_speed_feedback_has_a_gradual_response(self):
        ego = self.car(0, 100.0, 0, 20.0)
        self.assertAlmostEqual(self.r._request(ego, 110.0, 20.0), 20.6)
        self.assertAlmostEqual(self.r._request(ego, 100.0, 15.0), 19.0)
        self.assertAlmostEqual(self.r._request(ego, 100.0, 20.0), 20.0)

    def test_upstream_extra_car_fills_the_nearby_missing_middle_slot(self):
        ego = self.car(0, 285.0, 0)
        others = [
            self.car(1, 300.0, 2),
            self.car(2, 270.0, 2),
            self.car(3, 255.0, 1),
            self.car(4, 300.0, 0),
            self.car(5, 270.0, 0),
        ]
        self.assertEqual(self.command(ego, others, mode="formation", drop=None).lane, 1)

    def test_equal_distance_actual_heads_use_signed_geometry_not_track_order(self):
        ego = self.car(0, 300.0, 0)
        # Both peers are actual heads (>50m apart), equally close in phase.
        others = [self.car(99, 259.0, 1), self.car(1, 311.0, 1)]
        a = self.r._following(ego, others, 3)
        changed = [replace(c, track=100-c.track) for c in reversed(others)]
        b = self.r._following(ego, changed, 3)
        self.assertEqual(a, b)
        self.assertLess(a[1], ego.x)
        self.assertLess(a[0], self.r.CRUISE)
        self.assertLessEqual(abs(self.r.POSITION_GAIN * (a[1] - ego.x)), 2.0 + 1e-9)

    def test_transform_approaches_current_gap_without_skipping_its_front(self):
        ego = self.car(0, 700.0, 2)
        others = [
            self.car(i + 1, x, lane)
            for i, (x, lane) in enumerate(
                ((690.0, 1), (705.0, 1), (730.0, 1), (690.0, 0), (705.0, 0), (730.0, 0))
            )
        ]
        a = self.command(ego, others)
        self.assertGreaterEqual(a.target_x, 690.0)
        self.assertLessEqual(a.target_x, 705.0)

    def test_executing_helper_keeps_the_actual_receiving_gap(self):
        cars = self.six()
        ego = replace(cars[2], track=0)
        others = [
            replace(c, track=i + 1) for i, c in enumerate(c for j, c in enumerate(cars) if j != 2)
        ]
        memory = self.r.Memory(lane_target=0)
        a, _ = self.r.decide(ego, tuple(others), memory, "transform", 1000.0)
        self.assertAlmostEqual(a.speed, 28.8)
        # 横移期间保持700与670之间的实际间隙，居中后再30m入列。
        self.assertAlmostEqual(a.target_x, 685.0)

    def test_free_lane_ahead_does_not_slow_a_merging_leader(self):
        ego = self.car(0, 700.0, 2)
        a = self.command(ego, [self.car(1, 655.0, 1)], mode="noa")
        self.assertAlmostEqual(a.speed, 28.8)

    def test_ongoing_front_transfer_does_not_choose_a_second_helper(self):
        ego = self.car(0, 668.3, 1, 27.03)
        others = [
            self.car(1, 715.2, 1),
            self.car(2, 685.2, 2),
            self.car(3, 701.3, 1, 28.72),
            self.car(4, 710.9, 0, 27.37),
            self.car(5, 682.4, 0, 27.34),
        ]
        others[0] = replace(others[0], y=6.6, vy=-3.3)
        self.assertIsNone(self.command(ego, others).lane)

    def test_retained_lane_head_does_not_follow_an_ending_car_behind(self):
        ego = self.car(0, 700.0, 1)
        a = self.command(ego, [self.car(1, 670.0, 2)])
        self.assertAlmostEqual(a.speed, 28.8)

    def test_closing_a_stopped_car_has_the_same_response_limit_in_all_modes(self):
        ego = self.car(0, 100.0, 2, 20.0)
        front = self.car(1, 130.0, 2, 0.0)
        for mode in ("noa", "formation", "transform"):
            self.assertLessEqual(self.command(ego, [front], mode=mode, drop=None).speed, 20.3)

    def test_rejected_lane_request_keeps_adjusting_the_physical_gap(self):
        ego = self.car(0, 700.0, 2)
        others = (self.car(1, 690.0, 1), self.car(2, 705.0, 1), self.car(3, 730.0, 1))
        action, _ = self.r.decide(ego, others, self.r.Memory(lane_target=1), "noa", 1000.0)
        self.assertNotEqual(action.reason, "executing")
        self.assertIsNotNone(action.target_x)

    def test_closing_limit_protects_both_physically_occupied_lanes(self):
        ego = replace(self.car(0, 100.0, 1, 20.0), y=6.5, vy=2.0)
        self.assertLessEqual(self.r.safe_speed(ego, [self.car(1, 130.0, 2, 0.0)]), 20.3)

    def test_mandatory_merge_continues_until_actual_lane_exit(self):
        ego = self.car(0, 1000.0, 2, 0.0)
        self.assertEqual(self.command(ego, mode="noa").lane, 1)

    def test_upstream_fill_does_not_send_a_less_populated_lane_to_a_crowded_one(self):
        ego = self.car(0, 280.0, 1)
        others = [
            self.car(1, 315.0, 2),
            self.car(2, 265.0, 2),
            self.car(3, 215.0, 2),
            self.car(4, 270.0, 1),
            self.car(5, 315.0, 0),
        ]
        self.assertNotEqual(self.command(ego, others, mode="formation", drop=None).lane, 2)

    def test_nonadjacent_lane_head_does_not_pull_the_local_head_phase(self):
        ego = self.car(0, 100.0, 0)
        others = (self.car(7, 85.0, 1), self.car(9, 140.0, 2))
        a = self.command(ego, others, mode="formation", drop=None)
        adjacent_only = self.command(ego, others[:1], mode="formation", drop=None)
        self.assertEqual((a.speed, a.target_x), (adjacent_only.speed, adjacent_only.target_x))
        self.assertAlmostEqual(a.target_x, ego.x)
        self.assertAlmostEqual(a.speed, self.r.CRUISE)

    def test_two_lane_reforming_can_still_observe_an_unmerged_car_behind(self):
        ego = self.car(0, 1005.0, 0)
        others = (self.car(1, 1000.0, 2), self.car(2, 970.0, 0))
        command = self.command(ego, others)
        self.assertNotEqual(command.lane, 2)

    def test_aligned_group_can_follow_a_temporary_slow_reference(self):
        ego = self.car(0, 100.0, 2, 26.8)
        distance = 5.5 + (30.0 - 5.5) / 28.8 * ego.speed
        command = self.command(ego, [self.car(1, ego.x + distance, 2, 26.8)], drop=None)
        self.assertAlmostEqual(command.speed, 26.8)

    def test_visible_front_sequence_follows_the_nearest_physical_front(self):
        ego = self.car(0, 100.0, 2)
        command = self.command(ego, [self.car(1, 150.0, 2), self.car(2, 200.0, 2)], drop=None)
        self.assertAlmostEqual(command.target_x, 120.0)

    def test_a_complete_local_unit_does_not_race_a_distant_unit(self):
        cars = self.six()
        remote = self.car(99, 900.0, 2)
        self.assertAlmostEqual(self.command(cars[0], [*cars[1:], remote], drop=None).speed, 28.8)

    def test_unit_head_does_not_build_a_formation_chain_to_a_visible_distant_front(self):
        ego = self.car(0, 100.0, 2)
        rear, far = self.car(1, 70.0, 2), self.car(2, 230.0, 2)
        actual = self.r._following(ego, [rear, far], 3)
        self.assertEqual(actual, self.r._following(ego, [rear], 3))
        self.assertEqual(actual, (self.r.CRUISE, ego.x, None, 1))

    def test_a_head_keeps_cruise_without_a_cross_lane_position_error(self):
        ego = self.car(0, 100.0, 2)
        command = self.command(ego, [self.car(1, 20.0, 2)], drop=None)
        self.assertAlmostEqual(command.speed, 28.8)

    def test_a_rear_upper_lane_car_does_not_command_the_flow_head_to_stop(self):
        ego = self.car(0, 800.0, 0)
        command = self.command(ego, [self.car(1, 750.0, 1), self.car(2, 700.0, 2)], drop=None)
        self.assertGreaterEqual(command.speed, 26.8)
        self.assertLessEqual(command.speed, 30.8)

    def test_retained_lanes_restore_their_missing_cell_before_the_drop(self):
        ego = self.car(0, 755.0, 1)
        others = [
            self.car(i + 1, x, lane)
            for i, (x, lane) in enumerate(
                ((800.0, 1), (770.0, 1), (740.0, 1), (785.0, 0), (725.0, 0))
            )
        ]
        command = self.command(ego, others)
        self.assertEqual(command.lane, 0)
        command = self.command(
            replace(ego, x=ego.x + 300.0), [replace(c, x=c.x + 300.0) for c in others]
        )
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reason, "fill_layer")

    def test_following_a_braking_front_keeps_the_physical_stopping_distance(self):
        # 300s连续流168.9s追尾前的真实状态，两车均按10m/s²制动。
        ego = self.car(0, 609.2450418788159, 2, 31.46471611790964)
        front = self.car(1, 649.1962456625621, 2, 24.287615828852104)
        for _ in range(40):
            requested = self.r.safe_speed(ego, [front])
            ego = replace(ego, speed=max(ego.speed - 1.0, min(ego.speed + 0.5, requested)))
            front = replace(front, speed=max(0.0, front.speed - 1.0))
            ego = replace(ego, x=ego.x + 0.1 * ego.speed)
            front = replace(front, x=front.x + 0.1 * front.speed)
            self.assertGreaterEqual(front.x - ego.x, 5.5)

    def test_an_ending_lane_follower_does_not_get_a_virtual_merged_rank_at_640(self):
        ego = self.car(0, 639.0, 2)
        others = [
            self.car(i + 1, x, lane)
            for i, (x, lane) in enumerate(
                (
                    (680.0, 2),
                    (710.0, 2),
                    (639.0, 1),
                    (700.0, 1),
                    (730.0, 1),
                    (760.0, 1),
                    (730.0, 0),
                    (760.0, 0),
                )
            )
        ]
        before = self.command(ego, others)
        after = self.command(replace(ego, x=641.0), [replace(c, x=c.x + 2.0) for c in others])
        self.assertAlmostEqual(after.target_x, before.target_x + 2.0)

    def test_selected_local_cell_survives_lateral_motion_and_completion(self):
        ego = self.car(0, 285.0, 0)
        rows = [
            self.car(i + 1, x, lane)
            for i, (x, lane) in enumerate(
                ((300.0, 2), (270.0, 2), (255.0, 1), (300.0, 0), (270.0, 0))
            )
        ]
        command, memory = self.r.decide(ego, rows, self.r.Memory(), "transform", None)
        self.assertEqual(command.lane, 1)
        target = command.target_x
        ego = replace(ego, x=287.88, y=1.98, vy=3.3)
        rows = [replace(c, x=c.x + 2.88) for c in rows]
        command, memory = self.r.decide(ego, rows, memory, "transform", None)
        self.assertAlmostEqual(command.target_x, target + 2.88)
        ego = replace(ego, lane=1, y=4.95, vy=0.0)
        command, _ = self.r.decide(ego, rows, memory, "transform")
        self.assertIsNone(command.lane)
        self.assertAlmostEqual(command.target_x, target + 2.88)

    def test_a_free_merging_head_keeps_cruise_while_its_rear_car_slows(self):
        ego = self.car(0, 700.0, 2)
        rows = [self.car(1, 655.0, 1, 20.0)]
        _, memory = self.r.decide(ego, rows, self.r.Memory(), "transform")
        moving = replace(ego, y=7.9, vy=-3.3)
        command, _ = self.r.decide(moving, rows, memory, "transform")
        self.assertAlmostEqual(command.speed, 28.8)

    def test_a_helper_tracks_the_gap_while_the_rear_opens_space(self):
        cars = self.six()
        ego = replace(cars[2], track=0)
        rows = [
            replace(c, track=i + 1) for i, c in enumerate(c for j, c in enumerate(cars) if j != 2)
        ]
        _, memory = self.r.decide(ego, rows, self.r.Memory(), "transform")
        moved = [
            replace(c, x=650.0, speed=20.0) if c.lane == 0 and c.x == 670.0 else c for c in rows
        ]
        command, _ = self.r.decide(replace(ego, y=4.6, vy=-3.3), moved, memory, "transform")
        self.assertAlmostEqual(command.target_x, 675.0)

    def test_a_new_lane_head_uses_the_exact_lane_phase(self):
        ego = self.car(0, 285.0, 0)
        rows = [
            self.car(i + 1, x, lane)
            for i, (x, lane) in enumerate(
                ((300.0, 2), (270.0, 2), (255.0, 1), (300.0, 0), (270.0, 0))
            )
        ]
        command, memory = self.r.decide(ego, rows, self.r.Memory(), "transform", None)
        self.assertAlmostEqual(command.target_x, 285.0)
        self.assertTrue(memory.joining)

    def test_a_free_head_does_not_chase_its_own_positive_offset(self):
        ego = self.car(0, 700.0, 2)
        _, memory = self.r.decide(ego, [self.car(1, 691.0, 1)], self.r.Memory(), "transform")
        ego = replace(ego, x=730.0, lane=1, y=4.95)
        command, _ = self.r.decide(ego, [self.car(1, 706.0, 1, 20.0)], memory, "transform")
        self.assertAlmostEqual(command.speed, 28.8)

    def test_a_front_that_left_its_lane_does_not_keep_an_old_speed_reference(self):
        ego = self.car(0, 100.0, 0)
        rows = [self.car(1, 140.0, 1, 10.0)]
        memory = self.r.Memory(gap=(1, None))
        command, memory = self.r.decide(ego, rows, memory, "transform", None)
        fresh = self.command(ego, rows, drop=None)
        self.assertEqual(command, fresh)
        self.assertIsNone(command.reference)

    def test_a_retained_head_adopts_the_two_lane_phase(self):
        ego = self.car(0, 700.0, 0)
        reference = self.car(1, 700.0, 1)
        memory = self.r.Memory()
        command, _ = self.r.decide(ego, [reference], memory, "transform")
        self.assertEqual((self.r._phase(0, 2), self.r._phase(1, 2)), (15.0, 0.0))
        self.assertLess(command.target_x, ego.x)
        self.assertLess(command.speed, self.r.CRUISE)
        self.assertLessEqual(abs(self.r.POSITION_GAIN * (command.target_x - ego.x)), 2.0 + 1e-9)
        self.assertAlmostEqual(command.speed, self.r._request(ego, command.target_x, self.r.CRUISE))

    def test_an_unstarted_fill_does_not_enter_the_ending_lane_after_640(self):
        ego = self.car(0, 639.0, 1)
        rows = [
            self.car(i + 1, x, lane)
            for i, (x, lane) in enumerate(
                ((654.0, 2), (654.0, 1), (624.0, 1), (609.0, 0), (594.0, 0))
            )
        ]
        command, memory = self.r.decide(ego, rows, self.r.Memory(), "transform")
        self.assertEqual(command.lane, 2)
        command, _ = self.r.decide(
            replace(ego, x=642.0), [replace(c, x=c.x + 3.0) for c in rows], memory, "transform"
        )
        self.assertNotEqual(command.lane, 2)

    def test_opposite_sides_do_not_both_fill_the_same_physical_corridor(self):
        cars = [
            self.car(i, x, lane)
            for i, (x, lane) in enumerate(
                (
                    (0.0, 0),
                    (2.0, 2),
                    (-90.0, 0),
                    (-30.0, 2),
                    (-75.0, 1),
                    (30.0, 0),
                    (-60.0, 2),
                    (-15.0, 0),
                )
            )
        ]
        commands = []
        for car in cars[:2]:
            rows = [
                replace(c, track=i + 1)
                for i, c in enumerate(c for c in cars if c.track != car.track)
            ]
            commands.append(self.command(replace(car, track=0), rows, mode="formation", drop=None))
        self.assertLessEqual(sum(c.lane == 1 for c in commands), 1)

    def test_physical_phase_interpolates_continuously_independent_of_lane_index(self):
        phases = []
        for i in range(11):
            y = 8.25 - i * 0.33
            a = replace(self.car(1, 100.0, 2), y=y, vy=-3.3)
            b = replace(a, lane=1)
            phases.append(self.r._physical_phase(a, 3))
            self.assertAlmostEqual(phases[-1], self.r._physical_phase(b, 3))
            self.assertAlmostEqual(phases[-1], i * 1.5)
        self.assertAlmostEqual(phases[0], 0.0)
        self.assertAlmostEqual(phases[-1], 15.0)
        self.assertLess(max(abs(b-a) for a,b in zip(phases, phases[1:])), 2.0)

    def test_crossing_reference_keeps_position_and_damped_speed_corrections_bounded(self):
        ego = self.car(0, 100.0, 0)
        memory = self.r.Memory()
        targets = []
        for i in range(11):
            y = 8.25 - i * 0.33
            reference = replace(self.car(1, 100.0, 2 if y >= 6.6 else 1), y=y, vy=-3.3)
            command, _ = self.r.decide(ego, [reference], memory, "transform", None)
            targets.append(command.target_x)
            self.assertLessEqual(abs(self.r.POSITION_GAIN * (command.target_x-ego.x)), 2.0 + 1e-9)
            self.assertLessEqual(abs(command.speed-self.r.CRUISE), self.r.SPEED_RELAXATION * 2.0 + 1e-9)
            self.assertAlmostEqual(command.speed, self.r._request(ego, command.target_x, self.r.CRUISE))
        self.assertAlmostEqual(targets[0], 100.0)
        self.assertGreater(targets[-1], ego.x)

    def test_a_free_head_rejoins_cross_lane_alignment_after_lateral_completion(self):
        ego = self.car(0, 700.0, 1)
        rows = [self.car(1, 700.0, 0), self.car(2, 655.0, 1)]
        memory = self.r.Memory(lane_target=1, gap=(None, 2), joining=True)
        command, memory = self.r.decide(ego, rows, memory, "transform")
        self.assertGreater(command.speed, 28.8)
        self.assertGreater(command.target_x, ego.x)
        self.assertLessEqual(abs(self.r.POSITION_GAIN * (command.target_x-ego.x)), 2.0 + 1e-9)
        self.assertAlmostEqual(command.speed, self.r._request(ego, command.target_x, self.r.CRUISE))
        self.assertIsNone(memory.lane_target)
        self.assertIsNone(memory.gap)
        self.assertTrue(memory.joining)


if __name__ == "__main__":
    unittest.main()
