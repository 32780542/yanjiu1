"""Read-only recheck of sealed physical J2 traces and E/H comparison artifacts."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import tarfile
import xml.etree.ElementTree as ET
from PIL import Image

OUT=Path(__file__).resolve().parent
E=OUT.parent/'formation_demo'
ROOT=OUT.parents[3]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocol=json.loads((OUT/'protocol.json').read_text())
audit=json.loads((OUT/'verification.json').read_text())
assert sha(OUT/'evidence_reviewed.tar.gz')==audit['archive_sha256']
assert sha(E/'evidence_reviewed.tar.gz')=='b97209b2612c27a4d177ea1595c929ad7b468adf3ae49488cc44e60987433585'
with tarfile.open(OUT/'evidence_reviewed.tar.gz') as t:
    manifest=json.loads(t.extractfile('manifest.json').read())
    for name,m in manifest.items():
        raw=t.extractfile(name).read()
        assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
assert len(manifest)==52
runtime=Path(protocol['frozen_runtime'])
for name,h in protocol['source_sha256'].items():assert sha(runtime/name)==h
assert sha(E/'analyze_and_plot.py')==protocol['E_plot_tool_sha256']
hplot=(OUT/'analyze_and_plot.py').read_text()
assert hplot.replace('20261103_J2_formation_demo','20261103_E_formation_demo').replace("'J2 / ","'E / ")== (E/'analyze_and_plot.py').read_text()
for name in ['unformed24','formed45']:
    assert (OUT/(name+'_initial.json')).read_bytes()==(E/(name+'_initial.json')).read_bytes()
proof=json.loads((OUT/'initial_equilibrium_check.json').read_text())
assert proof['rules_sha256']==protocol['rules_sha256']
assert len(proof['checks'])==45
assert all(r['following_requested_speed_mps']==28.8 for r in proof['checks'])

def rows(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

frames={};full_geometry_rows=0
for result in json.loads((OUT/'demo_results.json').read_text()):
    case=Path(result['case_dir']);name=result['demo']
    with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=[json.loads(s) for s in f]
    with gzip.open(case/'positions.jsonl.gz','rt') as f:pp=[json.loads(s) for s in f]
    assert len(ff)==len(pp)==audit['raw_frames'][name]
    actual=json.loads((case/'result.json').read_text())
    assert actual['safe'] and actual['all_completed'] and actual['collisions']==actual['teleports']==0
    for src,h in actual['source_sha256'].items():assert sha(runtime/src)==h
    for f,p in zip(ff,pp):
        assert f['time_s']==p['time_s']
        assert {k:[v['x'],v['y'],v['speed'],v['acceleration']] for k,v in f['states'].items()}==p['states']
        assert {k:v['formation_state'] for k,v in f['actions'].items()}==p['formation_states']
    frames[name]={f['time_s']:f for f in ff}
    initial={r['id']:r for r in json.loads((OUT/(name+'_initial.json')).read_text())}
    assert set(ff[0]['states'])==set(initial)
    assert all(ff[0]['states'][k]['x']==r['x'] and ff[0]['states'][k]['speed']==r['speed'] for k,r in initial.items())
    gg=rows(OUT/(name+'_geometry.csv.gz'))
    assert len(gg)==sum(len(f['states']) for f in ff)
    full_geometry_rows+=len(gg)
    for r in gg:r['demo']=name
    frames[name]['geometry']=gg

def verify_geometry(r):
    f=frames[r['demo']][float(r['time_s'])];ss=f['states'];s=ss[r['vehicle_id']]
    assert all(float(r[k])==s[v] for k,v in [('x_m','x'),('y_m','y'),('speed_mps','speed'),('lane','lane')])
    desired=5.5+(30-5.5)/28.8*s['speed']
    assert float(r['cth_D_m'])==desired
    front=min((k for k,v in ss.items() if k!=r['vehicle_id'] and v['x']>s['x'] and abs(v['y']-(s['lane']+.5)*3.3)<2.55),key=lambda k:(ss[k]['x'],ss[k]['y'],ss[k]['speed']),default=None)
    assert r['front_id']==(front or '')
    if front is None:assert r['front_gap_m']==r['front_gap_minus_cth_D_m']==''
    else:
        gap=ss[front]['x']-s['x']
        assert float(r['front_gap_m'])==gap and float(r['front_gap_minus_cth_D_m'])==gap-desired
        assert r['front_inside_existing_50m_following_range']==str(gap<=50)
    for lane in range(3):
        other=min((k for k,v in ss.items() if k!=r['vehicle_id'] and v['lane']==lane),key=lambda k:(abs(ss[k]['x']-s['x']),ss[k]['x'],ss[k]['y'],ss[k]['speed']),default=None) if abs(lane-s['lane'])==1 else None
        assert r[f'adj_lane{lane}_id']==(other or '')
        assert (float(r[f'adj_lane{lane}_signed_dx_m'])==ss[other]['x']-s['x']) if other else r[f'adj_lane{lane}_signed_dx_m']==''

for name in frames:
    for r in frames[name]['geometry']:verify_geometry(r)
derived_rows=0
for file in ['snapshot_states.csv','tail_window_states.csv','per_vehicle_downstream.csv']:
    rr=rows(OUT/file)
    for r in rr:verify_geometry(r)
    derived_rows+=len(rr)
cross_rows=rows(OUT/'cross_lane_pair_references.csv')
for r in cross_rows:
    ss=frames[r['demo']][float(r['time_s'])]['states'];s=ss[r['vehicle_id']];peer=ss[r['peer_id']]
    assert float(r['raw_signed_dx_m'])==peer['x']-s['x'] and float(r['reference_15_m'])==15
    assert float(r['speed_mps'])==s['speed'] and float(r['peer_speed_mps'])==peer['speed']
    assert float(r['reference_D_pair_mean_speed_half_m'])==(5.5+(30-5.5)/28.8*(s['speed']+peer['speed'])/2)/2
pngs=[]
for png in sorted(OUT.glob('*.png')):
    svg=png.with_suffix('.svg');ET.parse(svg)
    with Image.open(png) as im:
        dpi=im.info['dpi'];assert min(dpi)>299
        pngs.append(dict(png=png.name,svg=svg.name,pixels=im.size,dpi=dpi))
assert len(pngs)==7
links=re.findall(r'\]\(([^)]+)\)',(OUT/'README.md').read_text(encoding='utf-8'))
for link in links:assert (OUT/link.split('#')[0]).exists() or link=='final_verification.json',link
final=dict(archive_members_verified=len(manifest),archive_sha256=audit['archive_sha256'],
    E_archive_sha256_unchanged=sha(E/'evidence_reviewed.tar.gz'),physical_runs=2,
    E_H_initials_byte_identical=True,plotting_logic_equal_after_path_title_substitution=True,
    all_recorded_geometry_rechecked=True,full_geometry_rows=full_geometry_rows,
    selected_and_downstream_rows_rechecked=derived_rows,initial_45_equilibrium_verified=True,
    PNG_SVG_pairs=pngs,all_seven_figures_visually_reviewed=True,local_links=len(links),
    cross_lane_reference_rows_rechecked=len(cross_rows),no_additional_simulations=True)
(OUT/'final_verification.json').write_text(json.dumps(final,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in final.items() if k!='PNG_SVG_pairs'}))
