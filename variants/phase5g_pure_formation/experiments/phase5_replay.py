"""Numerical stage-5 replay with explicit provenance and retained failures."""
import json
import math
from pathlib import Path
import re
from itertools import zip_longest
from experiments.phase3_replay import compare_tree
from experiments.phase4_replay import replay_readbacks
from experiments.records import RunRecord
from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.road import VisibleRoad
from simulation.noa_clock import ReplayBoundary
from research.common import ROOT, output_path, read_json, sha256, code_manifest


def rebuild_clock(metadata):
    from simulation.formation_clock import FormationClock
    model = KinematicModel(metadata['model_parameters'])
    road = VisibleRoad(tuple(tuple(tuple(point) for point in line) for line in metadata['road']['boundaries']),
                       tuple(tuple(tuple(point) for point in line) for line in metadata['road']['markings']))
    args = ({key: VehicleState(**state) for key, state in metadata['initial'].items()}, model, road,
            metadata['parameters'], metadata['policy_parameters'],
            metadata['case']['controlled'], metadata['case']['scripts'])
    if 'clock_schema' in metadata:
        from simulation.r5_clock import R5Clock, validate_metadata
        clock = R5Clock(*args, initial_memories=validate_metadata(metadata))
    else:
        if metadata['parameters'].get('r5_enabled', False) or metadata['policy_parameters'].get('r5_enabled', False):
            raise ValueError('Enabled R5 cannot be replayed without an explicit private-state schema')
        clock = FormationClock(*args)
    return model, road, clock


def replay_case(metadata, trace_path):
    errors, count, samples, maximum, completed, physical = [], 0, 0, 0., 0, 0
    failed_prefix = metadata.get('execution_status') == 'failed'
    try:
        if metadata.get('execution_status') not in ('completed', 'failed'):
            raise ValueError('Only finalized execution evidence can be replayed')
        model, road, clock = rebuild_clock(metadata)
        expected_count = metadata.get('trace_intervals', metadata['intervals']) if failed_prefix else metadata['intervals']
        if type(expected_count) is not int or not 0 < expected_count <= metadata['intervals']:
            raise ValueError('Invalid declared interval count')
        saw_failure = False
        with output_path(trace_path).open(encoding='utf-8') as handle:
            for count, line in enumerate(handle, 1):
                if count > expected_count:
                    raise ValueError('Extra trace interval beyond declared execution')
                stored = json.loads(line)
                failed_tail = failed_prefix and count == expected_count and stored['status'] == 'failed'
                boundary = (metadata.get('failure_stage'), metadata.get('failure_actor')) if failed_tail else None
                if failed_tail and not boundary[0]:
                    raise ValueError('Failed interval lacks explicit execution boundary')
                if boundary:
                    try:
                        clock.tick(stop_before=boundary)
                    except ReplayBoundary:
                        expected = clock.last_record
                        expected['error'] = metadata['failure_error']
                    else:
                        raise ValueError('Recorded failure boundary was not reached')
                else:
                    expected = clock.tick()
                if metadata['live'] and (not boundary or boundary[0] in ('synchronization', 'commit')):
                    expected['readback'] = replay_readbacks(metadata, stored, expected, model, failed_tail)
                if failed_tail:
                    saw_failure = True
                    if stored['error'] != metadata.get('failure_error'):
                        raise ValueError('Failure reason differs from preserved metadata')
                    expected.update(status='failed', error=stored['error'])
                    if metadata['live'] and boundary[0] == 'synchronization':
                        expected['readback_phase'] = metadata['failure_readback_phase']
                if metadata.get('clock_schema') == 'phase5_r5_v1':
                    from experiments.phase5_r5_replay import compare_private_record
                    compare_private_record(expected, stored)
                maximum = max(maximum, compare_tree(expected, stored, model.p['replay_absolute_tolerance'], f'interval{count}'))
                samples += sum(len(value['samples']) for value in expected.get('steps', {}).values())
                completed += stored['status'] == 'completed'
                physical += (set(stored.get('steps', {})) == set(metadata['initial']) and
                             set(stored.get('diagnostics', {})) == set(metadata['initial']))
        if count != expected_count or count < 1:
            raise ValueError(f'Truncated trace: {count}/{expected_count}')
        if failed_prefix and not saw_failure and not metadata.get('close_error'):
            raise ValueError('Failed execution lacks a failed tail or preserved close failure')
        counts = {'trace_intervals': count, 'completed_intervals': completed, 'physical_intervals': physical,
                  'recorded_intervals': physical, 'isolation_intervals': physical, 'partial_tail': count > physical}
        for name, value in counts.items():
            if name in metadata and metadata[name] != value:
                raise ValueError(f'Inconsistent {name}: {value}/{metadata[name]}')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed': not errors, 'errors': errors, 'intervals': count, 'vehicle_substeps': samples,
            'max_numeric_error': maximum, 'failed_execution_prefix': failed_prefix,
            'meaning': 'Recorded decisions, memory, physical prefix and captured SUMO reports reconstructed. Failed driving remains failed.'}


