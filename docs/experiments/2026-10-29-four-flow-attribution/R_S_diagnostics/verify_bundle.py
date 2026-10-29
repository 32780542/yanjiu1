"""Independent reader: verify exact archive members and logical source versions."""
import argparse
import ast
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile

BASE=Path(__file__).resolve().parent


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            block=stream.read(131072)
            if not block:break
            digest.update(block)
    return digest.hexdigest()


def read(name):
    return json.loads((BASE/name).read_text(encoding='utf-8'))


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--originals',action='store_true',help='also verify original local files and large trajectory references')
parser.add_argument('--report',type=Path,help='write verification JSON inside this directory only')
args=parser.parse_args()
manifest=read('bundle_manifest.json')
assert sha(BASE/'bundle_manifest.json')==(BASE/'bundle_manifest.sha256').read_text().split()[0]
for name,expected in manifest['files'].items():
    path=BASE/name
    assert path.resolve().is_relative_to(BASE)
    assert path.stat().st_size==expected['size'] and sha(path)==expected['sha256'],name

payloads={};member_count=0
for archive_name,expected in manifest['archives'].items():
    path=BASE/archive_name
    assert path.stat().st_size==expected['size'] and sha(path)==expected['sha256']
    declared={entry['path']:entry for entry in expected['members']}
    assert len(declared)==len(expected['members'])
    found=set()
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            name=PurePosixPath(member.name)
            assert not name.is_absolute() and '..' not in name.parts and member.isfile()
            assert member.name not in found and member.name in declared
            data=archive.extractfile(member).read();record=declared[member.name]
            assert member.size==len(data)==record['size']
            assert hashlib.sha256(data).hexdigest()==record['sha256'],(archive_name,member.name)
            payloads[(archive_name,member.name)]=data
            found.add(member.name);member_count+=1
    assert found==set(declared)

views={}
for label,view in manifest['source_views'].items():
    assert len(view['files'])==len(view['source_sha256'])==6
    sources={}
    for name,location in view['files'].items():
        data=(BASE/location['file']).read_bytes() if 'file' in location else payloads[(location['archive'],location['member'])]
        assert hashlib.sha256(data).hexdigest()==view['source_sha256'][name],(label,name)
        sources[name]=data
    views[label]=sources
assert manifest['source_views']['P_parent']['source_sha256']['noa/native_rules.py']=='8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864'
for name in views['P_parent']:
    if name!='noa/native_rules.py':assert views['P_parent'][name]==views['R'][name]==views['S'][name]

def definitions(data):
    return {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(data.decode('utf-8')).body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
defs={label:definitions(view['noa/native_rules.py']) for label,view in views.items()}
assert [n for n in defs['R'] if defs['R'][n]!=defs['P_parent'].get(n)]==['_front','_settled','_following','_fill']
assert [n for n in defs['S'] if defs['S'][n]!=defs['R'].get(n)]==['_following']
for name in ['Vehicle','Memory','_pair_error','_decide','safe_speed']:
    assert defs['P_parent'][name]==defs['R'][name]==defs['S'][name]

cases=read('case_index.json')
assert len(cases)==manifest['case_count']==12
assert sum(case['label'].startswith('six_') for case in cases)==4
for case in cases:
    archive=case['archive'];prefix=case['prefix']
    source=json.loads(payloads[(archive,prefix+'/input.json')])
    result=json.loads(payloads[(archive,prefix+'/result.json')])
    trips=json.loads(payloads[(archive,prefix+'/trips.json')])
    assert source['source_sha256']==result['source_sha256']==case['source_sha256']==manifest['source_views'][case['method']]['source_sha256']
    assert result['requested']==len(source['arrivals'])==len(trips)
    assert result['completed']==case['completed'] and result['status']==case['status']
    for filename in case['files']:assert (archive,prefix+'/'+filename) in payloads
    if case['label'].startswith('q1500'):
        assert (archive,prefix+'/positions.jsonl.gz') not in payloads
traces=read('positions_references.json')
assert len(traces)==12 and sum(not item['archived'] for item in traces)==8
originals=read('original_file_references.json')
assert len(originals)==manifest['original_reference_count']
checked=0
if args.originals:
    for item in originals:
        path=Path(item['path'])
        assert path.stat().st_size==item['size'] and sha(path)==item['sha256'],str(path)
        checked+=1
    for item in traces:
        path=Path(item['path'])
        assert path.stat().st_size==item['size'] and sha(path)==item['sha256']

size=sum(path.stat().st_size for path in BASE.rglob('*') if path.is_file())
assert size<3*1024*1024,size
report=dict(ok=True,archives_checked=len(manifest['archives']),archive_members_checked=member_count,
    logical_six_source_views=list(views),cases_checked=len(cases),large_positions_excluded=8,
    original_files_checked=checked,source_AST_scope_verified=True,bytes_before_report=size,
    simulation_run=False,controller_modified=False,Git_used=False)
if args.report:
    destination=args.report if args.report.is_absolute() else BASE/args.report
    assert destination.resolve().is_relative_to(BASE)
    with destination.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(report))
