"""Keep a timed-out worker's native provisional result; never launch SUMO."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]


class TrialRunnerTimeoutTests(unittest.TestCase):
    def test_timeout_retains_provisional_case_as_a_failed_row(self):
        spec = importlib.util.spec_from_file_location(
            "R_trial_runner_timeout", ROOT / "docs/experiments/2026-10-30-rule-trials/run_trials.py"
        )
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp/literature_trials/R", prefix="timeout_") as name:
            task = dict(
                source=name, output=str(Path(name) / "output"), candidate="T", stage="static_probe",
                flow=1250.0, seed=1, scenario="straight3", mode="noa", duration=600.0, max_time=900.0,
            )

            def provisional_then_timeout(command, **kwargs):
                directory = Path(task["output"]) / "provisional_native_case"
                directory.mkdir()
                # run_case writes this prefix before network/SUMO startup; final metrics do not exist yet.
                (directory / "result.json").write_text(
                    json.dumps(dict(status="starting", mode="noa", source_sha256={})), encoding="utf-8"
                )
                raise subprocess.TimeoutExpired(command, timeout=600)

            with patch.object(runner.subprocess, "run", side_effect=provisional_then_timeout):
                try:
                    row = runner.run_one(task)
                except KeyError as error:
                    self.fail(f"Timed-out provisional result must be retained, not raise KeyError({error}).")
            self.assertEqual(row["returncode"], 124)
            self.assertIn(row["status"], ("worker_failed", "starting"))
            self.assertEqual(row["candidate"], "T")
            self.assertEqual(row["seed"], 1)
            self.assertEqual(Path(row["run_dir"]).name, "provisional_native_case")
            self.assertTrue((Path(row["run_dir"]) / "result.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
