"""Stage4 small-case runner. All attempts and unsuccessful conditions persist."""
from dataclasses import asdict
import copy
import json
import math
import re
import shutil
import sys
import traceback
from experiments.records import RunRecord, atomic_json
from experiments.phase3 import integration_refinement, NET
from experiments.phase4_bootstrap import bootstrap
from experiments.phase3_audit import geometry_report, compare_records
from experiments.phase4_cases import cases
from experiments.phase4_audit import driving_metrics, isolation_audit
from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.road import VisibleRoad
from safety.geometry import RoadEnvelope
from simulation.noa_clock import NoaClock
from research.common import ROOT, output_path, settings, read_json, code_manifest, sha256, command


def run_case(path,model,p,policy,case,live=True):
    from experiments.phase4_replay import replay_case
    path=output_path(path)
    path.mkdir(parents=True,exist_ok=False)
    atomic_json(path/'validation.json',{'passed':False,'status':'running'})
    conn,bridge,clock=None,None,None
    records=[]
    trace_count,completed_count=0,0
    meta={'case':case,'parameters':dict(p),'policy_parameters':dict(policy),'model_parameters':dict(model.p),
          'initial':case['initial'],'intervals':round(case['duration_s']/p['control_sync_dt_s']),
          'live':live,'sumo_time_offset_s':None,'execution_status':'running'}
    atomic_json(path/'metadata.json',meta)
    failure,pending_interrupt=None,None
    try:
        if meta['intervals']<1 or not math.isclose(meta['intervals']*p['control_sync_dt_s'],case['duration_s'],abs_tol=1e-9):
            raise ValueError('Case duration must contain complete control intervals')
        road=VisibleRoad.from_net(NET)
        meta['road']=asdict(road)
        atomic_json(path/'metadata.json',meta)
        initial={k:VehicleState(**s) for k,s in case['initial'].items()}
        clock=NoaClock(initial,model,road,p,policy,case['controlled'],case['scripts'])
        with (path/'stdout.log').open('w',encoding='utf-8') as stdout,(path/'trace.jsonl').open('w',encoding='utf-8') as trace:
            if live:
                conn,bridge=bootstrap(path,initial,model,{**p,'phase3_seed':p['phase4_seed']},stdout)
                meta.update(sumo_time_offset_s=bridge.time_offset,sumo_version=conn.getVersion())
                atomic_json(path/'metadata.json',meta)
            for _ in range(meta['intervals']):
                try:
                    record=clock.tick(bridge=bridge)
                except BaseException:
                    trace.write(json.dumps(clock.last_record,allow_nan=False)+'\n')
                    trace.flush()
                    trace_count+=1
                    if set(clock.last_record.get('steps',{}))==set(initial) and set(clock.last_record.get('diagnostics',{}))==set(initial):
                        records.append(clock.last_record)
                    raise
                trace.write(json.dumps(record,allow_nan=False)+'\n')
                trace.flush()
                records.append(record)
                trace_count+=1
                completed_count+=1
        meta['execution_status']='completed'
    except BaseException as exc:
        failure=f'{type(exc).__name__}: {exc}'
        meta.update(execution_status='failed',failure_error=failure,failure_traceback=traceback.format_exc(),
                    failure_readback_phase=getattr(bridge,'readback_phase',None))
        if not isinstance(exc,Exception):
            pending_interrupt=exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:
                failure=f'Close failure: {exc}'
                meta.update(execution_status='failed',close_error=failure)
    meta.update(recorded_intervals=len(records),trace_intervals=trace_count,completed_intervals=completed_count,
                physical_intervals=len(records),isolation_intervals=len(records),partial_tail=trace_count>len(records),
                failure_stage=clock.last_record.get('failure_stage') if clock and clock.last_record else None,
                failure_actor=clock.last_record.get('failure_actor') if clock and clock.last_record else None)
    if failure and clock and clock.last_record and isinstance(clock.last_record.get('readback'),dict):
        meta['failure_readback_states']={key:report.get('status','recorded') for key,report in clock.last_record['readback'].items()}
    atomic_json(path/'metadata.json',meta)
    result={'passed':False,'status':meta['execution_status'],'recording_passed':False,'driving_passed':False,
            'error':failure,'recorded_intervals':len(records),'planned_intervals':meta['intervals'],
            'physical_sumo_advances':bridge.advances if bridge else 0}
    try:
        if trace_count:
            replay=replay_case(meta,path/'trace.jsonl')
            isolation=isolation_audit(records,model,p,policy,road,case['controlled'],path/'isolation.jsonl')
            if not records:
                isolation.update(passed=True,status='not_applicable',scope='No complete physical interval; partial tail checked by trace replay')
            result.update(isolation=isolation,replay=replay,recording_passed=replay['passed'] and isolation['passed'])
        if records:
            geometry=geometry_report(records,model,RoadEnvelope.from_net(NET))
            metrics=driving_metrics(records,model,p,case)
            readings=[v for r in records for v in (r['readback'] or {}).values() if 'position_error_m' in v]
            result.update(geometry=geometry,metrics=metrics,isolation=isolation,replay=replay,
                          recording_passed=replay['passed'] and isolation['passed'],
                          driving_passed=not failure and geometry['passed'] and metrics['requirements_passed'] and metrics['tracking_passed'],
                          comfort_passed=metrics['comfort_passed'],
                          max_position_readback_error_m=max((r['position_error_m'] for r in readings),default=0.),
                          max_time_readback_error_s=max((r['time_error_s'] for r in readings),default=0.),
                          edge_ids=sorted({r['edge_id'] for r in readings}),
                          lane_indices=sorted({r['lane_index'] for r in readings}))
    except Exception as exc:
        result.update(status='failed',evaluation_error=f'{type(exc).__name__}: {exc}',evaluation_traceback=traceback.format_exc())
    warnings={'initialization_only':[],'physical_or_unclassified':[]}
    if live and (path/'sumo.log').is_file():
        for line in (path/'sumo.log').read_text(encoding='utf-8',errors='replace').splitlines():
            if 'Warning:' not in line and 'Error:' not in line:
                continue
            stamp=re.search(r'time=([0-9.]+)',line)
            initial=(stamp and meta['sumo_time_offset_s'] is not None and float(stamp[1].rstrip('.'))<meta['sumo_time_offset_s']-1e-9 and 'moved by TraCI' in line)
            warnings['initialization_only' if initial else 'physical_or_unclassified'].append(line)
    result['sumo_warnings']=warnings
    if warnings['physical_or_unclassified']:
        result['driving_passed']=False
    result['passed']=result['recording_passed'] and result['driving_passed'] and result.get('comfort_passed',False)
    atomic_json(path/'validation.json',result)
    if pending_interrupt is not None:
        raise pending_interrupt
    return result


