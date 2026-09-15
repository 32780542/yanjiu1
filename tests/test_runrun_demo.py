"""Tests for the user-facing SUMO GUI demonstration entry point."""
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from demo import sumo_gui as gui
import runrun


def make_directory_reparse(link, target):
    if os.name == 'nt':
        subprocess.run(
            ['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)],
            check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


class DemoConfigurationTests(unittest.TestCase):
    def test_project_root_is_independent_of_current_directory(self):
        self.assertEqual(gui.PROJECT_ROOT, Path(__file__).resolve().parents[1])

    def test_default_config_is_valid(self):
        result = gui.validate_config(gui.DemoConfig(), gui.PROJECT_ROOT)
        self.assertEqual(result.sumo_gui.name, 'sumo-gui.exe')
        self.assertEqual(result.network.name, 'bottleneck.net.xml')

    def test_invalid_numeric_and_boolean_values_name_the_variable(self):
        bad = [
            (replace(gui.DemoConfig(), vehicle_count=0), 'VEHICLE_COUNT'),
            (replace(gui.DemoConfig(), vehicle_count=True), 'VEHICLE_COUNT'),
            (replace(gui.DemoConfig(), depart_interval_s=math.nan), 'DEPART_INTERVAL_S'),
            (replace(gui.DemoConfig(), vehicle_speed_mps=40), 'VEHICLE_SPEED_MPS'),
            (replace(gui.DemoConfig(), simulation_duration_s=0), 'SIMULATION_DURATION_S'),
            (replace(gui.DemoConfig(), gui_delay_ms=-1), 'GUI_DELAY_MS'),
            (replace(gui.DemoConfig(), auto_zoom=1), 'AUTO_ZOOM'),
            (replace(gui.DemoConfig(), wait_before_close='yes'), 'WAIT_BEFORE_CLOSE'),
        ]
        for config, name in bad:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, name):
                gui.validate_config(config, gui.PROJECT_ROOT)

    def test_last_departure_must_fit_inside_duration(self):
        config = replace(gui.DemoConfig(), vehicle_count=3, depart_interval_s=10,
                         simulation_duration_s=20)
        with self.assertRaisesRegex(ValueError, 'SIMULATION_DURATION_S'):
            gui.validate_config(config, gui.PROJECT_ROOT)

    def test_missing_registered_binary_names_expected_path(self):
        with tempfile.TemporaryDirectory(dir=gui.PROJECT_ROOT / 'tmp') as tmp:
            root = Path(tmp)
            (root / 'configs').mkdir()
            (root / 'configs/tools.json').write_text(
                '{"sumo_home":"D:/definitely-missing-sumo"}', encoding='utf-8')
            (root / 'scenarios/cai2024').mkdir(parents=True)
            (root / 'scenarios/cai2024/bottleneck.net.xml').write_text('<net/>', encoding='utf-8')
            (root / gui.ALGORITHM_RUN_REL).mkdir(parents=True)
            with self.assertRaisesRegex(FileNotFoundError, 'sumo-gui.exe'):
                gui.validate_config(gui.DemoConfig(), root)


class SimpleFormationConfigurationTests(unittest.TestCase):
    @staticmethod
    def make_clean_simple_root(path):
        root = Path(path)
        sumo_home = root / 'sumo'
        sumo_gui = sumo_home / 'bin' / 'sumo-gui.exe'
        traci_python = sumo_home / 'tools' / 'traci' / '__init__.py'
        network = root / 'scenarios' / 'cai2024' / 'bottleneck.net.xml'
        variant_run = root / gui.SIMPLE_VARIANT_REL / 'run.py'
        for file in (sumo_gui, traci_python, network, variant_run):
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('', encoding='utf-8')
        tools = root / 'configs' / 'tools.json'
        tools.parent.mkdir(parents=True)
        tools.write_text(
            json.dumps({'sumo_home': str(sumo_home)}), encoding='utf-8')
        return root

    def test_defaults_are_the_approved_immutable_simple_formation_values(self):
        expected = {
            'vehicle_count': 6,
            'target_speed_mps': 10.0,
            'random_seed': 1,
            'simulation_duration_s': 45.0,
            'show_gui': True,
            'gui_delay_ms': 40,
            'auto_zoom': True,
            'wait_before_close': True,
            'local_formation_range_m': 90.0,
            'adjacent_lane_gap_m': 15.0,
            'same_lane_gap_m': 30.0,
            'position_tolerance_m': 2.0,
            'formation_accel_limit_mps2': 0.5,
            'max_formation_lane_changes': 1,
        }
        config = gui.SimpleFormationDemoConfig()
        self.assertEqual(
            {name: getattr(config, name) for name in expected}, expected)
        with self.assertRaises(FrozenInstanceError):
            config.vehicle_count = 12

    def test_default_simple_config_resolves_only_current_dependencies(self):
        paths = gui.validate_simple_config(
            gui.SimpleFormationDemoConfig(), gui.PROJECT_ROOT)
        self.assertEqual(paths.variant_root.name, 'phase5g_pure_formation')
        self.assertEqual(paths.variant_run.name, 'run.py')
        self.assertEqual(paths.variant_results.name, 'results')
        self.assertEqual(paths.network.name, 'bottleneck.net.xml')
        self.assertEqual(paths.sumo_gui.name, 'sumo-gui.exe')
        self.assertEqual(paths.traci_python.name, '__init__.py')

    def test_invalid_simple_values_are_rejected_before_path_resolution(self):
        invalid = [
            ('vehicle_count', True, 'VEHICLE_COUNT'),
            ('vehicle_count', 5, 'VEHICLE_COUNT'),
            ('target_speed_mps', True, 'TARGET_SPEED_MPS'),
            ('target_speed_mps', math.nan, 'TARGET_SPEED_MPS'),
            ('random_seed', True, 'RANDOM_SEED'),
            ('random_seed', -1, 'RANDOM_SEED'),
            ('random_seed', 2**64, 'RANDOM_SEED'),
            ('simulation_duration_s', 0.15, 'SIMULATION_DURATION_S'),
            ('show_gui', 1, 'SHOW_GUI'),
            ('gui_delay_ms', True, 'GUI_DELAY_MS'),
            ('gui_delay_ms', -1, 'GUI_DELAY_MS'),
            ('auto_zoom', 1, 'AUTO_ZOOM'),
            ('wait_before_close', 'yes', 'WAIT_BEFORE_CLOSE'),
            ('local_formation_range_m', 0, 'LOCAL_FORMATION_RANGE_M'),
            ('adjacent_lane_gap_m', math.inf, 'ADJACENT_LANE_GAP_M'),
            ('same_lane_gap_m', False, 'SAME_LANE_GAP_M'),
            ('position_tolerance_m', -1, 'POSITION_TOLERANCE_M'),
            ('formation_accel_limit_mps2', math.nan,
             'FORMATION_ACCEL_LIMIT_MPS2'),
            ('max_formation_lane_changes', 2,
             'MAX_FORMATION_LANE_CHANGES'),
            ('max_formation_lane_changes', 1.0,
             'MAX_FORMATION_LANE_CHANGES'),
        ]
        for field, value, label in invalid:
            with self.subTest(field=field, value=value), \
                    self.assertRaisesRegex(ValueError, label):
                gui.validate_simple_config(
                    replace(gui.SimpleFormationDemoConfig(), **{field: value}),
                    gui.PROJECT_ROOT)

    def test_extreme_finite_duration_is_a_named_validation_error(self):
        config = replace(
            gui.SimpleFormationDemoConfig(),
            simulation_duration_s=sys.float_info.max)
        with patch.object(gui.subprocess, 'run') as process, \
                patch.object(gui, 'create_run_directory') as create, \
                self.assertRaisesRegex(ValueError, 'SIMULATION_DURATION_S'):
            gui.run_simple_formation_demo(
                config, gui.PROJECT_ROOT, output_fn=lambda line: None)
        process.assert_not_called()
        create.assert_not_called()

    def test_generation_timeout_budget_is_exact_and_validates_domain(self):
        self.assertEqual(gui.simple_generation_timeout_s(3, 45.0), 198)
        self.assertEqual(gui.simple_generation_timeout_s(6, 45.0), 306)
        self.assertEqual(gui.simple_generation_timeout_s(12, 45.0), 522)
        self.assertGreater(gui.simple_generation_timeout_s(12, 45.0), 411.375)
        for count in (True, 2, 5, 13):
            with self.subTest(count=count), \
                    self.assertRaisesRegex(ValueError, 'VEHICLE_COUNT'):
                gui.simple_generation_timeout_s(count, 45.0)
        for duration in (True, 0, -1.0, math.nan, math.inf):
            with self.subTest(duration=duration), \
                    self.assertRaisesRegex(ValueError, 'SIMULATION_DURATION_S'):
                gui.simple_generation_timeout_s(6, duration)
        with self.assertRaisesRegex(
                ValueError, 'SIMULATION_DURATION_S.*3600'):
            gui.simple_generation_timeout_s(12, 411.375)

    def test_clean_layout_check_accepts_future_results_without_writes_or_process(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_clean_simple_root(temp)
            results = root / gui.SIMPLE_VARIANT_REL / 'results'
            self.assertFalse(results.exists())
            before = sorted(
                item.relative_to(root).as_posix() for item in root.rglob('*'))
            with patch.object(gui.subprocess, 'run') as run, \
                    patch.object(gui.subprocess, 'Popen') as popen, \
                    patch.object(gui, 'create_run_directory') as create:
                report = gui.check_simple_environment(
                    gui.SimpleFormationDemoConfig(), root)
            after = sorted(
                item.relative_to(root).as_posix() for item in root.rglob('*'))
            self.assertEqual(before, after)
            self.assertEqual(Path(report['variant_results']), results.resolve())
            self.assertFalse(results.exists())
            run.assert_not_called()
            popen.assert_not_called()
            create.assert_not_called()

    def test_clean_layout_rejects_reparse_variant_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_clean_simple_root(temp)
            variant = root / gui.SIMPLE_VARIANT_REL
            shutil.rmtree(variant)
            outside = root / 'outside-variant'
            (outside / 'results').mkdir(parents=True)
            (outside / 'run.py').write_text('', encoding='utf-8')
            make_directory_reparse(variant, outside)
            before = sorted(
                item.relative_to(root).as_posix() for item in root.rglob('*'))
            with patch.object(gui.subprocess, 'run') as run, \
                    self.assertRaisesRegex(RuntimeError, 'reparse|junction|符号链接'):
                gui.check_simple_environment(
                    gui.SimpleFormationDemoConfig(), root)
            after = sorted(
                item.relative_to(root).as_posix() for item in root.rglob('*'))
            self.assertEqual(before, after)
            run.assert_not_called()


class NativeArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=gui.PROJECT_ROOT / 'tmp')
        self.root = Path(self.temporary.name)
        self.out = self.root / 'results' / 'demo_runs' / 'attempt'
        self.out.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_native_route_has_exact_unique_vehicles_and_round_robin_lanes(self):
        root = gui.native_routes_tree(replace(gui.DemoConfig(), vehicle_count=7))
        vehicles = root.findall('vehicle')
        self.assertEqual([v.get('id') for v in vehicles], [f'demo_{i:04d}' for i in range(7)])
        self.assertEqual([v.get('departLane') for v in vehicles],
                         ['0', '1', '2', '0', '1', '2', '0'])
        self.assertEqual([float(v.get('depart')) for v in vehicles],
                         [0, .8, 1.6, 2.4, 3.2, 4, 4.8])
        self.assertTrue(all(v.get('departSpeed') == '12' for v in vehicles))
        self.assertEqual(len({v.get('id') for v in vehicles}), 7)
        reparsed = ET.fromstring(ET.tostring(root, encoding='utf-8'))
        self.assertEqual(len(reparsed.findall('vehicle')), 7)

    def test_sumocfg_references_absolute_network_and_local_route(self):
        network = self.root / 'bottleneck.net.xml'
        tree = gui.sumo_config_tree(network, 'native.rou.xml', self.out, 120)
        self.assertEqual(tree.find('input/net-file').get('value'), str(network))
        self.assertEqual(tree.find('input/route-files').get('value'), 'native.rou.xml')
        self.assertEqual(tree.find('time/end').get('value'), '120')
        for filename in ('tripinfo.xml', 'summary.xml', 'lanechanges.xml', 'sumo.log'):
            nodes = [node.get('value') for node in tree.iter() if node.get('value')]
            self.assertIn(str(self.out / filename), nodes)

    def test_new_run_directory_never_reuses_an_old_attempt(self):
        first = gui.create_run_directory(
            self.root, 'native', stamp='20260914T010203000000Z', token='deadbeef')
        self.assertTrue(first.is_dir())
        with self.assertRaises(FileExistsError):
            gui.create_run_directory(
                self.root, 'native', stamp='20260914T010203000000Z', token='deadbeef')


class AlgorithmTraceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=gui.PROJECT_ROOT / 'tmp')
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def state(time_s, x_m):
        return {
            'time_s': time_s, 'x_m': x_m, 'y_m': 1.65, 'heading_rad': 0.0,
            'vx_mps': 5.0, 'vy_mps': 0.0, 'yaw_rate_radps': 0.0,
            'a_drive_mps2': 0.0, 'steering_rad': 0.0,
        }

    def make_source(self, records, evidence_status='failed'):
        trace = self.root / 'trace.jsonl'
        trace.write_text(
            ''.join(json.dumps(record, allow_nan=False) + '\n' for record in records),
            encoding='utf-8')
        return gui.TraceSource(
            case_name='fixture', case_dir=self.root, trace_path=trace,
            metadata={}, validation={}, evidence_status=evidence_status,
            actors=('ego',))

    def test_legacy_trace_frames_remain_readable_from_a_local_fixture(self):
        initial = {'status': 'running', 'initial': {'ego': self.state(0.0, 10.0)}}
        completed = {
            'status': 'completed', 'initial': {'ego': self.state(0.0, 10.0)},
            'steps': {'ego': {'final': self.state(0.1, 10.5), 'samples': []}},
        }
        source = self.make_source([initial, completed], evidence_status='completed')
        frames = gui.iter_trace_frames(source)
        first, second = next(frames), next(frames)
        self.assertEqual(set(first.states), {'ego'})
        self.assertGreater(second.time_s, first.time_s)
        self.assertEqual(source.evidence_status, 'completed')

    def test_unknown_case_is_rejected_before_legacy_evidence_is_read(self):
        with patch.object(gui, 'sha256_file') as digest, \
                self.assertRaisesRegex(ValueError, 'ALGORITHM_CASE'):
            gui.load_trace_source(gui.PROJECT_ROOT, '../missing')
        digest.assert_not_called()

    def test_tampered_trace_is_rejected(self):
        (self.root / 'trace.jsonl').write_text('{}\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            gui.verify_relative_hash(
                self.root, {'trace.jsonl': '0' * 64}, 'trace.jsonl')

    def test_failed_record_yields_only_preserved_completed_prefix(self):
        initial = {'status': 'running', 'initial': {'ego': self.state(0.0, 10.0)}}
        completed = {
            'status': 'completed', 'initial': {'ego': self.state(0.0, 10.0)},
            'steps': {'ego': {'final': self.state(0.1, 10.5), 'samples': []}},
        }
        failed = {
            'status': 'failed', 'initial': {'ego': self.state(0.1, 10.5)},
            'steps': {'ego': {'final': self.state(0.2, 11.0), 'samples': []}},
        }
        source = self.make_source([initial, completed, failed])
        frames = list(gui.iter_trace_frames(source))
        self.assertEqual([frame.time_s for frame in frames], [0.0, 0.1])
        self.assertEqual(source.evidence_status, 'failed')

    def test_trace_actor_or_time_mismatch_is_rejected(self):
        initial = {'status': 'running', 'initial': {'ego': self.state(0.0, 10.0)}}
        wrong = {
            'status': 'completed', 'initial': {'ego': self.state(0.0, 10.0)},
            'steps': {'other': {'final': self.state(0.1, 10.5), 'samples': []}},
        }
        source = self.make_source([initial, wrong])
        with self.assertRaisesRegex(ValueError, '车辆集合'):
            list(gui.iter_trace_frames(source))


