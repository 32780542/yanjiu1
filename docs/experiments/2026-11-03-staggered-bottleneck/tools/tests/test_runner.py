"""Safety contracts for this round's compact experiment runner."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class RunnerContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / "runner.py").is_file(), "runner implementation is missing")
        self.assertTrue((HERE / "seal_case.py").is_file(), "seal implementation is missing")
        import runner
        import seal_case
        self.runner, self.seal = runner, seal_case
        self.temp = tempfile.TemporaryDirectory(dir=runner.SAFE_ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def case(self):
        batch = self.root / "batch"
        run = batch / "cases" / "TM_1" / "run"
        run.mkdir(parents=True)
        (batch / ".staggered-runner-owned").write_text(str(batch.resolve()), encoding="utf-8")
        expected = {}
        for name in self.seal.RAW_FILES:
            payload = (name + " fixture").encode()
            (run / name).write_bytes(payload)
            expected[name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        return batch, run, expected

    def test_pruning_requires_verification(self):
        batch, run, expected = self.case()
        with self.assertRaisesRegex(ValueError, "verif"):
            self.seal.prune_raw(run, batch, expected, verified=False)
        self.assertTrue(all((run / n).exists() for n in expected))

    def test_pruning_refuses_paths_outside_owned_batch(self):
        batch, run, expected = self.case()
        outside = self.root / "old-results"
        outside.mkdir()
        (outside / "positions.jsonl.gz").write_bytes(b"old")
        with self.assertRaisesRegex(ValueError, "outside"):
            self.seal.prune_raw(outside, batch, expected, verified=True)
        self.assertEqual((outside / "positions.jsonl.gz").read_bytes(), b"old")

    def test_pruning_checks_all_hashes_before_deleting_anything(self):
        batch, run, expected = self.case()
        (run / "events.jsonl.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.seal.prune_raw(run, batch, expected, verified=True)
        self.assertTrue((run / "positions.jsonl.gz").exists())

    def test_verified_pruning_removes_only_two_raw_files(self):
        batch, run, expected = self.case()
        (run / "result.json").write_text("{}", encoding="utf-8")
        report = self.seal.prune_raw(run, batch, expected, verified=True)
        self.assertEqual(set(report["deleted"]), set(expected))
        self.assertTrue((run / "result.json").is_file())

    def test_freeze_uses_pinned_git_sources_and_only_replaces_rules(self):
        rules = self.root / "candidate.py"
        rules.write_bytes(b"# isolated candidate\n")
        hashes = self.runner.freeze(self.root / "source", rules)
        self.assertEqual(hashes["noa/native_rules.py"], hashlib.sha256(rules.read_bytes()).hexdigest())
        snapshot = json.loads((self.root / "source/freeze.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["base_commit"], "177f7a32088fb69efcc94d9acb72863e7e00e787")
        self.assertEqual(set(hashes), set(self.runner.FILES))

    def test_output_cannot_target_an_old_directory(self):
        with self.assertRaisesRegex(ValueError, "output"):
            self.runner.validate_output(self.root)

    def test_rounded_flow_path_collision_is_rejected_before_batch_creation(self):
        batch = self.root / "must_not_be_created"
        args = ["runner.py", "--candidate", "TM", "--stage", "fixture", "--flows",
                "1750.0001", "1750.0002", "--seeds", "1", "--output", str(batch)]
        with patch.object(sys, "argv", args), patch.object(self.runner, "freeze", return_value={}), patch.object(
                self.runner, "validate_output", return_value=batch), patch.object(
                self.runner, "ThreadPoolExecutor", side_effect=AssertionError("workers started before collision check")):
            with self.assertRaises(SystemExit) as result:
                self.runner.main()
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(batch.exists())

    def test_archive_failure_retains_raw_and_records_physical_failure(self):
        output = self.root / "attempt"
        task = dict(candidate="TM", stage="fixture", flow=1750, seed=1, scenario="lane_drop",
                    mode="transform", source=str(self.root / "source"), output=str(output),
                    duration=90, max_time=180, worker_timeout=30, batch=str(self.root), prune_raw=True)

        def worker(*args, **kwargs):
            run = output / "run"
            run.mkdir()
            (run / "result.json").write_text(json.dumps(dict(status="collision", safe=False,
                all_completed=False, collisions=1, teleports=0, error=None)), encoding="utf-8")
            for name in self.seal.RAW_FILES:
                (run / name).write_bytes(b"retain this failed attempt")
            return SimpleNamespace(returncode=0)

        with patch.object(self.runner.subprocess, "run", side_effect=worker), patch.object(
                self.seal, "seal", side_effect=ValueError("truncated gzip")):
            row = self.runner.run_one(task)
        self.assertEqual(row["returncode"], 0)
        self.assertFalse(row["safe"])
        self.assertEqual(row["collisions"], 1)
        self.assertEqual(row["seal_status"], "failed_raw_retained")
        self.assertTrue(all((output / "run" / name).is_file() for name in self.seal.RAW_FILES))
        self.assertTrue((output / "case_record.json").is_file())
        self.assertIn("truncated gzip", (output / "seal_error.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
