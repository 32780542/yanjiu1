"""Same-input J2/L geometry and finite-view bridge event audit, no simulation."""
import ast
from bisect import bisect_left,bisect_right
import csv
import difflib
import gzip
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

OUT=Path(__file__).resolve().parent;OLD=OUT.parent/'formation_demo_long'
p=json.loads((OUT/'protocol.json').read_text());runtime=Path(p['runtimes']['LT2400']['frozen_runtime'])
def rows(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rr):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)

comparison=[]
j2={(r['demo'],r['anchor_offset_s']):r for r in rows(OLD/'snapshot_summary.csv') if r['version']=='J22400' and r['frame_kind']=='registered_downstream'}
for r in rows(OUT/'snapshot_summary.csv'):
    if r['frame_kind']!='registered_downstream':continue
    old=j2[r['demo'],r['anchor_offset_s']]
    result=dict(demo=r['demo'],anchor_offset_s=r['anchor_offset_s'])
    for tag,data in [('J2',old),('L',r)]:
        result.update({tag+'_'+k:data[k] for k in ['time_s','initial_n','onroad_n','n_lane0','n_lane1','v_min','v_median','v_max','cth_error_min','cth_error_median','cth_error_max','all_initial_still_present']})
    comparison.append(result)
write('J2_LT_registered_comparison.csv',comparison)
Lspec=importlib.util.spec_from_file_location('frozen_LT_rules_for_audit',runtime/'noa/native_rules.py')
rule=importlib.util.module_from_spec(Lspec);sys.modules[Lspec.name]=rule;Lspec.loader.exec_module(rule)
tree=ast.parse((runtime/'experiments/native_sumo.py').read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LocalTracks')
env=dict(bisect_left=bisect_left,bisect_right=bisect_right)
exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_LocalTracks','exec'),env)
LocalTracks=env['LocalTracks']
events=[];tracked=[];frames={};runs=json.loads((OUT/'demo_results.json').read_text())
for run in runs:
    demo=run['demo'];case=Path(run['case_dir']);local=LocalTracks(rule.Vehicle)
    with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=list(map(json.loads,f))
    frames[demo]={f['time_s']:f for f in ff}
    selected=set(run['registered_downstream_times_s'])|{.1,5.,10.,15.,20.,52.8}
    for f in ff:
        states={k:SimpleNamespace(**s) for k,s in f['states'].items()}
        order=sorted(states,key=lambda k:(states[k].x,states[k].y,states[k].speed));xs=[states[k].x for k in order]
        for key in order:
            ego,neighbors=local.observe(key,states,order,xs)
            a=f['actions'][key];cf50=rule._front_following(ego,neighbors)
            ext=rule._front_following(ego,neighbors,60.)
            front=next((c for c in neighbors if c.track==ext[2]),None)
            if front is None or cf50[2] is not None:continue
            witnesses=[c for c in neighbors if abs(c.lane-ego.lane)==1 and ego.x<c.x<front.x and abs(c.x+rule._physical_phase(c,3)-rule._physical_phase(ego,3)-(front.x-30))<=2]
            if not witnesses:continue
            reverse={track:trueid for trueid,track in local.tracks[key].items()}
            assert 50<front.x-ego.x<=60
            if a['reason']=='formation_follow':assert a['reference']==ext[2] and a['target_x']==ext[1]
            for c in witnesses:
                events.append(dict(demo=demo,time_s=f['time_s'],ego_id=key,ego_lane=ego.lane,ego_x_m=ego.x,ego_speed_mps=ego.speed,
                    actual_extended_front_id=reverse[front.track],front_x_m=front.x,front_speed_mps=front.speed,front_gap_m=front.x-ego.x,
                    witness_id=reverse[c.track],witness_x_m=c.x,witness_lane=c.lane,witness_speed_mps=c.speed,
                    witness_residual_m=c.x+rule._physical_phase(c,3)-rule._physical_phase(ego,3)-(front.x-30),
                    cf50_reference=cf50[2],cf60_reference_private_track=ext[2],recorded_reason=a['reason'],recorded_reference_private_track=a['reference'],
                    recorded_reference_matches_extended_front=a['reference']==ext[2],recorded_command_speed_mps=a['speed'],recorded_requested_speed_mps=a['requested_speed'],
                    finite_observation_scope='100m behind / 200m ahead, frozen LocalTracks replay',all_initial_present=len(states)==run['initial_n']))
    if demo=='unformed24':
        geom=rows(OUT/'LT2400/unformed24_geometry.csv.gz')
        indexed={(float(r['time_s']),r['vehicle_id']):r for r in geom}
        for t in sorted(selected):
            if t not in frames[demo]:continue
            f=frames[demo][t];ego=f['states']['unformed_l2_r05'];original_front=f['states']['unformed_l2_r06'];g=indexed[t,'unformed_l2_r05']
            tracked.append(dict(time_s=t,frame_is_registered=t in run['registered_downstream_times_s'],ego_id='unformed_l2_r05',ego_lane=ego['lane'],ego_x_m=ego['x'],ego_speed_mps=ego['speed'],
                actual_front_id=g['front_id'],actual_front_gap_m=g['front_gap_m'],actual_cth_error_m=g['front_gap_minus_cth_D_m'],
                originally_named_front_id='unformed_l2_r06',original_front_lane=original_front['lane'],original_front_x_m=original_front['x'],original_front_speed_mps=original_front['speed'],
                original_named_pair_signed_dx_m=original_front['x']-ego['x'],same_original_front_still_actual=g['front_id']=='unformed_l2_r06',
                recorded_reason=f['actions']['unformed_l2_r05']['reason'],recorded_reference_private_track=f['actions']['unformed_l2_r05']['reference']))
write('all_finite_view_bridge_witness_events.csv',events)
write('original_59m_pair_actual_history.csv',tracked)
oldp=json.loads((OLD/'protocol.json').read_text())
j2source=Path(oldp['runtimes']['J22400']['frozen_runtime'])/'noa/native_rules.py'
diff=''.join(difflib.unified_diff(j2source.read_text(encoding='utf-8').splitlines(True),(runtime/'noa/native_rules.py').read_text(encoding='utf-8').splitlines(True),fromfile='frozen_J2',tofile='frozen_L'))
(OUT/'LT_vs_J2_rules.patch').write_text(diff,encoding='utf-8')
target=[r for r in events if r['ego_id']=='unformed_l2_r05' and r['demo']=='unformed24']
summary=dict(physical_runs=2,qualified_local_witness_event_rows=len(events),event_rows_by_demo={d:sum(r['demo']==d for r in events) for d in frames},
    event_vehicle_counts={d:len({r['ego_id'] for r in events if r['demo']==d}) for d in frames},
    original_ego_bridge_event_rows=len(target),first_original_ego_witness_event=target[0] if target else None,last_original_ego_witness_event=target[-1] if target else None,
    exact_finite_LocalTracks_class_reused=True,all_formation_follow_event_references_match_qualified_extended_front=True,no_new_simulation=True)
(OUT/'bridge_audit.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary))
