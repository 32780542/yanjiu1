"""Freeze L only; reuse the original long-road input/geometry/plot contract."""
import difflib
import hashlib
import json
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
ROOT=BASE.parents[2]
OLD=BASE/'formation_demo_long';OUT=BASE/'formation_demo_L_long'
RUNS=ROOT/'tmp/staggered_bottleneck/20261103_L_long_formation_demo'
SOURCE=ROOT/'tmp/staggered_bottleneck/20261103_L_screen180_8/sources/L'
EXPECTED='e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(SOURCE/'noa/native_rules.py')==EXPECTED
assert not OUT.exists() and not RUNS.exists()
OUT.mkdir();RUNS.mkdir(parents=True)
p=json.loads((OLD/'protocol.json').read_text());p['runtimes']={};p['run_base']=str(RUNS)
for key in ['retry_reason','failed_operations']:p.pop(key,None)
p.update(purpose='L same-input 2400 m local geometric diagnostic; never official traffic efficiency',physical_runs_planned=2,compare_to_frozen_J2_long=True)
for demo in ['unformed24','formed45']:(OUT/(demo+'_initial.json')).write_bytes((OLD/(demo+'_initial.json')).read_bytes())
tag='L2400';target=RUNS/'sources'/tag;original=OUT/'sources_original'/tag
files=list(json.loads((OLD/'protocol.json').read_text())['runtimes']['J22400']['original_sha256'])
before={};after={}
for name in files:
    raw=(SOURCE/name).read_bytes();before[name]=hashlib.sha256(raw).hexdigest()
    dest=original/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    if name=='experiments/native_sumo.py':
        old=raw.decode();new=old.replace('("exit", 1200)','("exit", 2400)').replace('retained, 1000, 1200)','retained, 1000, 2400)')
        assert new!=old and old.count('("exit", 1200)')==old.count('retained, 1000, 1200)')==1
        patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original/experiments/native_sumo.py',tofile=tag+'/experiments/native_sumo.py'))
        (OUT/(tag+'_network_only.patch')).write_text(patch,encoding='utf-8');raw=new.encode()
    compile(raw,name,'exec');dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);after[name]=sha(dest)
support={}
for name in ['configs/tools.json','experiments/__init__.py','noa/__init__.py','research/__init__.py']:
    dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((SOURCE/name).read_bytes());support[name]=sha(dest)
assert sum(before[k]!=after[k] for k in files)==1
p['runtimes'][tag]=dict(original_runtime=str(SOURCE),frozen_runtime=str(target),rules_sha256=EXPECTED,original_sha256=before,extended_sha256=after,support_file_sha256=support,changed_source_files=['experiments/native_sumo.py'],source_change='Only two exit coordinates1200->2400')
(OUT/tag).mkdir()
(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8')
extract=(OLD/'extract_long_demo.py').read_text().replace('physical_runs=4','physical_runs=2')
(OUT/'extract_long_demo.py').write_text(extract,encoding='utf-8')
(OUT/'plot_long_demo.py').write_bytes((OLD/'plot_long_demo.py').read_bytes())
print(json.dumps(dict(source_rules_sha256=sha(SOURCE/'noa/native_rules.py'),output=str(OUT),frozen_runtime=str(target),controller_unchanged=True,network_changed_lines=2)))
