"""Phase 5G paired runner, derived facts, replay, and CLI contracts."""

from copy import deepcopy
from dataclasses import asdict
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from unittest.mock import patch

from experiments import phase5g_cases
from research.common import native_io_path


ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / "tmp"
SUMMARY_KEYS = {
    "whole_cohort_formation_success", "formed_time_s", "held_time_s",
    "completed_lane_changes", "formation_lane_changes", "final_lane_counts",
    "minimum_speed_mps", "final_speed_spread_mps", "speed_recovered",
    "collision_count", "geometry_passed", "comfort_passed",
}
EXPECTED_MODES = {
    "off": {"formation_enabled": False, "formation_lane_change_enabled": False},
    "longitudinal": {"formation_enabled": True, "formation_lane_change_enabled": False},
    "lane_priority": {"formation_enabled": True, "formation_lane_change_enabled": True},
}


class _LongPathTemporaryDirectory(tempfile.TemporaryDirectory):
    """Keep test cleanup reliable for Windows snapshot paths beyond MAX_PATH."""

    @classmethod
    def _rmtree(cls, name, ignore_errors=False, repeated=False):
        shutil.rmtree(native_io_path(name), ignore_errors=ignore_errors)


class _PortableTempfile:
    TemporaryDirectory = _LongPathTemporaryDirectory


tempfile = _PortableTempfile()


def copy_tree(source, destination):
    """Copy deep snapshot fixtures through Windows extended-length paths."""
    shutil.copytree(native_io_path(source), native_io_path(destination))


