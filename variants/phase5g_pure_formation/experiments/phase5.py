"""Append-only stage5 development runs, with scientific failures retained."""
from dataclasses import asdict
from pathlib import Path
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
from experiments.phase4_audit import driving_metrics
from experiments.phase5_cases import cases
from experiments.phase5_detection import detect_frames
from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.road import VisibleRoad
from perception.road import ego_point, in_box
from safety.geometry import RoadEnvelope
from research.common import ROOT, output_path, settings, read_json, code_manifest, sha256


def parameters(enabled):
    model=KinematicModel.from_config()
    development=settings('phase5_experiments')
    p={**dict(model.p),**settings('phase3'),**settings('phase4_experiments'),**development,
       'formation_enabled':enabled}
    policy={**dict(model.p),**settings('phase4'),**settings('phase5'),
            'formation_enabled':enabled,'noa_target_speed_mps':development['phase5_target_speed_mps']}
    return model,p,policy


def frames_from_records(records):
    frames=[]
    final=None
    for record in records:
        if record['status']!='completed':
            continue
        states={key:dict(state) for key,state in record['initial'].items()}
        frames.append({'time_s':next(iter(states.values()))['time_s'],'states':states})
        final={key:dict(step['final']) for key,step in record['steps'].items()}
    if final is not None:
        frames.append({'time_s':next(iter(final.values()))['time_s'],'states':final})
    return frames


def detection_report(records):
    frames=frames_from_records(records)
    return {'default':detect_frames(frames), 'sensitivity':{
        str(factor):detect_frames(frames,position_tolerance=2*factor,speed_tolerance=factor)
        for factor in (.5,1.,1.5)}}


def recovery_report(detection,case):
    start=case.get('event_start_s',0.)
    # Confirmation must precede the event; a never-formed group cannot recover.
    prior=any(i['whole_cohort'] and i['formed_time_s'] is not None
              and i['formed_time_s']<=start and i['end_time_s']>=start-1e-9
              for i in detection['intervals'])
    losses=[f['time_s'] for f in detection['frames'] if f['time_s']>=start and f['fleet_failure_reasons']]
    loss=min(losses) if prior and losses else None
    later=[i for i in detection['intervals'] if loss is not None and i['whole_cohort']
           and i['start_time_s']>loss and i['held_time_s'] is not None]
    recovered=min(later,key=lambda i:i['start_time_s']) if later else None
    return {'formed_before_event':prior,'loss_time_s':loss,'recovered_and_held':recovered is not None,
            'recovery_formed_time_s':recovered['formed_time_s'] if recovered else None,
            'recovery_held_time_s':recovered['held_time_s'] if recovered else None,
            'meaning':'Recovery requires prior confirmed whole group, actual geometric loss, then a new 5s-confirmed group held another10s; initial30s deadline is not reapplied to recovery.'}


def reference_visibility(records,case,p):
    """Offline named-actor audit only; no event key enters the online policy."""
    actors={}
    if 'event' not in case['initial']:
        return {'passed':False,'actors':actors,'scope':'No exogenous reference-range case'}
    for key in case['controlled']:
        timeline=[]
        for r in records:
            own=VehicleState(**r['initial'][key])
            event=r['initial']['event']
            point=ego_point(event['x_m'],event['y_m'],own)
            visible=in_box(point,p)
            observation=r['inputs'][key]['observation']['neighbors']
            observed=any(math.hypot(n['relative_x_m']-point[0],n['relative_y_m']-point[1])<1e-6 for n in observation)
            m=r['decisions'][key]['memory']
            sig=m.get('reference_signature')
            ref=(event['x_m'],event['y_m'],
                 event['vx_mps']*math.cos(event['heading_rad'])-event['vy_mps']*math.sin(event['heading_rad']),
                 event['vx_mps']*math.sin(event['heading_rad'])+event['vy_mps']*math.cos(event['heading_rad']),
                 event['heading_rad'],p['length_m'],p['width_m'])
            selected=sig is not None and len(sig)==7 and all(abs(a-b)<1e-6 for a,b in zip(sig,ref))
            timeline.append({'time_s':own.time_s,'inside_range':visible,'observed':observed,
                'selected_as_reference':selected,'state':m.get('formation_state','OFF'),
                'weight':m.get('formation_weight',0.),'reason':r['decisions'][key]['diagnostics'].get('formation',{}).get('reason','OFF')})
        chains=[]
        for i in range(1,len(timeline)):
            previous,current=timeline[i-1:i+1]
            if previous['inside_range'] and previous['selected_as_reference'] and not current['inside_range']:
                # The old reference must lose authority; its command may only fade.
                released=(not current['selected_as_reference'] and
                          (current['state'] in ('RECONFIGURING','FALLBACK','NOA_ONLY') or current['weight']<previous['weight']))
                entry=next((j for j in range(i+1,len(timeline)) if timeline[j]['inside_range'] and timeline[j]['observed']),None)
                again=next((j for j in range(entry,len(timeline)) if timeline[j]['selected_as_reference']),None) if entry is not None else None
                chains.append({'exit_time_s':current['time_s'],'reference_released':released,
                    'reentry_time_s':timeline[entry]['time_s'] if entry is not None else None,
                    'reselected_time_s':timeline[again]['time_s'] if again is not None else None,
                    'passed':released and again is not None})
        actors[key]={'timeline':timeline,'chains':chains,'passed':any(c['passed'] for c in chains),
                     'range_observation_consistent':all(r['inside_range']==r['observed'] for r in timeline)}
    return {'passed':any(a['passed'] for a in actors.values()) and all(a['range_observation_consistent'] for a in actors.values()),
            'actors':actors,'scope':'Same exogenous actor was selected, exited the finite box, lost local reference authority, reentered and was selected again; offline actor key is never fed back.'}


