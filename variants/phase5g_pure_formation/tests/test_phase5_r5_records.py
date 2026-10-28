"""Private-state initialization and independent R5 recording boundaries."""
import copy
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from models.kinematic import kinematic_state
from noa.contracts import NoaMemory
from perception.road import VisibleRoad
from research.common import ROOT


class R5RecordTests(unittest.TestCase):
    def setUp(self):
        from experiments.phase5 import parameters
        self.model, self.p, self.policy = parameters(False)
        values = {'r5_enabled': True, 'r5_front_margin_m': 2.,
                  'r5_visible_inward_speed_mps': .05, 'r5_yield_deceleration_mps2': .5,
                  'r5_backoff_min_s': .5, 'r5_backoff_max_s': 2., 'r5_clear_stable_s': 1.}
        self.p.update(values)
        self.policy.update(values)
        self.road = VisibleRoad((((0., 0.), (2000., 0.)), ((0., 9.9), (2000., 9.9))),
                                (((0., 3.3), (2000., 3.3)), ((0., 6.6), (2000., 6.6))))
        self.initial = {'ego': kinematic_state(self.model.p, x_m=300., y_m=1.65, vx_mps=5.)}
        self.memories = {'ego': self.memory((1 << 64) - 1)}

    @staticmethod
    def memory(state):
        value = asdict(NoaMemory((), 'CRUISE'))
        value.update(r5_rng_state=state, r5_draw_count=0, r5_phase='IDLE',
                     r5_deadline_s=None, r5_episode_signature=None,
                     r5_clear_since_s=None, r5_last_time_s=None)
        return value

    def clock(self, memories=None, p=None, policy=None):
        from simulation.r5_clock import R5Clock
        return R5Clock(self.initial, self.model, self.road, p or self.p, policy or self.policy,
                       ['ego'], {}, self.memories if memories is None else memories)

    def fixture(self, path, failed=False):
        from simulation.noa_clock import ReplayBoundary
        from simulation.r5_clock import CLOCK_SCHEMA, initial_memory_hash
        clock = self.clock()
        rows = [clock.tick()]
        committed = asdict(clock.memories['ego'])
        if failed:
            with self.assertRaises(ReplayBoundary):
                clock.tick(stop_before=('integration', 'ego'))
            rows.append(clock.last_record)
            self.assertEqual(asdict(clock.memories['ego']), committed)
        else:
            rows.append(clock.tick())
        case = {'name': 'record_fixture', 'kind': 'r5_fixture', 'duration_s': .2,
                'controlled': ['ego'], 'scripts': {}, 'requirements': {},
                'initial': {k: asdict(v) for k, v in self.initial.items()},
                'initial_memories': copy.deepcopy(self.memories),
                'private_rng_provenance': {'algorithm': 'SplitMix64', 'version': 1,
                                           'source': 'deterministic_unit_fixture'}}
        meta = {'clock_schema': CLOCK_SCHEMA, 'initial_memories': copy.deepcopy(self.memories),
                'initial_memories_sha256': initial_memory_hash(self.memories),
                'private_rng_provenance': case['private_rng_provenance'],
                'model_parameters': dict(self.model.p), 'parameters': self.p,
                'policy_parameters': self.policy, 'road': asdict(self.road), 'initial': case['initial'],
                'case': case, 'intervals': 2, 'live': False, 'sumo_time_offset_s': 0.,
                'execution_status': 'failed' if failed else 'completed', 'trace_intervals': 2,
                'completed_intervals': 1 if failed else 2, 'physical_intervals': 1 if failed else 2,
                'recorded_intervals': 1 if failed else 2, 'isolation_intervals': 1 if failed else 2,
                'partial_tail': failed}
        if failed:
            meta.update({key: rows[-1][key] for key in ('failure_stage', 'failure_actor')})
            meta['failure_error'] = rows[-1]['error']
        self.write_rows(path, rows)
        return meta, rows

    @staticmethod
    def write_rows(path, rows):
        path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows), encoding='utf-8')

    def test_private_initial_state_survives_first_observation_and_full_uint64(self):
        clock = self.clock()
        self.assertEqual(clock.memories['ego'].r5_rng_state, (1 << 64) - 1)
        row = clock.tick()
        self.assertEqual(row['inputs']['ego']['memory']['r5_rng_state'], (1 << 64) - 1)
        self.assertEqual(row['decisions']['ego']['memory']['r5_draw_count'], 0)
        self.assertEqual(row['inputs']['ego']['observation']['time_s'], 0.)
        second = clock.tick()
        self.assertEqual(len(second['inputs']['ego']['memory']['observation_history']), 1)
        self.assertEqual(second['inputs']['ego']['memory']['r5_rng_state'], (1 << 64) - 1)
        self.assertEqual(self.memories['ego']['observation_history'], ())

    def test_missing_partial_noninteger_and_cross_switch_initializations_rejected(self):
        for bad in ({}, {'other': self.memory(1)}, {'ego': {'r5_rng_state': 1}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.clock(bad)
        for state in (None, True, 1., -1, 1 << 64):
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.clock({'ego': self.memory(state)})
        with self.assertRaises(ValueError):
            self.clock(policy={**self.policy, 'r5_enabled': False})

    def test_equal_private_states_allowed_but_each_instance_restored_separately(self):
        from simulation.r5_clock import R5Clock
        initial = {**self.initial, 'second': replace(self.initial['ego'], x_m=400.)}
        raw = self.memory(7)
        clock = R5Clock(initial, self.model, self.road, self.p, self.policy,
                        ['ego', 'second'], {}, {'ego': raw, 'second': raw})
        self.assertEqual(clock.memories['ego'], clock.memories['second'])
        self.assertIsNot(clock.memories['ego'], clock.memories['second'])

    def test_clock_order_and_identity_changes_preserve_each_own_private_chain(self):
        from experiments.phase5_r5 import parameters
        from experiments.phase5_r5_cases import physical_cases
        from experiments.phase3_replay import compare_tree
        from models.vehicle import VehicleState
        from noa.formation import FormationMemory
        from simulation.r5_clock import R5Clock
        model, p, policy = parameters(True, lane_priority=False)
        case = physical_cases(model.p)[1]
        initial = {key: VehicleState(**value) for key, value in case['initial'].items()}
        memories = {key: asdict(FormationMemory((), 'CRUISE', r5_rng_state=index+1))
                    for index, key in enumerate(case['controlled'])}
        rename = {key: 'renamed_'+str(len(initial)-index) for index, key in enumerate(initial)}
        first = R5Clock(initial, model, self.road, p, policy, case['controlled'], case['scripts'], memories)
        second = R5Clock({rename[k]: v for k, v in reversed(list(initial.items()))}, model, self.road, p, policy,
            [rename[k] for k in reversed(case['controlled'])], {rename[k]: v for k, v in case['scripts'].items()},
            {rename[k]: v for k, v in memories.items()})
        for _ in range(3):
            left, right = first.tick(), second.tick(order=list(reversed(sorted(second.states))))
            for section in ('inputs', 'decisions', 'actions', 'steps'):
                for key, value in left[section].items():
                    compare_tree(value, right[section][rename[key]], 0.)
        self.assertTrue(all(memory.r5_draw_count == 1 for memory in first.memories.values()))

    def test_disabled_r5_preserves_original_actions_and_non_r5_memory_semantics(self):
        from simulation.formation_clock import FormationClock
        from simulation.r5_clock import PRIVATE_FIELDS
        p, policy = {**self.p, 'r5_enabled': False}, {**self.policy, 'r5_enabled': False}
        original = FormationClock(self.initial, self.model, self.road, p, policy, ['ego'], {})
        restored = self.clock(p=p, policy=policy)
        for _ in range(3):
            left, right = original.tick(), restored.tick()
            self.assertEqual(left['actions'], right['actions'])
            self.assertEqual(left['steps'], right['steps'])
            left_memory, right_memory = left['decisions']['ego']['memory'], right['decisions']['ego']['memory']
            self.assertEqual({k:v for k,v in left_memory.items() if k not in PRIVATE_FIELDS},
                             {k:v for k,v in right_memory.items() if k not in PRIVATE_FIELDS})
            self.assertEqual(right_memory['r5_rng_state'], (1 << 64)-1)
            self.assertEqual(right_memory['r5_draw_count'], 0)

    def test_exact_trace_and_failed_prefix_restore_from_metadata(self):
        from experiments.phase5_r5_replay import replay_case
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            for failed in (False, True):
                meta, _ = self.fixture(Path(temp)/'trace.jsonl', failed)
                result = replay_case(meta, Path(temp)/'trace.jsonl')
                self.assertTrue(result['passed'], result)
                self.assertEqual(result['failed_execution_prefix'], failed)

    def test_private_initial_memory_draw_deadline_action_physics_and_truncation_tampering_rejected(self):
        from experiments.phase5_r5_replay import replay_case
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path = Path(temp)/'trace.jsonl'
            meta, rows = self.fixture(path)
            for mutation in ('draw', 'deadline', 'rng_float', 'action', 'physics', 'truncate'):
                changed = copy.deepcopy(rows)
                if mutation == 'draw': changed[0]['decisions']['ego']['memory']['r5_draw_count'] += 1
                if mutation == 'deadline': changed[0]['decisions']['ego']['memory']['r5_deadline_s'] = 1.
                if mutation == 'rng_float': changed[0]['inputs']['ego']['memory']['r5_rng_state'] = float((1 << 64) - 1)
                if mutation == 'action': changed[0]['actions']['ego']['acceleration_mps2'] += .01
                if mutation == 'physics': changed[0]['steps']['ego']['final']['x_m'] += .01
                if mutation == 'truncate': changed.pop()
                self.write_rows(path, changed)
                with self.subTest(mutation=mutation):
                    self.assertFalse(replay_case(meta, path)['passed'])
            self.write_rows(path, rows)
            for change in ('missing', 'state', 'hash', 'schema'):
                bad = copy.deepcopy(meta)
                if change == 'missing': del bad['initial_memories']
                if change == 'state': bad['initial_memories']['ego']['r5_rng_state'] -= 1
                if change == 'hash': bad['initial_memories_sha256'] = '0'*64
                if change == 'schema': bad['clock_schema'] = 'formation_v0'
                with self.subTest(change=change):
                    self.assertFalse(replay_case(bad, path)['passed'])

    def test_isolation_requires_verified_own_memory_and_reconstructs_uint64(self):
        from experiments.phase5_r5_audit import isolation_audit, replay_isolation
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path, audit = Path(temp)/'trace.jsonl', Path(temp)/'isolation.jsonl'
            meta, rows = self.fixture(path)
            result = isolation_audit(meta, path, audit)
            self.assertTrue(result['passed'], result)
            self.assertTrue(replay_isolation(meta, path, audit)['passed'])
            changed = copy.deepcopy(rows)
            changed[0]['inputs']['ego']['memory']['r5_draw_count'] += 1
            self.write_rows(path, changed)
            self.assertFalse(isolation_audit(meta, path, Path(temp)/'invalid.jsonl')['passed'])

    def test_runner_seals_private_initial_memory_before_any_tick(self):
        from experiments.phase5 import run_case
        from simulation.r5_clock import CLOCK_SCHEMA, initial_memory_hash
        case = {'name': 'r5_short', 'kind': 'r5_fixture', 'duration_s': .2, 'controlled': ['ego'],
                'scripts': {}, 'requirements': {}, 'initial': {k: asdict(v) for k,v in self.initial.items()},
                'initial_memories': self.memories,
                'private_rng_provenance': {'algorithm': 'SplitMix64', 'version': 1,
                                           'source': 'deterministic_unit_fixture'}}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path = Path(temp)/'case'
            result = run_case(path, self.model, self.p, self.policy, case, live=False,
                              clock_schema=CLOCK_SCHEMA, initial_memories=self.memories,
                              private_rng_provenance=case['private_rng_provenance'])
            self.assertTrue(result['recording_passed'], result)
            metadata = json.loads((path/'metadata.json').read_text())
            self.assertEqual(metadata['initial_memories_sha256'], initial_memory_hash(self.memories))
            self.assertEqual(metadata['initial_memories']['ego']['r5_rng_state'], (1 << 64) - 1)

    def test_mechanism_report_does_not_commit_a_failed_decision_or_claim_formation(self):
        from experiments.phase5_r5 import mechanism_report
        before = self.memory(7)
        after = {**before, 'r5_rng_state': 8, 'r5_draw_count': 1,
                 'r5_phase': 'BACKOFF', 'r5_deadline_s': 1.25}
        row = {'status': 'failed', 'initial': {k: asdict(v) for k,v in self.initial.items()},
               'inputs': {'ego': {'memory': before}}, 'steps': {},
               'decisions': {'ego': {'memory': after, 'diagnostics': {'r5': {
                   'phase': 'BACKOFF', 'reason': 'ambiguous_backoff', 'draws_this_tick': 1,
                   'proposed_yield': True, 'guard': None}}}}}
        case = {'name': 'failure', 'controlled': ['ego'], 'initial_memories': {'ego': before},
                'r5_requirements': {}}
        report = mechanism_report([row], case)
        actor = report['actors']['ego']
        self.assertEqual(actor['draws_in_decisions'], 1)
        self.assertEqual(actor['draws_committed'], 0)
        self.assertEqual(actor['final_committed_private_state'], 7)
        self.assertFalse(actor['timeline'][0]['committed'])
        self.assertNotIn('formation_success', report)

    def test_nonvacuity_is_an_engineering_requirement(self):
        from experiments.phase5_r5 import summarize_run
        variant = {'recording_passed': True, 'driving_passed': True, 'comfort_passed': True,
                   'r5_mechanism': {'draw_accounting_passed': True}, 'isolation': {}}
        index = {'expected_variants': {'one': {}}, 'finalized_variants': ['one'], 'completed_variants': ['one']}
        pairs = {'single': {'required': True, 'actions_equal': True}}
        result = summarize_run({'one': variant}, index, {'control_half': {'passed': True}}, True, [], pairs)
        self.assertFalse(result['engineering_passed'])
        variant['isolation']['visible_neighbor_removal_changes_r5_gate'] = 1
        self.assertTrue(summarize_run({'one': variant}, index, {'control_half': {'passed': True}}, True, [], pairs)['engineering_passed'])

    def test_required_current_input_changes_are_reported(self):
        from experiments.phase5_r5 import INPUTS, input_changes
        from research.common import sha256
        sealed = {name: sha256(ROOT/name) for name in INPUTS}
        self.assertEqual(input_changes(sealed), [])
        def changed_network(path):
            return '0'*64 if Path(path) == ROOT/INPUTS[0] else sha256(path)
        with patch('experiments.phase5_r5.sha256', side_effect=changed_network):
            self.assertEqual(input_changes(sealed), ['input:'+INPUTS[0]])

    def test_no_competition_pair_requires_full_window_and_equal_actions(self):
        from experiments.phase5_r5 import paired_action_case
        case = {'duration_s': .1, 'controlled': ['ego'], 'r5_requirements': ['paired_disabled_actions_equal']}
        row = self.clock().tick()
        equal = paired_action_case(case, [row], [copy.deepcopy(row)])
        self.assertTrue(equal['actions_equal'])
        self.assertTrue(equal['required'])
        different = copy.deepcopy(row)
        different['actions']['ego']['acceleration_mps2'] += .1
        self.assertFalse(paired_action_case(case, [row], [different])['actions_equal'])
        self.assertIsNone(paired_action_case(case, [row], [])['actions_equal'])
        failed = {**row, 'status': 'failed'}
        self.assertIsNone(paired_action_case(case, [row], [failed])['actions_equal'])

    def test_explicit_frozen_bundle_and_replay_reject_source_and_private_state_tampering(self):
        from experiments.phase5_r5 import run_phase5_r5
        from experiments.phase5_r5_replay import replay_run
        from experiments.phase5_r5_cases import freeze_cases, physical_cases
        from experiments.phase5 import _seal
        from experiments.records import atomic_json
        from simulation.r5_clock import initial_memory_hash
        physical = [{**case, 'duration_s': .2} for case in physical_cases(self.model.p)]
        # This explicitly shortened unit fixture is not a registered mechanism experiment.
        folder = Path(tempfile.mkdtemp(prefix='r5_complete_package_test_', dir=ROOT/'tmp'))
        with patch('experiments.phase5_r5_cases.physical_cases', side_effect=lambda p: copy.deepcopy(physical)):
            frozen = folder/'frozen.json'
            freeze_cases(frozen, dict(self.model.p), entropy_draw=lambda: 7)
            source = run_phase5_r5(frozen, base=folder/'runs', live=False, sampling=True)
            result = replay_run(source, base=folder/'replays')
            self.assertTrue(result['passed'], result)
            index = json.loads((source/'case_index.json').read_text())
            self.assertEqual(len(index['expected_variants']), 17)
            altered = folder/'altered_private'/source.name
            shutil.copytree(source, altered)
            case_dir = altered/'cases'/(physical[0]['name']+'_r5_on')
            original = (case_dir/'metadata.json').read_bytes()
            meta = json.loads(original)
            meta['initial_memories']['ego']['r5_rng_state'] += 1
            meta['initial_memories_sha256'] = initial_memory_hash(meta['initial_memories'])
            atomic_json(case_dir/'metadata.json', meta)
            _seal(altered)
            self.assertFalse(replay_run(altered, base=folder/'replays')['passed'])
            altered = folder/'altered_code'/source.name
            shutil.copytree(source, altered)
            hashes = json.loads((altered/'code_hashes.json').read_text())
            hashes['models/vehicle.py'] = '0'*64
            atomic_json(altered/'code_hashes.json', hashes)
            _seal(altered)
            self.assertFalse(replay_run(altered, base=folder/'replays')['passed'])
            for mutation in ('parameter_tolerance', 'missing_snapshot', 'truncation', 'pair_conclusion'):
                altered = folder/('altered_'+mutation)/source.name
                shutil.copytree(source, altered)
                case_dir = altered/'cases'/(physical[0]['name']+'_r5_off')
                if mutation == 'parameter_tolerance':
                    metadata = json.loads((case_dir/'metadata.json').read_text())
                    metadata['model_parameters']['replay_absolute_tolerance'] = .2
                    atomic_json(case_dir/'metadata.json', metadata)
                elif mutation == 'missing_snapshot':
                    (altered/'code_snapshot/models/vehicle.py').unlink()
                elif mutation == 'truncation':
                    lines = (case_dir/'trace.jsonl').read_text().splitlines()
                    (case_dir/'trace.jsonl').write_text('\n'.join(lines[:-1])+'\n')
                else:
                    pairs = json.loads((altered/'paired_actions.json').read_text())
                    pairs[physical[0]['name']]['actions_equal'] = False
                    atomic_json(altered/'paired_actions.json', pairs)
                _seal(altered)
                with self.subTest(mutation=mutation):
                    self.assertFalse(replay_run(altered, base=folder/'replays')['passed'])
            print(json.dumps({'retained_complete_fixture': str(source)}), flush=True)

    def test_sub_tolerance_private_draw_and_deadline_changes_are_rejected(self):
        from experiments.phase5 import run_case
        from experiments.phase5_r5 import parameters
        from experiments.phase5_r5_cases import physical_cases
        from experiments.phase5_r5_replay import replay_case
        from noa.formation import FormationMemory
        from simulation.r5_clock import CLOCK_SCHEMA
        # This legacy integrity probe needs an ambiguous private draw, not a
        # decisive phase 5C lane-priority relation.
        model, p, policy = parameters(True, lane_priority=False)
        case = {**physical_cases(model.p)[1], 'duration_s': .2}
        case['initial_memories'] = {key: asdict(FormationMemory((), 'CRUISE', r5_rng_state=index+1))
                                    for index, key in enumerate(case['controlled'])}
        case['private_rng_provenance'] = {'algorithm': 'SplitMix64', 'version': 1,
                                         'source': 'deterministic_unit_fixture'}
        folder = Path(tempfile.mkdtemp(prefix='r5_private_integrity_test_', dir=ROOT/'tmp'))
        for name in ('experiments/phase5_replay.py', 'experiments/phase5_r5_replay.py',
                     'tests/test_phase5_r5_records.py'):
            target = folder/'review_snapshot'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name, target)
        path = folder/'case'
        run_case(path, model, p, policy, case, live=False, clock_schema=CLOCK_SCHEMA,
                 initial_memories=case['initial_memories'], private_rng_provenance=case['private_rng_provenance'])
        metadata = json.loads((path/'metadata.json').read_text())
        rows = [json.loads(line) for line in (path/'trace.jsonl').read_text().splitlines()]
        key = case['controlled'][0]
        self.assertEqual(rows[0]['decisions'][key]['memory']['r5_draw_count'], 1)
        results = {}
        delta = model.p['replay_absolute_tolerance']/4
        for field in ('deadline', 'unit_interval', 'delay_s'):
            altered = copy.deepcopy(rows)
            if field == 'deadline':
                altered[0]['decisions'][key]['memory']['r5_deadline_s'] += delta
            else:
                altered[0]['decisions'][key]['diagnostics']['r5']['draws'][0][field] += delta
            target = folder/(field+'_altered.jsonl')
            self.write_rows(target, altered)
            results[field] = replay_case(metadata, target)
        (folder/'probe_results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        self.assertTrue(all(not value['passed'] for value in results.values()), (str(folder), results))

    def test_counterfactual_private_timer_tampering_is_also_exact(self):
        from experiments.phase5_r5_audit import isolation_audit, replay_isolation
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path, audit = Path(temp)/'trace.jsonl', Path(temp)/'audit.jsonl'
            meta, _ = self.fixture(path)
            self.assertTrue(isolation_audit(meta, path, audit)['passed'])
            rows = [json.loads(line) for line in audit.read_text().splitlines()]
            self.assertIsInstance(rows[0]['decision']['memory']['r5_last_time_s'], float)
            rows[0]['decision']['memory']['r5_last_time_s'] += self.model.p['replay_absolute_tolerance']/4
            self.write_rows(audit, rows)
            self.assertFalse(replay_isolation(meta, path, audit)['passed'])

    def test_standalone_provenance_version_rejects_bool(self):
        from experiments.phase5_r5_replay import replay_case
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path = Path(temp)/'trace.jsonl'
            meta, _ = self.fixture(path)
            meta['private_rng_provenance']['version'] = True
            self.assertFalse(replay_case(meta, path)['passed'])

    def test_noninterference_private_state_is_exact_against_original_trace(self):
        from experiments.phase5_r5_audit import isolation_audit
        from noa.controller import decide
        def tiny_counterfactual_drift(control, policy):
            result = decide(control, policy)
            return replace(result, memory=replace(result.memory,
                r5_last_time_s=result.memory.r5_last_time_s + self.model.p['replay_absolute_tolerance']/4))
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path = Path(temp)/'trace.jsonl'
            meta, _ = self.fixture(path)
            # FormationClock holds the original controller alias; only the audit's
            # direct import changes, so the original private chain still replays.
            with patch('noa.controller.decide', side_effect=tiny_counterfactual_drift):
                result = isolation_audit(meta, path, Path(temp)/'audit.jsonl')
            self.assertFalse(result['passed'], result)

    def test_interrupted_bundle_retains_draw_without_committing_private_state(self):
        from experiments.phase5_r5 import run_phase5_r5, expected_variants
        from experiments.phase5_r5_replay import replay_run
        from experiments.phase5_r5_cases import freeze_cases, physical_cases
        from experiments.phase5 import run_case
        physical = [{**case, 'duration_s': .2} for case in physical_cases(self.model.p)]
        folder = Path(tempfile.mkdtemp(prefix='r5_failed_package_test_', dir=ROOT/'tmp'))
        def interrupted(*args, **kwargs):
            model, p, case = args[1], args[2], args[4]
            if case['name'] == 'r5_competing' and p['r5_enabled']:
                with patch.object(model, 'advance', side_effect=KeyboardInterrupt('controlled failure after private draws before integration')):
                    return run_case(*args, **kwargs)
            return run_case(*args, **kwargs)
        # Explicit waiting-only unit matrix preserves this legacy interrupted
        # private-draw probe. Replay reconstructs the same recorded False flags.
        def waiting_specs(cases, sampling):
            return {name: {**spec, 'lane_priority_enabled': False}
                    for name, spec in expected_variants(cases, sampling).items()}
        with patch('experiments.phase5_r5_cases.physical_cases', side_effect=lambda p: copy.deepcopy(physical)), \
             patch('experiments.phase5_r5.expected_variants', side_effect=waiting_specs):
            frozen = folder/'frozen.json'
            freeze_cases(frozen, dict(self.model.p), entropy_draw=lambda: 7)
            with patch('experiments.phase5.run_case', side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
                run_phase5_r5(frozen, base=folder/'runs', live=False, sampling=True)
            source = next(path for path in (folder/'runs').iterdir() if path.is_dir())
            result = replay_run(source, base=folder/'replays')
            self.assertTrue(result['passed'], result)
            self.assertTrue(result['partial_source_package'])
            self.assertEqual(len(result['cases']), 4)
            self.assertEqual(len(result['unstarted_variants']), 13)
            report = json.loads((source/'cases/r5_competing_r5_on/r5_events.json').read_text())
            for actor in report['actors'].values():
                self.assertEqual(actor['draws_in_decisions'], 1)
                self.assertEqual(actor['draws_committed'], 0)
                self.assertEqual(actor['final_committed_private_state'], 7)
            from experiments.phase5 import _seal
            from experiments.records import atomic_json
            probes = {}
            for field in ('driving_passed', 'scientific_passed', 'next_stage_allowed', 'complete_execution'):
                altered = folder/('altered_'+field)/source.name
                shutil.copytree(source, altered)
                gate = json.loads((altered/'validation.json').read_text())
                gate[field] = True
                atomic_json(altered/'validation.json', gate)
                _seal(altered)
                checked = replay_run(altered, base=folder/'replays')
                probes[field] = {'source': str(altered), 'accepted': checked['passed'], 'errors': checked['errors']}
            (folder/'partial_summary_probe_results.json').write_text(json.dumps(probes, indent=2), encoding='utf-8')
            self.assertFalse(any(p['accepted'] for p in probes.values()), (str(folder), probes))
            print(json.dumps({'retained_failed_fixture': str(source)}), flush=True)


if __name__ == '__main__':
    unittest.main()
