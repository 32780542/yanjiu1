"""Independent R5 mechanism runs; implementation, observations and driving remain separate."""
from collections import Counter
import json
import math
from pathlib import Path
import shutil
import sys

from experiments.phase5 import parameters as formation_parameters
from experiments.records import RunRecord, atomic_json
from research.common import ROOT, output_path, settings, read_json, code_manifest, sha256
from simulation.r5_clock import CLOCK_SCHEMA

INPUTS = ('scenarios/cai2024/bottleneck.net.xml', 'docs/parameter_registry.csv',
          'docs/phase4_completion_acceptance.md', 'docs/phase5_implementation_plan.md',
          'docs/noa_staggered_formation_research_plan_2026-09-10.md',
          'docs/phase5_r5_completion_plan.md',
          'docs/phase5b_conservative_release_plan.md',
          'docs/phase5c_lane_priority_plan.md', 'parent_frozen_r5_cases.json',
          'docs/phase5d_local_game_plan.md', 'docs/phase5e_exact_endpoint_plan.md',
          'configs/phase5f.json', 'docs/phase5f_adaptive_duration_plan.md',
          'docs/superpowers/specs/2026-09-13-phase5f-adaptive-duration-design.md',
          'docs/superpowers/plans/2026-09-13-phase5f-adaptive-duration.md')


def _lane_change_parameters(mode):
    if mode not in ('fixed','adaptive_duration'):
        raise ValueError('Unknown Phase 5F lane-change policy')
    return settings('phase5f') if mode=='adaptive_duration' else {}


def parameters(enabled, lane_priority=True, waiting_policy='fixed', lane_change_policy='fixed'):
    from noa.waiting_game import waiting_parameters
    game = waiting_parameters(waiting_policy)
    adaptive = _lane_change_parameters(lane_change_policy)
    if type(lane_priority) is not bool:
        raise ValueError('r5_lane_priority_enabled must be bool')
    model, p, policy = formation_parameters(True)
    values = settings('phase5_r5')
    p.update(values, r5_enabled=enabled, r5_lane_priority_enabled=lane_priority)
    policy.update(values, r5_enabled=enabled, r5_lane_priority_enabled=lane_priority)
    if enabled and lane_priority:
        p.update(game)
        policy.update(game)
        if adaptive:
            p.update(adaptive)
            policy.update(adaptive)
    return model, p, policy


def input_changes(sealed):
    """Bound project inputs must stay equal to the actual runtime inputs."""
    return sorted('input:'+name for name in INPUTS if not (ROOT/name).is_file() or sha256(ROOT/name) != sealed.get(name))


