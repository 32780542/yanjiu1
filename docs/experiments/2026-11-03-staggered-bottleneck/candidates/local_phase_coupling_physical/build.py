"""Freeze J2/JT2 by changing only the physical-neighbor bound of J0/JT0."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parents[2]
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
PARENTS = (
    ("J2", "local_phase_coupling", "local_phase_coupling_physical",
     "dd0b7f466de943976af8fe44e1f5b89dfbafe5ea8e86f6f242fcea7a22f75e53"),
    ("JT2", "time_scaled_phase_coupling", "time_scaled_phase_coupling_physical",
     "443e082742d1400ad03b4381e91cdace35cde522c48b6f11efd375ff89af287e"),
)
protected = {REPO / NAME: (REPO / NAME).read_bytes()}
e_path = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
protected[e_path] = e_path.read_bytes()
for label, parent_name, name, expected in PARENTS:
    parent_path = REPO / "tmp/staggered_bottleneck/candidates" / parent_name / "native_rules.py"
    original_bytes = parent_path.read_bytes()
    protected[parent_path] = original_bytes
    assert hashlib.sha256(original_bytes).hexdigest() == expected
    original = original_bytes.decode("utf-8")
    old, new = "        if 0 <= lane < lanes:\n", "        if 0 <= lane < 3:\n"
    assert original.count(old) == 1
    source = original.replace(old, new)
    assert source.replace(new, old) == original
    differences = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body)
                   if ast.dump(a) != ast.dump(b)]
    assert differences == ["_following"]
    compile(source, name + "/native_rules.py", "exec")
    destination = REPO / "tmp/staggered_bottleneck/candidates" / name / "native_rules.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source, encoding="utf-8", newline="\n")
    evidence = DOC / "candidates" / name
    evidence.mkdir(parents=True, exist_ok=True)
    patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                        fromfile=parent_name + "/" + NAME, tofile=name + "/" + NAME))
    (evidence / "native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
    metadata = dict(label=label, parent_candidate=parent_name, parent_sha256=expected,
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(), changed_functions=differences,
                    reverse_to_parent_exact=True, lines=len(source.splitlines()), rules_path=str(destination),
                    production_e_and_parent_unchanged=True)
    (evidence / "source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata))
assert all(path.read_bytes() == data for path, data in protected.items())
