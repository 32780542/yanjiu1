"""Independent reconstruction and evidence-tampering regressions for stage 5."""
import copy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

from models.kinematic import KinematicModel, kinematic_state
from perception.road import VisibleRoad
from research.common import ROOT, settings


class Phase5ReplayTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase5_replay'))
        self.model = KinematicModel.from_config()
        self.p = {**self.model.p, **settings('phase3'), **settings('phase4_experiments'),
                  'formation_enabled': False, 'phase5_isolation_stride': 1}
        self.policy = {**self.model.p, **settings('phase4'), 'formation_enabled': False}
        self.road = VisibleRoad((((0., 0.), (2000., 0.)), ((0., 9.9), (2000., 9.9))),
                                (((0., 3.3), (2000., 3.3)), ((0., 6.6), (2000., 6.6))))
        self.initial = {key: kinematic_state(self.model.p, x_m=x, y_m=1.65, vx_mps=v)
                        for key, x, v in [('ego', 300., 15.), ('front', 325., 13.)]}

    def fixture(self, path, failure=False):
        from simulation.noa_clock import ReplayBoundary
        from simulation.formation_clock import FormationClock
        clock = FormationClock(self.initial, self.model, self.road, self.p, self.policy,
                         ['ego'], {'front': {'speed_steps': [[0, 13.]]}})
        rows = [clock.tick()]
        if failure:
            try:
                clock.tick(stop_before=('integration', 'front'))
            except ReplayBoundary:
                rows.append(clock.last_record)
        else:
            rows.append(clock.tick())
        meta = {'model_parameters': dict(self.model.p), 'parameters': self.p,
                'policy_parameters': self.policy, 'road': asdict(self.road),
                'initial': {k: asdict(v) for k, v in self.initial.items()},
                'case': {'controlled': ['ego'], 'scripts': {'front': {'speed_steps': [[0, 13.]]}}},
                'intervals': 2, 'live': False, 'sumo_time_offset_s': 0.,
                'execution_status': 'failed' if failure else 'completed', 'trace_intervals': 2,
                'completed_intervals': 1 if failure else 2,
                'physical_intervals': 1 if failure else 2, 'recorded_intervals': 1 if failure else 2,
                'isolation_intervals': 1 if failure else 2, 'partial_tail': failure}
        if failure:
            meta.update({key: rows[-1][key] for key in ('failure_stage', 'failure_actor')})
            meta['failure_error'] = rows[-1]['error']
        self.write_rows(path, rows)
        return meta, rows

    @staticmethod
    def write_rows(path, rows):
        path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows), encoding='utf-8')

    def test_exact_off_trace_and_failed_prefix_reconstruct(self):
        from experiments.phase5_replay import replay_case
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            for failed in (False, True):
                path = Path(temp)/'trace.jsonl'
                meta, _ = self.fixture(path, failed)
                result = replay_case(meta, path)
                self.assertTrue(result['passed'], result)
                self.assertEqual(result['failed_execution_prefix'], failed)

    def test_action_physics_input_memory_and_truncation_are_rejected(self):
        from experiments.phase5_replay import replay_case
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path = Path(temp)/'trace.jsonl'
            meta, rows = self.fixture(path)
            variants = []
            for field in ('actions', 'steps', 'inputs', 'decisions'):
                changed = copy.deepcopy(rows)
                if field == 'actions': changed[0][field]['ego']['acceleration_mps2'] += .1
                elif field == 'steps': changed[0][field]['ego']['samples'][0]['x_m'] += .1
                elif field == 'inputs': changed[1][field]['ego']['memory']['own_behavior'] = 'FORGED'
                else: changed[0][field]['ego']['memory']['completed_lane_changes'] += 1
                variants.append(changed)
            variants += [rows[:1], rows + [rows[-1]]]
            for index, changed in enumerate(variants):
                with self.subTest(variant=index):
                    self.write_rows(path, changed)
                    self.assertFalse(replay_case(meta, path)['passed'])

    def test_failed_metadata_cannot_relabel_a_completed_trace(self):
        from experiments.phase5_replay import replay_case
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path = Path(temp)/'trace.jsonl'
            meta, _ = self.fixture(path)
            meta['execution_status'] = 'failed'
            self.assertFalse(replay_case(meta, path)['passed'])

    def test_isolation_rebuilds_histories_and_rejects_tampering(self):
        from experiments.phase5_audit import isolation_audit
        from experiments.phase5_replay import replay_isolation
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path, audit = Path(temp)/'trace.jsonl', Path(temp)/'isolation.jsonl'
            meta, rows = self.fixture(path)
            result = isolation_audit(rows, self.model, self.p, self.policy, self.road, ['ego'], audit)
            self.assertTrue(result['passed'], result)
            self.assertGreater(result['visible_neighbor_removal_changes_action'], 0)
            self.assertTrue(replay_isolation(meta, path, audit)['passed'])
            saved = audit.read_text().splitlines()
            audit.write_text('\n'.join(saved[:-1])+'\n')
            self.assertFalse(replay_isolation(meta, path, audit)['passed'])

    def test_manifest_rejects_missing_file_tamper_and_path_escape(self):
        from experiments.phase5_replay import verify_manifest
        from research.common import sha256
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            folder = Path(temp)
            file = folder/'evidence.txt'
            file.write_text('retained evidence')
            digest = sha256(file)
            self.assertEqual(verify_manifest(folder, {'evidence.txt': digest}), [])
            file.write_text('modified evidence')
            self.assertTrue(verify_manifest(folder, {'evidence.txt': digest}))
            self.assertTrue(verify_manifest(folder, {'missing.txt': digest}))
            self.assertTrue(verify_manifest(folder, {'../escape.txt': digest}))

    def test_formation_memory_and_saved_sumo_readback_reconstruct(self):
        from experiments.phase5_replay import replay_case
        from models.geometry import to_sumo_pose
        from models.vehicle import VehicleState
        from simulation.external_bridge import audit_readback
        self.p['formation_enabled'] = self.policy['formation_enabled'] = True
        self.policy.update(settings('phase5'))
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            path = Path(temp)/'trace.jsonl'
            meta, rows = self.fixture(path)
            self.assertIn('formation_weight', rows[0]['inputs']['ego']['memory'])
            meta.update(live=True, sumo_time_offset_s=.1)
            for row in rows:
                row['readback'] = {}
                for key, step in row['steps'].items():
                    final = VehicleState(**step['final'])
                    previous = VehicleState(**step['initial'])
                    x, y, angle = to_sumo_pose(final, self.model.p['length_m'])
                    speed = self.model.observe(final)['speed_mps']
                    accel = (speed-self.model.observe(previous)['speed_mps'])/self.p['control_sync_dt_s']
                    raw = {'sumo_time_s': final.time_s+.1, 'front_x_m': x, 'front_y_m': y,
                           'angle_deg': angle, 'speed_mps': speed, 'acceleration_mps2': accel,
                           'edge_id': 'test', 'lane_id': 'test_0', 'lane_index': 0,
                           'colliding_vehicle_reports': 0, 'teleport_starts': 0}
                    row['readback'][key] = audit_readback(raw, final, self.model, .1, accel)
            self.write_rows(path, rows)
            self.assertTrue(replay_case(meta, path)['passed'])
            rows[0]['readback']['ego']['front_x_m'] += 1.
            self.write_rows(path, rows)
            self.assertFalse(replay_case(meta, path)['passed'])

    def bundle(self, folder):
        from experiments.phase5 import run_phase5
        from experiments.phase5_cases import cases
        case = {**cases(self.model.p)[0], 'duration_s': .2, 'name': 'fixture'}
        with patch('experiments.phase5.cases', return_value=[case]):
            source = run_phase5(base=folder.parent/'original_runs', live=False, sampling=False)
        shutil.copytree(source, folder)
        return folder/'cases'/'fixture_off'

    @staticmethod
    def seal(folder):
        from experiments.records import atomic_json
        from research.common import sha256
        atomic_json(folder/'evidence_hashes.json', {p.relative_to(folder).as_posix(): sha256(p)
            for p in folder.rglob('*') if p.is_file() and p.name != 'evidence_hashes.json'})

    def test_run_requires_explicit_source_and_recomputes_detection(self):
        import experiments.phase5_replay as module
        self.assertTrue(hasattr(module, 'replay_run'), 'Run replay is absent')
        with self.assertRaises((ValueError, TypeError)):
            module.replay_run(None)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            folder = Path(temp)/'source'
            case_dir = self.bundle(folder)
            report = module.replay_run(folder, base=Path(temp)/'replays')
            self.assertTrue(report['passed'], report)
            self.assertFalse(json.loads((folder/'validation.json').read_text())['passed'])
            detected = json.loads((case_dir/'detection.json').read_text())
            detected['default']['success'] = True
            (case_dir/'detection.json').write_text(json.dumps(detected))
            self.seal(folder)
            with self.assertRaisesRegex(RuntimeError, 'replay failed'):
                module.replay_run(folder, base=Path(temp)/'replays')

    def test_run_rejects_code_tamper_and_omitted_manifest_file(self):
        import experiments.phase5_replay as module
        self.assertTrue(hasattr(module, 'replay_run'), 'Run replay is absent')
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            folder = Path(temp)/'source'
            case_dir = self.bundle(folder)
            code = folder/'code_snapshot'/'experiments'/'phase5_detection.py'
            code.write_text(code.read_text()+'\n# tampered snapshot\n')
            self.seal(folder)
            with self.assertRaises(RuntimeError):
                module.replay_run(folder, base=Path(temp)/'replays')
            shutil.copy2(ROOT/'experiments'/'phase5_detection.py', code)
            self.seal(folder)
            hashes = json.loads((folder/'evidence_hashes.json').read_text())
            del hashes['cases/fixture_off/detection.json']
            (folder/'evidence_hashes.json').write_text(json.dumps(hashes))
            with self.assertRaises(RuntimeError):
                module.replay_run(folder, base=Path(temp)/'replays')

    def test_run_replays_per_vehicle_integration_refinement(self):
        from experiments.phase5_replay import replay_run
        from experiments.phase3 import integration_refinement
        from experiments.records import atomic_json
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            folder = Path(temp)/'source'
            case_dir = self.bundle(folder)
            records = [json.loads(row) for row in (case_dir/'trace.jsonl').read_text().splitlines()]
            report, _ = integration_refinement(folder/'integration_half', records, self.model, self.p)
            atomic_json(folder/'sampling.json', {'integration_half': report})
            gate = json.loads((folder/'validation.json').read_text())
            gate['sampling'] = {'integration_half': report}
            atomic_json(folder/'validation.json', gate)
            self.seal(folder)
            try:
                result = replay_run(folder, base=Path(temp)/'replays')
            except RuntimeError as exc:
                self.fail('Valid per-vehicle refinement must reconstruct: '+str(exc))
            self.assertTrue(result['passed'], result)
            self.assertEqual(len(result['integration_refinements']), len(records[0]['initial']))

    def test_real_runner_bundle_with_half_control_and_integration_replays(self):
        from experiments.phase5 import run_phase5
        from experiments.phase5_cases import cases
        from experiments.phase5_replay import replay_run
        case = {**cases(self.model.p)[0], 'duration_s': .2}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp, patch('experiments.phase5.cases', return_value=[case]):
            path = run_phase5(base=Path(temp)/'runs', live=False, sampling=True)
            try:
                result = replay_run(path, base=Path(temp)/'replays')
            except RuntimeError as exc:
                self.fail('Actual runner bundle must replay: '+str(exc))
            self.assertTrue(result['passed'], result)
            self.assertEqual(len(result['cases']), 3)
            self.assertEqual(len(result['integration_refinements']), 3)

    def test_resealed_derived_events_metrics_geometry_and_scientific_gate_are_rejected(self):
        from experiments.phase5_replay import replay_run
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            folder = Path(temp)/'source'
            case_dir = self.bundle(folder)
            case_original = json.loads((case_dir/'validation.json').read_text())
            gate_original = json.loads((folder/'validation.json').read_text())
            events_original = json.loads((case_dir/'events.json').read_text())
            for field in ('events', 'metrics', 'geometry', 'scientific_conditions'):
                with self.subTest(field=field):
                    gate, validation, events = copy.deepcopy(gate_original), copy.deepcopy(case_original), copy.deepcopy(events_original)
                    if field == 'events':
                        events['evolution']['recovered_and_held'] = True
                    elif field == 'scientific_conditions':
                        gate['scientific_conditions']['all_frozen_random_whole_formation'] = True
                    else:
                        validation[field]['forged_result'] = True
                        gate['variants']['fixture_off'] = validation
                    (case_dir/'validation.json').write_text(json.dumps(validation))
                    (folder/'validation.json').write_text(json.dumps(gate))
                    (case_dir/'events.json').write_text(json.dumps(events))
                    self.seal(folder)
                    with self.assertRaises(RuntimeError):
                        replay_run(folder, base=Path(temp)/'replays')

    def test_completed_run_cannot_drop_one_frozen_case_variant(self):
        from experiments.phase5_replay import replay_run
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            folder = Path(temp)/'source'
            self.bundle(folder)
            removed = (folder/'cases'/'fixture_on').resolve()
            self.assertTrue(removed.is_relative_to(Path(temp).resolve()))
            shutil.rmtree(removed)
            gate = json.loads((folder/'validation.json').read_text())
            del gate['variants']['fixture_on']
            (folder/'validation.json').write_text(json.dumps(gate))
            self.seal(folder)
            with self.assertRaises(RuntimeError):
                replay_run(folder, base=Path(temp)/'replays')

    def test_actual_interrupted_package_replays_only_retained_prefixes(self):
        from experiments import phase5
        from experiments.phase5_cases import cases
        from experiments.phase5_replay import replay_run
        case = {**cases(self.model.p)[0], 'duration_s': .2}
        original = phase5.run_case
        def interrupted(path, model, p, policy, case, live=True):
            if p['formation_enabled']:
                with patch.object(model, 'advance', side_effect=KeyboardInterrupt('retained integration interruption')):
                    return original(path, model, p, policy, case, live=live)
            return original(path, model, p, policy, case, live=live)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp, patch('experiments.phase5.cases', return_value=[case]), patch('experiments.phase5.run_case', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                phase5.run_phase5(base=Path(temp)/'runs', live=False, sampling=True)
            source = next(path for path in (Path(temp)/'runs').iterdir() if path.is_dir())
            try:
                report = replay_run(source, base=Path(temp)/'replays')
            except RuntimeError as exc:
                self.fail('Retained completed and failed prefixes must reconstruct: '+str(exc))
            self.assertTrue(report['passed'], report)
            self.assertTrue(report['partial_source_package'])
            self.assertFalse(report['source_driving_gate_passed'])
            self.assertEqual(len(report['unstarted_variants']), 1)
            self.assertTrue(report['cases'][-1]['trace']['failed_execution_prefix'])

    def test_metadata_cannot_relax_the_frozen_replay_tolerance(self):
        from experiments.phase5_replay import replay_run
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            folder = Path(temp)/'source'
            case_dir = self.bundle(folder)
            metadata = json.loads((case_dir/'metadata.json').read_text())
            metadata['model_parameters']['replay_absolute_tolerance'] = .2
            (case_dir/'metadata.json').write_text(json.dumps(metadata))
            rows = [json.loads(line) for line in (case_dir/'trace.jsonl').read_text().splitlines()]
            first = next(iter(rows[0]['actions']))
            rows[0]['actions'][first]['acceleration_mps2'] += .1
            self.write_rows(case_dir/'trace.jsonl', rows)
            self.seal(folder)
            with self.assertRaises(RuntimeError):
                replay_run(folder, base=Path(temp)/'replays')


if __name__ == '__main__':
    unittest.main()
