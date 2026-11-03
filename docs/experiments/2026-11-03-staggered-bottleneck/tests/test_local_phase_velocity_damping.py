"""M contracts; default source is frozen L for the red stage."""
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


base = load("damping_parent", PARENT)
r = load("damping_candidate", os.environ.get("RULES_M", PARENT))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class LocalPhaseVelocityDampingTests(unittest.TestCase):
    def test_relative_velocity_has_the_damping_sign_on_an_equilibrium_edge(self):
        ego = car(0, 100, 0)
        for dv in (-1., 1.):
            with self.subTest(dv=dv):
                peer = car(1, 85, 1, ego.speed + dv)
                speed, target, reference, state = r._following(ego, (peer,), 2)
                self.assertAlmostEqual(target, ego.x + dv / r.POSITION_GAIN)
                self.assertAlmostEqual(speed - r.CRUISE, r.SPEED_RELAXATION * dv)
                self.assertIsNone(reference)
                self.assertEqual(state, 1)

    def test_unsaturated_edge_correction_is_antisymmetric_in_both_directions(self):
        for error in (-1., 0., 1.):
            with self.subTest(error=error):
                a, b = car(0, 100, 0), car(1, 85 + error, 1, 29.3)
                first, second = r._following(a, (b,), 2), r._following(b, (a,), 2)
                u_a = r.POSITION_GAIN * (first[1] - a.x)
                u_b = r.POSITION_GAIN * (second[1] - b.x)
                self.assertAlmostEqual(u_a, r.POSITION_GAIN * error + b.speed - a.speed)
                self.assertAlmostEqual(u_a, -u_b)

    def test_uniform_cruise_lattice_remains_exactly_the_parent_for_all_cars(self):
        for lanes in (2, 3):
            cars = tuple(car(10 * lane + layer, 1000 - 30 * layer - 15 * (lane % 2), lane)
                         for lane in range(lanes) for layer in range(3))
            for ego in cars:
                rows = tuple(c for c in cars if c is not ego)
                with self.subTest(lanes=lanes, track=ego.track):
                    actual = r._following(ego, rows, lanes)
                    expected = base._following(ego, rows, lanes)
                    self.assertEqual(actual, expected)
                    self.assertAlmostEqual(actual[0], r.CRUISE)
                    self.assertAlmostEqual(actual[1], ego.x)

    def test_approaching_a_slight_phase_error_reduces_the_position_only_action(self):
        ego, peer = car(0, 100, 0), car(1, 86, 1, 28.5)
        actual = r._following(ego, (peer,), 2)
        old = base._following(ego, (peer,), 2)
        self.assertGreater(old[0], r.CRUISE)
        self.assertAlmostEqual(actual[0], r.CRUISE)
        self.assertLess(actual[0], old[0])

    def test_real_front_cth_target_reference_survive_the_velocity_increment(self):
        ego, front, peer = car(0, 100, 0), car(1, 130, 0), car(2, 85, 1, 29.8)
        actual = r._following(ego, (front, peer), 2)
        cf = r._front_following(ego, (front, peer))
        self.assertEqual(actual[1:3], cf[1:3])
        self.assertEqual(actual[2], front.track)
        self.assertAlmostEqual(actual[0] - cf[0], r.SPEED_RELAXATION * (peer.speed - ego.speed))

    def test_original_two_metre_per_second_phase_clip_remains(self):
        ego, peer = car(0, 100, 0), car(1, 85, 1, 33.3)
        actual = r._following(ego, (peer,), 2)
        self.assertAlmostEqual(actual[1], ego.x + 2. / r.POSITION_GAIN)
        self.assertAlmostEqual(actual[0], r.CRUISE + 2. * r.SPEED_RELAXATION)

    def test_relabel_reorder_and_far_traffic_leave_the_same_real_edge(self):
        ego, peer = car(0, 100, 0), car(1, 85, 1, 29.8)
        rows = (peer, car(2, 145, 1, 10.))
        expected = r._following(ego, rows, 2)
        label = lambda c: replace(c, track=991 - c.track * 17)
        actual = r._following(label(ego), (car(7777, 1000, 2), *map(label, reversed(rows))), 2)
        self.assertEqual((actual[0], actual[1], actual[3]), (expected[0], expected[1], expected[3]))
        self.assertEqual(actual[2], expected[2])

    def test_original_hard_safe_cap_still_applies_with_equal_edge_speeds(self):
        ego, front, witness = car(0, 100, 1, 33.3), car(1, 150.1, 1, 0.), car(2, 135.1, 0, 33.3)
        rows = (front, witness)
        self.assertGreater(r._following(ego, rows, 2, 640.)[0], r.safe_speed(ego, rows))
        command, _ = r.decide(ego, rows, r.Memory(), "formation", None)
        self.assertEqual(command.speed.hex(), r.safe_speed(ego, rows).hex())

    def test_six_hundred_saved_states_keep_noa_memory_cf_and_safety_exact(self):
        oracle = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz"
        with gzip.open(oracle, "rt", encoding="utf-8") as stream:
            for index, line in enumerate(stream):
                if index == 600:
                    break
                state = json.loads(line)["state"]
                cars = [r.Vehicle(**c) for c in state["cars"]]
                memory = state["memory"]
                if memory["gap"] is not None:
                    memory["gap"] = tuple(memory["gap"])
                actual = r.decide(cars[0], cars[1:], r.Memory(**memory), "noa", state["drop_x"])
                expected = base.decide(cars[0], cars[1:], base.Memory(**memory), "noa", state["drop_x"])
                self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
                self.assertEqual(actual[0].speed.hex(), expected[0].speed.hex())
                self.assertEqual(r.cf_speed(cars[0], cars[1:]).hex(), base.cf_speed(cars[0], cars[1:]).hex())
                self.assertEqual(r.safe_speed(cars[0], cars[1:]).hex(), base.safe_speed(cars[0], cars[1:]).hex())


if __name__ == "__main__":
    unittest.main()
