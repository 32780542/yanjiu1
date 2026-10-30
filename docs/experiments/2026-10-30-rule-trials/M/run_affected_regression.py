"""Run only affected existing static tests with the isolated M rules installed in memory."""
import importlib.util
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
VARIANT = ROOT / "variants/phase5g_pure_formation"
sys.path.insert(0, str(VARIANT))
sys.path.insert(0, str(VARIANT / "tests"))
import noa

parser = argparse.ArgumentParser()
parser.add_argument("--source", choices=("baseline", "candidate"), default="candidate")
parser.add_argument("--suite", choices=("native", "static-compatibility"), default="static-compatibility")
arguments = parser.parse_args()
source = (subprocess.check_output([
    "git", "show", "8ed11d90ac457269b2175e20aec5ba1bbba8a318:variants/phase5g_pure_formation/noa/native_rules.py"
], cwd=ROOT) if arguments.source == "baseline" else
          (ROOT / "tmp/literature_trials/M/native_rules.py").read_bytes())
module_path = ROOT / ("tmp/literature_trials/M/baseline_native_rules.py" if arguments.source == "baseline"
                      else "tmp/literature_trials/M/native_rules.py")
module_spec = importlib.util.spec_from_file_location("noa.native_rules", module_path)
module = importlib.util.module_from_spec(module_spec)
sys.modules[module.__name__] = module
exec(compile(source, "isolated_M_native_rules.py", "exec"), module.__dict__)
noa.native_rules = module
names = ["test_native_rules"]
if arguments.suite == "static-compatibility":
    names += ["test_physical_following", "test_formation_state.LocalFormationStateTests",
              "test_formation_state.FormationStateStatisticsTests"]
suite = unittest.defaultTestLoader.loadTestsFromNames(names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {"source": arguments.source, "suite": arguments.suite,
           "sha256": hashlib.sha256(source).hexdigest(),
           "tests_run": result.testsRun, "simulation_tests_excluded": True,
           "failures": [{"test": test.id(), "detail": detail} for test, detail in result.failures],
           "errors": [{"test": test.id(), "detail": detail} for test, detail in result.errors]}
(ROOT / f"tmp/literature_trials/M/{arguments.source}_{arguments.suite}.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k not in ("failures", "errors")}), flush=True)
raise SystemExit(not result.wasSuccessful())
