"""Build J and its single-expression JT increment from immutable E."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parents[2]
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
E_PATH = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
E_SHA = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
protected = {p: p.read_bytes() for p in (E_PATH, REPO / NAME)}
assert hashlib.sha256(protected[E_PATH]).hexdigest() == E_SHA
original = protected[E_PATH].decode("utf-8")
source = original


def function(name, replacement):
    global source
    lines = source.splitlines(True)
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines[node.lineno - 1:node.end_lineno] = replacement.splitlines(True)
    source = "".join(lines)


function("_phase", """def _phase(lane, lanes):
    return GAP / 2 if lane % 2 else 0.0
""")
pair = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "_pair_error")
old = ast.get_source_segment(source, pair)
before_return = old[:old.index("    return (")]
function("_pair_error", before_return + """    phase = _physical_phase(peer, 3) - _physical_phase(car, 3)
    return peer.x - car.x + phase, pair_lanes
""")
function("_following", '''def _following(ego, rows, lanes, phase_boundary=None):
    """真实前车CTH叠加实际相邻道互选相位；每车只输出自身速度。"""
    following = _front_following(ego, rows)
    cars = (ego, *rows)

    def nearest(car, lane):
        candidates = [c for c in cars if c.lane == lane and abs(c.x - car.x) <= 50.0]

        def order(c):
            difference, _ = _pair_error(car, c, lanes, phase_boundary)
            return abs(difference), abs(c.x - car.x), difference, c.x, c.y, c.speed, c.vy

        return min(candidates, key=order, default=None)

    linked = bool(following[3]) or any(
        -50.0 <= c.x - ego.x < 0.0 and _occupies(c, ego.lane, 0.0) for c in rows
    )
    error = 0.0
    for lane in (ego.lane - 1, ego.lane + 1):
        if 0 <= lane < lanes:
            peer = nearest(ego, lane)
            if peer is not None and nearest(peer, ego.lane) is ego:
                linked = True
                difference, pair_lanes = _pair_error(ego, peer, lanes, phase_boundary)
                error += difference / max(1, pair_lanes - 1)
    phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))
    if following[2] is not None:
        speed = max(0.0, min(MAX_SPEED, following[0] + SPEED_RELAXATION * phase_speed))
        return speed, following[1], following[2], int(linked)
    target = ego.x + phase_speed / POSITION_GAIN
    return _request(ego, target, CRUISE), target, None, int(linked)
''')
old_fill_phase = "        return 15.0 if (lanes - 1 - lane) % 2 else 0.0"
assert source.count(old_fill_phase) == 1
source = source.replace(old_fill_phase, "        return _phase(lane, lanes)")
j = source
old_return = "    return peer.x - car.x + phase, pair_lanes"
new_return = "    return peer.x - car.x + phase * (LENGTH + STANDSTILL + HEADWAY * (car.speed + peer.speed) / 2) / GAP, pair_lanes"
assert j.count(old_return) == 1
jt = j.replace(old_return, new_return)
changed = lambda a, b: [x.name for x, y in zip(ast.parse(a).body, ast.parse(b).body)
                        if ast.dump(x) != ast.dump(y)]
assert changed(original, j) == ["_phase", "_pair_error", "_following", "_fill"]
assert changed(j, jt) == ["_pair_error"]
for name, value, parent, parent_name in (("local_phase_coupling", j, original, "E"),
                                        ("time_scaled_phase_coupling", jt, j, "J")):
    compile(value, name + "/native_rules.py", "exec")
    path = REPO / "tmp/staggered_bottleneck/candidates" / name / "native_rules.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")
    evidence = DOC / "candidates" / name
    evidence.mkdir(parents=True, exist_ok=True)
    patch = "".join(difflib.unified_diff(parent.splitlines(True), value.splitlines(True),
                                        fromfile=parent_name + "/" + NAME, tofile=name + "/" + NAME))
    (evidence / "native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
    metadata = dict(parent_candidate=parent_name, parent_sha256=hashlib.sha256(parent.encode()).hexdigest(),
                    baseline_e_sha256=E_SHA, source_sha256=hashlib.sha256(value.encode()).hexdigest(),
                    changed_functions=changed(parent, value), lines=len(value.splitlines()),
                    rules_path=str(path), production_e_unchanged=True, noa_control_unchanged=True)
    (evidence / "source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata))
assert all(p.read_bytes() == data for p, data in protected.items())
