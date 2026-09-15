"""Contracts for deterministic Phase 5G cases and private-memory restoration."""

from copy import deepcopy
from dataclasses import asdict, fields
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.phase5 import parameters as phase5_parameters
from experiments.phase5_detection import detect_frames
from models.geometry import body_from_state
from models.vehicle import VehicleState
from noa.contracts import NoaMemory
from noa.formation import FormationMemory
from perception.road import VisibleRoad
from research.common import settings
from safety.geometry import collide


ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT.parents[1] / "tmp"
MAIN_SIX_EXPECTED = (
    ("v0", 100.0, 1.65, 10.0),
    ("v1", 145.0, 1.65, 9.5),
    ("v2", 190.0, 1.65, 10.5),
    ("v3", 122.0, 4.95, 10.5),
    ("v4", 167.0, 4.95, 9.5),
    ("v5", 108.0, 8.25, 10.0),
)
CASE_KEYS = {
    "name", "duration_s", "initial", "controlled", "scripts",
    "initial_memories", "private_rng_provenance", "purpose",
    "expected_lane_changes",
}


def phase5g_parameters(mode="lane_priority"):
    model, physical, policy = phase5_parameters(mode != "off")
    registered = json.loads((ROOT / "configs" / "phase5g.json").read_text(encoding="utf-8"))
    lane = mode == "lane_priority"
    enabled = mode != "off"
    switches = {
        "formation_enabled": enabled,
        "formation_lane_change_enabled": lane,
        "r5_enabled": False,
    }
    physical.update(registered)
    physical.update(settings("phase4"))
    physical.update(settings("phase5"))
    physical.update(switches)
    policy.update(registered)
    policy.update(switches)
    policy["noa_target_speed_mps"] = 10.0
    return model, physical, policy


def road():
    return VisibleRoad(
        (((0.0, 0.0), (2000.0, 0.0)), ((0.0, 9.9), (2000.0, 9.9))),
        (((0.0, 3.3), (2000.0, 3.3)), ((0.0, 6.6), (2000.0, 6.6))),
    )


def canonical_physical_memory_rows(case):
    rows = []
    for key, state in case["initial"].items():
        physical = tuple(state[name] for name in (
            "time_s", "x_m", "y_m", "heading_rad", "vx_mps", "vy_mps",
            "yaw_rate_radps", "a_drive_mps2", "steering_rad",
        ))
        memory = json.dumps(case["initial_memories"][key], sort_keys=True, separators=(",", ":"))
        rows.append((physical, memory))
    return tuple(sorted(rows))


