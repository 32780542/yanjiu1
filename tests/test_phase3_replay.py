import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class Phase3ReplayTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase3_replay'), 'Phase 3 replay missing')
        from research.common import ROOT, settings
        from models.vehicle import VehicleModel
        self.root, self.model = ROOT, VehicleModel.from_config()
        self.p = {**dict(self.model.p),**settings('phase3')}

    def fixture(self, path):
        from experiments.phase3_cases import cases
        from experiments.phase3 import run_case
        case = {**cases(self.p)[0], 'duration_s':.3}
        result = run_case(path,self.model,self.p,case,live=False)
        self.assertTrue(result['passed'], result)
        return json.loads((path/'metadata.json').read_text()), (path/'trace.jsonl').read_text().splitlines()

    def test_rebuilds_observations_memory_actions_and_all_physical_substeps(self):
        from experiments.phase3_replay import replay_case
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path = Path(tmp)/'case'
            meta,lines = self.fixture(path)
            report = replay_case(meta,path/'trace.jsonl')
            self.assertTrue(report['passed'],report)
            self.assertEqual(report['intervals'],3)
            self.assertEqual(report['vehicle_intervals'],3*len(meta['initial']))
            self.assertEqual(report['max_numeric_error'],0)

    def test_tampered_observation_memory_action_truth_substep_and_truncation_rejected(self):
        from experiments.phase3_replay import replay_case
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path = Path(tmp)/'case'
            meta,lines = self.fixture(path)
            original = [json.loads(s) for s in lines]
            key = sorted(meta['initial'])[0]
            for field in ('observation','memory','action','truth','substep','diagnostic','truncate','readback'):
                data = copy.deepcopy(original)
                if field == 'observation':
                    data[0]['inputs'][key]['observation']['neighbors'][0]['relative_x_m'] += .001
                elif field == 'memory':
                    data[1]['inputs'][key]['memory']['observation_history'] = []
                elif field == 'action':
                    data[0]['actions'][key]['acceleration_mps2'] += .001
                elif field == 'truth':
                    data[1]['initial'][key]['x_m'] += .001
                elif field == 'substep':
                    data[0]['steps'][key]['samples'][3]['y_m'] += .0001
                elif field == 'diagnostic':
                    data[0]['diagnostics'][key][3]['a_long_mps2'] += .001
                elif field == 'readback':
                    data[0]['readback'] = {}
                else:
                    data.pop()
                (path/'trace.jsonl').write_text('\n'.join(json.dumps(d) for d in data)+'\n')
                self.assertFalse(replay_case(meta,path/'trace.jsonl')['passed'],field)

    def test_initialization_failure_has_new_failed_run_and_traceback(self):
        from experiments.phase3 import run_phase3
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            base = Path(tmp)/'runs'
            with patch('experiments.phase3.VehicleModel.from_config',side_effect=RuntimeError('injected dependency failure')):
                with self.assertRaisesRegex(RuntimeError,'injected'):
                    run_phase3(base=base)
            latest = json.loads((base/'latest.json').read_text())
            result = json.loads((Path(latest['path'])/'validation.json').read_text())
            self.assertEqual(result['status'],'failed')
            self.assertIn('injected dependency failure',result['traceback'])
            meta = json.loads((Path(latest['path'])/'metadata.json').read_text())
            self.assertIn('command_line',meta)
            self.assertIn('code_and_config_hashes',meta)
            self.assertTrue((Path(latest['path'])/'source_snapshot/configs/phase3.json').is_file())

    def test_failed_physical_case_is_recorded_without_changing_action(self):
        from experiments.phase3 import run_case
        from experiments.phase3_cases import cases
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            case = copy.deepcopy(cases(self.p)[0])
            case['duration_s'] = .1
            keys = list(case['initial'])
            case['initial'][keys[1]] = dict(case['initial'][keys[0]])
            path = Path(tmp)/'collision'
            result = run_case(path,self.model,self.p,case,live=False)
            self.assertFalse(result['passed'])
            self.assertGreater(result['geometry']['collision_substeps'],0)
            self.assertEqual(result['status'],'completed')
            self.assertTrue((path/'trace.jsonl').is_file())

    def test_policy_has_only_local_import_dependencies(self):
        import ast
        tree = ast.parse((self.root/'perception/probe.py').read_text())
        modules = [n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertEqual(modules,['models.vehicle'])
        self.assertFalse(any(isinstance(n,ast.Import) for n in ast.walk(tree)))
        names = {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        self.assertTrue(names.isdisjoint({'open','eval','exec','globals','__import__'}))

    def test_mutation_audit_replays_histories_and_rejects_altered_mutant(self):
        from experiments.phase3_replay import replay_isolation
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path = Path(tmp)/'case'
            meta,lines = self.fixture(path)
            report = replay_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')
            self.assertTrue(report['passed'],report)
            self.assertEqual(report['comparisons'],len(meta['initial'])*3*4)
            lines = (path/'isolation.jsonl').read_text().splitlines()
            first = json.loads(lines[0])
            first['mutated_frame'][0]['state']['x_m'] += .01
            lines[0] = json.dumps(first)
            (path/'isolation.jsonl').write_text('\n'.join(lines)+'\n')
            self.assertFalse(replay_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')['passed'])

    def test_exact_track_identity_replay_does_not_tolerate_fractional_label_corruption(self):
        from experiments.phase3_replay import compare_tree
        with self.assertRaises(ValueError):
            compare_tree({'track_id':1},{'track_id':1.00000000001},1e-9)

    def test_live_fleet_readback_and_action_replay_rejects_physical_corruption(self):
        from experiments.phase3 import run_case
        from experiments.phase3_cases import cases
        from experiments.phase3_replay import replay_case
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path = Path(tmp)/'live'
            case = {**cases(self.p)[0],'duration_s':.2}
            result = run_case(path,self.model,self.p,case,live=True)
            self.assertTrue(result['passed'],result)
            self.assertEqual(result['physical_sumo_advances'],2)
            meta = json.loads((path/'metadata.json').read_text())
            lines = (path/'trace.jsonl').read_text().splitlines()
            data = json.loads(lines[0])
            data['readback']['a']['sumo_time_s'] += .1
            lines[0] = json.dumps(data)
            (path/'trace.jsonl').write_text('\n'.join(lines)+'\n')
            self.assertFalse(replay_case(meta,path/'trace.jsonl')['passed'])

    def test_persisted_faults_replay_and_separate_detection_from_failed_driving(self):
        from experiments.phase3 import run_case
        from experiments.phase3_cases import cases
        from experiments.phase3_faults import run_faults, replay_faults
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            source = Path(tmp)/'live'
            case = {**cases(self.p)[0],'duration_s':.3}
            self.assertTrue(run_case(source,self.model,self.p,case,live=True)['passed'])
            path = Path(tmp)/'faults'
            result = run_faults(path,self.model,self.p,source)
            self.assertTrue(result['passed'],result)
            self.assertFalse(result['overlap_case']['passed'])
            self.assertEqual(len(list(path.glob('*/trace.jsonl'))),9)
            replay = replay_faults(path)
            self.assertTrue(replay['passed'],replay)

    def test_completed_failed_gate_keeps_cases_fault_reason_and_hashes(self):
        from experiments.phase3 import run_phase3
        from experiments.phase3_cases import cases
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            base = Path(tmp)/'runs'
            with patch('experiments.phase3.command'),patch('experiments.phase3.cases',return_value=[cases(self.p)[0]]), \
                 patch('experiments.kinematic_bench.run_bench',return_value=({'passed':True},[])), \
                 patch('experiments.phase3.run_case',return_value={'passed':False,'status':'failed','error':'injected failed case'}):
                with self.assertRaisesRegex(RuntimeError,'gate failed'):
                    run_phase3(base=base)
            latest = json.loads((base/'latest.json').read_text())
            path = Path(latest['path'])
            result = json.loads((path/'validation.json').read_text())
            self.assertEqual(result['status'],'completed')
            self.assertFalse(result['passed'])
            self.assertIn('cases',result)
            self.assertIsNone(result['next_stage_allowed'])
            self.assertTrue((path/'evidence_hashes.json').is_file())