class _SimpleTraceFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=gui.PROJECT_ROOT / 'tmp')
        self.root = Path(self.temporary.name).resolve()
        self.variant_root = self.root / 'variants' / 'phase5g_pure_formation'
        self.variant_results = self.variant_root / 'results'
        self.variant_results.mkdir(parents=True)
        self.variant_run = self.variant_root / 'run.py'
        self.variant_run.write_text('# fixture\n', encoding='utf-8')
        self.network = self.root / 'scenarios' / 'cai2024' / 'bottleneck.net.xml'
        self.network.parent.mkdir(parents=True)
        self.network.write_text('<net/>', encoding='utf-8')
        self.sumo_home = self.root / 'sumo'
        self.sumo_gui = self.sumo_home / 'bin' / 'sumo-gui.exe'
        self.traci_python = self.sumo_home / 'tools' / 'traci' / '__init__.py'
        self.sumo_gui.parent.mkdir(parents=True)
        self.traci_python.parent.mkdir(parents=True)
        self.sumo_gui.write_text('', encoding='utf-8')
        self.traci_python.write_text('', encoding='utf-8')
        self.paths = gui.SimpleCheckedPaths(
            root=self.root,
            variant_root=self.variant_root,
            variant_run=self.variant_run,
            variant_results=self.variant_results,
            sumo_home=self.sumo_home,
            sumo_gui=self.sumo_gui,
            network=self.network,
            traci_python=self.traci_python,
        )
        self.config = replace(
            gui.SimpleFormationDemoConfig(), simulation_duration_s=0.1)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def state(time_s, x_m):
        return {
            'time_s': time_s, 'x_m': x_m, 'y_m': 1.65,
            'heading_rad': 0.0, 'vx_mps': 10.0, 'vy_mps': 0.0,
            'yaw_rate_radps': 0.0, 'a_drive_mps2': 0.0,
            'steering_rad': 0.0,
        }

    @staticmethod
    def seal(path):
        files = {
            item.relative_to(path).as_posix(): gui.sha256_file(item)
            for item in sorted(path.rglob('*'))
            if item.is_file() and item != path / 'evidence_hashes.json'
        }
        (path / 'evidence_hashes.json').write_text(
            json.dumps(files, sort_keys=True), encoding='utf-8')

    @staticmethod
    def canonical_digest(value):
        encoded = (json.dumps(
            value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
            allow_nan=False) + '\n').encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def snapshot_manifest(path):
        return {
            item.relative_to(path).as_posix(): {
                'sha256': gui.sha256_file(item), 'type': 'regular'}
            for item in sorted(path.rglob('*')) if item.is_file()
        }

    def write_completion_anchor(self, outer):
        trust = outer.parent / '.phase5g-trust'
        source_path = trust / f'{outer.name}.json'
        source = json.loads(source_path.read_text(encoding='utf-8'))
        evidence_path = outer / 'evidence_hashes.json'
        evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
        child_manifest = self.snapshot_manifest(outer / 'case')
        completion = {
            'schema': 'phase5g_simple_demo_completion_anchor_v1',
            'run_id': outer.name,
            'outer_schema': 'phase5g_simple_demo_v1',
            'source_anchor_schema': 'phase5g_external_trust_anchor_v2',
            'source_anchor_sha256': gui.sha256_file(source_path),
            'source_manifest_sha256': source['source_manifest_sha256'],
            'input_manifest_sha256': source['input_manifest_sha256'],
            'child_directory': 'case',
            'child_manifest': child_manifest,
            'child_manifest_sha256': self.canonical_digest(child_manifest),
            'outer_evidence_hashes': evidence,
            'outer_evidence_manifest_sha256': self.canonical_digest(evidence),
            'outer_evidence_file_sha256': gui.sha256_file(evidence_path),
        }
        (trust / f'{outer.name}.completion.json').write_text(
            json.dumps(completion, sort_keys=True), encoding='utf-8')

    def reseal_trusted(self, outer):
        self.seal(outer / 'case')
        self.seal(outer)
        self.write_completion_anchor(outer)

    def make_outer(self, name='fresh'):
        outer = self.variant_results / 'phase5g' / 'simple_gui_sources' / name
        case = outer / 'case'
        case.mkdir(parents=True)
        actors = [f'v{index}' for index in range(self.config.vehicle_count)]
        initial = {
            actor: self.state(0.0, 100.0 + index * 15.0)
            for index, actor in enumerate(actors)
        }
        simple_parameters = {
            'simple_formation_local_range_m':
                self.config.local_formation_range_m,
            'simple_formation_adjacent_gap_m':
                self.config.adjacent_lane_gap_m,
            'simple_formation_same_gap_m': self.config.same_lane_gap_m,
            'simple_formation_position_tolerance_m':
                self.config.position_tolerance_m,
            'simple_formation_accel_limit_mps2':
                self.config.formation_accel_limit_mps2,
            'simple_formation_max_lane_changes':
                self.config.max_formation_lane_changes,
        }
        private_rng_provenance = {
            'algorithm': 'SplitMix64', 'version': 1,
            'source': (
                'sha256_case_seed_vehicle_count_and_stable_physical_ordinal_v1'),
            'case_seed': self.config.random_seed,
            'vehicle_count': self.config.vehicle_count,
            'states_by_actor': {
                actor: index + 1 for index, actor in enumerate(actors)},
            'stable_ordinal_by_actor': {
                actor: index for index, actor in enumerate(actors)},
            'actor_identity_used': False, 'online_initialization': False,
        }
        case_payload = {
            'name': 'main_6_3_2_1', 'controlled': actors,
            'duration_s': self.config.simulation_duration_s,
            'initial': initial, 'scripts': {},
            'private_rng_provenance': private_rng_provenance,
        }
        execution = {
            'schema': 'phase5g_simple_demo_execution_v1',
            'case_directory': 'case', 'parent_run_id': outer.name,
            'output_nonce': '1' * 32, 'case_name': case_payload['name'],
            'mode': 'lane_priority',
            'vehicle_count': self.config.vehicle_count,
            'case_seed': self.config.random_seed,
            'target_speed_mps': self.config.target_speed_mps,
            'duration_s': self.config.simulation_duration_s,
            'simple_formation_enabled': True,
            'simple_parameters': simple_parameters,
            'physical_input_sha256': '2' * 64,
            'case_input_sha256': '3' * 64,
            'parameters_input_sha256': '4' * 64,
            'initial_memories_sha256': '5' * 64,
        }
        intervals = round(self.config.simulation_duration_s / 0.1)
        records = []
        current = initial
        for step in range(1, intervals + 1):
            time_s = step * 0.1
            final = {
                actor: self.state(
                    time_s, 100.0 + index * 15.0 + time_s * 10.0)
                for index, actor in enumerate(actors)
            }
            steps = {}
            for index, actor in enumerate(actors):
                samples = [
                    self.state(
                        (step - 1) * 0.1 + sample_index * 0.01,
                        100.0 + index * 15.0
                        + ((step - 1) * 0.1 + sample_index * 0.01) * 10.0)
                    for sample_index in range(1, 10)
                ]
                samples.append(final[actor])
                steps[actor] = {
                    'initial': current[actor], 'final': final[actor],
                    'samples': samples,
                    'command': {
                        'acceleration_mps2': 0.0, 'steering_rad': 0.0},
                    'dt_s': 0.01,
                }
            records.append({
                'status': 'completed', 'initial': current,
                'inputs': {}, 'decisions': {}, 'actions': {},
                'diagnostics': {}, 'readback': None,
                'steps': steps,
            })
            current = final
        (case / 'trace.jsonl').write_text(
            ''.join(json.dumps(record) + '\n' for record in records),
            encoding='utf-8')
        (case / 'metadata.json').write_text(json.dumps({
            'schema': 'phase5g_variant_v1', 'mode': 'lane_priority',
            'formal': False, 'live': False, 'lifecycle_status': 'finalized',
            'execution_status': 'completed',
            'intervals': intervals, 'trace_intervals': intervals,
            'initial': initial,
            'case': case_payload,
            'parameters': {
                'length_m': 4.0, 'control_sync_dt_s': 0.1,
                'dynamics_dt_s': 0.01,
                'noa_target_speed_mps': self.config.target_speed_mps,
                'simple_formation_enabled': True,
                **simple_parameters,
            },
            'policy_parameters': {
                'noa_target_speed_mps': self.config.target_speed_mps,
                'simple_formation_enabled': True,
                **simple_parameters,
            },
            'private_rng_provenance': private_rng_provenance,
            'parent_run_id': outer.name,
        }), encoding='utf-8')
        (case / 'validation.json').write_text(json.dumps({
            'status': 'completed', 'passed': True,
            'sealed': True, 'recording_passed': True,
        }), encoding='utf-8')
        self.seal(case)
        code_snapshot = outer / 'code_snapshot'
        input_snapshot = outer / 'input_snapshot'
        (code_snapshot / 'noa').mkdir(parents=True)
        (code_snapshot / 'configs').mkdir(parents=True)
        (input_snapshot / 'configs').mkdir(parents=True)
        (code_snapshot / 'noa/simple_formation.py').write_text(
            '# trusted fixture\n', encoding='utf-8')
        (code_snapshot / 'configs/phase5g.json').write_text(
            '{}\n', encoding='utf-8')
        (input_snapshot / 'configs/phase5g.json').write_text(
            '{}\n', encoding='utf-8')
        input_bundle = {
            'schema': 'phase5g_simple_demo_cases_v1',
            'cases': [case_payload], 'execution': execution,
        }
        (input_snapshot / 'phase5g_cases.json').write_text(
            json.dumps(
                input_bundle, sort_keys=True, separators=(',', ':'),
                ensure_ascii=False) + '\n', encoding='utf-8')
        code_manifest = self.snapshot_manifest(code_snapshot)
        input_manifest = self.snapshot_manifest(input_snapshot)
        source_hashes = {
            'noa/simple_formation.py':
                code_manifest['noa/simple_formation.py']['sha256'],
        }
        input_hashes = {
            name: entry['sha256'] for name, entry in input_manifest.items()
        }
        (outer / 'code_hashes.json').write_text(
            json.dumps(source_hashes, sort_keys=True), encoding='utf-8')
        (outer / 'input_hashes.json').write_text(
            json.dumps(input_hashes, sort_keys=True), encoding='utf-8')
        (outer / 'code_snapshot_manifest.json').write_text(
            json.dumps(code_manifest, sort_keys=True), encoding='utf-8')
        (outer / 'input_snapshot_manifest.json').write_text(
            json.dumps(input_manifest, sort_keys=True), encoding='utf-8')
        mode_registry = {
            'off': {'formation_enabled': False,
                    'formation_lane_change_enabled': False},
            'longitudinal': {'formation_enabled': True,
                             'formation_lane_change_enabled': False},
            'lane_priority': {'formation_enabled': True,
                              'formation_lane_change_enabled': True},
        }
        case_file_sha = input_hashes['phase5g_cases.json']
        (outer / 'metadata.json').write_text(json.dumps({
            'schema': 'phase5g_simple_demo_v1', 'formal': False,
            'run_id': outer.name,
            'mode': 'lane_priority', 'simple_formation_enabled': True,
            'vehicle_count': self.config.vehicle_count,
            'seed': self.config.random_seed,
            'target_speed_mps': self.config.target_speed_mps,
            'duration_s': self.config.simulation_duration_s,
            'simple_parameters': simple_parameters,
            'case_file_sha256': case_file_sha,
            'mode_registry': mode_registry,
            'execution': execution,
            'case_directory': 'case',
        }), encoding='utf-8')
        (outer / 'validation.json').write_text(json.dumps({
            'run_id': outer.name, 'status': 'completed', 'passed': True,
            'complete_execution': True, 'engineering_passed': True,
            'formal': False, 'mode': 'lane_priority',
            'case_directory': 'case',
        }), encoding='utf-8')
        self.seal(outer)
        trust = outer.parent / '.phase5g-trust'
        trust.mkdir(exist_ok=True)
        source_anchor = {
            'schema': 'phase5g_external_trust_anchor_v2',
            'run_id': outer.name,
            'source_manifest_sha256': self.canonical_digest(code_manifest),
            'input_manifest_sha256': self.canonical_digest(input_manifest),
            'source_hashes': source_hashes,
            'input_hashes': input_hashes,
            'code_snapshot_manifest': code_manifest,
            'input_snapshot_manifest': input_manifest,
            'case_file_sha256': case_file_sha,
            'mode_registry_sha256': self.canonical_digest(mode_registry),
        }
        (trust / f'{outer.name}.json').write_text(
            json.dumps(source_anchor, sort_keys=True), encoding='utf-8')
        self.write_completion_anchor(outer)
        return outer

    def assert_trust_failure_before_child(self, outer, pattern):
        original_read = gui._read_json
        original_strict_read = gui._read_strict_object

        def guarded_read(path):
            candidate = Path(path).resolve()
            if candidate.is_relative_to((outer / 'case').resolve()):
                raise AssertionError(f'信任验证前读取了child JSON: {candidate}')
            return original_read(path)

        def guarded_strict_read(path, *args, **kwargs):
            candidate = Path(path).resolve()
            if candidate.is_relative_to((outer / 'case').resolve()):
                raise AssertionError(f'信任验证前读取了child JSON: {candidate}')
            return original_strict_read(path, *args, **kwargs)

        completed = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({'path': str(outer)}), stderr='')
        with patch.object(gui, 'validate_simple_config', return_value=self.paths), \
                patch.object(gui.subprocess, 'run', return_value=completed), \
                patch.object(gui, '_read_json', side_effect=guarded_read), \
                patch.object(
                    gui, '_read_strict_object', side_effect=guarded_strict_read), \
                patch.object(gui, 'create_run_directory') as create, \
                patch.object(gui.subprocess, 'Popen') as popen, \
                self.assertRaisesRegex(RuntimeError, pattern):
            gui.run_simple_formation_demo(
                self.config, self.root, output_fn=lambda line: None)
        create.assert_not_called()
        popen.assert_not_called()

    def assert_trace_failure_before_gui(self, outer, pattern):
        completed = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({'path': str(outer)}), stderr='')
        with patch.object(gui, 'validate_simple_config', return_value=self.paths), \
                patch.object(gui.subprocess, 'run', return_value=completed), \
                patch.object(gui, 'create_run_directory') as create, \
                patch.object(gui.subprocess, 'Popen') as popen, \
                self.assertRaisesRegex(RuntimeError, pattern):
            gui.run_simple_formation_demo(
                self.config, self.root, output_fn=lambda line: None)
        create.assert_not_called()
        popen.assert_not_called()

    def assert_loader_failure_before_gui(self, outer, pattern):
        with patch.object(gui, 'create_run_directory') as create, \
                patch.object(gui.subprocess, 'Popen') as popen, \
                self.assertRaisesRegex(RuntimeError, pattern):
            gui.load_simple_trace_source(outer, self.paths, self.config)
        create.assert_not_called()
        popen.assert_not_called()

    def trace_records(self, outer):
        return [json.loads(line) for line in (
            outer / 'case' / 'trace.jsonl').read_text(
                encoding='utf-8').splitlines()]

    def write_trusted_trace(self, outer, records):
        (outer / 'case' / 'trace.jsonl').write_text(
            ''.join(json.dumps(record, allow_nan=True) + '\n' for record in records),
            encoding='utf-8')
        self.reseal_trusted(outer)


