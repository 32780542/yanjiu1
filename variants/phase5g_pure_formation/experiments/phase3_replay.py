"""Reconstruct local sensing/history/actions and continuous state, not just poses."""
from dataclasses import asdict
import json
import math
from pathlib import Path
from experiments.records import RunRecord, atomic_json
from models.vehicle import VehicleModel, VehicleState
from models.kinematic import model_from_parameters
from perception.road import VisibleRoad
from research.common import ROOT, output_path, read_json, sha256, code_manifest
from simulation.multi_vehicle import MultiVehicleClock
from simulation.external_bridge import audit_readback


def compare_tree(expected, actual, tolerance, name='root'):
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or expected.keys() != actual.keys():
            raise ValueError(f'{name}: fields differ')
        return max((compare_tree(v,actual[k],tolerance,name+'.'+k) for k,v in expected.items()),default=0.)
    if isinstance(expected,(tuple,list)):
        if not isinstance(actual,(tuple,list)) or len(expected) != len(actual):
            raise ValueError(f'{name}: sequence count differs')
        return max((compare_tree(a,b,tolerance,f'{name}[{i}]') for i,(a,b) in enumerate(zip(expected,actual))),default=0.)
    if isinstance(expected,bool) or expected is None or isinstance(expected,str):
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError(f'{name}: value differs')
        return 0.
    if isinstance(expected,int):
        if type(actual) is not int or actual != expected:
            raise ValueError(f'{name}: discrete value differs')
        return 0.
    if type(actual) not in (float,int) or not math.isfinite(actual) or abs(expected-actual) > tolerance:
        raise ValueError(f'{name}: numeric value differs')
    return abs(expected-actual)


def replay_case(metadata, trace_path):
    count, vehicles, samples, maximum, errors = 0,0,0,0.,[]
    try:
        model = model_from_parameters(metadata['model_parameters'])
        p = metadata['parameters']
        road = VisibleRoad(tuple(tuple(tuple(p) for p in line) for line in metadata['road']['boundaries']),
                           tuple(tuple(tuple(p) for p in line) for line in metadata['road']['markings']))
        initial = {k:VehicleState(**v) for k,v in metadata['initial'].items()}
        clock = MultiVehicleClock(initial,model,road,p)
        tol = model.p['replay_absolute_tolerance']
        with output_path(trace_path).open(encoding='utf-8') as handle:
            for count,line in enumerate(handle,1):
                stored = json.loads(line)
                expected = clock.tick()
                if metadata['live']:
                    if not isinstance(stored['readback'],dict) or set(stored['readback']) != set(initial):
                        raise ValueError('Missing live readback')
                    rebuilt = {}
                    raw_fields = ('sumo_time_s','front_x_m','front_y_m','angle_deg','speed_mps','acceleration_mps2',
                                  'edge_id','lane_id','lane_index','colliding_vehicle_reports','teleport_starts')
                    for key in initial:
                        raw = {k:stored['readback'][key][k] for k in raw_fields}
                        final = VehicleState(**expected['steps'][key]['final'])
                        previous = VehicleState(**expected['initial'][key])
                        accel = (model.observe(final)['speed_mps']-model.observe(previous)['speed_mps'])/p['control_sync_dt_s']
                        report = audit_readback(raw,final,model,metadata['sumo_time_offset_s'],accel)
                        if not report['passed'] or raw['colliding_vehicle_reports'] or raw['teleport_starts']:
                            raise ValueError('Live readback physical inconsistency')
                        rebuilt[key] = report
                    expected['readback'] = rebuilt
                maximum = max(maximum,compare_tree(expected,stored,tol,f'interval[{count}]'))
                vehicles += len(initial)
                samples += sum(len(v['samples']) for v in expected['steps'].values())
        if count != metadata['intervals'] or count < 1:
            raise ValueError(f'Incomplete intervals: {count}, expected {metadata["intervals"]}')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed':not errors,'errors':errors,'intervals':count,'vehicle_intervals':vehicles,
            'vehicle_substeps':samples,'max_numeric_error':maximum}


