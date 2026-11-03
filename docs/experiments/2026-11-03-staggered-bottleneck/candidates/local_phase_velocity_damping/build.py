"""Freeze M by changing one existing local mutual-edge contribution of L."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
OLD = ROOT / "tmp/staggered_bottleneck/candidates/local_vacancy_bridge/native_rules.py"
NEW = ROOT / "tmp/staggered_bottleneck/candidates/local_phase_velocity_damping/native_rules.py"
EXPECTED = "e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a"
raw = OLD.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED and not NEW.exists()
original = raw.decode("utf-8")
old = "                error += difference / max(1, pair_lanes - 1)\n"
new = "                error += (difference + (peer.speed - ego.speed) / POSITION_GAIN) / max(1, pair_lanes - 1)\n"
assert original.count(old) == 1
source = original.replace(old, new)
assert source.replace(new, old) == original
changed = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
assert changed == ["_following"]
compile(source, str(NEW), "exec")
NEW.parent.mkdir(parents=True)
NEW.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="local_vacancy_bridge/noa/native_rules.py", tofile="local_phase_velocity_damping/noa/native_rules.py")),
    encoding="utf-8", newline="\n")
meta = dict(parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            changed_functions=changed, reverse_to_parent_exact=True, lines=len(source.splitlines()),
            rules_path=str(NEW), original_parent_unchanged=True)
(DOC / "source.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
assert OLD.read_bytes() == raw
print(json.dumps(meta))
