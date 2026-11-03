"""V2 removes the receiver's redundant map-boundary gate, preserving V1 itself."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v1/native_rules.py"
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v2/native_rules.py"
raw = PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "517d169ff012950e288c20a9fca9225db20bae6ffcc1a6f3aca43c05c8790c7d" and not OUT.exists()
original = raw.decode("utf-8")
old = '(drop_x - 360.0, drop_x) if preparing and mode == "transform" else None,'
new = '(drop_x - 360.0, drop_x) if drop_x is not None and mode == "transform" else None,'
assert original.count(old) == 1
source = original.replace(old, new)
assert source.replace(new, old) == original
compile(source, str(OUT), "exec")
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="V1/noa/native_rules.py", tofile="V2/noa/native_rules.py")), encoding="utf-8", newline="\n")
meta = dict(parent_sha256=hashlib.sha256(raw).hexdigest(), source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            lines=len(source.splitlines()), sole_change="receiver need not cross 640m; actual merging car must be preparing",
            no_new_threshold_parameter_or_memory=True, exact_reverse=True, path=str(OUT))
(DOC / "source.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(json.dumps(meta))
