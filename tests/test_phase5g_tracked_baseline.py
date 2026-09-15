"""Acceptance tests for the deliberately enumerated Phase 5G Git closure."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "scripts" / "audit_runtime_closure.py"
ENTRIES = ("runrun.py", "variants/phase5g_pure_formation/run.py")
LAUNCHERS = (
    "variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py",
    "variants/phase5g_pure_formation/tests/phase5g_test_launcher.py",
)


def _audit_module():
    if not AUDIT_PATH.is_file():
        raise AssertionError(f"missing closure auditor: {AUDIT_PATH.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location("phase5g_runtime_closure", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load closure auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repository_baseline_files(root: Path) -> set[str]:
    """Use Git in a checkout and the actual file tree in a source archive."""
    if (root / ".git").exists():
        raw = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        return {
            item.decode("utf-8").replace("\\", "/")
            for item in raw.split(b"\0")
            if item
        }
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


class Phase5GTrackedBaselineTests(unittest.TestCase):
    def test_committed_tool_configs_are_machine_portable(self):
        for relative in (
            "configs/tools.json",
            "variants/phase5g_pure_formation/configs/tools.json",
        ):
            with self.subTest(relative=relative):
                text = (ROOT / relative).read_text(encoding="utf-8-sig")
                payload = json.loads(text)
                self.assertFalse(re.search(r"(?i)[a-z]:[/\\]", text), text)
                self.assertNotIn("84335", text)
                self.assertNotIn("yanjiu1", text.lower())
                self.assertIn("sumo_home", payload)
    def test_audit_contains_mandatory_runtime_inputs_and_imports(self):
        audit = _audit_module()
        required = set(audit.compute_runtime_closure(ROOT, ENTRIES, LAUNCHERS))
        expected = {
            "configs/tools.json",
            "demo/__init__.py",
            "demo/sumo_gui.py",
            "runrun.py",
            "scripts/audit_runtime_closure.py",
            "scripts/run_logged.py",
            "scenarios/cai2024/bottleneck.net.xml",
            "tests/test_phase5g_tracked_baseline.py",
            "tests/test_runrun_demo.py",
            "variants/phase5g_pure_formation/configs/phase5g.json",
            "variants/phase5g_pure_formation/configs/tools.json",
            "variants/phase5g_pure_formation/docs/parameter_registry.csv",
            "variants/phase5g_pure_formation/experiments/phase5g_cases.py",
            "variants/phase5g_pure_formation/noa/simple_formation.py",
            "variants/phase5g_pure_formation/scenarios/cai2024/bottleneck.net.xml",
            "variants/phase5g_pure_formation/tests/test_phase5g_harness.py",
            "variants/phase5g_pure_formation/tests/baselines/phase5f_controller.py",
        }
        self.assertFalse(expected - required, sorted(expected - required))
        self.assertNotIn(
            "variants/phase5g_pure_formation/experiments/phase5_r5.py", required
        )

    def test_audit_rejects_unresolved_local_import(self):
        audit = _audit_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "localpkg").mkdir()
            (root / "localpkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "entry.py").write_text(
                "from localpkg import missing\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "unresolved local import"):
                audit.compute_runtime_closure(root, ("entry.py",), ())

    def test_audit_rejects_missing_member_from_local_module(self):
        audit = _audit_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "localmod.py").write_text("present = 1\n", encoding="utf-8")
            (root / "entry.py").write_text(
                "from localmod import missing\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "unresolved local import"):
                audit.compute_runtime_closure(root, ("entry.py",), ())

    def test_audit_follows_static_read_json_source_inputs_only(self):
        audit = _audit_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "configs").mkdir()
            (root / "configs" / "tools.json").write_text("{}", encoding="utf-8")
            (root / "results").mkdir()
            (root / "results" / "old.json").write_text("{}", encoding="utf-8")
            (root / "entry.py").write_text(
                "read_json('configs/tools.json')\n"
                "read_json('results/old.json')\n",
                encoding="utf-8",
            )
            closure = set(audit.compute_runtime_closure(root, ("entry.py",), ()))
            self.assertIn("configs/tools.json", closure)
            self.assertNotIn("results/old.json", closure)

    def test_audit_rejects_forbidden_selected_path(self):
        audit = _audit_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            forbidden = root / "results" / "trace.json"
            forbidden.parent.mkdir()
            forbidden.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "forbidden closure path"):
                audit.compute_runtime_closure(root, ("results/trace.json",), ())

    def test_computed_runtime_closure_is_tracked_and_forbidden_files_are_absent(self):
        audit = _audit_module()
        required = set(audit.compute_runtime_closure(ROOT, ENTRIES, LAUNCHERS))
        tracked = _repository_baseline_files(ROOT)
        self.assertFalse(required - tracked, sorted(required - tracked))
        self.assertFalse({path for path in tracked if path.startswith("results/")})
        self.assertFalse({path for path in tracked if "/results/" in path})
        self.assertFalse({path for path in tracked if "/tmp/" in path})
        self.assertFalse({path for path in tracked if path.lower().endswith(".pdf")})
        self.assertFalse(
            {
                path
                for path in tracked
                if path.startswith("variants/")
                and not path.startswith("variants/phase5g_pure_formation/")
            }
        )

    def test_archive_mode_enumerates_files_without_git_metadata(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "nested").mkdir()
            (root / "entry.py").write_text("pass\n", encoding="utf-8")
            (root / "nested" / "input.json").write_text("{}", encoding="utf-8")
            self.assertEqual(
                {"entry.py", "nested/input.json"},
                _repository_baseline_files(root),
            )


if __name__ == "__main__":
    unittest.main()
