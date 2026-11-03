"""Freeze default front range 60; all longitudinal formulas stay J2fast."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
OLD = ROOT / "tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py"
NEW = ROOT / "tmp/staggered_bottleneck/candidates/noa_range60/native_rules.py"
EXPECTED = "03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6"
original = OLD.read_text(encoding="utf-8")
assert hashlib.sha256(OLD.read_bytes()).hexdigest() == EXPECTED and not NEW.exists()
changes = [
    ("def _front_following(ego, rows):", "def _front_following(ego, rows, distance=60.0):"),
    ("(c for c in rows if 0.0 < c.x - ego.x <= 50.0 and _occupies(c, ego.lane, 0.0)),",
     "(c for c in rows if 0.0 < c.x - ego.x <= distance and _occupies(c, ego.lane, 0.0)),"),
]
source = original
for old, new in changes:
    assert source.count(old) == 1
    source = source.replace(old, new)
reverse = source
for old, new in reversed(changes):
    assert reverse.count(new) == 1
    reverse = reverse.replace(new, old)
assert reverse == original
changed = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
assert changed == ["_front_following"]
compile(source, str(NEW), "exec")
NEW.parent.mkdir(parents=True)
NEW.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="local_phase_coupling_fast/noa/native_rules.py", tofile="noa_range60/noa/native_rules.py")),
    encoding="utf-8", newline="\n")
metadata = dict(parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=changed, reverse_to_parent_exact=True, lines=len(source.splitlines()),
                default_front_distance=60., traffic_evaluation_mode="noa only", rules_path=str(NEW),
                note="The shared helper default changes all callers; do not interpret formation/fill as NOA sensitivity.")
(DOC / "source.json").write_text(json.dumps(metadata, indent=2) + "\n")
assert OLD.read_text(encoding="utf-8") == original
print(json.dumps(metadata))
