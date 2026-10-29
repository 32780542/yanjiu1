"""Freeze the existing analysis code with enum/label-only cooperative support."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

package = Path(__file__).resolve().parent
root = package.parents[1]
frozen = root / "tmp/four_flow_D_analysis_frozen"
manifest = json.loads((frozen / "freeze.json").read_text(encoding="utf-8"))
destination = package / "analysis_source"
destination.mkdir(exist_ok=False)
for relative, digest in manifest["source_sha256"].items():
    content = (frozen / relative).read_bytes()
    assert hashlib.sha256(content).hexdigest() == digest
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
patches = {
    "experiments/native_comparison.py": [
        ('MODES = ("noa", "formation", "transform", "global")', 'MODES = ("noa", "formation", "transform", "global", "cooperative")'),
        ('    transform="Distributed formation + lane-drop transform",', '    transform="Distributed formation + lane-drop transform",\n    cooperative="Cooperative merge only; grouping and layer fill disabled",'),
    ],
    "experiments/bottleneck_attribution.py": [
        ('MODES = ("noa", "formation", "transform")', 'MODES = ("noa", "formation", "transform", "cooperative")'),
    ],
}
diff = []
for relative, replacements in patches.items():
    path = destination / relative
    before = path.read_text(encoding="utf-8")
    after = before
    for old, new in replacements:
        assert after.count(old) == 1
        after = after.replace(old, new)
    path.write_text(after, encoding="utf-8")
    def functions(code):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(code).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert functions(before) == functions(after), relative
    diff.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="frozen/"+relative, tofile="cooperative_enum_only/"+relative))
(destination / "enum_label_only.patch").write_text("".join(diff), encoding="utf-8")
report = dict(parent=str(frozen), parent_source_sha256=manifest["source_sha256"], source_sha256={relative: hashlib.sha256((destination / relative).read_bytes()).hexdigest() for relative in manifest["source_sha256"]}, changed_source_files=list(patches), all_function_and_class_AST_identical=True, changes="cooperative enum/label only; no evaluation formula or threshold changes; no runtime monkeypatch")
(destination / "freeze.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
print(json.dumps(report))