class SimpleTraceGenerationTests(_SimpleTraceFixture, unittest.TestCase):
    def test_missing_source_or_completion_anchor_fails_before_child_json(self):
        source_missing = self.make_outer('missing-source-anchor')
        trust = source_missing.parent / '.phase5g-trust'
        (trust / f'{source_missing.name}.json').unlink()
        self.assert_trust_failure_before_child(source_missing, 'source anchor.*缺失')

        completion_missing = self.make_outer('missing-completion-anchor')
        (trust / f'{completion_missing.name}.completion.json').unlink()
        self.assert_trust_failure_before_child(
            completion_missing, 'completion anchor.*缺失')

    def test_tampered_source_anchor_and_exact_fields_are_rejected(self):
        for index, operation in enumerate(('tamper', 'extra', 'missing')):
            with self.subTest(operation=operation):
                outer = self.make_outer(f'anchor-{index}')
                anchor_path = (
                    outer.parent / '.phase5g-trust' / f'{outer.name}.json')
                anchor = json.loads(anchor_path.read_text(encoding='utf-8'))
                if operation == 'tamper':
                    anchor['source_manifest_sha256'] = '0' * 64
                    pattern = 'source anchor.*SHA-256'
                elif operation == 'extra':
                    anchor['unexpected'] = True
                    pattern = 'source anchor.*额外字段'
                else:
                    del anchor['input_hashes']
                    pattern = 'source anchor.*缺少字段'
                anchor_path.write_text(json.dumps(anchor), encoding='utf-8')
                self.assert_trust_failure_before_child(outer, pattern)

    def test_completion_anchor_tamper_and_exact_fields_are_rejected(self):
        for index, operation in enumerate(('tamper', 'extra', 'missing')):
            with self.subTest(operation=operation):
                outer = self.make_outer(f'completion-{index}')
                completion_path = (
                    outer.parent / '.phase5g-trust'
                    / f'{outer.name}.completion.json')
                completion = json.loads(
                    completion_path.read_text(encoding='utf-8'))
                if operation == 'tamper':
                    completion['source_anchor_sha256'] = '0' * 64
                    pattern = 'completion anchor.*source anchor SHA-256'
                elif operation == 'extra':
                    completion['unexpected'] = True
                    pattern = 'completion anchor.*额外字段'
                else:
                    del completion['child_manifest']
                    pattern = 'completion anchor.*缺少字段'
                completion_path.write_text(
                    json.dumps(completion), encoding='utf-8')
                self.assert_trust_failure_before_child(outer, pattern)

    def test_tampered_or_swapped_child_is_rejected_even_after_resealing(self):
        tampered = self.make_outer('tampered-child')
        trace = tampered / 'case' / 'trace.jsonl'
        trace.write_text(
            trace.read_text(encoding='utf-8').replace('101.0', '102.0', 1),
            encoding='utf-8')
        self.seal(tampered / 'case')
        self.seal(tampered)
        self.assert_trust_failure_before_child(
            tampered, 'completion anchor.*child manifest')

        original = self.make_outer('swap-target')
        donor = self.make_outer('swap-donor')
        donor_trace = donor / 'case' / 'trace.jsonl'
        donor_trace.write_text(
            donor_trace.read_text(encoding='utf-8').replace('101.0', '103.0', 1),
            encoding='utf-8')
        self.reseal_trusted(donor)
        shutil.rmtree(original / 'case')
        shutil.copytree(donor / 'case', original / 'case')
        self.seal(original)
        self.assert_trust_failure_before_child(
            original, 'completion anchor.*child manifest')

    def test_snapshot_tamper_is_not_accepted(self):
        outer = self.make_outer('snapshot-tamper')
        source = outer / 'code_snapshot' / 'noa' / 'simple_formation.py'
        source.write_text('# changed\n', encoding='utf-8')
        self.seal(outer)
        self.write_completion_anchor(outer)
        self.assert_trust_failure_before_child(outer, 'code snapshot')

    def test_outer_reparse_is_rejected_before_resolve_and_child_read(self):
        outer = self.make_outer('outer-reparse')
        outer_info = os.lstat(outer)
        original_is_reparse = gui._is_reparse

        def mark_outer_reparse(info):
            if (getattr(info, 'st_dev', None), getattr(info, 'st_ino', None)) == (
                    outer_info.st_dev, outer_info.st_ino):
                return True
            return original_is_reparse(info)

        with patch.object(gui, '_is_reparse', side_effect=mark_outer_reparse):
            self.assert_trust_failure_before_child(
                outer, '结果路径.*reparse')

    def test_playback_uses_the_exact_trace_text_that_preflight_validated(self):
        outer = self.make_outer('immutable-preflight')
        source = gui.load_simple_trace_source(outer, self.paths, self.config)
        expected_digest = source.trace_sha256
        self.assertFalse(hasattr(source, 'verified_trace_bytes'))
        self.assertIsInstance(source.frames, tuple)
        self.assertEqual(len(source.frames), 2)
        with self.assertRaises(FrozenInstanceError):
            source.frames[0].states['v0'].x_m = -1.0
        records = self.trace_records(outer)
        records[0]['steps']['v0']['final']['x_m'] = -99.0
        records[0]['steps']['v0']['samples'][-1]['x_m'] = -99.0
        (outer / 'case' / 'trace.jsonl').write_text(
            ''.join(json.dumps(record) + '\n' for record in records),
            encoding='utf-8')

        with patch.object(
                Path, 'open', side_effect=AssertionError('reopened trace disk')):
            frames = list(gui.iter_trace_frames(source))
        self.assertIs(frames[0], source.frames[0])
        self.assertEqual(frames[1].states['v0']['x_m'], 101.0)
        self.assertEqual(source.trace_sha256, expected_digest)

    def test_full_duration_source_has_451_frozen_control_frames(self):
        self.config = gui.SimpleFormationDemoConfig()
        outer = self.make_outer('full-duration-frames')
        source = gui.load_simple_trace_source(outer, self.paths, self.config)
        self.assertIsInstance(source.frames, tuple)
        self.assertEqual(len(source.frames), 451)
        self.assertEqual(source.frames[0].time_s, 0.0)
        self.assertEqual(source.frames[-1].time_s, 45.0)
        self.assertEqual(tuple(source.frames[0].states), source.actors)

    def test_trusted_json_files_are_each_opened_once_for_hash_and_parse(self):
        outer = self.make_outer('single-read-json')
        trust = outer.parent / '.phase5g-trust'
        targets = tuple(path.resolve() for path in (
            trust / f'{outer.name}.json',
            trust / f'{outer.name}.completion.json',
            outer / 'metadata.json', outer / 'validation.json',
            outer / 'case' / 'metadata.json',
            outer / 'case' / 'validation.json',
            outer / 'code_snapshot_manifest.json',
            outer / 'input_snapshot_manifest.json',
            outer / 'code_hashes.json', outer / 'input_hashes.json',
            outer / 'input_snapshot' / 'phase5g_cases.json',
            outer / 'evidence_hashes.json',
            outer / 'case' / 'evidence_hashes.json',
            outer / 'case' / 'trace.jsonl',
        ))
        counts = {path: 0 for path in targets}
        original_open = Path.open

        def counting_open(path, *args, **kwargs):
            resolved = Path(path).resolve()
            if resolved in counts:
                counts[resolved] += 1
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', new=counting_open):
            gui.load_simple_trace_source(outer, self.paths, self.config)
        for path, count in counts.items():
            with self.subTest(path=path):
                self.assertEqual(count, 1)

    def test_outer_metadata_consumes_the_same_bytes_that_were_hashed(self):
        outer = self.make_outer('replace-between-hash-and-parse')
        target = (outer / 'metadata.json').resolve()
        original = target.read_bytes()
        replacement = json.loads(original.decode('utf-8'))
        replacement['diagnostic_marker'] = 'unverified replacement'
        replacement_bytes = json.dumps(replacement).encode('utf-8')
        original_open = Path.open
        open_count = 0

        def replacing_open(path, mode='r', *args, **kwargs):
            nonlocal open_count
            if Path(path).resolve() == target:
                open_count += 1
                if open_count > 1:
                    if 'b' in mode:
                        return io.BytesIO(replacement_bytes)
                    return io.StringIO(replacement_bytes.decode('utf-8'))
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', new=replacing_open):
            source = gui.load_simple_trace_source(
                outer, self.paths, self.config)
        self.assertEqual(open_count, 1)
        self.assertNotIn('diagnostic_marker', source.metadata)

    def test_trace_requires_exact_nine_field_vehicle_states(self):
        mutations = {
            'missing-yaw': lambda record: (
                record['initial']['v0'].pop('yaw_rate_radps'),
                record['steps']['v0']['initial'].pop('yaw_rate_radps')),
            'extra-state-field': lambda record: (
                record['steps']['v0']['final'].update(extra=0.0),
                record['steps']['v0']['samples'][-1].update(extra=0.0)),
            'bool-steering': lambda record: (
                record['steps']['v0']['final'].update(steering_rad=True),
                record['steps']['v0']['samples'][-1].update(steering_rad=True)),
        }
        patterns = {
            'missing-yaw': 'yaw_rate_radps',
            'extra-state-field': '字段.*精确|额外',
            'bool-steering': 'steering_rad.*exact int/float',
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                outer = self.make_outer(f'exact-state-{name}')
                records = self.trace_records(outer)
                mutate(records[0])
                self.write_trusted_trace(outer, records)
                self.assert_trace_failure_before_gui(outer, patterns[name])

    def test_trace_requires_exact_step_and_command_schema(self):
        mutations = {
            'extra-step': lambda step: step.update(extra={}),
            'missing-command-field': lambda step: step['command'].pop(
                'acceleration_mps2'),
            'extra-command-field': lambda step: step['command'].update(extra=0.0),
            'bool-command': lambda step: step['command'].update(
                acceleration_mps2=True),
        }
        patterns = {
            'extra-step': 'step.*字段',
            'missing-command-field': 'command.*acceleration_mps2',
            'extra-command-field': 'command.*字段',
            'bool-command': 'acceleration_mps2.*exact int/float',
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                outer = self.make_outer(f'exact-step-{name}')
                records = self.trace_records(outer)
                mutate(records[0]['steps']['v0'])
                self.write_trusted_trace(outer, records)
                self.assert_trace_failure_before_gui(outer, patterns[name])

    def test_real_dynamics_dt_samples_fill_each_control_interval(self):
        outer = self.make_outer('real-dynamics-dt')
        source = gui.load_simple_trace_source(outer, self.paths, self.config)
        self.assertEqual(source.trace_sha256, gui.sha256_file(source.trace_path))

    def test_trace_rejects_incomplete_or_misaligned_dynamics_samples(self):
        missing_sample = self.make_outer('missing-dynamics-sample')
        records = self.trace_records(missing_sample)
        for step in records[0]['steps'].values():
            del step['samples'][4]
        self.write_trusted_trace(missing_sample, records)
        self.assert_trace_failure_before_gui(
            missing_sample, '样本.*完整|dynamics')

        misaligned_sample = self.make_outer('misaligned-dynamics-sample')
        records = self.trace_records(misaligned_sample)
        for step in records[0]['steps'].values():
            step['samples'][0]['time_s'] = 0.015
        self.write_trusted_trace(misaligned_sample, records)
        self.assert_trace_failure_before_gui(
            misaligned_sample, 'dynamics|样本.*间隔')

    def test_trace_requires_positive_dynamics_dt_parameter(self):
        for index, value in enumerate((None, True, 0.0, math.nan)):
            with self.subTest(value=value):
                outer = self.make_outer(f'bad-dynamics-dt-{index}')
                metadata_path = outer / 'case' / 'metadata.json'
                metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                if value is None:
                    del metadata['parameters']['dynamics_dt_s']
                else:
                    metadata['parameters']['dynamics_dt_s'] = value
                metadata_path.write_text(
                    json.dumps(metadata, allow_nan=True), encoding='utf-8')
                self.reseal_trusted(outer)
                self.assert_trace_failure_before_gui(
                    outer, 'dynamics_dt_s|非有限JSON')

    def test_completed_record_requires_gui_dependency_containers(self):
        mutations = {
            'missing-inputs': lambda record: record.pop('inputs'),
            'bad-decisions': lambda record: record.update(decisions=[]),
            'bad-diagnostics': lambda record: record.update(diagnostics=None),
            'bad-actions': lambda record: record.update(actions='bad'),
            'bad-readback': lambda record: record.update(readback=[]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                outer = self.make_outer(f'record-container-{name}')
                records = self.trace_records(outer)
                mutate(records[0])
                self.write_trusted_trace(outer, records)
                self.assert_trace_failure_before_gui(
                    outer, 'inputs|decisions|diagnostics|actions|readback')

    def test_outer_and_child_metadata_json_must_be_objects(self):
        targets = (
            ('outer-metadata', 'metadata.json'),
            ('outer-validation', 'validation.json'),
            ('child-metadata', 'case/metadata.json'),
            ('child-validation', 'case/validation.json'),
        )
        for index, (name, relative) in enumerate(targets):
            for payload in ([], None):
                with self.subTest(name=name, payload=payload):
                    outer = self.make_outer(f'object-{index}-{payload is None}')
                    (outer / relative).write_text(
                        json.dumps(payload), encoding='utf-8')
                    self.reseal_trusted(outer)
                    self.assert_trace_failure_before_gui(outer, 'JSON对象')

    def test_metadata_requires_bound_schema_status_and_exact_types(self):
        mutations = {
            'outer-missing-schema': (
                'metadata.json', lambda value: value.pop('schema'), 'schema'),
            'child-missing-schema': (
                'case/metadata.json', lambda value: value.pop('schema'), 'schema'),
            'outer-bool-seed': (
                'metadata.json', lambda value: value.update(seed=True), 'seed'),
            'outer-bad-run-id': (
                'validation.json', lambda value: value.update(run_id=1), 'run_id'),
            'child-false-as-int': (
                'case/metadata.json', lambda value: value.update(formal=0), 'formal'),
            'child-true-as-int': (
                'case/validation.json',
                lambda value: value.update(recording_passed=1),
                'recording_passed'),
        }
        for name, (relative, mutate, pattern) in mutations.items():
            with self.subTest(name=name):
                outer = self.make_outer(f'metadata-{name}')
                path = outer / relative
                value = json.loads(path.read_text(encoding='utf-8'))
                mutate(value)
                path.write_text(json.dumps(value), encoding='utf-8')
                self.reseal_trusted(outer)
                self.assert_trace_failure_before_gui(outer, pattern)

    def test_child_execution_parameters_are_bound_to_anchored_input(self):
        simple_fields = (
            'simple_formation_local_range_m',
            'simple_formation_adjacent_gap_m',
            'simple_formation_same_gap_m',
            'simple_formation_position_tolerance_m',
            'simple_formation_accel_limit_mps2',
            'simple_formation_max_lane_changes',
        )
        mutations = [
            (container, field, 2 if field.endswith('lane_changes') else 99.0)
            for container in ('parameters', 'policy_parameters')
            for field in simple_fields
        ]
        mutations.extend((
            ('parameters', 'simple_formation_enabled', False),
            ('policy_parameters', 'simple_formation_enabled', False),
            ('parameters', 'noa_target_speed_mps', 11.0),
            ('policy_parameters', 'noa_target_speed_mps', 11.0),
        ))
        for index, (container, field, replacement) in enumerate(mutations):
            with self.subTest(container=container, field=field):
                outer = self.make_outer(f'child-parameter-{index}')
                metadata_path = outer / 'case' / 'metadata.json'
                metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                metadata[container][field] = replacement
                metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
                self.reseal_trusted(outer)
                self.assert_loader_failure_before_gui(outer, field)

        for index, field in enumerate(('case_seed', 'vehicle_count')):
            with self.subTest(field=field):
                outer = self.make_outer(f'child-provenance-{index}')
                metadata_path = outer / 'case' / 'metadata.json'
                metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                metadata['case']['private_rng_provenance'][field] += 1
                metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
                self.reseal_trusted(outer)
                self.assert_loader_failure_before_gui(outer, field)

    def test_trace_requires_json_objects_and_completed_frame_structure(self):
        invalid_rows = (
            ('array', '必须是JSON对象'),
            ('null', '必须是JSON对象'),
            ('string', '必须是JSON对象'),
            ('status', '必须是completed'),
            ('steps', 'steps'),
        )
        for index, (kind, pattern) in enumerate(invalid_rows):
            with self.subTest(index=index):
                outer = self.make_outer(f'bad-record-{index}')
                valid = self.trace_records(outer)[0]
                record = {
                    'array': [], 'null': None, 'string': 'record',
                    'status': {**valid, 'status': 'running'},
                    'steps': {**valid, 'steps': None},
                }[kind]
                self.write_trusted_trace(outer, [record])
                self.assert_trace_failure_before_gui(outer, pattern)

    def test_trace_rejects_missing_or_nonfinite_required_state_values(self):
        required = (
            'time_s', 'x_m', 'y_m', 'heading_rad', 'vx_mps', 'vy_mps')
        for index, field in enumerate(required):
            with self.subTest(field=field):
                outer = self.make_outer(f'missing-state-{index}')
                records = self.trace_records(outer)
                del records[0]['steps']['v0']['final'][field]
                self.write_trusted_trace(outer, records)
                self.assert_trace_failure_before_gui(outer, field)

        invalid = (True, math.nan, math.inf, -math.inf)
        for index, value in enumerate(invalid):
            with self.subTest(value=value):
                outer = self.make_outer(f'bad-number-{index}')
                records = self.trace_records(outer)
                records[0]['steps']['v0']['final']['x_m'] = value
                self.write_trusted_trace(outer, records)
                self.assert_trace_failure_before_gui(
                    outer, 'x_m.*有限数字|JSON常量')

    def test_trace_rejects_invalid_actor_step_states(self):
        mutations = {
            'empty-samples': (
                lambda step: step.update(samples=[]), '样本'),
            'nonobject-sample': (
                lambda step: step['samples'].__setitem__(0, None), 'JSON对象'),
            'bad-sample-number': (
                lambda step: step['samples'][0].update(x_m=True),
                'exact int/float'),
            'missing-step-initial': (
                lambda step: step.pop('initial'), 'initial'),
            'mismatched-step-initial': (
                lambda step: step['initial'].update(x_m=-1.0), 'initial'),
            'final-not-last-sample': (
                lambda step: step['samples'][-1].update(x_m=-1.0), 'final'),
        }
        for name, (mutate, pattern) in mutations.items():
            with self.subTest(name=name):
                outer = self.make_outer(f'bad-step-{name}')
                records = self.trace_records(outer)
                mutate(records[0]['steps']['v0'])
                self.write_trusted_trace(outer, records)
                self.assert_trace_failure_before_gui(outer, pattern)

    def test_trace_rejects_actor_and_time_contract_violations(self):
        missing_actor = self.make_outer('missing-actor')
        records = self.trace_records(missing_actor)
        del records[0]['steps']['v0']
        self.write_trusted_trace(missing_actor, records)
        self.assert_trace_failure_before_gui(missing_actor, '车辆集合')

        mismatched_time = self.make_outer('mismatched-time')
        records = self.trace_records(mismatched_time)
        records[0]['steps']['v0']['final']['time_s'] = 0.2
        records[0]['steps']['v0']['samples'][-1]['time_s'] = 0.2
        self.write_trusted_trace(mismatched_time, records)
        self.assert_trace_failure_before_gui(mismatched_time, '时间')

        self.config = replace(self.config, simulation_duration_s=0.2)
        nonmonotonic = self.make_outer('nonmonotonic-time')
        records = self.trace_records(nonmonotonic)
        for step in records[1]['steps'].values():
            step['final']['time_s'] = 0.1
            step['samples'][-1]['time_s'] = 0.1
        self.write_trusted_trace(nonmonotonic, records)
        self.assert_trace_failure_before_gui(
            nonmonotonic, '严格递增|控制周期|dynamics dt间隔')

        discontinuous = self.make_outer('discontinuous-state')
        self.config = replace(self.config, simulation_duration_s=0.2)
        records = self.trace_records(discontinuous)
        records[1]['initial']['v0']['x_m'] = -1.0
        records[1]['steps']['v0']['initial']['x_m'] = -1.0
        self.write_trusted_trace(discontinuous, records)
        self.assert_trace_failure_before_gui(discontinuous, '连续')

        mismatched_samples = self.make_outer('mismatched-sample-frames')
        records = self.trace_records(mismatched_samples)
        records[0]['steps']['v0']['samples'].insert(
            0, self.state(0.05, 100.5))
        self.write_trusted_trace(mismatched_samples, records)
        self.assert_trace_failure_before_gui(
            mismatched_samples, '样本.*车辆|车辆.*样本|样本.*完整')

    def test_generator_forwards_each_editable_value_once_with_safe_subprocess(self):
        config = replace(
            self.config, vehicle_count=12, target_speed_mps=9.5,
            random_seed=9, simulation_duration_s=40.0,
            local_formation_range_m=81.0, adjacent_lane_gap_m=13.0,
            same_lane_gap_m=29.0, position_tolerance_m=1.25,
            formation_accel_limit_mps2=0.35)
        self.config = config
        outer = self.make_outer()
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command, 0, stdout='diagnostic\n' + json.dumps({
                    'path': str(outer), 'formal': False}) + '\n', stderr='')

        generated = gui.generate_fresh_simple_trace(
            config, self.paths, process_runner=runner)
        self.assertEqual(generated.outer_path, outer.resolve())
        self.assertEqual(generated.source.actors,
                         tuple(f'v{index}' for index in range(12)))
        command, kwargs = calls[0]
        self.assertIsInstance(command, list)
        self.assertEqual(command[:6], [
            sys.executable, '-I', '-B', '-S', str(self.variant_run),
            'phase5g-demo'])
        expected_values = {
            '--vehicle-count': '12', '--seed': '9',
            '--target-speed-mps': '9.5', '--duration-s': '40',
            '--output-base': 'results/phase5g/simple_gui_sources',
            '--local-formation-range-m': '81',
            '--adjacent-lane-gap-m': '13', '--same-lane-gap-m': '29',
            '--position-tolerance-m': '1.25',
            '--formation-accel-limit-mps2': '0.35',
            '--max-formation-lane-changes': '1',
        }
        self.assertEqual(command.count('--offline'), 1)
        for flag, value in expected_values.items():
            with self.subTest(flag=flag):
                self.assertEqual(command.count(flag), 1)
                self.assertEqual(command[command.index(flag) + 1], value)
        self.assertEqual(kwargs, {
            'cwd': self.variant_root, 'capture_output': True, 'text': True,
            'encoding': 'utf-8', 'timeout': 474, 'check': False,
            'shell': False,
        })

    def test_generator_timeout_reports_the_actual_computed_budget(self):
        config = replace(
            self.config, vehicle_count=3, simulation_duration_s=45.0)

        def timeout_runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])

        with self.assertRaisesRegex(RuntimeError, '198秒'):
            gui.generate_fresh_simple_trace(
                config, self.paths, process_runner=timeout_runner)

    def test_generator_uses_only_the_last_nonempty_stdout_line(self):
        outer = self.make_outer()
        result = subprocess.CompletedProcess(
            [], 0, stdout='not json\n\n' + json.dumps({'path': str(outer)}) + '\n\n',
            stderr='')
        generated = gui.generate_fresh_simple_trace(
            self.config, self.paths, process_runner=lambda *args, **kwargs: result)
        self.assertEqual(generated.outer_path, outer.resolve())

    def test_external_or_unsealed_result_path_is_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        external = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({'path': str(outside)}), stderr='')
        with self.assertRaisesRegex(RuntimeError, '结果路径越界'):
            gui.generate_fresh_simple_trace(
                self.config, self.paths,
                process_runner=lambda *args, **kwargs: external)

        root_only = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({'path': str(self.variant_results)}), stderr='')
        with self.assertRaisesRegex(RuntimeError, '结果路径越界'):
            gui.generate_fresh_simple_trace(
                self.config, self.paths,
                process_runner=lambda *args, **kwargs: root_only)

        outer = self.make_outer('unsealed')
        (outer / 'evidence_hashes.json').unlink()
        unsealed = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({'path': str(outer)}), stderr='')
        with self.assertRaisesRegex(RuntimeError, '证据'):
            gui.generate_fresh_simple_trace(
                self.config, self.paths,
                process_runner=lambda *args, **kwargs: unsealed)

    def test_generator_failure_reports_exit_and_stderr(self):
        failed = subprocess.CompletedProcess(
            [], 7, stdout='partial output', stderr='injected failure')
        with self.assertRaisesRegex(
                RuntimeError, 'exit code 7.*injected failure'):
            gui.generate_fresh_simple_trace(
                self.config, self.paths,
                process_runner=lambda *args, **kwargs: failed)

    def test_bad_final_json_is_rejected(self):
        bad = subprocess.CompletedProcess([], 0, stdout='progress\nnot-json\n', stderr='')
        with self.assertRaisesRegex(RuntimeError, '最后一行不是有效JSON'):
            gui.generate_fresh_simple_trace(
                self.config, self.paths,
                process_runner=lambda *args, **kwargs: bad)

    def test_loader_rejects_rule_mismatch_and_noncontrolled_case_members(self):
        rules = self.make_outer('wrong-rules')
        metadata_path = rules / 'metadata.json'
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        metadata['simple_parameters']['simple_formation_adjacent_gap_m'] = 99.0
        metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
        self.reseal_trusted(rules)
        with self.assertRaisesRegex(RuntimeError, 'simple_parameters'):
            gui.load_simple_trace_source(rules, self.paths, self.config)

        members = self.make_outer('background-member')
        child_metadata_path = members / 'case' / 'metadata.json'
        child_metadata = json.loads(child_metadata_path.read_text(encoding='utf-8'))
        child_metadata['case']['initial']['background'] = self.state(0.0, 500.0)
        child_metadata_path.write_text(json.dumps(child_metadata), encoding='utf-8')
        self.reseal_trusted(members)
        with self.assertRaisesRegex(RuntimeError, '全量受控'):
            gui.load_simple_trace_source(members, self.paths, self.config)


class GuiRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=gui.PROJECT_ROOT / 'tmp')
        self.root = Path(self.temporary.name)
        self.out = self.root / 'attempt'
        self.out.mkdir()
        (self.root / 'bottleneck.net.xml').write_text('<net/>', encoding='utf-8')
        self.paths = gui.CheckedPaths(
            self.root, self.root / 'sumo-gui.exe', self.root / 'bottleneck.net.xml',
            self.root / 'algorithm-run', self.root / 'sumo-home')
        self.connection = SimpleNamespace(
            gui=MagicMock(), route=MagicMock(), vehicle=MagicMock(), simulation=MagicMock(),
            simulationStep=MagicMock(), close=MagicMock())
        self.connection.gui.getIDList.return_value = ('View #0',)
        self.connection.vehicle.getIDList.return_value = ('ego',)
        self.connection.simulation.getCollidingVehiclesNumber.return_value = 0
        self.connection.simulation.getStartingTeleportNumber.return_value = 0
        self.source = self.make_source()

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def state(time_s, x_m):
        return {
            'time_s': time_s, 'x_m': x_m, 'y_m': 1.65, 'heading_rad': 0.0,
            'vx_mps': 5.0, 'vy_mps': 0.0, 'yaw_rate_radps': 0.0,
            'a_drive_mps2': 0.0, 'steering_rad': 0.0,
        }

    def make_source(self):
        trace = self.root / 'trace.jsonl'
        initial = {'status': 'running', 'initial': {'ego': self.state(0.0, 10.0)}}
        completed = {
            'status': 'completed', 'initial': {'ego': self.state(0.0, 10.0)},
            'steps': {'ego': {'final': self.state(0.1, 10.5), 'samples': []}},
        }
        trace.write_text(
            json.dumps(initial) + '\n' + json.dumps(completed) + '\n', encoding='utf-8')
        return gui.TraceSource(
            'fixture', self.root, trace,
            {'case': {'controlled': ['ego']}, 'parameters': {'length_m': 4.0}},
            {'passed': True}, 'completed', ('ego',))

    def test_gui_command_uses_registered_binary_port_and_delay(self):
        command = gui.gui_command(self.paths, self.out / 'demo.sumocfg', 40, 8813)
        self.assertEqual(Path(command[0]), self.paths.sumo_gui)
        self.assertEqual(command[command.index('--remote-port') + 1], '8813')
        self.assertEqual(command[command.index('--delay') + 1], '40')
        self.assertIn('--start', command)

    def test_algorithm_route_defines_external_vehicle_type_and_routes(self):
        root = gui.algorithm_routes_tree()
        self.assertIsNotNone(root.find("vType[@id='external_demo']"))
        self.assertEqual(
            {node.get('id'): node.get('edges') for node in root.findall('route')},
            {'demo_full': 'upstream downstream', 'demo_remaining': 'downstream'})

    def test_algorithm_playback_moves_every_actor_and_sets_zoom(self):
        status = gui.play_algorithm(self.connection, self.source, auto_zoom=True)
        self.connection.gui.setBoundary.assert_called_once()
        self.assertEqual(self.connection.vehicle.moveToXY.call_count, 2)
        self.assertEqual(self.connection.vehicle.setSpeed.call_count, 2)
        self.assertEqual(status.frames_played, 2)
        self.assertAlmostEqual(status.final_time_s, 0.1)

    def test_native_playback_counts_collisions_and_drains(self):
        self.connection.simulation.getTime.side_effect = [0.0, 0.1]
        self.connection.simulation.getMinExpectedNumber.side_effect = [1, 0]
        self.connection.simulation.getCollidingVehiclesNumber.side_effect = [2, 0]
        self.connection.simulation.getStartingTeleportNumber.side_effect = [0, 1]
        status = gui.play_native(self.connection, duration_s=10, auto_zoom=True)
        self.assertEqual(status.frames_played, 2)
        self.assertEqual(status.colliding_vehicle_reports, 2)
        self.assertEqual(status.teleport_starts, 1)
        self.assertEqual(status.end_reason, 'demand_drained')

    def test_owned_session_closes_connection_process_and_log_on_error(self):
        process = MagicMock()
        process.poll.return_value = None
        log = MagicMock()
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            with gui.OwnedGuiSession(self.connection, process, log):
                raise RuntimeError('injected')
        self.connection.close.assert_called_once_with(False)
        process.terminate.assert_called_once()
        process.wait.assert_called()
        log.close.assert_called_once()

    def test_xml_and_json_writers_create_replayable_files(self):
        xml_path = self.out / 'native.rou.xml'
        json_path = self.out / 'run_metadata.json'
        gui.write_xml(xml_path, gui.native_routes_tree(replace(gui.DemoConfig(), vehicle_count=2)))
        gui.write_json_atomic(json_path, {'status': 'running', 'count': 2})
        self.assertEqual(len(ET.parse(xml_path).getroot().findall('vehicle')), 2)
        self.assertEqual(json.loads(json_path.read_text(encoding='utf-8'))['count'], 2)

    def test_algorithm_workflow_saves_completed_metadata_and_waits(self):
        session = MagicMock()
        session.__enter__.return_value = self.connection
        session.__exit__.return_value = False
        outputs = []
        with patch.object(gui, 'validate_config', return_value=self.paths), \
                patch.object(gui, 'load_trace_source', return_value=self.source):
            run_dir = gui.run_algorithm_demo(
                gui.DemoConfig(), self.root, runtime=lambda *args: session,
                input_fn=lambda prompt: '', output_fn=outputs.append)
        metadata = json.loads((run_dir / 'run_metadata.json').read_text(encoding='utf-8'))
        snapshot = json.loads((run_dir / 'config_snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['status'], 'completed')
        self.assertEqual(metadata['frames_played'], 2)
        self.assertEqual(snapshot['algorithm_case'], 'r5c_gradual_three_r5_on')
        self.assertTrue(any('封存轨迹' in line for line in outputs))

    def test_start_gui_session_uses_traci_and_returns_owned_session(self):
        process = MagicMock()
        process.poll.return_value = None
        traci = MagicMock()
        traci.connect.return_value = self.connection
        socket_instance = MagicMock()
        socket_instance.__enter__.return_value.getsockname.return_value = ('127.0.0.1', 8813)
        sumocfg = self.out / 'demo.sumocfg'
        sumocfg.write_text('<configuration/>', encoding='utf-8')
        with patch.object(gui.socket, 'socket', return_value=socket_instance), \
                patch.object(gui.subprocess, 'Popen', return_value=process) as popen, \
                patch.object(gui, '_load_traci', return_value=traci):
            session = gui.start_gui_session(
                self.paths, sumocfg, 40, self.out / 'stdout_stderr.log')
        self.assertIs(session.connection, self.connection)
        command = popen.call_args.args[0]
        self.assertEqual(command[command.index('--remote-port') + 1], '8813')
        traci.connect.assert_called_once()
        session.__exit__(None, None, None)

    def test_user_closed_window_is_recorded_without_traceback(self):
        class FatalTraCIError(Exception):
            pass

        session = MagicMock()
        session.__enter__.return_value = self.connection
        session.__exit__.return_value = False
        with patch.object(gui, 'validate_config', return_value=self.paths), \
                patch.object(gui, 'load_trace_source', return_value=self.source), \
                patch.object(gui, 'play_algorithm',
                             side_effect=FatalTraCIError('connection closed by peer')):
            run_dir = gui.run_algorithm_demo(
                replace(gui.DemoConfig(), wait_before_close=False), self.root,
                runtime=lambda *args: session, output_fn=lambda line: None)
        metadata = json.loads((run_dir / 'run_metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['status'], 'user_closed')
        self.assertNotIn('traceback', metadata)

    def test_keyboard_interrupt_is_recorded_and_cleaned_up(self):
        session = MagicMock()
        session.__enter__.return_value = self.connection
        session.__exit__.return_value = False
        with patch.object(gui, 'validate_config', return_value=self.paths), \
                patch.object(gui, 'play_native', side_effect=KeyboardInterrupt):
            run_dir = gui.run_native_demo(
                replace(gui.DemoConfig(), wait_before_close=False), self.root,
                runtime=lambda *args: session, output_fn=lambda line: None)
        metadata = json.loads((run_dir / 'run_metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['status'], 'interrupted')
        session.__exit__.assert_called_once()

    def test_startup_failure_is_saved_and_reraised(self):
        with patch.object(gui, 'validate_config', return_value=self.paths):
            with self.assertRaisesRegex(RuntimeError, 'cannot connect'):
                gui.run_native_demo(
                    replace(gui.DemoConfig(), wait_before_close=False), self.root,
                    runtime=lambda *args: (_ for _ in ()).throw(RuntimeError('cannot connect')),
                    output_fn=lambda line: None)
        attempts = list((self.root / 'results' / 'demo_runs').iterdir())
        self.assertEqual(len(attempts), 1)
        metadata = json.loads(
            (attempts[0] / 'run_metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['status'], 'failed')
        self.assertIn('RuntimeError: cannot connect', metadata['error'])
        self.assertIn('Traceback', metadata['traceback'])


class SimpleFormationWorkflowTests(_SimpleTraceFixture, unittest.TestCase):
    def test_trace_only_mode_returns_outer_without_gui_or_demo_directory(self):
        outer = self.make_outer()
        source = gui.load_simple_trace_source(outer, self.paths, self.config)
        generated = gui.GeneratedSimpleTrace(outer.resolve(), source)
        config = replace(self.config, show_gui=False)
        output = []
        with patch.object(gui, 'validate_simple_config', return_value=self.paths), \
                patch.object(gui, 'create_run_directory') as create, \
                patch.object(gui, 'start_gui_session') as runtime:
            result = gui.run_simple_formation_demo(
                config, self.root, generator=lambda *args: generated,
                output_fn=output.append)
        self.assertEqual(result, outer.resolve())
        create.assert_not_called()
        runtime.assert_not_called()
        self.assertFalse((self.root / 'results' / 'demo_runs').exists())
        self.assertTrue(any(str(outer.resolve()) in line for line in output))

    def test_gui_mode_plays_only_controlled_trace_actors_and_saves_metadata(self):
        outer = self.make_outer()
        source = gui.load_simple_trace_source(outer, self.paths, self.config)
        expected_trace_sha256 = source.trace_sha256
        generated = gui.GeneratedSimpleTrace(outer.resolve(), source)
        source.trace_path.write_text('replaced after preflight\n', encoding='utf-8')
        session = MagicMock()
        connection = MagicMock()
        session.__enter__.return_value = connection
        session.__exit__.return_value = False
        stats = gui.PlaybackStats(451, 45.0, 0, 0, 'trace_completed')
        original_sha256_file = gui.sha256_file

        def forbid_trace_reread(path):
            if Path(path) == source.trace_path:
                raise AssertionError('GUI metadata reread trace disk')
            return original_sha256_file(path)

        with patch.object(gui, 'validate_simple_config', return_value=self.paths), \
                patch.object(gui, 'play_algorithm', return_value=stats) as playback, \
                patch.object(gui, 'sha256_file', side_effect=forbid_trace_reread):
            result = gui.run_simple_formation_demo(
                self.config, self.root, generator=lambda *args: generated,
                runtime=lambda *args: session, input_fn=lambda prompt: '',
                output_fn=lambda line: None)
        self.assertIn('_simple_formation_', result.name)
        playback.assert_called_once_with(connection, source, True)
        metadata = json.loads(
            (result / 'run_metadata.json').read_text(encoding='utf-8'))
        snapshot = json.loads(
            (result / 'config_snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['status'], 'completed')
        self.assertEqual(metadata['generation_source'], str(outer.resolve()))
        self.assertEqual(metadata['controlled_actors'], list(source.actors))
        self.assertEqual(metadata['source_trace_sha256'], expected_trace_sha256)
        self.assertEqual(metadata['frames_played'], 451)
        self.assertEqual(metadata['colliding_vehicle_reports'], 0)
        self.assertEqual(metadata['teleport_starts'], 0)
        self.assertEqual(snapshot['vehicle_count'], 6)

    def test_user_close_keyboard_interrupt_and_startup_failure_are_recorded(self):
        outer = self.make_outer()
        source = gui.load_simple_trace_source(outer, self.paths, self.config)
        generated = gui.GeneratedSimpleTrace(outer.resolve(), source)

        class FatalTraCIError(Exception):
            pass

        scenarios = (
            ('user_closed', FatalTraCIError('connection closed by peer')),
            ('interrupted', KeyboardInterrupt()),
            ('failed', RuntimeError('cannot connect')),
        )
        for expected_status, injected in scenarios:
            with self.subTest(expected_status=expected_status):
                session = MagicMock()
                session.__enter__.return_value = MagicMock()
                session.__exit__.return_value = False

                if expected_status == 'failed':
                    runtime = lambda *args: (_ for _ in ()).throw(injected)
                    context = self.assertRaisesRegex(RuntimeError, 'cannot connect')
                else:
                    runtime = lambda *args: session
                    context = patch.object(
                        gui, 'play_algorithm', side_effect=injected)
                with patch.object(
                        gui, 'validate_simple_config', return_value=self.paths), context:
                    gui.run_simple_formation_demo(
                        replace(self.config, wait_before_close=False), self.root,
                        generator=lambda *args: generated, runtime=runtime,
                        output_fn=lambda line: None)
                attempts = sorted(
                    (self.root / 'results' / 'demo_runs').iterdir())
                metadata = json.loads(
                    (attempts[-1] / 'run_metadata.json').read_text(encoding='utf-8'))
                self.assertEqual(metadata['status'], expected_status)
                if expected_status != 'failed':
                    self.assertNotIn('traceback', metadata)

    def test_user_close_during_owned_session_cleanup_is_user_closed(self):
        outer = self.make_outer('close-during-default-wait')
        source = gui.load_simple_trace_source(outer, self.paths, self.config)
        generated = gui.GeneratedSimpleTrace(outer.resolve(), source)

        class FatalTraCIError(Exception):
            pass

        connection = MagicMock()
        connection.close.side_effect = FatalTraCIError(
            'connection closed by peer')
        process = MagicMock()
        process.poll.return_value = None
        log = MagicMock()
        session = gui.OwnedGuiSession(connection, process, log)
        stats = gui.PlaybackStats(2, 0.1, 0, 0, 'trace_completed')
        caught = None
        try:
            with patch.object(
                    gui, 'validate_simple_config', return_value=self.paths), \
                    patch.object(gui, 'play_algorithm', return_value=stats):
                run_dir = gui.run_simple_formation_demo(
                    self.config, self.root,
                    generator=lambda *args: generated,
                    runtime=lambda *args: session,
                    input_fn=lambda prompt: '', output_fn=lambda line: None)
        except RuntimeError as error:
            caught = error
            run_dir = sorted(
                (self.root / 'results' / 'demo_runs').iterdir())[-1]
        metadata = json.loads(
            (run_dir / 'run_metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['status'], 'user_closed')
        self.assertNotIn('traceback', metadata)
        self.assertIsNone(caught)
        process.terminate.assert_called_once()
        log.close.assert_called_once()

    def test_generation_failure_never_creates_demo_run_or_starts_gui(self):
        runtime = MagicMock()

        def fail(*args):
            raise RuntimeError('fresh generation failed')

        with patch.object(gui, 'validate_simple_config', return_value=self.paths), \
                self.assertRaisesRegex(RuntimeError, 'fresh generation failed'):
            gui.run_simple_formation_demo(
                self.config, self.root, generator=fail, runtime=runtime,
                output_fn=lambda line: None)
        runtime.assert_not_called()
        self.assertFalse((self.root / 'results' / 'demo_runs').exists())

    def test_check_only_validates_and_never_runs_process_or_creates_directory(self):
        with patch.object(gui, 'validate_simple_config', return_value=self.paths), \
                patch.object(gui.subprocess, 'run') as run, \
                patch.object(gui.subprocess, 'Popen') as popen, \
                patch.object(gui, 'create_run_directory') as create:
            report = gui.check_simple_environment(self.config, self.root)
        run.assert_not_called()
        popen.assert_not_called()
        create.assert_not_called()
        self.assertEqual(report['variant_run'], str(self.variant_run))
        self.assertEqual(report['traci'], str(self.traci_python))
        self.assertFalse((self.root / 'results' / 'demo_runs').exists())


class EntrypointTests(unittest.TestCase):
    def test_top_level_defaults_build_expected_config(self):
        self.assertEqual(runrun.build_config(), gui.SimpleFormationDemoConfig())
        self.assertEqual(runrun.PROJECT_ROOT, gui.PROJECT_ROOT)

    def test_check_does_not_start_gui(self):
        report = {
            'sumo_gui': 'D:/SUMO/bin/sumo-gui.exe', 'network': 'bottleneck.net.xml',
            'variant_root': 'D:/variant', 'variant_run': 'D:/variant/run.py',
            'variant_results': 'D:/variant/results',
            'traci': 'D:/SUMO/tools/traci/__init__.py',
            'configuration': {'vehicle_count': 6},
        }
        output = []
        with patch.object(runrun, 'check_simple_environment', return_value=report), \
                patch.object(runrun, 'run_simple_formation_demo') as demo:
            self.assertEqual(runrun.main(['--check'], output_fn=output.append), 0)
        demo.assert_not_called()
        self.assertTrue(any('自检通过' in line for line in output))

    def test_main_directly_runs_simple_formation_without_reading_input(self):
        output = []

        def forbidden_input(prompt):
            raise AssertionError('入口不应显示菜单或读取输入')

        with patch.object(runrun, 'run_simple_formation_demo') as demo:
            self.assertEqual(runrun.main(
                [], input_fn=forbidden_input, output_fn=output.append), 0)
        demo.assert_called_once_with(
            gui.SimpleFormationDemoConfig(), input_fn=unittest.mock.ANY,
            output_fn=unittest.mock.ANY)
        self.assertTrue(any('局部自组织交错编队' in line for line in output))

    def test_unknown_command_line_option_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '只支持 --check'):
            runrun.main(['--bad'], output_fn=lambda line: None)

    def test_direct_process_emits_utf8_chinese_from_another_working_directory(self):
        result = subprocess.run(
            [sys.executable, str(gui.PROJECT_ROOT / 'runrun.py'), '--check'],
            cwd=gui.PROJECT_ROOT.parent, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        output = result.stdout.decode('utf-8')
        self.assertIn('自检通过：没有启动SUMO GUI。', output)


if __name__ == '__main__':
    unittest.main()
