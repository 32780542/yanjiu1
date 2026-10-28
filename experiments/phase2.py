"""Small, replayable phase-2 benches. No traffic policy or traffic benefit study."""
from dataclasses import asdict,astuple,replace
import json
import math
from pathlib import Path
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from experiments.records import RunRecord,atomic_json
from models.vehicle import VehicleModel,VehicleState,Actuation
from models.geometry import BodyPose,body_from_state,to_sumo_pose
from research.common import ROOT,output_path,read_json,sha256,code_manifest,lock_traci,binary,write_xml
from safety.geometry import RoadEnvelope,swept_outside,swept_collision,collide
from simulation.external_bridge import ExternalBridge,SynchronizationError,validate_integrated_step

BASE=ROOT/'results/phase2/runs'
NET=ROOT/'scenarios/cai2024/bottleneck.net.xml'


def save_trace(path,model,steps):
    path=output_path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8') as handle:
        for step in steps:
            record=asdict(step)
            record['diagnostics']=[model.observe(s) for s in step.samples]
            handle.write(json.dumps(record,allow_nan=False,separators=(',',':'))+'\n')


def replay_trace(metadata,path):
    errors=[]
    checked_samples=0
    max_error=0.
    try:
        model=VehicleModel(metadata['parameters'])
        current=VehicleState(**metadata['initial'])
        tolerance=model.p['replay_absolute_tolerance']
        count=0
        with output_path(path).open(encoding='utf-8') as handle:
            for count,line in enumerate(handle,1):
                record=json.loads(line)
                if VehicleState(**record['initial'])!=current:
                    raise ValueError(f'Initial state chain mismatch at interval {count}')
                if record['dt_s']!=metadata['dynamics_dt_s']:
                    raise ValueError('Trace step differs from metadata')
                step=model.advance(current,Actuation(**record['command']),metadata['control_dt_s'],record['dt_s'])
                if len(record['samples'])!=len(step.samples) or len(record['diagnostics'])!=len(step.samples):
                    raise ValueError('Missing substeps or diagnostic records')
                for sample,stored,diagnostic in zip(step.samples,record['samples'],record['diagnostics']):
                    actual=VehicleState(**stored)
                    for a,b in zip(astuple(sample),astuple(actual)):
                        if not math.isfinite(b) or abs(a-b)>tolerance:
                            raise ValueError(f'State mismatch at t={sample.time_s}')
                        max_error=max(max_error,abs(a-b))
                    expected=model.observe(sample)
                    if set(expected)!=set(diagnostic):
                        raise ValueError('Diagnostic fields differ')
                    for key,value in expected.items():
                        other=diagnostic[key]
                        if isinstance(value,bool):
                            equal=type(other) is bool and value==other
                        else:
                            equal=math.isfinite(other) and abs(value-other)<=tolerance
                        if not equal:
                            raise ValueError(f'Diagnostic {key} mismatch at t={sample.time_s}')
                    checked_samples+=1
                if VehicleState(**record['final'])!=VehicleState(**record['samples'][-1]):
                    raise ValueError('Endpoint differs from last stored substep')
                current=step.final
        if count!=metadata['intervals'] or count<1:
            raise ValueError(f'Incomplete interval count: {count} expected {metadata["intervals"]}')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed':not errors,'errors':errors,'checked_samples':checked_samples,'max_state_error':max_error}


def audit_geometry(model,steps,road):
    outside=[]
    for step in steps:
        previous=body_from_state(step.initial,model.p)
        for state in step.samples:
            body=body_from_state(state,model.p)
            if swept_outside(road,previous,body,model.p['sweep_max_depth']):
                outside.append(state.time_s)
            previous=body
    return {'passed':not outside,'outside_substeps':len(outside),'first_times_s':outside[:10],
            'scope':'Conservative sweep of linear pose interpolation per integration substep; not arbitrary continuous-time proof'}


