"""Ablation removes only longitudinal phase feedback, retaining real relations."""
from dataclasses import asdict
import importlib.util
import os
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
PARENT = ROOT / 'tmp/staggered_bottleneck/candidates/local_vacancy_bridge/native_rules.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load('phase_off_parent', PARENT)
rules = load('phase_off_subject', os.environ.get('RULES_PHASE_OFF', PARENT))


def car(r, track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class PhaseOffTests(unittest.TestCase):
    def test_parallel_body_keeps_actual_cth_without_phase_increment(self):
        ego = car(rules, 1, 100, 0)
        rows = (car(rules, 2, 130, 0), car(rules, 3, 100, 1), car(rules, 4, 130, 1))
        actual = rules._following(ego, rows, 3)
        self.assertEqual(actual[:3], rules._front_following(ego, rows)[:3])
        self.assertEqual(actual[3], 1)

    def test_head_keeps_cruise_with_actual_relation(self):
        ego = car(rules, 1, 100, 0)
        rows = (car(rules, 2, 100, 1),)
        self.assertEqual(rules._following(ego, rows, 3), (28.8, 100.0, None, 1))

    def test_noa_cf_safety_and_input_identity_are_preserved(self):
        rng = random.Random(202611031407)
        for _ in range(300):
            values = [(0, 700, rng.randrange(3), rng.uniform(10, 32))]
            values += [(k, 700 + rng.uniform(-100, 200), rng.randrange(3), rng.uniform(10, 32))
                       for k in range(1, 7)]
            converted = [tuple(car(r, *value) for value in values) for r in (base, rules)]
            results = []
            for r, cars in zip((base, rules), converted):
                command, memory = r.decide(cars[0], cars[1:], r.Memory(), 'noa')
                results.append((asdict(command), asdict(memory), r.cf_speed(cars[0], cars[1:]),
                                r.safe_speed(cars[0], cars[1:])))
            self.assertEqual(*results)


if __name__ == '__main__':
    unittest.main()
