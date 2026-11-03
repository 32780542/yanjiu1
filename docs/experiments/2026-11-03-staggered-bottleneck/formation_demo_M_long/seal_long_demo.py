"""Package immutable inputs, sources, full traces, audit logs and reviewed figures."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
p=json.loads((OUT/'protocol.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
files={}
def add(path,name):
    assert name not in files
    files[name]=path
for f in OUT.rglob('*'):
    if f.is_file() and '__pycache__' not in f.parts and f.name not in ['evidence_reviewed.tar.gz','archive_verification.json']:
        add(f,'reviewed/'+f.relative_to(OUT).as_posix())
for tag,runtime in p['runtimes'].items():
    frozen=Path(runtime['frozen_runtime'])
    for name in {**runtime['extended_sha256'],**runtime['support_file_sha256']}:
        add(frozen/name,'frozen_runtime/'+tag+'/'+name)
for run in json.loads((OUT/'demo_results.json').read_text()):
    case=Path(run['case_dir'])
    for f in case.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:add(f,'raw/'+run['version']+'/'+run['demo']+'/'+f.relative_to(case).as_posix())
add(OUT.parent/'formation_demo/analyze_and_plot.py','reference/original_E_geometry_and_plotting.py')
add(Path('C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py'),'reference/academic_figure_style.py')
ops=ROOT/'results/operations'
chosen=[]
for d in ops.iterdir():
    if d.is_dir() and (d/'result.json').exists() and (d.name in p.get('failed_operations',[]) or any(t in d.name for t in ['M2400-demo-','M-long-'])):
        chosen.append(d.name)
        for f in d.rglob('*'):
            if f.is_file():add(f,'operations/'+d.name+'/'+f.relative_to(d).as_posix())
manifest={name:dict(bytes=f.stat().st_size,sha256=sha(f.read_bytes())) for name,f in sorted(files.items())}
archive=OUT/'evidence_reviewed.tar.gz'
assert not archive.exists(),'Use a new archive name instead of overwriting a sealed archive'
with tarfile.open(archive,'w:gz',compresslevel=9) as t:
    raw=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('manifest.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for name,f in sorted(files.items()):t.add(f,arcname=name,recursive=False)
assert archive.stat().st_size<20_000_000
with tarfile.open(archive) as t:
    stored=json.loads(t.extractfile('manifest.json').read());assert stored==manifest
    assert len(t.getmembers())==len(manifest)+1
    for name,m in stored.items():
        raw=t.extractfile(name).read();assert len(raw)==m['bytes'] and sha(raw)==m['sha256']
result=dict(archive=archive.name,archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,archive_members_including_manifest=len(manifest)+1,all_member_hashes_rechecked=True,operation_directories=sorted(chosen),includes_both_full_positions_events_diagnostic=True,includes_failed_pre_SUMO_attempts=False,no_pruning=True)
(OUT/'archive_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='operation_directories'}))
