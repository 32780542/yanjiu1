"""Build isolated F from a frozen Git S blob, without V modifications."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
SOURCE = "1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py"
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_future_resources/native_rules.py"
EXPECTED = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
raw = subprocess.check_output(["git", "show", SOURCE], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == EXPECTED
assert not OUT.exists(), "A prior attempt must stay read-only; choose a new candidate path"
original = raw.decode("utf-8")
start, end = original.index("def _fill("), original.index("def _mandatory_priority(")
fill = original[start:end]
edits = [
    ("def _fill(ego, rows, lanes):", "def _fill(ego, rows, lanes, future=False):"),
    ("    members = tuple(c for c in cars if c.lane < lanes)\n\n    def phase(lane):\n        return _phase(lane, lanes)\n",
     "    def resource_lane(car):\n"
     "        return min(car.lane, 1) if future else car.lane\n\n"
     "    members = tuple(c for c in cars if resource_lane(c) < lanes)\n\n"
     "    def phase(lane):\n"
     "        return _phase(min(lane, 1) if future else lane, lanes)\n"),
    ("(c for c in component if c.lane < lanes), key=lambda c: (c.x + phase(c.lane), c.lane, c.x)",
     "(c for c in component if resource_lane(c) < lanes), key=lambda c: (c.x + phase(c.lane), c.lane, c.x)"),
    ("return [c for c in cars if c.lane == lane and abs(c.x - (center - phase(lane))) <= 2.0]",
     "return [c for c in cars if resource_lane(c) == lane and abs(c.x - (center - phase(c.lane))) <= 2.0]"),
    ("        if c.track != anchor.track\n", "        if c.lane < lanes and c.track != anchor.track\n"),
    ("        window = [c for c in component if c.lane < lanes and center - 60.0 <= c.x <= center + 30.0]\n"
     "        counts = [sum(c.lane == lane for c in window) for lane in range(lanes)]\n",
     "        window = [c for c in component if resource_lane(c) < lanes\n"
     "                  and center - 60.0 <= (c.x + phase(c.lane) if future else c.x) <= center + 30.0]\n"
     "        counts = [sum(resource_lane(c) == lane for c in window) for lane in range(lanes)]\n"),
    ("            target = center - phase(lane)\n            if any(_occupies(c, lane)",
     "            target = center - phase(lane)\n"
     "            if future and matches(center, lane):\n"
     "                continue\n"
     "            if any(_occupies(c, lane)"),
]
for old, new in edits:
    assert fill.count(old) == 1, repr(old)
    fill = fill.replace(old, new)
source = original[:start] + fill + original[end:]
old_call = '        lane = _fill(ego, rows, 2 if preparing else lanes)\n'
new_call = '        lane = _fill(ego, rows, 2 if preparing else lanes, future=preparing and mode == "transform")\n'
assert source.count(old_call) == 1
source = source.replace(old_call, new_call)
reverse = source.replace(new_call, old_call)
for old, new in reversed(edits):
    assert reverse.count(new) == 1
    reverse = reverse.replace(new, old)
assert reverse == original
before, after = ast.parse(original), ast.parse(source)
assert len(before.body) == len(after.body)
changed = [left.name for left, right in zip(before.body, after.body)
           if ast.dump(left) != ast.dump(right)]
assert changed == ["_fill", "_decide"]
assert "merge_bounds" not in source and "projected =" not in source
compile(source, str(OUT), "exec")
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(
    original.splitlines(True), source.splitlines(True),
    fromfile="S/noa/native_rules.py", tofile="F/noa/native_rules.py")), encoding="utf-8", newline="\n")
meta = dict(parent_path=str(SOURCE), parent_sha256=EXPECTED,
            path=str(OUT), source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            changed_functions=changed, exact_reverse=True,
            no_V_projection=True, no_new_vehicle_state_memory_or_tunable_gain=True,
            enabled_scope="transform and preparing only",
            execution_slot_closed=False,
            status="isolated resource-selection prototype; lane-only interface does not retain scored slot")
(DOC / "source.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(meta, ensure_ascii=False))
