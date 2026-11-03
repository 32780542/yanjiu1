"""Run the actual installed controller and disk tests, without module injection."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
VARIANT = ROOT / 'variants/phase5g_pure_formation'
HERE = Path(__file__).resolve().parent
EXPECTED = '8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = VARIANT / 'noa/native_rules.py'
assert sha(source) == EXPECTED
old = json.loads((HERE / 'S_core14_minimal_migrated.json').read_text(encoding='utf-8'))
files = list(old['selected_files'])
assert len(files) == 14
files.append('tests/test_local_staggered_rules.py')
migration = json.loads((HERE / 'S_test_migration_sources.json').read_text())
for entry in migration:
    path = ROOT / entry['path']
    actual = hashlib.sha256(path.read_text(encoding='utf-8').encode()).hexdigest()
    assert actual == entry['modified_text_sha256'], path
before = {name: sha(VARIANT / name) for name in ['noa/native_rules.py', *files]}
result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-m', 'pytest', *files,
                         '-q', '--junitxml=' + str(HERE / 'installed_S_core.xml')], cwd=VARIANT)
assert before == {name: sha(VARIANT / name) for name in before}
(HERE / 'installed_S_core.json').write_text(json.dumps(dict(
    installed_source_sha256=EXPECTED, tests_on_disk=True, module_injection=False,
    test_files=files, source_and_test_hashes=before, returncode=result.returncode), indent=2) + '\n', encoding='utf-8')
raise SystemExit(result.returncode)
