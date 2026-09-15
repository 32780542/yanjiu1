"""TDD contracts for Phase 5G local-priority formation lane changes."""

from dataclasses import asdict, fields, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from noa.contracts import NoaMemory
from noa.formation import FormationMemory, decide, memory_from_dict
from noa.formation_lane import draw_uniform
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.road import VisibleRoad
from research.common import settings


CENTERS_M = (1.65, 4.95, 8.25)
TRACKED_BASELINE_FILES = ("tests/baselines/phase5f_controller.py",)
PHASE5F_CONTROLLER_SHA256 = (
    "76c64c73fb673849db196448a0ecf9b3142ab8206b7433949cad777c1e83a2e3"
)
SAFE = {
    "safe": True,
    "reason": "unit_guard_accept",
    "at_s": None,
    "checked_s": 10.5,
}
REJECTED = {
    "safe": False,
    "reason": "unit_guard_reject",
    "at_s": 0.1,
    "checked_s": 0.1,
}


def road() -> VisibleRoad:
    return VisibleRoad(
        (((-300.0, 0.0), (2000.0, 0.0)), ((-300.0, 9.9), (2000.0, 9.9))),
        (
            ((-300.0, 3.3), (2000.0, 3.3)),
            ((-300.0, 6.6), (2000.0, 6.6)),
        ),
    )


