"""LT: fixed L plus one symmetric headway scaling line in _pair_error."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
OLD = ROOT / "tmp/staggered_bottleneck/candidates/local_vacancy_bridge/native_rules.py"
NEW = ROOT / "tmp/staggered_bottleneck/candidates/local_time_scaled_phase/native_rules.py"
EXPECTED = "e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a"
raw = OLD.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED and not NEW.exists()
original = raw.decode("utf-8")
old = "    phase = _physical_phase(peer, 3) - _physical_phase(car, 3)\n"
new = old + "    phase *= (LENGTH + STANDSTILL + HEADWAY * (car.speed + peer.speed) / 2) / GAP\n"
assert original.count(old) == 1
source = original.replace(old, new)
assert source.replace(new, old) == original
changed = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
assert changed == ["_pair_error"]
compile(source, str(NEW), "exec")
NEW.parent.mkdir(parents=True)
NEW.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="local_vacancy_bridge/noa/native_rules.py", tofile="local_time_scaled_phase/noa/native_rules.py")),
    encoding="utf-8", newline="\n")
meta = dict(parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(), lines=len(source.splitlines()),
            changed_functions=changed, reverse_to_parent_exact=True, effective_line_increment=1,
            formula="phase *= (5.5 + HEADWAY * (vi+vj)/2) / GAP", fill_witness_safety_and_memory_unchanged=True,
            rules_path=str(NEW))
(DOC / "source.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
assert OLD.read_bytes() == raw
print(json.dumps(meta))
