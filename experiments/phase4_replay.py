"""Recompute stage4 policy, own memory and physics, retaining failed-run status."""
from dataclasses import asdict
import json
from pathlib import Path
from experiments.records import RunRecord, atomic_json
from experiments.phase3_replay import compare_tree, replay_motion_trace
from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.road import VisibleRoad
from simulation.external_bridge import audit_readback
from simulation.noa_clock import NoaClock, ReplayBoundary
from research.common import ROOT, output_path, read_json, code_manifest, sha256


def rebuild_clock(metadata):
    model=KinematicModel(metadata['model_parameters'])
    road=VisibleRoad(tuple(tuple(tuple(v) for v in line) for line in metadata['road']['boundaries']),
                     tuple(tuple(tuple(v) for v in line) for line in metadata['road']['markings']))
    clock=NoaClock({k:VehicleState(**v) for k,v in metadata['initial'].items()},model,road,
                   metadata['parameters'],metadata['policy_parameters'],metadata['case']['controlled'],metadata['case']['scripts'])
    return model,road,clock


def replay_readbacks(metadata,stored,expected,model,failed_tail):
    """Audit only captured reports, at their preserved pre/postcommit time."""
    phase=metadata.get('failure_readback_phase') if failed_tail else 'postcommit'
    phase=phase or 'postcommit'
    if phase not in ('integration_validation','precommit','commit','postcommit'):
        raise ValueError('Unknown synchronization failure phase')
    reports=stored['readback']
    if not isinstance(reports,dict):
        raise ValueError('Missing live readback object')
    states={key:report.get('status','recorded') for key,report in reports.items()}
    declared=metadata.get('failure_readback_states',{key:'recorded' for key in metadata['initial']}) if failed_tail else {key:'recorded' for key in metadata['initial']}
    if states!=declared:
        raise ValueError('Captured readback coverage differs from metadata')
    if phase in ('integration_validation','commit'):
        if reports:
            raise ValueError('Readbacks were not produced during this synchronization phase')
        return {}
    if set(reports)!=set(metadata['initial']):
        raise ValueError('Incomplete live vehicle readback')
    raw_fields=('sumo_time_s','front_x_m','front_y_m','angle_deg','speed_mps','acceleration_mps2',
                'edge_id','lane_id','lane_index','colliding_vehicle_reports','teleport_starts')
    rebuilt={}
    for key in metadata['initial']:
        status=states[key]
        if status=='not_read' and failed_tail:
            rebuilt[key]={'passed':False,'status':'not_read','errors':['Readback not reached']}
        elif status=='readback_exception' and failed_tail:
            rebuilt[key]={'passed':False,'status':'readback_exception','errors':[metadata['failure_error']]}
        elif status=='recorded':
            raw={name:reports[key][name] for name in raw_fields}
            previous=VehicleState(**expected['initial'][key])
            current=VehicleState(**expected['steps'][key]['final']) if phase=='postcommit' else previous
            accel=(model.observe(current)['speed_mps']-model.observe(previous)['speed_mps'])/metadata['parameters']['control_sync_dt_s'] if phase=='postcommit' else None
            report=audit_readback(raw,current,model,metadata['sumo_time_offset_s'],accel)
            if raw['colliding_vehicle_reports'] or raw['teleport_starts']:
                report['errors'].append('SUMO collision or teleport reported')
                report['passed']=False
            if not report['passed'] and not failed_tail:
                raise ValueError('Invalid live synchronization')
            rebuilt[key]=report
        else:
            raise ValueError('Unknown readback capture state')
    return rebuilt


def replay_case(metadata,trace_path):
    errors,count,samples,maximum=[],0,0,0.
    completed,physical=0,0
    failed_prefix=metadata.get('execution_status','completed')=='failed'
    try:
        model,road,clock=rebuild_clock(metadata)
        expected_count=metadata.get('trace_intervals',metadata.get('recorded_intervals',metadata['intervals'])) if failed_prefix else metadata['intervals']
        with output_path(trace_path).open(encoding='utf-8') as handle:
            for count,line in enumerate(handle,1):
                stored=json.loads(line)
                failed_tail=failed_prefix and count==expected_count and stored['status']=='failed'
                boundary=(metadata.get('failure_stage'),metadata.get('failure_actor')) if failed_tail else None
                if boundary and boundary[0] is not None:
                    try:
                        clock.tick(stop_before=boundary)
                    except ReplayBoundary:
                        expected=clock.last_record
                        expected['error']=metadata['failure_error']
                    else:
                        raise ValueError('Recorded failure boundary was not reached')
                else:
                    expected=clock.tick()
                if metadata['live'] and (not boundary or boundary[0] in (None,'synchronization','commit')):
                    expected['readback']=replay_readbacks(metadata,stored,expected,model,failed_tail)
                if failed_tail:
                    if stored['error']!=metadata.get('failure_error'):
                        raise ValueError('Failure reason differs from preserved metadata')
                    expected.update(status='failed',error=stored['error'])
                    if metadata['live'] and (not boundary or boundary[0] in (None,'synchronization')):
                        expected['readback_phase']=metadata['failure_readback_phase']
                maximum=max(maximum,compare_tree(expected,stored,model.p['replay_absolute_tolerance'],f'interval{count}'))
                samples+=sum(len(v['samples']) for v in expected.get('steps',{}).values())
                completed+=stored['status']=='completed'
                physical+=set(stored.get('steps',{}))==set(metadata['initial']) and set(stored.get('diagnostics',{}))==set(metadata['initial'])
        if count!=expected_count or count<1:
            raise ValueError(f'Truncated trace: {count}/{expected_count}')
        counts={'trace_intervals':count,'completed_intervals':completed,'physical_intervals':physical,
                'recorded_intervals':physical,'isolation_intervals':physical,'partial_tail':count>physical}
        for name,value in counts.items():
            if name in metadata and metadata[name]!=value:
                raise ValueError(f'Inconsistent {name}: {value}/{metadata[name]}')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed':not errors,'errors':errors,'intervals':count,'vehicle_substeps':samples,'max_numeric_error':maximum,
            'failed_execution_prefix':failed_prefix,'meaning':'Recorded policy and physical prefix reconstructed; a failed drive remains failed'}


