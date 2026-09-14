"""Task 3 contracts for the replayable non-formal simple-formation demo."""

from copy import deepcopy
from dataclasses import asdict, fields
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import MappingProxyType
from unittest.mock import patch

from experiments import phase5g_cases
from models.bezier import QuadraticLaneChange
from noa.simple_formation import PARAMETERS, SimpleFormationMemory


ROOT = Path(__file__).resolve().parents[1]

SIMPLE_DEFAULTS = {
    "simple_formation_local_range_m": 90.0,
    "simple_formation_adjacent_gap_m": 15.0,
    "simple_formation_same_gap_m": 30.0,
    "simple_formation_position_tolerance_m": 2.0,
    "simple_formation_accel_limit_mps2": 0.5,
    "simple_formation_max_lane_changes": 1,
}
SIMPLE_NONDEFAULTS = {
    "simple_formation_local_range_m": 78.0,
    "simple_formation_adjacent_gap_m": 14.0,
    "simple_formation_same_gap_m": 28.0,
    "simple_formation_position_tolerance_m": 1.5,
    "simple_formation_accel_limit_mps2": 0.4,
    "simple_formation_max_lane_changes": 1,
}
EXPECTED_MODES = {
    "off": {"formation_enabled": False, "formation_lane_change_enabled": False},
    "longitudinal": {"formation_enabled": True, "formation_lane_change_enabled": False},
    "lane_priority": {"formation_enabled": True, "formation_lane_change_enabled": True},
}


def mutable_ids(value):
    """Collect every recursively reachable mutable container identity."""
    if isinstance(value, dict):
        result = {id(value)}
        for item in value.values():
            result.update(mutable_ids(item))
        return result
    if isinstance(value, (list, set, bytearray)):
        result = {id(value)}
        for item in value:
            result.update(mutable_ids(item))
        return result
    if isinstance(value, tuple):
        result = set()
        for item in value:
            result.update(mutable_ids(item))
        return result
    return set()


class SimpleFormationHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = importlib.import_module("experiments.phase5g")
        cls.replay = importlib.import_module("experiments.phase5g_replay")
        cls.entry = importlib.import_module("run")

    def short_case(self, physical, *, count=3, seed=101, duration_s=0.1):
        case = phase5g_cases.seeded_case(physical, count, seed)
        return {**case, "duration_s": duration_s}

    def simple_parameters(self, overrides=None):
        resolved = SIMPLE_NONDEFAULTS if overrides is None else overrides
        return self.harness.parameters(
            "lane_priority", 10.0,
            simple_rules=True, simple_overrides=resolved,
        )

    def call_cli(self, argv):
        with patch.object(sys, "argv", ["run.py", *argv]):
            return self.entry.main()

    def test_registered_simple_defaults_and_formal_modes_are_exact(self):
        registered = json.loads(
            (ROOT / "configs" / "phase5g.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {key: registered[key] for key in PARAMETERS}, SIMPLE_DEFAULTS,
        )
        self.assertIs(registered["simple_formation_enabled"], False)
        self.assertEqual(dict(self.harness.MODES), EXPECTED_MODES)
        self.assertEqual(tuple(self.harness.MODES), ("off", "longitudinal", "lane_priority"))

    def test_simple_parameters_change_only_switch_and_six_resolved_values(self):
        base_model, base_physical, base_policy = self.harness.parameters("lane_priority")
        model, physical, policy = self.simple_parameters()
        expected_differences = {
            "simple_formation_enabled",
            *(key for key in PARAMETERS
              if SIMPLE_NONDEFAULTS[key] != SIMPLE_DEFAULTS[key]),
        }
        self.assertEqual(dict(model.p), dict(base_model.p))
        self.assertEqual(
            {key for key in physical if physical[key] != base_physical[key]},
            expected_differences,
        )
        self.assertEqual(
            {key for key in policy if policy[key] != base_policy[key]},
            expected_differences,
        )
        self.assertIs(base_physical["simple_formation_enabled"], False)
        self.assertIs(base_policy["simple_formation_enabled"], False)
        self.assertIs(physical["simple_formation_enabled"], True)
        self.assertIs(policy["simple_formation_enabled"], True)
        self.assertIs(physical["r5_enabled"], False)
        self.assertIs(policy["r5_enabled"], False)
        self.assertEqual({key: physical[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)
        self.assertEqual({key: policy[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)

    def test_parameter_trees_share_no_mutable_identity_in_legacy_or_simple_mode(self):
        for simple_rules in (False, True):
            overrides = SIMPLE_NONDEFAULTS if simple_rules else None
            with self.subTest(simple_rules=simple_rules):
                model, physical, policy = self.harness.parameters(
                    "lane_priority", simple_rules=simple_rules,
                    simple_overrides=overrides,
                )
                physical_ids = mutable_ids(physical)
                policy_ids = mutable_ids(policy)
                model_ids = mutable_ids(dict(model.p))
                self.assertTrue(physical_ids.isdisjoint(policy_ids))
                self.assertTrue(physical_ids.isdisjoint(model_ids))
                self.assertTrue(policy_ids.isdisjoint(model_ids))

                policy_before = deepcopy(policy)
                model_before = deepcopy(dict(model.p))
                physical["formation_lane_duration_candidates_s"].append(12.5)
                self.assertEqual(policy, policy_before)
                self.assertEqual(dict(model.p), model_before)

                _, later_physical, later_policy = self.harness.parameters(
                    "lane_priority", simple_rules=simple_rules,
                    simple_overrides=overrides,
                )
                self.assertNotIn(
                    12.5, later_physical["formation_lane_duration_candidates_s"],
                )
                self.assertNotIn(
                    12.5, later_policy["formation_lane_duration_candidates_s"],
                )
                self.assertTrue(mutable_ids(later_physical).isdisjoint(
                    mutable_ids(later_policy)
                ))

    def test_parameters_require_exact_boolean_and_override_contract(self):
        for value in (None, 0, 1, "true", [], {}):
            if value is False:
                continue
            with self.subTest(simple_rules=value), self.assertRaisesRegex(
                ValueError, "simple_rules"
            ):
                self.harness.parameters(
                    "lane_priority", simple_rules=value,
                    simple_overrides=SIMPLE_NONDEFAULTS,
                )
        self.harness.parameters("lane_priority", simple_rules=False)
        self.harness.parameters(
            "lane_priority", simple_rules=False,
            simple_overrides=MappingProxyType({}),
        )
        with self.assertRaisesRegex(ValueError, "simple_overrides"):
            self.harness.parameters(
                "lane_priority", simple_rules=False,
                simple_overrides={"simple_formation_local_range_m": 90.0},
            )
        for invalid in (None, [], (), "mapping"):
            with self.subTest(overrides=invalid), self.assertRaisesRegex(
                ValueError, "simple_overrides"
            ):
                self.harness.parameters(
                    "lane_priority", simple_rules=True, simple_overrides=invalid,
                )
        self.simple_parameters(MappingProxyType(SIMPLE_NONDEFAULTS))

    def test_simple_overrides_reject_missing_extra_and_invalid_values(self):
        invalid = []
        missing = dict(SIMPLE_NONDEFAULTS)
        missing.pop("simple_formation_same_gap_m")
        invalid.append(missing)
        invalid.append({**SIMPLE_NONDEFAULTS, "extra": 1})
        for key in PARAMETERS[:-1]:
            for value in (True, 0, -1.0, float("nan"), float("inf")):
                invalid.append({**SIMPLE_NONDEFAULTS, key: value})
        for value in (True, 0, 2, 1.0, float("nan")):
            invalid.append({**SIMPLE_NONDEFAULTS,
                            "simple_formation_max_lane_changes": value})
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.harness.parameters(
                    "lane_priority", simple_rules=True,
                    simple_overrides=overrides,
                )

    def test_demo_writes_exact_simple_metadata_and_forwards_resolved_parameters(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(
            self.harness, "run_variant",
            return_value={"recording_passed": True},
        ) as run_variant:
            output = Path(temp) / "simple-demo"
            result = self.harness.run_phase5g_demo(
                vehicle_count=6, seed=7, target_speed_mps=9.5,
                duration_s=0.1, output_base=output, live=False,
                local_formation_range_m=78.0,
                adjacent_lane_gap_m=14.0,
                same_lane_gap_m=28.0,
                position_tolerance_m=1.5,
                formation_accel_limit_mps2=0.4,
                max_formation_lane_changes=1,
            )
            self.assertTrue(result.is_dir())
            metadata = json.loads((result / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["purpose"],
                             "Non-formal simple local if/else formation GUI source trace")
            self.assertEqual(metadata["schema"], "phase5g_simple_demo_v1")
            self.assertIs(metadata["formal"], False)
            self.assertEqual(metadata["mode"], "lane_priority")
            self.assertIs(metadata["simple_formation_enabled"], True)
            self.assertEqual(metadata["vehicle_count"], 6)
            self.assertEqual(metadata["seed"], 7)
            self.assertEqual(metadata["target_speed_mps"], 9.5)
            self.assertEqual(metadata["duration_s"], 0.1)
            self.assertEqual(metadata["simple_parameters"], SIMPLE_NONDEFAULTS)
            run_variant.assert_called_once()
            args = run_variant.call_args.args
            self.assertEqual(args[5], "lane_priority")
            physical, policy = args[2], args[3]
            self.assertIs(physical["simple_formation_enabled"], True)
            self.assertIs(policy["simple_formation_enabled"], True)
            self.assertEqual({key: physical[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)
            self.assertEqual({key: policy[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)

    def test_demo_rejects_every_invalid_value_before_creating_result_base(self):
        valid = {
            "vehicle_count": 3, "seed": 1, "target_speed_mps": 10.0,
            "duration_s": 0.1, "live": False,
            "local_formation_range_m": 90.0,
            "adjacent_lane_gap_m": 15.0,
            "same_lane_gap_m": 30.0,
            "position_tolerance_m": 2.0,
            "formation_accel_limit_mps2": 0.5,
            "max_formation_lane_changes": 1,
        }
        invalid = [
            ("vehicle_count", True), ("vehicle_count", 5),
            ("seed", True), ("seed", -1),
            ("target_speed_mps", True), ("target_speed_mps", 0),
            ("target_speed_mps", float("nan")),
            ("duration_s", True), ("duration_s", 0),
            ("duration_s", float("inf")), ("duration_s", 0.15),
        ]
        for name in (
            "local_formation_range_m", "adjacent_lane_gap_m", "same_lane_gap_m",
            "position_tolerance_m", "formation_accel_limit_mps2",
        ):
            invalid.extend((name, value) for value in
                           (True, 0, -1.0, float("nan"), float("inf")))
        invalid.extend(("max_formation_lane_changes", value)
                       for value in (True, 0, 2, 1.0))
        with tempfile.TemporaryDirectory() as temp:
            for index, (name, value) in enumerate(invalid):
                output = Path(temp) / f"invalid-{index}"
                kwargs = {**valid, name: value, "output_base": output}
                with self.subTest(name=name, value=value), patch.object(
                    self.harness, "run_variant"
                ) as runner, self.assertRaises(ValueError):
                    self.harness.run_phase5g_demo(**kwargs)
                runner.assert_not_called()
                self.assertFalse(output.exists())

    def test_cli_forwards_every_demo_value_exactly_once(self):
        with patch("experiments.phase5g.run_phase5g_demo",
                   return_value=Path("literal-demo")) as demo:
            self.call_cli([
                "phase5g-demo", "--vehicle-count", "12", "--seed", "9",
                "--target-speed-mps", "9.5", "--duration-s", "40",
                "--output-base", "results/phase5g/custom-demo", "--offline",
                "--local-formation-range-m", "81",
                "--adjacent-lane-gap-m", "13",
                "--same-lane-gap-m", "29",
                "--position-tolerance-m", "1.25",
                "--formation-accel-limit-mps2", "0.35",
                "--max-formation-lane-changes", "1",
            ])
        demo.assert_called_once_with(
            vehicle_count=12, seed=9, target_speed_mps=9.5, duration_s=40.0,
            output_base="results/phase5g/custom-demo", mode="lane_priority",
            formal=False, live=False, local_formation_range_m=81.0,
            adjacent_lane_gap_m=13.0, same_lane_gap_m=29.0,
            position_tolerance_m=1.25, formation_accel_limit_mps2=0.35,
            max_formation_lane_changes=1,
        )

    def test_cli_rejects_invalid_simple_values_without_calling_demo(self):
        invalid = (
            ("--local-formation-range-m", "0"),
            ("--adjacent-lane-gap-m", "nan"),
            ("--same-lane-gap-m", "-1"),
            ("--position-tolerance-m", "inf"),
            ("--formation-accel-limit-mps2", "0"),
            ("--max-formation-lane-changes", "2"),
        )
        for flag, value in invalid:
            with self.subTest(flag=flag), patch(
                "experiments.phase5g.run_phase5g_demo"
            ) as demo, self.assertRaises(SystemExit):
                self.call_cli(["phase5g-demo", flag, value])
            demo.assert_not_called()

    def test_run_variant_reconstructs_nondefault_rules_and_neutral_private_memories(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "simple-variant"
            result = self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            self.assertEqual(result["status"], "completed")
            metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        expected_fields = {field.name for field in fields(SimpleFormationMemory)}
        self.assertEqual(set(metadata["initial_memories"]), set(case["controlled"]))
        for memory in metadata["initial_memories"].values():
            self.assertEqual(set(memory), expected_fields)
            self.assertIsNone(memory["reference_track_id"])
            self.assertIs(memory["formation_lane_change_done"], False)
        self.assertEqual({key: metadata["parameters"][key] for key in PARAMETERS},
                         SIMPLE_NONDEFAULTS)

    def test_replay_rebuilds_from_saved_simple_values_not_current_defaults(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "simple-replay-source"
            self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            exact_replay = self.replay.replay_variant(path)
            self.assertTrue(exact_replay["passed"], exact_replay)
            self.assertTrue(exact_replay["decision_replay_passed"])
            self.assertTrue(exact_replay["integration_replay_passed"])
        changed_defaults = self.harness._registered()
        changed_defaults.update(SIMPLE_DEFAULTS)
        with patch.object(self.harness, "_registered", return_value=changed_defaults):
            restored_model, restored_physical, restored_policy = (
                self.replay._validate_metadata(metadata)
            )
        self.assertEqual(dict(restored_model.p), metadata["model_parameters"])
        self.assertEqual(restored_physical, metadata["parameters"])
        self.assertEqual(restored_policy, metadata["policy_parameters"])

        missing = deepcopy(metadata)
        del missing["parameters"]["simple_formation_same_gap_m"]
        with self.assertRaises(ValueError):
            self.replay._validate_metadata(missing)
        tampered = deepcopy(metadata)
        tampered["parameters"]["simple_formation_adjacent_gap_m"] = 12.0
        with self.assertRaises(ValueError):
            self.replay._validate_metadata(tampered)

    def test_replay_rejects_resealed_bilateral_parameter_tampering_by_input_digest(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bilateral-parameter-tampering"
            self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            metadata_path = path / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIn("parameters_input_sha256", metadata)
            metadata["parameters"]["simple_formation_local_range_m"] = 79.0
            metadata["policy_parameters"]["simple_formation_local_range_m"] = 79.0
            self.harness.atomic_json(metadata_path, metadata)
            self.harness.seal_directory(path)
            replay = self.replay.replay_variant(path)
        self.assertFalse(replay["passed"], replay)
        self.assertIn("metadata.parameters_input_sha256", "\n".join(replay["errors"]))

    def test_replay_rejects_missing_parameter_input_digest_by_exact_field_name(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing-parameter-input-digest"
            self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            metadata_path = path / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            del metadata["parameters_input_sha256"]
            self.harness.atomic_json(metadata_path, metadata)
            self.harness.seal_directory(path)
            replay = self.replay.replay_variant(path)
        self.assertFalse(replay["passed"], replay)
        self.assertIn("metadata.parameters_input_sha256", "\n".join(replay["errors"]))

    def test_replay_rejects_missing_or_changed_case_input_digests_by_field_name(self):
        from experiments.phase5g_cases import digest_json, physical_case

        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "digest-source"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            original = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(
                original["physical_input_sha256"], digest_json(physical_case(case)),
            )
            self.assertEqual(original["case_input_sha256"], digest_json(case))
            for index, (field, operation) in enumerate((
                ("physical_input_sha256", "delete"),
                ("physical_input_sha256", "change"),
                ("case_input_sha256", "delete"),
                ("case_input_sha256", "change"),
            )):
                path = Path(temp) / f"digest-tamper-{index}"
                shutil.copytree(source, path)
                metadata_path = path / "metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if operation == "delete":
                    del metadata[field]
                else:
                    metadata[field] = "0" * 64
                self.harness.atomic_json(metadata_path, metadata)
                self.harness.seal_directory(path)
                with self.subTest(field=field, operation=operation):
                    replay = self.replay.replay_variant(path)
                    self.assertFalse(replay["passed"], replay)
                    self.assertIn(f"metadata.{field}", "\n".join(replay["errors"]))

    def test_lane_change_facts_count_both_formation_reasons_only(self):
        state0 = {
            "time_s": 0.0, "x_m": 0.0, "y_m": 1.65, "heading_rad": 0.0,
            "vx_mps": 10.0, "vy_mps": 0.0, "yaw_rate_radps": 0.0,
            "a_drive_mps2": 0.0, "steering_rad": 0.0,
        }
        state1 = {**state0, "time_s": 0.1}
        state2 = {**state0, "time_s": 0.2, "y_m": 4.95}
        plan = asdict(QuadraticLaneChange(
            start_s=0.0, y_start_m=1.65, y_target_m=4.95,
            duration_s=0.2, speed_mps=10.0,
        ))

        def records(reason):
            return [{
                "status": "completed", "initial": {"v0": state0},
                "inputs": {"v0": {"memory": {
                    "plan": None, "completed_lane_changes": 0,
                }}},
                "decisions": {"v0": {"memory": {
                    "plan": plan, "lane_change_reason": reason,
                    "completed_lane_changes": 0,
                }}},
                "steps": {"v0": {"samples": [state1], "final": state1}},
            }, {
                "status": "completed", "initial": {"v0": state2},
                "inputs": {"v0": {"memory": {
                    "plan": plan, "completed_lane_changes": 0,
                }}},
                "decisions": {"v0": {"memory": {
                    "plan": None, "lane_change_reason": "",
                    "completed_lane_changes": 1,
                }}},
                "steps": {"v0": {"samples": [state2], "final": state2}},
            }]

        self.assertEqual(
            self.harness.FORMATION_LANE_REASONS,
            frozenset({"formation_geometry", "simple_formation_balance"}),
        )
        for reason in self.harness.FORMATION_LANE_REASONS | {"slower_visible_lead"}:
            rows = records(reason)
            facts = self.harness._lane_change_facts(
                rows, {"controlled": ["v0"]},
                {"lane_width_m": 3.3},
            )
            expected = 0 if reason == "slower_visible_lead" else 1
            self.assertEqual(facts["completed_lane_changes"], 1)
            self.assertEqual(facts["formation_lane_changes"], expected)

    def test_source_hashes_bind_simple_rules_and_approved_documents(self):
        required = {
            "noa/simple_formation.py",
            "docs/superpowers/specs/2026-09-14-phase5g-simple-local-ifelse-formation-design.md",
            "docs/superpowers/plans/2026-09-14-phase5g-simple-local-ifelse-formation.md",
        }
        self.assertTrue(required.issubset(self.harness.SOURCE_FILES))
        self.assertTrue((required - {"noa/simple_formation.py"}).issubset(
            self.harness.INPUTS
        ))
        hashes = self.harness.source_hashes()
        self.assertTrue(required.issubset(hashes))
        self.assertTrue(all(len(hashes[name]) == 64 for name in required))


if __name__ == "__main__":
    unittest.main()
