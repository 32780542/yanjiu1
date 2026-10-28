"""Phase 3 small multi-vehicle sensing benches. All attempts remain on disk."""
from dataclasses import asdict
import json
import math
import re
from pathlib import Path
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from experiments.records import RunRecord, atomic_json
from experiments.phase3_cases import cases
from experiments.phase3_audit import geometry_report, isolation_audit, compare_records
from models.vehicle import VehicleState, Actuation
from models.kinematic import KinematicModel as VehicleModel
from models.geometry import to_sumo_pose
from perception.road import VisibleRoad
from research.common import (ROOT, output_path, settings, read_json, sha256,
                             code_manifest, binary, lock_traci, write_xml, command)
from safety.geometry import RoadEnvelope
from simulation.multi_vehicle import MultiVehicleClock, FleetBridge

NET = ROOT/'scenarios/cai2024/bottleneck.net.xml'
PHASE2_RUN = ROOT/'results/phase2/runs/20260910T124949249161Z_77673fca'


def bootstrap(path, initial, model, p, stdout):
    routes = ET.Element('routes')
    ET.SubElement(routes,'vType',id='external_probe',length=str(model.p['length_m']),width=str(model.p['width_m']),
                  maxSpeed=str(model.p['max_speed_mps']),accel='5',decel='10',emergencyDecel='10',speedFactor='1',speedDev='0')
    ET.SubElement(routes,'route',id='r',edges='upstream downstream')
    write_xml(path/'routes.rou.xml',routes)
    cmd = [binary('sumo'),'-n',str(NET),'-r',str(path/'routes.rou.xml'),'--step-length',str(p['control_sync_dt_s']),
           '--seed',str(p['phase3_seed']),'--no-step-log','true','--time-to-teleport','-1','--collision.action','warn',
           '--log',str(path/'sumo.log')]
    atomic_json(path/'command.json',{'command':cmd,'cwd':str(ROOT),'seed':p['phase3_seed']})
    label = 'phase3_'+path.parent.parent.name+'_'+path.parent.name+'_'+path.name
    conn = None
    progress = {'status':'running','initial_readbacks':{},'completed_initialization_steps':0,'phase':'load_traci'}
    atomic_json(path/'bootstrap.json',progress)
    try:
        traci = lock_traci()
        progress['phase'] = 'start_sumo'
        traci.start(cmd,label=label,stdout=stdout)
        conn = traci.getConnection(label)
        progress.update(phase='insert_vehicles',sumo_version=conn.getVersion())
        # Safe staging positions only during excluded initialization; no
        # traffic algorithm or physical-time entrance schedule is inferred.
        for i,key in enumerate(sorted(initial)):
            conn.vehicle.add(key,'r',typeID='external_probe',departLane=str(i%3),departPos=str(20+20*i),departSpeed='0')
        conn.simulationStep()
        progress.update(phase='install_initial_states',completed_initialization_steps=1)
        if set(conn.vehicle.getIDList()) != set(initial):
            raise RuntimeError('Not all prescribed vehicles inserted during bootstrap')
        for key,s in sorted(initial.items()):
            conn.vehicle.setSpeedMode(key,model.p['sumo_speed_mode'])
            conn.vehicle.setLaneChangeMode(key,model.p['sumo_lane_change_mode'])
            x,y,angle = to_sumo_pose(s,model.p['length_m'])
            conn.vehicle.setSpeed(key,model.observe(s)['speed_mps'])
            conn.vehicle.moveToXY(key,'',-1,x,y,angle=angle,keepRoute=model.p['sumo_move_keep_route'])
        conn.simulationStep()
        progress.update(phase='initial_readback',completed_initialization_steps=2,sumo_time_s=conn.simulation.getTime())
        bridge = FleetBridge(conn,initial,model,p['control_sync_dt_s'])
        atomic_json(path/'bootstrap.json',{'status':'completed','sumo_version':conn.getVersion(),'initial_readbacks':bridge.initial_reports,
                    'excluded_initialization_steps':2,'time_offset_s':bridge.time_offset,
                    'purpose':'Install prescribed small-case CG states before physical t=0'})
        return conn,bridge
    except BaseException as exc:
        progress.update(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc(),
                        initial_readbacks=getattr(exc,'fleet_initial_reports',{}))
        atomic_json(path/'bootstrap.json',progress)
        if conn is not None:
            conn.close()
        raise


