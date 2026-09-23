"""Physical, local contracts for layered formation following and filling."""

from dataclasses import replace
import unittest

from noa.simple_formation import (
    LocalVehicle,
    SimpleFormationMemory,
    choose_formation_target,
    choose_layered_fill,
    layered_window,
)


CENTERS = (1.65, 4.95, 8.25)
P = {
    "simple_formation_component_gap_m": 50.0,
    "simple_formation_middle_offset_m": 15.0,
    "simple_formation_same_lane_gap_m": 30.0,
    "simple_formation_position_tolerance_m": 2.0,
    "simple_formation_speed_tolerance_mps": 1.0,
    "simple_formation_stable_time_s": 1.0,
    "simple_formation_reference_switch_gain_m": 2.0,
    "simple_formation_min_lane_change_speed_mps": 5.0,
    "simple_formation_target_lane_clearance_m": 8.0,
    "noa_target_speed_mps": 10.0,
    "noa_completion_lateral_error_m": 0.15,
}


def car(track, x, lane, speed=10.0):
    return LocalVehicle(track, x, CENTERS[lane], speed, lane)


class LayeredFormationTests(unittest.TestCase):
    def test_followers_use_same_lane_front_and_heads_use_outer_reference(self):
        memory = SimpleFormationMemory((), "CRUISE")
        lower = choose_formation_target(
            car(9, 100, 0), (car(1, 130, 0), car(2, 145, 2)),
            CENTERS, memory, P,
        )
        self.assertEqual((lower.role, lower.target_x_m, lower.reference_track_id),
                         ("same_lane_follower", 100, 1))
        middle_head = choose_formation_target(
            car(9, 100, 1), (car(2, 115, 0),), CENTERS, memory, P,
        )
        self.assertEqual((middle_head.role, middle_head.target_x_m),
                         ("middle_offset", 100))

    def test_same_lane_following_replaces_a_farther_remembered_reference(self):
        target = choose_formation_target(
            car(9, 100, 0), (car(1, 120, 0), car(2, 125, 0)),
            CENTERS, SimpleFormationMemory(
                (), "CRUISE", reference_track_id=2), P,
        )
        self.assertEqual(target.reference_track_id, 1)

    def test_window_is_four_layers_and_90_metres_only(self):
        ego = car(99, 100, 2)
        rows = (car(1, 160, 2), car(2, 130, 2), car(3, 100, 0),
                car(4, 85, 1), car(5, 70, 2), car(6, 191, 2))
        window = layered_window(ego, rows, CENTERS, P)
        self.assertTrue(window.consistent)
        self.assertEqual(tuple(row.track_id if row else None
                               for row in window.layers[2]), (3, 4, 99))
        self.assertEqual(tuple(row.track_id if row else None
                               for row in window.layers[0]), (None, None, 1))
        self.assertNotIn(6, tuple(row.track_id for layer in window.layers
                                  for row in layer if row))

    def test_window_reads_other_lanes_across_a_60_metre_gap(self):
        window = layered_window(
            car(99, 100, 2), (car(1, 160, 0),), CENTERS, P)
        self.assertEqual(window.layers[0][0].track_id, 1)

    def test_one_car_rules_fill_outer_lanes_in_physical_order(self):
        cases = (
            (2, 100, 130, 0, 130),
            (0, 100, 130, 2, 130),
            (1, 100, 130, 2, 145),
        )
        for lane, x, front_x, target_lane, target_x in cases:
            with self.subTest(lane=lane):
                ego = car(99, x, lane)
                decision = choose_layered_fill(
                    ego, (car(1, front_x, lane),), CENTERS, P,
                )
                self.assertEqual((decision.target_lane_index,
                                  decision.target_x_m),
                                 (target_lane, target_x))

    def test_two_car_rules_choose_exactly_one_actor(self):
        cases = (
            ((2, 0), (2, 0), 1),
            ((2, 1), (2, 1), 0),
            ((0, 1), (0, 1), 2),
        )
        for current_lanes, front_lanes, missing in cases:
            with self.subTest(current=current_lanes):
                current = tuple(car(20 + lane, 85 if lane == 1 else 100, lane)
                                for lane in current_lanes)
                front = tuple(car(10 + lane, 115 if lane == 1 else 130, lane)
                              for lane in front_lanes)
                decisions = tuple(choose_layered_fill(
                    ego, front + tuple(row for row in current if row is not ego),
                    CENTERS, P,
                ) for ego in current)
                selected = tuple(row for row in decisions
                                 if row.target_lane_index is not None)
                self.assertEqual(len(selected), 1)
                self.assertEqual(selected[0].target_lane_index, missing)

    def test_full_previous_or_two_incomplete_previous_layers_wait(self):
        ego = car(99, 100, 2)
        full = (car(1, 130, 2), car(2, 130, 0), car(3, 115, 1))
        self.assertIsNone(choose_layered_fill(ego, full, CENTERS, P).target_lane_index)
        two_open = (car(1, 130, 2), car(2, 160, 2))
        self.assertIsNone(choose_layered_fill(ego, two_open, CENTERS, P).target_lane_index)
        second_layer_other_lane = (car(1, 130, 2), car(2, 160, 0))
        self.assertIsNone(choose_layered_fill(
            ego, second_layer_other_lane, CENTERS, P).target_lane_index)
        other_lane_predecessor = (car(1, 115, 1),)
        self.assertEqual(choose_layered_fill(
            ego, other_lane_predecessor, CENTERS, P).target_lane_index, 0)

    def test_crossing_or_speed_spread_blocks_and_labels_do_not_decide(self):
        ego = car(99, 100, 2)
        front = car(1, 130, 2)
        crossing = replace(car(2, 115, 1), lane_index=None)
        self.assertIsNone(choose_layered_fill(
            ego, (front, crossing), CENTERS, P).target_lane_index)
        moving = replace(front, vy_mps=0.1)
        self.assertIsNone(choose_layered_fill(
            ego, (moving,), CENTERS, P).target_lane_index)
        fast = replace(front, vx_mps=12.0)
        self.assertIsNone(choose_layered_fill(
            ego, (fast,), CENTERS, P).target_lane_index)
        first = choose_layered_fill(ego, (front,), CENTERS, P)
        relabeled = choose_layered_fill(
            replace(ego, track_id=999), (replace(front, track_id=777),),
            CENTERS, P,
        )
        self.assertEqual((first.target_lane_index, first.target_x_m),
                         (relabeled.target_lane_index, relabeled.target_x_m))


if __name__ == "__main__":
    unittest.main()
