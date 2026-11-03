"""GP2: CTH-compatible admission within a bound real gap; preserve GP source."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_bound_real_gap/native_rules.py"
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py"
EXPECTED = "3e2a722f997713e6ad504bce22d741c39d58b1ad6808765a5b9b8d62a68a1007"
raw = PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED and not OUT.exists()
original = raw.decode("utf-8")
start, end = original.index("def _gap_plan("), original.index("def _gap_clear(")
planner = original[start:end]
planner = planner.replace("    T, v = max(0.1, remaining), ego.speed\n", "    v = ego.speed\n")
loop_start, loop_end = planner.index("    for rear, front in zip("), planner.index("    return min(choices")
body = planner[loop_start:loop_end]
body = body.replace("score = (gap != held, cost,", "score = (gap != held, T, cost,")
planner = (planner[:loop_start]
           + "    for T in sorted({min(5.0, max(0.1, remaining)), max(0.1, remaining)}):\n"
           + "".join("    "+line if line.strip() else line for line in body.splitlines(True))
           + planner[loop_end:])
planner = planner.replace("        if low > high:\n            continue\n", "        if low > high:\n            if low > high + ulp(origin):\n                continue\n            low = high\n")
# The planner loop gained one indentation level above.
planner = planner.replace("            if low > high:\n                continue\n", "            if low > high:\n                if low > high + ulp(origin):\n                    continue\n                low = high\n")
guard_start, guard_end = original.index("def _gap_clear("), original.index("def _join_speed(")
guard = '''def _gap_clear(ego, rows, lane, gap, drop_x, continuing=False):
    if _gap_plan(ego, rows, lane, gap, drop_x) is None:
        return continuing or _clear(ego, rows, lane)
    if continuing or ego.pending_lane == lane:
        return True
    by_track = {c.track: c for c in rows}
    if gap is None or any(key is not None and key not in by_track for key in gap):
        return False
    front, rear = (by_track.get(key) for key in gap)
    if front is None or rear is None:
        return False
    low = rear.x + LENGTH + STANDSTILL + HEADWAY * rear.speed - 2.0
    high = front.x - LENGTH - STANDSTILL - HEADWAY * ego.speed + 2.0
    return low <= ego.x <= high and _clear(ego, rows, lane)


'''
source = original[:start] + planner + guard + original[guard_end:]
source = source.replace("from math import sqrt\n", "from math import sqrt, ulp\n")
before = {n.name:ast.dump(n) for n in ast.parse(original).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
changed = [n.name for n in ast.parse(source).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))
           and ast.dump(n) != before.get(n.name)]
assert changed == ["_gap_plan", "_gap_clear"]
assert len(source.splitlines()) <= 535
compile(source, str(OUT), "exec")
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
(DOC / "GP_to_GP2.patch").write_text("".join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),
    fromfile="GP/noa/native_rules.py",tofile="GP2/noa/native_rules.py")),encoding="utf-8",newline="\n")
meta = dict(parent_path=str(PARENT),parent_sha256=EXPECTED,
            frozen_s_sha256="8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f",
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),path=str(OUT),lines=len(source.splitlines()),
            changed_functions_from_GP=changed, no_V_F_C5_source_stacking=True,
            strategy="CTH-compatible admission within bound real gap",
            horizon_priority="held feasible pair first; then shortest of Cai5s/map remaining; then J",
            no_new_vehicle_state_memory_or_tuned_gain=True, no_traffic_simulation=True)
(DOC / "source.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(meta,ensure_ascii=False))