class Phase5GCaseTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("experiments.phase5g_cases"),
            "Missing Phase 5G pure-formation case generator",
        )
        self.cases = importlib.import_module("experiments.phase5g_cases")
        self.model, self.p, _ = phase5g_parameters()

    def test_registered_seed_sets_counts_and_main_rows_are_exact(self):
        self.assertEqual(self.cases.DEV_SEEDS, (101, 102, 103))
        self.assertEqual(self.cases.HOLDOUT_SEEDS, (5101, 5102, 5103, 5104, 5105))
        self.assertEqual(self.cases.SUPPORTED_COUNTS, (3, 6, 12))
        self.assertEqual(self.cases.LANE_CENTERS_M, (1.65, 4.95, 8.25))
        self.assertEqual(self.cases.MAIN_SIX, MAIN_SIX_EXPECTED)

    def test_main_case_contract_distribution_and_target_are_exact(self):
        case = self.cases.main_six_case(self.p)
        self.assertTrue(CASE_KEYS <= set(case))
        self.assertEqual(case["duration_s"], 45.0)
        self.assertEqual(case["scripts"], {})
        self.assertEqual(set(case["initial"]), set(case["controlled"]))
        self.assertEqual(
            tuple((key, state["x_m"], state["y_m"], state["vx_mps"])
                  for key, state in case["initial"].items()),
            MAIN_SIX_EXPECTED,
        )
        self.assertEqual(sorted(sum(state["y_m"] == center for state in case["initial"].values())
                                for center in self.cases.LANE_CENTERS_M), [1, 2, 3])
        self.assertEqual(case["expected_lane_changes"]["minimum"], 1)
        self.assertEqual(case["expected_lane_changes"]["target_lane_counts"], [2, 2, 2])

    def test_exact_main_is_independently_collision_free_dynamic_gap_safe_and_unformed(self):
        case = self.cases.main_six_case(self.p)
        states = {key: VehicleState(**value) for key, value in case["initial"].items()}
        bodies = [body_from_state(state, self.p) for state in states.values()]
        self.assertFalse(any(collide(left, right) for index, left in enumerate(bodies)
                             for right in bodies[index + 1:]))
        self.assertTrue(self.cases.dynamic_minimum_gap_ok(case["initial"], self.p))
        detection = detect_frames([{"time_s": 0.0, "states": deepcopy(case["initial"])}])
        self.assertTrue(detection["frames"][0]["fleet_failure_reasons"])
        self.assertFalse(detection["success"])

    def test_seeded_counts_are_all_controlled_safe_and_initially_unformed(self):
        templates = {3: (1, 1, 1), 6: (3, 2, 1), 12: (4, 4, 4)}
        for count, seed in zip(self.cases.SUPPORTED_COUNTS, self.cases.DEV_SEEDS):
            with self.subTest(count=count, seed=seed):
                case = self.cases.seeded_case(self.p, count, seed)
                self.assertTrue(CASE_KEYS <= set(case))
                self.assertEqual(case["scripts"], {})
                self.assertEqual(set(case["initial"]), set(case["controlled"]))
                lane_counts = tuple(sum(state["y_m"] == center for state in case["initial"].values())
                                    for center in self.cases.LANE_CENTERS_M)
                self.assertEqual(lane_counts, templates[count])
                bases = case["sampling"]["longitudinal_bases_m"]
                self.assertTrue(all(80.0 <= base <= 260.0 for base in bases))
                offset = 0
                for lane_count in templates[count]:
                    lane_bases = bases[offset:offset + lane_count]
                    self.assertTrue(all(right - left >= 36.0 - 1e-12
                                        for left, right in zip(lane_bases, lane_bases[1:])))
                    offset += lane_count
                for state, base in zip(case["initial"].values(), bases):
                    self.assertLessEqual(abs(state["x_m"] - base), 4.0 + 1e-12)
                    self.assertTrue(8.0 <= state["vx_mps"] <= 12.0)
                self.assertTrue(self.cases.validate_initial(case["initial"], self.p)["passed"])
                detection = detect_frames([{"time_s": 0.0, "states": deepcopy(case["initial"])}])
                self.assertTrue(detection["frames"][0]["fleet_failure_reasons"])

    def test_seed_generation_and_canonical_development_bundle_are_byte_identical(self):
        first = self.cases.seeded_case(self.p, 12, 103)
        second = self.cases.seeded_case(self.p, 12, 103)
        self.assertEqual(self.cases.canonical_json_bytes(first), self.cases.canonical_json_bytes(second))
        specs = ((3, 101), (6, 102), (12, 103))
        self.assertEqual(
            self.cases.bundle_bytes(self.p, specs),
            self.cases.bundle_bytes(self.p, specs),
        )

    def test_actor_relabeling_carries_physics_and_memory_without_changing_rows(self):
        original = self.cases.seeded_case(self.p, 6, 102)
        relabeled = self.cases.seeded_case(
            self.p, 6, 102, actor_keys=("zeta", "alpha", "mu", "q", "b", "r")
        )
        self.assertEqual(canonical_physical_memory_rows(original),
                         canonical_physical_memory_rows(relabeled))
        self.assertNotEqual(set(original["initial"]), set(relabeled["initial"]))
        self.assertFalse(relabeled["private_rng_provenance"]["actor_identity_used"])

    def test_each_controlled_actor_has_full_independent_seeded_memory(self):
        case = self.cases.seeded_case(self.p, 12, 101)
        expected = {field.name for field in fields(FormationMemory)}
        memories = case["initial_memories"]
        self.assertEqual(set(memories), set(case["controlled"]))
        self.assertTrue(all(set(memory) == expected for memory in memories.values()))
        seeds = [memory["formation_lane_rng_state"] for memory in memories.values()]
        self.assertEqual(len(seeds), len(set(seeds)))
        self.assertTrue(all(type(seed) is int and 0 <= seed < 2**64 for seed in seeds))
        self.assertEqual(case["private_rng_provenance"]["states_by_actor"],
                         {key: memories[key]["formation_lane_rng_state"] for key in case["controlled"]})

    def test_private_seed_domain_includes_vehicle_count_but_never_actor_key(self):
        three = self.cases.seeded_case(self.p, 3, 101)
        six = self.cases.seeded_case(self.p, 6, 101)
        self.assertNotEqual(
            three["initial_memories"]["v0"]["formation_lane_rng_state"],
            six["initial_memories"]["v0"]["formation_lane_rng_state"],
        )
        self.assertEqual(three["private_rng_provenance"]["vehicle_count"], 3)
        self.assertEqual(six["private_rng_provenance"]["vehicle_count"], 6)
        self.assertFalse(three["private_rng_provenance"]["actor_identity_used"])

    def test_invalid_count_seed_speed_and_actor_keys_fail_before_any_file_is_written(self):
        invalid = (
            (((5, 101),), 8.0, 12.0),
            (((3, True),), 8.0, 12.0),
            (((3, 101),), True, 12.0),
            (((3, 101),), 12.0, 8.0),
            (((3, 101),), 8.0, float("inf")),
        )
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            for index, (specs, low, high) in enumerate(invalid):
                target = Path(temp) / f"invalid_{index}.json"
                with self.subTest(specs=specs, low=low, high=high), self.assertRaises((TypeError, ValueError)):
                    self.cases.freeze_cases(target, self.p, specs, speed_min_mps=low, speed_max_mps=high)
                self.assertFalse(target.exists())
        with self.assertRaises(ValueError):
            self.cases.seeded_case(self.p, 3, 101, actor_keys=("a", "a", "b"))

    def test_speed_overflow_and_model_limit_are_named_and_rejected_before_write(self):
        with self.assertRaisesRegex(ValueError, "speed_min_mps"):
            self.cases.seeded_case(self.p, 3, 101,
                                   speed_min_mps=10**10000, speed_max_mps=12.0)
        with self.assertRaisesRegex(ValueError, "max_speed_mps"):
            self.cases.seeded_case(self.p, 3, 101,
                                   speed_min_mps=100.0, speed_max_mps=101.0)
        maximum = self.p["max_speed_mps"]
        boundary = self.cases.seeded_case(
            self.p, 3, 101, speed_min_mps=maximum - 1.0,
            speed_max_mps=maximum,
        )
        self.assertTrue(all(state["vx_mps"] <= maximum
                            for state in boundary["initial"].values()))
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            target = Path(temp) / "invalid_speed.json"
            with self.assertRaisesRegex(ValueError, "max_speed_mps"):
                self.cases.freeze_cases(target, self.p, ((3, 101),),
                                        speed_min_mps=100.0, speed_max_mps=101.0)
            self.assertFalse(target.exists())

    def test_main_and_seeded_case_audits_reject_speed_above_model_limit(self):
        with self.assertRaisesRegex(RuntimeError, "speed"):
            self.cases.main_six_case({**self.p, "max_speed_mps": 9.0})
        case = self.cases.seeded_case(self.p, 3, 101)
        changed = deepcopy(case["initial"])
        changed[next(iter(changed))]["vx_mps"] = self.p["max_speed_mps"] + 0.1
        audit = self.cases.validate_initial(changed, self.p)
        self.assertFalse(audit["passed"])
        self.assertIn("initial_speed_outside_model", audit["failure_reasons"])

    def test_strict_bundle_roundtrip_and_all_envelope_mutations_are_rejected(self):
        specs = ((3, 101), (6, 102), (12, 103))
        original = self.cases.bundle_bytes(self.p, specs)
        loaded = self.cases.load_bundle(original, self.p, specs)
        self.assertEqual(self.cases.canonical_json_bytes(loaded), original)

        def reseal(bundle):
            bundle["physical_sha256"] = self.cases.digest_json(
                [self.cases.physical_case(case) for case in bundle["cases"]]
            )
            bundle["initial_state_sha256"] = self.cases.digest_json(bundle["cases"])
            envelope = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
            bundle["bundle_sha256"] = self.cases.digest_json(envelope)

        base = json.loads(original)
        mutations = {}
        changed = deepcopy(base)
        changed["cases"][0]["initial"]["v0"]["x_m"] += 0.25
        reseal(changed)
        mutations["resealed_physics"] = changed
        changed = deepcopy(base)
        changed["generator_sha256"] = "0" * 64
        reseal(changed)
        mutations["resealed_source"] = changed
        changed = deepcopy(base)
        changed["schema"] = "phase5g_unregistered"
        reseal(changed)
        mutations["resealed_schema"] = changed
        changed = deepcopy(base)
        changed["extra"] = 1
        reseal(changed)
        mutations["resealed_extra"] = changed
        changed = deepcopy(base)
        changed["cases"][0]["purpose"] += " tampered"
        mutations["hash_mismatch"] = changed
        changed = deepcopy(base)
        actor = changed["cases"][0]["controlled"][0]
        changed["cases"][0]["initial_memories"][actor]["formation_lane_rng_state"] ^= 1
        reseal(changed)
        mutations["resealed_memory"] = changed
        for name, bundle in mutations.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.cases.load_bundle(self.cases.canonical_json_bytes(bundle), self.p, specs)

    def test_freeze_is_exclusive_and_reload_preserves_exact_normalized_bytes(self):
        specs = ((3, 101), (6, 102), (12, 103))
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            target = Path(temp) / "development_only.json"
            self.cases.freeze_cases(target, self.p, specs)
            self.assertEqual(target.read_bytes(), self.cases.bundle_bytes(self.p, specs))
            self.assertEqual(self.cases.canonical_json_bytes(
                self.cases.load_bundle(target, self.p, specs)), target.read_bytes())
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                self.cases.freeze_cases(target, self.p, specs)
            self.assertEqual(target.read_bytes(), original)

    def test_staged_validation_failure_never_publishes_target_and_same_path_retries(self):
        specs = ((3, 101), (6, 102), (12, 103))
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            target = Path(temp) / "fault_injected.json"
            with patch.object(self.cases, "_validate_staged_bundle",
                              side_effect=ValueError("injected staged validation failure")):
                with self.assertRaisesRegex(RuntimeError, "staging.*preserved"):
                    self.cases.freeze_cases(target, self.p, specs)
            self.assertFalse(target.exists())
            self.assertEqual(len(list(target.parent.glob(".fault_injected.json.*.staging"))), 1)
            self.cases.freeze_cases(target, self.p, specs)
            self.assertTrue(target.exists())

    def test_case_and_bundle_builds_share_no_nested_mutable_input_objects(self):
        specs = ((3, 101), (6, 102), (12, 103))
        first = self.cases.build_bundle(self.p, specs)
        second = self.cases.build_bundle(self.p, specs)
        actor = first["cases"][0]["controlled"][0]
        original_x = second["cases"][0]["initial"][actor]["x_m"]
        original_seed = second["cases"][0]["initial_memories"][actor]["formation_lane_rng_state"]
        first["cases"][0]["initial"][actor]["x_m"] += 1.0
        first["cases"][0]["initial_memories"][actor]["formation_lane_rng_state"] ^= 1
        self.assertEqual(second["cases"][0]["initial"][actor]["x_m"], original_x)
        self.assertEqual(second["cases"][0]["initial_memories"][actor]["formation_lane_rng_state"],
                         original_seed)
        case = second["cases"][0]
        self.assertEqual(len({id(row) for row in case["initial"].values()}),
                         len(case["initial"]))
        self.assertEqual(len({id(row) for row in case["initial_memories"].values()}),
                         len(case["initial_memories"]))


