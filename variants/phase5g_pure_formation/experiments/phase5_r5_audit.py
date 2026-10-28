"""Sampled noninterference only after independent private-memory trace reconstruction."""
from dataclasses import asdict, replace
from itertools import zip_longest
import json

from experiments.phase3_replay import compare_tree
from experiments.phase5_audit import isolation_rows as formation_isolation_rows
from experiments.phase5_replay import rebuild_clock
from perception.contracts import ControlInput, EgoState, LocalObservation, NeighborDetection, RoadObservation
from research.common import output_path


def _control(data, formation_enabled):
    if formation_enabled:
        from noa.formation import memory_from_dict
    else:
        from noa.contracts import memory_from_dict
    observation = data['observation']
    road = observation['road']
    local = LocalObservation(observation['time_s'], tuple(NeighborDetection(**n) for n in observation['neighbors']),
        RoadObservation(road['measurement_time_s'],
            tuple(tuple(tuple(p) for p in line) for line in road['boundary_polylines_m']),
            tuple(tuple(tuple(p) for p in line) for line in road['marking_polylines_m'])))
    return ControlInput(EgoState(**data['ego']), local, memory_from_dict(data['memory']))


def _gate(decision):
    r5 = decision.diagnostics.get('r5', {})
    return {name: r5.get(name) for name in ('phase', 'reason', 'blocking', 'proposed_yield_mps2')}


def _private(decision):
    return {name: getattr(decision.memory, name) for name in
            ('r5_rng_state', 'r5_draw_count', 'r5_deadline_s')}


def isolation_rows(metadata, trace_path):
    from experiments.phase5_r5_replay import replay_case, compare_private_record
    verified = replay_case(metadata, trace_path)
    if not verified['passed']:
        raise ValueError(f'Own memory chain did not independently reconstruct: {verified["errors"]}')
    model, road, _ = rebuild_clock(metadata)
    records = [json.loads(line) for line in output_path(trace_path).read_text(encoding='utf-8').splitlines()]
    records = records[:metadata['physical_intervals']]
    p, policy = metadata['parameters'], metadata['policy_parameters']
    if p['formation_enabled']:
        from noa.formation import decide
    else:
        from noa.controller import decide
    for row in formation_isolation_rows(records, model, p, policy, road, metadata['case']['controlled']):
        baseline = records[row['interval']]
        key = row['ego']
        try:
            compare_private_record(
                {'inputs': {key: baseline['inputs'][key]}, 'decisions': {key: baseline['decisions'][key]}},
                {'inputs': {key: row['input']}, 'decisions': {key: row['decision']}})
        except ValueError:
            row['identical'] = False
        row.update(visible_removal_changes_r5_gate=False, visible_removal_changes_private_random=False,
                   r5_visible_removal=None)
        if row['mutation'] == 'hidden_type':
            control = _control(row['input'], p['formation_enabled'])
            original = decide(control, policy)
            removed = decide(replace(control, observation=replace(control.observation, neighbors=())), policy)
            row['visible_removal_changes_r5_gate'] = _gate(original) != _gate(removed)
            row['visible_removal_changes_private_random'] = _private(original) != _private(removed)
            row['r5_visible_removal'] = {'gate': _gate(removed), 'private': _private(removed),
                                        'action': asdict(removed.action)}
        yield row


def _empty_report(metadata):
    return {'passed': False, 'comparisons': 0, 'mismatches': [],
            'visible_neighbor_removal_changes_action': 0,
            'visible_neighbor_removal_changes_r5_gate': 0,
            'visible_neighbor_removal_changes_private_random': 0,
            'sample_stride_intervals': metadata['parameters']['phase5_isolation_stride'],
            'scope': 'Every counterfactual sensor history rebuilt. Sampled same-own-memory comparisons use only '
                     'a separately reconstructed complete trace/private RNG chain; not separate closed-loop worlds.'}


def _count(report, row):
    report['comparisons'] += 1
    for source, target in (
            ('visible_removal_changes_action', 'visible_neighbor_removal_changes_action'),
            ('visible_removal_changes_r5_gate', 'visible_neighbor_removal_changes_r5_gate'),
            ('visible_removal_changes_private_random', 'visible_neighbor_removal_changes_private_random')):
        report[target] += bool(row[source])
    if not row['identical']:
        report['mismatches'].append({key: row[key] for key in ('interval', 'ego', 'mutation')})


def isolation_audit(metadata, trace_path, audit_path):
    report = _empty_report(metadata)
    try:
        with output_path(audit_path).open('w', encoding='utf-8') as handle:
            for row in isolation_rows(metadata, trace_path):
                handle.write(json.dumps(row, allow_nan=False) + '\n')
                _count(report, row)
        report['passed'] = not report['mismatches']
        if not report['comparisons']:
            report.update(status='not_applicable', meaning='No complete physical interval; failed tail independently reconstructed')
    except Exception as exc:
        report['mismatches'].append(f'{type(exc).__name__}: {exc}')
    return report


def replay_isolation(metadata, trace_path, audit_path):
    from experiments.phase5_r5_replay import compare_private_record, _exact_private
    report = _empty_report(metadata)
    try:
        with output_path(audit_path).open(encoding='utf-8') as handle:
            for expected, line in zip_longest(isolation_rows(metadata, trace_path), handle):
                if expected is None or line is None:
                    raise ValueError('Truncated or extra R5 isolation evidence')
                actual = json.loads(line)
                compare_private_record({'inputs': {'own': expected['input']}, 'decisions': {'own': expected['decision']}},
                                       {'inputs': {'own': actual['input']}, 'decisions': {'own': actual['decision']}})
                if expected['r5_visible_removal'] is not None:
                    _exact_private(expected['r5_visible_removal']['private'], actual['r5_visible_removal']['private'],
                                   'visible_removal.private')
                compare_tree(expected, actual, metadata['model_parameters']['replay_absolute_tolerance'])
                _count(report, expected)
        report['passed'] = not report['mismatches']
    except Exception as exc:
        report['mismatches'].append(f'{type(exc).__name__}: {exc}')
    return report
