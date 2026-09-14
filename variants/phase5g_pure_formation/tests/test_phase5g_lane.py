"""TDD contract for the Phase 5G pure lane-formation geometry."""

import math
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import noa.formation_lane as formation_lane
import noa.simple_formation as simple_formation
from noa.formation_lane import LaneCandidate, candidate_key, phase_residual_m, rank_candidates
from noa.road import LocalRoad
from perception.contracts import (
    ControlInput,
    EgoState,
    LocalMemory,
    LocalObservation,
    NeighborDetection,
    RoadObservation,
)


CENTERS_M = (1.65, 4.95, 8.25)
LANE_PARAMETERS = {
    "noa_geometry_tolerance_m": 1e-9,
    "noa_completion_lateral_error_m": 0.2,
    "formation_position_tolerance_m": 2.0,
}


def lane_fixture(neighbors, *, ego_x_m=100.0, ego_lane=1, decorated=False):
    ego_y_m = CENTERS_M[ego_lane]
    ego = EgoState(0.0, ego_x_m, ego_y_m, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0)
    detections = []
    for track_id, x_m, y_m, vx_mps, vy_mps, hidden_type in neighbors:
        fields = {
            "track_id": track_id,
            "relative_x_m": x_m - ego_x_m,
            "relative_y_m": y_m - ego_y_m,
            "relative_vx_mps": vx_mps - ego.vx_mps,
            "relative_vy_mps": vy_mps,
            "relative_heading_rad": 0.0,
            "length_m": 4.5,
            "width_m": 1.8,
            "measurement_time_s": 0.0,
        }
        if decorated:
            fields.update(actor_label=f"actor-{track_id}", hidden_type=hidden_type)
            detections.append(SimpleNamespace(**fields))
        else:
            detections.append(NeighborDetection(**fields))
    road_observation = RoadObservation(0.0, (), ())
    observation = LocalObservation(0.0, tuple(detections), road_observation)
    control = ControlInput(ego, observation, LocalMemory((), "phase5g_test"))
    road = LocalRoad(None, CENTERS_M, ego_y_m)
    return control, road


def translated_candidate(candidate, offset_m):
    signature = candidate.reference_signature
    if signature is not None:
        signature = (signature[0] - offset_m,) + signature[1:]
    return (
        candidate.lane_index,
        candidate.target_y_m,
        candidate.target_x_m - offset_m,
        signature,
        candidate.satisfied_relations,
        candidate.max_residual_m,
        candidate.residual_sum_m,
        candidate.changes_lane,
    )


def relation_winner(result):
    if result.startswith("yield_"):
        return "peer"
    if result.startswith("ego_"):
        return "ego"
    return None