def mechanism_report(records, case, policy=None):
    actors = {}
    errors = []
    for key in case['controlled']:
        initial_memory = case['initial_memories'][key]
        committed = initial_memory
        timeline = []
        requested_draws = 0
        guard_attempts = guard_rejections = candidate_attempts = candidate_rejections = 0
        requested_starts = committed_starts = 0
        for index, record in enumerate(records):
            if key not in record.get('decisions', {}) or key not in record.get('inputs', {}):
                continue
            before = record['inputs'][key]['memory']
            decision = record['decisions'][key]
            after, detail = decision['memory'], decision['diagnostics'].get('r5', {})
            draw_delta = after['r5_draw_count'] - before['r5_draw_count']
            if draw_delta < 0 or detail.get('draws_this_tick', 0) != draw_delta:
                errors.append({'actor': key, 'interval': index, 'reason': 'Private draw count/diagnostic differ'})
            requested_draws += draw_delta
            guard, candidate = detail.get('guard'), detail.get('candidate_guard')
            if guard is not None:
                guard_attempts += 1
                guard_rejections += not guard['safe']
            if candidate is not None:
                candidate_attempts += 1
                candidate_rejections += not candidate['safe']
            started = before.get('plan') is None and after.get('plan') is not None
            requested_starts += started
            success = record['status'] == 'completed'
            if success:
                committed = after
                committed_starts += started
            state = record['initial'][key]
            final = record.get('steps', {}).get(key, {}).get('final')
            timeline.append({'interval': index, 'time_s': state['time_s'], 'committed': success,
                'speed_mps': state['vx_mps'], 'phase': after['r5_phase'],
                'own_behavior': after['own_behavior'], 'deadline_s': after['r5_deadline_s'],
                'draw_count_before': before['r5_draw_count'], 'draw_count_after_decision': after['r5_draw_count'],
                'draws_this_decision': draw_delta, 'draws': detail.get('draws', []),
                'rng_state_after_decision': after['r5_rng_state'], 'reason': detail.get('reason'),
                'assessment': detail.get('assessment'), 'blocking': detail.get('blocking', False),
                'proposed_yield_mps2': detail.get('proposed_yield_mps2'), 'guard': guard,
                'candidate_guard': candidate, 'new_plan_request': started,
                'actual_lateral_displacement_m': None if final is None else final['y_m'] - state['y_m']})
        phases = Counter(row['phase'] for row in timeline)
        actors[key] = {'draws_in_decisions': requested_draws,
            'draws_committed': committed['r5_draw_count'] - initial_memory['r5_draw_count'],
            'initial_private_state': initial_memory['r5_rng_state'],
            'final_committed_private_state': committed['r5_rng_state'],
            'final_committed_draw_count': committed['r5_draw_count'],
            'phase_counts': dict(phases), 'guard_attempts': guard_attempts, 'guard_rejections': guard_rejections,
            'guard_rejection_fraction': guard_rejections/guard_attempts if guard_attempts else None,
            'candidate_guard_attempts': candidate_attempts, 'candidate_guard_rejections': candidate_rejections,
            'new_plan_requests': requested_starts, 'new_plans_committed': committed_starts,
            'first_eligible_s': next((r['time_s'] for r in timeline if r['phase'] == 'ELIGIBLE'), None),
            'eligible_below_minimum_lc_speed_observed': any(r['phase'] == 'ELIGIBLE' and
                r['speed_mps'] < policy['noa_min_lane_change_speed_mps'] for r in timeline) if policy else None,
            'timeline': timeline}
    return {'schema': 'phase5_r5_mechanism_observations_v1', 'case_name': case['name'],
            'declared_observation_targets': case.get('r5_requirements', []), 'actors': actors,
            'draw_accounting_passed': not errors, 'errors': errors,
            'scope': 'Recorded local gate, private draws, expiry and actual commit facts. Observation targets '
                     'do not require a winner, successful maneuver or formation. Driving/comfort are separate.'}


def mechanism_summary(report):
    actors = report['actors'].values()
    return {'draw_accounting_passed': report['draw_accounting_passed'],
            'draws_in_decisions': sum(a['draws_in_decisions'] for a in actors),
            'draws_committed': sum(a['draws_committed'] for a in report['actors'].values()),
            'new_plans_committed': sum(a['new_plans_committed'] for a in report['actors'].values()),
            'gate_blocking_decisions': sum(bool(r['blocking']) for a in report['actors'].values() for r in a['timeline'])}


def expected_variants(cases, sampling, waiting_policy='fixed', lane_change_policy='fixed'):
    from noa.waiting_game import waiting_parameters
    waiting_parameters(waiting_policy)
    _lane_change_parameters(lane_change_policy)
    result = {case['name']+suffix: {'case_name': case['name'], 'r5_enabled': enabled,
              'sampling': 'ordinary'} for case in cases for suffix, enabled in (('_r5_off', False), ('_r5_on', True))}
    for case in cases:
        waiting = case.get('priority_waiting_baseline', False)
        if type(waiting) is not bool:
            raise ValueError('priority_waiting_baseline must be bool')
        if waiting:
            result[case['name']+'_r5_waiting'] = {'case_name': case['name'], 'r5_enabled': True,
                'sampling': 'ordinary', 'lane_priority_enabled': False}
    if sampling:
        result[cases[0]['name']+'_r5_on_half_control'] = {
            'case_name': cases[0]['name'], 'r5_enabled': True, 'sampling': 'half_control'}
    if waiting_policy != 'fixed':
        for spec in result.values():
            if spec['r5_enabled'] and spec.get('lane_priority_enabled', True):
                spec['waiting_policy'] = waiting_policy
    if lane_change_policy != 'fixed':
        for spec in result.values():
            if spec['r5_enabled'] and spec.get('lane_priority_enabled', True):
                spec['lane_change_policy'] = lane_change_policy
    return result


