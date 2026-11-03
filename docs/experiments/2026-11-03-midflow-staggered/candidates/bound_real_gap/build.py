"""GP: frozen S plus local bound-real-gap planning; no traffic or production edit."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_bound_real_gap/native_rules.py"
COMMIT = "1aa86344af2a269053cd4fcda9d58168697daf17"
EXPECTED = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
raw = subprocess.check_output(["git", "show", COMMIT+":variants/phase5g_pure_formation/noa/native_rules.py"], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == EXPECTED and not OUT.exists()
original = raw.decode("utf-8")
addition = '''def _gap_plan(ego, rows, lane, held, drop_x):
    """Visible real pairs, constant-speed nominal CTH windows and bounded cubics."""
    remaining = (drop_x - ego.x) / CRUISE - 1.0
    if remaining <= 0.0 or not 0.0 <= ego.speed <= MAX_SPEED:
        return None
    T, v = max(0.1, remaining), ego.speed
    ordered = sorted((c for c in rows if _occupies(c, lane)), key=lambda c: (c.x, c.y, c.speed, c.vy))
    choices = []
    for rear, front in zip(ordered, ordered[1:]):
        u = (front.speed + rear.speed) / 2
        if front.x <= rear.x or not 0.0 <= u <= MAX_SPEED:
            continue
        E, origin = u - v, ego.x + v * T
        low = max(rear.x + rear.speed * T + LENGTH + STANDSTILL + HEADWAY * rear.speed - origin,
                  (-BRAKING * T*T + 2*E*T) / 6, (-5.0 * T*T + 4*E*T) / 6,
                  T / 3 * (u - 2*v - sqrt(v*u)))
        high = min(front.x + front.speed * T - LENGTH - STANDSTILL - HEADWAY * u - origin,
                   drop_x - u - origin,
                   (5.0 * T*T + 2*E*T) / 6, (BRAKING * T*T + 4*E*T) / 6,
                   T / 3 * (MAX_SPEED + u - 2*v + sqrt((MAX_SPEED-v)*(MAX_SPEED-u))))
        if low > high:
            continue
        D = max(low, min(high, E*T/2))
        cost = 12*D*D/T**3 - 12*D*E/T**2 + 4*E*E/T
        gap = (front.track, rear.track)
        score = (gap != held, cost, front.x, rear.x, front.speed, rear.speed)
        choices.append((score, origin + D - u*T, u, gap, T))
    return min(choices, key=lambda choice: choice[0])[1:] if choices else None


def _gap_clear(ego, rows, lane, gap, drop_x, continuing=False):
    if _gap_plan(ego, rows, lane, gap, drop_x) is None:
        return continuing or _clear(ego, rows, lane)
    by_track = {c.track: c for c in rows}
    if gap is None or any(key is not None and key not in by_track for key in gap):
        return False
    front, rear = (by_track.get(key) for key in gap)
    return (front is None or ego.x <= front.x) and (rear is None or rear.x <= ego.x) and _clear(ego, rows, lane)


'''
old_join = '''def _join_speed(ego, rows, memory, lane):
    target, speed, gap = _merge_target(ego, rows, lane, memory.gap)
    return _request(ego, target, speed), target, replace(memory, gap=gap)
'''
new_join = '''def _join_speed(ego, rows, memory, lane, drop_x=None):
    plan = _gap_plan(ego, rows, lane, memory.gap, drop_x) if drop_x is not None and lane == 1 else None
    if plan is not None:
        target, speed, gap, T = plan
        acceleration = 6*(target-ego.x)/T**2 + 4*(speed-ego.speed)/T
        speed = max(0.0, min(MAX_SPEED, ego.speed + 0.1*acceleration))
        return speed, target, replace(memory, gap=gap)
    target, speed, gap = _merge_target(ego, rows, lane, memory.gap)
    return _request(ego, target, speed), target, replace(memory, gap=gap)
'''
edits = [
    (old_join, addition+new_join),
    ('    organized = mode != "noa"\n',
     '    organized = mode != "noa"\n    planner_drop = drop_x if mode == "transform" and preparing else None\n'),
    ('                _join_speed(ego, rows, memory, memory.lane_target)\n',
     '                _join_speed(ego, rows, memory, memory.lane_target, planner_drop)\n'),
    ('            if moving or _clear(ego, rows, memory.lane_target):\n',
     '            if (_gap_clear(ego, rows, 1, memory.gap, planner_drop, moving) if planner_drop is not None and memory.lane_target == 1\n'
     '                    else moving or _clear(ego, rows, memory.lane_target)):\n'),
    ('''        target, gap_speed, gap = _merge_target(ego, rows, 1, memory.gap)
        memory = replace(memory, gap=gap)
        speed = _request(ego, target, gap_speed)
        if _clear(ego, rows, 1):
''', '''        if organized and planner_drop is not None:
            speed, target, memory = _join_speed(ego, rows, memory, 1, planner_drop)
        else:
            target, gap_speed, gap = _merge_target(ego, rows, 1, memory.gap)
            memory = replace(memory, gap=gap)
            speed = _request(ego, target, gap_speed)
        if (_gap_clear(ego, rows, 1, memory.gap, planner_drop) if planner_drop is not None else _clear(ego, rows, 1)):
'''),
    ('                speed, target, memory = _join_speed(ego, rows, memory, lane)\n',
     '                speed, target, memory = _join_speed(ego, rows, memory, lane, planner_drop)\n'
     '                if planner_drop is not None and lane == 1 and not _gap_clear(ego, rows, 1, memory.gap, planner_drop):\n'
     '                    return action(speed, None, "approach_join", target), memory\n'),
]
source = original
for old, new in edits:
    assert source.count(old) == 1, repr(old)
    source = source.replace(old, new)
reverse = source
for old, new in reversed(edits):
    assert reverse.count(new) == 1
    reverse = reverse.replace(new, old)
assert reverse == original
before = {n.name: ast.dump(n) for n in ast.parse(original).body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
changed = [n.name for n in ast.parse(source).body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
           and ast.dump(n) != before.get(n.name)]
assert changed == ["_gap_plan", "_gap_clear", "_join_speed", "_decide"]
lines = len(source.splitlines())
assert lines <= 540, f"Review design before increasing source to {lines} lines"
compile(source, str(OUT), "exec")
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="S/noa/native_rules.py", tofile="GP/noa/native_rules.py")), encoding="utf-8", newline="\n")
meta = dict(base_commit=COMMIT, parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            path=str(OUT), lines=lines, changed_functions=changed, exact_reverse=True,
            no_V_F_C5_source_stacking=True, no_new_vehicle_state_memory_or_tunable_gain=True,
            domain="transform map preparation; initial/active destination lane1 only",
            nominal_assumptions="visible real F/R remain constant-speed over map-derived horizon",
            no_traffic_simulation=True)
(DOC / "source.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(meta, ensure_ascii=False))
