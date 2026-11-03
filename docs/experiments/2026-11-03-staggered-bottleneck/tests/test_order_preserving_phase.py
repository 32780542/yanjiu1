"""H contracts; default target is immutable E, not production TM."""
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


baseline = load("phase_frozen_e", E_PATH)
rules = load("order_preserving_rules", os.environ["RULES_PATH"]) if os.environ.get("RULES_PATH") else baseline


class OrderPreservingPhaseTests(unittest.TestCase):
    def car(self, track, x, lane, speed=28.8, y=None, module=rules):
        return module.Vehicle(track, x, (lane + .5) * module.LANE_WIDTH if y is None else y, speed, lane)

    def test_both_existing_staggered_orders_have_zero_pair_error(self):
        for lanes, lane in ((2, 0), (3, 0), (3, 1)):
            for separation in (-15.0, 15.0):
                with self.subTest(lanes=lanes, lane=lane, separation=separation):
                    a, b = self.car(0, 700, lane), self.car(1, 700 + separation, lane + 1)
                    self.assertAlmostEqual(rules._pair_error(a, b, lanes)[0], 0.0)

    def test_an_already_staggered_head_pair_does_not_change_speed_to_swap_order(self):
        for separation in (-15.0, 15.0):
            a, b = self.car(0, 700, 0), self.car(1, 700 + separation, 1)
            for ego, peer in ((a, b), (b, a)):
                with self.subTest(separation=separation, lane=ego.lane):
                    speed, target, _, _ = rules._following(ego, (peer,), 2)
                    self.assertAlmostEqual(speed, rules.CRUISE)
                    self.assertAlmostEqual(target, ego.x)

    def test_same_pair_is_continuous_across_640_and_1000_including_exact_ties(self):
        for boundary in (640.0, 1000.0):
            for dx in (-15.0, -5.0, 0.0, 5.0, 15.0):
                with self.subTest(boundary=boundary, dx=dx):
                    a, b = self.car(0, boundary - 20, 0), self.car(1, boundary - 20 + dx, 1)
                    before, n0 = rules._pair_error(a, b, 3, boundary)
                    after, n1 = rules._pair_error(replace(a, x=a.x + 60), replace(b, x=b.x + 60), 2, boundary)
                    self.assertEqual((n0, n1), (3, 2))
                    self.assertAlmostEqual(before, after)

    def test_pair_error_is_antisymmetric_including_moving_lane_boundaries(self):
        geometry = ((1.65, 4.95), (3.3, 6.6), (2.4, 5.1))
        for lanes in (2, 3):
            for ya, yb in geometry:
                for dx in (-45.0, -15.0, -1.0, 0.0, 1.0, 15.0, 45.0):
                    with self.subTest(lanes=lanes, ya=ya, yb=yb, dx=dx):
                        a, b = self.car(0, 700, 0, y=ya), self.car(1, 700 + dx, 1, y=yb)
                        self.assertAlmostEqual(rules._pair_error(a, b, lanes)[0],
                                               -rules._pair_error(b, a, lanes)[0])

    def test_no_thirty_metre_wrapping_of_a_distant_head(self):
        a = self.car(0, 700, 0)
        for dx in (-45.0, 45.0):
            with self.subTest(dx=dx):
                b = self.car(1, 700 + dx, 1)
                self.assertAlmostEqual(rules._pair_error(a, b, 2)[0], 30.0 if dx > 0 else -30.0)

    def test_lateral_phase_amplitude_stays_continuous_at_lane_centres(self):
        a = self.car(0, 700, 0)
        for y in (3.3, 4.95, 6.6):
            left = rules._pair_error(a, self.car(1, 720, 1, y=y - 1e-6), 2)[0]
            right = rules._pair_error(a, self.car(1, 720, 1, y=y + 1e-6), 2)[0]
            self.assertLess(abs(right - left), 1e-5)

    def test_true_front_cth_has_priority_over_adjacent_head_order(self):
        ego, front = self.car(0, 700, 0), self.car(1, 730, 0)
        for peer_x in (685, 700, 715, 745):
            rows = (front, self.car(2, peer_x, 1))
            self.assertEqual(rules._following(ego, rows, 3), rules._front_following(ego, rows))

    def test_track_relabel_and_remote_observations_do_not_change_head_action(self):
        ego, peer = self.car(0, 700, 0), self.car(1, 715, 1)
        expected, _ = rules.decide(ego, (peer,), rules.Memory(), "formation", None)
        actual, _ = rules.decide(replace(ego, track=500),
                                 (self.car(900, 1700, 0), replace(peer, track=123)),
                                 rules.Memory(), "formation", None)
        self.assertEqual((actual.speed, actual.lane, actual.target_x),
                         (expected.speed, expected.lane, expected.target_x))

    def test_noa_commands_and_private_memory_are_exactly_frozen_e(self):
        rng = random.Random(202611034)
        for _ in range(600):
            x, lane = rng.uniform(200, 1150), rng.randrange(3)
            values = [(0, x, lane, rng.uniform(0, 33.3))]
            values += [(i, x + rng.uniform(-130, 230), rng.randrange(3), rng.uniform(0, 33.3)) for i in range(1, 10)]
            memory = dict(lane_target=rng.choice([None, 0, 1, 2]), gap=rng.choice([None, (1, 2)]),
                          joining=rng.choice([True, False]))
            cars = [[self.car(*v, module=m) for v in values] for m in (rules, baseline)]
            actual = rules.decide(cars[0][0], cars[0][1:], rules.Memory(**memory), "noa")
            expected = baseline.decide(cars[1][0], cars[1][1:], baseline.Memory(**memory), "noa")
            self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))


if __name__ == "__main__":
    unittest.main()
