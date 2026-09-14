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
from models.vehicle import VehicleState
from noa import simple_formation
from noa.contracts import NoaMemory
from noa.controller import decide
from noa.simple_formation import SimpleFormationMemory
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
            "simple_formation_local_range_m": 90.0,
            "simple_formation_adjacent_gap_m": 15.0,
            "simple_formation_same_gap_m": 30.0,
            "simple_formation_position_tolerance_m": 2.0,
            "simple_formation_accel_limit_mps2": 0.5,
            "simple_formation_max_lane_changes": 1,
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

    def test_no_reference_keeps_base_cruise_and_clears_private_reference(self):
        side = self.neighbor(4, 0.0, 1)
        control = self.control(
            neighbors=(side,),
            memory=SimpleFormationMemory((), "CRUISE", reference_track_id=19)
        )
        baseline = decide(
            replace(control, memory=NoaMemory((), "CRUISE")),
            {
                **self.p,
                "formation_enabled": False,
                "simple_formation_enabled": False,
                "formation_lane_change_enabled": False,
            },
        )
        decision = decide(control, self.p)
        self.assertEqual(decision.action, baseline.action)
        self.assertIsNone(decision.memory.reference_track_id)
        self.assertEqual(
            decision.diagnostics["simple_formation"]["reference_reason"],
            "no_visible_reference",
        )

    def test_adjacent_reference_uses_fifteen_metres_and_bounded_increment(self):
        reference = self.neighbor(7, 40.0, 1)
        with patch("noa.controller.verify_candidate", return_value=SAFE) as guard:
            decision = decide(self.control(neighbors=(reference,)), self.p)
        diagnostic = decision.diagnostics["simple_formation"]
        self.assertEqual(diagnostic["reference_track_id"], 7)
        self.assertEqual(diagnostic["desired_gap_m"], 15.0)
        self.assertEqual(diagnostic["raw_increment_mps2"], 0.5)
        self.assertLessEqual(abs(diagnostic["applied_increment_mps2"]), 0.5)
        self.assertEqual(decision.action.acceleration_mps2, 0.5)
        hold = guard.call_args.args[1]
        self.assertEqual(hold.y_start_m, hold.y_target_m)

    def test_unique_less_populated_lane_creates_one_fixed_safe_plan(self):
        neighbors = (
            self.neighbor(1, 70.0, 0),
            self.neighbor(2, 80.0, 0),
        )
        with patch("noa.controller.verify_candidate", return_value=SAFE) as guard:
            decision = decide(self.control(neighbors=neighbors), self.p)
        self.assertGreaterEqual(guard.call_count, 1)
        self.assertIsNotNone(decision.memory.plan)
        self.assertAlmostEqual(decision.memory.plan.y_target_m, CENTERS_M[1])
        self.assertEqual(decision.memory.plan.duration_s, self.p["noa_lane_change_duration_s"])
        self.assertEqual(decision.memory.lane_change_reason, "simple_formation_balance")
        self.assertEqual(decision.memory.own_behavior, "EXECUTE_LC")
        self.assertEqual(
            decision.diagnostics["simple_formation"]["lane_reason"],
            "simple_formation_balance",
        )

    def test_lane_guard_rejection_keeps_certified_longitudinal_request(self):
        neighbors = (
            self.neighbor(1, 70.0, 0),
            self.neighbor(2, 80.0, 0),
        )
        with patch(
            "noa.controller.verify_candidate", side_effect=(SAFE, REJECTED)
        ) as guard:
            decision = decide(self.control(neighbors=neighbors), self.p)
        self.assertEqual(guard.call_count, 2)
        self.assertIsNone(decision.memory.plan)
        self.assertEqual(
            decision.diagnostics["simple_formation"]["applied_increment_mps2"],
            0.5,
        )
        self.assertEqual(
            decision.action.acceleration_mps2,
            guard.call_args_list[1].args[3],
        )
        self.assertEqual(
            decision.diagnostics["simple_formation"]["lane_reason"],
            "safety_rejected",
        )
        self.assertEqual(
            decision.diagnostics["simple_formation"]["guard"]["kind"],
            "lane_change",
        )

    def test_completed_simple_plan_sets_done_and_blocks_a_second_request(self):
        duration = self.p["noa_lane_change_duration_s"]
        plan = QuadraticLaneChange(0.0, CENTERS_M[0], CENTERS_M[1], duration, 20.0)
        executing = SimpleFormationMemory(
            (),
            "EXECUTE_LC",
            plan=plan,
            target_y_m=CENTERS_M[1],
            prepare_since_s=0.0,
            lane_change_reason="simple_formation_balance",
        )
        completed = decide(
            self.control(time_s=duration, x=200.0, lane=1, memory=executing), self.p
        )
        self.assertTrue(completed.memory.formation_lane_change_done)
        self.assertIsNone(completed.memory.plan)
        self.assertEqual(completed.memory.completed_lane_changes, 1)

        later_time = duration + self.p["noa_lane_change_cooldown_s"] + 0.1
        imbalance = (
            self.neighbor(11, 70.0, 1, time_s=later_time, relative_y=0.0),
            self.neighbor(12, 80.0, 1, time_s=later_time, relative_y=0.0),
        )
        with patch("noa.controller.verify_candidate", return_value=SAFE):
            blocked = decide(
                self.control(
                    time_s=later_time,
                    x=300.0,
                    lane=1,
                    neighbors=imbalance,
                    memory=completed.memory,
                ),
                self.p,
            )
        self.assertIsNone(blocked.memory.plan)
        self.assertEqual(
            blocked.diagnostics["simple_formation"]["lane_reason"],
            "formation_lane_change_done",
        )

    def test_active_plan_is_rechecked_but_never_retargeted(self):
        plan = QuadraticLaneChange(0.0, CENTERS_M[0], CENTERS_M[1], 5.0, 20.0)
        memory = SimpleFormationMemory(
            (),
            "EXECUTE_LC",
            plan=plan,
            target_y_m=CENTERS_M[1],
            prepare_since_s=0.0,
            lane_change_reason="simple_formation_balance",
        )
        with patch("noa.controller.verify_candidate", return_value=SAFE), patch(
            "noa.controller.simple_formation.choose_lane",
            side_effect=AssertionError("active plan was retargeted"),
        ) as choose:
            decision = decide(
                self.control(time_s=1.0, x=120.0, lane=0, memory=memory), self.p
            )
        choose.assert_not_called()
        self.assertEqual(decision.memory.plan, plan)
        self.assertEqual(decision.memory.own_behavior, "EXECUTE_LC")

    def test_emergency_and_base_overtake_motivation_preempt_simple_rules(self):
        close = self.neighbor(3, 8.0, 0, speed=0.0)
        with patch(
            "noa.controller.simple_formation.local_vehicles",
            side_effect=AssertionError("simple branch ran during emergency"),
            create=True,
        ):
            emergency = decide(self.control(neighbors=(close,)), self.p)
        self.assertEqual(emergency.memory.own_behavior, "EMERGENCY")

        slow = self.neighbor(4, 70.0, 0, speed=10.0)
        with patch("noa.controller.verify_candidate", return_value=SAFE), patch(
            "noa.controller.simple_formation.local_vehicles",
            side_effect=AssertionError("simple branch ran during base motivation"),
            create=True,
        ):
            overtake = decide(self.control(neighbors=(slow,)), self.p)
        self.assertEqual(overtake.memory.lane_change_reason, "slower_visible_lead")
        self.assertEqual(overtake.memory.own_behavior, "PREPARE_LC")

    def test_consistent_local_track_relabel_preserves_physical_action(self):
        first = (
            self.neighbor(7, 50.0, 0),
            self.neighbor(8, 20.0, 1),
        )
        second = tuple(replace(row, track_id=row.track_id + 100) for row in first)
        with patch("noa.controller.verify_candidate", return_value=SAFE):
            a = decide(
                self.control(
                    neighbors=first,
                    memory=SimpleFormationMemory((), "CRUISE", reference_track_id=7),
                ),
                self.p,
            )
            b = decide(
                self.control(
                    neighbors=second,
                    memory=SimpleFormationMemory((), "CRUISE", reference_track_id=107),
                ),
                self.p,
            )
        self.assertEqual(a.action, b.action)

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
            (), "CRUISE", reference_track_id=17, formation_lane_change_done=True
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
        self.assertFalse(restored.formation_lane_change_done)

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