def replay_isolation(metadata, trace_path, audit_path):
    """Re-run saved counterfactual frames with separate per-ego local memories."""
    from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
    from perception.probe import probe_action
    count, errors, maximum = 0,[],0.
    try:
        p = metadata['parameters']
        road = VisibleRoad(tuple(tuple(tuple(p) for p in line) for line in metadata['road']['boundaries']),
                           tuple(tuple(tuple(p) for p in line) for line in metadata['road']['markings']))
        reference = [json.loads(line) for line in output_path(trace_path).read_text().splitlines()]
        kinds = ('identity_order','hidden_type','future_plan','outside_state')
        sensors = {(key,kind):IdealSensor(p,road) for key in metadata['initial'] for kind in kinds}
        expected_keys = [(i,key,kind) for i in range(metadata['intervals']) for key in sorted(metadata['initial']) for kind in kinds]
        with output_path(audit_path).open(encoding='utf-8') as handle:
            for count,line in enumerate(handle,1):
                row = json.loads(line)
                i,key,kind = row['interval'],row['ego'],row['mutation']
                if count > len(expected_keys) or (i,key,kind) != expected_keys[count-1]:
                    raise ValueError('Missing, duplicated or reordered mutation audit row')
                frame = WorldFrame(tuple(TruthVehicle(**{**v,'state':VehicleState(**v['state']),
                                                         'future_plan':tuple(v['future_plan'])}) for v in row['mutated_frame']))
                ego_key = 'renamed_'+str(len(key))+key[::-1] if kind=='identity_order' else key
                inp = sensors[key,kind].sample(ego_key,frame)
                action = asdict(probe_action(inp,p))
                expected = {'interval':i,'ego':key,'mutation':kind,'mutated_frame':row['mutated_frame'],
                            'input':asdict(inp),'action':action,'identical':True}
                maximum = max(maximum,compare_tree(expected,row,p['replay_absolute_tolerance']))
                compare_tree(asdict(inp),reference[i]['inputs'][key],p['replay_absolute_tolerance'])
                compare_tree(action,reference[i]['actions'][key],p['replay_absolute_tolerance'])
        if count != len(expected_keys) or not count:
            raise ValueError('Truncated mutation audit')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed':not errors,'errors':errors,'comparisons':count,'max_numeric_error':maximum}


def replay_motion_trace(metadata,path):
    from models.vehicle import Actuation
    count,samples,maximum,errors = 0,0,0.,[]
    try:
        model = model_from_parameters(metadata['parameters'])
        current = VehicleState(**metadata['initial'])
        for count,line in enumerate(output_path(path).read_text().splitlines(),1):
            stored = json.loads(line)
            action = Actuation(**stored['command'])
            if metadata.get('command_mode') == 'own_bezier_reference':
                from models.bezier import QuadraticLaneChange,bezier_command
                expected_action = bezier_command(current,QuadraticLaneChange(**metadata['reference']),model.p)
                compare_tree(asdict(expected_action),stored['command'],model.p['replay_absolute_tolerance'])
            step = model.advance(current,action,metadata['control_dt_s'],metadata['dynamics_dt_s'])
            expected = {**asdict(step),'diagnostics':[model.observe(s) for s in step.samples]}
            maximum = max(maximum,compare_tree(expected,stored,model.p['replay_absolute_tolerance']))
            current = step.final
            samples += len(step.samples)
        if count != metadata['intervals'] or count < 1:
            raise ValueError('Incomplete motion trace')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed':not errors,'errors':errors,'checked_samples':samples,'max_state_error':maximum}


def replay_run(run_dir=None,base=None):
    with RunRecord(base or ROOT/'results/phase3/replays',{'purpose':'Independent phase3 numerical replay','source_run':str(run_dir)}) as run:
        path = output_path(run_dir or read_json('results/phase3/runs/latest.json')['path'])
        source = read_json(path/'metadata.json')
        gate = read_json(path/'validation.json')
        hashes = read_json(path/'evidence_hashes.json')
        mismatches = [k for k,v in hashes.items() if not output_path(path/k).is_file() or sha256(path/k) != v]
        current = code_manifest()
        changed = [k for k,v in source['code_and_config_hashes'].items() if current.get(k) != v]
        results = []
        for relative in source['case_trace_directories']:
            sub = output_path(path/relative)
            meta = read_json(sub/'metadata.json')
            r = replay_case(meta,sub/'trace.jsonl')
            isolation = replay_isolation(meta,sub/'trace.jsonl',sub/'isolation.jsonl')
            results.append({'case':relative,**r,'isolation':isolation,'passed':r['passed'] and isolation['passed']})
        refined = []
        for relative in source['integration_trace_directories']:
            sub = output_path(path/relative)
            refined.append({'case':relative,**replay_motion_trace(read_json(sub/'metadata.json'),sub/'trace.jsonl')})
        from experiments.phase3_faults import replay_faults
        faults = replay_faults(path/'faults') if (path/'faults/validation.json').is_file() else None
        motion = [{'case':relative,**replay_motion_trace(read_json(path/relative/'metadata.json'),path/relative/'trace.jsonl')}
                  for relative in source.get('motion_trace_directories',[])]
        result = {'passed':bool(results) and not mismatches and all(r['passed'] for r in results+refined)
                  and gate['status']=='completed' and (faults is None or faults['passed']) and all(r['passed'] for r in motion),
                  'source_run_id':gate['run_id'],'source_gate_passed':gate['passed'],
                  'evidence_hash_mismatches':mismatches,'changed_current_source_files':changed,
                  'cases':results,'integration_refinements':refined,'faults':faults,'simplified_motion':motion,
                  'meaning':'Recomputed local inputs/actions and dynamics; original SUMO evidence audited, SUMO not restarted'}
        run.finish(result)
    print(json.dumps(result),flush=True)
    if not result['passed']:
        raise RuntimeError(f'Phase3 replay failed; retained at {run.path}')
    return result
