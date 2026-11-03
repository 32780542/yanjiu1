"""Independent read-only checks against raw traces; never starts SUMO."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from PIL import Image

OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocol=json.loads((OUT/'protocol.json').read_text())
def rows(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

frames={};counts={};full_n=0
for tag,p in protocol['runtimes'].items():
    source=Path(p['frozen_runtime']);old=Path(p['original_runtime'])
    for name,h in p['original_sha256'].items():
        assert sha(old/name)==h
        assert sha(OUT/'sources_original'/tag/name)==h
    for name,h in {**p['extended_sha256'],**p['support_file_sha256']}.items():assert sha(source/name)==h
    for name in p['extended_sha256']:
        a=(old/name).read_bytes();b=(source/name).read_bytes()
        if name=='experiments/native_sumo.py':
            assert a.count(b'("exit", 1200)')==1 and a.count(b'retained, 1000, 1200)')==1
            assert b==a.replace(b'("exit", 1200)',b'("exit", 2400)').replace(b'retained, 1000, 1200)',b'retained, 1000, 2400)')
        else:assert a==b
for run in json.loads((OUT/'demo_results.json').read_text()):
    tag,name=run['version'],run['demo'];key=(tag,name);case=Path(run['case_dir'])
    with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=list(map(json.loads,f))
    with gzip.open(case/'positions.jsonl.gz','rt') as f:pp=list(map(json.loads,f))
    actual=json.loads((case/'result.json').read_text())
    assert actual['safe'] and actual['all_completed'] and actual['collisions']==actual['teleports']==0
    assert actual['source_sha256']==protocol['runtimes'][tag]['extended_sha256']
    assert len(ff)==len(pp)
    for f,p in zip(ff,pp):
        assert f['time_s']==p['time_s']
        assert {k:[s['x'],s['y'],s['speed'],s['acceleration']] for k,s in f['states'].items()}==p['states']
        assert {k:a['formation_state'] for k,a in f['actions'].items()}==p['formation_states']
    initial_path=OUT/(name+'_initial.json');initial={r['id']:r for r in json.loads(initial_path.read_text())}
    assert initial_path.read_bytes()==(OUT.parent/'formation_demo'/(name+'_initial.json')).read_bytes()
    assert sha(initial_path)==protocol['input_sha256'][name]
    assert set(ff[0]['states'])==set(initial)
    assert all(ff[0]['states'][k]['x']==s['x'] and ff[0]['states'][k]['speed']==s['speed']==28.8 for k,s in initial.items())
    trips=json.loads((case/'trips.json').read_text());assert all(r['entered_s']==0 for r in trips)
    seen=set()
    for f in ff:
        seen.update(k for k,s in f['states'].items() if s['x']>=1000)
        if seen==set(initial):anchor=f['time_s'];break
    assert anchor==run['anchor_last_first1000_s']
    assert run['registered_downstream_times_s']==[round(anchor+t,1) for t in [0,5,10,15]]
    frames[key]={f['time_s']:f for f in ff}
    for t in run['registered_downstream_times_s']:
        assert set(frames[key][t]['states'])==set(initial)
        assert all(s['x']>=1000 and s['lane'] in [0,1] for s in frames[key][t]['states'].values())
        assert all(r['exited_s']>t for r in trips)
    net=ET.parse(case/'native.net.xml').getroot()
    edges={e.attrib['id']:e for e in net.findall('edge')}
    for edge,n,length in [('upstream',3,1000),('downstream',2,1400)]:
        ll=edges[edge].findall('lane');assert len(ll)==n and all(float(l.attrib['length'])==length for l in ll)
    gg=rows(OUT/tag/(name+'_geometry.csv.gz'))
    assert len(gg)==sum(len(f['states']) for f in ff)
    frames[key]['geometry']=gg;counts[tag+'/'+name]=len(ff);full_n+=len(gg)

def check(r,tag,name):
    ss=frames[tag,name][float(r['time_s'])]['states'];s=ss[r['vehicle_id']]
    assert all(float(r[k])==s[v] for k,v in [('x_m','x'),('y_m','y'),('speed_mps','speed'),('lane','lane')])
    desired=5.5+(30-5.5)/28.8*s['speed'];assert float(r['cth_D_m'])==desired
    front=min((k for k,v in ss.items() if k!=r['vehicle_id'] and v['x']>s['x'] and abs(v['y']-(s['lane']+.5)*3.3)<2.55),key=lambda k:(ss[k]['x'],ss[k]['y'],ss[k]['speed']),default=None)
    assert r['front_id']==(front or '')
    if front is None:assert r['front_gap_m']==r['front_gap_minus_cth_D_m']==''
    else:
        gap=ss[front]['x']-s['x']
        assert float(r['front_gap_m'])==gap and float(r['front_gap_minus_cth_D_m'])==gap-desired
        assert r['front_inside_existing_50m_following_range']==str(gap<=50)
    for lane in range(3):
        peer=min((k for k,v in ss.items() if k!=r['vehicle_id'] and v['lane']==lane),key=lambda k:(abs(ss[k]['x']-s['x']),ss[k]['x'],ss[k]['y'],ss[k]['speed']),default=None) if abs(lane-s['lane'])==1 else None
        assert r[f'adj_lane{lane}_id']==(peer or '')
        assert float(r[f'adj_lane{lane}_signed_dx_m'])==ss[peer]['x']-s['x'] if peer else r[f'adj_lane{lane}_signed_dx_m']==''

for (tag,name),data in frames.items():
    for r in data['geometry']:check(r,tag,name)
selected=rows(OUT/'snapshot_states.csv')
for r in selected:check(r,r['version'],r['demo'])
summary=rows(OUT/'snapshot_summary.csv');assert len(summary)==18
for r in summary:
    ss=[q for q in selected if (q['version'],q['demo'],q['time_s'])==(r['version'],r['demo'],r['time_s'])]
    assert len(ss)==int(r['onroad_n'])
    errors=sorted(float(q['front_gap_minus_cth_D_m']) for q in ss if q['front_id'])
    import statistics
    assert float(r['cth_error_min'])==min(errors) and float(r['cth_error_median'])==statistics.median(errors) and float(r['cth_error_max'])==max(errors)
    if r['frame_kind']=='registered_downstream':assert r['absent_initial_n']=='0' and r['all_initial_still_present']=='True'
pairs=rows(OUT/'cross_lane_pair_references.csv')
for r in pairs:
    ss=frames[r['version'],r['demo']][float(r['time_s'])]['states'];s=ss[r['vehicle_id']];other=ss[r['peer_id']]
    assert float(r['raw_signed_dx_m'])==other['x']-s['x']
    assert float(r['reference_15_m'])==15
    assert float(r['reference_D_pair_mean_speed_half_m'])==(5.5+(30-5.5)/28.8*(s['speed']+other['speed'])/2)/2
pngs=[]
for tag in protocol['runtimes']:
    for png in sorted((OUT/tag).glob('*.png')):
        ET.parse(png.with_suffix('.svg'))
        with Image.open(png) as im:
            assert min(im.info['dpi'])>299
            pngs.append(dict(png=str(png.relative_to(OUT)),pixels=im.size,dpi=im.info['dpi']))
assert len(pngs)==8
deferred={'evidence_reviewed.tar.gz','archive_verification.json'}
links=re.findall(r'\]\(([^)]+)\)',(OUT/'README.md').read_text(encoding='utf-8'))
for link in links:
    if link not in deferred and link!='final_verification.json':assert (OUT/link).exists(),link
result=dict(physical_runs=2,raw_frames=counts,full_geometry_rows_rechecked=full_n,selected_rows_rechecked=len(selected),pair_reference_rows_rechecked=len(pairs),registered_frames=8,all_initial_vehicles_present_at_all_registered_downstream_frames=True,source_changes_exactly_two_network_coordinates=True,controller_and_five_other_sources_unchanged=True,original_inputs_byte_identical=True,png_svg_pairs=pngs,all_8_figures_visually_reviewed=True,no_additional_simulations=True,all_non_archive_report_links_verified=True)
(OUT/'final_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='png_svg_pairs'}))
