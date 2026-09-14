"""Tests for the user-facing SUMO GUI demonstration entry point."""
import json
import math
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
        self.config = gui.SimpleFormationDemoConfig()

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

    def make_outer(self, name='fresh'):
        outer = self.variant_results / 'phase5g' / 'simple_gui_sources' / name
        case = outer / 'case'
        case.mkdir(parents=True)
        actors = [f'v{index}' for index in range(self.config.vehicle_count)]
        initial = {
            actor: self.state(0.0, 100.0 + index * 15.0)
            for index, actor in enumerate(actors)
        }
        completed = {
            'status': 'completed', 'initial': initial,
            'steps': {
                actor: {
                    'final': self.state(0.1, 101.0 + index * 15.0),
                    'samples': [],
                }
                for index, actor in enumerate(actors)
            },
        }
        (case / 'trace.jsonl').write_text(
            json.dumps({'status': 'running', 'initial': initial}) + '\n'
            + json.dumps(completed) + '\n', encoding='utf-8')
        (case / 'metadata.json').write_text(json.dumps({
            'execution_status': 'completed',
            'case': {'name': 'main_6_3_2_1', 'controlled': actors,
                     'duration_s': self.config.simulation_duration_s,
                     'initial': initial, 'scripts': {}},
            'parameters': {'length_m': 4.0},
        }), encoding='utf-8')
        (case / 'validation.json').write_text(json.dumps({
            'status': 'completed', 'sealed': True, 'recording_passed': True,
        }), encoding='utf-8')
        self.seal(case)
        (outer / 'metadata.json').write_text(json.dumps({
            'schema': 'phase5g_simple_demo_v1', 'formal': False,
            'mode': 'lane_priority', 'simple_formation_enabled': True,
            'vehicle_count': self.config.vehicle_count,
            'seed': self.config.random_seed,
            'target_speed_mps': self.config.target_speed_mps,
            'duration_s': self.config.simulation_duration_s,
            'simple_parameters': {
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
            },
            'case_directory': 'case',
        }), encoding='utf-8')
        (outer / 'validation.json').write_text(json.dumps({
            'status': 'completed', 'complete_execution': True,
            'engineering_passed': True, 'case_directory': 'case',
        }), encoding='utf-8')
        self.seal(outer)
        return outer


class SimpleTraceGenerationTests(_SimpleTraceFixture, unittest.TestCase):
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
            'encoding': 'utf-8', 'timeout': 180, 'check': False,
            'shell': False,
        })

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
        self.seal(rules)
        with self.assertRaisesRegex(ValueError, 'simple_parameters'):
            gui.load_simple_trace_source(rules, self.paths, self.config)

        members = self.make_outer('background-member')
        child_metadata_path = members / 'case' / 'metadata.json'
        child_metadata = json.loads(child_metadata_path.read_text(encoding='utf-8'))
        child_metadata['case']['initial']['background'] = self.state(0.0, 500.0)
        child_metadata_path.write_text(json.dumps(child_metadata), encoding='utf-8')
        self.seal(members / 'case')
        self.seal(members)
        with self.assertRaisesRegex(ValueError, '全量受控'):
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
        generated = gui.GeneratedSimpleTrace(outer.resolve(), source)
        session = MagicMock()
        connection = MagicMock()
        session.__enter__.return_value = connection
        session.__exit__.return_value = False
        stats = gui.PlaybackStats(451, 45.0, 0, 0, 'trace_completed')
        with patch.object(gui, 'validate_simple_config', return_value=self.paths), \
                patch.object(gui, 'play_algorithm', return_value=stats) as playback:
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
