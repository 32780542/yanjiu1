"""Contract tests for the deliberately small local if/else formation rules."""
from dataclasses import FrozenInstanceError, asdict
import math
import unittest

from noa.contracts import NoaMemory
from noa.simple_formation import (
    PARAMETERS,
    LaneDecision,
    JoinDecision,
    LocalVehicle,
    SimpleFormationMemory,
    choose_lane,
    choose_join,
    choose_reference,
    connected_tail_neighborhood,
    desired_gap_m,
    longitudinal_increment,
    infer_tail_join,
    is_next_waiting_vehicle,
    lane_counts,
    memory_from_dict,
    validate_parameters,
)
from simulation.phase5g_clock import restore_initial_memories


class SimpleFormationRuleTests(unittest.TestCase):
    def setUp(self):
        self.p = {
            "simple_formation_component_gap_m": 50.0,
            "simple_formation_middle_offset_m": 15.0,
            "simple_formation_same_lane_gap_m": 30.0,
            "simple_formation_position_tolerance_m": 2.0,
            "simple_formation_speed_tolerance_mps": 0.5,
            "simple_formation_stable_time_s": 1.0,
            "simple_formation_reference_switch_gain_m": 5.0,
            "simple_formation_min_lane_change_speed_mps": 5.0,
            "simple_formation_target_lane_clearance_m": 15.0,
            # Temporary compatibility values for the unmodified old rule tests below.
            "simple_formation_local_range_m": 90.0,
            "simple_formation_adjacent_gap_m": 15.0,
            "simple_formation_same_gap_m": 30.0,
            "simple_formation_accel_limit_mps2": 0.5,
            "simple_formation_max_lane_changes": 1,
        }
        self.centers = (1.65, 4.95, 8.25)

    @staticmethod
    def vehicle(track, x, lane, speed=20.0, y=0.0):
        return LocalVehicle(track, x, y, speed, lane)

    def test_public_parameter_names_are_exactly_the_local_tail_contract(self):
        self.assertEqual(
            PARAMETERS,
            (
                "simple_formation_component_gap_m",
                "simple_formation_middle_offset_m",
                "simple_formation_same_lane_gap_m",
                "simple_formation_position_tolerance_m",
                "simple_formation_speed_tolerance_mps",
                "simple_formation_stable_time_s",
                "simple_formation_reference_switch_gain_m",
                "simple_formation_min_lane_change_speed_mps",
                "simple_formation_target_lane_clearance_m",
            ),
        )

    def test_parameters_accept_only_complete_positive_finite_exact_numbers(self):
        validate_parameters(self.p)
        for key in PARAMETERS:
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_parameters({name: value for name, value in self.p.items() if name != key})
        for key in PARAMETERS:
            for bad in (
                True,
                False,
                0,
                -0.1,
                math.inf,
                -math.inf,
                math.nan,
                10**1000,
                "1",
            ):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    validate_parameters({**self.p, key: bad})

    def test_records_are_frozen_and_slotted(self):
        memory = SimpleFormationMemory((), "CRUISE")
        vehicle = self.vehicle(1, 10.0, 0)
        decision = LaneDecision(1, "simple_formation_balance", (2, 0, 0))
        for row, field in ((memory, "own_behavior"), (vehicle, "x_m"), (decision, "reason")):
            with self.subTest(type=type(row).__name__), self.assertRaises(FrozenInstanceError):
                setattr(row, field, None)
            self.assertFalse(hasattr(row, "__dict__"))

    def test_memory_restores_old_noa_dictionary_with_neutral_defaults(self):
        restored = memory_from_dict(asdict(NoaMemory((), "CRUISE")))
        self.assertIsInstance(restored, SimpleFormationMemory)
        self.assertIsNone(restored.reference_track_id)
        self.assertIsNone(restored.join_anchor_track_id)
        self.assertIsNone(restored.desired_lane_index)
        self.assertEqual(restored.join_phase, "FREE")
        self.assertIsNone(restored.stable_since_s)
        self.assertFalse(hasattr(restored, "formation_lane_change_done"))
        self.assertEqual(restored.own_behavior, "CRUISE")

    def test_memory_round_trip_preserves_base_and_private_simple_fields(self):
        original = SimpleFormationMemory(
            (),
            "PREPARE",
            reference_track_id=7,
            join_anchor_track_id=9,
            desired_lane_index=2,
            join_phase="STABILIZING",
            stable_since_s=3.0,
        )
        self.assertEqual(memory_from_dict(asdict(original)), original)

    def test_memory_rejects_invalid_private_local_tail_fields_and_unknown_schema(self):
        base = asdict(NoaMemory((), "CRUISE"))
        for key in ("reference_track_id", "join_anchor_track_id"):
            for bad in (-1, True, 1.0, "1"):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    memory_from_dict({**base, key: bad})
        for bad in (-1, 3, True, 1.0, "1"):
            with self.subTest(desired_lane=bad), self.assertRaises(ValueError):
                memory_from_dict({**base, "desired_lane_index": bad})
        for bad in (None, True, "joining", "UNKNOWN"):
            with self.subTest(phase=bad), self.assertRaises(ValueError):
                memory_from_dict({**base, "join_phase": bad})
        for bad in (-1, True, math.inf, -math.inf, math.nan, 10**1000, "1"):
            with self.subTest(stable_since=bad), self.assertRaises(ValueError):
                memory_from_dict({**base, "stable_since_s": bad})
        for key in ("formation_lane_change_done", "unexpected"):
            with self.subTest(extra=key), self.assertRaises(ValueError):
                memory_from_dict({**base, key: True})

    def test_clock_restores_new_simple_memory_and_accepts_join_reason(self):
        raw = asdict(NoaMemory((), "CRUISE", lane_change_reason="simple_formation_join"))
        restored = restore_initial_memories(
            {"ego": raw},
            ("ego",),
            formation_enabled=True,
            lane_priority_enabled=False,
            simple_enabled=True,
        )
        self.assertEqual(restored["ego"].join_phase, "FREE")
        self.assertEqual(restored["ego"].lane_change_reason, "simple_formation_join")

    def test_clock_restores_every_private_local_tail_memory_field(self):
        original = SimpleFormationMemory(
            (),
            "CRUISE",
            reference_track_id=7,
            join_anchor_track_id=9,
            desired_lane_index=2,
            join_phase="STABILIZING",
            stable_since_s=3.0,
        )
        restored = restore_initial_memories(
            {"ego": asdict(original)},
            ("ego",),
            formation_enabled=True,
            lane_priority_enabled=False,
            simple_enabled=True,
        )
        self.assertIs(type(restored["ego"]), SimpleFormationMemory)
        self.assertEqual(restored["ego"], original)

    def test_reference_is_none_without_a_visible_lane_resolved_front_vehicle(self):
        rows = (
            self.vehicle(1, -1.0, 0),
            self.vehicle(2, 50.0, None),
            self.vehicle(3, 2.0, 1),
        )
        self.assertIsNone(choose_reference(0.0, rows, None, 2.0))

    def test_visible_remembered_front_reference_is_held_over_a_nearer_vehicle(self):
        rows = (self.vehicle(41, 40.0, 0), self.vehicle(9, 10.0, 1))
        self.assertEqual(choose_reference(0.0, rows, 41, 2.0), rows[0])

    def test_reference_forgets_a_remembered_vehicle_that_moved_behind(self):
        rows = (self.vehicle(41, -5.0, 0), self.vehicle(9, 10.0, 1))
        self.assertEqual(choose_reference(0.0, rows, 41, 2.0), rows[1])

    def test_unique_nearest_front_vehicle_is_selected_without_track_priority(self):
        farther_low_track = self.vehicle(1, 40.0, 0)
        nearer_high_track = self.vehicle(99, 10.0, 2)
        self.assertEqual(
            choose_reference(0.0, (farther_low_track, nearer_high_track), None, 2.0),
            nearer_high_track,
        )

    def test_nearest_front_tie_within_tolerance_is_ambiguous(self):
        rows = (self.vehicle(1, 10.0, 0), self.vehicle(2, 11.9, 2))
        self.assertIsNone(choose_reference(0.0, rows, None, 2.0))
        self.assertEqual(choose_reference(0.0, rows, None, 1.0), rows[0])

    def test_desired_gap_uses_adjacent_geometry_only(self):
        self.assertEqual(desired_gap_m(1, 0, self.p), 15.0)
        self.assertEqual(desired_gap_m(1, 2, self.p), 15.0)
        self.assertEqual(desired_gap_m(1, 1, self.p), 30.0)
        self.assertEqual(desired_gap_m(0, 2, self.p), 30.0)

    def test_longitudinal_rule_accelerates_or_brakes_outside_position_tolerance(self):
        ahead = self.vehicle(1, 33.0, 0, speed=20.0)
        behind = self.vehicle(2, 27.0, 0, speed=20.0)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, ahead, self.p), 0.5)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, behind, self.p), -0.5)

    def test_longitudinal_rule_tracks_clipped_reference_speed_inside_tolerance(self):
        fast = self.vehicle(1, 30.0, 0, speed=25.0)
        slow = self.vehicle(2, 30.0, 0, speed=15.0)
        close = self.vehicle(3, 30.0, 0, speed=20.25)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, fast, self.p), 0.5)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, slow, self.p), -0.5)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, close, self.p), 0.25)

    def test_longitudinal_threshold_is_strict_and_uses_adjacent_gap(self):
        at_upper = self.vehicle(1, 17.0, 1, speed=20.2)
        over_upper = self.vehicle(2, 17.01, 1, speed=10.0)
        at_lower = self.vehicle(3, 28.0, 0, speed=20.3)
        below_lower = self.vehicle(4, 27.99, 0, speed=20.3)
        self.assertAlmostEqual(longitudinal_increment(0.0, 20.0, 0, at_upper, self.p), 0.2)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, over_upper, self.p), 0.5)
        self.assertAlmostEqual(longitudinal_increment(0.0, 20.0, 0, at_lower, self.p), 0.3)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, below_lower, self.p), -0.5)

    def test_lane_balance_moves_local_rear_vehicle_to_unique_less_populated_side(self):
        rows = (
            self.vehicle(1, 10.0, 1),
            self.vehicle(2, 20.0, 1),
            self.vehicle(3, 10.0, 0),
        )
        decision = choose_lane(0.0, 1, rows, self.centers, False, self.p)
        self.assertEqual(decision, LaneDecision(2, "simple_formation_balance", (1, 3, 0)))

    def test_lane_balance_stays_when_adjacent_minimum_is_tied(self):
        rows = (self.vehicle(1, 10.0, 1), self.vehicle(2, 20.0, 1))
        decision = choose_lane(0.0, 1, rows, self.centers, False, self.p)
        self.assertIsNone(decision.target_lane_index)
        self.assertEqual(decision.reason, "adjacent_lane_tie")
        self.assertEqual(decision.counts, (0, 3, 0))

    def test_lane_balance_reports_no_candidate_when_neither_adjacent_lane_is_strictly_less(self):
        rows = (self.vehicle(1, 10.0, 0), self.vehicle(2, 10.0, 2))
        decision = choose_lane(0.0, 1, rows, self.centers, False, self.p)
        self.assertIsNone(decision.target_lane_index)
        self.assertEqual(decision.reason, "no_less_populated_adjacent_lane")
        self.assertEqual(decision.counts, (1, 1, 1))

    def test_lane_balance_requires_ego_to_be_local_rear_most(self):
        rows = (
            self.vehicle(1, -5.0, 1),
            self.vehicle(2, 10.0, 1),
            self.vehicle(3, 10.0, 0),
        )
        decision = choose_lane(0.0, 1, rows, self.centers, False, self.p)
        self.assertIsNone(decision.target_lane_index)
        self.assertEqual(decision.reason, "not_local_rear_most")

    def test_lane_balance_stops_after_the_one_completed_formation_change(self):
        rows = (self.vehicle(1, 10.0, 0),)
        decision = choose_lane(0.0, 0, rows, self.centers, True, self.p)
        self.assertIsNone(decision.target_lane_index)

    def test_outer_lane_considers_only_its_existing_adjacent_lane(self):
        rows = (self.vehicle(1, 10.0, 0),)
        decision = choose_lane(0.0, 0, rows, self.centers, False, self.p)
        self.assertEqual(decision.target_lane_index, 1)
        self.assertEqual(decision.counts, (2, 0, 0))

    def test_unresolved_lane_is_not_counted(self):
        rows = (self.vehicle(1, 10.0, 0), self.vehicle(2, 1.0, None))
        decision = choose_lane(0.0, 0, rows, self.centers, False, self.p)
        self.assertEqual(decision.target_lane_index, 1)
        self.assertEqual(decision.counts, (2, 0, 0))

    def test_vehicles_outside_symmetric_local_range_do_not_change_decision(self):
        current = (self.vehicle(1, 10.0, 0),)
        baseline = choose_lane(0.0, 0, current, self.centers, False, self.p)
        outside = current + (
            self.vehicle(2, 90.01, 1),
            self.vehicle(3, -90.01, 1),
        )
        self.assertEqual(choose_lane(0.0, 0, outside, self.centers, False, self.p), baseline)

    def test_moving_the_same_vehicles_inside_local_range_changes_only_local_counts(self):
        current = (self.vehicle(1, 10.0, 0),)
        outside = current + (self.vehicle(2, 90.01, 1), self.vehicle(3, -90.01, 1))
        inside = current + (self.vehicle(2, 89.99, 1), self.vehicle(3, -89.99, 1))
        self.assertEqual(
            choose_lane(0.0, 0, outside, self.centers, False, self.p).target_lane_index,
            1,
        )
        decision = choose_lane(0.0, 0, inside, self.centers, False, self.p)
        self.assertIsNone(decision.target_lane_index)
        self.assertEqual(decision.counts, (2, 2, 0))

    def test_component_joins_at_exactly_fifty_and_splits_above(self):
        ego = self.vehicle(99, 0.0, 1)
        connected = (self.vehicle(1, 50.0, 1), self.vehicle(2, 100.0, 2))
        self.assertEqual(connected_tail_neighborhood(ego, connected, self.centers, self.p), connected)
        split = (self.vehicle(1, 50.01, 1), self.vehicle(2, 100.0, 2))
        self.assertEqual(connected_tail_neighborhood(ego, split, self.centers, self.p), ())

    def test_component_excludes_rows_past_a_gap_and_unresolved_lanes(self):
        ego = self.vehicle(99, 0.0, 1)
        local = (self.vehicle(1, 20.0, 1),)
        extended = local + (self.vehicle(2, 71.0, 2), self.vehicle(3, 80.0, None))
        self.assertEqual(connected_tail_neighborhood(ego, extended, self.centers, self.p), local)
        self.assertEqual(choose_join(ego, extended, self.centers, self.p),
                         choose_join(ego, local, self.centers, self.p))

    def test_tail_patterns_choose_upper_lower_then_middle(self):
        ego = self.vehicle(99, 0.0, 1)
        middle = self.vehicle(1, 45.0, 1)
        upper = self.vehicle(2, 30.0, 2)
        lower = self.vehicle(3, 30.0, 0)
        for rows, lane, x, anchor, reason in (
            ((middle,), 2, 30.0, 1, "middle_tail"),
            ((middle, upper), 0, 30.0, 2, "upper_tail"),
            ((middle, upper, lower), 1, 15.0, 2, "outer_tail"),
        ):
            with self.subTest(rows=rows):
                result = infer_tail_join(ego, rows, self.centers, self.p)
                self.assertEqual((result.target_lane_index, result.target_x_m,
                                  result.anchor_track_id, result.reason), (lane, x, anchor, reason))

    def test_outer_pair_within_position_tolerance_is_one_physical_layer(self):
        ego = self.vehicle(99, 0.0, 1)
        rows = (self.vehicle(1, 45.0, 1), self.vehicle(2, 30.0, 2),
                self.vehicle(3, 31.0, 0))
        result = choose_join(ego, rows, self.centers, self.p)
        self.assertEqual((result.target_lane_index, result.target_x_m,
                          result.anchor_track_id, result.reason),
                         (1, 15.0, 2, "outer_tail"))

    def test_counts_recover_malformed_tail_in_physical_lane_order(self):
        ego = self.vehicle(99, 0.0, 1)
        cases = (
            ((), (0, 0, 0), 2),
            ((self.vehicle(1, 35.0, 2),), (0, 0, 1), 0),
            ((self.vehicle(1, 45.0, 0), self.vehicle(2, 30.0, 2)), (1, 0, 1), 1),
            ((self.vehicle(1, 60.0, 1), self.vehicle(2, 45.0, 0),
              self.vehicle(3, 30.0, 2)), (1, 1, 1), 2),
        )
        for rows, counts, target in cases:
            with self.subTest(counts=counts):
                self.assertEqual(lane_counts(rows, self.centers), counts)
                result = infer_tail_join(ego, rows, self.centers, self.p)
                self.assertEqual(result.local_counts, counts)
                self.assertEqual(result.target_lane_index, target)

    def test_unresolved_lane_is_neither_counted_nor_tail_pattern(self):
        ego = self.vehicle(99, 0.0, 1)
        rows = (self.vehicle(1, 45.0, None), self.vehicle(2, 30.0, 2))
        self.assertEqual(lane_counts(rows, self.centers), (0, 0, 1))
        self.assertEqual(infer_tail_join(ego, rows, self.centers, self.p).reason, "upper_tail")

    def test_only_closest_waiter_behind_stable_tail_is_admitted(self):
        tail = (self.vehicle(1, 45.0, 1),)
        near = self.vehicle(20, 20.0, 0)
        far = self.vehicle(21, 10.0, 1)
        self.assertTrue(is_next_waiting_vehicle(near, tail + (far,), self.centers, self.p))
        self.assertFalse(is_next_waiting_vehicle(far, tail + (near,), self.centers, self.p))
        self.assertIsNone(choose_join(far, tail + (near,), self.centers, self.p).target_lane_index)

    def test_equal_x_waiters_use_upper_lane_then_wait_on_unresolved_priority(self):
        tail = (self.vehicle(1, 45.0, 1),)
        upper = self.vehicle(20, 20.0, 2)
        lower = self.vehicle(21, 21.0, 0)
        self.assertTrue(is_next_waiting_vehicle(upper, tail + (lower,), self.centers, self.p))
        self.assertFalse(is_next_waiting_vehicle(lower, tail + (upper,), self.centers, self.p))
        unresolved = self.vehicle(22, 20.0, None)
        self.assertFalse(is_next_waiting_vehicle(upper, tail + (unresolved,), self.centers, self.p))

    def test_relabel_and_neighbor_order_leave_physical_decision_unchanged(self):
        ego = self.vehicle(99, 0.0, 1)
        a = self.vehicle(1, 45.0, 1)
        b = self.vehicle(2, 30.0, 2)
        first = choose_join(ego, (a, b), self.centers, self.p)
        second = choose_join(ego, (self.vehicle(200, 30.0, 2),
                                   self.vehicle(100, 45.0, 1)), self.centers, self.p)
        self.assertEqual((first.target_lane_index, first.target_x_m, first.reason, first.local_counts),
                         (second.target_lane_index, second.target_x_m, second.reason, second.local_counts))
        self.assertEqual((first.anchor_track_id, second.anchor_track_id), (2, 200))

    def test_duplicate_physical_tail_anchor_waits_independent_of_input_order(self):
        ego = self.vehicle(99, 0.0, 1)
        rows = (self.vehicle(1, 30.0, 2), self.vehicle(2, 30.0, 2))
        for ordering in (rows, tuple(reversed(rows))):
            decision = choose_join(ego, ordering, self.centers, self.p)
            self.assertIsNone(decision.target_lane_index)
            self.assertIsNone(decision.anchor_track_id)
            self.assertEqual(decision.reason, "wait_ambiguous_tail")

    def test_join_decision_is_frozen_and_slotted(self):
        decision = JoinDecision(None, None, None, "wait", (0, 0, 0))
        with self.assertRaises(FrozenInstanceError):
            decision.reason = "other"
        self.assertFalse(hasattr(decision, "__dict__"))


if __name__ == "__main__":
    unittest.main()