def finalize_case(folder):
    metadata = read_json(folder/'metadata.json')
    records = [json.loads(line) for line in (folder/'trace.jsonl').read_text(encoding='utf-8').splitlines()] if (folder/'trace.jsonl').is_file() else []
    report = mechanism_report(records, metadata['case'], metadata['policy_parameters'])
    atomic_json(folder/'r5_events.json', report)
    result = read_json(folder/'validation.json')
    result['r5_mechanism'] = mechanism_summary(report)
    atomic_json(folder/'validation.json', result)
    return result


def paired_action_case(case, off, on):
    """Actual commands on a complete common window; failed/absent pairs are unknown."""
    required = 'paired_disabled_actions_equal' in case.get('r5_requirements', [])
    def complete(records):
        return bool(records) and all(r['status'] == 'completed' for r in records) and all(
            records[0]['initial'][key]['time_s'] == 0. and math.isclose(
                records[-1]['steps'][key]['final']['time_s'], case['duration_s'], rel_tol=0., abs_tol=1e-9)
            for key in case['controlled'])
    full = complete(off) and complete(on)
    differences = []
    if full:
        if len(off) != len(on):
            differences.append({'reason': 'Control grid lengths differ'})
        else:
            for index, (left, right) in enumerate(zip(off, on)):
                for key in case['controlled']:
                    if (left['initial'][key]['time_s'] != right['initial'][key]['time_s'] or
                            left['actions'][key] != right['actions'][key]):
                        differences.append({'interval': index, 'actor': key})
    return {'required': required, 'complete_common_window': full,
            'actions_equal': not differences if full else None, 'differences': differences,
            'scope': 'Exact controlled actual commands on the declared full duration; private diagnostic fields are separate.'}


def paired_action_report(folder, cases):
    def rows(name):
        path = folder/'cases'/name/'trace.jsonl'
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.is_file() else []
    return {case['name']: paired_action_case(case, rows(case['name']+'_r5_off'), rows(case['name']+'_r5_on'))
            for case in cases}


def summarize_run(variants, index, sampling, live, changed, pairs=None):
    expected = set(index['expected_variants'])
    attempted = set(index['finalized_variants']) == expected
    complete = set(index['completed_variants']) == expected
    recording = bool(variants) and all(v.get('recording_passed', False) for v in variants.values())
    driving = bool(variants) and all(v.get('driving_passed', False) and v.get('comfort_passed', False) for v in variants.values())
    accounting = bool(variants) and all(v.get('r5_mechanism', {}).get('draw_accounting_passed', False) for v in variants.values())
    r5_positive = sum(v.get('isolation', {}).get('visible_neighbor_removal_changes_r5_gate', 0) +
                      v.get('isolation', {}).get('visible_neighbor_removal_changes_private_random', 0) for v in variants.values())
    sample_ok = bool(sampling) and all(v.get('passed', False) for v in sampling.values())
    required_pairs = [pair for pair in (pairs or {}).values() if pair['required']]
    pairs_ok = bool(required_pairs) and all(pair['actions_equal'] is True for pair in required_pairs)
    engineering = live and complete and recording and driving and accounting and sample_ok and not changed and r5_positive > 0 and pairs_ok
    return {'passed': engineering, 'engineering_passed': engineering, 'scientific_passed': None,
            'live': live, 'complete_matrix_attempted': attempted, 'complete_execution': complete,
            'recording_passed': recording, 'driving_passed': driving,
            'private_draw_accounting_passed': accounting, 'r5_nonvacuous_gate_or_draw_changes': r5_positive,
            'r5_nonvacuity_passed': r5_positive > 0, 'required_no_competition_actions_equal': pairs_ok,
            'sampling': sampling, 'variants': variants, 'source_changed_during_run': changed,
            'next_stage_allowed': None,
            'scope': 'R5 implementation evidence and observed mechanism facts. Engineering includes actual driving; '
                     'no formation improvement, winner, finite-time passage or next-stage approval is implied.'}


