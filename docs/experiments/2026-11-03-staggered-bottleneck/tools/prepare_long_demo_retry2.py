"""Repair packaging in a new runtime; retain failed attempt and preregistration."""
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
ROOT=BASE.parents[2];OUT=BASE/'formation_demo_long'
p=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
assert not (OUT/'protocol_initial_attempt.json').exists()
(OUT/'protocol_initial_attempt.json').write_bytes((OUT/'protocol.json').read_bytes())
retry=ROOT/'tmp/staggered_bottleneck/20261103_long_formation_demo_retry2'
assert not retry.exists();retry.mkdir()
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
for tag,r in p['runtimes'].items():
    original=Path(r['original_runtime']);old=Path(r['frozen_runtime']);new=retry/'sources'/tag
    for name,h in r['extended_sha256'].items():
        assert sha(old/name)==h
        dest=new/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((old/name).read_bytes())
    support={}
    for name in ['configs/tools.json','experiments/__init__.py','noa/__init__.py','research/__init__.py']:
        src=original/name
        if src.exists():
            dest=new/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(src.read_bytes());support[name]=sha(dest)
    assert 'configs/tools.json' in support
    r.update(frozen_runtime=str(new),failed_attempt_runtime=str(old),support_file_sha256=support)
p.update(run_base=str(retry),retry_reason='Initial runtime packaging omitted unchanged original configs/tools.json; failed before SUMO, no controller modification',
    failed_operations=[
        '20261103T050215393520Z_E2400-demo-unformed24_2b4f777b',
        '20261103T050215354000Z_E2400-demo-formed45_80be89ad',
        '20261103T050215393520Z_J22400-demo-unformed24_86ceb589',
        '20261103T050215398809Z_J22400-demo-formed45_a6e2422e'])
(OUT/'protocol.json').write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(dict(run_base=str(retry),unchanged_support_files=True,controller_or_engine_changes_after_attempt1=False)))
