"""Read full 2400 m traces at preregistered times; reuse sealed E geometry verbatim."""
import ast
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics as st
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
BASE=OUT.parent
p=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
baseline=BASE/'formation_demo/analyze_and_plot.py'
tree=ast.parse(baseline.read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='geometry')
env={'HEADWAY':(30-5.5)/28.8}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(baseline),'exec'),env)
geometry=env['geometry']

def write(path,rr):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'wt',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)

summary=[];snapshot_summary=[];snapshot_states=[];pair_rows=[];frame_counts={}
for tag,runtime in p['runtimes'].items():
    source=Path(runtime['frozen_runtime'])
    for name,h in runtime['extended_sha256'].items():assert sha(source/name)==h
    for name,h in runtime['support_file_sha256'].items():assert sha(source/name)==h
    for demo in ['unformed24','formed45']:
        initial=json.loads((OUT/(demo+'_initial.json')).read_text());byid={r['id']:r for r in initial}
        assert sha(OUT/(demo+'_initial.json'))==p['input_sha256'][demo]
        assert (OUT/(demo+'_initial.json')).read_bytes()==(BASE/'formation_demo'/(demo+'_initial.json')).read_bytes()
        case=next((Path(p['run_base'])/tag/demo).glob('20*'))
        result=json.loads((case/'result.json').read_text())
        assert result['safe'] and result['all_completed'] and result['collisions']==result['teleports']==0
        assert result['source_sha256']==runtime['extended_sha256']
        trips=json.loads((case/'trips.json').read_text());assert all(r['entered_s']==0 for r in trips)
        with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=[json.loads(s) for s in f]
        with gzip.open(case/'positions.jsonl.gz','rt') as f:pp=[json.loads(s) for s in f]
        assert len(ff)==len(pp)
        for f,pos in zip(ff,pp):
            assert f['time_s']==pos['time_s']
            assert {k:[v['x'],v['y'],v['speed'],v['acceleration']] for k,v in f['states'].items()}==pos['states']
            assert {k:v['formation_state'] for k,v in f['actions'].items()}==pos['formation_states']
        assert set(ff[0]['states'])==set(byid)
        assert all(ff[0]['states'][k]['x']==v['x'] and ff[0]['states'][k]['speed']==v['speed'] for k,v in byid.items())
        net=ET.parse(case/'native.net.xml').getroot()
        network={e.attrib['id']:[dict(length_m=float(l.attrib['length']),shape=l.attrib['shape']) for l in e.findall('lane')] for e in net.findall('edge') if e.attrib['id'] in ['upstream','downstream']}
        assert len(network['upstream'])==3 and len(network['downstream'])==2
        assert all(l['length_m']==1000 for l in network['upstream']) and all(l['length_m']==1400 for l in network['downstream'])
        nodes=ET.parse(case/'native.nod.xml').getroot()
        assert {n.attrib['id']:float(n.attrib['x']) for n in nodes}==dict(entry=0,bottleneck=1000,exit=2400)
        seen=set();anchor=None
        for f in ff:
            seen.update(k for k,s in f['states'].items() if s['x']>=1000)
            if set(byid)<=seen:anchor=f['time_s'];break
        assert anchor is not None
        registered=[round(anchor+dt,1) for dt in p['preregistered_downstream_offsets_s']]
        selected=[ff[0]['time_s'],5.,10.,15.,20.,*registered]
        indexed={f['time_s']:f for f in ff};assert all(t in indexed for t in selected)
        first_missing=next(f['time_s'] for f in ff if set(f['states'])!=set(byid))
        first_exit=min(r['exited_s'] for r in trips)
        all_rows=[]
        for f in ff:all_rows.extend(geometry(f['time_s'],f['states'],f['actions']))
        write(OUT/tag/(demo+'_geometry.csv.gz'),all_rows)
        frame_counts[tag+'/'+demo]=len(ff)
        for t in selected:
            f=indexed[t];gg=geometry(t,f['states'],f['actions'])
            kind='registered_downstream' if t in registered else 'fixed_original'
            offset=round(t-anchor,1) if t in registered else ''
            absent=sorted(set(byid)-set(f['states']))
            errors=[q['front_gap_minus_cth_D_m'] for q in gg if q['front_id'] is not None]
            speeds=[q['speed_mps'] for q in gg]
            snapshot_summary.append(dict(version=tag,demo=demo,time_s=t,frame_kind=kind,anchor_offset_s=offset,
                initial_n=len(initial),onroad_n=len(gg),absent_initial_n=len(absent),absent_initial_ids=json.dumps(absent),
                all_initial_still_present=not absent,n_lane0=sum(q['lane']==0 for q in gg),n_lane1=sum(q['lane']==1 for q in gg),
                n_lane2=sum(q['lane']==2 for q in gg),n_with_front=len(errors),n_without_front=len(gg)-len(errors),
                v_min=min(speeds),v_median=st.median(speeds),v_max=max(speeds),
                cth_error_min=min(errors),cth_error_median=st.median(errors),cth_error_max=max(errors)))
            for q in gg:
                snapshot_states.append(dict(version=tag,demo=demo,frame_kind=kind,anchor_offset_s=offset,**q))
                for lane in range(3):
                    peer=q[f'adj_lane{lane}_id']
                    if peer is None:continue
                    peer_speed=f['states'][peer]['speed']
                    pair_rows.append(dict(version=tag,demo=demo,time_s=t,frame_kind=kind,anchor_offset_s=offset,
                        vehicle_id=q['vehicle_id'],lane=q['lane'],x_m=q['x_m'],y_m=q['y_m'],speed_mps=q['speed_mps'],
                        peer_id=peer,peer_lane=lane,peer_speed_mps=peer_speed,raw_signed_dx_m=q[f'adj_lane{lane}_signed_dx_m'],
                        reference_15_m=15.,reference_D_pair_mean_speed_half_m=(5.5+env['HEADWAY']*(q['speed_mps']+peer_speed)/2)/2))
        summary.append(dict(version=tag,demo=demo,case_dir=str(case),initial_n=len(initial),safe=result['safe'],
            all_completed=result['all_completed'],actual_end_s=result['actual_end_s'],mean_travel_time_s=result['mean_travel_time_s'],
            collisions=result['collisions'],teleports=result['teleports'],lane_change_completions=result['lane_change_completions'],
            anchor_last_first1000_s=anchor,registered_downstream_times_s=registered,first_actual_exit_s=first_exit,
            first_missing_initial_frame_s=first_missing,
            all_initial_present_at_all_registered_frames=all(set(indexed[t]['states'])==set(byid) for t in registered),
            network=network,source_sha256=result['source_sha256'],flag_participation_rate=result['formation_state']['participation_rate']))
write(OUT/'snapshot_summary.csv',snapshot_summary);write(OUT/'snapshot_states.csv',snapshot_states)
write(OUT/'cross_lane_pair_references.csv',pair_rows)
(OUT/'demo_results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
(OUT/'extraction_verification.json').write_text(json.dumps(dict(physical_runs=2,raw_frames=frame_counts,
    source_controller_unchanged=True,source_engine_only_two_coordinate_lines=True,
    native_network_xml_verified=True,E_geometry_function_code_reused_verbatim=True,
    E_plot_tool_sha256=sha(baseline),snapshot_rows=len(snapshot_states),cross_pair_rows=len(pair_rows),
    first_physical_state_exact_input=True,all_pos_diag_physical_states_and_flags_equal=True),indent=2)+'\n',encoding='utf-8')
print(json.dumps([r for r in snapshot_summary if r['frame_kind']=='registered_downstream']))