class Phase5GClockTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("simulation.phase5g_clock"),
            "Missing Phase 5G private-memory clock",
        )
        self.clock_module = importlib.import_module("simulation.phase5g_clock")
        self.case_module = importlib.import_module("experiments.phase5g_cases")
        self.model, self.p, self.policy = phase5g_parameters()
        self.case = self.case_module.seeded_case(self.p, 3, 101)
        self.initial = {key: VehicleState(**value) for key, value in self.case["initial"].items()}

    def clock(self, memories=None, mode="lane_priority", **changes):
        model, physical, policy = phase5g_parameters(mode)
        digest = self.clock_module.initial_memory_hash(
            self.case["initial_memories"] if memories is None else memories
        )
        return self.clock_module.Phase5GClock(
            self.initial, model, road(), physical, policy, self.case["controlled"], {},
            self.case["initial_memories"] if memories is None else memories,
            clock_schema=changes.pop("clock_schema", self.clock_module.CLOCK_SCHEMA),
            initial_memories_sha256=changes.pop("initial_memories_sha256", digest),
            **changes,
        )

    def test_lane_priority_restores_full_separate_immutable_memories_and_tuples(self):
        clock = self.clock()
        expected_fields = {field.name for field in fields(FormationMemory)}
        self.assertTrue(all(type(memory) is FormationMemory for memory in clock.memories.values()))
        self.assertTrue(all(set(asdict(memory)) == expected_fields for memory in clock.memories.values()))
        self.assertEqual(len({id(memory) for memory in clock.memories.values()}), len(clock.memories))
        actor = self.case["controlled"][0]
        row = deepcopy(self.case["initial_memories"][actor])
        row["formation_lane_signature"] = [0, 120.0, 1.65, 10.0, 0.0, 0.0, 4.0, 1.8]
        row["formation_lane_since_s"] = 0.0
        memories = deepcopy(self.case["initial_memories"])
        memories[actor] = row
        restored = self.clock(memories).memories[actor]
        self.assertIsInstance(restored.formation_lane_signature, tuple)

    def test_clock_rejects_shared_input_identity_actor_schema_hash_and_seed_errors(self):
        actor0, actor1 = self.case["controlled"][:2]
        shared = deepcopy(self.case["initial_memories"])
        shared[actor1] = shared[actor0]
        bad_cases = {}
        bad_cases["shared"] = shared
        missing = deepcopy(self.case["initial_memories"])
        missing.pop(actor0)
        bad_cases["keys"] = missing
        extra = deepcopy(self.case["initial_memories"])
        extra[actor0]["extra"] = 1
        bad_cases["extra"] = extra
        no_seed = deepcopy(self.case["initial_memories"])
        no_seed[actor0]["formation_lane_rng_state"] = None
        bad_cases["missing_seed"] = no_seed
        bool_seed = deepcopy(self.case["initial_memories"])
        bool_seed[actor0]["formation_lane_rng_state"] = True
        bad_cases["bool_seed"] = bool_seed
        for name, memories in bad_cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.clock(memories)
        with self.assertRaises(ValueError):
            self.clock(clock_schema="phase5g_wrong")
        with self.assertRaises(ValueError):
            self.clock(initial_memories_sha256="0" * 64)

    def test_clock_rejects_invalid_semantics_in_every_inherited_memory_layer(self):
        actor = self.case["controlled"][0]
        signature = [120.0, 1.65, 10.0, 0.0, 0.0, 4.0, 1.8]
        invalid = {
            "formation_weight": 2.0,
            "formation_state": "UNKNOWN_FORMATION_STATE",
            "own_behavior": "UNKNOWN_OWN_BEHAVIOR",
            "formation_last_time_s": -0.1,
            "completed_lane_changes": -1,
            "candidate_signature": signature[:-1],
            "candidate_since_s": -0.1,
            "reference_signature": signature[:-1],
            "prepare_since_s": -0.1,
            "last_lc_end_s": -0.1,
            "r5_last_time_s": -0.1,
            "r5_draw_count": -1,
            "r5_phase": "UNKNOWN_R5_PHASE",
            "formation_lane_draw_count": -1,
            "lane_change_reason": "unknown_reason",
        }
        for field, value in invalid.items():
            memories = deepcopy(self.case["initial_memories"])
            memories[actor][field] = value
            if field == "candidate_signature":
                memories[actor]["candidate_since_s"] = 0.0
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.clock(memories)

        negative_plan = deepcopy(self.case["initial_memories"])
        negative_plan[actor].update(
            own_behavior="EXECUTE_LC",
            target_y_m=4.95,
            prepare_since_s=0.0,
            lane_change_reason="formation_geometry",
            plan={"start_s": -0.1, "y_start_m": 1.65, "y_target_m": 4.95,
                  "duration_s": 5.0, "speed_mps": 10.0},
        )
        with self.assertRaises(ValueError):
            self.clock(negative_plan)

        cross_field_rows = []
        missing_since = deepcopy(self.case["initial_memories"])
        missing_since[actor]["formation_lane_signature"] = [0] + signature
        cross_field_rows.append(missing_since)
        deadline_without_episode = deepcopy(self.case["initial_memories"])
        deadline_without_episode[actor]["formation_lane_backoff_until_s"] = 1.0
        cross_field_rows.append(deadline_without_episode)
        draw_without_seed = deepcopy(self.case["initial_memories"])
        draw_without_seed[actor]["formation_lane_rng_state"] = None
        draw_without_seed[actor]["formation_lane_draw_count"] = 1
        cross_field_rows.append(draw_without_seed)
        for memories in cross_field_rows:
            with self.subTest(cross=True), self.assertRaises(ValueError):
                self.clock(memories)

    def test_clock_accepts_semantically_valid_active_full_memory(self):
        actor = self.case["controlled"][0]
        signature = [120.0, 1.65, 10.0, 0.0, 0.0, 4.0, 1.8]
        memories = deepcopy(self.case["initial_memories"])
        memories[actor].update(
            own_behavior="PREPARE_LC",
            target_y_m=4.95,
            prepare_since_s=0.0,
            lane_change_reason="formation_geometry",
            reference_signature=signature,
            candidate_signature=signature,
            candidate_since_s=0.0,
            formation_weight=0.5,
            cached_increment_mps2=0.25,
            formation_state="FORMING",
            formation_last_time_s=0.0,
        )
        clock = self.clock(memories)
        self.assertEqual(clock.memories[actor].formation_state, "FORMING")
        self.assertIsInstance(clock.memories[actor].candidate_signature, tuple)

    def test_clock_deep_snapshots_nested_parameters_and_policy_independently(self):
        model, physical, policy = phase5g_parameters("lane_priority")
        shared_durations = [5.0, 7.5, 10.0]
        shared_nested = {"probe": [1, 2]}
        physical["formation_lane_duration_candidates_s"] = shared_durations
        policy["formation_lane_duration_candidates_s"] = shared_durations
        physical["quality_probe_nested"] = shared_nested
        policy["quality_probe_nested"] = shared_nested
        digest = self.clock_module.initial_memory_hash(self.case["initial_memories"])
        clock = self.clock_module.Phase5GClock(
            self.initial, model, road(), physical, policy, self.case["controlled"], {},
            self.case["initial_memories"], clock_schema=self.clock_module.CLOCK_SCHEMA,
            initial_memories_sha256=digest,
        )
        baseline = self.clock()
        shared_durations[0] = 99.0
        shared_nested["probe"][0] = 99
        self.assertEqual(clock.p["formation_lane_duration_candidates_s"], (5.0, 7.5, 10.0))
        self.assertEqual(clock.policy["formation_lane_duration_candidates_s"], (5.0, 7.5, 10.0))
        self.assertIsNot(clock.p["formation_lane_duration_candidates_s"],
                         clock.policy["formation_lane_duration_candidates_s"])
        self.assertEqual(tuple(clock.p["quality_probe_nested"]["probe"]), (1, 2))
        with self.assertRaises(TypeError):
            clock.p["quality_probe_nested"]["probe"][0] = 3
        self.assertEqual(clock.tick(), baseline.tick())

    def test_formation_and_communication_switches_require_exact_bool(self):
        for field, value, mode in (
            ("formation_enabled", 1, "lane_priority"),
            ("formation_enabled", 0, "off"),
            ("communication_enabled", 0, "lane_priority"),
        ):
            model, physical, policy = phase5g_parameters(mode)
            physical[field] = value
            policy[field] = value
            memories = self.case["initial_memories"]
            if mode == "off":
                memories = self.clock_module.neutral_phase5g_memories(memories)
            digest = self.clock_module.initial_memory_hash(memories)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.clock_module.Phase5GClock(
                    self.initial, model, road(), physical, policy,
                    self.case["controlled"], {}, memories,
                    clock_schema=self.clock_module.CLOCK_SCHEMA,
                    initial_memories_sha256=digest,
                )

    def test_off_mode_requires_all_six_phase5g_fields_neutral_and_returns_noa_memory(self):
        neutral = self.clock_module.neutral_phase5g_memories(self.case["initial_memories"])
        clock = self.clock(neutral, mode="off")
        self.assertTrue(all(type(memory) is NoaMemory for memory in clock.memories.values()))
        actor = self.case["controlled"][0]
        phase5g_fields = {
            "formation_lane_signature": (0, 1.0, 1.65, 1.0, 0.0, 0.0, 4.0, 1.8),
            "formation_lane_since_s": 0.0,
            "formation_lane_lock_until_s": 1.0,
            "formation_lane_rng_state": 1,
            "formation_lane_draw_count": 1,
            "formation_lane_backoff_until_s": 1.0,
        }
        for field, value in phase5g_fields.items():
            changed = deepcopy(neutral)
            changed[actor][field] = value
            if field in {"formation_lane_signature", "formation_lane_since_s"}:
                changed[actor]["formation_lane_signature"] = phase5g_fields["formation_lane_signature"]
                changed[actor]["formation_lane_since_s"] = 0.0
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.clock(changed, mode="off")

    def test_longitudinal_mode_does_not_require_lane_priority_seed(self):
        neutral = self.clock_module.neutral_phase5g_memories(self.case["initial_memories"])
        clock = self.clock(neutral, mode="longitudinal")
        self.assertTrue(all(type(memory) is FormationMemory for memory in clock.memories.values()))


if __name__ == "__main__":
    unittest.main()
