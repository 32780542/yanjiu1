"""Physical examples for a locally sensed pre-merge predecessor, through decide."""
from dataclasses import asdict, replace
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import subprocess
import sys
from types import ModuleType
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


raw = subprocess.check_output(["git", "show", "1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py"], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
base = ModuleType("midflow_S_oracle")
sys.modules[base.__name__] = base
exec(compile(raw, "frozen_S_native_rules.py", "exec"), base.__dict__)
r = load("midflow_premerge_candidate", os.environ.get("RULES_V", SOURCE))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def exact(value):
    if hasattr(value, "__dataclass_fields__"):
        return exact(asdict(value))
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {key: exact(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(item) for item in value]
    return value


class PremergeTopologyTests(unittest.TestCase):
    def test_receiving_car_establishes_following_before_lateral_occupancy(self):
        ego, front, merging = car(0, 700., 1), car(1, 730., 1), car(2, 705., 2)
        command, _ = r.decide(ego, (front, merging), r.Memory(), "transform")
        self.assertIsNone(command.lane)
        self.assertEqual(command.reference, merging.track)
        self.assertAlmostEqual(command.target_x, 675.)
        self.assertLessEqual(command.speed, r._request(ego, 675., merging.speed))

    def test_opposite_phase_acceleration_cannot_cancel_projected_cth(self):
        ego, front, merging, left = car(0, 700., 1), car(1, 730., 1), car(2, 705., 2), car(3, 720., 0)
        command, _ = r.decide(ego, (front, merging, left), r.Memory(), "transform")
        self.assertEqual(command.reference, merging.track)
        self.assertLessEqual(command.speed, r._request(ego, 675., merging.speed))

    def test_actual_nearer_front_owns_the_receiving_rear(self):
        ego, front, merging = car(0, 700., 1), car(1, 703., 1), car(2, 710., 2)
        actual = r.decide(ego, (front, merging), r.Memory(), "transform")
        expected = base.decide(ego, (front, merging), base.Memory(), "transform")
        self.assertEqual(exact(actual), exact(expected))

    def test_slow_actual_front_still_limits_the_request(self):
        ego, front, merging = car(0, 700., 1), car(1, 740., 1, 10.), car(2, 720., 2)
        command, _ = r.decide(ego, (front, merging), r.Memory(), "transform")
        self.assertLessEqual(command.speed, r._front_following(ego, (front,))[0])
        self.assertLessEqual(command.speed, r.safe_speed(ego, (front, merging)))

    def test_no_projected_front_preserves_the_real_single_vacancy_bridge(self):
        ego = car(0, 700., 1)
        rows = (car(1, 760., 1), car(2, 745., 0))
        self.assertEqual(exact(r.decide(ego, rows, r.Memory(), "transform")),
                         exact(base.decide(ego, rows, base.Memory(), "transform")))

    def test_parallel_rear_and_not_yet_preparing_cars_are_not_virtual_fronts(self):
        ego, front = car(0, 700., 1), car(1, 730., 1)
        for x in (699., 700., 639., 751.):
            rows = (front, car(2, x, 2))
            with self.subTest(x=x):
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(), "transform")),
                                 exact(base.decide(ego, rows, base.Memory(), "transform")))

    def test_labels_and_observation_order_do_not_assign_priority(self):
        ego = car(0, 700., 1)
        rows = (car(1, 730., 1), car(2, 705., 2))
        expected, memory = r.decide(ego, rows, r.Memory(), "transform")
        label = lambda c: replace(c, track=401 - 19 * c.track)
        actual, changed_memory = r.decide(label(ego), tuple(label(c) for c in reversed(rows)), r.Memory(), "transform")
        self.assertEqual((actual.speed.hex(), actual.lane, actual.target_x, actual.reason, actual.formation_state),
                         (expected.speed.hex(), expected.lane, expected.target_x, expected.reason, expected.formation_state))
        self.assertEqual(actual.reference, 401 - 19 * expected.reference)
        self.assertEqual(exact(memory), exact(changed_memory))

    def test_ten_thousand_valid_states_preserve_noa_formation_and_safety(self):
        rng = random.Random(202611031835)
        for _ in range(10000):
            x = rng.uniform(0., 1199.)
            ego = car(0, x, rng.randrange(3), rng.uniform(0., 33.3))
            rows = tuple(car(k + 1, x + dx, lane, rng.uniform(0., 33.3))
                         for lane in range(3) for k, dx in enumerate((-90., -45., 18., 48., 85., 150.))
                         if not (lane == ego.lane and abs(dx) < 8.))
            rows = tuple(replace(c, track=i + 1) for i, c in enumerate(rows))
            drop = None if rng.random() < .25 else 1000.
            for mode in ("noa", "formation"):
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(), mode, drop)),
                                 exact(base.decide(ego, rows, base.Memory(), mode, drop)))
            self.assertEqual(r.safe_speed(ego, rows).hex(), base.safe_speed(ego, rows).hex())


if __name__ == "__main__":
    unittest.main()
