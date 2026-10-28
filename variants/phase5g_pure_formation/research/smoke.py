"""Instrumented native SUMO road test. This is NOT a NOA implementation."""
import csv
import json
import math
import sys
import shutil
import traceback
import uuid
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from research.common import ROOT, settings, binary, lock_traci, write_json, sha256, code_manifest, output_path
from research.demand import write_csv
from research.network import SCENARIO, validate_tree


def run_smoke():
    out=output_path(ROOT/'results/phase1/smoke')
    out.mkdir(parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]
    result_path=out/'validation.json'
    prior=result_path.read_text(encoding='utf-8') if result_path.exists() else None
    had_output=any(out.iterdir())
    # Invalidate old success before any launch, copy, parsing or tool call.
    write_json(result_path,{'passed':False,'status':'running','end_reason':'not_completed','run_id':run_id})
    try:
        if had_output:
            archive=output_path(ROOT/'results/phase1/smoke_history'/run_id)
            shutil.copytree(out,archive)
            if prior is not None:
                (archive/'validation.json').write_text(prior,encoding='utf-8')
        _run_native_smoke(run_id)
        result=json.loads(result_path.read_text(encoding='utf-8'))
        write_json(result_path,{**result,'status':'completed','run_id':run_id})
    except BaseException as exc:
        partial=json.loads(result_path.read_text(encoding='utf-8'))
        write_json(result_path,{**partial,'passed':False,'status':'failed','end_reason':'exception','run_id':run_id,
                   'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc(),
                   'purpose':'native topology smoke only; partial diagnostics retained'})
        raise


