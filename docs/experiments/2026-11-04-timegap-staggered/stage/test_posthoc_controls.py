"""Small rule checks for post-hoc h sensitivity and the supplementary NOA front range."""
from dataclasses import asdict
import importlib.util
import os
from pathlib import Path
import sys
import unittest

BASE = Path(__file__).resolve().parents[4] / 'tmp/staggered_bottleneck/candidates'


def load(name, preview):
    if os.environ.get('POSTHOC_PARENT_ONLY') == '1':
        name = 'C12'
    path = BASE / f'20261104_{name}_{preview}/native_rules.py'
    spec = importlib.util.spec_from_file_location(f'posthoc_{name}_{preview}', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def car(r, track, x, lane=0, speed=28.8, **extra):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **extra)


class PosthocControls(unittest.TestCase):
    def check_headway(self, name, headway, distance):
        for preview in (200, 300):
            r = load(name, preview)
            self.assertEqual(r.HEADWAY, headway)
            self.assertAlmostEqual(r.desired_spacing(28.8), distance)
            ego, front = car(r, 0, 0.), car(r, 1, 30.)
            commands = [r.decide(ego, (front,), r.Memory(), mode, None)[0]
                        for mode in ('noa', 'transform')]
            for command in commands:
                self.assertAlmostEqual(command.target_x, 30. - distance)
                self.assertEqual(command.reference, 1)
            self.assertAlmostEqual(commands[0].speed, commands[1].speed)

    def test_h075_is_shared_by_noa_and_transform(self):
        self.check_headway('sensitivity_h075', .75, 27.1)

    def test_h100_is_shared_by_noa_and_transform(self):
        self.check_headway('sensitivity_h100', 1., 34.3)

    def test_noa_fresh_eighty_tracks_the_actual_far_front(self):
        for preview in (200, 300):
            r = load('NOA_front200', preview)
            command, memory = r.decide(car(r, 0, 0.), (car(r, 1, 80.),), r.Memory(), 'noa', None)
            self.assertEqual(command.reference, 1)
            self.assertAlmostEqual(command.target_x, 80. - 29.98)
            self.assertGreater(command.speed, r.CRUISE)
            self.assertEqual(command.formation_state, 0)
            self.assertIsNone(memory.front)

    def test_noa_has_no_cross_lane_phase_virtual_receiver_or_slot(self):
        for preview in (200, 300):
            r = load('NOA_front200', preview)
            for ego, rows, road in (
                    (car(r, 0, 0.), (car(r, 1, 5., 1),), None),
                    (car(r, 0, 0., 1), (car(r, 1, 15., 2),), 100.),
                    (car(r, 0, 0., 1), (car(r, 1, 29., 1), car(r, 2, 44., 0)), 100.)):
                command, memory = r.decide(ego, rows, r.Memory(), 'noa', road)
                self.assertEqual(command.formation_state, 0)
                self.assertIsNone(command.lane)
                self.assertEqual(asdict(memory), {'lane_target': None, 'front': None})
                if len(rows) == 1:
                    self.assertEqual(command.speed, r.CRUISE)
                    self.assertIsNone(command.reference)

    def test_exact_source_deltas_and_transform_control_memory_unchanged(self):
        for preview in (200, 300):
            parent_path = BASE / f'20261104_C12_{preview}/native_rules.py'
            parent_text = parent_path.read_text(encoding='utf-8')
            for name, replacement in (('sensitivity_h075', 'HEADWAY = .75'),
                                      ('sensitivity_h100', 'HEADWAY = 1.00')):
                actual = (BASE / f'20261104_{name}_{preview}/native_rules.py').read_text(encoding='utf-8')
                self.assertEqual(actual, parent_text.replace('HEADWAY = .85', replacement))
            far_path = BASE / f'20261104_NOA_front200_{preview}/native_rules.py'
            old = 'speed, target, reference, _ = _front_following(ego, rows)'
            new = 'speed, target, reference, _ = _front_following(ego, rows, distance=200.)'
            self.assertEqual(parent_text.count(old), 1)
            self.assertEqual(far_path.read_text(encoding='utf-8'), parent_text.replace(old, new))
            parent, far = load('C12', preview), load('NOA_front200', preview)
            for r in (parent, far):
                snapshots = (
                    (car(r, 0, 0.), (car(r, 1, 80.),), r.Memory(), None),
                    (car(r, 0, 0., 1), (car(r, 1, 15., 2),), r.Memory(), 100.),
                    (car(r, 0, 0., 1, pending_lane=0), (car(r, 1, 50., 0),),
                     r.Memory(lane_target=0, front=1), 100.))
                result = [(asdict(c), asdict(m)) for c, m in
                          (r.decide(ego, rows, memory, 'transform', road)
                           for ego, rows, memory, road in snapshots)]
                if r is parent:
                    expected = result
                else:
                    self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