class Phase5GHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TEMP_ROOT.mkdir(exist_ok=True)
        cls.harness = importlib.import_module("experiments.phase5g")
        cls.replay = importlib.import_module("experiments.phase5g_replay")

    def short_case(self, p, *, count=3, seed=101, duration_s=0.2):
        case = phase5g_cases.seeded_case(p, count, seed)
        return {**case, "duration_s": duration_s}

    def run_short_variant(self, parent, mode="lane_priority", duration_s=0.2):
        model, physical, policy = self.harness.parameters(mode)
        case = self.short_case(physical, duration_s=duration_s)
        folder = Path(parent) / mode
        result = self.harness.run_variant(
            folder, model, physical, policy, case, mode, live=False,
        )
        return folder, result

    def run_short_suite(self, parent, *, duration_s=0.1):
        case_file = Path(parent) / "development_input.json"
        self.harness.write_development_case_bundle(
            case_file, case_specs=[(3, 101)], duration_s=duration_s,
        )
        return self.harness.run_phase5g(
            case_file, base=Path(parent) / "runs", live=False, formal=False,
        )

    def test_exact_modes_and_only_registered_flags_differ(self):
        self.assertEqual(self.harness.MODES, EXPECTED_MODES)
        triples = {mode: self.harness.parameters(mode) for mode in EXPECTED_MODES}
        self.assertTrue(all(values[1]["phase5g_enabled"] is True for values in triples.values()))
        self.assertTrue(all(values[1]["r5_enabled"] is False for values in triples.values()))
        self.assertTrue(all(values[2]["r5_enabled"] is False for values in triples.values()))
        ignored = set(next(iter(EXPECTED_MODES.values())))
        physical = {
            mode: {key: value for key, value in values[1].items() if key not in ignored}
            for mode, values in triples.items()
        }
        policy = {
            mode: {key: value for key, value in values[2].items() if key not in ignored}
            for mode, values in triples.items()
        }
        self.assertEqual(len({json.dumps(value, sort_keys=True) for value in physical.values()}), 1)
        self.assertEqual(len({json.dumps(value, sort_keys=True) for value in policy.values()}), 1)
        self.assertTrue(all(
            {key: values[1][key] for key in ignored} == flags
            and {key: values[2][key] for key in ignored} == flags
            for mode, (values, flags) in {
                key: (triples[key], EXPECTED_MODES[key]) for key in EXPECTED_MODES
            }.items()
        ))

    def test_public_mode_registry_mutation_cannot_change_strict_modes(self):
        original = deepcopy({key: dict(value) for key, value in self.harness.MODES.items()})
        try:
            with self.assertRaises(TypeError):
                self.harness.MODES["rogue"] = {
                    "formation_enabled": True,
                    "formation_lane_change_enabled": True,
                }
            with self.assertRaises(TypeError):
                self.harness.MODES["off"]["formation_enabled"] = True
        finally:
            if isinstance(self.harness.MODES, dict):
                self.harness.MODES.clear()
                self.harness.MODES.update(original)
        with self.assertRaisesRegex(ValueError, "exactly off"):
            self.harness.parameters("rogue")
        self.assertEqual(self.harness.MODES, EXPECTED_MODES)

    def test_formation_lane_change_requires_active_plan_counter_and_physical_arrival(self):
        state0 = {"time_s": 0.0, "x_m": 0.0, "y_m": 1.65,
                  "heading_rad": 0.0, "vx_mps": 10.0, "vy_mps": 0.0,
                  "yaw_rate_radps": 0.0, "a_drive_mps2": 0.0, "steering_rad": 0.0}
        state1 = {**state0, "time_s": 0.1}
        state2 = {**state0, "time_s": 0.2, "y_m": 4.95}
        old_reason = [{
            "status": "completed", "initial": {"v0": state0},
            "inputs": {"v0": {"memory": {"plan": None, "completed_lane_changes": 0}}},
            "decisions": {"v0": {"memory": {"plan": None,
                "lane_change_reason": "formation_geometry", "completed_lane_changes": 0}}},
            "steps": {"v0": {"samples": [state1], "final": state1}},
        }, {
            "status": "completed", "initial": {"v0": state1},
            "inputs": {"v0": {"memory": {"plan": None, "completed_lane_changes": 0}}},
            "decisions": {"v0": {"memory": {"plan": None,
                "lane_change_reason": "", "completed_lane_changes": 0}}},
            "steps": {"v0": {"samples": [state2], "final": state2}},
        }]
        case = {"controlled": ["v0"]}
        stale = self.harness._lane_change_facts(old_reason, case, {"lane_width_m": 3.3})
        self.assertEqual(stale["formation_lane_changes"], 0)

        from models.bezier import QuadraticLaneChange
        plan = asdict(QuadraticLaneChange(
            start_s=0.0, y_start_m=1.65, y_target_m=4.95,
            duration_s=0.2, speed_mps=10.0,
        ))
        real = deepcopy(old_reason)
        real[0]["decisions"]["v0"]["memory"].update(
            plan=plan, lane_change_reason="formation_geometry")
        real[1]["inputs"]["v0"]["memory"].update(plan=plan)
        real[1]["decisions"]["v0"]["memory"].update(
            plan=None, lane_change_reason="", completed_lane_changes=1)
        real[1]["initial"]["v0"] = state2
        facts = self.harness._lane_change_facts(real, case, {"lane_width_m": 3.3})
        self.assertEqual(facts["formation_lane_changes"], 1)
        self.assertEqual(facts["completed_lane_changes"], 1)
        same_lane = deepcopy(real)
        same_plan = asdict(QuadraticLaneChange(
            start_s=0.0, y_start_m=1.65, y_target_m=1.65,
            duration_s=0.2, speed_mps=10.0,
        ))
        same_lane[0]["decisions"]["v0"]["memory"]["plan"] = same_plan
        same_lane[1]["inputs"]["v0"]["memory"]["plan"] = same_plan
        same_lane[1]["initial"]["v0"] = state0
        same = self.harness._lane_change_facts(same_lane, case, {"lane_width_m": 3.3})
        self.assertEqual(same["completed_lane_changes"], 0)
        self.assertEqual(same["formation_lane_changes"], 0)

    def test_runner_binds_approved_design_plan_cli_and_research_inputs(self):
        for name in (
            "run.py",
            "docs/superpowers/specs/2026-09-14-phase5g-pure-formation-design.md",
            "docs/superpowers/plans/2026-09-14-phase5g-pure-formation.md",
        ):
            with self.subTest(name=name):
                self.assertIn(name, self.harness.SOURCE_FILES + self.harness.INPUTS)

    def test_target_speed_and_mode_validation_precede_run_record_creation(self):
        invalid = (None, True, 0, "LANE_PRIORITY", "", [], {})
        for mode in invalid:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.harness.parameters(mode)
        for speed in (True, 0.0, -1.0, float("nan"), float("inf"), 10**10000, 100.0):
            with self.subTest(speed=speed), self.assertRaisesRegex(ValueError, "target_speed_mps"):
                self.harness.parameters("off", speed)
        with patch.object(self.harness, "RunRecord") as record:
            with self.assertRaises(ValueError):
                self.harness.run_phase5g("missing.json", mode_registry={"bad": {}})
            record.assert_not_called()

    def test_variant_summary_has_exact_public_keys_and_replays_all_layers(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            folder, result = self.run_short_variant(temp)
            self.assertEqual(set(result["summary"]), SUMMARY_KEYS)
            report = self.replay.replay_variant(folder)
            self.assertTrue(report["passed"], report)
            self.assertTrue(report["decision_replay_passed"])
            self.assertTrue(report["integration_replay_passed"])
            self.assertTrue(report["detection_replay_passed"])
            self.assertTrue(report["lane_change_replay_passed"])
            self.assertTrue(report["speed_recovery_replay_passed"])
            self.assertTrue(report["acceptance_replay_passed"])

    def test_failed_variant_retains_completed_prefix_failed_tail_and_replays_it(self):
        model, physical, policy = self.harness.parameters("lane_priority")
        case = self.short_case(physical, duration_s=0.3)
        original = type(model).advance
        calls = {"count": 0}

        def fail_second_interval(instance, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == len(case["controlled"]) + 1:
                raise RuntimeError("injected integration boundary")
            return original(instance, *args, **kwargs)

        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            folder = Path(temp) / "partial"
            with patch.object(type(model), "advance", fail_second_interval):
                result = self.harness.run_variant(
                    folder, model, physical, policy, case, "lane_priority", live=False,
                )
            self.assertEqual(result["status"], "failed")
            metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in (folder / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(metadata["trace_intervals"], 2)
            self.assertEqual(metadata["completed_intervals"], 1)
            self.assertEqual([row["status"] for row in rows], ["completed", "failed"])
            report = self.replay.replay_variant(folder)
            self.assertTrue(report["passed"], report)
            self.assertTrue(report["partial_source"])

    def test_failure_before_first_tick_replays_only_the_empty_produced_prefix(self):
        model, physical, policy = self.harness.parameters("lane_priority")
        case = self.short_case(physical, duration_s=0.15)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            folder = Path(temp) / "empty_prefix"
            result = self.harness.run_variant(
                folder, model, physical, policy, case, "lane_priority", live=False,
            )
            self.assertEqual(result["status"], "failed")
            metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["trace_intervals"], 0)
            report = self.replay.replay_variant(folder)
            self.assertTrue(report["passed"], report)
            self.assertEqual(report["trace"]["intervals"], 0)
            self.assertTrue(report["partial_source"])

    def test_resealed_semantic_tampering_names_exact_path(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            source, _ = self.run_short_variant(temp)
            actor = phase5g_cases.seeded_case(
                self.harness.parameters("lane_priority")[1], 3, 101
            )["controlled"][0]
            mutations = {
                "mode": ("metadata.json", lambda value: value.__setitem__("mode", "off"), "metadata.mode"),
                "config": ("metadata.json", lambda value: value["parameters"].__setitem__("formation_enabled", False), "metadata.parameters.formation_enabled"),
                "source": ("metadata.json", lambda value: value["source_hashes"].__setitem__("noa/controller.py", "0" * 64), "metadata.source_hashes.noa/controller.py"),
                "memory": ("trace.jsonl", lambda value: value[0]["inputs"][actor]["memory"].__setitem__("formation_lane_draw_count", 7), f"trace[0].inputs.{actor}.memory"),
                "action": ("trace.jsonl", lambda value: value[0]["actions"][actor].__setitem__("acceleration_mps2", 0.123), f"trace[0].actions.{actor}.acceleration_mps2"),
                "detection": ("detection.json", lambda value: value["default"].__setitem__("whole_cohort_success", not value["default"]["whole_cohort_success"]), "detection.default.whole_cohort_success"),
            }
            for name, (relative, mutate, expected_path) in mutations.items():
                with self.subTest(name=name):
                    changed = Path(temp) / ("tampered_" + name)
                    copy_tree(source, changed)
                    path = changed / relative
                    if relative.endswith(".jsonl"):
                        value = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                        mutate(value)
                        path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in value), encoding="utf-8")
                    else:
                        value = json.loads(path.read_text(encoding="utf-8"))
                        mutate(value)
                        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                    self.harness.seal_directory(changed)
                    report = self.replay.replay_variant(changed)
                    self.assertFalse(report["passed"])
                    self.assertIn(expected_path, "\n".join(report["errors"]))

    def test_variant_acceptance_fields_are_independently_recomputed(self):
        fields = ("passed", "recording_passed", "driving_passed",
                  "comfort_passed", "status")
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            source, _ = self.run_short_variant(temp)
            for field in fields:
                with self.subTest(field=field):
                    changed = Path(temp) / f"acceptance_{field}"
                    copy_tree(source, changed)
                    validation = changed / "validation.json"
                    value = json.loads(validation.read_text(encoding="utf-8"))
                    original = value[field]
                    value[field] = ("failed" if original == "completed" else "completed") \
                        if field == "status" else not original
                    validation.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
                    self.harness.seal_directory(changed)
                    report = self.replay.replay_variant(changed)
                    self.assertFalse(report["passed"])
                    self.assertIn(f"validation.{field}", "\n".join(report["errors"]))

            partial = Path(temp) / "partial_source"
            model, physical, policy = self.harness.parameters("lane_priority")
            case = self.short_case(physical, duration_s=0.15)
            self.harness.run_variant(
                partial, model, physical, policy, case, "lane_priority", live=False,
            )
            validation = partial / "validation.json"
            value = json.loads(validation.read_text(encoding="utf-8"))
            self.assertFalse(value["recording_passed"])
            value["recording_passed"] = True
            validation.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
            self.harness.seal_directory(partial)
            report = self.replay.replay_variant(partial)
            self.assertFalse(report["passed"])
            self.assertIn("validation.recording_passed", "\n".join(report["errors"]))

    def test_resealed_whole_variant_swap_is_rejected_against_frozen_input(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            source = self.run_short_suite(temp)
            cases = source / "cases"
            left = cases / "main_6_3_2_1_off"
            right = cases / "seeded_3_seed101_off"
            staging = cases / "swap_staging"
            left.rename(staging)
            right.rename(left)
            staging.rename(right)
            gate_path = source / "validation.json"
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            gate["variants"]["main_6_3_2_1_off"], gate["variants"]["seeded_3_seed101_off"] = (
                gate["variants"]["seeded_3_seed101_off"],
                gate["variants"]["main_6_3_2_1_off"],
            )
            gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
            self.harness.seal_directory(left)
            self.harness.seal_directory(right)
            self.harness.seal_directory(source)
            report = self.replay.replay_run(source, base=Path(temp) / "replays")
            self.assertFalse(report["passed"])
            self.assertIn("cases.main_6_3_2_1_off.metadata.case.name",
                          "\n".join(report["errors"]))

    def test_outer_acceptance_fields_are_recomputed_after_full_reseal(self):
        mutations = {
            "status": "failed", "complete_execution": False,
            "passed": True, "engineering_passed": False,
            "scientific_gate_passed": True, "retained_partial_package": True,
        }
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            source = self.run_short_suite(temp)
            original_anchor_path = source.parent / ".phase5g-trust" / f"{source.name}.json"
            original_anchor = json.loads(original_anchor_path.read_text(encoding="utf-8"))
            roots = {
                "expected_source_sha256": original_anchor["source_manifest_sha256"],
                "expected_input_sha256": original_anchor["input_manifest_sha256"],
            }
            for field, replacement in mutations.items():
                with self.subTest(field=field):
                    changed = source.parent / f"outer_{field}"
                    copy_tree(source, changed)
                    anchor = {**original_anchor, "run_id": changed.name}
                    anchor_path = changed.parent / ".phase5g-trust" / f"{changed.name}.json"
                    anchor_path.write_text(json.dumps(anchor, sort_keys=True,
                                                      separators=(",", ":")) + "\n",
                                           encoding="utf-8")
                    validation = changed / "validation.json"
                    value = json.loads(validation.read_text(encoding="utf-8"))
                    self.assertNotEqual(value[field], replacement)
                    value[field] = replacement
                    validation.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
                    self.harness.seal_directory(changed)
                    report = self.replay.replay_run(
                        changed, base=Path(temp) / "replays", **roots,
                    )
                    self.assertFalse(report["passed"])
                    self.assertIn(f"validation.{field}", "\n".join(report["errors"]))

    def test_fresh_isolated_process_replays_saved_snapshot_after_runner_exit(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            case_file = Path(temp) / "development_input.json"
            self.harness.write_development_case_bundle(
                case_file, case_specs=[(3, 101)], duration_s=0.1,
            )
            purelib = sysconfig.get_path("purelib")
            generate = (
                "import sys;from pathlib import Path;"
                f"sys.path.insert(0,{str(ROOT)!r});sys.path.append({purelib!r});"
                "from experiments.phase5g import run_phase5g;"
                f"run_phase5g(Path({str(case_file)!r}),base=Path({str(Path(temp) / 'runs')!r}),"
                "live=False,formal=False)"
            )
            made = subprocess.run([sys.executable, "-I", "-B", "-S", "-c", generate],
                                  cwd=ROOT, capture_output=True, text=True, check=True)
            source = Path(json.loads(made.stdout.splitlines()[-1])["path"])
            replay_code = (
                "import json,sys;from pathlib import Path;"
                f"sys.path.insert(0,{str(ROOT)!r});sys.path.append({purelib!r});"
                "from experiments.phase5g_replay import replay_run;"
                f"r=replay_run(Path({str(source)!r}),base=Path({str(Path(temp) / 'replays')!r}));"
                "print(json.dumps(r))"
            )
            checked = subprocess.run([sys.executable, "-I", "-B", "-S", "-c", replay_code],
                                     cwd=ROOT, capture_output=True, text=True, check=True)
            report = json.loads(checked.stdout.splitlines()[-1])
            self.assertTrue(report["semantic_replay_passed"], report)

    def test_top_replay_does_not_call_current_worktree_variant_replayer(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            source = self.run_short_suite(temp)
            with patch.object(self.replay, "replay_variant",
                              side_effect=AssertionError("current worktree sentinel")):
                report = self.replay.replay_run(source, base=Path(temp) / "replays")
            self.assertTrue(report["semantic_replay_passed"], report)

    def test_external_anchor_rejects_resealed_source_and_input_snapshot_tampering(self):
        mutations = (
            ("source", "code_hashes.noa/controller.py"),
            ("input", "input_hashes.phase5g_cases.json"),
        )
        for kind, expected_path in mutations:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
                source = self.run_short_suite(temp)
                if kind == "source":
                    changed = source / "code_snapshot" / "noa" / "controller.py"
                    changed.write_text(changed.read_text(encoding="utf-8") + "\n# resealed attack\n",
                                       encoding="utf-8")
                    hashes_path = source / "code_hashes.json"
                else:
                    changed = source / "input_snapshot" / "phase5g_cases.json"
                    value = json.loads(changed.read_text(encoding="utf-8"))
                    value["cases"][0]["purpose"] = "resealed attack"
                    changed.write_bytes(phase5g_cases.canonical_json_bytes(value))
                    hashes_path = source / "input_hashes.json"
                hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
                relative = changed.relative_to(
                    source / ("code_snapshot" if kind == "source" else "input_snapshot")
                ).as_posix()
                from research.common import sha256
                hashes[relative] = sha256(changed)
                hashes_path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
                self.harness.seal_directory(source)
                report = self.replay.replay_run(source, base=Path(temp) / "replays")
                self.assertFalse(report["passed"])
                self.assertIn(expected_path, "\n".join(report["errors"]))

    def test_unregistered_snapshot_module_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            source = self.run_short_suite(temp)
            anchor_path = source.parent / ".phase5g-trust" / f"{source.name}.json"
            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
            marker = Path(temp) / "malicious-import-marker.txt"
            attack = source / "code_snapshot" / "sysconfig.py"
            attack.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('imported', encoding='utf-8')\n",
                encoding="utf-8",
            )
            self.harness.seal_directory(source)
            report = self.replay.replay_run(
                source, base=Path(temp) / "replays",
                expected_source_sha256=anchor["source_manifest_sha256"],
                expected_input_sha256=anchor["input_manifest_sha256"],
            )
            self.assertFalse(report["passed"])
            self.assertIn("code_snapshot unexpected file: sysconfig.py",
                          "\n".join(report["errors"]))
            self.assertFalse(marker.exists(), "unregistered module was imported")

    def test_lifecycle_failures_finalize_and_replay_only_produced_evidence(self):
        stages = ("evaluation", "derived.detection", "acceptance")
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
                model, physical, policy = self.harness.parameters("lane_priority")
                case = self.short_case(physical, duration_s=0.1)
                folder = Path(temp) / stage.replace(".", "_")
                original_atomic = self.harness.atomic_json

                def injected_atomic(path, data):
                    if stage == "derived.detection" and Path(path).name == "detection.json":
                        raise RuntimeError("injected derived persistence failure")
                    return original_atomic(path, data)

                patches = []
                if stage == "evaluation":
                    patches.append(patch.object(
                        self.harness, "evaluate_records",
                        side_effect=RuntimeError("injected evaluation failure")))
                elif stage == "derived.detection":
                    patches.append(patch.object(self.harness, "atomic_json",
                                                side_effect=injected_atomic))
                else:
                    patches.append(patch.object(
                        self.harness, "variant_acceptance",
                        side_effect=RuntimeError("injected acceptance failure")))
                with patches[0]:
                    try:
                        result = self.harness.run_variant(
                            folder, model, physical, policy, case,
                            "lane_priority", live=False,
                        )
                    except RuntimeError:
                        result = None
                self.assertIsNotNone(result, "ordinary lifecycle failure escaped finalization")
                saved = json.loads((folder / "validation.json").read_text(encoding="utf-8"))
                self.assertEqual(saved["status"], "failed")
                self.assertEqual(saved["failure_stage"], stage)
                self.assertEqual(saved["case_index"], {
                    "case_name": case["name"], "mode": "lane_priority"})
                self.assertIn("trace.jsonl", saved["produced_evidence"])
                self.assertTrue((folder / "evidence_hashes.json").is_file())
                replay = self.replay.replay_variant(folder)
                self.assertTrue(replay["passed"], replay)
                self.assertTrue(replay["partial_source"])

    def test_child_seal_failure_is_parent_bound_and_semantically_replayable(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            original = self.harness.seal_directory
            injected = {"done": False}

            def fail_first_child(path):
                candidate = Path(path)
                if not injected["done"] and candidate.parent.name == "cases":
                    injected["done"] = True
                    raise RuntimeError("injected child seal failure")
                return original(path)

            with patch.object(self.harness, "seal_directory", side_effect=fail_first_child):
                source = self.run_short_suite(temp)
            index = json.loads((source / "case_index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["unsealed_variants"]), 1)
            child = source / "cases" / index["unsealed_variants"][0]
            self.assertTrue((child / "unsealed_evidence_hashes.json").is_file())
            self.assertFalse((child / "validation.json").read_text(encoding="utf-8").find(
                '"failure_stage": "sealing"') < 0)
            replay = self.replay.replay_run(source, base=Path(temp) / "replays")
            self.assertTrue(replay["semantic_replay_passed"], replay)
            self.assertFalse(replay["complete_execution"])

    def test_sync_failure_metadata_counts_only_committed_physics_and_replays(self):
        from models.geometry import to_sumo_pose
        from simulation.external_bridge import audit_readback

        class Connection:
            def getVersion(self):
                return (0, "fake")

            def close(self):
                return None

        for phase, expected_physical in (("precommit", 0), ("commit", 0),
                                         ("postcommit", 1)):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
                model, physical, policy = self.harness.parameters("lane_priority")
                case = self.short_case(physical, duration_s=0.1)
                error_text = f"RuntimeError: injected sync {phase} fault"

                class Bridge:
                    time_offset = 0.0
                    readback_phase = "bootstrap"
                    last_reports = {}
                    advances = 0

                    def synchronize(self, steps):
                        self.readback_phase = phase
                        keys = sorted(steps)
                        if phase == "commit":
                            self.last_reports = {}
                        else:
                            self.last_reports = {}
                            reference_final = phase == "postcommit"
                            for index, key in enumerate(keys):
                                if index == 0:
                                    state = steps[key].final if reference_final else steps[key].initial
                                    speed = model.observe(state)["speed_mps"]
                                    x, y, angle = to_sumo_pose(state, model.p["length_m"])
                                    raw = {
                                        "sumo_time_s": state.time_s, "front_x_m": x,
                                        "front_y_m": y, "angle_deg": angle,
                                        "speed_mps": speed, "acceleration_mps2": (
                                            (speed - model.observe(steps[key].initial)["speed_mps"])
                                            / physical["control_sync_dt_s"]
                                            if reference_final else 0.0),
                                        "edge_id": "upstream", "lane_id": "upstream_0",
                                        "lane_index": 0, "colliding_vehicle_reports": 0,
                                        "teleport_starts": 0,
                                    }
                                    self.last_reports[key] = audit_readback(
                                        raw, state, model, 0.0,
                                        raw["acceleration_mps2"] if reference_final else None)
                                elif index == 1:
                                    self.last_reports[key] = {
                                        "passed": False, "status": "readback_exception",
                                        "errors": [error_text],
                                    }
                                else:
                                    self.last_reports[key] = {
                                        "passed": False, "status": "not_read",
                                        "errors": ["Readback not reached"],
                                    }
                        if phase == "postcommit":
                            self.advances += 1
                        raise RuntimeError(f"injected sync {phase} fault")

                bridge = Bridge()
                with patch.object(self.harness, "bootstrap",
                                  return_value=(Connection(), bridge)):
                    folder = Path(temp) / phase
                    result = self.harness.run_variant(
                        folder, model, physical, policy, case,
                        "lane_priority", live=True,
                    )
                metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(result["status"], "failed")
                self.assertEqual(metadata["failure_phase"], phase)
                self.assertIs(metadata["commit_applied"], phase == "postcommit")
                self.assertEqual(metadata["physical_intervals"], expected_physical)
                self.assertEqual(set(metadata["failure_readback_states"]), set(case["initial"]))
                self.assertEqual(sum(len(v) for v in metadata["readback_coverage"].values()),
                                 len(case["initial"]))
                replay = self.replay.replay_variant(folder)
                self.assertTrue(replay["passed"], replay)
                changed = Path(temp) / f"{phase}_tamper"
                copy_tree(folder, changed)
                changed_meta = json.loads((changed / "metadata.json").read_text(encoding="utf-8"))
                changed_meta["commit_applied"] = not changed_meta["commit_applied"]
                (changed / "metadata.json").write_text(
                    json.dumps(changed_meta, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                self.harness.seal_directory(changed)
                rejected = self.replay.replay_variant(changed)
                self.assertFalse(rejected["passed"])
                self.assertIn("metadata.commit_applied", "\n".join(rejected["errors"]))

    def test_speed_recovery_covers_every_saved_hold_window_frame(self):
        controlled = [f"v{i}" for i in range(6)]
        case = {"controlled": controlled}

        def records(speed_by_time):
            rows = []
            for time in range(13):
                def state(at, speed):
                    return {"time_s": float(at), "x_m": float(at) * speed,
                            "y_m": 1.65, "heading_rad": 0.0,
                            "vx_mps": speed, "vy_mps": 0.0,
                            "yaw_rate_radps": 0.0, "a_drive_mps2": 0.0,
                            "steering_rad": 0.0}
                initial = {key: state(time, speed_by_time.get(time, 10.0))
                           for key in controlled}
                final = {key: state(time + 1, speed_by_time.get(time + 1, 10.0))
                         for key in controlled}
                rows.append({"status": "completed", "initial": initial,
                             "steps": {key: {"samples": [final[key]],
                                              "final": final[key]}
                                       for key in controlled}})
            return rows

        good = self.harness._speed_facts(
            records({0: 0.0}), case, 10.0, 1.0,
            formed_time_s=2.0, held_time_s=12.0)
        self.assertTrue(good["speed_recovered"])
        self.assertEqual(good["hold_window"]["minimum_speed_mps"], 10.0)
        stopped_hold = self.harness._speed_facts(
            records({5: 0.0}), case, 10.0, 1.0,
            formed_time_s=2.0, held_time_s=12.0)
        self.assertFalse(stopped_hold["speed_recovered"])
        self.assertEqual(stopped_hold["final_speeds_mps"], [10.0] * 6)
        insufficient = self.harness._speed_facts(
            records({}), case, 10.0, 1.0,
            formed_time_s=5.0, held_time_s=None)
        self.assertFalse(insufficient["speed_recovered"])

    def test_expected_variants_bind_identical_physics_and_three_modes(self):
        model, physical, _ = self.harness.parameters("off")
        cases = [self.short_case(physical)]
        variants = self.harness.expected_variants(cases)
        self.assertEqual(list(variants), [
            cases[0]["name"] + "_off",
            cases[0]["name"] + "_longitudinal",
            cases[0]["name"] + "_lane_priority",
        ])
        self.assertEqual({spec["mode"] for spec in variants.values()}, set(EXPECTED_MODES))
        self.assertEqual(len({spec["physical_input_sha256"] for spec in variants.values()}), 1)

    def test_completed_matrix_may_truthfully_include_a_failed_execution_variant(self):
        expected = {name: {} for name in ("a_off", "a_longitudinal", "a_lane_priority")}
        started = list(expected)
        finalized = list(expected)
        completed = started[:2]
        self.replay.validate_execution_index(
            expected, started, finalized, completed, partial=False,
        )

    def test_partial_semantic_replay_is_not_complete_or_an_aggregate_pass(self):
        expected = {name: {} for name in (
            "main_6_3_2_1_off", "main_6_3_2_1_longitudinal",
            "main_6_3_2_1_lane_priority",
        )}
        cases = [
            {"case": "main_6_3_2_1_off", "passed": True,
             "partial_source": True, "scientific_passed": None},
            {"case": "main_6_3_2_1_longitudinal", "passed": True,
             "partial_source": False, "scientific_passed": None},
            {"case": "main_6_3_2_1_lane_priority", "passed": True,
             "partial_source": False, "scientific_passed": True},
        ]
        result = self.replay.aggregate_replay_results(expected, cases)
        self.assertTrue(result["semantic_replay_passed"])
        self.assertFalse(result["complete_execution"])
        self.assertFalse(result["execution_gate_passed"])
        self.assertFalse(result["passed"])
        produced_prefix = self.replay.aggregate_replay_results(expected, cases[:1])
        self.assertTrue(produced_prefix["semantic_replay_passed"])
        self.assertFalse(produced_prefix["complete_execution"])
        self.assertFalse(produced_prefix["passed"])
        factual_failure = [
            {**row, "execution_completed": True, "source_passed": index != 0,
             "partial_source": False}
            for index, row in enumerate(cases)
        ]
        complete_but_failed = self.replay.aggregate_replay_results(expected, factual_failure)
        self.assertTrue(complete_but_failed["complete_execution"])
        self.assertFalse(complete_but_failed["execution_gate_passed"])
        self.assertFalse(complete_but_failed["passed"])

    def test_output_base_rejects_dangerous_paths_before_run_record(self):
        dangerous = ("", "   ", ".", str(ROOT), str(ROOT.parent),
                     str(ROOT / "experiments"), str(ROOT / "run.py"), "C:\\")
        for value in dangerous:
            with self.subTest(value=value), patch.object(self.harness, "RunRecord") as record:
                with self.assertRaisesRegex(ValueError, "output_base"):
                    self.harness.run_phase5g_demo(
                        vehicle_count=3, seed=1, target_speed_mps=10.0,
                        duration_s=0.1, output_base=value, live=False,
                    )
                record.assert_not_called()
        allowed = self.harness._validated_output_base(ROOT / "tmp" / "safe_task6")
        self.assertEqual(allowed, (ROOT / "tmp" / "safe_task6").resolve())
        with tempfile.TemporaryDirectory() as external:
            result = self.harness.run_phase5g_demo(
                vehicle_count=3, seed=1, target_speed_mps=10.0,
                duration_s=0.1, output_base=Path(external) / "phase5g", live=False,
            )
            self.assertTrue(result.is_relative_to(Path(external)))

    def test_formal_runner_rejects_development_bundle_even_with_formal_filename(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            case_file = Path(temp) / "phase5g_cases_frozen.json"
            self.harness.write_development_case_bundle(
                case_file, case_specs=[(3, 101)], duration_s=0.1,
            )
            with patch.object(self.harness, "RunRecord") as record:
                with self.assertRaisesRegex(ValueError, "formal.*frozen"):
                    self.harness.run_phase5g(case_file, base=Path(temp) / "runs",
                                             live=False, formal=True)
                record.assert_not_called()

    def test_parent_manifest_includes_nested_variant_manifest(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            parent = Path(temp) / "parent"
            child = parent / "cases" / "child"
            child.mkdir(parents=True)
            (child / "trace.jsonl").write_text("{}\n", encoding="utf-8")
            self.harness.seal_directory(child)
            self.harness.seal_directory(parent)
            hashes = json.loads((parent / "evidence_hashes.json").read_text(encoding="utf-8"))
            self.assertIn("cases/child/evidence_hashes.json", hashes)
            self.assertEqual(self.replay._manifest_differences(parent), [])

    def test_scientific_hold_is_ten_seconds_after_confirmation_timestamp(self):
        case = {"name": "main_6_3_2_1", "controlled": [f"v{i}" for i in range(6)]}
        summary = {
            "whole_cohort_formation_success": True, "formed_time_s": 25.0,
            "held_time_s": 34.9, "completed_lane_changes": 1,
            "formation_lane_changes": 1, "final_lane_counts": [2, 2, 2],
            "minimum_speed_mps": 9.0, "final_speed_spread_mps": 0.1,
            "speed_recovered": True, "collision_count": 0,
            "geometry_passed": True, "comfort_passed": True,
        }
        self.assertFalse(self.harness.scientific_gate(
            case, "lane_priority", summary, execution_completed=True,
            speed_recovery={"speed_recovered": True},
        ))
        summary["held_time_s"] = 35.0
        self.assertTrue(self.harness.scientific_gate(
            case, "lane_priority", summary, execution_completed=True,
            speed_recovery={"speed_recovered": True},
        ))
        self.assertFalse(self.harness.scientific_gate(
            case, "lane_priority", summary, execution_completed=True,
            speed_recovery={"speed_recovered": False},
        ))
        summary["final_speed_spread_mps"] = 1.1
        self.assertFalse(self.harness.scientific_gate(
            case, "lane_priority", summary, execution_completed=True,
            speed_recovery={"speed_recovered": True},
        ))


class Phase5GCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = importlib.import_module("run")

    def call(self, argv):
        with patch.object(sys, "argv", ["run.py", *argv]):
            return self.entry.main()

    def test_phase5g_and_replay_require_explicit_paths_before_runner_call(self):
        for argv in (("phase5g",), ("phase5g-formal",), ("phase5g-replay",)):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                self.call(list(argv))

    def test_standalone_replay_forwards_optional_caller_trust_roots_as_a_pair(self):
        source_hash = "a" * 64
        input_hash = "b" * 64
        with patch("experiments.phase5g_replay.replay_run",
                   return_value={"passed": True}) as replay:
            with self.assertRaises(SystemExit) as exited:
                self.call(["phase5g-replay", "--run-dir", "saved-run",
                           "--expected-source-sha256", source_hash,
                           "--expected-input-sha256", input_hash])
        self.assertEqual(exited.exception.code, 0)
        replay.assert_called_once_with(
            "saved-run", expected_source_sha256=source_hash,
            expected_input_sha256=input_hash,
        )
        with patch("experiments.phase5g_replay.replay_run") as replay:
            with self.assertRaises(SystemExit):
                self.call(["phase5g-replay", "--run-dir", "saved-run",
                           "--expected-source-sha256", source_hash])
            replay.assert_not_called()

    def test_formal_calls_runner_once_and_replays_literal_returned_path(self):
        literal = Path("literal-returned-run")
        replay_result = {"passed": True, "scientific_gate_passed": True}
        anchors = {"expected_source_sha256": "1" * 64,
                   "expected_input_sha256": "2" * 64}
        with patch("experiments.phase5g.expected_replay_anchors",
                   return_value=anchors) as bind, patch(
            "experiments.phase5g.run_phase5g", return_value=literal) as run, patch(
            "experiments.phase5g_replay.replay_run", return_value=replay_result
        ) as replay:
            result = self.call(["phase5g-formal", "--case-file", "frozen.json"])
        self.assertIsNone(result)
        bind.assert_called_once_with("frozen.json")
        run.assert_called_once()
        replay.assert_called_once()
        self.assertIs(replay.call_args.args[0], literal)
        self.assertEqual(replay.call_args.kwargs, anchors)

    def test_formal_nonzero_on_replay_or_scientific_gate_failure(self):
        for replay_result in (
            {"passed": False, "scientific_gate_passed": True},
            {"passed": True, "scientific_gate_passed": False},
        ):
            with self.subTest(replay_result=replay_result), patch(
                "experiments.phase5g.expected_replay_anchors",
                return_value={"expected_source_sha256": "1" * 64,
                              "expected_input_sha256": "2" * 64},
            ), patch(
                "experiments.phase5g.run_phase5g", return_value=Path("literal")
            ), patch("experiments.phase5g_replay.replay_run", return_value=replay_result):
                with self.assertRaisesRegex(SystemExit, "1"):
                    self.call(["phase5g-formal", "--case-file", "frozen.json"])

    def test_demo_validates_arguments_and_runs_only_lane_priority_nonformal(self):
        invalid = (
            ["phase5g-demo", "--vehicle-count", "5"],
            ["phase5g-demo", "--vehicle-count", "6", "--target-speed-mps", "nan"],
            ["phase5g-demo", "--vehicle-count", "6", "--duration-s", "0"],
        )
        for argv in invalid:
            with self.subTest(argv=argv), patch("experiments.phase5g.run_phase5g_demo") as demo:
                with self.assertRaises(SystemExit):
                    self.call(argv)
                demo.assert_not_called()
        with patch("experiments.phase5g.run_phase5g_demo", return_value=Path("demo-run")) as demo:
            self.call(["phase5g-demo", "--vehicle-count", "6", "--seed", "1",
                       "--target-speed-mps", "10", "--duration-s", "45",
                       "--output-base", "results/test-demo"])
        kwargs = demo.call_args.kwargs
        self.assertEqual(kwargs["mode"], "lane_priority")
        self.assertFalse(kwargs["formal"])


if __name__ == "__main__":
    unittest.main()