def event_report(records,case,detected=None,parameters=None):
    """Offline actual response; an unchanged geometric interval is not recovery."""
    records=[r for r in records if r['status']=='completed']
    actors={}
    for key in case['initial']:
        rows=[r['initial'][key] for r in records]
        if records:
            rows.append(records[-1]['steps'][key]['final'])
        start=case.get('event_start_s',0.)
        active=[s for s in rows if s['time_s']>=start]
        actors[key]={'peak_actual_speed_deviation_from_5_mps':max((abs(s['vx_mps']-5.) for s in active),default=0.),
                     'speed_range_mps':[min((s['vx_mps'] for s in rows),default=0.),max((s['vx_mps'] for s in rows),default=0.)]}
    event_peak=actors.get('event',{}).get('peak_actual_speed_deviation_from_5_mps')
    if event_peak:
        for value in actors.values():
            value['peak_ratio_to_event']=value['peak_actual_speed_deviation_from_5_mps']/event_peak
    transitions={}
    exits_and_returns=[]
    for key in case['controlled']:
        history=[]
        previous=None
        for r in records:
            m=r['decisions'][key]['memory']
            d=r['decisions'][key]['diagnostics'].get('formation',{})
            state={'state':m.get('formation_state','OFF'),'reference_present':m.get('reference_signature') is not None,
                   'reason':d.get('reason','OFF')}
            counts=len(r['inputs'][key]['observation']['neighbors'])
            signature=(json.dumps(state,sort_keys=True),counts)
            if signature!=previous:
                history.append({'time_s':r['initial'][key]['time_s'],'visible_count':counts,'formation_memory':state})
                previous=signature
        transitions[key]=history
        counts=[r['visible_count'] for r in history]
        drops=[i for i in range(1,len(counts)) if counts[i]<counts[i-1]]
        exits_and_returns.append(any(any(c>counts[i] for c in counts[i+1:]) for i in drops))
    evolution=recovery_report(detected or detection_report(records)['default'],case)
    return {'actors':actors,'local_transitions':transitions,'neighbor_count_exit_and_return':any(exits_and_returns),
            'reference_visibility':reference_visibility(records,case,parameters or KinematicModel.from_config().p),
            'evolution':evolution,
            'scope':'Actual finite-window response and visibility; no string-stability claim from peak ratios'}


def summarize_conditions(variants,event_reports):
    random_on=[v for k,v in variants.items() if k.startswith('random_') and k.endswith('_on')]
    negative=event_reports.get('nonrecovery',{}).get('evolution',{})
    return {'all_frozen_random_whole_formation':len(random_on)==6 and all(v['formation_success'] for v in random_on),
        'disturbance_lost_and_recovered':event_reports.get('disturbance',{}).get('evolution',{}).get('recovered_and_held',False),
        'reference_exit_release_reentry_reselection':event_reports.get('visibility',{}).get('reference_visibility',{}).get('passed',False),
        'nonrecovery_counterexample_retained':negative.get('loss_time_s') is not None and not negative.get('recovered_and_held',False)}


def _seal(path):
    atomic_json(path/'evidence_hashes.json',{
        f.relative_to(path).as_posix():sha256(f) for f in sorted(path.rglob('*'))
        if f.is_file() and f.name!='evidence_hashes.json'})