def fault_checks(model,road):
    initial=VehicleState(x_m=100,y_m=1.65,vx_mps=20)
    good=model.advance(initial,Actuation(0,0),.1,.01)
    bad=replace(good.final,x_m=good.final.x_m+15)
    variants={'teleport':replace(good,final=bad,samples=good.samples[:-1]+(bad,)),
              'incomplete_integration':replace(good,samples=good.samples[:-1]),
              'duplicate_integration':model.advance(good.final,good.command,.1,.01)}
    reports={}
    for name,step in variants.items():
        try:
            validate_integrated_step(step,initial,.1,model)
            reports[name]={'detected':False}
        except ValueError as exc:
            reports[name]={'detected':True,'reason':str(exc)}
    a0,a1=BodyPose(100,4,0,4,1.8),BodyPose(120,4,0,4,1.8)
    b0,b1=BodyPose(110,-6,math.pi/2,4,1.8),BodyPose(110,14,math.pi/2,4,1.8)
    reports['between_endpoint_collision']={'detected':swept_collision(a0,a1,b0,b1),
        'endpoint_collisions':[collide(a0,b0),collide(a1,b1)],'poses':[asdict(x) for x in (a0,a1,b0,b1)]}
    a,b=BodyPose(500,1.65,0,4,1.8),BodyPose(500,1.65,math.pi,4,1.8)
    reports['between_endpoint_road_exit']={'detected':swept_outside(road,a,b),
        'endpoints_inside':[road.contains(a),road.contains(b)],'poses':[asdict(a),asdict(b)]}
    reports['body_crosses_lane_drop']={'detected':not road.contains(BodyPose(999,8.25,0,4,1.8))}
    return {'passed':all(x['detected'] for x in reports.values()),'faults':reports,
            'purpose':'Deliberate faults; detections count as test successes, never normal driving outcomes'}