def replay_isolation(metadata, trace_path, audit_path):
    from experiments.phase5_audit import isolation_rows
    errors, count = [], 0
    try:
        report = replay_case(metadata, trace_path)
        if not report['passed']:
            raise ValueError(f'Invalid trace for isolation replay: {report["errors"]}')
        model, road, _ = rebuild_clock(metadata)
        records = [json.loads(line) for line in output_path(trace_path).read_text(encoding='utf-8').splitlines()]
        scope = metadata.get('isolation_intervals', metadata.get('recorded_intervals', len(records)))
        records = records[:scope]
        expected = isolation_rows(records, model, metadata['parameters'], metadata['policy_parameters'], road, metadata['case']['controlled'])
        with output_path(audit_path).open(encoding='utf-8') as handle:
            for count, (reference, line) in enumerate(zip_longest(expected, handle), 1):
                if reference is None or line is None:
                    raise ValueError('Truncated or extra isolation audit')
                compare_tree(reference, json.loads(line), model.p['replay_absolute_tolerance'])
                if not reference['identical']:
                    raise ValueError('Local information isolation mismatch')
        if count < 1 and records:
            raise ValueError('No isolation comparisons')
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed': not errors, 'comparisons': count, 'errors': errors}


def verify_manifest(root, hashes):
    """Validate every declared relative file; never follow a path out of root."""
    root = Path(root).resolve()
    differences = []
    if not isinstance(hashes, dict) or not hashes:
        return ['manifest missing or empty']
    for name, digest in hashes.items():
        path = (root / name).resolve()
        if (not isinstance(name, str) or Path(name).is_absolute() or not path.is_relative_to(root)
                or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                or not path.is_file() or sha256(path) != digest):
            differences.append(name)
    return differences


def replay_detection(metadata, trace_path, detection_path):
    """Recompute fixed independent 15/30 m geometry and tolerance sensitivity."""
    from experiments.phase5_detection import detect_frames
    errors = []
    try:
        rows = [json.loads(line) for line in output_path(trace_path).read_text(encoding='utf-8').splitlines()]
        rows = [row for row in rows if row['status'] == 'completed']
        frames = [{'time_s': next(iter(row['initial'].values()))['time_s'], 'states': row['initial']} for row in rows]
        if rows:
            final = {key: step['final'] for key, step in rows[-1]['steps'].items()}
            if set(final) != set(metadata['initial']):
                raise ValueError('Detector scope contains incomplete physical interval')
            frames.append({'time_s': next(iter(final.values()))['time_s'], 'states': final})
        expected = {'default': detect_frames(frames), 'sensitivity': {
            str(factor): detect_frames(frames, position_tolerance=2 * factor, speed_tolerance=factor)
            for factor in (.5, 1., 1.5)}}
        compare_tree(expected, read_json(detection_path), metadata['model_parameters']['replay_absolute_tolerance'])
        return {'passed': True, 'errors': [], 'frames': len(frames),
                'formation_success': expected['default']['success'],
                'local_formation_success': expected['default']['local_success']}
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return {'passed': False, 'errors': errors}


def _manifest_file_set(path):
    return {file.relative_to(path).as_posix() for file in path.rglob('*') if file.is_file()}