def run_case(path,model,p,case,live=True):
    path = output_path(path)
    path.mkdir(parents=True,exist_ok=False)
    atomic_json(path/'validation.json',{'passed':False,'status':'running'})
    conn,bridge,clock = None,None,None
    records = []
    try:
        road = VisibleRoad.from_net(NET)
        initial = {k:VehicleState(**s) for k,s in case['initial'].items()}
        intervals = round(case['duration_s']/p['control_sync_dt_s'])
        if intervals < 1 or not math.isclose(intervals*p['control_sync_dt_s'],case['duration_s'],abs_tol=1e-9,rel_tol=0):
            raise ValueError('Case duration must contain complete sampling intervals')
        meta = {'case':case,'parameters':dict(p),'model_parameters':dict(model.p),'initial':case['initial'],
                'road':asdict(road),'intervals':intervals,'live':live,'sumo_time_offset_s':None,
                'controller':'perception.probe.probe_action; pure local test strategy, not NOA'}
        atomic_json(path/'metadata.json',meta)
        clock = MultiVehicleClock(initial,model,road,p)
        with (path/'stdout.log').open('w',encoding='utf-8') as stdout,(path/'trace.jsonl').open('w',encoding='utf-8') as trace:
            if live:
                conn,bridge = bootstrap(path,initial,model,p,stdout)
                meta['sumo_time_offset_s'] = bridge.time_offset
                meta['sumo_version'] = conn.getVersion()
                atomic_json(path/'metadata.json',meta)
            for _ in range(intervals):
                try:
                    record = clock.tick(bridge=bridge)
                except BaseException:
                    trace.write(json.dumps(clock.last_record,allow_nan=False)+'\n')
                    trace.flush()
                    raise
                trace.write(json.dumps(record,allow_nan=False)+'\n')
                trace.flush()
                records.append(record)
        geometry = geometry_report(records,model,RoadEnvelope.from_net(NET))
        isolation = isolation_audit(records,model,p,road,path/'isolation.jsonl')
        from experiments.phase3_replay import replay_case
        replay = replay_case(meta,path/'trace.jsonl')
        readings = [v for r in records for v in (r['readback'] or {}).values()]
        result = {'passed':geometry['passed'] and isolation['passed'] and replay['passed'],'status':'completed',
                  'intervals':len(records),'vehicle_intervals':len(records)*len(initial),'geometry':geometry,
                  'isolation':isolation,'replay':replay,'physical_sumo_advances':bridge.advances if bridge else 0,
                  'sumo_version':conn.getVersion() if conn else None,
                  'max_position_readback_error_m':max((r['position_error_m'] for r in readings),default=0.),
                  'max_time_readback_error_s':max((r['time_error_s'] for r in readings),default=0.),
                  'max_heading_readback_error_rad':max((r['heading_error_rad'] for r in readings),default=0.),
                  'max_speed_readback_error_mps':max((r['speed_error_mps'] for r in readings),default=0.),
                  'max_acceleration_readback_error_mps2':max((r['interval_acceleration_error_mps2'] for r in readings),default=0.),
                  'edge_ids':sorted({r['edge_id'] for r in readings}),
                  'ego_a_neighbor_counts':[len(r['inputs']['a']['observation']['neighbors']) for r in records]}
    except BaseException as exc:
        result = {'passed':False,'status':'failed','error':f'{type(exc).__name__}: {exc}',
                  'traceback':traceback.format_exc(),'completed_intervals':len(records)}
        # Preserve partial evidence even for close/interrupt/dependency failures.
        atomic_json(path/'validation.json',result)
        if not isinstance(exc,Exception):
            raise
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:
                result.update(passed=False,status='failed',close_error=f'{type(exc).__name__}: {exc}')
    if live and (path/'sumo.log').is_file():
        warnings = [line for line in (path/'sumo.log').read_text(encoding='utf-8',errors='replace').splitlines()
                    if 'Warning:' in line or 'Error:' in line]
        initialization,other = [],[]
        offset = meta.get('sumo_time_offset_s') if 'meta' in locals() else None
        for line in warnings:
            time = re.search(r'time=([0-9.]+)',line)
            # SUMO's warning timestamp denotes start of the native interval.
            is_initial = (offset is not None and time is not None and float(time[1].rstrip('.')) < offset-1e-9
                          and 'moved by TraCI' in line and 'Warning:' in line)
            (initialization if is_initial else other).append(line)
        result['sumo_warnings'] = {'initialization_only':initialization,'physical_or_unclassified':other}
        if other:
            result['passed'] = False
    atomic_json(path/'validation.json',result)
    return result