class Phase5GGeometryTests(unittest.TestCase):
    def test_target_spacing_uses_same_and_adjacent_lane_rules(self):
        self.assertEqual(
            formation_lane.target_spacing_m(candidate_lane=1, reference_lane=1, d_m=15.0),
            30.0,
        )
        self.assertEqual(
            formation_lane.target_spacing_m(candidate_lane=1, reference_lane=0, d_m=15.0),
            15.0,
        )
        self.assertIsNone(
            formation_lane.target_spacing_m(candidate_lane=2, reference_lane=0, d_m=15.0)
        )

    def test_priority_relation_exact_public_results_and_precedence(self):
        priority_relation = formation_lane.priority_relation
        self.assertEqual(
            priority_relation(100.0, 0, 101.0, 1, False, False, 2.0),
            "yield_upper_lane",
        )
        self.assertEqual(
            priority_relation(105.0, 0, 100.0, 1, False, False, 2.0),
            "ego_visible_front",
        )
        self.assertEqual(
            priority_relation(100.0, 0, 103.0, 1, False, False, 2.0),
            "yield_visible_front",
        )
        self.assertEqual(
            priority_relation(100.0, 0, 100.0, 1, True, False, 2.0),
            "yield_entered",
        )
        self.assertEqual(
            priority_relation(100.0, 0, 100.0, 1, False, True, 2.0),
            "yield_visible_inward_motion",
        )
        self.assertEqual(
            priority_relation(100.0, 0, 200.0, 1, True, True, 2.0),
            "yield_entered",
        )

    def test_priority_relation_is_translation_invariant(self):
        arguments = (100.0, 0, 103.0, 1, False, False, 2.0)
        shifted = (6100.0, 0, 6103.0, 1, False, False, 2.0)
        self.assertEqual(
            formation_lane.priority_relation(*arguments),
            formation_lane.priority_relation(*shifted),
        )

    def test_priority_relation_two_view_winners_are_antisymmetric(self):
        cases = (
            ((100.0, 0, 100.0, 1, True, False, 2.0), (100.0, 1, 100.0, 0, False, False, 2.0)),
            ((100.0, 0, 100.0, 1, False, True, 2.0), (100.0, 1, 100.0, 0, False, False, 2.0)),
            ((100.0, 0, 103.0, 1, False, False, 2.0), (103.0, 1, 100.0, 0, False, False, 2.0)),
            ((105.0, 0, 100.0, 1, False, False, 2.0), (100.0, 1, 105.0, 0, False, False, 2.0)),
            ((100.0, 0, 101.0, 1, False, False, 2.0), (101.0, 1, 100.0, 0, False, False, 2.0)),
            ((101.0, 1, 100.0, 0, False, False, 2.0), (100.0, 0, 101.0, 1, False, False, 2.0)),
        )
        seen = set()
        for first, second in cases:
            with self.subTest(first=first, second=second):
                first_result = formation_lane.priority_relation(*first)
                second_result = formation_lane.priority_relation(*second)
                self.assertIsNotNone(relation_winner(first_result))
                self.assertIsNotNone(relation_winner(second_result))
                self.assertNotEqual(relation_winner(first_result), relation_winner(second_result))
                seen.add(first_result)
        self.assertEqual(
            seen,
            {
                "yield_entered",
                "yield_visible_inward_motion",
                "yield_visible_front",
                "ego_visible_front",
                "yield_upper_lane",
                "ego_upper_lane",
            },
        )

    def test_visible_candidates_use_forward_physics_and_include_exactly_one_stay(self):
        neighbors = (
            (10, 115.0, CENTERS_M[0], 10.0, 0.0, "NOA"),
            (20, 130.0, CENTERS_M[1], 10.0, 0.0, "NOA"),
            (30, 115.0, CENTERS_M[2], 10.0, 0.0, "NOA"),
            (40, 90.0, CENTERS_M[1], 10.0, 0.0, "NOA"),
        )
        control, road = lane_fixture(neighbors)
        candidates = formation_lane.visible_lane_candidates(control, road, LANE_PARAMETERS)

        self.assertIs(type(candidates), tuple)
        stays = tuple(candidate for candidate in candidates if not candidate.changes_lane)
        self.assertEqual(len(stays), 1)
        self.assertEqual((stays[0].lane_index, stays[0].target_x_m), (1, 100.0))
        self.assertIsNone(stays[0].reference_signature)
        self.assertEqual({candidate.lane_index for candidate in candidates}, {0, 1, 2})
        self.assertTrue(all(abs(candidate.lane_index - 1) <= 1 for candidate in candidates))
        references = tuple(
            candidate.reference_signature[0]
            for candidate in candidates
            if candidate.reference_signature is not None
        )
        self.assertNotIn(90.0, references)
        self.assertEqual(
            {(candidate.lane_index, candidate.target_x_m) for candidate in candidates if candidate.changes_lane},
            {(0, 85.0), (0, 115.0), (2, 85.0), (2, 115.0)},
        )
        self.assertTrue(all(candidate.satisfied_relations >= 1 for candidate in candidates))
        self.assertTrue(all(candidate.max_residual_m >= 0 for candidate in candidates))
        self.assertTrue(all(candidate.residual_sum_m >= candidate.max_residual_m for candidate in candidates))

    def test_visible_candidates_are_neighbor_order_and_sensor_label_invariant(self):
        physical = (
            (10, 115.0, CENTERS_M[0], 9.5, 0.0, "NOA"),
            (20, 130.0, CENTERS_M[1], 10.5, 0.0, "NOA"),
            (30, 145.0, CENTERS_M[2], 10.0, 0.0, "NOA"),
        )
        relabeled = tuple(
            (900 - track_id, x_m, y_m, vx_mps, vy_mps, "HDV")
            for track_id, x_m, y_m, vx_mps, vy_mps, _ in reversed(physical)
        )
        first_control, first_road = lane_fixture(physical, decorated=True)
        second_control, second_road = lane_fixture(relabeled, decorated=True)
        self.assertEqual(
            formation_lane.visible_lane_candidates(first_control, first_road, LANE_PARAMETERS),
            formation_lane.visible_lane_candidates(second_control, second_road, LANE_PARAMETERS),
        )

    def test_visible_candidates_are_translation_invariant(self):
        physical = (
            (10, 115.0, CENTERS_M[0], 9.5, 0.0, "NOA"),
            (20, 130.0, CENTERS_M[1], 10.5, 0.0, "NOA"),
        )
        offset_m = 5000.0
        shifted = tuple(
            (track_id, x_m + offset_m, y_m, vx_mps, vy_mps, hidden_type)
            for track_id, x_m, y_m, vx_mps, vy_mps, hidden_type in physical
        )
        first_control, first_road = lane_fixture(physical)
        second_control, second_road = lane_fixture(shifted, ego_x_m=100.0 + offset_m)
        first = tuple(translated_candidate(candidate, 0.0) for candidate in
                      formation_lane.visible_lane_candidates(first_control, first_road, LANE_PARAMETERS))
        second = tuple(translated_candidate(candidate, offset_m) for candidate in
                       formation_lane.visible_lane_candidates(second_control, second_road, LANE_PARAMETERS))
        self.assertEqual(first, second)

    def test_visible_candidates_reject_ambiguous_or_unstable_lane_association(self):
        equidistant = ((10, 115.0, 3.30, 10.0, 0.0, "NOA"),)
        control, road = lane_fixture(equidistant)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            formation_lane.visible_lane_candidates(
                control,
                road,
                {**LANE_PARAMETERS, "noa_completion_lateral_error_m": 2.0},
            )

        unstable = ((10, 115.0, 2.10, 10.0, 0.0, "NOA"),)
        control, road = lane_fixture(unstable)
        with self.assertRaisesRegex(ValueError, "unstable"):
            formation_lane.visible_lane_candidates(control, road, LANE_PARAMETERS)

    def test_phase_residual_is_zero_for_equivalent_lattice_positions(self):
        self.assertEqual(phase_residual_m(100, 0, 115, 1, 15), 0.0)
        self.assertEqual(phase_residual_m(100, 0, 130, 0, 15), 0.0)
        self.assertEqual(phase_residual_m(100, 0, 100, 2, 15), 0.0)

    def test_phase_residual_measures_distance_to_nearest_lattice_position(self):
        self.assertEqual(phase_residual_m(100, 0, 112, 1, 15), 3.0)

    def test_phase_residual_uses_remainder_for_large_representable_positions(self):
        self.assertEqual(phase_residual_m(2**54, 0, 0, 0, 1), 0.0)

    def test_phase_residual_rejects_unrepresentable_intermediate_values(self):
        with self.assertRaises(ValueError):
            phase_residual_m(1e308, 0, -1e308, 0, 15)
        with self.assertRaises(ValueError):
            phase_residual_m(0, 0, 0, 0, 1e308)

    def test_candidate_key_uses_the_predeclared_lexicographic_order(self):
        candidate = LaneCandidate(2, 8.25, 115.0, None, 3, 1.5, 2.0, True)
        self.assertEqual(candidate_key(candidate), (-3, 1.5, 2.0, True, -2))

    def test_change_wins_when_it_meets_the_relation_gain(self):
        stay = LaneCandidate(0, 1.65, 100, None, 2, 1, 1.5, False)
        change = LaneCandidate(1, 4.95, 115, (1.0,) * 7, 3, 1.5, 2, True)
        self.assertIs(rank_candidates((stay, change), 1)[0], change)

    def test_stay_wins_when_change_does_not_meet_the_relation_gain(self):
        stay = LaneCandidate(0, 1.65, 100, None, 2, 1, 1.5, False)
        tied_change = LaneCandidate(1, 4.95, 115, (1.0,) * 7, 2, 1, 1.5, True)
        self.assertIs(rank_candidates((stay, tied_change), 1)[0], stay)

    def test_multiple_stay_candidates_use_the_deterministic_best_key(self):
        worse_stay = LaneCandidate(0, 1.65, 100, None, 2, 2, 2, False)
        best_stay = LaneCandidate(1, 4.95, 115, None, 2, 1, 1.5, False)
        self.assertEqual(rank_candidates((worse_stay, best_stay), 1), (best_stay, worse_stay))


