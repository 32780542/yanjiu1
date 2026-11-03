"""One-second relative-position prediction on the unchanged mutual graph."""
from dataclasses import asdict
import importlib.util
import os
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
PARENT = ROOT / 'tmp/staggered_bottleneck/candidates/local_phase_velocity_damping/native_rules.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load('one_second_parent', PARENT)
r = load('one_second_subject', os.environ.get('RULES_Q', PARENT))


def car(module, track, x, lane, speed=28.8):
    return module.Vehicle(track, x, (lane + .5) * module.LANE_WIDTH, speed, lane)


class OneSecondPhaseTests(unittest.TestCase):
    def test_head_uses_one_second_projected_error(self):
        ego, peer = car(r, 1, 100, 0), car(r, 2, 85, 1, 27.8)
        speed, target, reference, state = r._following(ego, (peer,), 3)
        # Current phase error is zero; in one second the slower peer falls 1m behind.
        self.assertAlmostEqual(target, 99.5)
        self.assertAlmostEqual(speed, 28.77)
        self.assertIsNone(reference)
        self.assertEqual(state, 1)

    def test_body_preserves_actual_front_and_cth_target(self):
        ego = car(r, 1, 100, 0)
        rows = (car(r, 2, 130, 0), car(r, 3, 85, 1, 27.8), car(r, 4, 115, 1, 27.8))
        actual = r._following(ego, rows, 3)
        self.assertEqual(actual[1:3], r._front_following(ego, rows)[1:3])
        self.assertAlmostEqual(actual[0], 28.77)

    def test_equal_speed_staggered_strings_remain_at_cruise(self):
        cars = tuple(car(r, 10 * lane + layer, 300 - 30 * layer - (15 if lane % 2 else 0), lane)
                     for lane in range(3) for layer in range(4))
        for ego in cars:
            self.assertAlmostEqual(r._following(ego, tuple(c for c in cars if c != ego), 3)[0], 28.8)

    def test_noa_cf_and_safety_are_unchanged(self):
        rng = random.Random(202611031453)
        for _ in range(300):
            values = [(0, 700, rng.randrange(3), rng.uniform(8, 33))]
            values += [(k, 700 + rng.uniform(-100, 200), rng.randrange(3), rng.uniform(8, 33))
                       for k in range(1, 7)]
            results = []
            for module in (base, r):
                ego, *rows = (car(module, *value) for value in values)
                command, memory = module.decide(ego, rows, module.Memory(), 'noa')
                results.append((asdict(command), asdict(memory), module.cf_speed(ego, rows),
                                module.safe_speed(ego, rows)))
            self.assertEqual(*results)


if __name__ == '__main__':
    unittest.main()
