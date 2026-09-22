"""Integration tests for the small local if/else formation controller path."""
from dataclasses import asdict, fields, replace
import ast
import inspect
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from models.bezier import QuadraticLaneChange
from models.kinematic import KinematicModel
from models.vehicle import Actuation, VehicleState
from noa import simple_formation
from noa.contracts import NoaMemory
from noa.controller import decide
from noa.simple_formation import JoinDecision, SimpleFormationMemory
from perception.contracts import (
    ControlInput,
    EgoState,
    LocalObservation,
    NeighborDetection,
    RoadObservation,
)
from perception.road import VisibleRoad
from research.common import settings
from simulation.phase5g_clock import (
    CLOCK_SCHEMA,
    Phase5GClock,
    initial_memory_hash,
    restore_initial_memories,
)


SAFE = {
    "safe": True,
    "reason": "conditional_swept_prediction_clear",
    "at_s": None,
    "checked_s": 5.0,
}
REJECTED = {
    "safe": False,
    "reason": "neighbor_reachable_occupancy",
    "at_s": 0.1,
    "checked_s": 0.1,
}
CENTERS_M = (1.65, 4.95, 8.25)


class SimpleFormationControllerTests(unittest.TestCase):
    def setUp(self):
        self.model = KinematicModel.from_config()
        self.simple = {
            "simple_formation_component_gap_m": 50.0,
            "simple_formation_middle_offset_m": 15.0,
            "simple_formation_same_lane_gap_m": 30.0,
            "simple_formation_position_tolerance_m": 2.0,
            "simple_formation_speed_tolerance_mps": 0.5,
            "simple_formation_stable_time_s": 1.0,
            "simple_formation_reference_switch_gain_m": 2.0,
            "simple_formation_min_lane_change_speed_mps": 5.0,
            "simple_formation_target_lane_clearance_m": 8.0,
        }
        self.p = {
            **self.model.p,
            **settings("phase4"),
            **self.simple,
            "formation_enabled": True,
            "phase5g_enabled": True,
            "simple_formation_enabled": True,
            # Simple mode must override, rather than enter, the legacy lane path.
            "formation_lane_change_enabled": True,
            "r5_enabled": False,
        }

    @staticmethod
    def road_observation(time_s=0.0, ego_x=100.0, ego_y=1.65):
        x0, x1 = -300.0, 1200.0
        return RoadObservation(
            time_s,
            (
                ((x0, -ego_y), (x1, -ego_y)),
                ((x0, 9.9 - ego_y), (x1, 9.9 - ego_y)),
            ),
            tuple(
                ((x0, center - ego_y + 1.65), (x1, center - ego_y + 1.65))
                for center in CENTERS_M[:-1]
            ),
        )

    @staticmethod
    def neighbor(track_id, relative_x, lane, speed=20.0, *, ego_speed=20.0,
                 time_s=0.0, relative_y=None, width=1.8, length=4.5):
        y = CENTERS_M[lane] - CENTERS_M[0] if relative_y is None else relative_y
        return NeighborDetection(
            track_id,
            relative_x,
            y,
            speed - ego_speed,
            0.0,
            0.0,
            length,
            width,
            time_s,
        )

    def control(self, *, time_s=0.0, x=100.0, lane=0, speed=20.0,
                heading=0.0, vy=0.0, acceleration=0.0, neighbors=(), memory=None,
                road=None):
        ego = EgoState(
            time_s, x, CENTERS_M[lane], heading, speed, vy, 0.0, acceleration, 0.0
        )
        observation = LocalObservation(
            time_s,
            tuple(neighbors),
            road or self.road_observation(time_s, x, CENTERS_M[lane]),
        )
        return ControlInput(
            ego,
            observation,
            memory or SimpleFormationMemory((), "CRUISE"),
        )

    def test_no_target_uses_noa_fallback_and_clears_reference(self):
        memory = SimpleFormationMemory((), "CRUISE", reference_track_id=19,
                                       join_phase="FORMED", desired_lane_index=0)
        control = self.control(memory=memory)
        with patch("noa.controller._longitudinal", return_value=(-1.25, None, None, False, "cruise")):
            decision = decide(control, self.p)
        self.assertEqual(decision.action.acceleration_mps2, -1.25)
        self.assertIsNone(decision.memory.reference_track_id)
        simple = decision.diagnostics["simple_formation"]
        self.assertEqual(simple["role"], "no_target")
        self.assertIsNone(simple["target_x_m"])
        self.assertIsNone(simple["requested_acceleration_mps2"])
        self.assertFalse(simple["emergency_override"])

    def test_direct_formation_accel_replaces_opposite_base_cruise(self):
        upper = self.neighbor(7, 20.0, 2)
        with patch("noa.controller._longitudinal", return_value=(-2.0, None, None, False, "cruise")):
            decision = decide(self.control(neighbors=(upper,), memory=SimpleFormationMemory(
                (), "CRUISE", join_phase="FORMED", desired_lane_index=0)), self.p)
        self.assertEqual(decision.action.acceleration_mps2, 2.0)
        self.assertEqual(decision.memory.reference_track_id, 7)
        simple = decision.diagnostics["simple_formation"]
        self.assertEqual(simple["role"], "lower_aligned")
        self.assertEqual(simple["target_x_m"], 120.0)
        self.assertEqual(simple["position_error_m"], 20.0)
        self.assertEqual(simple["reference_track_id"], 7)
        self.assertEqual(simple["requested_acceleration_mps2"], 2.0)
        self.assertEqual(simple["lane_reason"], "formed_hold")

    def test_distant_lane_end_does_not_cap_direct_request(self):
        road = SimpleNamespace(
            centers_m=CENTERS_M,
            current_center_m=CENTERS_M[2],
            lane_end=lambda *_: 1000.0,
            envelope=SimpleNamespace(regions=((-300.0, 1200.0, 0.0, 9.9),)),
        )
        with patch("noa.controller.reconstruct", return_value=road), patch(
            "noa.controller._longitudinal",
            side_effect=((0.5, None, None, False, "cruise"),
                         (-1.5, None, None, False, "observed_lane_end_braking")),
        ) as longitudinal:
            decision = decide(self.control(lane=2, speed=18.0), self.p)
        self.assertEqual(longitudinal.call_count, 1)
        self.assertEqual(decision.diagnostics["simple_formation"]["requested_acceleration_mps2"],
                         2.0)
        self.assertEqual(decision.action.acceleration_mps2, 2.0)

    @staticmethod
    def ending_upper_road(end_x, *, time_s=0.0, ego_x=100.0):
        end_rel = end_x - ego_x
        ego_y = CENTERS_M[2]
        return RoadObservation(
            time_s,
            (
                ((-300.0, -ego_y), (1200.0, -ego_y)),
                ((-300.0, 9.9-ego_y), (end_rel, 9.9-ego_y)),
                ((end_rel, 6.6-ego_y), (1200.0, 6.6-ego_y)),
            ),
            (
                ((-300.0, 3.3-ego_y), (end_rel, 3.3-ego_y)),
                ((-300.0, 6.6-ego_y), (end_rel, 6.6-ego_y)),
            ),
        )

    def test_near_lane_end_caps_direct_request_with_road_stop(self):
        road = SimpleNamespace(
            centers_m=CENTERS_M,
            current_center_m=CENTERS_M[2],
            lane_end=lambda *_: 140.0,
            envelope=SimpleNamespace(regions=((-300.0, 1200.0, 0.0, 9.9),)),
        )
        with patch("noa.controller.reconstruct", return_value=road), patch(
            "noa.controller._longitudinal",
            side_effect=((0.5, None, None, False, "cruise"),
                         (-1.5, None, None, False, "observed_lane_end_braking")),
        ) as longitudinal:
            decision = decide(self.control(lane=2, speed=18.0), self.p)
        self.assertEqual(longitudinal.call_count, 2)
        self.assertEqual(decision.diagnostics["simple_formation"]["requested_acceleration_mps2"],
                         2.0)
        self.assertEqual(decision.action.acceleration_mps2, -1.5)

    def test_low_speed_lane_end_capture_never_restarts_formation_drive(self):
        safe_end = (100.0 + self.p["length_m"]/2
                    + self.p["noa_body_margin_m"]
                    + self.p["noa_standstill_gap_m"] + 1.0)
        for speed in (0.0, 0.1):
            with self.subTest(speed=speed):
                decision = decide(self.control(
                    lane=2, speed=speed,
                    road=self.ending_upper_road(safe_end)), self.p)
                self.assertEqual(decision.diagnostics["reason"],
                                 "observed_lane_end_hold")
                self.assertEqual(decision.diagnostics["simple_formation"][
                    "requested_acceleration_mps2"], 2.0)
                self.assertLessEqual(decision.action.acceleration_mps2, 0.0)

    def test_simple_final_acceleration_respects_configured_model_bounds(self):
        narrow = {**self.p, "min_accel_mps2": -1.0, "max_accel_mps2": 1.0}
        for speed, requested, expected in ((18.0, 2.0, 1.0),
                                           (23.0, -3.0, -1.0)):
            with self.subTest(speed=speed):
                decision = decide(self.control(lane=2, speed=speed), narrow)
                self.assertEqual(decision.diagnostics["simple_formation"][
                    "requested_acceleration_mps2"], requested)
                self.assertEqual(decision.action.acceleration_mps2, expected)

    def test_near_road_emergency_sets_action_diagnostic_and_state(self):
        end_x = (100.0 + self.p["length_m"]/2
                 + self.p["noa_body_margin_m"]
                 + self.p["noa_standstill_gap_m"] + 10.0)
        decision = decide(self.control(
            lane=2, speed=20.0,
            road=self.ending_upper_road(end_x)), self.p)
        simple = decision.diagnostics["simple_formation"]
        self.assertEqual(decision.action.acceleration_mps2,
                         self.p["min_accel_mps2"])
        self.assertTrue(simple["road_end_override"])
        self.assertTrue(simple["emergency_override"])
        self.assertEqual(decision.memory.own_behavior, "EMERGENCY")
        self.assertEqual(simple["road_end_reason"], decision.diagnostics["reason"])

    def test_upper_leader_uses_target_speed(self):
        with patch("noa.controller._longitudinal", return_value=(-1.0, None, None, False, "cruise")):
            decision = decide(self.control(lane=2, speed=20.0), self.p)
        expected = max(-3.0, min(2.0, self.p["noa_target_speed_mps"] - 20.0))
        self.assertEqual(decision.action.acceleration_mps2, expected)
        self.assertEqual(decision.diagnostics["simple_formation"]["role"], "upper_leader")
        self.assertIsNone(decision.memory.reference_track_id)

    def test_joiner_tracks_fixed_anchor_and_preserves_join_memory(self):
        memory = SimpleFormationMemory((), "CRUISE", join_phase="JOINING",
                                       desired_lane_index=2, join_anchor_track_id=7)
        anchor = self.neighbor(7, 30.0, 1, speed=18.0)
        decision = decide(self.control(neighbors=(anchor,), memory=memory), self.p)
        self.assertEqual(decision.diagnostics["simple_formation"]["role"], "joiner")
        self.assertEqual(decision.diagnostics["simple_formation"]["target_x_m"], 115.0)
        self.assertEqual(decision.memory.join_anchor_track_id, 7)
        self.assertEqual(decision.memory.desired_lane_index, 2)
        self.assertEqual(decision.memory.reference_track_id, 7)

    def joining(self, lane=0, final=2, anchor=7):
        return SimpleFormationMemory((), "CRUISE", join_phase="JOINING",
                                     desired_lane_index=final,
                                     join_anchor_track_id=anchor)

    def test_reachable_guard_cannot_veto_new_simple_plan(self):
        anchor = self.neighbor(7, 30.0, 1)
        with patch("noa.controller.verify_candidate", side_effect=AssertionError("reachable guard used")):
            result = decide(self.control(neighbors=(anchor,),
                                         memory=self.joining()), self.p)
        self.assertIsNotNone(result.memory.plan)
        self.assertAlmostEqual(result.memory.plan.y_target_m, CENTERS_M[1])
        self.assertEqual(result.memory.lane_change_reason, "simple_formation_join")
        self.assertEqual(result.diagnostics["simple_formation"]["hard_gate"], "clear")

    def test_speed_gate_exact_boundary(self):
        for speed, allowed in ((4.99, False), (5.0, True)):
            with self.subTest(speed=speed):
                anchor = self.neighbor(7, 30.0, 1, ego_speed=speed)
                result = decide(self.control(speed=speed, neighbors=(anchor,),
                                             memory=self.joining()), self.p)
                self.assertEqual(result.memory.plan is not None, allowed)
                if not allowed:
                    self.assertEqual(result.diagnostics["simple_formation"]["hard_gate"], "speed")

    def test_clearance_gate_exact_boundary_and_body_overlap(self):
        for distance, allowed in ((7.99, False), (8.0, True)):
            with self.subTest(distance=distance):
                anchor = self.neighbor(7, 30.0, 1)
                near = self.neighbor(8, -distance, 1)
                result = decide(self.control(neighbors=(anchor, near),
                                             memory=self.joining()), self.p)
                self.assertEqual(result.memory.plan is not None, allowed)
                if not allowed:
                    self.assertEqual(result.diagnostics["simple_formation"]["hard_gate"], "clearance")
        narrow = {**self.p, "simple_formation_target_lane_clearance_m": 1.0}
        anchor = self.neighbor(7, 30.0, 1)
        overlapping = self.neighbor(8, 1.1, 1)
        result = decide(self.control(neighbors=(anchor, overlapping),
                                     memory=self.joining()), narrow)
        self.assertIsNone(result.memory.plan)
        self.assertEqual(result.diagnostics["simple_formation"]["hard_gate"], "body")

    def test_current_lane_body_overlap_blocks_free_admission(self):
        admission = JoinDecision(2, 115.0, 7, "middle_tail", (0, 1, 0))
        anchor = self.neighbor(7, 30.0, 1)
        overlap = self.neighbor(8, 0.0, 0)
        with patch("noa.controller.simple_formation.choose_join", return_value=admission):
            result = decide(self.control(neighbors=(anchor, overlap)), self.p)
        self.assertEqual(result.memory.join_phase, "FREE")
        self.assertIsNone(result.memory.plan)
        self.assertEqual(result.diagnostics["simple_formation"]["hard_gate"], "body")

    def test_final_lane_outside_visible_road_blocks_plan(self):
        anchor = self.neighbor(7, 30.0, 1)
        result = decide(self.control(neighbors=(anchor,), memory=self.joining(final=3)), self.p)
        self.assertIsNone(result.memory.plan)
        self.assertEqual(result.diagnostics["simple_formation"]["hard_gate"], "road")

    def test_active_simple_plan_keeps_lateral_target_with_new_gap_and_brakes(self):
        plan = QuadraticLaneChange(0.0, CENTERS_M[0], CENTERS_M[1], 5.0, 20.0)
        memory = replace(self.joining(), plan=plan, target_y_m=CENTERS_M[1],
                         lane_change_reason="simple_formation_join")
        anchor = self.neighbor(7, 30.0, 1, time_s=1.0)
        cut_in = self.neighbor(8, 3.0, 1, speed=0.0, time_s=1.0)
        with patch("noa.controller.verify_candidate", side_effect=AssertionError("reachable guard used")):
            result = decide(self.control(time_s=1.0, neighbors=(anchor, cut_in),
                                         memory=memory), self.p)
        self.assertIs(result.memory.plan, plan)
        self.assertEqual(result.memory.desired_lane_index, 2)
        self.assertEqual(result.memory.join_anchor_track_id, 7)
        self.assertLess(result.action.acceleration_mps2, 0.0)
        self.assertEqual(result.diagnostics["simple_formation"]["next_lane_index"], 1)

    def test_active_simple_plan_brakes_for_present_target_lane_body_overlap(self):
        plan = QuadraticLaneChange(0.0, CENTERS_M[0], CENTERS_M[1], 5.0, 20.0)
        memory = replace(self.joining(), plan=plan, target_y_m=CENTERS_M[1],
                         lane_change_reason="simple_formation_join")
        anchor = self.neighbor(7, 80.0, 1, time_s=1.0)
        overlap = self.neighbor(8, 0.0, 1, time_s=1.0)
        with patch("noa.controller.verify_candidate", side_effect=AssertionError("reachable guard used")):
            result = decide(self.control(time_s=1.0, neighbors=(anchor, overlap),
                                         memory=memory), self.p)
        self.assertIs(result.memory.plan, plan)
        self.assertEqual(result.action.acceleration_mps2, self.p["min_accel_mps2"])
        self.assertTrue(result.diagnostics["simple_formation"]["emergency_override"])

    def test_two_adjacent_steps_keep_final_lane_and_then_stabilize(self):
        anchor = self.neighbor(7, 15.0, 1)
        first = decide(self.control(neighbors=(anchor,), memory=self.joining()), self.p)
        self.assertAlmostEqual(first.memory.plan.y_target_m, CENTERS_M[1])
        middle = decide(self.control(time_s=5.0, lane=1, neighbors=(self.neighbor(
            7, 15.0, 1, time_s=5.0, relative_y=0.0),),
            memory=first.memory), self.p)
        self.assertEqual(middle.memory.desired_lane_index, 2)
        self.assertNotEqual(middle.memory.join_phase, "STABILIZING")
        second = decide(self.control(time_s=5.1, lane=1, neighbors=(self.neighbor(
            7, 15.0, 1, time_s=5.1, relative_y=0.0),),
            memory=middle.memory), self.p)
        self.assertIsNotNone(second.memory.plan)
        self.assertAlmostEqual(second.memory.plan.y_target_m, CENTERS_M[2])
        final = decide(self.control(time_s=10.1, lane=2, neighbors=(self.neighbor(
            7, 15.0, 1, time_s=10.1, relative_y=CENTERS_M[1]-CENTERS_M[2]),),
            memory=second.memory), self.p)
        self.assertEqual(final.memory.join_phase, "STABILIZING")

    def test_free_admission_uses_join_decision_and_waiter_does_not_plan(self):
        anchor = self.neighbor(7, 30.0, 1)
        admission = JoinDecision(2, 130.0, 7, "upper_tail", (0, 0, 1))
        with patch("noa.controller.simple_formation.choose_join", return_value=admission) as choose:
            result = decide(self.control(neighbors=(anchor,)), self.p)
        choose.assert_called_once()
        self.assertEqual(result.memory.join_phase, "JOINING")
        self.assertEqual(result.memory.desired_lane_index, 2)
        self.assertEqual(result.memory.join_anchor_track_id, 7)
        self.assertIsNotNone(result.memory.plan)
        waiting = JoinDecision(None, None, None, "wait_not_next", (0, 0, 1))
        with patch("noa.controller.simple_formation.choose_join", return_value=waiting):
            result = decide(self.control(neighbors=(anchor,)), self.p)
        self.assertEqual(result.memory.join_phase, "FREE")
        self.assertIsNone(result.memory.plan)

    def test_physical_nearest_waiter_acts_while_following_waiter_stays_free(self):
        near = decide(self.control(x=120.0, lane=0, neighbors=(
            self.neighbor(1, 25.0, 1),
            self.neighbor(2, -10.0, 1))), self.p)
        far = decide(self.control(x=110.0, lane=1, neighbors=(
            self.neighbor(1, 35.0, 1, relative_y=0.0),
            self.neighbor(2, 10.0, 0, relative_y=CENTERS_M[0]-CENTERS_M[1]))), self.p)
        self.assertEqual(near.memory.join_phase, "JOINING")
        self.assertIsNotNone(near.memory.plan)
        self.assertEqual(far.memory.join_phase, "FREE")
        self.assertIsNone(far.memory.plan)

    def test_isolated_founder_keeps_anchor_none_during_adjacent_join(self):
        first = decide(self.control(lane=0), self.p)
        self.assertEqual(first.memory.join_phase, "JOINING")
        self.assertEqual(first.memory.desired_lane_index, 2)
        self.assertIsNone(first.memory.join_anchor_track_id)
        self.assertAlmostEqual(first.memory.plan.y_target_m, CENTERS_M[1])
        active = decide(self.control(time_s=1.0, lane=0, memory=first.memory), self.p)
        self.assertIsNotNone(active.memory.plan)
        self.assertIsNone(active.memory.join_anchor_track_id)

    def test_completed_change_does_not_limit_later_physical_join_step(self):
        memory = replace(self.joining(lane=1, final=2),
                         completed_lane_changes=1, last_lc_end_s=5.0)
        anchor = self.neighbor(7, 15.0, 1, relative_y=0.0, time_s=5.1)
        result = decide(self.control(time_s=5.1, lane=1, neighbors=(anchor,),
                                     memory=memory), self.p)
        self.assertIsNotNone(result.memory.plan)
        self.assertAlmostEqual(result.memory.plan.y_target_m, CENTERS_M[2])

    def test_stability_requires_continuous_position_speed_lane_and_no_emergency(self):
        memory = self.joining(lane=2, final=2)
        good = self.neighbor(7, 15.0, 1, speed=20.0,
                             relative_y=CENTERS_M[1]-CENTERS_M[2])
        first = decide(self.control(lane=2, x=100.0, neighbors=(good,), memory=memory), self.p)
        self.assertEqual(first.memory.stable_since_s, 0.0)
        self.assertEqual(first.memory.join_phase, "STABILIZING")
        late = decide(self.control(time_s=1.0, lane=2, x=100.0,
                                   neighbors=(replace(good, measurement_time_s=1.0),),
                                   memory=first.memory), self.p)
        self.assertEqual(late.memory.join_phase, "FORMED")
        for change in (dict(neighbors=(replace(good, relative_x_m=19.0),)),
                       dict(speed=18.0, neighbors=(replace(good, relative_vx_mps=2.0),)),
                       dict(lane=1, neighbors=(replace(good, relative_y_m=0.0),)),
                       dict(neighbors=(self.neighbor(9, 3.0, 2, speed=0.0,
                                                     time_s=0.5, relative_y=0.0), good))):
            with self.subTest(change=change):
                case = {"time_s": 0.5, "lane": 2,
                        "neighbors": (replace(good, measurement_time_s=0.5),),
                        "memory": first.memory}
                case.update(change)
                if "neighbors" in change:
                    case["neighbors"] = tuple(replace(row, measurement_time_s=0.5)
                                               for row in change["neighbors"])
                result = decide(self.control(**case), self.p)
                self.assertEqual(result.memory.join_phase, "JOINING")
                self.assertIsNone(result.memory.stable_since_s)
        broken = decide(self.control(time_s=0.5, lane=2,
                                     neighbors=(replace(good, relative_x_m=19.0,
                                                        measurement_time_s=0.5),),
                                     memory=first.memory), self.p)
        restarted = decide(self.control(time_s=0.6, lane=2,
                                        neighbors=(replace(good, measurement_time_s=0.6),),
                                        memory=broken.memory), self.p)
        self.assertEqual(restarted.memory.stable_since_s, 0.6)
        before = decide(self.control(time_s=1.5, lane=2,
                                     neighbors=(replace(good, measurement_time_s=1.5),),
                                     memory=restarted.memory), self.p)
        self.assertEqual(before.memory.join_phase, "STABILIZING")
        after = decide(self.control(time_s=1.7, lane=2,
                                    neighbors=(replace(good, measurement_time_s=1.7),),
                                    memory=before.memory), self.p)
        self.assertEqual(after.memory.join_phase, "FORMED")

    def test_formed_vehicle_does_not_start_new_plan(self):
        memory = SimpleFormationMemory((), "CRUISE", join_phase="FORMED",
                                       desired_lane_index=2)
        with patch("noa.controller.simple_formation.choose_join", side_effect=AssertionError("readmission")):
            result = decide(self.control(lane=2, memory=memory), self.p)
        self.assertIsNone(result.memory.plan)
        self.assertEqual(result.memory.join_phase, "FORMED")

    def test_join_anchor_loss_uses_noa_fallback_without_retargeting(self):
        memory = SimpleFormationMemory((), "CRUISE", join_phase="STABILIZING",
                                       desired_lane_index=2, join_anchor_track_id=7,
                                       reference_track_id=7)
        other = self.neighbor(8, 20.0, 2)
        with patch("noa.controller._longitudinal", return_value=(-1.0, None, None, False, "cruise")):
            decision = decide(self.control(neighbors=(other,), memory=memory), self.p)
        self.assertEqual(decision.action.acceleration_mps2, -1.0)
        self.assertEqual(decision.diagnostics["simple_formation"]["reference_reason"],
                         "join_anchor_lost")
        self.assertIsNone(decision.memory.reference_track_id)
        self.assertIsNone(decision.memory.join_anchor_track_id)

    def test_existing_noa_plan_keeps_running_without_simple_diagnostic_crash(self):
        plan = QuadraticLaneChange(0.0, CENTERS_M[0], CENTERS_M[1], 5.0, 20.0)
        memory = SimpleFormationMemory((), "EXECUTE_LC", plan=plan,
                                       target_y_m=CENTERS_M[1], prepare_since_s=0.0,
                                       lane_change_reason="observed_lane_end")
        with patch("noa.controller.verify_candidate", return_value=SAFE):
            decision = decide(self.control(time_s=1.0, memory=memory), self.p)
        self.assertEqual(decision.memory.plan, plan)
        self.assertEqual(decision.diagnostics["simple_formation"]["lane_reason"],
                         "active_plan")

    def test_existing_noa_plan_fallback_guard_matches_executed_braking(self):
        plan = QuadraticLaneChange(0.0, CENTERS_M[0], CENTERS_M[1], 5.0, 20.0)
        memory = SimpleFormationMemory((), "EXECUTE_LC", plan=plan,
                                       target_y_m=CENTERS_M[1], prepare_since_s=0.0,
                                       lane_change_reason="observed_lane_end")
        with patch("noa.controller.verify_candidate",
                   side_effect=(REJECTED, SAFE)) as guard:
            decision = decide(self.control(time_s=1.0, memory=memory), self.p)
        simple = decision.diagnostics["simple_formation"]
        self.assertEqual(guard.call_count, 2)
        self.assertEqual(simple["active_plan_guards"], [
            {"kind": "active_plan", "result": REJECTED},
            {"kind": "active_plan", "result": SAFE},
        ])
        self.assertIs(simple["guard"]["result"], SAFE)
        self.assertEqual(decision.action.acceleration_mps2,
                         guard.call_args_list[-1].args[3])
        self.assertEqual(decision.memory.own_behavior, "EMERGENCY")
        self.assertTrue(simple["emergency_override"])

    def test_immediate_emergency_keeps_noa_braking(self):
        close = self.neighbor(3, 8.0, 0, speed=0.0)
        memory = SimpleFormationMemory((), "CRUISE", reference_track_id=99,
                                       join_phase="FORMED", desired_lane_index=0)
        decision = decide(self.control(neighbors=(close,), memory=memory), self.p)
        self.assertEqual(decision.memory.own_behavior, "EMERGENCY")
        self.assertTrue(decision.diagnostics["simple_formation"]["emergency_override"])
        self.assertLessEqual(decision.action.acceleration_mps2, -3.0)
        self.assertEqual(decision.memory.reference_track_id, 3)

    def test_equal_speed_forty_metre_lead_is_not_immediate_emergency(self):
        lead = self.neighbor(5, 40.0, 2, speed=20.0, relative_y=0.0)
        decision = decide(self.control(lane=2, speed=20.0,
                                       neighbors=(lead,), memory=SimpleFormationMemory(
                                           (), "CRUISE", join_phase="FORMED",
                                           desired_lane_index=2)), self.p)
        simple = decision.diagnostics["simple_formation"]
        self.assertEqual(simple["role"], "upper_follower")
        self.assertEqual(simple["requested_acceleration_mps2"], 2.0)
        self.assertFalse(simple["emergency_override"])
        self.assertEqual(decision.action.acceleration_mps2, 2.0)

    def test_current_bumper_gap_and_closing_ttc_override_direct_request(self):
        cases = ((5.0, 20.0), (40.0, 0.0))
        for distance, speed in cases:
            with self.subTest(distance=distance, speed=speed):
                lead = self.neighbor(5, distance, 2, speed=speed,
                                     relative_y=0.0)
                decision = decide(self.control(lane=2, speed=20.0,
                                               neighbors=(lead,)), self.p)
                self.assertTrue(decision.diagnostics["simple_formation"]["emergency_override"])
                self.assertLess(decision.action.acceleration_mps2, 0.0)

    def test_overlapping_same_speed_body_forces_emergency_braking(self):
        overlap = self.neighbor(5, 0.0, 0, speed=18.0, ego_speed=18.0)
        upper = self.neighbor(6, 20.0, 2, speed=20.0, ego_speed=18.0)
        decision = decide(self.control(speed=18.0, neighbors=(overlap, upper)), self.p)
        simple = decision.diagnostics["simple_formation"]
        self.assertEqual(simple["role"], "lower_aligned")
        self.assertTrue(simple["emergency_override"])
        self.assertLessEqual(decision.action.acceleration_mps2,
                             self.p["min_accel_mps2"])

    def test_stopped_ego_with_close_fast_front_body_still_brakes(self):
        close = self.neighbor(5, 5.0, 0, speed=20.0, ego_speed=0.0)
        decision = decide(self.control(speed=0.0, neighbors=(close,)), self.p)
        simple = decision.diagnostics["simple_formation"]
        self.assertEqual(simple["requested_acceleration_mps2"], 2.0)
        self.assertTrue(simple["emergency_override"])
        self.assertLessEqual(decision.action.acceleration_mps2,
                             self.p["min_accel_mps2"])

    def test_slow_lead_motivation_does_not_preempt_formation_longitudinal(self):
        slow = self.neighbor(4, 70.0, 0, speed=10.0)
        decision = decide(self.control(neighbors=(slow,), memory=SimpleFormationMemory(
            (), "CRUISE", join_phase="FORMED", desired_lane_index=0)), self.p)
        self.assertEqual(decision.diagnostics["simple_formation"]["role"],
                         "same_lane_follower")
        self.assertEqual(decision.action.acceleration_mps2, -3.0)
        self.assertIsNone(decision.memory.plan)

    def test_consistent_local_track_relabel_preserves_physical_action(self):
        first = self.neighbor(7, 20.0, 2)
        second = replace(first, track_id=107)
        a = decide(self.control(neighbors=(first,), memory=SimpleFormationMemory(
            (), "CRUISE", reference_track_id=7)), self.p)
        b = decide(self.control(neighbors=(second,), memory=SimpleFormationMemory(
            (), "CRUISE", reference_track_id=107)), self.p)
        self.assertEqual(a.action, b.action)
        self.assertEqual(a.diagnostics["simple_formation"]["target_x_m"],
                         b.diagnostics["simple_formation"]["target_x_m"])

    def test_adapter_rotates_ego_frame_measurements_without_truth_fields(self):
        adapter = getattr(simple_formation, "local_vehicles", None)
        self.assertTrue(callable(adapter), "local observation adapter is missing")
        if adapter is None:
            return
        ego = EgoState(0.0, 10.0, 20.0, math.pi / 2, 10.0, 2.0, 0.0, 0.0, 0.0)
        detection = NeighborDetection(5, 5.0, 1.0, 3.0, 4.0, 0.0, 4.5, 1.8, 0.0)
        control = ControlInput(
            ego,
            LocalObservation(0.0, (detection,), self.road_observation()),
            SimpleFormationMemory((), "CRUISE"),
        )
        vehicle = adapter(
            control,
            SimpleNamespace(
                centers_m=(21.65, 24.95, 28.25),
                envelope=SimpleNamespace(regions=((-100.0, 100.0, 20.0, 29.9),)),
            ),
            self.p,
        )[0]
        self.assertAlmostEqual(vehicle.x_m, 9.0)
        self.assertAlmostEqual(vehicle.y_m, 25.0)
        self.assertAlmostEqual(vehicle.vx_mps, -6.0)
        self.assertEqual(vehicle.track_id, 5)
        self.assertNotIn("hidden_type", {field.name for field in fields(type(detection))})

    def test_adapter_requires_the_whole_body_inside_one_lane_strip(self):
        adapter = getattr(simple_formation, "local_vehicles", None)
        point_lane = getattr(simple_formation, "lane_index", None)
        self.assertTrue(callable(adapter), "local observation adapter is missing")
        self.assertTrue(callable(point_lane), "lane point classifier is missing")
        if adapter is None or point_lane is None:
            return
        centered = self.neighbor(1, 10.0, 0)
        straddling = self.neighbor(2, 12.0, 0, relative_y=1.65)
        outside = self.neighbor(3, 100.0, 0)
        local_road = SimpleNamespace(
            centers_m=CENTERS_M,
            envelope=SimpleNamespace(regions=((0.0, 150.0, 0.0, 9.9),)),
        )
        rows = adapter(
            self.control(neighbors=(centered, straddling, outside)),
            local_road,
            self.p,
        )
        self.assertEqual([row.lane_index for row in rows], [0, None, None])
        tolerance = self.p["noa_geometry_tolerance_m"]
        self.assertIsNone(point_lane(3.3, CENTERS_M, tolerance))
        self.assertIsNone(point_lane(-2.0, CENTERS_M, tolerance))

    def test_simple_diagnostics_exclude_complex_candidate_and_game_fields(self):
        with patch("noa.controller.verify_candidate", return_value=SAFE):
            diagnostic = decide(
                self.control(neighbors=(self.neighbor(1, 40.0, 1),)), self.p
            ).diagnostics["simple_formation"]
        forbidden = {
            "candidate_evaluations",
            "candidate_geometry",
            "candidate_rejections",
            "rank_keys",
            "scores",
            "games",
            "random_draws",
            "weights",
            "lattices",
        }
        self.assertFalse(forbidden.intersection(diagnostic))

    def test_simple_source_has_no_hidden_truth_or_external_state_access(self):
        root = Path(__file__).resolve().parents[1]
        for relative in ("noa/simple_formation.py", "noa/controller.py"):
            source = ast.parse((root / relative).read_text(encoding="utf-8"))
            for node in ast.walk(source):
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, {"hidden_type", "future_plan", "truth_id"})
                if isinstance(node, ast.ImportFrom) and relative.endswith("simple_formation.py"):
                    self.assertNotIn(
                        (node.module or "").split(".")[0],
                        {"simulation", "experiments", "research", "traci"},
                    )

    def test_simple_switch_is_exact_boolean_and_wrong_memory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SimpleFormationMemory"):
            decide(self.control(memory=NoaMemory((), "CRUISE")), self.p)

        disabled = {**self.p, "simple_formation_enabled": 1,
                    "formation_lane_change_enabled": False}
        control = self.control(memory=NoaMemory((), "CRUISE"))
        baseline = decide(
            control,
            {**disabled, "phase5g_enabled": False, "formation_enabled": False},
        )
        self.assertEqual(decide(control, disabled), baseline)

    def test_clock_restores_simple_private_fields_without_a_rng_seed(self):
        signature = inspect.signature(restore_initial_memories)
        self.assertIn("simple_enabled", signature.parameters)
        if "simple_enabled" not in signature.parameters:
            return
        original = SimpleFormationMemory(
            (), "CRUISE", reference_track_id=17, join_anchor_track_id=7,
            desired_lane_index=2, join_phase="JOINING"
        )
        restored = restore_initial_memories(
            {"ego": asdict(original)},
            ("ego",),
            formation_enabled=True,
            lane_priority_enabled=True,
            simple_enabled=True,
        )
        self.assertEqual(restored["ego"], original)
        self.assertNotIn("formation_lane_rng_state", asdict(restored["ego"]))

    def test_clock_accepts_old_noa_checkpoint_as_neutral_simple_memory(self):
        signature = inspect.signature(restore_initial_memories)
        self.assertIn("simple_enabled", signature.parameters)
        if "simple_enabled" not in signature.parameters:
            return
        restored = restore_initial_memories(
            {"ego": json.loads(json.dumps(asdict(NoaMemory((), "CRUISE"))))},
            ("ego",),
            formation_enabled=True,
            lane_priority_enabled=True,
            simple_enabled=True,
        )["ego"]
        self.assertIsInstance(restored, SimpleFormationMemory)
        self.assertIsNone(restored.reference_track_id)
        self.assertIsNone(restored.join_anchor_track_id)
        self.assertEqual(restored.join_phase, "FREE")

    def test_clock_simple_path_bypasses_formation_wrapper_and_false_uses_it(self):
        clock = object.__new__(Phase5GClock)
        clock.policy = {"simple_formation_enabled": True}
        control = self.control()
        sentinel = object()
        with patch("simulation.phase5g_clock.noa_decide", return_value=sentinel,
                   create=True) as direct, patch(
            "simulation.formation_clock.decide",
            side_effect=AssertionError("legacy wrapper entered"),
        ) as legacy:
            self.assertIs(clock._decide(control), sentinel)
        direct.assert_called_once_with(control, clock.policy)
        legacy.assert_not_called()

        clock.policy = {"simple_formation_enabled": False}
        with patch("simulation.formation_clock.decide", return_value=sentinel) as legacy:
            self.assertIs(clock._decide(control), sentinel)
        legacy.assert_called_once_with(control, clock.policy)

    def test_clock_requires_explicit_boolean_simple_switch(self):
        initial = {"ego": VehicleState(x_m=100.0, y_m=CENTERS_M[0], vx_mps=20.0)}
        road = VisibleRoad(
            (((0.0, 0.0), (1000.0, 0.0)), ((0.0, 9.9), (1000.0, 9.9))),
            (((0.0, 3.3), (1000.0, 3.3)), ((0.0, 6.6), (1000.0, 6.6))),
        )
        physical = {
            **self.model.p,
            **settings("phase3"),
            "formation_enabled": True,
            "communication_enabled": False,
            "phase5g_enabled": True,
            "formation_lane_change_enabled": True,
            "r5_enabled": False,
            "simple_formation_enabled": 1,
        }
        policy = {**self.p, "simple_formation_enabled": 1}
        raw = {"ego": asdict(SimpleFormationMemory((), "CRUISE"))}
        with self.assertRaisesRegex(ValueError, "simple_formation_enabled"):
            Phase5GClock(
                initial,
                self.model,
                road,
                physical,
                policy,
                ("ego",),
                {},
                raw,
                clock_schema=CLOCK_SCHEMA,
                initial_memories_sha256=initial_memory_hash(raw),
            )


if __name__ == "__main__":
    unittest.main()
