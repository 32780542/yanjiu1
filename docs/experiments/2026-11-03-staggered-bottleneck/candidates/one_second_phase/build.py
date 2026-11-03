"""Shorten only the phase prediction, from 1/kp to one second."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / 'tmp/staggered_bottleneck/candidates/local_phase_velocity_damping/native_rules.py'
EXPECTED = 'a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762'
raw = PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED
old = raw.decode('utf-8')
before = '(difference + (peer.speed - ego.speed) / POSITION_GAIN)'
after = '(difference + 1.0 * (peer.speed - ego.speed))'
assert old.count(before) == 1
new = old.replace(before, after)
assert new.replace(after, before) == old
changed = [a.name for a, b in zip(ast.parse(old).body, ast.parse(new).body) if ast.dump(a) != ast.dump(b)]
assert changed == ['_following']
output = ROOT / 'tmp/staggered_bottleneck/candidates/one_second_phase/native_rules.py'
output.parent.mkdir(parents=True, exist_ok=True)
assert not output.exists(), output
output.write_bytes(new.encode('utf-8'))
(HERE / 'native_rules.patch').write_text(''.join(difflib.unified_diff(
    old.splitlines(True), new.splitlines(True), fromfile='M/native_rules.py',
    tofile='Q/native_rules.py')), encoding='utf-8')
(HERE / 'source.json').write_text(json.dumps(dict(parent_sha256=EXPECTED,
    sha256=hashlib.sha256(output.read_bytes()).hexdigest(), source=str(output),
    changed_functions=changed, horizon_s=1.0), indent=2) + '\n', encoding='utf-8')
print(output)
