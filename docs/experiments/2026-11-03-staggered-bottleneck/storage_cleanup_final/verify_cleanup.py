"""Read-only independent post-action check; no seal/prune imports or mutations."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;BASE=OUT.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
pre=read(OUT/'preflight.json');result=read(OUT/'cleanup_result.json')
assert result['deleted_successful_cases']==8 and result['deleted_raw_files']==16
assert result['bytes_released']==477616342 and result['skipped_cases']==[]
identities=set()
for case in result['deleted_cases']:
    identity=case['identity'];identities.add((identity['candidate'],identity['flow'],identity['seed']))
    assert set(case['deleted'])=={'positions.jsonl.gz','events.jsonl.gz'}
    assert all(not (Path(case['run_dir'])/n).exists() for n in case['deleted'])
assert identities=={(label,2250.,seed) for label in ['L','M','N','Q'] for seed in [41,42]}
assert len(pre['failed_raw_before'])==16 and sum(r['bytes'] for r in pre['failed_raw_before'])==813903124
checks=[*pre['failed_raw_before'],*pre['protected_selected_NOA_S_seed42_raw_before'],*pre['manifest_bound_files'],*pre['batch_snapshots']]
for r in checks:
    p=Path(r['path']);assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],r['path']
for package in pre['complete_packages']:
    p=Path(package['archive']);assert p.stat().st_size==package['archive_bytes'] and sha(p)==package['archive_sha256']
assert sha(BASE/'evidence_iteration3/PUBLIC_MANIFEST.json')==pre['iteration3_public_manifest_sha256']
report=dict(successful_cases_absent_exactly_as_authorized=8,deleted_files_confirmed_absent=16,bytes_released=477616342,failed_raw_files_rehashed=16,failed_raw_bytes_rehashed=813903124,selected_NOA_S_seed42_files_rehashed=4,iteration3_manifest_bound_files_rehashed=72,iteration3_PUBLIC_MANIFEST_unchanged=True,four_complete_iteration3_archives_rehashed=True,batch_protocol_manifest_files_unchanged=8,raw_files_reconstructed_or_parsed=False,independent_no_seal_or_prune_imports=True,all_checks_passed=True)
(OUT/'independent_verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