class Phase5GControllerTests(unittest.TestCase):
    def setUp(self):
        self.model = KinematicModel.from_config()
        phase5g_path = Path(__file__).resolve().parents[1] / "configs" / "phase5g.json"
        phase5g = json.loads(phase5g_path.read_text(encoding="utf-8"))
        self.p = {
            **self.model.p,
            **settings("phase4"),
            **settings("phase5"),
            **phase5g,
            "formation_enabled": True,
            "noa_target_speed_mps": 10.0,
            "r5_enabled": False,
            "phase5f_enabled": False,
        }

    def memory(self, **changes) -> FormationMemory:
        return replace(
            FormationMemory((), "CRUISE", formation_lane_rng_state=0x123456789ABCDEF0),
            **changes,
        )

    def control(
        self,
        time_s=0.0,
        *,
        ego_lane=1,
        memory=None,
        neighbors=((42.0, 0, 10.0, 0.0), (27.0, 1, 10.0, 0.0)),
        speed_mps=10.0,
    ):
        ego = VehicleState(
            time_s=time_s,
            x_m=100.0 + speed_mps * time_s,
            y_m=CENTERS_M[ego_lane],
            vx_mps=speed_mps,
        )
        truth = tuple(
            TruthVehicle(
                f"sensor-label-{index}",
                VehicleState(
                    time_s=time_s,
                    x_m=ego.x_m + relative_x_m,
                    y_m=CENTERS_M[lane],
                    vx_mps=neighbor_speed_mps,
                    vy_mps=neighbor_vy_mps,
                ),
                4.5,
                1.8,
            )
            for index, (relative_x_m, lane, neighbor_speed_mps, neighbor_vy_mps) in enumerate(neighbors)
        )
        sensor = IdealSensor({**self.model.p, **settings("phase3")}, road())
        sampled = sensor.sample(
            "ego-sensor-label",
            WorldFrame((TruthVehicle("ego-sensor-label", ego, 4.5, 1.8),) + truth),
        )
        return replace(sampled, memory=memory or self.memory())

    @staticmethod
    def duration_guard(_control, plan, _road, _acceleration, _parameters):
        return SAFE if plan.duration_s == 7.5 else REJECTED

    def step(self, time_s, memory, *, neighbors=None, guard=None, ego_lane=1):
        kwargs = {} if neighbors is None else {"neighbors": neighbors}
        lane_guard = guard or self.duration_guard
        with patch("noa.controller.verify_candidate", side_effect=lane_guard), patch(
            "noa.formation.verify_candidate", return_value=SAFE
        ):
            return decide(
                self.control(time_s, memory=memory, ego_lane=ego_lane, **kwargs),
                self.p,
            )

    def test_memory_adds_only_six_phase5g_fields_and_json_round_trips(self):
        phase5g_names = {
            field.name for field in fields(FormationMemory)
            if field.name.startswith("formation_lane_")
        }
        self.assertEqual(
            phase5g_names,
            {
                "formation_lane_signature",
                "formation_lane_since_s",
                "formation_lane_lock_until_s",
                "formation_lane_rng_state",
                "formation_lane_draw_count",
                "formation_lane_backoff_until_s",
            },
        )
        value = self.memory(
            formation_lane_signature=(0, 127.0, 4.95, 10.0, 0.0, 0.0, 4.5, 1.8),
            formation_lane_since_s=1.0,
            formation_lane_lock_until_s=9.0,
            formation_lane_rng_state=2**64 - 1,
            formation_lane_draw_count=3,
            formation_lane_backoff_until_s=2.0,
        )
        encoded = json.loads(json.dumps(asdict(value), allow_nan=False))
        self.assertEqual(memory_from_dict(encoded), value)

    def test_memory_rejects_invalid_phase5g_fields(self):
        invalid = (
            {"formation_lane_since_s": float("nan")},
            {"formation_lane_lock_until_s": -0.1},
            {"formation_lane_backoff_until_s": True},
            {"formation_lane_rng_state": True},
            {"formation_lane_rng_state": -1},
            {"formation_lane_rng_state": 2**64},
            {"formation_lane_draw_count": True},
            {"formation_lane_draw_count": -1},
            {"formation_lane_signature": [0, 127.0, 4.95, 10.0, 0.0, 0.0, 4.5, 1.8]},
            {"formation_lane_signature": (-1, 127.0, 4.95, 10.0, 0.0, 0.0, 4.5, 1.8)},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.memory(**changes)

    def test_memory_rejects_inconsistent_candidate_episode_before_base_controller(self):
        signature = (0, 127.0, 4.95, 10.0, 0.0, 0.0, 4.5, 1.8)
        invalid = (
            {"formation_lane_signature": signature},
            {"formation_lane_since_s": 1.0},
            {
                "formation_lane_backoff_until_s": 2.0,
                "formation_lane_draw_count": 1,
            },
            {
                "formation_lane_signature": signature,
                "formation_lane_since_s": 1.0,
                "formation_lane_backoff_until_s": 1.0,
                "formation_lane_draw_count": 1,
            },
            {
                "formation_lane_signature": signature,
                "formation_lane_since_s": 1.0,
                "formation_lane_backoff_until_s": 2.0,
                "formation_lane_draw_count": 0,
            },
        )
        for changes in invalid:
            with self.subTest(source="direct", changes=changes), self.assertRaisesRegex(
                ValueError, "Phase 5G"
            ):
                self.memory(**changes)

            encoded = asdict(self.memory())
            encoded.update(changes)
            with self.subTest(source="json", changes=changes), self.assertRaisesRegex(
                ValueError, "Phase 5G"
            ):
                memory_from_dict(json.loads(json.dumps(encoded, allow_nan=False)))

        future_episode = self.memory(
            formation_lane_signature=signature,
            formation_lane_since_s=1.0,
        )
        with patch(
            "noa.formation.noa_decide",
            side_effect=AssertionError("invalid Phase 5G memory entered base controller"),
        ) as base_decide, self.assertRaisesRegex(ValueError, "Phase 5G"):
            decide(self.control(time_s=0.0, memory=future_episode), self.p)
        base_decide.assert_not_called()

    def test_old_checkpoint_without_phase5g_fields_restores_neutral_defaults(self):
        neutral = FormationMemory((), "CRUISE")
        encoded = asdict(neutral)
        for name in (
            "formation_lane_signature",
            "formation_lane_since_s",
            "formation_lane_lock_until_s",
            "formation_lane_rng_state",
            "formation_lane_draw_count",
            "formation_lane_backoff_until_s",
        ):
            encoded.pop(name)
        self.assertEqual(
            memory_from_dict(json.loads(json.dumps(encoded, allow_nan=False))),
            neutral,
        )

        ended_episode = self.memory(formation_lane_draw_count=3)
        self.assertEqual(
            memory_from_dict(json.loads(json.dumps(asdict(ended_episode), allow_nan=False))),
            ended_episode,
        )

    def test_private_splitmix64_draw_matches_registered_word_and_full_interval(self):
        state, word, unit = draw_uniform(0)
        self.assertEqual(state, 11400714819323198485)
        self.assertEqual(word, 16294208416658607535)
        self.assertEqual(unit, word / float(1 << 64))

    def test_continuously_moving_candidate_accumulates_one_second_then_prepares(self):
        memory = self.memory()
        first = self.step(0.0, memory)
        decision = first
        middle = None
        for tick in range(1, 11):
            decision = self.step(tick / 10.0, decision.memory)
            if tick == 5:
                middle = decision
        ready = decision

        self.assertEqual(first.memory.formation_lane_since_s, 0.0)
        self.assertEqual(middle.memory.formation_lane_since_s, 0.0)
        self.assertEqual(ready.memory.own_behavior, "PREPARE_LC")
        self.assertEqual(ready.memory.lane_change_reason, "formation_geometry")
        self.assertIsNone(ready.memory.plan)
        self.assertEqual(ready.diagnostics["formation_lane"]["selected_duration_s"], 7.5)
        self.assertTrue(ready.diagnostics["formation_lane"]["candidate_geometry"])
        self.assertEqual(
            [row["duration_s"] for row in ready.diagnostics["formation_lane"]["duration_guards"]],
            [5.0, 7.5],
        )

        committed = ready
        for tick in range(11, 16):
            committed = self.step(tick / 10.0, committed.memory)
        self.assertEqual(committed.memory.own_behavior, "EXECUTE_LC")
        self.assertIsNotNone(committed.memory.plan)
        self.assertEqual(committed.memory.plan.duration_s, 7.5)
        self.assertEqual(committed.memory.plan.speed_mps, 10.0)

    def test_genuinely_changed_reference_resets_candidate_timer(self):
        first = self.step(0.0, self.memory())
        previous = first
        for tick in range(1, 5):
            previous = self.step(tick / 10.0, previous.memory)
        changed = self.step(
            0.5,
            previous.memory,
            neighbors=((60.0, 0, 10.0, 0.0), (45.0, 1, 10.0, 0.0)),
        )
        self.assertEqual(changed.memory.formation_lane_since_s, 0.5)
        self.assertEqual(changed.diagnostics["formation_lane"]["candidate_timer"]["association"], "new")
        self.assertNotEqual(
            changed.memory.formation_lane_signature,
            first.memory.formation_lane_signature,
        )

    def test_candidate_reference_in_adjacent_source_lane_must_yield_when_moving_inward(self):
        decision = self.step(
            0.0,
            self.memory(),
            neighbors=((42.0, 0, 10.0, 0.0), (27.0, 1, 10.0, 1.0)),
        )
        lane = decision.diagnostics["formation_lane"]
        self.assertTrue(lane["candidate_geometry"])
        self.assertEqual(lane["priority_reason"], "yield_visible_inward_motion")
        self.assertTrue(lane["priority"]["blocking"])
        self.assertNotEqual(lane["priority_reason"], "no_potential_competition")

    def test_ambiguous_episode_draws_once_while_unambiguous_priority_never_draws(self):
        ambiguous_neighbors = (
            (42.0, 1, 10.0, 0.0),
            (27.0, 0, 10.0, 0.0),
            (6.0, 2, 10.0, 0.0),
            (-6.0, 2, 10.0, 0.0),
        )
        first = self.step(0.0, self.memory(), neighbors=ambiguous_neighbors, ego_lane=0)
        self.assertEqual(first.memory.formation_lane_draw_count, 1)
        self.assertEqual(first.diagnostics["formation_lane"]["backoff"]["draws_this_tick"], 1)
        persistent = first
        for tick in range(1, 26):
            persistent = self.step(
                tick / 10.0,
                persistent.memory,
                neighbors=ambiguous_neighbors,
                ego_lane=0,
            )
            with self.subTest(ambiguous_tick=tick):
                self.assertEqual(persistent.memory.formation_lane_draw_count, 1)
                self.assertEqual(
                    persistent.diagnostics["formation_lane"]["backoff"]["draws_this_tick"],
                    0,
                )

        unambiguous_neighbors = (
            (42.0, 1, 10.0, 0.0),
            (27.0, 0, 10.0, 0.0),
            (6.0, 2, 10.0, 0.0),
        )
        unambiguous = self.step(
            0.0, self.memory(), neighbors=unambiguous_neighbors, ego_lane=0
        )
        self.assertEqual(unambiguous.memory.formation_lane_draw_count, 0)
        self.assertEqual(
            unambiguous.diagnostics["formation_lane"]["priority_reason"],
            "yield_visible_front",
        )

    def test_every_guard_rejection_preserves_no_plan(self):
        memory = self.memory()
        rejected = None
        for tick in range(21):
            rejected = self.step(tick / 10.0, memory, guard=lambda *_: REJECTED)
            memory = rejected.memory
            with self.subTest(rejected_tick=tick):
                self.assertNotEqual(rejected.memory.own_behavior, "PREPARE_LC")
                self.assertIsNone(rejected.memory.target_y_m)
                self.assertNotEqual(rejected.memory.lane_change_reason, "formation_geometry")
                self.assertIsNone(rejected.memory.plan)
                if tick >= 10:
                    self.assertEqual(
                        [
                            row["guard"]["safe"]
                            for row in rejected.diagnostics["formation_lane"]["duration_guards"]
                        ],
                        [False, False, False],
                    )
        self.assertIsNone(rejected.memory.plan)
        self.assertNotEqual(rejected.memory.own_behavior, "EXECUTE_LC")
        self.assertEqual(
            [row["guard"]["safe"] for row in rejected.diagnostics["formation_lane"]["duration_guards"]],
            [False, False, False],
        )
        self.assertEqual(rejected.diagnostics["formation_lane"]["fallback"], "all_guards_rejected")

    def test_real_guard_rejects_visible_target_corridor_conflict_without_a_plan(self):
        memory = self.memory()
        decision = None
        neighbors = (
            (42.0, 0, 10.0, 0.0),
            (27.0, 1, 10.0, 0.0),
            (8.0, 2, 10.0, 0.0),
        )
        for tick in range(11):
            decision = decide(
                self.control(tick / 10.0, memory=memory, neighbors=neighbors),
                self.p,
            )
            memory = decision.memory
        lane = decision.diagnostics["formation_lane"]
        self.assertTrue(lane["candidate_geometry"])
        self.assertTrue(lane["duration_guards"])
        self.assertEqual(
            [row["duration_s"] for row in lane["duration_guards"]],
            [5.0, 7.5, 10.0],
        )
        self.assertTrue(all(row["guard"]["safe"] is False for row in lane["duration_guards"]))
        self.assertEqual(lane["fallback"], "all_guards_rejected")
        self.assertIsNone(decision.memory.plan)

    def test_completion_sets_five_second_lock_and_blocks_reverse_candidate(self):
        decision = self.step(0.0, self.memory())
        self.assertIsNone(decision.memory.formation_lane_lock_until_s)
        for tick in range(1, 11):
            decision = self.step(tick / 10.0, decision.memory)
            self.assertIsNone(decision.memory.formation_lane_lock_until_s)
        prepared = decision
        self.assertEqual(prepared.memory.own_behavior, "PREPARE_LC")
        self.assertIsNone(prepared.memory.plan)

        for tick in range(11, 16):
            decision = self.step(tick / 10.0, decision.memory)
            self.assertIsNone(decision.memory.formation_lane_lock_until_s)
            if tick < 15:
                self.assertEqual(decision.memory.own_behavior, "PREPARE_LC")
        executing = decision
        self.assertEqual(executing.memory.own_behavior, "EXECUTE_LC")
        self.assertIsNotNone(executing.memory.plan)
        self.assertIsNone(executing.memory.formation_lane_lock_until_s)

        not_completed = self.step(1.6, executing.memory)
        self.assertEqual(not_completed.memory.own_behavior, "EXECUTE_LC")
        self.assertIsNotNone(not_completed.memory.plan)
        self.assertIsNone(not_completed.memory.formation_lane_lock_until_s)
        self.assertEqual(
            not_completed.diagnostics["formation_lane"]["fallback"],
            "active_plan",
        )

        plan = not_completed.memory.plan
        completion_time = plan.start_s + plan.duration_s
        target_lane = min(
            range(len(CENTERS_M)),
            key=lambda lane: abs(CENTERS_M[lane] - plan.y_target_m),
        )
        completed = self.step(
            completion_time,
            not_completed.memory,
            ego_lane=target_lane,
            neighbors=(),
        )
        self.assertAlmostEqual(
            completed.memory.formation_lane_lock_until_s,
            completion_time + self.p["formation_lane_lock_s"],
        )
        self.assertEqual(completed.memory.completed_lane_changes, 1)

        reverse = self.step(
            completion_time + 0.1,
            completed.memory,
            ego_lane=target_lane,
            neighbors=((42.0, 1, 10.0, 0.0), (27.0, target_lane, 10.0, 0.0)),
        )
        self.assertIsNone(reverse.memory.plan)
        self.assertEqual(reverse.diagnostics["formation_lane"]["fallback"], "lane_lock_active")
        self.assertTrue(reverse.diagnostics["formation_lane"]["lock"]["active"])

    def test_disabled_switches_are_action_identical_to_copied_baseline(self):
        variant_root = Path(__file__).resolve().parents[1]
        baseline_path = variant_root / TRACKED_BASELINE_FILES[0]
        self.assertTrue(baseline_path.is_file(), "tracked Phase5F controller baseline missing")
        self.assertEqual(
            hashlib.sha256(
                baseline_path.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest(),
            PHASE5F_CONTROLLER_SHA256,
        )
        spec = importlib.util.spec_from_file_location("sealed_phase5f_controller", baseline_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        baseline_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline_module)
        control = self.control(memory=self.memory())
        switch_pairs = ((False, False), (False, True), (True, False), (1, True), (True, 1))
        for phase5g_enabled, lane_enabled in switch_pairs:
            disabled = {
                **self.p,
                "formation_enabled": False,
                "phase5g_enabled": phase5g_enabled,
                "formation_lane_change_enabled": lane_enabled,
            }
            expected = baseline_module.decide(
                replace(control, memory=NoaMemory((), "CRUISE")),
                disabled,
            )
            actual = decide(control, disabled)
            with self.subTest(phase5g=phase5g_enabled, lane=lane_enabled):
                self.assertEqual(actual, expected)

        lane_active = {
            **self.p,
            "formation_enabled": False,
            "phase5g_enabled": True,
            "formation_lane_change_enabled": True,
        }
        expected = baseline_module.decide(
            replace(control, memory=NoaMemory((), "CRUISE")), lane_active
        )
        actual = decide(control, lane_active)
        self.assertEqual(actual.action, expected.action)
        self.assertTrue(actual.diagnostics["formation_lane"]["enabled"])

    def test_phase5g_path_does_not_activate_r5(self):
        with patch("noa.controller.r5.validate") as validate, patch(
            "noa.controller.r5.assess_candidate"
        ) as assess:
            decision = self.step(0.0, self.memory())
        validate.assert_not_called()
        assess.assert_not_called()
        self.assertNotIn("r5", decision.diagnostics)
        self.assertEqual(decision.memory.r5_draw_count, 0)
        self.assertIsNone(decision.memory.r5_episode_signature)

    def test_real_slow_lead_preempts_formation_geometry(self):
        neighbors = (
            (35.0, 1, 2.0, 0.0),
            (42.0, 0, 10.0, 0.0),
        )
        memory = self.memory()
        with patch("noa.controller.verify_candidate", return_value=SAFE), patch(
            "noa.formation.verify_candidate", return_value=SAFE
        ):
            for tick in range(6):
                decision = decide(
                    self.control(tick / 10.0, memory=memory, neighbors=neighbors),
                    self.p,
                )
                memory = decision.memory
        self.assertEqual(decision.memory.own_behavior, "EXECUTE_LC")
        self.assertIsNotNone(decision.memory.plan)
        self.assertEqual(decision.memory.lane_change_reason, "slower_visible_lead")
        self.assertLess(decision.action.acceleration_mps2, 0.0)
        self.assertEqual(decision.diagnostics["reason"], "slower_visible_lead")
        self.assertEqual(
            decision.diagnostics["formation_lane"]["fallback"],
            "higher_priority_plan_committed",
        )


if __name__ == "__main__":
    unittest.main()
