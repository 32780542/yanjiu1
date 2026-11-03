"""Build V from the frozen S: projected merge predecessor before phase priority."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
BASE = "1aa86344af2a269053cd4fcda9d58168697daf17"
EXPECTED = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v1/native_rules.py"
raw = subprocess.check_output(["git", "show", BASE + ":variants/phase5g_pure_formation/noa/native_rules.py"], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == EXPECTED and not OUT.exists()
original = raw.decode("utf-8")
edits = [
    ("def _following(ego, rows, lanes, phase_boundary=None):",
     "def _following(ego, rows, lanes, phase_boundary=None, merge_bounds=None):"),
    ("            following = extended\n    cars = (ego, *rows)\n",
     "            following = extended\n"
     "    if merge_bounds is not None and ego.lane == 1:\n"
     "        projected = tuple(\n"
     "            replace(c, lane=1, y=1.5 * LANE_WIDTH, vy=0.0) for c in rows\n"
     "            if c.lane == 2 and merge_bounds[0] <= c.x < merge_bounds[1]\n"
     "        )\n"
     "        anticipated = _front_following(ego, (*rows, *projected))\n"
     "        if anticipated[2] is not None and anticipated[0] < following[0]:\n"
     "            following = anticipated\n"
     "    cars = (ego, *rows)\n"),
    ("            drop_x - 360.0 if mode == \"transform\" and drop_x is not None else drop_x,\n",
     "            drop_x - 360.0 if mode == \"transform\" and drop_x is not None else drop_x,\n"
     "            (drop_x - 360.0, drop_x) if preparing and mode == \"transform\" else None,\n"),
]
source = original
for old, new in edits:
    assert source.count(old) == 1
    source = source.replace(old, new)
reverse = source
for old, new in reversed(edits):
    reverse = reverse.replace(new, old)
assert reverse == original
changed = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
assert changed == ["_following", "_decide"]
compile(source, str(OUT), "exec")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="S/noa/native_rules.py", tofile="V/noa/native_rules.py")), encoding="utf-8", newline="\n")
meta = dict(base_commit=BASE, parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            changed_functions=changed, lines=len(source.splitlines()), exact_reverse=True,
            no_new_gain_parameter_state_or_memory=True, path=str(OUT))
(DOC / "source.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(json.dumps(meta))
