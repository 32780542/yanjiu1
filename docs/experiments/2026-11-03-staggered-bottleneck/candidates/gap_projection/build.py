"""Reconstruct one small candidate from its immutable Git baseline."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[5]
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
original = subprocess.check_output(["git", "show", BASE + ":" + NAME], cwd=REPO).decode("utf-8")
source = original


def edit(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)


edit("def _merge_target(ego, rows, lane, held=None):",
     "def _merge_target(ego, rows, lane, held=None, project=False):")
edit("        return (front.x + rear.x) / 2, (front.speed + rear.speed) / 2, gap",
     """        target = (front.x + rear.x) / 2
        if project:
            low = rear.x + CLEARANCE + max(0.0, rear.speed - ego.speed)
            high = front.x - CLEARANCE + min(0.0, front.speed - ego.speed)
            if low <= high:
                target = max(low, min(high, ego.x))
        return target, (front.speed + rear.speed) / 2, gap""")
edit("_merge_target(ego, rows, lane, memory.gap)",
     "_merge_target(ego, rows, lane, memory.gap, project=True)")
edit("_merge_target(ego, rows, 1, memory.gap)",
     "_merge_target(ego, rows, 1, memory.gap, project=organized)")
destination = REPO / "tmp/staggered_bottleneck/candidates/gap_projection/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="a/" + NAME, tofile="b/" + NAME))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
metadata = dict(base_commit=BASE, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=["_merge_target", "_join_speed", "_decide"],
                production_unchanged=True, noa_control_unchanged=True,
                rules_path=str(destination))
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