def write_faults(path,source):
    from experiments.phase4_replay import replay_case
    path.mkdir(parents=True,exist_ok=False)
    meta=read_json(source/'metadata.json')
    original=[json.loads(line) for line in (source/'trace.jsonl').read_text().splitlines()]
    entries=[]
    for name in ('observation','own_memory','action','initial','substep','decision','time','truncate','readback'):
        records=copy.deepcopy(original)
        key=meta['case']['controlled'][0]
        if name=='observation': records[0]['inputs'][key]['observation']['road']['measurement_time_s']+=.01
        elif name=='own_memory': records[1]['inputs'][key]['memory']['observation_history']=[]
        elif name=='action': records[0]['actions'][key]['acceleration_mps2']+=.01
        elif name=='initial': records[1]['initial'][key]['x_m']+=.01
        elif name=='substep': records[0]['steps'][key]['samples'][0]['y_m']+=.01
        elif name=='decision': records[0]['decisions'][key]['memory']['own_behavior']='CORRUPTED'
        elif name=='time': records[0]['steps'][key]['final']['time_s']+=.01
        elif name=='readback':
            if meta['live']:
                records[0]['readback'][key]['sumo_time_s']+=.01
            else:
                records[0]['readback']={}
        else: records.pop()
        trace=path/(name+'.jsonl')
        trace.write_text(''.join(json.dumps(row)+'\n' for row in records),encoding='utf-8')
        atomic_json(path/(name+'.metadata.json'),meta)
        report=replay_case(meta,trace)
        entries.append({'name':name,'rejected':not report['passed'],'errors':report['errors'],
                        'trace':trace.relative_to(path.parent).as_posix(),
                        'metadata':(path/(name+'.metadata.json')).relative_to(path.parent).as_posix()})
    result={'passed':all(e['rejected'] for e in entries),'faults':entries}
    atomic_json(path/'manifest.json',result)
    return result


