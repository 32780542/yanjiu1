"""Phase 5F mode, input, matrix, and semantic replay binding."""

import copy
import inspect
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from experiments import phase5_r5 as harness
from experiments import phase5c_cases as extension
from experiments.phase5 import _seal
from experiments.records import atomic_json
from research.common import ROOT, read_json


class Phase5FHarnessTests(unittest.TestCase):
    def require_api(self):
        for function in (harness.parameters, harness.expected_variants, harness.run_phase5_r5):
            self.assertIn("lane_change_policy", inspect.signature(function).parameters)

    def test_explicit_mode_and_fixed_parameter_compatibility(self):
        self.require_api()
        parent = harness.parameters(True)
        fixed = harness.parameters(True, lane_change_policy="fixed")
        self.assertEqual(dict(fixed[0].p), dict(parent[0].p))
        self.assertEqual(fixed[1:], parent[1:])
        model, p, policy = harness.parameters(True, lane_change_policy="adaptive_duration")
        self.assertEqual(dict(model.p), dict(parent[0].p))
        new_p = {key: value for key, value in p.items() if key not in parent[1]}
        new_policy = {key: value for key, value in policy.items() if key not in parent[2]}
        expected = {
            "phase5f_enabled": True,
            "phase5f_duration_candidates_s": [5.0, 7.5, 10.0],
        }
        self.assertEqual(new_p, expected)
        self.assertEqual(new_policy, expected)
        self.assertEqual({key: p[key] for key in parent[1]}, parent[1])
        self.assertEqual({key: policy[key] for key in parent[2]}, parent[2])

    def test_adaptive_mode_is_not_applied_to_r5_off_or_priority_waiting(self):
        self.require_api()
        for enabled, lane in ((False, True), (False, False), (True, False)):
            with self.subTest(enabled=enabled, lane=lane):
                adaptive = harness.parameters(
                    enabled, lane_priority=lane, lane_change_policy="adaptive_duration"
                )
                fixed = harness.parameters(
                    enabled, lane_priority=lane, lane_change_policy="fixed"
                )
                self.assertEqual(dict(adaptive[0].p), dict(fixed[0].p))
                self.assertEqual(adaptive[1:], fixed[1:])

    def test_bad_lane_change_modes_are_rejected_even_when_r5_is_disabled(self):
        self.require_api()
        for bad in (None, True, 1, "", "adaptive", "Adaptive_Duration", [], {}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                harness.parameters(False, lane_change_policy=bad)

    def test_exact_extension_matrix_marks_only_r5_lane_priority_variants(self):
        self.require_api()
        cases = extension.build_cases(dict(harness.parameters(False)[0].p))
        fixed = harness.expected_variants(cases, True, lane_change_policy="fixed")
        adaptive = harness.expected_variants(cases, True, lane_change_policy="adaptive_duration")
        self.assertEqual(len(fixed), 6)
        self.assertEqual(list(adaptive), list(fixed))
        for name, spec in fixed.items():
            wanted = {**spec}
            if spec["r5_enabled"] and spec.get("lane_priority_enabled", True):
                wanted["lane_change_policy"] = "adaptive_duration"
            self.assertEqual(adaptive[name], wanted)

    def test_phase5f_sources_are_bound_experiment_inputs(self):
        for name in (
            "configs/phase5f.json",
            "docs/phase5f_adaptive_duration_plan.md",
            "docs/superpowers/specs/2026-09-13-phase5f-adaptive-duration-design.md",
            "docs/superpowers/plans/2026-09-13-phase5f-adaptive-duration.md",
        ):
            self.assertIn(name, harness.INPUTS)

    def test_offline_roundtrip_and_resealed_top_mode_mutation_is_rejected(self):
        self.require_api()
        from experiments.phase5_r5_replay import replay_run

        model_parameters = dict(harness.parameters(False)[0].p)
        cases = [{**case, "duration_s": 0.2} for case in extension.build_cases(model_parameters)]
        (ROOT / "tmp").mkdir(exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="phase5f_mode_unit_", dir=ROOT / "tmp"))
        with patch.object(extension, "build_cases", side_effect=lambda *args: copy.deepcopy(cases)):
            frozen = folder / "unit_cases.json"
            extension.freeze_cases(frozen, model_parameters)
            source = harness.run_phase5_r5(
                frozen,
                base=folder / "runs",
                live=False,
                sampling=False,
                lane_change_policy="adaptive_duration",
            )
            replay = replay_run(source, base=folder / "replays")
            self.assertTrue(replay["passed"], replay)
            self.assertEqual(len(replay["cases"]), 5)
            self.assertEqual(read_json(source / "metadata.json")["lane_change_policy"],
                             "adaptive_duration")
            index = read_json(source / "case_index.json")["expected_variants"]
            for name, spec in index.items():
                metadata = read_json(source / "cases" / name / "metadata.json")
                self.assertEqual(
                    metadata["policy_parameters"].get("phase5f_enabled", False),
                    spec.get("lane_change_policy", "fixed") == "adaptive_duration",
                )

            altered = folder / "mutated_top_mode" / source.name
            shutil.copytree(source, altered)
            metadata = read_json(altered / "metadata.json")
            metadata["lane_change_policy"] = "fixed"
            atomic_json(altered / "metadata.json", metadata)
            _seal(altered)
            rejected = replay_run(altered, base=folder / "mutated_replays")
            self.assertFalse(rejected["passed"])
            self.assertTrue(rejected["errors"])


if __name__ == "__main__":
    unittest.main()
