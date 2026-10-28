import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.common import ROOT


class RunRecordTests(unittest.TestCase):
    def test_completed_scientific_failure_preserves_results_and_hashes(self):
        from experiments import phase2
        from models.vehicle import VehicleState
        from dataclasses import asdict
        case={'name':'deliberately_unrecognized_acceptance_case','initial':asdict(VehicleState(x_m=100,y_m=1.65,vx_mps=20)),
              'duration_s':.1,'reference':{'kind':'constant_actuation','acceleration_mps2':0.,'steering_rad':0.}}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            base=Path(tmp)/'runs'
            original_read=phase2.read_json
            def precondition_fixture(path):
                if str(path)=='results/phase1/foundation_verification.json':
                    return {'passed':True}
                if str(path)=='results/phase1/smoke/validation.json':
                    return {'passed':True,'run_id':'isolated_test_fixture'}
                return original_read(path)
            with patch.object(phase2,'BASE',base),patch('experiments.phase2_cases.cases',return_value=[case]),patch('research.verify.verify'),patch.object(phase2,'read_json',side_effect=precondition_fixture):
                with self.assertRaisesRegex(RuntimeError,'gate failed'):
                    phase2.run_phase2()
            latest=json.loads((base/'latest.json').read_text())
            path=Path(latest['path'])
            result=json.loads((path/'validation.json').read_text())
            self.assertEqual(result['status'],'completed')
            self.assertFalse(result['passed'])
            self.assertEqual(result['cases'][0]['name'],case['name'])
            hashes=json.loads((path/'evidence_hashes.json').read_text())
            self.assertEqual(hashes['validation.json'],phase2.sha256(path/'validation.json'))

    def test_completed_failed_replay_preserves_mismatch_details(self):
        from experiments import phase2
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            root=Path(tmp)
            source=root/'source'
            source.mkdir()
            for name,data in {'metadata.json':{'code_and_config_hashes':{}},
                              'validation.json':{'passed':False,'status':'completed','run_id':'fixture'},
                              'evidence_hashes.json':{}}.items():
                (source/name).write_text(json.dumps(data))
            with patch.object(phase2,'ROOT',root):
                with self.assertRaisesRegex(RuntimeError,'replay failed'):
                    phase2.replay_run(source)
            latest=json.loads((root/'results/phase2/replays/latest.json').read_text())
            report=json.loads((Path(latest['path'])/'validation.json').read_text())
            self.assertEqual(report['status'],'completed')
            self.assertFalse(report['passed'])
            self.assertIn('evidence_hash_mismatches',report)
            self.assertIn('traces',report)

    def test_enter_metadata_failure_is_persisted_with_traceback(self):
        from experiments.records import RunRecord
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            run=RunRecord(Path(tmp),{'bad':float('nan')})
            with self.assertRaises(ValueError):
                with run:
                    pass
            failed=json.loads((run.path/'validation.json').read_text())
            self.assertEqual(failed['status'],'failed')
            self.assertIn('traceback',failed)

    def test_exception_leaves_failure_and_never_reuses_previous_run(self):
        from experiments.records import RunRecord
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            base=Path(tmp)
            with RunRecord(base,{'purpose':'test'}) as first:
                first.finish({'passed':True})
            with self.assertRaisesRegex(RuntimeError,'injected'):
                with RunRecord(base,{'purpose':'test'}) as second:
                    raise RuntimeError('injected interruption')
            self.assertNotEqual(first.path,second.path)
            self.assertTrue(json.loads((first.path/'validation.json').read_text())['passed'])
            failed=json.loads((second.path/'validation.json').read_text())
            self.assertFalse(failed['passed'])
            self.assertEqual(failed['status'],'failed')
            self.assertIn('injected',failed['traceback'])
            self.assertEqual(json.loads((base/'latest.json').read_text())['run_id'],second.run_id)

    def test_unfinished_context_is_explicit_failure(self):
        from experiments.records import RunRecord
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            with self.assertRaisesRegex(RuntimeError,'not finalized'):
                with RunRecord(Path(tmp),{}) as run:
                    pass
            self.assertFalse(json.loads((run.path/'validation.json').read_text())['passed'])

    def test_model_initialization_failure_replaces_latest_success(self):
        from experiments import phase2
        from experiments.records import RunRecord
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            base=Path(tmp)/'runs'
            with RunRecord(base,{}) as previous:
                previous.finish({'passed':True})
            with patch.object(phase2,'BASE',base),patch.object(phase2.VehicleModel,'from_config',side_effect=ValueError('bad model config')):
                with self.assertRaisesRegex(ValueError,'bad model config'):
                    phase2.run_phase2()
            latest=json.loads((base/'latest.json').read_text())
            self.assertNotEqual(latest['run_id'],previous.run_id)
            self.assertFalse(latest['passed'])

    def test_missing_replay_input_replaces_latest_success(self):
        from experiments import phase2
        from experiments.records import RunRecord
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            root=Path(tmp)
            base=root/'results/phase2/replays'
            with RunRecord(base,{}) as previous:
                previous.finish({'passed':True})
            with patch.object(phase2,'ROOT',root):
                with self.assertRaises(FileNotFoundError):
                    phase2.replay_run(root/'missing_run')
            latest=json.loads((base/'latest.json').read_text())
            self.assertNotEqual(latest['run_id'],previous.run_id)
            self.assertFalse(latest['passed'])