def summarize_partial(variants, index, sampling, live, changed, pairs=None):
    result = summarize_run(variants, index, sampling, live, changed, pairs)
    result.update(recorded_prefix_replay_passed=result['recording_passed'],
                  recorded_case_driving_passed=result['driving_passed'],
                  passed=False, engineering_passed=False, scientific_passed=None,
                  recording_passed=False, driving_passed=False, next_stage_allowed=None,
                  retained_partial_package=True,
                  scope='Interrupted R5 execution. Attempt and physical-completion coverage are reconstructed; '
                        'recorded prefix facts do not authorize whole-run driving, scientific or next-stage success.')
    return result


def run_phase5_r5(case_file, base=None, live=True, sampling=True, waiting_policy='fixed',
                  lane_change_policy='fixed'):
    from experiments.phase5 import run_case, _seal
    from experiments.phase5c_cases import load_frozen_cases
    from experiments.phase3 import integration_refinement
    from experiments.phase3_audit import compare_records
    from noa.waiting_game import waiting_parameters
    waiting_parameters(waiting_policy)
    _lane_change_parameters(lane_change_policy)
    case_file = output_path(case_file)
    if not case_file.is_file():
        raise ValueError('An explicit previously frozen R5 case file is required')
    run = RunRecord(base or ROOT/'results/phase5_r5/runs', {
        'purpose': 'Independent R5 mechanism suite', 'clock_schema': CLOCK_SCHEMA,
        'command_line': sys.argv, 'python': sys.version, 'live': live, 'sampling_enabled': sampling,
        'case_file_source': str(case_file), 'case_file_sha256': sha256(case_file),
        'waiting_policy': waiting_policy, 'lane_change_policy': lane_change_policy})
    variants, index, source, comparisons, inputs = {}, {}, {}, {}, {}
    try:
        with run:
            source = code_manifest()
            atomic_json(run.path/'code_hashes.json', source)
            for name in source:
                destination = run.path/'code_snapshot'/name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/name, destination)
            inputs = {}
            for name in INPUTS:
                destination = run.path/'input_snapshot'/name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/name, destination)
                inputs[name] = sha256(destination)
            frozen = run.path/'input_snapshot/frozen_r5_cases.json'
            shutil.copy2(case_file, frozen)
            inputs['frozen_r5_cases.json'] = sha256(frozen)
            atomic_json(run.path/'input_hashes.json', inputs)
            model, _, _ = parameters(False)
            cases = load_frozen_cases(frozen, dict(model.p),
                                      parent_file=run.path/'input_snapshot/parent_frozen_r5_cases.json')
            atomic_json(run.path/'frozen_cases.json', cases)
            specs = (expected_variants(cases, sampling)
                     if waiting_policy == 'fixed' and lane_change_policy == 'fixed'
                     else expected_variants(cases, sampling, waiting_policy=waiting_policy,
                                            lane_change_policy=lane_change_policy))
            index = {'expected_variants': specs, 'started_variants': [],
                     'finalized_variants': [], 'completed_variants': []}
            atomic_json(run.path/'case_index.json', index)
            for name, spec in index['expected_variants'].items():
                case = next(c for c in cases if c['name'] == spec['case_name'])
                model, p, policy = parameters(spec['r5_enabled'],
                                               lane_priority=spec.get('lane_priority_enabled', True),
                                               waiting_policy=spec.get('waiting_policy', 'fixed'),
                                               lane_change_policy=spec.get('lane_change_policy', 'fixed'))
                if spec['sampling'] == 'half_control':
                    p = {**p, 'control_sync_dt_s': p['control_sync_dt_s']/2, 'perception_dt_s': p['perception_dt_s']/2}
                    policy = {**policy, 'control_sync_dt_s': p['control_sync_dt_s'], 'perception_dt_s': p['perception_dt_s']}
                index['started_variants'].append(name)
                atomic_json(run.path/'case_index.json', index)
                folder = run.path/'cases'/name
                run_case(folder, model, p, policy, case, live=live, clock_schema=CLOCK_SCHEMA,
                         initial_memories=case['initial_memories'], private_rng_provenance=case['private_rng_provenance'])
                variants[name] = finalize_case(folder)
                index['finalized_variants'].append(name)
                if read_json(folder/'metadata.json')['execution_status'] == 'completed':
                    index['completed_variants'].append(name)
                atomic_json(run.path/'case_index.json', index)
                atomic_json(run.path/'progress.json', {'finalized_variants': index['finalized_variants'], 'last': name})
                print(json.dumps({'variant': name, 'recording': variants[name]['recording_passed'],
                                  'driving': variants[name]['driving_passed'], 'r5': variants[name]['r5_mechanism']}), flush=True)
            comparisons = {}
            if sampling:
                ordinary_name = cases[0]['name']+'_r5_on'
                half_name = ordinary_name+'_half_control'
                load = lambda name: [json.loads(line) for line in (run.path/'cases'/name/'trace.jsonl').read_text().splitlines()]
                coarse, fine = load(ordinary_name), load(half_name)
                if coarse and fine and all(r['status'] == 'completed' for r in coarse+fine):
                    comp = compare_records(coarse, fine)
                    ordinary_spec = index['expected_variants'][ordinary_name]
                    model, p, _ = parameters(ordinary_spec['r5_enabled'],
                        lane_priority=ordinary_spec.get('lane_priority_enabled', True),
                        waiting_policy=ordinary_spec.get('waiting_policy', 'fixed'),
                        lane_change_policy=ordinary_spec.get('lane_change_policy', 'fixed'))
                    comp['passed'] = comp['max_position_error_m'] <= model.p['control_position_tolerance_m'] and comp['max_heading_error_rad'] <= model.p['control_heading_tolerance_rad']
                    comparisons['control_half'] = comp
                    destination = run.path/'integration_half'
                    destination.mkdir()
                    comparisons['integration_half'], _ = integration_refinement(destination, coarse, model, p)
                else:
                    comparisons['sampling_failed_prefix'] = {'passed': False}
            atomic_json(run.path/'sampling.json', comparisons)
            current = code_manifest()
            changed = sorted(name for name in set(source)|set(current) if source.get(name) != current.get(name))
            changed += input_changes(inputs)
            pairs = paired_action_report(run.path, cases)
            atomic_json(run.path/'paired_actions.json', pairs)
            result = summarize_run(variants, index, comparisons, live, changed, pairs)
            run.finish(result)
    except BaseException:
        if (run.path/'validation.json').is_file() and index:
            for name in index['started_variants']:
                folder = run.path/'cases'/name
                if (folder/'validation.json').is_file() and (folder/'metadata.json').is_file():
                    variants[name] = finalize_case(folder)
                    if name not in index['finalized_variants']:
                        index['finalized_variants'].append(name)
                    if read_json(folder/'metadata.json')['execution_status'] == 'completed' and name not in index['completed_variants']:
                        index['completed_variants'].append(name)
            atomic_json(run.path/'case_index.json', index)
            half = [name for name in variants if name.endswith('_half_control')]
            if half and variants[half[0]].get('status') == 'failed':
                comparisons = {'sampling_failed_prefix': {'passed': False}}
            atomic_json(run.path/'sampling.json', comparisons)
            failure = read_json(run.path/'validation.json')
            current = code_manifest()
            changed = sorted(name for name in set(source)|set(current) if source.get(name) != current.get(name))
            changed += input_changes(inputs)
            pairs = paired_action_report(run.path, cases)
            atomic_json(run.path/'paired_actions.json', pairs)
            failure.update(summarize_partial(variants, index, comparisons, live, changed, pairs))
            atomic_json(run.path/'validation.json', failure)
        raise
    finally:
        if run.path.exists():
            _seal(run.path)
    print(json.dumps({'path': str(run.path), 'engineering_passed': result['engineering_passed'],
                      'recording_passed': result['recording_passed']}), flush=True)
    return run.path