def integration_refinement(path,records,model,p):
    """Numerical integration check under identical saved commands, no controller."""
    from experiments.phase2 import save_trace
    from experiments.phase3_replay import replay_motion_trace
    from experiments.offline import compare_trajectories
    from models.vehicle import IntegratedStep
    results, directories = [],[]
    for key in records[0]['initial']:
        original,refined = [],[]
        current = VehicleState(**records[0]['initial'][key])
        for r in records:
            stored = r['steps'][key]
            original.append(IntegratedStep(VehicleState(**stored['initial']),VehicleState(**stored['final']),
                Actuation(**stored['command']),tuple(VehicleState(**s) for s in stored['samples']),stored['dt_s']))
            step = model.advance(current,Actuation(**r['actions'][key]),p['control_sync_dt_s'],p['dynamics_dt_s']/2)
            refined.append(step)
            current = step.final
        sub = path/key
        sub.mkdir(parents=True)
        meta = {'parameters':dict(model.p),'initial':asdict(refined[0].initial),'dynamics_dt_s':p['dynamics_dt_s']/2,
                'control_dt_s':p['control_sync_dt_s'],'intervals':len(refined),'purpose':'Same commands; numerical refinement only'}
        atomic_json(sub/'metadata.json',meta)
        save_trace(sub/'trace.jsonl',model,refined)
        compare = compare_trajectories(original,refined)
        replay = replay_motion_trace(meta,sub/'trace.jsonl')
        result = {'vehicle':key,**compare,'replay':replay,'passed':replay['passed']
                   and compare['max_position_error_m']<=model.p['integration_position_tolerance_m']
                   and compare['max_heading_error_rad']<=model.p['integration_heading_tolerance_rad']}
        atomic_json(sub/'validation.json',result)
        results.append(result)
        directories.append(sub)
    return {'passed':all(r['passed'] for r in results),'vehicles':results},directories