def run_sumo(path,model,steps,sync_dt_s):
    path=output_path(path)
    path.mkdir(parents=True,exist_ok=False)
    atomic_json(path/'validation.json',{'passed':False,'status':'running'})
    try:
        return _execute_sumo(path,model,steps,sync_dt_s)
    except BaseException as exc:
        atomic_json(path/'validation.json',{'passed':False,'status':'failed',
                    'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()})
        raise


def _execute_sumo(path,model,steps,sync_dt_s):
    routes=ET.Element('routes')
    ET.SubElement(routes,'vType',id='external_bench',length=str(model.p['length_m']),width=str(model.p['width_m']),
                  maxSpeed=str(model.p['max_speed_mps']),accel='5',decel='10',emergencyDecel='10',speedFactor='1',speedDev='0')
    ET.SubElement(routes,'route',id='r',edges='upstream downstream')
    write_xml(path/'routes.rou.xml',routes)
    command=[binary('sumo'),'-n',str(NET),'-r',str(path/'routes.rou.xml'),'--step-length',str(sync_dt_s),
             '--seed','20260910','--no-step-log','true','--time-to-teleport','-1','--collision.action','warn',
             '--log',str(path/'sumo.log')]
    atomic_json(path/'command.json',{'command':command,'cwd':str(ROOT)})
    conn=None
    reports=[]
    traci=lock_traci()
    try:
        with (path/'stdout.log').open('w') as stdout,(path/'readback.jsonl').open('w',encoding='utf-8') as trace:
            label='phase2_'+path.parent.name+'_'+path.name
            traci.start(command,label=label,stdout=stdout)
            conn=traci.getConnection(label)
            initial=steps[0].initial
            x,y,angle=to_sumo_pose(initial,model.p['length_m'])
            lane=min(2,max(0,int(initial.y_m/model.p['lane_width_m'])))
            conn.vehicle.add('ego','r',typeID='external_bench',departLane=str(lane),departPos=str(x),departSpeed='0')
            conn.simulationStep()
            conn.vehicle.setSpeedMode('ego',model.p['sumo_speed_mode'])
            conn.vehicle.setLaneChangeMode('ego',model.p['sumo_lane_change_mode'])
            conn.vehicle.setSpeed('ego',model.observe(initial)['speed_mps'])
            conn.vehicle.moveToXY('ego','',-1,x,y,angle=angle,keepRoute=model.p['sumo_move_keep_route'])
            conn.simulationStep()
            bridge=ExternalBridge(conn,'ego',model,initial,sync_dt_s)
            atomic_json(path/'bootstrap.json',{'sumo_version':conn.getVersion(),'initial_readback':bridge.last_report,
                       'excluded_initialization_steps':2,'purpose':'Initialize prescribed state before physical t=0'})
            for step in steps:
                try:
                    report=bridge.synchronize(step)
                except SynchronizationError as exc:
                    trace.write(json.dumps(exc.report,allow_nan=False)+'\n')
                    trace.flush()
                    raise
                trace.write(json.dumps(report,allow_nan=False)+'\n')
                reports.append(report)
            result={'passed':True,'status':'completed','intervals':len(reports),'sumo_version':conn.getVersion(),
                    'sumo_time_offset_s':bridge.time_offset,
                    'max_position_error_m':max(r['position_error_m'] for r in reports),
                    'max_speed_error_mps':max(r['speed_error_mps'] for r in reports),
                    'max_heading_error_rad':max(r['heading_error_rad'] for r in reports),
                    'max_time_error_s':max(r['time_error_s'] for r in reports),
                    'max_interval_acceleration_error_mps2':max(r['interval_acceleration_error_mps2'] for r in reports),
                    'colliding_vehicle_reports':sum(r['colliding_vehicle_reports'] for r in reports),
                    'teleport_starts':sum(r['teleport_starts'] for r in reports),
                    'edge_ids':sorted(set(r['edge_id'] for r in reports)),
                    'lane_ids':sorted(set(r['lane_id'] for r in reports)),
                    'edge_transitions':[{'time_s':b['physical_time_s'],'from':a['lane_id'],'to':b['lane_id'],
                                         'lateral_step_m':abs(b['cg_y_m']-a['cg_y_m'])}
                        for a,b in zip(reports,reports[1:]) if a['edge_id']!=b['edge_id']]}
    except Exception as exc:
        result={'passed':False,'status':'failed','error':f'{type(exc).__name__}: {exc}',
                'traceback':traceback.format_exc(),'completed_intervals':len(reports)}
    finally:
        if conn is not None:
            conn.close()
    atomic_json(path/'validation.json',result)
    return result


def run_phase2():
    with RunRecord(BASE,{'purpose':'Phase 2 attempt; initialization pending'}) as run:
        path,passed=_execute_phase2(run)
    if not passed:
        raise RuntimeError(f'Phase 2 gate failed; complete evidence retained in {path}')
    return path


def _execute_phase2(run):
    from experiments.phase2_cases import cases
    from experiments.offline import run_case,evaluate_case,compare_trajectories
    from research.verify import verify
    model=VehicleModel.from_config()
    manifest=code_manifest()
    metadata={'purpose':'Phase 2 isolated single-vehicle dynamics benches; no NOA or efficiency conclusion',
              'parameters':dict(model.p),'python':sys.version,'code_and_config_hashes':manifest,
              'input_hashes':{str(p.relative_to(ROOT)):sha256(p) for p in (NET,ROOT/'docs/parameter_registry.csv',
                 ROOT/'docs/noa_staggered_formation_research_plan_2026-09-10.md')},
              'perception_mode':model.p['perception_mode'],'controller_access':'Own state and prescribed single-vehicle reference only'}
    atomic_json(run.path/'metadata.json',{**metadata,'run_id':run.run_id})
    verify()
    foundation=read_json('results/phase1/foundation_verification.json')
    smoke=read_json('results/phase1/smoke/validation.json')
    atomic_json(run.path/'preconditions.json',{'foundation_passed':foundation['passed'],
                'phase1_smoke_passed':smoke['passed'],'phase1_smoke_run_id':smoke['run_id'],
                'source_hash_check':read_json('results/phase0/source_hash_check.json'),
                'note':'Fresh source/network/demand verification; native smoke is historical topology evidence'})
    if not foundation['passed'] or not smoke['passed']:
        raise RuntimeError('Phase 0-1 prerequisites not passed')
    for relative in manifest:
        target=run.path/'source_snapshot'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
    for relative in metadata['input_hashes']:
        target=run.path/'input_snapshot'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
    road=RoadEnvelope.from_net(NET)
    all_results=[]
    for case in cases():
        case_path=run.path/case['name']
        case_path.mkdir()
        atomic_json(case_path/'case.json',case)
        base=run_case(model,case,.1,.01)
        refined=run_case(model,case,.1,.005,commands=[s.command for s in base])
        fast=run_case(model,case,.05,.01)
        variants={}
        for name,steps,control_dt,dynamics_dt in (('base',base,.1,.01),('integration_half',refined,.1,.005),('control_half',fast,.05,.01)):
            sub=case_path/name
            sub.mkdir()
            save_trace(sub/'trace.jsonl',model,steps)
            trace_meta={'parameters':dict(model.p),'case':case,'initial':asdict(steps[0].initial),
                        'control_dt_s':control_dt,'dynamics_dt_s':dynamics_dt,'intervals':len(steps)}
            atomic_json(sub/'metadata.json',trace_meta)
            variants[name]={'case_evaluation':evaluate_case(model,case,steps),'geometry':audit_geometry(model,steps,road),
                            'replay':replay_trace(trace_meta,sub/'trace.jsonl')}
            # Integration half uses the identical stored command schedule; both control rates are also verified in real SUMO.
            if name!='integration_half':
                variants[name]['sumo']=run_sumo(sub/'sumo',model,steps,control_dt)
            atomic_json(sub/'validation.json',variants[name])
        integration=compare_trajectories(base,refined)
        control=compare_trajectories(base,fast)
        integration['passed']=(integration['max_position_error_m']<=model.p['integration_position_tolerance_m'] and
                               integration['max_heading_error_rad']<=model.p['integration_heading_tolerance_rad'])
        control['passed']=(control['max_position_error_m']<=model.p['control_position_tolerance_m'] and
                           control['max_heading_error_rad']<=model.p['control_heading_tolerance_rad'])
        passed=integration['passed'] and control['passed'] and all(r['passed'] for variant in variants.values() for r in variant.values())
        if case['name']=='edge_crossing':
            passed=passed and all(v['sumo']['edge_ids']==['downstream','upstream'] for k,v in variants.items() if 'sumo' in v)
        result={'name':case['name'],'passed':passed,'variants':variants,'integration_halving':integration,'control_halving':control}
        atomic_json(case_path/'validation.json',result)
        all_results.append(result)
        print(json.dumps({'case':case['name'],'passed':passed,'integration':integration,'control':control}),flush=True)
    faults=fault_checks(model,road)
    atomic_json(run.path/'faults.json',faults)
    passed=all(r['passed'] for r in all_results) and faults['passed']
    result={'passed':passed,'cases':all_results,'faults':faults,'noa_implemented':False,'traffic_benefits_evaluated':False,
            'next_stage_allowed':'phase3_small_case_development' if passed else None}
    run.finish(result)
    evidence={p.relative_to(run.path).as_posix():sha256(p) for p in run.path.rglob('*') if p.is_file() and p.name!='evidence_hashes.json'}
    atomic_json(run.path/'evidence_hashes.json',evidence)
    print(json.dumps({'run_id':run.run_id,'passed':passed,'path':str(run.path)}),flush=True)
    return run.path,passed


def replay_run(run_dir=None):
    with RunRecord(ROOT/'results/phase2/replays',{'source_run':str(run_dir),'purpose':'Numerical replay attempt'}) as record:
        result=_execute_replay(run_dir,record)
    if not result['passed']:
        raise RuntimeError('Phase 2 replay failed')
    return result


def _execute_replay(run_dir,record):
    run_path=output_path(run_dir or read_json(BASE/'latest.json')['path'])
    source=read_json(run_path/'metadata.json')
    validations=read_json(run_path/'validation.json')
    hashes=read_json(run_path/'evidence_hashes.json')
    mismatches=[name for name,digest in hashes.items() if not (run_path/name).is_file() or sha256(run_path/name)!=digest]
    current=code_manifest()
    code_changed=[name for name,digest in source['code_and_config_hashes'].items() if current.get(name)!=digest]
    traces=[]
    for meta_path in sorted(run_path.glob('*/*/metadata.json')):
        traces.append({'path':str(meta_path.parent.relative_to(run_path)),
                       **replay_trace(read_json(meta_path),meta_path.parent/'trace.jsonl')})
    passed=bool(traces) and validations['status']=='completed' and not mismatches and all(x['passed'] for x in traces)
    result={'passed':passed,'source_run_id':validations['run_id'],'source_gate_passed':validations['passed'],
            'changed_current_source_files':code_changed,'evidence_hash_mismatches':mismatches,'traces':traces,
            'meaning':'Numerical replay consistency is distinct from the original scientific gate passing'}
    atomic_json(record.path/'metadata.json',{'run_id':record.run_id,'source_run':str(run_path)})
    record.finish(result)
    print(json.dumps(result),flush=True)
    return result