def run_phase5(base=None,live=True,case_names=None,sampling=True):
    run=RunRecord(base or ROOT/'results/phase5/runs',{'purpose':'Stage5 frozen development suite',
        'command_line':sys.argv,'python':sys.version,'live':live})
    variants,case_index={},{}
    try:
        with run:
            source=code_manifest()
            atomic_json(run.path/'code_hashes.json',source)
            for name in source:
                dest=run.path/'code_snapshot'/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/name,dest)
            inputs=('scenarios/cai2024/bottleneck.net.xml','docs/parameter_registry.csv',
                    'docs/phase4_completion_acceptance.md','docs/phase5_implementation_plan.md',
                    'docs/noa_staggered_formation_research_plan_2026-09-10.md')
            input_hashes={}
            for name in inputs:
                dest=run.path/'input_snapshot'/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/name,dest)
                input_hashes[name]=sha256(dest)
            atomic_json(run.path/'input_hashes.json',input_hashes)
            model,_,_=parameters(False)
            all_cases=cases(model.p)
            selected=[c for c in all_cases if case_names is None or c['name'] in case_names]
            if not selected or (case_names and set(case_names)-{c['name'] for c in all_cases}):
                raise ValueError('Unknown/empty case selection')
            atomic_json(run.path/'frozen_cases.json',selected)
            expected={c['name']+suffix:{'case_name':c['name'],'sampling':'ordinary'} for c in selected for suffix in ('_off','_on')}
            if sampling:
                expected[selected[0]['name']+'_on_half_control']={'case_name':selected[0]['name'],'sampling':'half_control'}
            case_index={'expected_variants':expected,'started_variants':[],'completed_variants':[]}
            atomic_json(run.path/'case_index.json',case_index)
            variants,comparisons={},{}
            for case in selected:
                for enabled in (False,True):
                    name=case['name']+('_on' if enabled else '_off')
                    model,p,policy=parameters(enabled)
                    case_index['started_variants'].append(name)
                    atomic_json(run.path/'case_index.json',case_index)
                    variants[name]=run_case(run.path/'cases'/name,model,p,policy,case,live=live)
                    case_index['completed_variants'].append(name)
                    atomic_json(run.path/'case_index.json',case_index)
                    atomic_json(run.path/'progress.json',{'completed_variants':list(variants),'latest':name})
                    print(json.dumps({'variant':name,'driving':variants[name]['driving_passed'],
                        'recording':variants[name]['recording_passed'],'formation':variants[name]['formation_success']}),flush=True)
            if sampling:
                case=selected[0]
                name=case['name']+'_on_half_control'
                model,p,policy=parameters(True)
                p={**p,'control_sync_dt_s':.05,'perception_dt_s':.05}
                policy={**policy,'control_sync_dt_s':.05,'perception_dt_s':.05}
                case_index['started_variants'].append(name)
                atomic_json(run.path/'case_index.json',case_index)
                variants[name]=run_case(run.path/'cases'/name,model,p,policy,case,live=live)
                case_index['completed_variants'].append(name)
                atomic_json(run.path/'case_index.json',case_index)
                load=lambda name:[json.loads(line) for line in (run.path/'cases'/name/'trace.jsonl').read_text().splitlines()]
                ordinary=load(case['name']+'_on')
                finer=load(name)
                if all(r['status']=='completed' for r in ordinary+finer):
                    comp=compare_records(ordinary,finer)
                    comp['passed']=comp['max_position_error_m']<=model.p['control_position_tolerance_m'] and comp['max_heading_error_rad']<=model.p['control_heading_tolerance_rad']
                    comparisons['control_half']=comp
                    finepath=run.path/'integration_half'
                    finepath.mkdir()
                    ordinary_p={**p,'control_sync_dt_s':.1,'perception_dt_s':.1}
                    comparisons['integration_half'],_=integration_refinement(finepath,ordinary,model,ordinary_p)
                else:
                    comparisons['sampling_failed_prefix']={'passed':False}
            atomic_json(run.path/'sampling.json',comparisons)
            random_on=[v for k,v in variants.items() if k.startswith('random_') and k.endswith('_on')]
            source_after=code_manifest()
            changed=sorted(n for n in source.keys()|source_after.keys() if source.get(n)!=source_after.get(n))
            recording=all(v['recording_passed'] for v in variants.values())
            driving=all(v['driving_passed'] and v.get('comfort_passed',False) for v in variants.values())
            event_conditions={}
            for kind in ('disturbance','visibility','nonrecovery'):
                event_path=run.path/'cases'/(kind+'_on')/'events.json'
                if event_path.is_file():
                    event_conditions[kind]=read_json(event_path)
            conditions=summarize_conditions(variants,event_conditions)
            nonvacuous=sum(v.get('isolation',{}).get('visible_neighbor_removal_changes_action',0) for v in variants.values())
            result={'passed':False,'live':live,'complete_suite':len(selected)==len(all_cases) and sampling,
                'variants':variants,'recording_passed':recording,'driving_passed':driving,
                'random_whole_formation_passed':sum(v['formation_success'] for v in random_on),
                'random_whole_formation_total':len(random_on),'sampling':comparisons,
                'scientific_conditions':conditions,'nonvacuous_action_changes':nonvacuous,
                'source_changed_during_run':changed,'next_stage_allowed':None,
                'scope':'Development facts, no traffic benefit. Phase6 requires separate acceptance review.'}
            result['engineering_passed']=live and recording and driving and not changed and nonvacuous>0 and all(c.get('passed',False) for c in comparisons.values())
            result['passed']=result['engineering_passed'] and result['complete_suite'] and all(conditions.values())
            run.finish(result)
    except BaseException as exc:
        # RunRecord records the exception first. Preserve its state, then add the
        # started-case index so completed and failed prefixes remain discoverable.
        if (run.path/'validation.json').is_file() and case_index:
            for name in case_index['started_variants']:
                validation=run.path/'cases'/name/'validation.json'
                if validation.is_file():
                    variants[name]=read_json(validation)
            failure=read_json(run.path/'validation.json')
            failure.update(variants=variants,live=live,retained_partial_package=True,
                complete_suite=False,recording_passed=False,engineering_passed=False,next_stage_allowed=None,
                case_index='case_index.json',scope='Interrupted package; only retained prefixes may be replayed. Never a complete experiment.')
            atomic_json(run.path/'validation.json',failure)
        raise
    finally:
        if run.path.exists():
            _seal(run.path)
    print(json.dumps({'path':str(run.path),'scientific_passed':result['passed'],'recording_passed':result['recording_passed']}),flush=True)
    return run.path


