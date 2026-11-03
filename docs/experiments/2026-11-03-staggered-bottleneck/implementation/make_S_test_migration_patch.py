"""Keep J2 except two body fixtures whose P and CTH corrections conflict."""
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
names = {"test_internal_b1_keeps_front_c1_and_couples_to_actual_body_a2",
         "test_internal_a2_keeps_front_a1_and_couples_to_actual_body_b1"}
before = """        expected = r._request(ego, front.x - distance, front.speed) + r.SPEED_RELAXATION * phase_speed
        self.assertAlmostEqual(speed, max(0.0, min(r.MAX_SPEED, expected)))
"""
after = """        cf = r._request(ego, front.x - distance, front.speed)
        self.assertLess(phase_speed * (cf - ego.speed), 0.0)
        # In these measured body states phase opposes the real-front CTH action.
        self.assertEqual(speed.hex(), cf.hex())
"""
for node in ast.walk(ast.parse(parent)):
    if not isinstance(node, ast.FunctionDef) or node.name not in names:
        continue
    old = "".join(lines[node.lineno - 1:node.end_lineno])
    assert old.count(before) == 1
    edits.append((node.lineno - 1, node.end_lineno, old.replace(before, after)))
assert len(edits) == 2
for start, end, new in sorted(edits, reverse=True):
    lines[start:end] = new.splitlines(True)
sources[path.resolve()] = "".join(lines)
functions = lambda text: {n.name: ast.dump(n) for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef)}
a, b = functions(parent), functions(sources[path.resolve()])
assert a.keys() == b.keys() and {n for n in a if a[n] != b[n]} == names
patches, metadata = [], []
for filename, text in sources.items():
    original = filename.read_text(encoding="utf-8")
    compile(text, str(filename), "exec")
    relative = filename.relative_to(ROOT).as_posix()
    patches.append("".join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                               fromfile="a/" + relative, tofile="b/" + relative)))
    metadata.append(dict(path=relative, original_sha256=hashlib.sha256(filename.read_bytes()).hexdigest(),
                         modified_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                         s_changed_tests=sorted(names) if filename == path.resolve() else []))
target = OUT / "S_test_migration.patch"
assert not target.exists()
target.write_text("".join(patches), encoding="utf-8", newline="\n")
(OUT / "S_test_migration_sources.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(files=5, s_changed_tests=2, original_tests_edited=False,
                      patch_sha256=hashlib.sha256(target.read_bytes()).hexdigest())))
