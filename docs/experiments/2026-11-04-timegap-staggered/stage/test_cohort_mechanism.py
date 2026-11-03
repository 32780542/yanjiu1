"""No SUMO: CLI/protocol, initialization geometry and crossing interpolation checks."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

DOC = Path(__file__).resolve().parents[1]
ROOT = DOC.parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CohortMechanism(unittest.TestCase):
    def run_helper(self, extra):
        geometry = load(DOC / 'geometry_trial.py', 'cohort_geometry')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            rules = folder / 'rules.py'
            rules.write_text('# frozen rules\n', encoding='utf-8')
            output = folder / 'trial'
            argv = ['geometry_trial.py', '--rules', str(rules), '--output', str(output),
                    '--demo', 'formed45', '--scenario', 'lane_drop', '--exit-m', '3600', *extra]
            # Source copying is replaced with text only; no Git or SUMO is launched.
            raw = b'("exit", 1200)\nretained, 1000, 1200)\n'
            with patch.object(sys, 'argv', argv), \
                    patch.object(geometry.subprocess, 'check_output', return_value=raw), \
                    patch.object(geometry.subprocess, 'call', return_value=0):
                with self.assertRaises(SystemExit) as raised:
                    geometry.main()
            self.assertEqual(raised.exception.code, 0)
            return json.loads((output / 'protocol.json').read_text(encoding='utf-8'))

    def test_default_mode_and_old_tape_are_preserved(self):
        protocol = self.run_helper([])
        command = protocol['command']
        self.assertEqual(command[command.index('--mode') + 1], 'transform')
        self.assertTrue(protocol['initial'].endswith('formed45_initial.json'))

    def test_override_mode_and_initial_are_recorded_and_executed(self):
        initial = DOC / 'stage/cohort_parallel45_initial.json'
        protocol = self.run_helper(['--mode', 'noa', '--initial', str(initial)])
        command = protocol['command']
        self.assertEqual(protocol['mode'], 'noa')
        self.assertEqual(protocol['initial'], str(initial))
        self.assertEqual(command[command.index('--mode') + 1], 'noa')
        self.assertEqual(command[command.index('--initial') + 1], str(initial))

    def test_parallel_input_preserves_ids_speed_spacing_and_cohort_center(self):
        original = json.loads((ROOT / 'docs/experiments/2026-11-03-staggered-bottleneck/'
                               'formation_demo_D1/formed45_initial.json').read_text(encoding='utf-8'))
        parallel = json.loads((DOC / 'stage/cohort_parallel45_initial.json').read_text(encoding='utf-8'))
        self.assertEqual(len(parallel), 45)
        self.assertEqual(sum(c['x'] for c in parallel), sum(c['x'] for c in original))
        for old, new in zip(original, parallel):
            self.assertEqual({k: v for k, v in old.items() if k != 'x'},
                             {k: v for k, v in new.items() if k != 'x'})
            self.assertEqual(new['x'] - old['x'], 10 if old['lane'] == 1 else -5)
        for lane in range(3):
            self.assertEqual(sorted(c['x'] for c in parallel if c['lane'] == lane),
                             [30 + 30 * i for i in range(15)])

    def test_actual_crossing_interpolation_and_own_first_frame_baseline(self):
        probe = load(DOC / 'tools/cohort_probe.py', 'cohort_probe')
        frames = [
            {'time_s': 5., 'states': {'a': [990., 8.25, 0., 0.]}},
            {'time_s': 5.1, 'states': {'a': [998., 8.25, 20., 0.]}},
            {'time_s': 5.2, 'states': {'a': [1002., 4.95, 20., 0.]}}]
        trips = [{'vehicle_id': 'a', 'lane_completion_events': [
            {'time_s': 5.15, 'x': 1000.}, {'time_s': 6., 'x': 1020.}]}]
        summary, rows = probe.summarize(frames, trips, ['a'])
        self.assertAlmostEqual(rows[0]['crossing_time_s'], 5.15)
        self.assertAlmostEqual(rows[0]['free_crossing_time_s'], 5. + 10. / 28.8)
        self.assertAlmostEqual(rows[0]['bottleneck_delay_s'], 5.15 - 5. - 10. / 28.8)
        self.assertAlmostEqual(summary['ending_stop_sample_vehicle_s'], .1)
        self.assertEqual(summary['lane_completions_to_bottleneck'], 1)
        self.assertEqual(summary['lane_completions_full_observation'], 2)


if __name__ == '__main__':
    unittest.main()
