"""New J2/JT2 adjacency contracts; default targets are immutable J0/JT0."""
from dataclasses import asdict
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import sys
import unittest


REPO = Path(__file__).resolve().parents[4]
PARENTS = {
    "J2": ("local_phase_coupling", "dd0b7f466de943976af8fe44e1f5b89dfbafe5ea8e86f6f242fcea7a22f75e53"),
    "JT2": ("time_scaled_phase_coupling", "443e082742d1400ad03b4381e91cdace35cde522c48b6f11efd375ff89af287e"),
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


parents, variants = {}, {}
for name, (directory, expected) in PARENTS.items():
    path = REPO / "tmp/staggered_bottleneck/candidates" / directory / "native_rules.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    parents[name] = load("adjacency_parent_" + name, path)
    variants[name] = load("adjacency_" + name, os.environ.get("RULES_" + name, path))


def car(r, track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class PhysicalPhaseAdjacencyTests(unittest.TestCase):
    def test_preparing_retained_and_ending_bodies_share_actual_adjacent_edge(self):
        for name, r in variants.items():
            middle, ending = car(r, 1, 700, 1), car(r, 2, 700, 2)
            cars = (middle, ending, car(r, 11, 730, 1), car(r, 12, 730, 2))
            for ego, desired_lanes, sign in ((middle, 2, -1), (ending, 3, 1)):
                with self.subTest(candidate=name, lane=ego.lane):
                    rows = tuple(c for c in cars if c is not ego)
                    actual = r._following(ego, rows, desired_lanes, 640)
                    self.assertAlmostEqual(actual[0] - r._front_following(ego, rows)[0], sign * .4)
                    self.assertEqual(actual[2], 11 if ego.lane == 1 else 12)

    def test_missing_or_more_than_fifty_metre_ending_car_creates_no_edge(self):
        for name, r in variants.items():
            ego, front = car(r, 1, 700, 1), car(r, 11, 730, 1)
            for extra in ((), (car(r, 2, 750.001, 2),)):
                with self.subTest(candidate=name, extra=bool(extra)):
                    expected = r._front_following(ego, (front, *extra))
                    actual = r._following(ego, (front, *extra), 2, 640)
                    self.assertEqual(actual, expected)

    def test_actual_ending_pair_keeps_common_three_lane_normalization(self):
        for name, r in variants.items():
            a, b = car(r, 0, 700, 1), car(r, 1, 700, 2)
            first, count = r._pair_error(a, b, 2, 640)
            reverse, other_count = r._pair_error(b, a, 3, 640)
            with self.subTest(candidate=name):
                self.assertEqual((count, other_count), (3, 3))
                self.assertAlmostEqual(first, -reverse)

    def test_without_actual_lane_two_both_policies_are_exactly_their_frozen_parent(self):
        rng = random.Random(202611036)
        for _ in range(300):
            x, lane = rng.uniform(630, 1150), rng.randrange(2)
            values = [(0, x, lane, rng.uniform(0, 33.3))]
            values += [(i, x + rng.uniform(-130, 230), rng.randrange(2), rng.uniform(0, 33.3)) for i in range(1, 10)]
            for name, r in variants.items():
                old = parents[name]
                actual_cars, old_cars = [car(r, *v) for v in values], [car(old, *v) for v in values]
                for mode in ("noa", "formation", "transform"):
                    actual = r.decide(actual_cars[0], actual_cars[1:], r.Memory(), mode)
                    expected = old.decide(old_cars[0], old_cars[1:], old.Memory(), mode)
                    self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))


if __name__ == "__main__":
    unittest.main()
