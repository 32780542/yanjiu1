"""Build the single-term L ablation from a hash-pinned parent."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / 'tmp/staggered_bottleneck/candidates/local_vacancy_bridge/native_rules.py'
EXPECTED = 'e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a'
raw = PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED
old = raw.decode('utf-8')
before = 'phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))'
after = 'phase_speed = 0.0  # Longitudinal-phase ablation; geometric fill is retained.'
assert old.count(before) == 1
new = old.replace(before, after)
assert new.replace(after, before) == old
output = ROOT / 'tmp/staggered_bottleneck/candidates/phase_off_L/native_rules.py'
output.parent.mkdir(parents=True, exist_ok=True)
assert not output.exists(), output
output.write_bytes(new.encode('utf-8'))
(HERE / 'native_rules.patch').write_text(''.join(difflib.unified_diff(
    old.splitlines(True), new.splitlines(True), fromfile='L/native_rules.py',
    tofile='LP0/native_rules.py')), encoding='utf-8')
(HERE / 'source.json').write_text(json.dumps(dict(parent_sha256=EXPECTED,
    sha256=hashlib.sha256(output.read_bytes()).hexdigest(), source=str(output),
    change='only phase_speed becomes zero; fill geometry and local relation flags remain'),
    indent=2) + '\n', encoding='utf-8')
print(output)
