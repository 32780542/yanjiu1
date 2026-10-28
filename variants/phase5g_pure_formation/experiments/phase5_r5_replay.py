"""Explicit R5 replay entry; private random state is rebuilt from sealed initial memory."""
import json
import math
from pathlib import Path
import shutil
import sys

from experiments.phase3_replay import compare_tree
from experiments.phase5_replay import replay_case as phase5_replay_case
from experiments.phase5_replay import verify_manifest, _manifest_file_set, replay_detection, replay_derived, replay_sampling
from experiments.records import RunRecord, atomic_json
from research.common import ROOT, output_path, read_json, sha256, code_manifest
from simulation.r5_clock import CLOCK_SCHEMA, validate_metadata


def _exact_private(expected, actual, name):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            raise ValueError(name+': private fields differ')
        for key, value in expected.items():
            _exact_private(value, actual[key], name+'.'+key)
    elif isinstance(expected, (tuple, list)):
        if not isinstance(actual, (tuple, list)) or len(expected) != len(actual):
            raise ValueError(name+': private sequence differs')
        for index, (left, right) in enumerate(zip(expected, actual)):
            _exact_private(left, right, name+f'[{index}]')
    elif type(expected) is float:
        if type(actual) is not float or expected.hex() != actual.hex():
            raise ValueError(name+': private floating-point value is not bit-exact')
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError(name+': private discrete value differs')


def compare_private_record(expected, actual):
    """PRNG outputs and timer latch are exact; physical signatures keep the model tolerance."""
    for section in ('inputs', 'decisions'):
        for key, entry in expected.get(section, {}).items():
            memory = entry['memory']
            for field in ('r5_rng_state', 'r5_draw_count', 'r5_phase', 'r5_deadline_s',
                          'r5_clear_since_s', 'r5_last_time_s'):
                _exact_private(memory[field], actual[section][key]['memory'][field], section+'.'+key+'.'+field)
            if section == 'decisions' and 'r5' in entry['diagnostics']:
                detail = entry['diagnostics']['r5']
                actual_detail = actual[section][key]['diagnostics']['r5']
                if ('waiting_game' in detail) != ('waiting_game' in actual_detail):
                    raise ValueError(section+'.'+key+'.r5.waiting_game presence differs')
                if 'waiting_game' in detail:
                    _exact_private(detail['waiting_game'], actual_detail['waiting_game'],
                                   section+'.'+key+'.r5.waiting_game')
                for field in ('deadline_s', 'draw_count', 'draws_this_tick', 'draws'):
                    if field in detail:
                        _exact_private(detail[field], actual[section][key]['diagnostics']['r5'][field],
                                       section+'.'+key+'.r5.'+field)


def replay_case(metadata, trace_path):
    try:
        validate_metadata(metadata)
    except Exception as exc:
        return {'passed': False, 'errors': [f'{type(exc).__name__}: {exc}'],
                'intervals': 0, 'vehicle_substeps': 0, 'max_numeric_error': 0.,
                'failed_execution_prefix': metadata.get('execution_status') == 'failed'}
    return phase5_replay_case(metadata, trace_path)


def _source_state(source):
    from experiments.phase5_r5 import INPUTS, input_changes
    hashes = read_json(source/'evidence_hashes.json')
    files = {name for name in _manifest_file_set(source) if Path(name).name != 'evidence_hashes.json'}
    if verify_manifest(source, hashes) or files != set(hashes):
        raise ValueError('Source evidence manifest/file set differs')
    code, inputs = read_json(source/'code_hashes.json'), read_json(source/'input_hashes.json')
    for name, mapping in (('code_snapshot', code), ('input_snapshot', inputs)):
        if verify_manifest(source/name, mapping) or _manifest_file_set(source/name) != set(mapping):
            raise ValueError(name+' manifest/file set differs')
    current = code_manifest()
    changed = sorted(name for name in set(current)|set(code) if current.get(name) != code.get(name))
    if changed:
        raise ValueError(f'Current source differs from sealed source: {changed}; restore code_snapshot into a separate workspace')
    changed_inputs = input_changes(inputs)
    if changed_inputs:
        raise ValueError(f'Current required inputs differ from sealed input snapshot: {changed_inputs}')
    return {'evidence_manifest_sha256': sha256(source/'evidence_hashes.json'),
            'code_manifest_sha256': sha256(source/'code_hashes.json'),
            'input_manifest_sha256': sha256(source/'input_hashes.json'),
            'source_validation_sha256': sha256(source/'validation.json'),
            'code_hashes': code, 'input_hashes': inputs, 'current_code_hashes': current,
            'current_required_input_hashes': {name: sha256(ROOT/name) for name in INPUTS},
            'evidence_file_count': len(hashes)}