def replay_isolation(metadata,trace_path,audit_path):
    from experiments.phase4_audit import isolation_rows
    errors,count=[],0
    try:
        trace_report=replay_case(metadata,trace_path)
        if not trace_report['passed']:
            raise ValueError(f'Invalid trace for isolation audit: {trace_report["errors"]}')
        model,road,clock=rebuild_clock(metadata)
        records=[json.loads(line) for line in output_path(trace_path).read_text().splitlines()]
        scope=metadata.get('isolation_intervals',metadata.get('recorded_intervals',len(records)))
        records=records[:scope]
        expected=isolation_rows(records,model,metadata['parameters'],metadata['policy_parameters'],road,metadata['case']['controlled'])
        from itertools import zip_longest
        with output_path(audit_path).open(encoding='utf-8') as handle:
            for count,(reference,line) in enumerate(zip_longest(expected,handle),1):
                if reference is None or line is None:
                    raise ValueError('Truncated or extra isolation audit')
                row=json.loads(line)
                compare_tree(reference,row,model.p['replay_absolute_tolerance'])
                if not row['identical']:
                    raise ValueError('Local information isolation mismatch')
        if count<1 and records:
            raise ValueError('No isolation comparisons')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed':not errors,'comparisons':count,'errors':errors}


def replay_run(run_dir=None,base=None):
    with RunRecord(base or ROOT/'results/phase4/replays',{'purpose':'Independent phase4 replay','source_run':str(run_dir)}) as replay:
        path=output_path(run_dir or read_json('results/phase4/runs/latest.json')['path'])
        metadata=read_json(path/'metadata.json')
        gate=read_json(path/'validation.json')
        hashes=read_json(path/'evidence_hashes.json')
        differences=[name for name,digest in hashes.items() if not (path/name).is_file() or sha256(path/name)!=digest]
        current=code_manifest()
        changed=[name for name,digest in metadata['code_and_config_hashes'].items() if current.get(name)!=digest]
        cases=[]
        for relative in metadata['case_trace_directories']:
            folder=path/relative
            case_meta=read_json(folder/'metadata.json')
            trace=replay_case(case_meta,folder/'trace.jsonl')
            isolation=replay_isolation(case_meta,folder/'trace.jsonl',folder/'isolation.jsonl') if (folder/'isolation.jsonl').is_file() else {'passed':False,'errors':['No complete isolation audit']}
            cases.append({'case':relative,'trace':trace,'isolation':isolation,'passed':trace['passed'] and isolation['passed']})
        refinements=[{'case':relative,**replay_motion_trace(read_json(path/relative/'metadata.json'),path/relative/'trace.jsonl')}
                     for relative in metadata.get('integration_trace_directories',[])]
        faults=[]
        if (path/'faults/manifest.json').is_file():
            for item in read_json(path/'faults/manifest.json')['faults']:
                report=replay_case(read_json(path/item['metadata']),path/item['trace'])
                faults.append({'name':item['name'],'rejected':not report['passed'],'errors':report['errors']})
        interrupted_before_faults=(gate['status']=='failed' and metadata.get('execution_status')=='failed'
                                  and metadata.get('fault_injection_status')=='not_run')
        faults_valid=(bool(faults) and all(f['rejected'] for f in faults)) or interrupted_before_faults
        result={'passed':bool(cases) and not differences and all(r['passed'] for r in cases+refinements) and faults_valid,
                'source_run_id':path.name,'source_driving_gate_passed':gate['passed'],'evidence_hash_mismatches':differences,
                'changed_current_source_files':changed,'cases':cases,'integration_refinements':refinements,'faults':faults,
                'fault_injection_performed':bool(faults),'interrupted_before_fault_injection':interrupted_before_faults,
                'meaning':'Reconstructed local decisions and physics; original SUMO readbacks checked without restarting SUMO. Replay success does not turn driving failures into successes.'}
        replay.finish(result)
    print(json.dumps(result),flush=True)
    if not result['passed']:
        raise RuntimeError(f'Phase4 replay failed; retained at {replay.path}')
    return result
