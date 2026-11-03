"""Run real on-disk regression tests in the variant working directory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
VARIANT = ROOT / "variants/phase5g_pure_formation"
EXPECTED = "2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tag", required=True)
args = parser.parse_args()
assert args.tag.replace("_", "").isalnum()
report = HERE / ("installed_D1_" + args.tag)
assert not report.with_suffix(".xml").exists() and not report.with_suffix(".json").exists()
record = ROOT / "docs/experiments/2026-11-03-staggered-bottleneck/implementation/S_core14_minimal_migrated.json"
files = list(json.loads(record.read_text(encoding="utf-8"))["selected_files"])
files.append("tests/test_local_staggered_rules.py")
balance = "tests/test_local_formation_balance.py"
if (VARIANT / balance).exists():
    files.append(balance)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = VARIANT / "noa/native_rules.py"
assert sha(source) == EXPECTED
before = {name: sha(VARIANT / name) for name in ["noa/native_rules.py", *files]}
result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "pytest", *files,
                         "-q", "--junitxml=" + str(report.with_suffix(".xml"))], cwd=VARIANT)
assert before == {name: sha(VARIANT / name) for name in before}
metadata = dict(installed_source_sha256=EXPECTED, tests_on_disk=True, module_injection=False,
                test_files=files, source_and_test_hashes=before, returncode=result.returncode)
report.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(returncode=result.returncode, report=str(report.with_suffix(".json")))))
raise SystemExit(result.returncode)
