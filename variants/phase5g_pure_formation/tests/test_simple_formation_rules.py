"""Contract tests for the deliberately small local if/else formation rules."""
from dataclasses import FrozenInstanceError, asdict
import math
import unittest

from noa.contracts import NoaMemory
from noa.simple_formation import (
    PARAMETERS,
    LaneDecision,
    LocalVehicle,
    SimpleFormationMemory,
    choose_lane,
    choose_reference,
    desired_gap_m,
    longitudinal_increment,
    memory_from_dict,
    validate_parameters,
)


class SimpleFormationRuleTests(unittest.TestCase):
    def setUp(self):
        self.p = {
            "simple_formation_local_range_m": 90.0,
            "simple_formation_adjacent_gap_m": 15.0,
            "simple_formation_same_gap_m": 30.0,
            "simple_formation_position_tolerance_m": 2.0,
            "simple_formation_accel_limit_mps2": 0.5,
            "simple_formation_max_lane_changes": 1,
        }
        self.centers = (1.65, 4.95, 8.25)

    @staticmethod
    def vehicle(track, x, lane, speed=20.0, y=0.0):
        return LocalVehicle(track, x, y, speed, lane)

    def test_public_parameter_names_are_exactly_the_six_simple_rules(self):
        self.assertEqual(
            PARAMETERS,
            (
                "simple_formation_local_range_m",
                "simple_formation_adjacent_gap_m",
                "simple_formation_same_gap_m",
                "simple_formation_position_tolerance_m",
                "simple_formation_accel_limit_mps2",
                "simple_formation_max_lane_changes",
            ),
        )

    def test_parameters_accept_only_complete_positive_finite_numbers_and_one_change(self):
        validate_parameters(self.p)
        for key in PARAMETERS:
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_parameters({name: value for name, value in self.p.items() if name != key})
        numeric = PARAMETERS[:-1]
        for key in numeric:
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
        for bad in (True, False, 0, 2, 1.0, math.nan, "1"):
            with self.subTest(max_changes=bad), self.assertRaises(ValueError):
                validate_parameters({**self.p, "simple_formation_max_lane_changes": bad})

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
        self.assertFalse(restored.formation_lane_change_done)
        self.assertEqual(restored.own_behavior, "CRUISE")

    def test_memory_round_trip_preserves_base_and_private_simple_fields(self):
        original = SimpleFormationMemory(
            (), "PREPARE", reference_track_id=7, formation_lane_change_done=True
        )
        self.assertEqual(memory_from_dict(asdict(original)), original)

    def test_memory_rejects_nonlocal_reference_schema_and_nonboolean_done(self):
        base = asdict(NoaMemory((), "CRUISE"))
        for bad in (-1, True, 1.0, "1"):
            with self.subTest(reference=bad), self.assertRaises(ValueError):
                memory_from_dict({**base, "reference_track_id": bad})
        for bad in (0, 1, None, "false"):
            with self.subTest(done=bad), self.assertRaises(ValueError):
                memory_from_dict({**base, "formation_lane_change_done": bad})

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
        self.assertAlmostEqual(longitudinal_increment(0.0, 20.0, 0, at_upper, self.p), 0.2)
        self.assertEqual(longitudinal_increment(0.0, 20.0, 0, over_upper, self.p), 0.5)

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
        self.assertEqual(decision.counts, (0, 3, 0))

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


if __name__ == "__main__":
    unittest.main()
