"""Phase 5F finite adaptive-duration and controller contracts."""

from dataclasses import replace
import math
import unittest
from unittest.mock import patch

from experiments.phase5_r5 import parameters
import test_phase5_r5_controller as fixtures
from models.bezier import QuadraticLaneChange
from noa.controller import decide
from noa.low_speed import (
    candidate_profiles,
    peak_reference_lateral_accel,
    steering_speed_floor,
    validated_durations,
)
from noa.road import reconstruct
from research.common import settings


class Phase5FLowSpeedMathTests(unittest.TestCase):
    def setUp(self):
        _, _, self.p = parameters(True)
        self.p = {**self.p, "phase5f_duration_candidates_s": [5.0, 7.5, 10.0]}

    def test_registered_duration_set_and_exact_derived_boundaries(self):
        self.assertEqual(validated_durations(self.p), (5.0, 7.5, 10.0))
        expected = (
            (5.0, 0.528, 1.3034431025565734),
            (7.5, 0.23466666666666666, 0.8689620683710490),
            (10.0, 0.132, 0.6517215512782867),
        )
        for duration, peak, floor in expected:
            with self.subTest(duration=duration):
                self.assertAlmostEqual(peak_reference_lateral_accel(duration, self.p), peak, places=15)
                self.assertAlmostEqual(steering_speed_floor(duration, self.p), floor, places=15)
                self.assertLessEqual(peak, self.p["comfort_lateral_accel_mps2"])

    def test_real_low_speeds_return_only_model_admissible_profiles(self):
        for speed in (1.7, 1.85, 4.511, 5.0):
            with self.subTest(speed=speed):
                profiles = candidate_profiles(speed, self.p)
                self.assertEqual([item["duration_s"] for item in profiles], [5.0, 7.5, 10.0])
                self.assertTrue(all(speed >= item["speed_floor_mps"] for item in profiles))
        self.assertEqual(candidate_profiles(0.65, self.p), [])
        self.assertEqual(candidate_profiles(0.0, self.p), [])

    def test_each_duration_enters_at_its_exact_floor_without_tolerance(self):
        for duration in validated_durations(self.p):
            floor = steering_speed_floor(duration, self.p)
            exact = candidate_profiles(floor, self.p)
            below = candidate_profiles(math.nextafter(floor, 0.0), self.p)
            self.assertIn(duration, [item["duration_s"] for item in exact])
            self.assertNotIn(duration, [item["duration_s"] for item in below])

    def test_invalid_or_uncomfortable_duration_sets_are_rejected_or_filtered(self):
        for values in ([], [5.0, 5.0], [7.5, 5.0], [0.0, 5.0], [5.0, float("inf")], "5,7.5,10"):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validated_durations({**self.p, "phase5f_duration_candidates_s": values})
        uncomfortable = {**self.p, "comfort_lateral_accel_mps2": 0.2}
        self.assertEqual(
            [item["duration_s"] for item in candidate_profiles(5.0, uncomfortable)],
            [10.0],
        )


