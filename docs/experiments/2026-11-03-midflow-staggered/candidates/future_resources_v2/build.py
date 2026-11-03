"""F2: preserve F, reject future occupied opportunities with existing clearance."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_future_resources/native_rules.py"
BASE = "1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py"
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_future_resources_v2/native_rules.py"
EXPECTED_F = "e4b18ac1a61970b9f45e6815725b036a35e91e6773dc6afdcd2032b64daba7e7"
EXPECTED_S = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
raw = PARENT.read_bytes()
base_raw = subprocess.check_output(["git", "show", BASE], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == EXPECTED_F
assert hashlib.sha256(base_raw).hexdigest() == EXPECTED_S
assert not OUT.exists(), "Preserve previous attempts; choose a new revision path"
original, base = raw.decode("utf-8"), base_raw.decode("utf-8")
old = "            if future and matches(center, lane):\n"
new = ("            if future and any(resource_lane(c) == lane and abs(c.x - target) < CLEARANCE\n"
       "                              for c in cars):\n")
assert original.count(old) == 1
source = original.replace(old, new)
assert source.replace(new, old) == original
before, after = ast.parse(original), ast.parse(source)
changed = [left.name for left, right in zip(before.body, after.body) if ast.dump(left) != ast.dump(right)]
assert changed == ["_fill"]
base_ast = ast.parse(base)
changed_from_s = [left.name for left, right in zip(base_ast.body, after.body) if ast.dump(left) != ast.dump(right)]
assert changed_from_s == ["_fill", "_decide"]
compile(source, str(OUT), "exec")
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
for name, previous, label in (("native_rules.patch", base, "S"), ("F_to_F2.patch", original, "F")):
    (DOC / name).write_text("".join(difflib.unified_diff(
        previous.splitlines(True), source.splitlines(True),
        fromfile=f"{label}/noa/native_rules.py", tofile="F2/noa/native_rules.py")), encoding="utf-8", newline="\n")
meta = dict(base_s_path=str(BASE), base_s_sha256=EXPECTED_S,
            parent_revision_path=str(PARENT), parent_revision_sha256=EXPECTED_F,
            path=str(OUT), source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            changed_functions_from_f=changed, changed_functions_from_s=changed_from_s,
            no_V_projection=True, no_new_state_memory_or_tunable_parameter=True,
            future_vacancy_uses_existing_CLEARANCE=8.0,
            enabled_scope="transform and preparing only",
            strategy="future-resource lane choice, actual-gap execution",
            specified_future_slot_tracking=False)
(DOC / "source.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(meta, ensure_ascii=False))