def replay_sampling(path, variants):
    """Reconstruct refinement commands, numerical differences and saved gates."""
    from experiments.phase3_audit import compare_records
    from experiments.phase3_replay import replay_motion_trace
    from experiments.offline import compare_trajectories
    from models.vehicle import Actuation, IntegratedStep
    declared = read_json(path/'sampling.json') if (path/'sampling.json').is_file() else {}
    expected, refinements = {}, []
    half = [name for name in variants if name.endswith('_half_control')]
    if len(half) > 1:
        raise ValueError('Multiple undeclared control refinements')
    source = half[0][:-len('_half_control')] if half else next(iter(variants))
    source_dir = path/'cases'/source
    metadata = read_json(source_dir/'metadata.json')
    records = [json.loads(line) for line in (source_dir/'trace.jsonl').read_text().splitlines()]
    model = KinematicModel(metadata['model_parameters'])
    p = metadata['parameters']
    if half:
        finer_meta = read_json(path/'cases'/half[0]/'metadata.json')
        expected_p = {**p, 'control_sync_dt_s': p['control_sync_dt_s']/2,
                      'perception_dt_s': p['perception_dt_s']/2}
        compare_tree(expected_p, finer_meta['parameters'], 0., 'half_control.parameters')
        expected_policy = {**metadata['policy_parameters'], 'control_sync_dt_s': expected_p['control_sync_dt_s'],
                           'perception_dt_s': expected_p['perception_dt_s']}
        compare_tree(expected_policy, finer_meta['policy_parameters'], 0., 'half_control.policy')
        compare_tree(metadata['case'], finer_meta['case'], 0., 'half_control.case')
        finer = [json.loads(line) for line in (path/'cases'/half[0]/'trace.jsonl').read_text().splitlines()]
        if all(row['status'] == 'completed' for row in records + finer):
            comparison = compare_records(records, finer)
            comparison['passed'] = (comparison['max_position_error_m'] <= model.p['control_position_tolerance_m'] and
                                    comparison['max_heading_error_rad'] <= model.p['control_heading_tolerance_rad'])
            expected['control_half'] = comparison
        else:
            expected['sampling_failed_prefix'] = {'passed': False}
    refinement = path/'integration_half'
    if refinement.is_dir():
        folders = {folder.name for folder in refinement.iterdir() if folder.is_dir()}
        if folders != set(metadata['initial']):
            raise ValueError('Integration refinement does not cover every source vehicle')
        results = []
        for key in records[0]['initial']:
            folder = refinement/key
            meta = read_json(folder/'metadata.json')
            expected_meta = {'parameters': dict(model.p), 'initial': records[0]['initial'][key],
                'dynamics_dt_s': p['dynamics_dt_s']/2, 'control_dt_s': p['control_sync_dt_s'],
                'intervals': len(records), 'purpose': 'Same commands; numerical refinement only'}
            compare_tree(expected_meta, meta, 0., 'integration_half.'+key+'.metadata')
            saved = [json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
            if len(saved) != len(records):
                raise ValueError('Integration refinement trace count differs from source')
            original, refined = [], []
            def step(raw):
                return IntegratedStep(VehicleState(**raw['initial']), VehicleState(**raw['final']),
                    Actuation(**raw['command']), tuple(VehicleState(**state) for state in raw['samples']), raw['dt_s'])
            for coarse, fine in zip(records, saved):
                compare_tree(coarse['actions'][key], fine['command'], 0., 'integration_half.'+key+'.command')
                original.append(step(coarse['steps'][key]))
                refined.append(step(fine))
            comparison = compare_trajectories(original, refined)
            report = replay_motion_trace(meta, folder/'trace.jsonl')
            result = {'vehicle': key, **comparison, 'replay': report,
                'passed': report['passed'] and comparison['max_position_error_m'] <= model.p['integration_position_tolerance_m']
                          and comparison['max_heading_error_rad'] <= model.p['integration_heading_tolerance_rad']}
            compare_tree(result, read_json(folder/'validation.json'), model.p['replay_absolute_tolerance'])
            results.append(result)
            refinements.append({'vehicle': key, **report})
        expected['integration_half'] = {'passed': all(item['passed'] for item in results), 'vehicles': results}
    compare_tree(expected, declared, model.p['replay_absolute_tolerance'], 'sampling')
    return refinements, expected


def replay_derived(metadata, folder, frozen_net, trace_report, isolation_report, detection_report):
    """Recompute event interpretation, geometry, comfort and driving gates."""
    from dataclasses import asdict
    from experiments.phase3_audit import geometry_report
    from experiments.phase4_audit import driving_metrics
    from experiments.phase5 import event_report
    from safety.geometry import RoadEnvelope
    model = KinematicModel(metadata['model_parameters'])
    tolerance = model.p['replay_absolute_tolerance']
    compare_tree(asdict(VisibleRoad.from_net(frozen_net)), metadata['road'], tolerance, 'frozen_road')
    records = [json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    physical = records[:metadata['physical_intervals']]
    events = event_report(records, metadata['case'], read_json(folder/'detection.json')['default'], metadata['parameters'])
    compare_tree(events, read_json(folder/'events.json'), tolerance, 'events')
    saved = read_json(folder/'validation.json')
    warnings = {'initialization_only': [], 'physical_or_unclassified': []}
    if metadata['live'] and (folder/'sumo.log').is_file():
        for line in (folder/'sumo.log').read_text(encoding='utf-8', errors='replace').splitlines():
            if 'Warning:' not in line and 'Error:' not in line:
                continue
            stamp = re.search(r'time=([0-9.]+)', line)
            initial = (stamp and metadata['sumo_time_offset_s'] is not None and
                       float(stamp[1].rstrip('.')) < metadata['sumo_time_offset_s']-1e-9 and 'moved by TraCI' in line)
            warnings['initialization_only' if initial else 'physical_or_unclassified'].append(line)
    compare_tree(warnings, saved['sumo_warnings'], 0., 'sumo_warnings')
    expected = {'recording_passed': trace_report['passed'] and isolation_report['passed'],
                'driving_passed': False, 'recorded_intervals': len(physical),
                'planned_intervals': metadata['intervals'], 'live': metadata['live'],
                'formation_success': detection_report['formation_success'],
                'local_formation_success': detection_report['local_formation_success']}
    iso_rows = [json.loads(line) for line in (folder/'isolation.jsonl').read_text().splitlines()]
    sensitive = sum(row['visible_removal_changes_action'] for row in iso_rows)
    if saved['isolation']['visible_neighbor_removal_changes_action'] != sensitive:
        raise ValueError('Isolation positive-control count differs')
    if saved['isolation']['comparisons'] != len(iso_rows):
        raise ValueError('Isolation comparison count differs')
    if physical:
        geometry = geometry_report(physical, model, RoadEnvelope.from_net(frozen_net))
        metrics = driving_metrics(physical, model, metadata['parameters'], metadata['case'])
        compare_tree(geometry, saved['geometry'], tolerance, 'geometry')
        compare_tree(metrics, saved['metrics'], tolerance, 'metrics')
        expected.update(comfort_passed=metrics['comfort_passed'],
            driving_passed=metadata['execution_status']=='completed' and geometry['passed'] and
            metrics['requirements_passed'] and metrics['tracking_passed'] and not warnings['physical_or_unclassified'])
    expected['passed'] = expected['recording_passed'] and expected['driving_passed'] and expected.get('comfort_passed', False)
    for key, value in expected.items():
        compare_tree(value, saved[key], tolerance, 'validation.'+key)
    return {'passed': True, 'events': events, 'nonvacuous_action_changes': sensitive, 'facts': expected}


def replay_run(run_dir, base=None):
    """Reject altered source/evidence and recompute each explicitly named run.

    A matching source checkout is required. An older snapshot may be restored
    into a separate workspace by the caller; this function never overwrites the
    active workspace and never follows a mutable latest-run pointer.
    """
    if run_dir is None:
        raise ValueError('An explicit phase5 source run directory is required')
    path = output_path(run_dir)
    destination = output_path(base or ROOT/'results/phase5/replays')
    if destination.is_relative_to(path):
        raise ValueError('Replay output must be outside the sealed source run')
    result = {'passed': False, 'source_run': str(path), 'source_run_id': path.name,
              'source_driving_gate_passed': False, 'errors': [], 'cases': [],
              'evidence_hash_mismatches': [], 'code_snapshot_mismatches': [],
              'input_snapshot_mismatches': [], 'changed_current_source_files': [],
              'meaning': 'Numerical reconstruction and captured SUMO report checks; scientific and driving failures remain unchanged. SUMO is not restarted.',
              'source_restore_entry': str(path/'code_snapshot')}
    with RunRecord(destination, {'purpose': 'Independent phase5 replay', 'source_run': str(path)}) as replay:
        try:
            gate = read_json(path/'validation.json')
            if read_json(path/'metadata.json').get('clock_schema') == 'phase5_r5_v1':
                raise ValueError('R5 whole packages require the explicit phase5-r5-replay entry')
            if gate.get('status') not in ('completed', 'failed'):
                raise ValueError('Source run has not finalized')
            result['source_driving_gate_passed'] = gate.get('driving_passed', gate.get('passed', False))
            hashes = read_json(path/'evidence_hashes.json')
            actual_files = {name for name in _manifest_file_set(path) if Path(name).name != 'evidence_hashes.json'}
            result['evidence_hash_mismatches'] = sorted(set(verify_manifest(path, hashes)) |
                (actual_files ^ set(hashes)))
            code_hashes = read_json(path/'code_hashes.json')
            input_hashes = read_json(path/'input_hashes.json')
            result['code_snapshot_mismatches'] = sorted(set(verify_manifest(path/'code_snapshot', code_hashes)) |
                (_manifest_file_set(path/'code_snapshot') ^ set(code_hashes)))
            result['input_snapshot_mismatches'] = sorted(set(verify_manifest(path/'input_snapshot', input_hashes)) |
                (_manifest_file_set(path/'input_snapshot') ^ set(input_hashes)))
            current = code_manifest()
            result['changed_current_source_files'] = sorted(name for name in current.keys() | code_hashes.keys()
                if current.get(name) != code_hashes.get(name))
            if any(result[name] for name in ('evidence_hash_mismatches', 'code_snapshot_mismatches',
                                            'input_snapshot_mismatches', 'changed_current_source_files')):
                raise ValueError('Source or evidence manifest differs; numerical replay refused')
            frozen = read_json(path/'frozen_cases.json')
            if not isinstance(frozen, list) or not frozen or len({case['name'] for case in frozen}) != len(frozen):
                raise ValueError('Missing or duplicate frozen cases')
            variants = gate['variants']
            if not isinstance(variants, dict) or not variants:
                raise ValueError('No declared variant evidence')
            folders = {folder.name for folder in (path/'cases').iterdir() if folder.is_dir()}
            if folders != set(variants):
                raise ValueError('Case folders differ from declared variants')
            required = {case['name'] + suffix for case in frozen for suffix in ('_off', '_on')}
            optional = {frozen[0]['name'] + '_on_half_control'}
            partial = gate.get('retained_partial_package', False)
            index = read_json(path/'case_index.json')
            planned = index['expected_variants']
            if not required <= set(planned) or set(planned) - required - optional:
                raise ValueError('Case index does not cover the frozen on/off and optional sampling plan')
            for name, entry in planned.items():
                case_name = name[:-len('_on_half_control')] if name.endswith('_on_half_control') else name.rsplit('_', 1)[0]
                compare_tree({'case_name': case_name, 'sampling': 'half_control' if name.endswith('_half_control') else 'ordinary'}, entry, 0., 'case_index.'+name)
            started, completed = index['started_variants'], index['completed_variants']
            if (len(started) != len(set(started)) or len(completed) != len(set(completed)) or
                    started != list(planned)[:len(started)] or completed != started[:len(completed)] or
                    set(started) != set(variants)):
                raise ValueError('Started/completed case index differs from retained evidence')
            if not partial and (not required <= set(variants) or set(variants) != set(planned) or completed != started):
                raise ValueError('Frozen cases do not have exactly the declared on/off and optional sampling coverage')
            if partial and (gate['status'] != 'failed' or gate['complete_suite'] or gate['passed'] or gate['engineering_passed']):
                raise ValueError('Interrupted package cannot claim completed scientific or engineering success')
            result.update(partial_source_package=partial, unstarted_variants=[name for name in planned if name not in started])
            event_reports, nonvacuous = {}, 0
            frozen_net = path/'input_snapshot/scenarios/cai2024/bottleneck.net.xml'
            from experiments.phase5 import parameters, cases as configured_cases
            for name, preserved in variants.items():
                if not re.fullmatch('[A-Za-z0-9_-]+', name):
                    raise ValueError('Invalid variant directory name')
                folder = path/'cases'/name
                metadata = read_json(folder/'metadata.json')
                compare_tree(planned[name]['case_name'], metadata['case']['name'], 0., name+'.indexed_case')
                enabled = name.endswith('_on') or name.endswith('_on_half_control')
                fixed_model, fixed_p, fixed_policy = parameters(enabled)
                if name.endswith('_half_control'):
                    fixed_p.update(control_sync_dt_s=.05, perception_dt_s=.05)
                    fixed_policy.update(control_sync_dt_s=.05, perception_dt_s=.05)
                for key, expected_value in (('model_parameters', dict(fixed_model.p)), ('parameters', fixed_p), ('policy_parameters', fixed_policy)):
                    compare_tree(expected_value, metadata[key], 0., name+'.frozen_'+key)
                compare_tree(gate['live'], metadata['live'], 0., name+'.live')
                matching = [case for case in frozen if case['name'] == metadata['case']['name']]
                if len(matching) != 1:
                    raise ValueError(f'{name}: no unique frozen case')
                compare_tree(matching[0], metadata['case'], 0., name+'.frozen_case')
                planned_intervals = round(matching[0]['duration_s']/fixed_p['control_sync_dt_s'])
                if not math.isclose(planned_intervals*fixed_p['control_sync_dt_s'], matching[0]['duration_s'], abs_tol=1e-9, rel_tol=0.):
                    raise ValueError('Frozen case duration does not contain complete control intervals')
                compare_tree(planned_intervals, metadata['intervals'], 0., name+'.intervals')
                compare_tree(metadata['case']['initial'], metadata['initial'], 0., name+'.initial')
                compare_tree(preserved, read_json(folder/'validation.json'), 0., name+'.validation')
                if metadata['execution_status'] == 'failed' and preserved.get('status') != 'failed':
                    raise ValueError(f'{name}: failed execution was relabeled')
                trace = replay_case(metadata, folder/'trace.jsonl')
                isolation = replay_isolation(metadata, folder/'trace.jsonl', folder/'isolation.jsonl')
                detection = replay_detection(metadata, folder/'trace.jsonl', folder/'detection.json')
                if detection['passed']:
                    for key in ('formation_success', 'local_formation_success'):
                        if preserved.get(key) != detection[key]:
                            detection['passed'] = False
                            detection['errors'].append('Preserved '+key+' disagrees with independent geometry')
                derived = {'passed': False, 'errors': ['Trace, isolation or detection did not reconstruct']}
                if trace['passed'] and isolation['passed'] and detection['passed']:
                    try:
                        derived = replay_derived(metadata, folder, frozen_net, trace, isolation, detection)
                        nonvacuous += derived['nonvacuous_action_changes']
                        if name.endswith('_on'):
                            event_reports[metadata['case']['kind']] = derived['events']
                    except Exception as exc:
                        derived = {'passed': False, 'errors': [f'{type(exc).__name__}: {exc}']}
                result['cases'].append({'case': name, 'trace': trace, 'isolation': isolation, 'detection': detection,
                    'derived': derived,
                    'source_driving_passed': preserved.get('driving_passed', False),
                    'passed': trace['passed'] and isolation['passed'] and detection['passed'] and derived['passed']})
            result['integration_refinements'], result['sampling'] = ([], {}) if partial else replay_sampling(path, variants)
            from experiments.phase5 import summarize_conditions
            conditions = summarize_conditions(variants, event_reports)
            recording = all(value['recording_passed'] for value in variants.values())
            driving = all(value['driving_passed'] and value.get('comfort_passed', False) for value in variants.values())
            if not partial:
                compare_tree(conditions, gate['scientific_conditions'], 0., 'scientific_conditions')
                compare_tree(result['sampling'], gate['sampling'], 0., 'top.sampling')
                complete_suite = ({case['name'] for case in frozen} == {case['name'] for case in configured_cases(fixed_model.p)} and
                                  bool(set(variants) & optional))
                engineering = (gate['live'] and recording and driving and not gate['source_changed_during_run'] and
                               nonvacuous > 0 and all(value.get('passed', False) for value in result['sampling'].values()))
                random_on = [value for name, value in variants.items() if name.startswith('random_') and name.endswith('_on')]
                for key, value in {'recording_passed': recording, 'driving_passed': driving,
                    'nonvacuous_action_changes': nonvacuous, 'engineering_passed': engineering, 'complete_suite': complete_suite,
                    'random_whole_formation_total': len(random_on), 'random_whole_formation_passed': sum(value['formation_success'] for value in random_on),
                    'passed': engineering and complete_suite and all(conditions.values())}.items():
                    compare_tree(value, gate[key], 0., 'top.'+key)
            result['scientific_conditions'] = conditions
            result['passed'] = (bool(result['cases']) and all(case['passed'] for case in result['cases'])
                                and all(item['passed'] for item in result['integration_refinements']))
        except Exception as exc:
            result['errors'].append(f'{type(exc).__name__}: {exc}')
        replay.finish(result)
    print(json.dumps({'path': str(replay.path), 'passed': result['passed'], 'source_run': str(path)}), flush=True)
    if not result['passed']:
        raise RuntimeError(f'Phase5 replay failed; retained at {replay.path}')
    return result