def run_phase3(base=None):
    with RunRecord(base or ROOT/'results/phase3/runs',{'purpose':'Phase 3 attempt; prerequisites pending',
                   'command_line':sys.argv,'python':sys.version,'cwd':str(ROOT)}) as run:
        manifest = code_manifest()
        meta = {'run_id':run.run_id,'python':sys.version,'command_line':sys.argv,'initialization':'configuration_pending',
                'code_and_config_hashes':manifest,'case_trace_directories':[],'integration_trace_directories':[],
                'phase2_frozen_run_id':PHASE2_RUN.name,
                'scope':'Finite ideal sensing and synchronized independent probes; no NOA, formation, traffic or energy benefit claim'}
        atomic_json(run.path/'metadata.json',meta)
        for relative in manifest:
            target = run.path/'source_snapshot'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/relative,target)
        model = VehicleModel.from_config()
        p = {**dict(model.p),**settings('phase3')}
        meta.update(parameters=p,seed=p['phase3_seed'],initialization='configured')
        atomic_json(run.path/'metadata.json',meta)
        # Fresh clean subprocesses avoid TraCI import-path contamination.
        python = read_json('configs/tools.json')['python']
        command([python,'-I','-B','-S','run.py','verify'],run.path/'verify.json')
        command([python,'-I','-B','-S','run.py','phase2-replay','--run-dir',str(PHASE2_RUN)],run.path/'phase2_replay.json')
        original = read_json(PHASE2_RUN/'validation.json')
        if not original['passed']:
            raise RuntimeError('Frozen phase2 scientific gate did not pass')
        for relative in ('scenarios/cai2024/bottleneck.net.xml','docs/parameter_registry.csv',
                         'docs/noa_staggered_formation_research_plan_2026-09-10.md','docs/phase2_acceptance.md',
                         'results/phase0/source_hash_check.json','results/phase1/foundation_verification.json'):
            target = run.path/'input_snapshot'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/relative,target)
        atomic_json(run.path/'preconditions.json',{'phase2_gate_passed':original['passed'],
            'foundation':read_json('results/phase1/foundation_verification.json'),
            'source_hashes_matched':read_json('results/phase0/source_hash_check.json')['all_matched'],
            'phase2_replay':'phase2_replay.json; changes in stage3 files expected, frozen evidence remains unchanged'})
        results = []
        for case in cases(p):
            entry = {'name':case['name'],'variants':{}}
            records_by_variant = {}
            for name,params in (('base',p),('sampling_half',{**p,'control_sync_dt_s':p['control_sync_dt_s']/2,
                                                          'perception_dt_s':p['perception_dt_s']/2})):
                sub = run.path/case['name']/name
                result = run_case(sub,model,params,case)
                entry['variants'][name] = result
                meta['case_trace_directories'].append(sub.relative_to(run.path).as_posix())
                if result['status'] == 'completed':
                    records_by_variant[name] = [json.loads(line) for line in (sub/'trace.jsonl').read_text().splitlines()]
            if 'base' in records_by_variant:
                refinement,dirs = integration_refinement(run.path/case['name']/'integration_half',records_by_variant['base'],model,p)
                entry['integration_half'] = refinement
                meta['integration_trace_directories'].extend(d.relative_to(run.path).as_posix() for d in dirs)
            if len(records_by_variant) == 2:
                compare = compare_records(records_by_variant['base'],records_by_variant['sampling_half'])
                compare['passed'] = (compare['max_position_error_m']<=model.p['control_position_tolerance_m']
                                     and compare['max_heading_error_rad']<=model.p['control_heading_tolerance_rad'])
                entry['sampling_half_comparison'] = compare
            entry['passed'] = (all(r['passed'] for r in entry['variants'].values())
                               and entry.get('integration_half',{}).get('passed',False)
                               and entry.get('sampling_half_comparison',{}).get('passed',False))
            if case['name'] == 'cross_edge':
                entry['passed'] = entry['passed'] and all(v.get('edge_ids') == ['downstream','upstream'] for v in entry['variants'].values())
            if case['name'] == 'range_entry':
                entry['passed'] = entry['passed'] and all(v.get('ego_a_neighbor_counts',[None])[0] == 0
                                  and max(v.get('ego_a_neighbor_counts',[0])) == 2 for v in entry['variants'].values())
            atomic_json(run.path/case['name']/'validation.json',entry)
            atomic_json(run.path/'metadata.json',meta)
            results.append(entry)
            print(json.dumps({'case':case['name'],'passed':entry['passed']}),flush=True)
        sensitive = sum(v.get('isolation',{}).get('visible_neighbor_removal_changes_action',0)
                        for c in results for v in c['variants'].values())
        from experiments.phase3_faults import run_faults
        fault_source = run.path/'local_following/base'
        faults = run_faults(run.path/'faults',model,p,fault_source) if results[0]['variants']['base']['status']=='completed' else {'passed':False,'error':'No complete normal source for deliberate faults'}
        from experiments.kinematic_bench import run_bench
        motion,dirs = run_bench(run.path/'bezier_motion',model)
        meta['motion_trace_directories'] = [d.relative_to(run.path).as_posix() for d in dirs]
        atomic_json(run.path/'metadata.json',meta)
        result = {'passed':all(c['passed'] for c in results) and sensitive>0 and faults['passed'] and motion['passed'],
                  'cases':results,'faults':faults,'simplified_motion':motion,
                  'nonvacuous_action_changes':sensitive,'noa_implemented':False,'traffic_benefits_evaluated':False,
                  'next_stage_allowed':'phase4_NOA_small_case_development' if all(c['passed'] for c in results) and sensitive>0 and faults['passed'] and motion['passed'] else None}
        run.finish(result)
        hashes = {f.relative_to(run.path).as_posix():sha256(f) for f in run.path.rglob('*') if f.is_file()}
        atomic_json(run.path/'evidence_hashes.json',hashes)
    print(json.dumps({'run_id':run.run_id,'passed':result['passed'],'path':str(run.path)}),flush=True)
    if not result['passed']:
        raise RuntimeError(f'Phase3 gate failed; full results retained at {run.path}')
    return run.path
