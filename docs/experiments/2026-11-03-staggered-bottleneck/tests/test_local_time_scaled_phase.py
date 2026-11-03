"""LT: symmetric headway phase on fixed L; default L is the red stage."""
from dataclasses import asdict, replace
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[4]
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/local_vacancy_bridge/native_rules.py"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == "e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


base = load("lt_parent", PARENT)
r = load("lt_candidate", os.environ.get("RULES_LT", PARENT))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def lattice(lanes, speed):
    distance = r.LENGTH + r.STANDSTILL + r.HEADWAY * speed
    return tuple(car(10 * lane + layer, 1000 - layer * distance - (distance / 2 if lane % 2 else 0), lane, speed)
                 for lane in range(lanes) for layer in range(3))


def exact(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(v) for v in value]
    return value


class LocalTimeScaledPhaseTests(unittest.TestCase):
    def test_low_speed_bodies_balance_at_D_and_half_D(self):
        for lanes in (2, 3):
            cars = lattice(lanes, 10.)
            for ego in cars:
                if ego.track % 10 == 0:
                    continue
                rows = tuple(c for c in cars if c is not ego)
                with self.subTest(lanes=lanes, track=ego.track):
                    speed, target, reference, _ = r._following(ego, rows, lanes)
                    self.assertAlmostEqual(speed, 10.)
                    self.assertAlmostEqual(target, ego.x)
                    self.assertEqual(reference, ego.track - 1)

    def test_low_speed_free_heads_still_return_to_cruise(self):
        cars = lattice(3, 10.)
        for ego in cars:
            if ego.track % 10:
                continue
            with self.subTest(lane=ego.lane):
                speed, _, reference, _ = r._following(ego, tuple(c for c in cars if c is not ego), 3)
                self.assertIsNone(reference)
                self.assertAlmostEqual(speed, 10. + r.SPEED_RELAXATION * (r.CRUISE - 10.))

    def test_unequal_velocity_edge_is_symmetric_and_uses_average_headway(self):
        for boundary in (640., 1000.):
            a, b = car(0, boundary - 10, 0, 10.), car(1, boundary + 10, 1, 20.)
            error, count = r._pair_error(a, b, 3, boundary)
            reverse, other_count = r._pair_error(b, a, 2, boundary)
            scale = (r.LENGTH + r.STANDSTILL + r.HEADWAY * (a.speed + b.speed) / 2) / r.GAP
            expected = b.x - a.x + (r._physical_phase(b, 3) - r._physical_phase(a, 3)) * scale
            with self.subTest(boundary=boundary):
                self.assertEqual((count, other_count), (3, 3))
                self.assertEqual(error, -reverse)
                self.assertEqual(error, expected)

    def test_relabel_reordering_and_remote_car_leave_local_body_output_unchanged(self):
        cars = lattice(3, 10.)
        ego, rows = cars[1], tuple(c for c in cars if c is not cars[1])
        expected = r._following(ego, rows, 3)
        label = lambda c: replace(c, track=9001 - 17 * c.track)
        actual = r._following(label(ego), (car(77777, 1700, 2, 10.), *map(label, reversed(rows))), 3)
        self.assertEqual(exact((actual[0], actual[1], actual[3])), exact((expected[0], expected[1], expected[3])))
        self.assertEqual(actual[2], label(next(c for c in rows if c.track == expected[2])).track)

    def test_L_witness_remains_cruise_geometry_while_actual_target_uses_headway(self):
        ego, front, witness = car(0, 100, 1, 10.), car(1, 160, 1, 10.), car(2, 145, 0, 10.)
        actual = r._following(ego, (front, witness), 2, 640.)
        self.assertEqual(actual[2], front.track)
        self.assertAlmostEqual(actual[1], front.x - r.LENGTH - r.STANDSTILL - r.HEADWAY * ego.speed)

    def test_three_hundred_saved_states_keep_noa_exact_and_cruise_exactly_L(self):
        oracle = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz"
        with gzip.open(oracle, "rt", encoding="utf-8") as stream:
            for index, line in enumerate(stream):
                if index == 300:
                    break
                state = json.loads(line)["state"]
                memory = state["memory"]
                if memory["gap"] is not None:
                    memory["gap"] = tuple(memory["gap"])
                cars = [r.Vehicle(**c) for c in state["cars"]]
                actual = r.decide(cars[0], cars[1:], r.Memory(**memory), "noa", state["drop_x"])
                expected = base.decide(cars[0], cars[1:], base.Memory(**memory), "noa", state["drop_x"])
                self.assertEqual(exact(tuple(map(asdict, actual))), exact(tuple(map(asdict, expected))))
                cruise = [replace(c, speed=r.CRUISE) for c in cars]
                for mode in ("noa", "formation", "transform"):
                    actual = r.decide(cruise[0], cruise[1:], r.Memory(**memory), mode, state["drop_x"])
                    expected = base.decide(cruise[0], cruise[1:], base.Memory(**memory), mode, state["drop_x"])
                    self.assertEqual(exact(tuple(map(asdict, actual))), exact(tuple(map(asdict, expected))))


if __name__ == "__main__":
    unittest.main()
