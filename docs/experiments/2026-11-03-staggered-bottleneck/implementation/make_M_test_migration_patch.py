"""Add only four explicit PD expectations to the fixed J2 memory patch."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

from run_core_with_rules import memory_test_patch


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PARENT_PATCH = OUT / "J2_test_migration.patch"
assert hashlib.sha256(PARENT_PATCH.read_bytes()).hexdigest() == "13aaefe37d8fd7705da74a00499a2b40601519c7df611072fce57ac9706a4640"
sources = memory_test_patch(PARENT_PATCH, text_only=True)
path = ROOT / "variants/phase5g_pure_formation/tests/test_head_group_rules.py"
parent = sources[path.resolve()]
lines, edits = parent.splitlines(True), []
names = {
    "test_real_lane_zero_head_c1_uses_fixed_phase_of_actual_a1",
    "test_real_lane_one_head_a1_uses_fixed_phase_of_actual_c1",
    "test_internal_b1_keeps_front_c1_and_couples_to_actual_body_a2",
    "test_internal_a2_keeps_front_a1_and_couples_to_actual_body_b1",
}
for node in ast.walk(ast.parse(parent)):
    if not isinstance(node, ast.FunctionDef) or node.name not in names:
        continue
    old = new = "".join(lines[node.lineno - 1:node.end_lineno])
    if "test_real_lane_" in node.name:
        new = new.replace("        self.assertLess(abs(r.POSITION_GAIN * error), 2.0)\n",
                          "        # u=.3*e+(v_peer-v_ego); this actual edge is unsaturated.\n"
                          "        phase_speed = r.POSITION_GAIN * error + (peer.speed - ego.speed)\n"
                          "        self.assertLess(abs(phase_speed), 2.0)\n")
        new = new.replace("self.assertAlmostEqual(target, ego.x + error)",
                          "self.assertAlmostEqual(target, ego.x + phase_speed / r.POSITION_GAIN)")
    else:
        new = new.replace("phase_speed = max(-2.0, min(2.0, r.POSITION_GAIN * error))",
                          "phase_speed = max(-2.0, min(2.0, r.POSITION_GAIN * error + (peer.speed - ego.speed)))")
    assert new != old
    edits.append((node.lineno - 1, node.end_lineno, new, node.name))
assert len(edits) == 4
for start, end, new, _ in sorted(edits, reverse=True):
    lines[start:end] = new.splitlines(True)
sources[path.resolve()] = "".join(lines)
changed_functions = []
old_tree = {n.name: ast.dump(n) for n in ast.walk(ast.parse(parent)) if isinstance(n, ast.FunctionDef)}
new_tree = {n.name: ast.dump(n) for n in ast.walk(ast.parse(sources[path.resolve()])) if isinstance(n, ast.FunctionDef)}
assert old_tree.keys() == new_tree.keys()
assert {n for n in old_tree if old_tree[n] != new_tree[n]} == names
patches, metadata = [], []
for filename, text in sources.items():
    original = filename.read_text(encoding="utf-8")
    compile(text, str(filename), "exec")
    relative = filename.relative_to(ROOT).as_posix()
    patches.append("".join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                               fromfile="a/" + relative, tofile="b/" + relative)))
    metadata.append(dict(path=relative, original_sha256=hashlib.sha256(filename.read_bytes()).hexdigest(),
                         modified_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                         m_changed_tests=sorted(names) if filename == path.resolve() else []))
target = OUT / "M_test_migration.patch"
assert not target.exists()
target.write_text("".join(patches), encoding="utf-8", newline="\n")
(OUT / "M_test_migration_sources.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(files=5, m_changed_tests=4, parent_j2_patch_unchanged=True,
                      patch_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), original_tests_edited=False)))
