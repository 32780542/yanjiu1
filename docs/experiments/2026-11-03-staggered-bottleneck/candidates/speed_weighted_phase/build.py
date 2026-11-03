"""One feedback-weight increment on immutable, behavior-equivalent J2fast."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
PARENT = REPO / "tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py"
EXPECTED = "03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6"
raw = PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED
original = raw.decode("utf-8")
old = "                error += difference / max(1, pair_lanes - 1)"
new = """                weight = min(1.0, (ego.speed + peer.speed) / (2 * CRUISE))
                error += weight * difference / max(1, pair_lanes - 1)"""
assert original.count(old) == 1
source = original.replace(old, new)
assert source.replace(new, old) == original
differences = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body)
               if ast.dump(a) != ast.dump(b)]
assert differences == ["_following"]
destination = REPO / "tmp/staggered_bottleneck/candidates/speed_weighted_phase/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
name = "variants/phase5g_pure_formation/noa/native_rules.py"
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="J2fast/" + name, tofile="K/" + name))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
metadata = dict(label="K", parent_sha256=EXPECTED, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=differences, lines=len(source.splitlines()), rules_path=str(destination),
                normalization="symmetric observed mean speed / existing cruise; capped at one")
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