def run_phase4(base=None,live=True,case_names=None):
    run=RunRecord(base or ROOT/'results/phase4/runs',{'purpose':'Phase4 attempt','command_line':sys.argv,'python':sys.version})
    try:
        return _run_phase4(run,live,case_names)
    except BaseException as exc:
        if not run.finished and (run.path/'metadata.json').is_file():
            meta=read_json(run.path/'metadata.json')
            meta.update(execution_status='failed',failure_error=f'{type(exc).__name__}: {exc}')
            atomic_json(run.path/'metadata.json',meta)
        raise
    finally:
        if run.path.is_dir():
            # RunRecord has already persisted its final failure/completion state.
            hashes={f.relative_to(run.path).as_posix():sha256(f) for f in run.path.rglob('*')
                    if f.is_file() and f!=run.path/'evidence_hashes.json'}
            atomic_json(run.path/'evidence_hashes.json',hashes)


def _run_phase4(run,live,case_names):
    with run:
        manifest=code_manifest()
        meta={'run_id':run.run_id,'command_line':sys.argv,'python':sys.version,'code_and_config_hashes':manifest,
              'case_trace_directories':[],'integration_trace_directories':[],'execution_status':'running',
              'fault_injection_status':'not_run','scope':'Independent NOA small cases, formation off; no traffic or energy comparison'}
        atomic_json(run.path/'metadata.json',meta)
        for relative in manifest:
            target=run.path/'source_snapshot'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/relative,target)
        model=KinematicModel.from_config()
        p={**dict(model.p),**settings('phase3'),**settings('phase4_experiments')}
        policy={**dict(model.p),**settings('phase4')}
        meta.update(parameters=p,policy_parameters=policy,live=live)
        atomic_json(run.path/'metadata.json',meta)
        python=read_json('configs/tools.json')['python']
        command([python,'-I','-B','-S','run.py','verify'],run.path/'verify.json')
        previous=read_json('results/phase3/runs/20260910T163533938451Z_2dcd59f7/validation.json')
        if not previous['passed']:
            raise RuntimeError('Stage3 prerequisite gate not passed')
        for relative in ('scenarios/cai2024/bottleneck.net.xml','docs/parameter_registry.csv',
                         'docs/noa_staggered_formation_research_plan_2026-09-10.md','docs/phase3_acceptance.md','docs/phase4_implementation_plan.md'):
            target=run.path/'input_snapshot'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/relative,target)
        selected=[case for case in cases(model.p) if case_names is None or case['name'] in case_names]
        if not selected:
            raise ValueError('No cases selected')
        atomic_json(run.path/'cases.json',selected)
        results=[]
        for case in selected:
            sub=run.path/case['name']/'base'
            meta['case_trace_directories'].append(sub.relative_to(run.path).as_posix())
            atomic_json(run.path/'metadata.json',meta)
            result=run_case(sub,model,p,policy,case,live=live)
            entry={'name':case['name'],'stress':case['stress'],'variants':{'base':result}}
            if case['name']=='normal_lane_change' and result['status']=='completed':
                records=[json.loads(line) for line in (sub/'trace.jsonl').read_text().splitlines()]
                refinement,dirs=integration_refinement(run.path/case['name']/'integration_half',records,model,p)
                entry['integration_half']=refinement
                meta['integration_trace_directories'].extend(d.relative_to(run.path).as_posix() for d in dirs)
                half=run.path/case['name']/'sampling_half'
                half_p={**p,'control_sync_dt_s':p['control_sync_dt_s']/2,'perception_dt_s':p['perception_dt_s']/2}
                half_policy={**policy,'control_sync_dt_s':half_p['control_sync_dt_s'],'perception_dt_s':half_p['perception_dt_s']}
                meta['case_trace_directories'].append(half.relative_to(run.path).as_posix())
                atomic_json(run.path/'metadata.json',meta)
                entry['variants']['sampling_half']=run_case(half,model,half_p,half_policy,case,live=live)
                if entry['variants']['sampling_half']['status']=='completed':
                    other=[json.loads(line) for line in (half/'trace.jsonl').read_text().splitlines()]
                    comparison=compare_records(records,other)
                    comparison['passed']=(comparison['max_position_error_m']<=model.p['control_position_tolerance_m'] and comparison['max_heading_error_rad']<=model.p['control_heading_tolerance_rad'])
                    entry['sampling_half_comparison']=comparison
            entry['passed']=all(v['passed'] for v in entry['variants'].values())
            if 'integration_half' in entry:
                entry['passed'] &= entry['integration_half']['passed'] and entry.get('sampling_half_comparison',{}).get('passed',False)
            results.append(entry)
            atomic_json(run.path/case['name']/'validation.json',entry)
            atomic_json(run.path/'metadata.json',meta)
            print(json.dumps({'case':case['name'],'passed':entry['passed'],'driving_passed':result['driving_passed'],
                              'recording_passed':result['recording_passed'],'status':result['status']}),flush=True)
        source=next((run.path/e['name']/'base' for e in results if e['variants']['base']['recording_passed'] and e['variants']['base']['status']=='completed'),None)
        faults=write_faults(run.path/'faults',source) if source else {'passed':False,'error':'No valid source for fault injection'}
        meta['fault_injection_status']='completed' if source else 'unavailable'
        normal=[e for e in results if not e['stress']]
        recording=all(v['recording_passed'] for e in results for v in e['variants'].values())
        sensitive=sum(v.get('isolation',{}).get('visible_neighbor_removal_changes_action',0) for e in results for v in e['variants'].values())
        final_manifest=code_manifest()
        source_changes=[name for name in set(manifest)|set(final_manifest) if manifest.get(name)!=final_manifest.get(name)]
        result={'passed':live and len(selected)==len(cases(model.p)) and bool(normal) and all(e['passed'] for e in normal) and recording and faults['passed'] and sensitive>0 and not source_changes,
                'cases':results,'faults':faults,'recording_passed':recording,'nonvacuous_action_changes':sensitive,
                'normal_cases_passed':sum(e['passed'] for e in normal),'normal_cases_total':len(normal),
                'stress_cases':[e['name'] for e in results if e['stress']],'formation_enabled':False,'traffic_benefits_evaluated':False,
                'complete_suite':len(selected)==len(cases(model.p)),'live':live,'source_changed_during_run':sorted(source_changes)}
        result['next_stage_allowed']='phase5_small_cases' if result['passed'] else None
        meta['execution_status']='completed'
        atomic_json(run.path/'metadata.json',meta)
        run.finish(result)
    print(json.dumps({'run_id':run.run_id,'passed':result['passed'],'path':str(run.path)}),flush=True)
    if not result['passed']:
        raise RuntimeError(f'Phase4 gate failed; all evidence retained at {run.path}')
    return run.path
