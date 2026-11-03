"""Keep the physical surviving lanes' staggered offsets across 3->2."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[5]
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
original = subprocess.check_output(["git", "show", BASE + ":" + NAME], cwd=REPO).decode("utf-8")
old = "return GAP / 2 if (lanes - 1 - min(lane, lanes - 1)) % 2 else 0.0"
assert original.count(old) == 1
source = original.replace(old, "return GAP / 2 if min(lane, lanes - 1) % 2 else 0.0")
old = "return 15.0 if (lanes - 1 - lane) % 2 else 0.0"
assert source.count(old) == 1
source = source.replace(old, "return _phase(lane, lanes)")
destination = REPO / "tmp/staggered_bottleneck/candidates/continuous_phase/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="a/" + NAME, tofile="b/" + NAME))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
metadata = dict(base_commit=BASE, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=["_phase", "_fill"], production_unchanged=True,
                noa_control_unchanged=True, straight3_control_unchanged=True, rules_path=str(destination))
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
