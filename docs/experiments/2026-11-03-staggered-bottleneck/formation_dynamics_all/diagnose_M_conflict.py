"""Recompute frozen M local following only; no neighbor private Memory."""
import ast
from bisect import bisect_left,bisect_right
import csv,gzip,importlib.util,json,math,sys
from pathlib import Path
from types import SimpleNamespace
OUT=Path(__file__).resolve().parent;M=OUT.parent/'formation_demo_M_long'
p=json.loads((M/'protocol.json').read_text());runtime=Path(p['runtimes']['M2400']['frozen_runtime'])
spec=importlib.util.spec_from_file_location('frozen_M_conflict_rules',runtime/'noa/native_rules.py');rule=importlib.util.module_from_spec(spec);sys.modules[spec.name]=rule;spec.loader.exec_module(rule)
tree=ast.parse((runtime/'experiments/native_sumo.py').read_text(encoding='utf-8'));node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LocalTracks')
env=dict(bisect_left=bisect_left,bisect_right=bisect_right);exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_LocalTracks','exec'),env)
following_ast=next(n for n in ast.parse((runtime/'noa/native_rules.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='_following')
nearest_ast=next(n for n in following_ast.body if isinstance(n,ast.FunctionDef) and n.name=='nearest')
run=next(r for r in json.loads((M/'demo_results.json').read_text()) if r['demo']=='formed45');case=Path(run['case_dir'])
with (OUT/'fixed_extra_20_25_states.csv').open(encoding='utf-8-sig') as f:rr=[r for r in csv.DictReader(f) if r['version']=='M2400' and r['demo']=='formed45' and r['front_id']]
events=[]
for offset in [20,25]:
    selected=[r for r in rr if float(r['anchor_offset_s'])==offset]
    for sign,fun in [('min',min),('max',max)]:
        r=fun(selected,key=lambda r:float(r['front_gap_minus_cth_D_m']));events.append(dict(offset=offset,kind=sign,time=float(r['time_s']),ego_id=r['vehicle_id']))
ids={r['ego_id'] for r in events};times={round(r['time']+dt,1) for r in events for dt in [-1,0,1]}
local=env['LocalTracks'](rule.Vehicle);result=[]
with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=list(map(json.loads,f))
for f in ff:
    states={k:SimpleNamespace(**s) for k,s in f['states'].items()};order=sorted(states,key=lambda k:(states[k].x,states[k].y,states[k].speed));xs=[states[k].x for k in order]
    for key in ids:
        if key not in states:continue
        ego,neighbors=local.observe(key,states,order,xs)
        if f['time_s'] not in times:continue
        reverse={v:k for k,v in local.tracks[key].items()};reverse[0]=key;cars=(ego,*neighbors)
        e=dict(rule.__dict__,cars=cars,lanes=2,phase_boundary=640.)
        exec(compile(ast.Module(body=[nearest_ast],type_ignores=[]),'frozen_inner_nearest','exec'),e);nearest=e['nearest']
        cf=rule._front_following(ego,neighbors);front=next((c for c in neighbors if c.track==cf[2]),None)
        correction_error=0.;peer_data=[]
        for lane in [ego.lane-1,ego.lane+1]:
            if not 0<=lane<3:continue
            peer=nearest(ego,lane)
            if peer is None:continue
            back=nearest(peer,ego.lane);mutual=back is ego;diff,pair_lanes=rule._pair_error(ego,peer,2,640.)
            contribution=(diff+(peer.speed-ego.speed)/rule.POSITION_GAIN)/max(1,pair_lanes-1) if mutual else 0.
            correction_error+=contribution
            peer_data.append(dict(actual_phase_peer_id=reverse[peer.track],peer_lane=peer.lane,peer_x_m=peer.x,peer_speed_mps=peer.speed,
                peer_back_selection_id=reverse[back.track] if back else None,mutual=mutual,raw_signed_dx_m=peer.x-ego.x,
                q_peer_minus_q_ego_m=diff,peer_speed_minus_ego_speed_mps=peer.speed-ego.speed,
                velocity_feedback_equivalent_m=(peer.speed-ego.speed)/rule.POSITION_GAIN,local_pair_error_contribution_m=contribution))
        ps=max(-2.,min(2.,rule.POSITION_GAIN*correction_error));following=rule._following(ego,neighbors,2,640.)
        a=f['actions'][key];safe=rule.safe_speed(ego,neighbors)
        assert a['reason']=='formation_follow'
        assert math.isclose(a['requested_speed'],min(following[0],safe),abs_tol=1e-10)
        assert a['reference']==following[2]
        for pp in peer_data:
            result.append(dict(time_s=f['time_s'],ego_id=key,ego_lane=ego.lane,ego_x_m=ego.x,ego_speed_mps=ego.speed,
                actual_front_id=reverse[front.track] if front else None,actual_front_x_m=front.x if front else None,actual_front_speed_mps=front.speed if front else None,
                front_gap_m=front.x-ego.x if front else None,cth_D_m=5.5+rule.HEADWAY*ego.speed,
                actual_cth_error_m=front.x-ego.x-(5.5+rule.HEADWAY*ego.speed) if front else None,
                base_CTH_command_mps=cf[0],base_CTH_increment_mps=cf[0]-ego.speed,
                phase_error_sum_m=correction_error,phase_speed_before_clip_mps=rule.POSITION_GAIN*correction_error,
                phase_speed_after_clip_mps=ps,added_phase_command_correction_mps=rule.SPEED_RELAXATION*ps,
                phase_and_CTH_increments_opposed=(cf[0]-ego.speed)*ps<0,
                recomputed_following_command_mps=following[0],actual_recorded_command_mps=a['speed'],actual_requested_speed_mps=a['requested_speed'],
                **pp,is_prespecified_extreme_event=any(ev['ego_id']==key and ev['time']==f['time_s'] for ev in events)))
with (OUT/'M45_actual_local_phase_CTH_replay.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
selected=[r for r in result if r['is_prespecified_extreme_event']]
assert len(selected)==4
(OUT/'M45_local_replay_verification.json').write_text(json.dumps(dict(controller_sha256=p['runtimes']['M2400']['rules_sha256'],local_tracks_source_exact=True,nearest_function_ast_exact=True,no_neighbor_memory_read=True,all_recomputed_commands_match_recorded=True,rows=len(result),extreme_rows=selected),indent=2)+'\n',encoding='utf-8')
print(json.dumps(selected))
