"""Freeze D1 and original two initial tapes, only extend the two exit coordinates."""
import difflib,hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;BASE=OUT.parent;ROOT=BASE.parents[2]
OLD=BASE/'formation_demo_S_long'
RUNS=ROOT/'tmp/staggered_bottleneck/20261103_D1_long_formation_demo'
SOURCE=ROOT/'tmp/staggered_bottleneck/20261103_S_screen180_8/sources/S'
CANDIDATE=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py'
EXPECTED='2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(CANDIDATE)==EXPECTED
assert sha(SOURCE/'noa/native_rules.py')=='8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'
assert not RUNS.exists() and not (OUT/'protocol.json').exists()
RUNS.mkdir(parents=True);tag='D12400';target=RUNS/'sources'/tag;original=OUT/'sources_original'/tag
p=json.loads((OLD/'protocol.json').read_text());oldruntime=p['runtimes']['S2400']
p['runtimes']={};p['run_base']=str(RUNS)
for k in ['retry_reason','failed_operations','compare_to_frozen_J2_long']:p.pop(k,None)
p.update(purpose='D1 same original24/45 tapes;2400m local geometry diagnostic, not traffic experiment',physical_runs_planned=2,compare_to_frozen_S_long=True,flow_metadata_veh_h_lane=1750.,demand_override='Exact original initial tapes override generated demand;duration1 metadata only',preregistered_downstream_offsets_s=[0,5,10,15,20,25])
for demo in ['unformed24','formed45']:
    path=OUT/(demo+'_initial.json');path.write_bytes((OLD/(demo+'_initial.json')).read_bytes());assert sha(path)==p['input_sha256'][demo]
before={};after={}
for name in oldruntime['original_sha256']:
    raw=CANDIDATE.read_bytes() if name=='noa/native_rules.py' else (SOURCE/name).read_bytes()
    if name!='noa/native_rules.py':assert hashlib.sha256(raw).hexdigest()==oldruntime['original_sha256'][name]
    dest=original/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);before[name]=sha(dest)
    if name=='experiments/native_sumo.py':
        a=raw.decode();assert a.count('("exit", 1200)')==a.count('retained, 1000, 1200)')==1
        b=a.replace('("exit", 1200)','("exit", 2400)').replace('retained, 1000, 1200)','retained, 1000, 2400)')
        (OUT/(tag+'_network_only.patch')).write_text(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='original/experiments/native_sumo.py',tofile=tag+'/experiments/native_sumo.py')),encoding='utf-8');raw=b.encode()
    compile(raw,name,'exec');dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);after[name]=sha(dest)
support={}
for name in ['configs/tools.json','experiments/__init__.py','noa/__init__.py','research/__init__.py']:
    dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((SOURCE/name).read_bytes());support[name]=sha(dest)
assert sum(before[k]!=after[k] for k in before)==1 and before['noa/native_rules.py']==EXPECTED
p['runtimes'][tag]=dict(original_runtime=str(original),base_frozen_S_runtime=str(SOURCE),candidate_source=str(CANDIDATE),candidate_lines=len(CANDIDATE.read_text(encoding='utf-8').splitlines()),frozen_runtime=str(target),rules_sha256=EXPECTED,original_sha256=before,extended_sha256=after,support_file_sha256=support,changed_source_files=['experiments/native_sumo.py'],source_change='Only two exit coordinate lines1200->2400;all controller/nonengine sources unchanged')
(OUT/tag).mkdir()
(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8')
extract=(OLD/'extract_long_demo.py').read_text();(OUT/'extract_long_demo.py').write_text(extract,encoding='utf-8')
plot=(OLD/'plot_long_demo.py').read_text().replace("9 if kind=='fixed' else 8","9 if kind=='fixed' else 12").replace('plt.subplots(4,3,figsize=(15,11)','plt.subplots(len(result[\'registered_downstream_times_s\']),3,figsize=(15,16)').replace('anchor + 0/5/10/15 s','anchor + 0/5/10/15/20/25 s')
(OUT/'plot_long_demo.py').write_text(plot,encoding='utf-8')
verify=(OLD/'verify_long_demo.py').read_text().replace('for t in [0,5,10,15]','for t in [0,5,10,15,20,25]').replace('registered_frames=8','registered_frames=12')
# Presence is measured, not a new admission test: retain exits and absent IDs.
verify=verify.replace("        assert set(frames[key][t]['states'])==set(initial)","        assert set(frames[key][t]['states'])<=set(initial)").replace("        assert all(r['exited_s']>t for r in trips)","        assert len(frames[key][t]['states'])==len(initial)-sum(r['exited_s']<t for r in trips)")
verify=verify.replace("summary=rows(OUT/'snapshot_summary.csv');assert len(summary)==18","summary=rows(OUT/'snapshot_summary.csv');assert len(summary)==22")
verify=verify.replace("    if r['frame_kind']=='registered_downstream':assert r['absent_initial_n']=='0' and r['all_initial_still_present']=='True'","    assert int(r['absent_initial_n'])==len(initials_by_demo[r['demo']])-len(ss)")
verify=verify.replace("summary=rows(OUT/'snapshot_summary.csv');assert len(summary)==22","initials_by_demo={n:json.loads((OUT/(n+'_initial.json')).read_text()) for n in ['unformed24','formed45']}\nsummary=rows(OUT/'snapshot_summary.csv');assert len(summary)==22")
verify=verify.replace('all_initial_vehicles_present_at_all_registered_downstream_frames=True',"all_initial_vehicles_present_at_all_registered_downstream_frames=all(r['absent_initial_n']=='0' for r in summary if r['frame_kind']=='registered_downstream')")
(OUT/'verify_long_demo.py').write_text(verify,encoding='utf-8')
print(json.dumps(dict(candidate_rules_sha256=EXPECTED,candidate_lines=p['runtimes'][tag]['candidate_lines'],runtime=str(target),output=str(OUT),input_sha256=p['input_sha256'],network_changed_lines=2,all_other_source_sha_exact=True)))