def run_case(path,model,p,policy,case,live=True,*,clock_schema=None,initial_memories=None,
             private_rng_provenance=None):
    from experiments.phase5_replay import replay_case
    from experiments.phase5_audit import isolation_audit
    from simulation.formation_clock import FormationClock
    path=output_path(path)
    path.mkdir(parents=True,exist_ok=False)
    atomic_json(path/'validation.json',{'passed':False,'status':'running'})
    conn,bridge,clock=None,None,None
    records=[]
    trace_count,completed_count=0,0
    meta={'case':case,'parameters':dict(p),'policy_parameters':dict(policy),'model_parameters':dict(model.p),
          'initial':case['initial'],'intervals':round(case['duration_s']/p['control_sync_dt_s']),
          'live':live,'sumo_time_offset_s':None,'execution_status':'running'}
    if clock_schema is not None:
        from simulation.r5_clock import initial_memory_hash
        meta.update(clock_schema=clock_schema,initial_memories=initial_memories,
                    initial_memories_sha256=initial_memory_hash(initial_memories),
                    private_rng_provenance=private_rng_provenance)
    atomic_json(path/'metadata.json',meta)
    failure,pending_interrupt=None,None
    try:
        if meta['intervals']<1 or not math.isclose(meta['intervals']*p['control_sync_dt_s'],case['duration_s'],abs_tol=1e-9):
            raise ValueError('Case duration must contain complete control intervals')
        road=VisibleRoad.from_net(NET)
        meta['road']=asdict(road)
        atomic_json(path/'metadata.json',meta)
        initial={k:VehicleState(**s) for k,s in case['initial'].items()}
        if clock_schema is not None:
            from simulation.r5_clock import R5Clock, validate_metadata
            clock=R5Clock(initial,model,road,p,policy,case['controlled'],case['scripts'],validate_metadata(meta))
        else:
            if p.get('r5_enabled',False) or policy.get('r5_enabled',False) or initial_memories is not None:
                raise ValueError('R5 requires explicit clock schema and sealed private initial memory')
            clock=FormationClock(initial,model,road,p,policy,case['controlled'],case['scripts'])
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
            'error':failure,'live':live,'recorded_intervals':len(records),'planned_intervals':meta['intervals'],
            'physical_sumo_advances':bridge.advances if bridge else 0}
    try:
        if trace_count:
            replay=replay_case(meta,path/'trace.jsonl')
            if clock_schema is not None:
                from experiments.phase5_r5_audit import isolation_audit as r5_isolation
                isolation=r5_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')
            else:
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
    detected=detection_report(records)
    atomic_json(path/'detection.json',detected)
    atomic_json(path/'events.json',event_report(records,case,detected['default'],p))
    result.update(formation_success=detected['default']['success'],
                  local_formation_success=detected['default']['local_success'])
    atomic_json(path/'validation.json',result)
    if pending_interrupt is not None:
        raise pending_interrupt
    return result
