"""Fixed phase 5C extension and exact runner/replay policy binding."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from experiments import phase5_r5_cases as parent_cases
from experiments.phase5_r5 import INPUTS, expected_variants, parameters
from models.kinematic import kinematic_state
from noa.formation import FormationMemory
from dataclasses import asdict
from research.common import ROOT, sha256


class Phase5CCaseTests(unittest.TestCase):
    def setUp(self):
        self.model, self.p, self.policy = parameters(True)
        self.model_p = dict(self.model.p)
        self.parent = ROOT/'parent_frozen_r5_cases.json'

    def extension(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase5c_cases'),
                             'The preregistered extension loader must exist')
        return importlib.import_module('experiments.phase5c_cases')

    def test_parameter_default_records_priority_in_both_parameter_domains(self):
        self.assertIs(self.p.get('r5_lane_priority_enabled'), True)
        self.assertIs(self.policy.get('r5_lane_priority_enabled'), True)

    def test_explicit_waiting_flag_changes_only_that_flag(self):
        self.assertIn('r5_lane_priority_enabled', self.p)
        model, p, policy = parameters(True, lane_priority=False)
        self.assertEqual(dict(model.p), self.model_p)
        self.assertEqual(p, {**self.p, 'r5_lane_priority_enabled': False})
        self.assertEqual(policy, {**self.policy, 'r5_lane_priority_enabled': False})
        _, off_p, off_policy = parameters(False, lane_priority=False)
        self.assertIs(off_p['r5_enabled'], False)
        self.assertIs(off_policy['r5_lane_priority_enabled'], False)

    def test_waiting_flag_requires_bool(self):
        self.assertIn('r5_lane_priority_enabled', self.p)
        for bad in (None, 0, 1, 'false', [], {}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parameters(True, lane_priority=bad)

    def test_plan_and_parent_bytes_are_required_run_inputs(self):
        self.assertIn('docs/phase5c_lane_priority_plan.md', INPUTS)
        self.assertIn('parent_frozen_r5_cases.json', INPUTS)

    def test_original_matrix_specs_stay_exact_and_registry_adds_only_waiting(self):
        original = parent_cases.load_frozen_cases(self.parent, self.model_p)
        expected = {case['name']+suffix: {'case_name': case['name'], 'r5_enabled': enabled,
                   'sampling': 'ordinary'} for case in original
                   for suffix, enabled in (('_r5_off', False), ('_r5_on', True))}
        expected[original[0]['name']+'_r5_on_half_control'] = {
            'case_name': original[0]['name'], 'r5_enabled': True, 'sampling': 'half_control'}
        self.assertEqual(expected_variants(original, True), expected)
        registered = [original[0], {**original[1], 'priority_waiting_baseline': True}]
        matrix = expected_variants(registered, True)
        self.assertEqual(len(matrix), 6)
        waiting = matrix[original[1]['name']+'_r5_waiting']
        self.assertEqual(waiting, {'case_name': original[1]['name'], 'r5_enabled': True,
                                  'sampling': 'ordinary', 'lane_priority_enabled': False})
        self.assertEqual(len(expected_variants(registered, False)), 5)

    def test_registry_flag_rejects_nonboolean_truthy_values(self):
        case = {'name': 'unit', 'priority_waiting_baseline': 1}
        with self.assertRaises(ValueError):
            expected_variants([case], False)

    def test_old_schema_delegates_to_unchanged_parent_loader(self):
        ext = self.extension()
        original = parent_cases.load_frozen_cases(self.parent, self.model_p)
        with patch.object(parent_cases, 'load_frozen_cases', wraps=parent_cases.load_frozen_cases) as delegated:
            self.assertEqual(ext.load_frozen_cases(self.parent, self.model_p), original)
            delegated.assert_called_once_with(self.parent, self.model_p)

    def test_fixed_extension_exact_parent_and_three_own_private_states(self):
        ext = self.extension()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'new.json'
            with patch.object(parent_cases.secrets, 'randbits', side_effect=AssertionError('No entropy in extension')):
                cases = ext.freeze_cases(path, self.model_p)
            self.assertEqual(cases, ext.load_frozen_cases(path, self.model_p))
            self.assertEqual(len(cases), 2)
            parent = parent_cases.load_frozen_cases(self.parent, self.model_p)
            self.assertEqual(cases[0], parent[0])
            case = cases[1]
            self.assertEqual(case['name'], 'r5c_gradual_three')
            self.assertEqual(case['duration_s'], 60.)
            self.assertEqual(case['controlled'], ['lower', 'upper', 'middle_front'])
            self.assertIs(case['priority_waiting_baseline'], True)
            placements = {'lower': (250., 1.65, 8.), 'upper': (250., 8.25, 8.),
                          'middle_front': (280., 4.95, 8.), 'lead_lower': (310., 1.65, 2.),
                          'lead_upper': (310., 8.25, 2.)}
            for actor, (x, y, speed) in placements.items():
                self.assertEqual(case['initial'][actor],
                    asdict(kinematic_state(self.model_p, x_m=x, y_m=y, vx_mps=speed)))
            self.assertEqual(case['scripts'], {actor: {'speed_steps': [[0., 2.]]}
                                              for actor in ('lead_lower', 'lead_upper')})
            memory = json.loads(json.dumps(asdict(FormationMemory((), 'CRUISE', r5_rng_state=1))))
            self.assertEqual(case['initial_memories'], {actor: memory for actor in case['controlled']})
            self.assertEqual(case['private_rng_provenance'], {
                'algorithm': 'SplitMix64', 'version': 1, 'source': 'adversarial_fixed_private_state',
                'states_by_actor': {actor: 1 for actor in case['controlled']},
                'independent_draws_requested': False, 'uniqueness_enforced': False,
                'online_initialization': False})
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['parent_file_sha256'], sha256(self.parent))
            self.assertEqual(len(expected_variants(cases, True)), 6)

    def test_freezer_is_deterministic_and_never_overwrites(self):
        ext = self.extension()
        with tempfile.TemporaryDirectory() as tmp:
            one, two = Path(tmp)/'one.json', Path(tmp)/'two.json'
            ext.freeze_cases(one, self.model_p)
            ext.freeze_cases(two, self.model_p)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            before = one.read_bytes()
            with self.assertRaises(FileExistsError):
                ext.freeze_cases(one, self.model_p, parent_file=Path(tmp)/'absent.json')
            self.assertEqual(one.read_bytes(), before)

    def test_rehashed_mutations_cannot_change_registered_extension(self):
        ext = self.extension()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'cases.json'
            ext.freeze_cases(path, self.model_p)
            original = json.loads(path.read_text(encoding='utf-8'))
            for field in ('duration', 'physics', 'script', 'private_state', 'partial_memory',
                          'private_bool', 'provenance', 'registry', 'parent_case', 'case_count',
                          'source', 'model', 'parent_hash', 'schema'):
                with self.subTest(field=field):
                    data = copy.deepcopy(original)
                    case = data['cases'][1]
                    if field == 'duration': case['duration_s'] = 59.
                    elif field == 'physics': case['initial']['upper']['x_m'] += 1.
                    elif field == 'script': case['scripts']['lead_upper']['speed_steps'][0][1] = 3.
                    elif field == 'private_state': case['initial_memories']['upper']['r5_rng_state'] = 2
                    elif field == 'partial_memory': del case['initial_memories']['upper']['r5_phase']
                    elif field == 'private_bool': case['initial_memories']['upper']['r5_rng_state'] = True
                    elif field == 'provenance': case['private_rng_provenance']['version'] = True
                    elif field == 'registry': case['priority_waiting_baseline'] = False
                    elif field == 'parent_case': data['cases'][0]['initial_memories']['ego']['r5_rng_state'] += 1
                    elif field == 'case_count': data['cases'].pop()
                    elif field == 'source': data['generator_sha256'] = '0'*64
                    elif field == 'model': data['model_parameters_sha256'] = '0'*64
                    elif field == 'parent_hash': data['parent_file_sha256'] = '0'*64
                    else: data['schema'] = 'unregistered_extension'
                    data['physical_sha256'] = parent_cases._digest([parent_cases._physical(c) for c in data['cases']])
                    data['initial_state_sha256'] = parent_cases._digest(data['cases'])
                    path.write_text(json.dumps(data), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        ext.load_frozen_cases(path, self.model_p)

    def test_parent_binding_uses_actual_fixed_bytes_not_self_reported_hash(self):
        ext = self.extension()
        with tempfile.TemporaryDirectory() as tmp:
            path, parent = Path(tmp)/'cases.json', Path(tmp)/'parent.json'
            ext.freeze_cases(path, self.model_p)
            parent.write_bytes(self.parent.read_bytes()+b'\n')
            data = json.loads(path.read_text(encoding='utf-8'))
            data['parent_file_sha256'] = sha256(parent)
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError):
                ext.load_frozen_cases(path, self.model_p, parent_file=parent)
            with self.assertRaises(ValueError):
                ext.freeze_cases(Path(tmp)/'other.json', self.model_p, parent_file=parent)

    def test_loader_binds_current_model_and_generator_source(self):
        ext = self.extension()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'cases.json'
            ext.freeze_cases(path, self.model_p)
            changed_p = {**self.model_p, 'wheelbase_m': self.model_p.get('wheelbase_m', 2.8)+.1}
            with self.assertRaises(ValueError):
                ext.load_frozen_cases(path, changed_p)
            other_source = Path(tmp)/'other_source.py'
            other_source.write_text('# changed source\n', encoding='utf-8')
            with patch.object(ext, '__file__', str(other_source)), self.assertRaises(ValueError):
                ext.load_frozen_cases(path, self.model_p)

    def test_short_unit_bundle_runs_and_replays_all_six_with_exact_waiting_binding(self):
        from experiments.phase5 import _seal
        from experiments.phase5_r5 import run_phase5_r5
        from experiments.phase5_r5_replay import replay_run
        from experiments.records import atomic_json
        ext = self.extension()
        cases = [{**case, 'duration_s': .2} for case in ext.build_cases(self.model_p)]
        # Deliberately shortened unit fixture; never a registered vehicle experiment.
        # Keep the exact parent file unchanged and patch only the generator seam.
        folder = Path(tempfile.mkdtemp(prefix='phase5c_six_unit_', dir=ROOT/'tmp'))
        with patch.object(ext, 'build_cases', side_effect=lambda *args: copy.deepcopy(cases)):
            frozen = folder/'unit_cases.json'
            ext.freeze_cases(frozen, self.model_p)
            try:
                source = run_phase5_r5(frozen, base=folder/'runs', live=False, sampling=True)
            except ValueError as exc:
                self.fail(f'The runner must accept the validated phase 5C schema: {exc}')
            result = replay_run(source, base=folder/'replays')
            self.assertTrue(result['passed'], result)
            self.assertEqual(len(result['cases']), 6)
            index = json.loads((source/'case_index.json').read_text())
            self.assertEqual(len(index['expected_variants']), 6)
            self.assertEqual(index['completed_variants'], list(index['expected_variants']))
            input_hashes = json.loads((source/'input_hashes.json').read_text())
            self.assertEqual(set(input_hashes), set(INPUTS)|{'frozen_r5_cases.json'})
            pairs = json.loads((source/'paired_actions.json').read_text())
            self.assertEqual(set(pairs), {case['name'] for case in cases})
            for name, spec in index['expected_variants'].items():
                metadata = json.loads((source/'cases'/name/'metadata.json').read_text())
                for field in ('parameters', 'policy_parameters'):
                    self.assertIs(metadata[field]['r5_lane_priority_enabled'],
                                  spec.get('lane_priority_enabled', True))
            waiting_name = 'r5c_gradual_three_r5_waiting'
            for mutation in ('waiting_policy', 'waiting_index', 'rehashed_case', 'rehashed_parent'):
                with self.subTest(mutation=mutation):
                    altered = folder/('altered_'+mutation)/source.name
                    shutil.copytree(source, altered)
                    if mutation == 'waiting_policy':
                        target = altered/'cases'/waiting_name/'metadata.json'
                        metadata = json.loads(target.read_text())
                        for field in ('parameters', 'policy_parameters'):
                            metadata[field]['r5_lane_priority_enabled'] = True
                        atomic_json(target, metadata)
                    elif mutation == 'waiting_index':
                        target = altered/'case_index.json'
                        changed_index = json.loads(target.read_text())
                        changed_index['expected_variants'][waiting_name]['lane_priority_enabled'] = True
                        atomic_json(target, changed_index)
                    elif mutation == 'rehashed_case':
                        target = altered/'input_snapshot/frozen_r5_cases.json'
                        bundle = json.loads(target.read_text())
                        bundle['cases'][1]['initial_memories']['upper']['r5_rng_state'] = 2
                        bundle['initial_state_sha256'] = parent_cases._digest(bundle['cases'])
                        atomic_json(target, bundle)
                        atomic_json(altered/'frozen_cases.json', bundle['cases'])
                        metadata = json.loads((altered/'metadata.json').read_text())
                        metadata['case_file_sha256'] = sha256(target)
                        atomic_json(altered/'metadata.json', metadata)
                        hashes = json.loads((altered/'input_hashes.json').read_text())
                        hashes['frozen_r5_cases.json'] = sha256(target)
                        atomic_json(altered/'input_hashes.json', hashes)
                    else:
                        target = altered/'input_snapshot/parent_frozen_r5_cases.json'
                        target.write_bytes(target.read_bytes()+b'\n')
                        hashes = json.loads((altered/'input_hashes.json').read_text())
                        hashes['parent_frozen_r5_cases.json'] = sha256(target)
                        atomic_json(altered/'input_hashes.json', hashes)
                    _seal(altered)
                    rejected = replay_run(altered, base=folder/'replays')
                    self.assertFalse(rejected['passed'], rejected)
            print(json.dumps({'retained_phase5c_six_unit_fixture': str(source)}), flush=True)


if __name__ == '__main__':
    unittest.main()