class Phase5GLaneValidationTests(unittest.TestCase):
    def test_target_spacing_rejects_unrepresentable_integer_with_field_context(self):
        with self.assertRaisesRegex(ValueError, "d_m"):
            formation_lane.target_spacing_m(0, 0, 10**400)

    def test_priority_rejects_unrepresentable_integer_with_field_context(self):
        with self.assertRaisesRegex(ValueError, "ego_x_m"):
            formation_lane.priority_relation(10**400, 0, 0, 1, False, False, 2.0)

    def test_candidate_rejects_unrepresentable_integer_with_field_context(self):
        with self.assertRaisesRegex(ValueError, "target_y_m"):
            LaneCandidate(0, 10**400, 0, None, 0, 0, 0, False)

    def test_phase_residual_rejects_unrepresentable_integer_with_field_context(self):
        with self.assertRaisesRegex(ValueError, "ego_x_m"):
            phase_residual_m(10**400, 0, 0, 0, 15.0)

    def test_candidate_lane_index_must_be_nonnegative(self):
        with self.assertRaisesRegex(ValueError, "lane_index"):
            LaneCandidate(-1, 1.65, 100, None, 0, 0, 0, False)

    def test_new_lane_apis_reject_invalid_public_arguments(self):
        with self.assertRaises(TypeError):
            formation_lane.target_spacing_m(True, 0, 15.0)
        with self.assertRaises(ValueError):
            formation_lane.target_spacing_m(0, 0, 0.0)
        with self.assertRaises(TypeError):
            formation_lane.priority_relation(100.0, 0, 101.0, 1, 1, False, 2.0)
        with self.assertRaises(ValueError):
            formation_lane.priority_relation(100.0, 0, math.inf, 1, False, False, 2.0)
        control, road = lane_fixture(())
        with self.assertRaisesRegex(ValueError, "formation_position_tolerance_m"):
            formation_lane.visible_lane_candidates(
                control,
                road,
                {key: value for key, value in LANE_PARAMETERS.items()
                 if key != "formation_position_tolerance_m"},
            )

    def test_registration_is_exactly_the_twenty_top_level_parameters(self):
        expected_lane = {
            "formation_lane_change_enabled": True,
            "formation_lane_stable_s": 1.0,
            "formation_lane_lock_s": 5.0,
            "formation_lane_front_margin_m": 2.0,
            "formation_lane_backoff_min_s": 0.5,
            "formation_lane_backoff_max_s": 2.0,
            "formation_lane_duration_candidates_s": [5.0, 7.5, 10.0],
            "formation_lane_min_relation_gain": 1,
        }
        expected_simple = {
            "simple_formation_local_range_m": 90.0,
            "simple_formation_adjacent_gap_m": 15.0,
            "simple_formation_same_gap_m": 30.0,
            "simple_formation_position_tolerance_m": 2.0,
            "simple_formation_accel_limit_mps2": 0.5,
            "simple_formation_max_lane_changes": 1,
        }
        expected = {
            "phase5g_enabled": True,
            "simple_formation_enabled": False,
            **expected_lane,
            **expected_simple,
            "phase5g_target_speed_mps": 10.0,
            "phase5g_initial_speed_min_mps": 8.0,
            "phase5g_initial_speed_max_mps": 12.0,
            "phase5g_duration_s": 45.0,
        }
        config_path = Path(__file__).resolve().parents[1] / "configs" / "phase5g.json"
        actual = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)
        self.assertEqual(set(actual), set(expected))
        self.assertEqual(len(actual), 20)

        lane_keys = {key for key in actual if key.startswith("formation_lane_")}
        self.assertEqual(lane_keys, set(expected_lane))
        self.assertEqual({key: actual[key] for key in lane_keys}, expected_lane)
        self.assertTrue(all(type(actual[key]) is float for key in lane_keys
                            if key not in {
                                "formation_lane_change_enabled",
                                "formation_lane_duration_candidates_s",
                                "formation_lane_min_relation_gain",
                            }))
        self.assertIs(type(actual["formation_lane_change_enabled"]), bool)
        self.assertIs(type(actual["formation_lane_duration_candidates_s"]), list)
        self.assertTrue(all(type(value) is float
                            for value in actual["formation_lane_duration_candidates_s"]))
        self.assertIs(type(actual["formation_lane_min_relation_gain"]), int)

        self.assertEqual(set(simple_formation.PARAMETERS), set(expected_simple))
        self.assertEqual(
            {key: actual[key] for key in simple_formation.PARAMETERS},
            expected_simple,
        )
        self.assertIs(type(actual["simple_formation_enabled"]), bool)
        self.assertTrue(all(type(actual[key]) is float
                            for key in simple_formation.PARAMETERS[:-1]))
        self.assertIs(type(actual[simple_formation.PARAMETERS[-1]]), int)

        self.assertIs(type(actual["phase5g_enabled"]), bool)

    def test_lane_indices_must_be_exact_ints_not_bools(self):
        with self.assertRaises(TypeError):
            LaneCandidate(True, 1.65, 100, None, 0, 0, 0, False)
        with self.assertRaises(TypeError):
            phase_residual_m(100, False, 115, 1, 15)

    def test_changes_lane_must_be_an_exact_bool(self):
        with self.assertRaises(TypeError):
            LaneCandidate(0, 1.65, 100, None, 0, 0, 0, 0)

    def test_satisfied_relations_must_be_a_nonnegative_exact_int(self):
        with self.assertRaises(TypeError):
            LaneCandidate(0, 1.65, 100, None, True, 0, 0, False)
        with self.assertRaises(ValueError):
            LaneCandidate(0, 1.65, 100, None, -1, 0, 0, False)

    def test_candidate_numbers_must_be_finite_and_residuals_nonnegative(self):
        with self.assertRaises(TypeError):
            LaneCandidate(0, "1.65", 100, None, 0, 0, 0, False)
        with self.assertRaises(ValueError):
            LaneCandidate(0, math.inf, 100, None, 0, 0, 0, False)
        with self.assertRaises(ValueError):
            LaneCandidate(0, 1.65, 100, None, 0, -0.1, 0, False)
        with self.assertRaises(ValueError):
            LaneCandidate(0, 1.65, 100, None, 0, 0, math.nan, False)

    def test_reference_signature_is_none_or_seven_finite_fields_with_positive_size(self):
        with self.assertRaises(TypeError):
            LaneCandidate(0, 1.65, 100, [1.0] * 7, 0, 0, 0, False)
        with self.assertRaises(ValueError):
            LaneCandidate(0, 1.65, 100, (1.0,) * 6, 0, 0, 0, False)
        with self.assertRaises(ValueError):
            LaneCandidate(0, 1.65, 100, (1.0,) * 5 + (0.0, 1.0), 0, 0, 0, False)
        with self.assertRaises(ValueError):
            LaneCandidate(0, 1.65, 100, (1.0,) * 6 + (math.inf,), 0, 0, 0, False)

    def test_phase_residual_requires_finite_numbers_and_positive_spacing(self):
        with self.assertRaises(ValueError):
            phase_residual_m(math.nan, 0, 115, 1, 15)
        with self.assertRaises(ValueError):
            phase_residual_m(100, 0, 115, 1, 0)

    def test_minimum_gain_is_an_exact_positive_int(self):
        stay = LaneCandidate(0, 1.65, 100, None, 0, 0, 0, False)
        with self.assertRaises(TypeError):
            rank_candidates((stay,), True)
        with self.assertRaises(ValueError):
            rank_candidates((stay,), 0)

    def test_rank_requires_nonempty_candidates_and_a_stay_candidate(self):
        change = LaneCandidate(1, 4.95, 115, None, 1, 0, 0, True)
        with self.assertRaises(ValueError):
            rank_candidates((), 1)
        with self.assertRaises(ValueError):
            rank_candidates((change,), 1)