def replay_run(run_dir, base=None):
    from experiments.phase5 import _seal
    from experiments.phase5_r5 import (INPUTS, parameters, expected_variants, mechanism_report,
                                       mechanism_summary, summarize_run, summarize_partial, paired_action_report)
    from experiments.phase5c_cases import load_frozen_cases
    from experiments.phase5_r5_audit import replay_isolation
    if run_dir is None:
        raise ValueError('R5 replay requires an explicit source run; latest is not evidence')
    source = output_path(run_dir)
    destination = output_path(base or ROOT/'results/phase5_r5/replays')
    if destination.is_relative_to(source):
        raise ValueError('Replay output must be outside the sealed source')
    result = {'passed': False, 'source_run': str(source), 'source_run_id': source.name,
              'clock_schema': CLOCK_SCHEMA, 'errors': [], 'cases': [],
              'source_restore_entry': str(source/'code_snapshot'),
              'scope': 'Independent private-state, action, physical-prefix and captured SUMO reconstruction; '
                       'physical failures and unobserved mechanisms remain failures or unobserved.'}
    replay = RunRecord(destination, {'purpose': 'Independent R5 replay', 'clock_schema': CLOCK_SCHEMA,
                       'source_run': str(source), 'command_line': sys.argv, 'python': sys.version})
    try:
        with replay:
            shutil.copy2(Path(__file__), replay.path/'replay_script_snapshot.py')
            try:
                result['source_before'] = _source_state(source)
                gate, source_meta = read_json(source/'validation.json'), read_json(source/'metadata.json')
                if source_meta.get('purpose') != 'Independent R5 mechanism suite' or source_meta.get('clock_schema') != CLOCK_SCHEMA:
                    raise ValueError('Source is not an explicitly versioned R5 mechanism suite')
                if gate.get('status') not in ('completed', 'failed'):
                    raise ValueError('Source execution has not finalized')
                if type(source_meta.get('live')) is not bool or type(source_meta.get('sampling_enabled')) is not bool:
                    raise ValueError('R5 source live/sampling flags must be booleans')
                if set(result['source_before']['input_hashes']) != set(INPUTS)|{'frozen_r5_cases.json'}:
                    raise ValueError('R5 required frozen input set differs')
                frozen_file = source/'input_snapshot/frozen_r5_cases.json'
                if sha256(frozen_file) != source_meta['case_file_sha256']:
                    raise ValueError('Explicit initial case file binding differs')
                fixed_model, _, _ = parameters(False)
                cases = load_frozen_cases(frozen_file, dict(fixed_model.p),
                    parent_file=source/'input_snapshot/parent_frozen_r5_cases.json')
                compare_tree(cases, read_json(source/'frozen_cases.json'), 0., 'frozen_cases')
                by_name = {case['name']: case for case in cases}
                waiting_policy = source_meta['waiting_policy']
                lane_change_policy = source_meta.get('lane_change_policy','fixed')
                expected = (expected_variants(cases, source_meta['sampling_enabled'])
                    if waiting_policy == 'fixed' and lane_change_policy == 'fixed'
                    else expected_variants(cases, source_meta['sampling_enabled'],
                        waiting_policy=waiting_policy, lane_change_policy=lane_change_policy))
                index = read_json(source/'case_index.json')
                compare_tree(expected, index['expected_variants'], 0., 'expected_variants')
                started, finalized, completed = (index[key] for key in
                    ('started_variants', 'finalized_variants', 'completed_variants'))
                if any(not isinstance(value, list) or len(value) != len(set(value)) for value in (started, finalized, completed)):
                    raise ValueError('Invalid/duplicate R5 attempt index')
                if started != list(expected)[:len(started)] or finalized != started:
                    raise ValueError('R5 started/finalized attempts are not the declared execution prefix')
                variants = gate['variants']
                if set(variants) != set(started) or not variants:
                    raise ValueError('Declared variants differ from finalized attempted cases')
                folders = {folder.name for folder in (source/'cases').iterdir() if folder.is_dir()}
                if folders != set(variants):
                    raise ValueError('Case directory coverage differs')
                partial = bool(gate.get('retained_partial_package', False))
                if partial:
                    if gate['status'] != 'failed' or gate.get('passed') or gate.get('engineering_passed'):
                        raise ValueError('Interrupted R5 package cannot claim completed engineering')
                elif set(started) != set(expected):
                    raise ValueError('Unattempted declared R5 cases were omitted')
                completed_actual = []
                for name in started:
                    spec, folder = expected[name], source/'cases'/name
                    metadata, saved = read_json(folder/'metadata.json'), read_json(folder/'validation.json')
                    compare_tree(saved, variants[name], 0., name+'.top_variant')
                    model, p, policy = parameters(spec['r5_enabled'],
                        lane_priority=spec.get('lane_priority_enabled', True),
                        waiting_policy=spec.get('waiting_policy', 'fixed'),
                        lane_change_policy=spec.get('lane_change_policy', 'fixed'))
                    if spec['sampling'] == 'half_control':
                        p = {**p, 'control_sync_dt_s': p['control_sync_dt_s']/2, 'perception_dt_s': p['perception_dt_s']/2}
                        policy = {**policy, 'control_sync_dt_s': p['control_sync_dt_s'], 'perception_dt_s': p['perception_dt_s']}
                    case = by_name[spec['case_name']]
                    for key, value in (('case', case), ('initial', case['initial']), ('parameters', p),
                                       ('policy_parameters', policy), ('model_parameters', dict(model.p)),
                                       ('live', source_meta['live']), ('clock_schema', CLOCK_SCHEMA)):
                        compare_tree(value, metadata[key], 0., name+'.'+key)
                    validate_metadata(metadata)
                    intervals = round(case['duration_s']/p['control_sync_dt_s'])
                    if type(metadata['intervals']) is not int or metadata['intervals'] != intervals or not math.isclose(
                            intervals*p['control_sync_dt_s'], case['duration_s'], abs_tol=1e-9, rel_tol=0.):
                        raise ValueError(name+': interval coverage differs from frozen duration')
                    if metadata['execution_status'] == 'completed':
                        completed_actual.append(name)
                    elif metadata['execution_status'] != 'failed':
                        raise ValueError(name+': unfinished case evidence')
                    trace = replay_case(metadata, folder/'trace.jsonl')
                    isolation = replay_isolation(metadata, folder/'trace.jsonl', folder/'isolation.jsonl')
                    detection = replay_detection(metadata, folder/'trace.jsonl', folder/'detection.json')
                    if not all(report['passed'] for report in (trace, isolation, detection)):
                        result['cases'].append({'case': name, 'passed': False, 'trace': trace,
                                                'isolation': isolation, 'detection': detection})
                        raise ValueError(name+': trace/isolation/detection reconstruction failed')
                    for key in ('passed', 'comparisons', 'visible_neighbor_removal_changes_action',
                                'visible_neighbor_removal_changes_r5_gate',
                                'visible_neighbor_removal_changes_private_random', 'sample_stride_intervals'):
                        compare_tree(isolation[key], saved['isolation'][key], 0., name+'.isolation.'+key)
                    derived = replay_derived(metadata, folder, source/'input_snapshot/scenarios/cai2024/bottleneck.net.xml',
                                             trace, isolation, detection)
                    records = [json.loads(line) for line in (folder/'trace.jsonl').read_text(encoding='utf-8').splitlines()]
                    mechanism = mechanism_report(records, case, policy)
                    compare_tree(mechanism, read_json(folder/'r5_events.json'), 0., name+'.r5_events')
                    compare_tree(mechanism_summary(mechanism), saved['r5_mechanism'], 0., name+'.r5_summary')
                    result['cases'].append({'case': name, 'passed': True, 'trace': trace, 'isolation': isolation,
                                            'detection': detection, 'derived': derived, 'mechanism': saved['r5_mechanism'],
                                            'source_execution_status': metadata['execution_status']})
                compare_tree(completed_actual, completed, 0., 'completed_variant_index')
                # A partial label never skips numerical evidence that has already been recorded.
                # Incomplete refinement artifacts that cannot reconstruct cause a replay failure;
                # the independently verified vehicle prefixes remain in this report.
                result['integration_refinements'], sampling = replay_sampling(source, variants)
                pairs = paired_action_report(source, cases)
                compare_tree(pairs, read_json(source/'paired_actions.json'), 0., 'paired_actions')
                if not partial:
                    if source_meta['sampling_enabled'] and all(v['status'] == 'completed' for v in variants.values()):
                        if set(sampling) != {'control_half', 'integration_half'}:
                            raise ValueError('Required numerical refinements are absent')
                    elif not source_meta['sampling_enabled'] and sampling:
                        raise ValueError('Undeclared numerical refinements')
                    expected_top = summarize_run(variants, index, sampling, source_meta['live'], [], pairs)
                    for key, value in expected_top.items():
                        compare_tree(value, gate[key], 0., 'top.'+key)
                else:
                    expected_top = summarize_partial(variants, index, sampling, source_meta['live'], [], pairs)
                    for key, value in expected_top.items():
                        compare_tree(value, gate[key], 0., 'partial_top.'+key)
                result.update(partial_source_package=partial,
                    unstarted_variants=[name for name in expected if name not in started],
                    source_engineering_passed=expected_top['engineering_passed'],
                    source_driving_passed=expected_top['driving_passed'],
                    source_scientific_passed=expected_top['scientific_passed'])
                result['source_after'] = _source_state(source)
                compare_tree(result['source_before'], result['source_after'], 0., 'source_before_after')
                result['passed'] = bool(result['cases']) and all(c['passed'] for c in result['cases'])
            except Exception as exc:
                result['errors'].append(f'{type(exc).__name__}: {exc}')
            replay.finish(result)
    finally:
        if replay.path.exists():
            _seal(replay.path)
    result['path'] = str(replay.path)
    print(json.dumps({'path': str(replay.path), 'passed': result['passed'], 'source_run': str(source),
                      'errors': result['errors']}), flush=True)
    return result
