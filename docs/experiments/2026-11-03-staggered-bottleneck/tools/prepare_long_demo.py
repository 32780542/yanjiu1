"""Freeze authorized 2400 m diagnostics: exactly two network-coordinate changes."""
import difflib
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
ROOT=BASE.parents[2]
OUT=BASE/'formation_demo_long'
RUNS=ROOT/'tmp/staggered_bottleneck/20261103_long_formation_demo'
assert not OUT.exists() and not RUNS.exists()
OUT.mkdir();RUNS.mkdir(parents=True)
SOURCES=['run_native_flow.py','experiments/native_sumo.py','experiments/global_reference.py',
         'experiments/complete_layers.py','noa/native_rules.py','research/common.py']
sha=lambda raw:hashlib.sha256(raw).hexdigest()
protocol=dict(purpose='Geometric diagnostic only; never pooled into original 1200 m efficiency samples',
    exit_x_m=2400,bottleneck_x_m=1000,preparation_x_m=640,upstream_lanes=3,downstream_lanes=2,
    duration_s=1,max_time_s=180,mode='transform',sumo_seed=1,scenario='lane_drop',diagnostic=True,
    original_input_byte_identity=True,original_initial_depart_s=0,original_initial_speed_mps=28.8,
    fixed_requested_times_s=[0,5,10,15,20],physical_t0_policy='first real physical frame at .1; no fabricated t=0 positions',
    preregistered_downstream_anchor='First stored frame by which each initial vehicle has been physically observed x>=1000 m',
    preregistered_downstream_offsets_s=[0,5,10,15],
    early_exit_policy='Record actual arrived/exited IDs before each selected frame; never infer whole-fleet completion from survivors',
    no_geometry_success_classifier=True,no_modulo_or_position_reordering=True,
    selected_geometry_ids=json.loads((BASE/'formation_demo/protocol.json').read_text())['selected_geometry_ids'],
    input_sha256={},runtimes={})
for demo in ['unformed24','formed45']:
    raw=(BASE/'formation_demo'/(demo+'_initial.json')).read_bytes()
    (OUT/(demo+'_initial.json')).write_bytes(raw);protocol['input_sha256'][demo]=sha(raw)
for tag,source,expected in [
    ('E2400',ROOT/'tmp/staggered_bottleneck/20261103_heldout_E40/sources/E','04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274'),
    ('J22400',ROOT/'tmp/staggered_bottleneck/20261103_J2_JT2_screen180_16/sources/J2','895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689')]:
    target=RUNS/'sources'/tag;original=OUT/'sources_original'/tag
    assert sha((source/'noa/native_rules.py').read_bytes())==expected
    before={};after={}
    for name in SOURCES:
        raw=(source/name).read_bytes();before[name]=sha(raw)
        (original/name).parent.mkdir(parents=True,exist_ok=True);(original/name).write_bytes(raw)
        if name=='experiments/native_sumo.py':
            old=raw.decode('utf-8');new=old.replace('("exit", 1200)','("exit", 2400)').replace('retained, 1000, 1200)','retained, 1000, 2400)')
            assert old!=new and old.count('("exit", 1200)')==1 and old.count('retained, 1000, 1200)')==1
            assert new.replace('("exit", 2400)','("exit", 1200)').replace('retained, 1000, 2400)','retained, 1000, 1200)')==old
            patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original/experiments/native_sumo.py',tofile=tag+'/experiments/native_sumo.py'))
            (OUT/(tag+'_network_only.patch')).write_text(patch,encoding='utf-8',newline='\n')
            assert len([s for s in patch.splitlines() if s.startswith('-') and not s.startswith('---')])==2
            assert len([s for s in patch.splitlines() if s.startswith('+') and not s.startswith('+++')])==2
            raw=new.encode('utf-8')
        compile(raw,name,'exec')
        (target/name).parent.mkdir(parents=True,exist_ok=True);(target/name).write_bytes(raw);after[name]=sha(raw)
    assert sum(before[k]!=after[k] for k in SOURCES)==1
    protocol['runtimes'][tag]=dict(original_runtime=str(source),frozen_runtime=str(target),
        rules_sha256=expected,original_sha256=before,extended_sha256=after,changed_source_files=['experiments/native_sumo.py'],
        source_change='Exactly two build_network 1200 exit coordinates -> 2400; five other sources byte-identical')
    (OUT/tag).mkdir()
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(dict(output=str(OUT),runtimes=list(protocol['runtimes']),source_files_per_runtime=6,
    changed_lines_per_runtime=2,registered_offsets_s=[0,5,10,15])))
