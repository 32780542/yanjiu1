"""Contracts shared by local following and layered lane selection."""

from dataclasses import FrozenInstanceError, asdict
import math
import unittest

from noa.contracts import NoaMemory
from noa.simple_formation import (
    PARAMETERS,
    JoinDecision,
    LocalVehicle,
    SimpleFormationMemory,
    choose_formation_target,
    connected_tail_neighborhood,
    formation_acceleration,
    memory_from_dict,
    target_lane_clear,
    validate_parameters,
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


class SimpleFormationRuleTests(unittest.TestCase):
    def test_parameters_are_positive_finite_and_complete(self):
        self.assertEqual(len(PARAMETERS), 9)
        validate_parameters(P)
        for key in PARAMETERS:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    validate_parameters({name: value for name, value in P.items()
                                         if name != key})
                for bad in (True, 0, -1, math.inf, math.nan):
                    with self.assertRaises(ValueError):
                        validate_parameters({**P, key: bad})

    def test_private_memory_round_trip_and_neutral_old_checkpoint(self):
        original = SimpleFormationMemory(
            (), "CRUISE", reference_track_id=7, join_anchor_track_id=9,
            desired_lane_index=1, join_phase="JOINING", stable_since_s=0.5,
            stable_window_signature="((0, 2, 7),)",
        )
        self.assertEqual(memory_from_dict(asdict(original)), original)
        neutral = memory_from_dict(asdict(NoaMemory((), "CRUISE")))
        self.assertEqual(neutral, SimpleFormationMemory((), "CRUISE"))
        self.assertFalse(hasattr(neutral, "formation_lane_change_done"))

    def test_private_memory_rejects_invalid_or_obsolete_fields(self):
        base = asdict(NoaMemory((), "CRUISE"))
        for extra in (
            {"reference_track_id": True}, {"join_anchor_track_id": -1},
            {"desired_lane_index": 3}, {"join_phase": "UNKNOWN"},
            {"stable_since_s": math.nan},
            {"stable_window_signature": ""},
            {"formation_lane_change_done": True},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                memory_from_dict({**base, **extra})

    def test_records_are_immutable(self):
        for row, name in (
            (SimpleFormationMemory((), "CRUISE"), "join_phase"),
            (car(1, 10, 0), "x_m"),
            (JoinDecision(None, None, None, "wait", (0, 0, 0)), "reason"),
        ):
            with self.assertRaises(FrozenInstanceError):
                setattr(row, name, None)
            self.assertFalse(hasattr(row, "__dict__"))

    def test_50_m_boundary_is_physical_and_includes_crossing_vehicle(self):
        ego = car(9, 0, 0)
        crossing = LocalVehicle(1, 30, 3.4, 10, None)
        upper = car(2, 75, 2)
        self.assertEqual(connected_tail_neighborhood(
            ego, (crossing, upper), CENTERS, P), (crossing, upper))
        self.assertEqual(connected_tail_neighborhood(
            ego, (car(2, 50.01, 2),), CENTERS, P), ())

    def test_reference_switch_requires_two_metres_improvement(self):
        ego = car(9, 130, 0)
        memory = SimpleFormationMemory((), "CRUISE", reference_track_id=1)
        held = choose_formation_target(
            ego, (car(1, 120, 2), car(2, 121, 2)), CENTERS, memory, P)
        self.assertEqual(held.reference_track_id, 1)
        switched = choose_formation_target(
            ego, (car(1, 120, 2), car(2, 123, 2)), CENTERS, memory, P)
        self.assertEqual(switched.reference_track_id, 2)

    def test_longitudinal_request_is_direct_and_bounded(self):
        ego = car(9, 100, 0, 8)
        target = choose_formation_target(
            ego, (car(1, 130, 0, 10),), CENTERS,
            SimpleFormationMemory((), "CRUISE"), P)
        self.assertEqual(formation_acceleration(ego, target, P), 2.0)
        isolated = choose_formation_target(
            ego, (), CENTERS, SimpleFormationMemory((), "CRUISE"), P)
        self.assertEqual(isolated.role, "local_head")
        self.assertEqual(formation_acceleration(ego, isolated, P), 2.0)

    def test_target_lane_gap_has_exact_eight_metre_boundary(self):
        ego = car(9, 100, 0)
        self.assertFalse(target_lane_clear(
            ego, (car(1, 107.99, 1),), 1, P))
        self.assertTrue(target_lane_clear(
            ego, (car(1, 108, 1),), 1, P))


if __name__ == "__main__":
    unittest.main()
