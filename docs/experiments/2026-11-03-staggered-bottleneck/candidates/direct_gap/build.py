"""Delete anticipatory waiting chains; keep real-gap distributed transformation."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[5]
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
original = subprocess.check_output(["git", "show", BASE + ":" + NAME], cwd=REPO).decode("utf-8")
lines = original.splitlines(True)
tree = ast.parse(original)
removed = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in ("_make_room", "_receiving", "_receiving_distance"):
        removed.append((node.lineno - 1, node.end_lineno))
    if isinstance(node, ast.FunctionDef) and node.name == "_decide":
        for statement in node.body:
            if isinstance(statement, ast.If) and ast.unparse(statement.test) == "preparing and mode == 'transform'":
                removed.append((statement.lineno - 1, statement.end_lineno))
assert len(removed) == 4
for start, end in sorted(removed, reverse=True):
    del lines[start:end]
source = "".join(lines)
while "\n\n\n\n" in source:
    source = source.replace("\n\n\n\n", "\n\n\n")
compile(source, "direct_gap/native_rules.py", "exec")
destination = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="a/" + NAME, tofile="b/" + NAME))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
metadata = dict(base_commit=BASE, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                lines=len(source.splitlines()), removed_functions=["_make_room", "_receiving", "_receiving_distance"],
                changed_functions=["_decide"], equivalent_to="NC", production_unchanged=True,
                noa_control_unchanged=True, rules_path=str(destination))
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
