"""C5: a receding local five-second minimum-acceleration gap approach, from S."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_local_gap_trajectory/native_rules.py"
raw = subprocess.check_output(["git", "show", "1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py"], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f" and not OUT.exists()
original = raw.decode("utf-8")
marker = "\ndef _phase(lane, lanes):\n"
addition = ("\ndef _gap_approach(ego, target, reference_speed):\n"
            "    \"\"\"5s局部移动端点的最小加速度平方解，逐帧重算初始控制量。\"\"\"\n"
            "    horizon = 5.0\n"
            "    acceleration = (6 * (target - ego.x) / horizon**2\n"
            "                    + 4 * (reference_speed - ego.speed) / horizon)\n"
            "    return max(0.0, min(MAX_SPEED, ego.speed + 0.1 * acceleration))\n"
            "\n")
edits = [
    (marker, addition + marker),
    ("    return _request(ego, target, speed), target, replace(memory, gap=gap)\n",
     "    return _gap_approach(ego, target, speed), target, replace(memory, gap=gap)\n"),
    ("        speed = _request(ego, target, gap_speed)\n",
     "        speed = _gap_approach(ego, target, gap_speed) if organized else _request(ego, target, gap_speed)\n"),
]
source = original
for old, new in edits:
    assert source.count(old) == 1
    source = source.replace(old, new)
reverse = source
for old, new in reversed(edits):
    reverse = reverse.replace(new, old)
assert reverse == original
compile(source, str(OUT), "exec")
original_nodes = {node.name: ast.dump(node) for node in ast.parse(original).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
changed = [node.name for node in ast.parse(source).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
           and ast.dump(node) != original_nodes.get(node.name)]
assert changed == ["_gap_approach", "_join_speed", "_decide"]
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="S/noa/native_rules.py", tofile="C5/noa/native_rules.py")), encoding="utf-8", newline="\n")
meta = dict(parent_sha256=hashlib.sha256(raw).hexdigest(), source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            lines=len(source.splitlines()), changed_functions=changed, exact_reverse=True,
            horizon_s=5.0, horizon_source="Cai MATLAB stage duration; local endpoint derivation, not centralized reproduction",
            no_new_memory_waiting_or_lane_gate=True, path=str(OUT))
(DOC / "source.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(json.dumps(meta))
