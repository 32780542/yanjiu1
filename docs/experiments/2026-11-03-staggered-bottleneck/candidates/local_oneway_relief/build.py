"""Add self-directed one-way relief to the fixed, independently built E source."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[5]
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
E_SHA = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
e_path = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
if not e_path.exists():
    subprocess.run([sys.executable, "-B", str(Path(__file__).parents[1] / "direct_gap/build.py")],
                   cwd=REPO, check=True)
e_bytes = e_path.read_bytes()
assert hashlib.sha256(e_bytes).hexdigest() == E_SHA
production_before = (REPO / NAME).read_bytes()
original = e_bytes.decode("utf-8")
old = "    if preparing and ego.lane == 2:\n"
new = """    if preparing and mode == "transform" and ego.lane < 2:
        window = [c for c in (ego, *rows) if ego.x - 60.0 <= c.x <= ego.x + 30.0]
        pressure = sum(1 if c.lane in (1, 2) else -1 for c in window)
        if ego.lane == 1 and pressure >= 2 and _clear(ego, rows, 0):
            memory = Memory(lane_target=0, joining=True)
            speed, target, memory = _join_speed(ego, rows, memory, 0)
            return action(speed, 0, "local_relief", target), memory
        reason = "join_follow" if memory.joining else "formation_follow"
        return action(speed, None, reason, target, reference), memory

    if preparing and ego.lane == 2:
"""
assert original.count(old) == 1
source = original.replace(old, new)
compile(source, "local_oneway_relief/native_rules.py", "exec")
destination = REPO / "tmp/staggered_bottleneck/candidates/local_oneway_relief/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="E/" + NAME, tofile="F/" + NAME))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
assert production_before == (REPO / NAME).read_bytes()
assert e_bytes == e_path.read_bytes()
metadata = dict(base_commit="177f7a32088fb69efcc94d9acb72863e7e00e787",
                parent_candidate="direct_gap", parent_sha256=E_SHA,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=["_decide"], lines=len(source.splitlines()),
                production_unchanged=True, parent_unchanged=True,
                noa_control_unchanged=True, formation_control_unchanged=True,
                rules_path=str(destination))
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
