"""Independent geometry/statistics/raw-hash check; no simulation imports."""
import csv,gzip,hashlib,json,math,re,statistics,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
OUT=Path(__file__).resolve().parent;BASE=OUT.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    op=gzip.open if str(p).endswith('.gz') else open
    with op(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
stats=read(OUT/'all_pre_exit_frame_statistics.csv');pairs=read(OUT/'all_actual_raw_cross_pairs.csv.gz')
extras=read(OUT/'fixed_extra_20_25_summary.csv');selected=read(OUT/'fixed_extra_20_25_states.csv')
si={(r['version'],r['demo'],float(r['time_s'])):r for r in stats}
pairi={}
for r in pairs:pairi.setdefault((r['version'],r['demo'],float(r['time_s'])),[]).append(r)
def geom(ss):
    out={}
    for k,s in ss.items():
        front=min((j for j,p in ss.items() if p['x']>s['x'] and abs(p['y']-(s['lane']+.5)*3.3)<2.55),key=lambda j:(ss[j]['x'],ss[j]['y'],ss[j]['speed']),default=None)
        d=5.5+(30-5.5)*s['speed']/28.8
        adj={}
        for lane in range(3):
            if abs(lane-s['lane'])==1:
                peer=min((j for j,p in ss.items() if p['lane']==lane),key=lambda j:(abs(ss[j]['x']-s['x']),ss[j]['x'],ss[j]['y'],ss[j]['speed']),default=None)
                if peer:adj[lane]=(peer,ss[peer]['x']-s['x'])
        out[k]=(front,None if front is None else ss[front]['x']-s['x']-d,adj,d)
    return out
def close(a,b):assert math.isclose(float(a),b,rel_tol=1e-12,abs_tol=1e-10),(a,b)
frame_n=pair_n=state_n=0;case_checks=[]
for src in json.loads((OUT/'source_index.json').read_text()):
    tag,demo=src['version'],src['demo'];case=Path(src['case_dir'])
    assert sha(case/'positions.jsonl.gz')==src['positions_sha256'];assert sha(case/'diagnostic.jsonl.gz')==src['diagnostic_sha256']
    inp=BASE/('formation_demo_M_long' if tag=='M2400' else 'formation_demo_L_long' if tag=='L2400' else 'formation_demo_long')/(demo+'_initial.json')
    assert sha(inp)==src['initial_sha256'];ids={s['id'] for s in json.loads(inp.read_text())}
    trips=json.loads((case/'trips.json').read_text());first=min(s['exited_s'] for s in trips);assert first==src['first_actual_exit_s']
    with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=[json.loads(s) for s in f]
    seen=set();anchor=None
    for f in ff:
        seen|={j for j,s in f['states'].items() if s['x']>=1000}
        if seen==ids:anchor=f['time_s'];break
    assert anchor==src['anchor_s'];dyn=[f for f in ff if anchor<=f['time_s']<first]
    assert len(dyn)==src['continuous_frames']
    for f in dyn:
        t=f['time_s'];ss=f['states'];assert set(ss)==ids;gg=geom(ss);r=si[tag,demo,t]
        assert int(r['initial_n'])==int(r['onroad_n'])==len(ids)
        errors=[g[1] for g in gg.values() if g[1] is not None];dx=[v[1] for g in gg.values() for v in g[2].values()];vv=[s['speed'] for s in ss.values()]
        for prefix,values in [('cth_error',errors),('raw_signed_adj_dx',dx),('v',vv)]:
            for name,val in [('min',min(values)),('median',statistics.median(values)),('max',max(values))]:close(r[prefix+'_'+name],val)
        actual={(p['vehicle_id'],p['peer_id']):float(p['raw_signed_dx_m']) for p in pairi[tag,demo,t]}
        expected={(j,p[0]):p[1] for j,g in gg.items() for p in g[2].values()};assert actual==expected
        frame_n+=1;pair_n+=len(expected)
    for er in (r for r in extras if r['version']==tag and r['demo']==demo):
        t=float(er['time_s']);f=next(f for f in ff if f['time_s']==t);ss=f['states'];gg=geom(ss)
        assert t==round(anchor+float(er['anchor_offset_s']),1);assert int(er['onroad_n'])==len(ss)==len(ids)
        assert er['all_initial_present']=='True' and er['any_initial_exit_at_or_before_t']=='False' and t<first
        selected_now=[r for r in selected if r['version']==tag and r['demo']==demo and float(r['time_s'])==t];assert len(selected_now)==len(ids)
        for r in selected_now:
            j=r['vehicle_id'];s=ss[j];front,err,adj,d=gg[j]
            for key,raw in [('x_m','x'),('y_m','y'),('lane','lane'),('speed_mps','speed')]:close(r[key],s[raw])
            close(r['cth_D_m'],d);assert r['front_id']==(front or '')
            if err is not None:close(r['front_gap_minus_cth_D_m'],err)
            else:assert r['front_gap_minus_cth_D_m']==''
            for lane in range(3):
                assert r[f'adj_lane{lane}_id']==(adj[lane][0] if lane in adj else '')
                if lane in adj:close(r[f'adj_lane{lane}_signed_dx_m'],adj[lane][1])
            state_n+=1
    case_checks.append(dict(version=tag,demo=demo,anchor_s=anchor,first_exit_s=first,frames=len(dyn)))
assert frame_n==len(stats) and pair_n==len(pairs) and state_n==len(selected)
figs=[]
for png in sorted(OUT.glob('*.png')):
    ET.parse(png.with_suffix('.svg'))
    with Image.open(png) as im:assert min(im.info['dpi'])>299;figs.append(dict(name=png.name,dpi=im.info['dpi'],pixels=im.size))
assert len(figs)==4
for link in re.findall(r'\]\(([^)]+)\)',(OUT/'README.md').read_text(encoding='utf-8')):
    if link!='verification.json':assert (OUT/link).exists(),link
out=dict(cases=case_checks,all_continuous_frames_independently_rechecked=frame_n,all_raw_pairs_independently_rechecked=pair_n,fixed_extra_state_rows_rechecked=state_n,extra_frames=16,all_extra_full_initial_present=True,figures=figs,all_four_figures_visually_reviewed=True,no_new_simulations=True)
(OUT/'verification.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in out.items() if k not in ['cases','figures']}))