def _run_native_smoke(run_id):
    network=validate_tree(ET.parse(SCENARIO/'bottleneck.net.xml').getroot())
    if not network['passed']:
        raise RuntimeError('Topology gate not passed')
    traci=lock_traci()
    cfg=settings('topology_smoke')
    out=ROOT/'results/phase1/smoke'
    out.mkdir(parents=True,exist_ok=True)
    route_xml=ET.parse(SCENARIO/'smoke.rou.xml').getroot()
    plans={v.get('id'):{'vehicle_id':v.get('id'),'planned_depart_s':float(v.get('depart')),
            'planned_depart_lane':int(v.get('departLane')),'actual_depart_s':None,'actual_depart_lane':None,
            'arrival_s':None,'arrival_notification_time_s':None,'upstream_merge_seen':False,'status':'not_departed'} for v in route_xml.findall('vehicle')}
    fields=['time_s','vehicle_id','edge','lane','x_m','y_m','speed_mps','acceleration_mps2','angle_deg']
    violations=[]
    transitions=[]
    conservation=[]
    last={}
    departed_ids,arrived_ids=set(),set()
    collisions,teleports,merge_count=0,0,0
    max_lateral_step=0.
    end_reason='timeout'
    cmd=[binary('sumo'),'-c',str(SCENARIO/'smoke.sumocfg')]
    write_json(out/'run_metadata.json',{'run_id':run_id,'purpose':'native topology smoke only','command':cmd,'cwd':str(ROOT),
               'seed':cfg['seed'],'code_and_config_hashes':code_manifest(),
               'net_sha256':sha256(SCENARIO/'bottleneck.net.xml'),'route_sha256':sha256(SCENARIO/'smoke.rou.xml'),
               'sumocfg_sha256':sha256(SCENARIO/'smoke.sumocfg'),'batch_experiments':False,
               'dynamics_source':'SUMO native IDM/LC2013; not an external bicycle integrator; no NOA controller'})
    with (out/'state_trace.csv').open('w',newline='',encoding='utf-8') as trace, (out/'stdout.log').open('w',encoding='utf-8') as log:
        w=csv.DictWriter(trace,fieldnames=fields)
        w.writeheader()
        conn=None
        try:
            traci.start(cmd,label='topology-smoke',stdout=log)
            conn=traci.getConnection('topology-smoke')
            version=conn.getVersion()
            dt=conn.simulation.getDeltaT()
            if abs(dt-cfg['sumo_dt_s'])>1e-12:
                raise RuntimeError('Unexpected getDeltaT units/value')
            while conn.simulation.getTime()<cfg['smoke_end_s']:
                conn.simulationStep()
                t=conn.simulation.getTime()
                departed=conn.simulation.getDepartedIDList()
                arrived=conn.simulation.getArrivedIDList()
                for vid in departed:
                    departed_ids.add(vid)
                    plans[vid]['actual_depart_s']=conn.vehicle.getDeparture(vid)
                    plans[vid]['actual_depart_lane']=conn.vehicle.getLaneIndex(vid)
                    plans[vid]['status']='running'
                    if plans[vid]['actual_depart_lane']!=plans[vid]['planned_depart_lane']:
                        violations.append(f'{vid}: silently moved to other entry lane')
                for vid in arrived:
                    arrived_ids.add(vid)
                    plans[vid]['arrival_notification_time_s']=t
                    plans[vid]['status']='arrived'
                collisions+=conn.simulation.getCollidingVehiclesNumber()
                teleports+=conn.simulation.getStartingTeleportNumber()
                current=conn.vehicle.getIDList()  # evaluator-only truth access; no controllers in this test
                pending=len(plans)-len(departed_ids)
                conserved=len(plans)==pending+len(current)+len(arrived_ids)
                if not conserved:
                    violations.append(f'Conservation failed at {t}')
                conservation.append(dict(time_s=t,planned=len(plans),departed=len(departed_ids),arrived=len(arrived_ids),
                                         running=len(current),not_yet_departed=pending,conserved=conserved))
                for vid in current:
                    x,y=conn.vehicle.getPosition(vid)
                    state={'time_s':t,'vehicle_id':vid,'edge':conn.vehicle.getRoadID(vid),'lane':conn.vehicle.getLaneIndex(vid),
                           'x_m':x,'y_m':y,'speed_mps':conn.vehicle.getSpeed(vid),
                           'acceleration_mps2':conn.vehicle.getAcceleration(vid),'angle_deg':conn.vehicle.getAngle(vid)}
                    if vid in last:
                        prev=last[vid]
                        dy=abs(y-prev['y_m'])
                        max_lateral_step=max(max_lateral_step,dy)
                        if dy>cfg['max_lateral_step_m']+1e-9:
                            violations.append(f'{vid}: lateral jump {dy} m at {t}')
                        if x<prev['x_m']-1e-6 or x-prev['x_m']>33.3*dt+.02:
                            violations.append(f'{vid}: invalid longitudinal displacement at {t}')
                        if state['edge']=='upstream' and prev['lane']==2 and state['lane']==1:
                            plans[vid]['upstream_merge_seen']=True
                            merge_count+=1
                        if prev['edge']=='upstream' and state['edge']=='downstream':
                            pair=(prev['lane'],state['lane'])
                            transitions.append({'vehicle_id':vid,'time_s':t,'from_lane':prev['lane'],'to_lane':state['lane'],
                                                'x_before_m':prev['x_m'],'x_after_m':x,'lateral_step_m':dy})
                            if pair not in ((0,0),(1,1)):
                                violations.append(f'{vid}: illegal cross-edge transition {pair}')
                            if plans[vid]['planned_depart_lane']==2 and not plans[vid]['upstream_merge_seen']:
                                violations.append(f'{vid}: terminated lane bypassed upstream merging')
                    w.writerow(state)
                    last[vid]=state
                if conn.simulation.getMinExpectedNumber()==0:
                    end_reason='demand_drained'
                    break
            end_time=conn.simulation.getTime()
        finally:
            if conn is not None:
                conn.close()
    # tripinfo provides authoritative SUMO departure/arrival times, including insertion delay.
    trips={r.get('id'):r for r in ET.parse(out/'tripinfo.xml').getroot().findall('tripinfo')}
    departures=[]
    for vid,p in plans.items():
        row=dict(p)
        row['entry_wait_s']=None if p['actual_depart_s'] is None else p['actual_depart_s']-p['planned_depart_s']
        row['is_topology_probe']=vid=='termination_probe'
        if vid in trips:
            trip=trips[vid]
            row['tripinfo_depart_s']=float(trip.get('depart'))
            row['tripinfo_arrival_s']=float(trip.get('arrival'))
            row['tripinfo_depart_delay_s']=float(trip.get('departDelay'))
            row['arrival_s']=row['tripinfo_arrival_s'] if row['tripinfo_arrival_s']>=0 else None
            if row['arrival_s'] is not None:
                lag=row['arrival_notification_time_s']-row['arrival_s']
                if not -1e-9<=lag<=dt+1e-9:
                    violations.append(f'{vid}: arrival notification exceeds one simulation step')
            if abs(row['tripinfo_depart_s']-row['actual_depart_s'])>1e-6 or abs(row['entry_wait_s']-row['tripinfo_depart_delay_s'])>1e-6:
                violations.append(f'{vid}: departure/wait mismatch with tripinfo')
        departures.append(row)
    write_csv(out/'departures.csv',departures,list(departures[0]))
    write_csv(out/'transitions.csv',transitions,list(transitions[0]) if transitions else ['vehicle_id'])
    write_csv(out/'conservation.csv',conservation,list(conservation[0]))
    if len(transitions)!=len(plans):
        violations.append('Not every planned vehicle crossed the bottleneck')
    if collisions or teleports:
        violations.append(f'Colliding-vehicle reports={collisions}; teleport-starts={teleports}')
    if end_reason!='demand_drained':
        violations.append('Failed to drain before timeout')
    if not plans['termination_probe']['upstream_merge_seen']:
        violations.append('Explicit terminated-lane probe never merged')
    regular=[x for x in departures if not x['is_topology_probe']]
    result={'passed':not violations,'errors':violations,'purpose':'native road test, not NOA dynamics/safety/efficiency validation',
            'sumo_version':version,'getDeltaT_s':dt,'end_time_s':end_time,'end_reason':end_reason,
            'planned_demand_vehicles':len(regular),'additional_topology_probes':1,
            'departed_including_probe':len(departed_ids),'arrived_including_probe':len(arrived_ids),
            'uninserted':len(plans)-len(departed_ids),'unfinished':len(departed_ids)-len(arrived_ids),
            'colliding_vehicle_reports':collisions,'teleport_starts':teleports,'upstream_2_to_1_merges':merge_count,
            'edge_transitions':len(transitions),'max_lateral_step_m':max_lateral_step,
            'max_cross_edge_lateral_step_m':max((r['lateral_step_m'] for r in transitions),default=0),
            'max_entry_wait_s':max((r['entry_wait_s'] for r in regular if r['entry_wait_s'] is not None),default=0),
            'all_steps_conserved':all(x['conserved'] for x in conservation),
            'type_labels_consumed_by_controller':False,'controller_implemented':False}
    result['arrival_time_semantics']='arrival_s from SUMO tripinfo; notification time kept separately; event notification can be one dt later'
    write_json(out/'validation.json',result)
    print(json.dumps(result,ensure_ascii=True))
    if violations:
        raise RuntimeError('Smoke failed; see saved results, no batch work allowed')
