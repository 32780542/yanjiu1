"""Build two matched nonformation controls; preserve each full _decide."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parents[1]
BASE = ROOT / "tmp/staggered_bottleneck/candidates"
PARENTS = (
    ("G0", "local_phase_velocity_damping", "matched_nonformation", "a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762"),
    ("G0N", "local_conflict_release", "matched_nonformation_release", "5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6"),
)
FOLLOW = '''def _following(ego, rows, lanes, phase_boundary=None):
    """Matched nonformation: actual front CTH only, no formation relation flag."""
    speed, target, reference, _ = _front_following(ego, rows)
    return speed, target, reference, 0
'''
FILL = '''def _fill(ego, rows, lanes):
    """Original NOA slow-front overtake proposal; caller retains gap execution."""
    front = min(
        (c for c in rows if c.lane == ego.lane and c.x > ego.x), key=lambda c: c.x, default=None
    )
    if front is not None and ego.speed < CRUISE - 2 and front.speed < CRUISE - 2:
        options = [
            lane
            for lane in (ego.lane - 1, ego.lane + 1)
            if 0 <= lane < lanes and _clear(ego, rows, lane)
        ]

        def free_distance(lane):
            return min(
                (c.x - ego.x for c in rows if c.lane == lane and c.x > ego.x), default=200.0
            )

        if options:
            lane = max(options, key=free_distance)
            if free_distance(lane) > front.x - ego.x + 15.0:
                return lane
    return None
'''


def functions(source):
    lines = source.splitlines(True)
    return {n.name: "".join(lines[n.lineno - 1:n.end_lineno])
            for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}


sources, original_bytes, metadata = {}, {}, []
production = ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"
production_before = production.read_bytes()
for label, parent, name, expected in PARENTS:
    path = BASE / parent / "native_rules.py"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    original_bytes[path] = raw
    original = raw.decode("utf-8")
    lines = original.splitlines(True)
    nodes = [n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name in ("_following", "_fill")]
    assert len(nodes) == 2
    for node in sorted(nodes, key=lambda n: n.lineno, reverse=True):
        lines[node.lineno - 1:node.end_lineno] = (FOLLOW if node.name == "_following" else FILL).splitlines(True)
    source = "".join(lines)
    changes = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
    assert changes == ["_following", "_fill"]
    assert functions(original)["_decide"] == functions(source)["_decide"]
    compile(source, name, "exec")
    destination = BASE / name / "native_rules.py"
    assert not destination.exists()
    destination.parent.mkdir(parents=True)
    destination.write_text(source, encoding="utf-8", newline="\n")
    evidence = DOC / name
    evidence.mkdir(exist_ok=True)
    (evidence / "native_rules.patch").write_text("".join(difflib.unified_diff(
        original.splitlines(True), source.splitlines(True), fromfile=parent + "/noa/native_rules.py",
        tofile=name + "/noa/native_rules.py")), encoding="utf-8", newline="\n")
    item = dict(label=label, parent_sha256=expected, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                lines=len(source.splitlines()), changed_functions=changes, full_decide_and_original_NOA_block_byte_unchanged=True,
                role="matched-nonformation control, transform mode; not original NOA",
                formation_state_always_zero=True, rules_path=str(destination))
    sources[label] = source
    metadata.append((evidence, item))
g0, g0n = sources["G0"], sources["G0N"]
changes = [a.name for a, b in zip(ast.parse(g0).body, ast.parse(g0n).body) if ast.dump(a) != ast.dump(b)]
assert changes == ["_decide"]
old = """    if organized and not memory.joining:
        lane = _fill(ego, rows, 2 if preparing else lanes)
"""
new = """    if organized and not memory.joining:
        if not moving and preparing and ego.lane == 1 and _clear(ego, rows, 0) and any(
            c.lane == 2 and c.x >= drop_x - 360.0 and abs(c.x - ego.x) <= 50.0
            and not _clear(c, (ego, *rows), 1) and _clear(c, rows, 1)
            for c in rows
        ):
            memory = Memory(lane_target=0, joining=True)
            speed, target, memory = _join_speed(ego, rows, memory, 0)
            return action(speed, 0, "release_ending", target), memory
        lane = _fill(ego, rows, 2 if preparing else lanes)
"""
assert g0.count(old) == 1 and g0.replace(old, new) == g0n
for evidence, item in metadata:
    item["G0N_minus_G0_exactly_original_N_release"] = True
    (evidence / "source.json").write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(item))
assert all(path.read_bytes() == raw for path, raw in original_bytes.items())
assert production.read_bytes() == production_before
