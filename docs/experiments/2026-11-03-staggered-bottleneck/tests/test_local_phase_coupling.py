"""J/JT contracts; unset paths exercise frozen E for the red stage."""
from dataclasses import asdict, replace
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import sys
import unittest


REPO = Path(__file__).resolve().parents[4]
E_PATH = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
E_SHA = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
assert hashlib.sha256(E_PATH.read_bytes()).hexdigest() == E_SHA


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load("coupling_frozen_e", E_PATH)
variants = {name: load("coupling_" + name, os.environ.get("RULES_" + name, E_PATH)) for name in ("J", "JT")}


def car(r, track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def strings(r, speed=28.8, stagger=True, lanes=3):
    distance = r.LENGTH + r.STANDSTILL + r.HEADWAY * speed
    return tuple(car(r, 10 * lane + layer, 1000 - layer * distance
                     - (distance / 2 if stagger and lane % 2 else 0), lane, speed)
                 for lane in range(lanes) for layer in range(3))


class LocalPhaseCouplingTests(unittest.TestCase):
    def test_physical_phase_does_not_flip_in_two_retained_lanes(self):
        for name, r in variants.items():
            with self.subTest(candidate=name):
                self.assertEqual([r._phase(l, 3) for l in range(3)], [0, 15, 0])
                self.assertEqual([r._phase(l, 2) for l in range(2)], [0, 15])

    def test_parallel_three_strings_all_heads_and_bodies_receive_phase_correction(self):
        for name, r in variants.items():
            cars = strings(r, stagger=False)
            for ego in cars:
                with self.subTest(candidate=name, track=ego.track):
                    rows = tuple(c for c in cars if c.track != ego.track)
                    speed, target, reference, state = r._following(ego, rows, 3)
                    expected = .4 if ego.lane % 2 == 0 else -.4
                    self.assertAlmostEqual(speed - r.CRUISE, expected)
                    self.assertEqual(state, 1)
                    if ego.track % 10:
                        self.assertEqual(reference, ego.track - 1)
                        self.assertAlmostEqual(target, ego.x)

    def test_parallel_body_tie_chooses_the_aligned_peer_instead_of_its_rear(self):
        for name, r in variants.items():
            cars = strings(r, stagger=False, lanes=2)
            for track, sign in ((1, 1), (11, -1)):
                ego = next(c for c in cars if c.track == track)
                with self.subTest(candidate=name, track=track):
                    speed, _, _, _ = r._following(ego, tuple(c for c in cars if c is not ego), 2)
                    self.assertAlmostEqual(speed - r.CRUISE, sign * .4)

    def test_cruise_thirty_fifteen_formation_is_equilibrium_for_every_vehicle(self):
        for name, r in variants.items():
            for lanes in (2, 3):
                cars = strings(r, lanes=lanes)
                for ego in cars:
                    with self.subTest(candidate=name, lanes=lanes, track=ego.track):
                        speed, target, _, state = r._following(ego, tuple(c for c in cars if c is not ego), lanes)
                        self.assertAlmostEqual(speed, r.CRUISE)
                        self.assertAlmostEqual(target, ego.x)
                        self.assertEqual(state, 1)

    def test_jt_low_speed_body_cth_and_half_headway_phase_are_equilibrium(self):
        r = variants["JT"]
        cars = strings(r, speed=10)
        for ego in cars:
            if ego.track % 10:
                with self.subTest(track=ego.track):
                    speed, target, reference, _ = r._following(ego, tuple(c for c in cars if c is not ego), 3)
                    self.assertAlmostEqual(speed, 10)
                    self.assertAlmostEqual(target, ego.x)
                    self.assertEqual(reference, ego.track - 1)
        a, b = cars[1], cars[4]
        self.assertAlmostEqual(r._pair_error(a, b, 3)[0], 0)

    def test_jt_low_speed_free_heads_still_return_to_cruise(self):
        r = variants["JT"]
        cars = strings(r, speed=10)
        for ego in cars:
            if ego.track % 10 == 0:
                with self.subTest(track=ego.track):
                    speed, _, reference, _ = r._following(ego, tuple(c for c in cars if c is not ego), 3)
                    self.assertIsNone(reference)
                    self.assertAlmostEqual(speed, 10 + r.SPEED_RELAXATION * (r.CRUISE - 10))

    def test_pair_error_is_antisymmetric_and_continuous_across_configuration_boundary(self):
        for name, r in variants.items():
            for boundary in (640, 1000):
                for dx in (-30, -15, 0, 15, 30):
                    a, b = car(r, 0, boundary - 40, 0), car(r, 1, boundary - 40 + dx, 1)
                    before, n0 = r._pair_error(a, b, 3, boundary)
                    after, n1 = r._pair_error(replace(a, x=a.x + 100), replace(b, x=b.x + 100), 2, boundary)
                    with self.subTest(candidate=name, boundary=boundary, dx=dx):
                        self.assertEqual((n0, n1), (3, 2))
                        self.assertAlmostEqual(before, after)
                        self.assertAlmostEqual(before, -r._pair_error(b, a, 3, boundary)[0])

    def test_real_front_target_and_reference_survive_extra_phase_velocity(self):
        for name, r in variants.items():
            cars = strings(r, stagger=False, lanes=2)
            ego = cars[1]
            rows = tuple(c for c in cars if c is not ego)
            following = r._front_following(ego, rows)
            actual = r._following(ego, rows, 2)
            with self.subTest(candidate=name):
                self.assertEqual(actual[1:3], following[1:3])
                self.assertAlmostEqual(actual[0] - following[0], .4)

    def test_original_hard_safe_speed_overrides_phase_acceleration(self):
        for name, r in variants.items():
            ego, front, peer = car(r, 0, 700, 0), car(r, 1, 708, 0, 0), car(r, 2, 700, 1)
            rows = (front, peer)
            command, _ = r.decide(ego, rows, r.Memory(), "formation", None)
            with self.subTest(candidate=name):
                self.assertLessEqual(command.speed, r.safe_speed(ego, rows))
                self.assertGreaterEqual(command.speed, 0)

    def test_fifty_metre_neighbor_limit_and_private_relation_state(self):
        for name, r in variants.items():
            ego = car(r, 0, 700, 0)
            isolated = r._following(ego, (car(r, 1, 750.001, 1),), 3)
            near = r._following(ego, (car(r, 1, 750, 1),), 3)
            with self.subTest(candidate=name):
                self.assertEqual(isolated[3], 0)
                self.assertAlmostEqual(isolated[0], r.CRUISE)
                self.assertEqual(near[3], 1)

    def test_relabel_reordering_and_remote_traffic_preserve_local_body_control(self):
        for name, r in variants.items():
            cars = strings(r, stagger=False)
            ego, rows = cars[1], tuple(c for c in cars if c is not cars[1])
            expected = r._following(ego, rows, 3)
            change = lambda c: replace(c, track=9001 - 13 * c.track)
            actual = r._following(change(ego), (*reversed(tuple(map(change, rows))), car(r, 50000, 1700, 0)), 3)
            with self.subTest(candidate=name):
                self.assertEqual((actual[0], actual[1], actual[3]), (expected[0], expected[1], expected[3]))
                self.assertEqual(actual[2], 9001 - 13 * expected[2])

    def test_noa_complete_command_and_memory_remain_exactly_frozen_e(self):
        rng = random.Random(202611035)
        for _ in range(600):
            x, lane = rng.uniform(200, 1150), rng.randrange(3)
            values = [(0, x, lane, rng.uniform(0, 33.3))]
            values += [(i, x + rng.uniform(-130, 230), rng.randrange(3), rng.uniform(0, 33.3)) for i in range(1, 10)]
            memory = dict(lane_target=rng.choice([None, 0, 1, 2]), gap=rng.choice([None, (1, 2)]),
                          joining=rng.choice([True, False]))
            old = [car(baseline, *v) for v in values]
            expected = baseline.decide(old[0], old[1:], baseline.Memory(**memory), "noa")
            for r in variants.values():
                cars = [car(r, *v) for v in values]
                actual = r.decide(cars[0], cars[1:], r.Memory(**memory), "noa")
                self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
                self.assertEqual(actual[0].formation_state, 0)


if __name__ == "__main__":
    unittest.main()