class Phase5FControllerTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.R5Tests()
        self.f.setUp()
        self.base = {**self.f.p, "r5_lane_priority_enabled": True}
        self.p = {**self.base, **settings("phase5f"), "phase5f_enabled": True}

    def low_control(self, speed=1.7, time_s=0.0, memory=None):
        return self.f.control(
            t=time_s,
            speed=speed,
            y=1.65,
            memory=memory,
            # Motivating lead remains outside even the 10 s R5 competition
            # radius, so these tests isolate duration/guard selection.
            neighbors=((26.0, 1.65, 0.0, 0.0),),
        )

    @staticmethod
    def guard_by_duration(_control, plan, _road, _acceleration, _parameters):
        safe = plan.duration_s == 7.5
        return {
            "safe": safe,
            "reason": "unit_safe_7p5" if safe else "unit_reject_duration",
            "at_s": None if safe else 0.1,
            "checked_s": plan.duration_s + 0.5 if safe else 0.1,
        }

    def test_low_speed_checks_durations_in_order_and_commits_shortest_safe(self):
        with patch("noa.controller.verify_candidate", side_effect=self.guard_by_duration) as guard:
            first = decide(self.low_control(), self.p)
            second = decide(self.low_control(time_s=0.5, memory=first.memory), self.p)
        self.assertEqual([call.args[1].duration_s for call in guard.call_args_list], [5.0, 7.5, 5.0, 7.5])
        self.assertEqual(first.memory.own_behavior, "PREPARE_LC")
        self.assertEqual(second.memory.own_behavior, "EXECUTE_LC")
        self.assertIsNotNone(second.memory.plan)
        self.assertEqual(second.memory.plan.duration_s, 7.5)
        self.assertEqual(second.memory.plan.speed_mps, 1.7)
        self.assertEqual(
            [item["duration_s"] for item in second.diagnostics["candidate_evaluations"]],
            [5.0, 7.5],
        )
        self.assertEqual(second.diagnostics["selected_candidate_duration_s"], 7.5)

    def test_every_admissible_duration_rejection_preserves_no_plan(self):
        rejected = {
            "safe": False, "reason": "unit_all_rejected", "at_s": 0.1, "checked_s": 0.1,
        }
        with patch("noa.controller.verify_candidate", return_value=rejected) as guard:
            decision = decide(self.low_control(speed=1.85), self.p)
        self.assertEqual([call.args[1].duration_s for call in guard.call_args_list], [5.0, 7.5, 10.0])
        self.assertIsNone(decision.memory.plan)
        self.assertIsNone(decision.memory.prepare_since_s)
        self.assertEqual(
            [item["guard"]["reason"] for item in decision.diagnostics["candidate_evaluations"]],
            ["unit_all_rejected"] * 3,
        )

    def test_real_1p7_and_1p85_speeds_reach_guard_with_measured_plan_speed(self):
        accepted = {
            "safe": True, "reason": "unit_accept", "at_s": None, "checked_s": 5.5,
        }
        for speed in (1.7, 1.85):
            with self.subTest(speed=speed), patch(
                "noa.controller.verify_candidate", return_value=accepted
            ) as guard:
                decision = decide(self.low_control(speed=speed), self.p)
                self.assertGreater(guard.call_count, 0)
                self.assertEqual(guard.call_args.args[1].speed_mps, speed)
                self.assertEqual(decision.memory.own_behavior, "PREPARE_LC")

    def test_zero_and_below_all_floors_do_not_reach_guard_or_prepare(self):
        with patch("noa.controller.verify_candidate") as guard:
            stopped = decide(self.low_control(speed=0.0), self.p)
            below = decide(self.f.control(
                speed=0.65, y=1.65, neighbors=((8.0, 1.65, 0.0, 0.0),)
            ), self.p)
        guard.assert_not_called()
        for decision in (stopped, below):
            self.assertIsNone(decision.memory.plan)
            self.assertIsNone(decision.memory.prepare_since_s)
        self.assertEqual(stopped.diagnostics.get("candidate_evaluations", []), [])
        self.assertEqual(
            [item["duration_s"] for item in below.diagnostics["candidate_evaluations"]],
            [5.0, 7.5, 10.0],
        )
        self.assertTrue(
            all(not item["model_admissible"]
                for item in below.diagnostics["candidate_evaluations"])
        )

    def test_fixed_r5_off_and_priority_off_paths_equal_phase5e_behavior(self):
        fixed = {**self.p, "phase5f_enabled": False}
        for current in (
            fixed,
            {**self.p, "r5_enabled": False},
            {**self.p, "r5_lane_priority_enabled": False},
        ):
            legacy = {k: value for k, value in current.items() if not k.startswith("phase5f_")}
            control = self.low_control(speed=4.9)
            with self.subTest(enabled=current.get("r5_enabled"), lane=current.get("r5_lane_priority_enabled")):
                self.assertEqual(decide(control, current), decide(control, legacy))

    def test_r5_relative_speed_radius_uses_candidate_duration(self):
        control = self.f.control(
            speed=1.7, y=1.65, neighbors=((50.0, 8.25, 8.0, 0.0),)
        )
        road = reconstruct(control.ego, control.observation.road, self.p)
        short = QuadraticLaneChange(0.0, 1.65, 4.95, 5.0, 1.7)
        long = replace(short, duration_s=10.0)
        from noa import r5
        short_assessment = r5.assess_candidate(control, road, short, control.memory, self.p)
        long_assessment = r5.assess_candidate(control, road, long, control.memory, self.p)
        self.assertEqual(short_assessment["participant_signatures"], ())
        self.assertEqual(len(long_assessment["participant_signatures"]), 1)
        self.assertEqual(long_assessment["reason"], "yield_visible_upper_lane")


if __name__ == "__main__":
    unittest.main()
