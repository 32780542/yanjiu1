"""Freeze L's witnessed single-vacancy fallback from fixed J2fast."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
OLD = ROOT / "tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py"
NEW = ROOT / "tmp/staggered_bottleneck/candidates/local_vacancy_bridge/native_rules.py"
EXPECTED = "03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6"
protected = [OLD, ROOT / "tmp/staggered_bottleneck/candidates/local_phase_coupling_physical/native_rules.py",
             ROOT / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py",
             ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"]
before = {p: p.read_bytes() for p in protected}
assert hashlib.sha256(before[OLD]).hexdigest() == EXPECTED and not NEW.exists()
changes = [
    ("def _front_following(ego, rows):\n", "def _front_following(ego, rows, distance=50.0):\n"),
    ("(c for c in rows if 0.0 < c.x - ego.x <= 50.0 and _occupies(c, ego.lane, 0.0)),",
     "(c for c in rows if 0.0 < c.x - ego.x <= distance and _occupies(c, ego.lane, 0.0)),"),
    ("    following = _front_following(ego, rows)\n    cars = (ego, *rows)\n", """    following = _front_following(ego, rows)
    if following[2] is None:
        extended = _front_following(ego, rows, 2 * GAP)
        front = next((c for c in rows if c.track == extended[2]), None)
        if front is not None and any(
            abs(c.lane - ego.lane) == 1 and ego.x < c.x < front.x
            and abs(c.x + _physical_phase(c, 3) - _physical_phase(ego, 3) - (front.x - GAP)) <= 2.0
            for c in rows
        ):
            following = extended
    cars = (ego, *rows)
"""),
]
source = original = before[OLD].decode()
for old, new in changes:
    assert source.count(old) == 1
    source = source.replace(old, new)
reverse = source
for old, new in reversed(changes):
    assert reverse.count(new) == 1
    reverse = reverse.replace(new, old)
assert reverse == original
changed = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
assert changed == ["_front_following", "_following"]
compile(source, str(NEW), "exec")
NEW.parent.mkdir(parents=True)
NEW.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(
    original.splitlines(True), source.splitlines(True), fromfile="local_phase_coupling_fast/noa/native_rules.py",
    tofile="local_vacancy_bridge/noa/native_rules.py")), encoding="utf-8", newline="\n")
metadata = dict(parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=changed, reverse_to_parent_exact=True, lines=len(source.splitlines()),
                effective_line_increment=sum(bool(l.strip()) for l in source.splitlines())-
                                         sum(bool(l.strip()) for l in original.splitlines()),
                rules_path=str(NEW), original_sources_unchanged=True)
(DOC / "source.json").write_text(json.dumps(metadata, indent=2) + "\n")
assert all(p.read_bytes() == content for p, content in before.items())
print(json.dumps(metadata))
