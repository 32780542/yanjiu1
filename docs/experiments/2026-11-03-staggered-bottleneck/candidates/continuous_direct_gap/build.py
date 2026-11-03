"""Test phase continuity on the cleaned real-gap transformation baseline."""
import difflib
import hashlib
import json
from pathlib import Path
import runpy

REPO = Path(__file__).resolve().parents[5]
ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "direct_gap/build.py"))
base = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
assert hashlib.sha256(base.read_bytes()).hexdigest() == "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
original = base.read_text(encoding="utf-8")
source = original
for old, new in (
    ("return GAP / 2 if (lanes - 1 - min(lane, lanes - 1)) % 2 else 0.0",
     "return GAP / 2 if min(lane, lanes - 1) % 2 else 0.0"),
    ("return 15.0 if (lanes - 1 - lane) % 2 else 0.0", "return _phase(lane, lanes)"),
):
    assert source.count(old) == 1
    source = source.replace(old, new)
destination = REPO / "tmp/staggered_bottleneck/candidates/continuous_direct_gap/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
name = "variants/phase5g_pure_formation/noa/native_rules.py"
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="E/" + name, tofile="ED/" + name))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
metadata = dict(parent="E", source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=["_phase", "_fill"], rules_path=str(destination))
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
