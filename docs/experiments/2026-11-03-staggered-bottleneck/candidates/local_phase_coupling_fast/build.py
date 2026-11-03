"""Freeze J2fast from fixed J2; only reuse pure work within one call."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
OLD = ROOT / "tmp/staggered_bottleneck/candidates/local_phase_coupling_physical/native_rules.py"
NEW = ROOT / "tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py"
EXPECTED = "895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689"
assert not NEW.exists()
protected = [OLD, ROOT / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py",
             ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"]
before = {p: p.read_bytes() for p in protected}
assert hashlib.sha256(before[OLD]).hexdigest() == EXPECTED
oracle = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/source.json"
assert json.loads(oracle.read_text())["saved_before_fast_source"]
changes = [
    ("    costs = {}\n", """    costs, before_speeds = {}, {}

    def cf_cached(car, snapshot, cache):
        if car.track not in cache:
            cache[car.track] = cf_speed(car, snapshot)
        return cache[car.track]
"""),
    ("        new_rear = followers[0]\n", "        new_rear = followers[0]\n        after_speeds = {}\n"),
    ("cf_speed(new_rear, after) < new_rear.speed", "cf_cached(new_rear, after, after_speeds) < new_rear.speed"),
    ("""        cost = sum(max(0.0, cf_speed(c, observed) - cf_speed(
            moved if c.track == car.track else c, after)) for c in affected)
""", """        cost = sum(max(0.0, cf_cached(c, observed, before_speeds) - cf_cached(
            moved if c.track == car.track else c, after, after_speeds)) for c in affected)
"""),
    ("""    for front in neighbors:
        shared = any(_occupies(ego, lane) and _occupies(front, lane) for lane in range(3))
        if 0.0 < front.x - ego.x <= 200.0 and shared:
""", """    occupied = tuple(lane for lane in range(3) if _occupies(ego, lane))
    for front in neighbors:
        if not 0.0 < front.x - ego.x <= 200.0:
            continue
        shared = any(_occupies(front, lane) for lane in occupied)
        if shared:
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
assert changed == ["_fill", "safe_speed"]
compile(source, str(NEW), "exec")
NEW.parent.mkdir(parents=True)
NEW.write_text(source, encoding="utf-8", newline="\n")
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="local_phase_coupling_physical/noa/native_rules.py", tofile="local_phase_coupling_fast/noa/native_rules.py"))
(DOC / "native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
metadata = dict(parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=changed, reverse_to_parent_exact=True, lines=len(source.splitlines()),
                effective_line_increment=sum(bool(l.strip()) for l in source.splitlines())-
                                         sum(bool(l.strip()) for l in original.splitlines()),
                oracle_metadata_sha256=hashlib.sha256(oracle.read_bytes()).hexdigest(),
                rules_path=str(NEW), original_sources_unchanged=True)
(DOC / "source.json").write_text(json.dumps(metadata, indent=2) + "\n")
assert all(p.read_bytes() == content for p, content in before.items())
print(json.dumps(metadata))
