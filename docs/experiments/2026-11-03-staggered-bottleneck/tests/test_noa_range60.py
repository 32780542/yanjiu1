"""NOA60 range sensitivity; fixed J2fast is the default red-stage source."""
from dataclasses import asdict, replace
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import sys
import unittest


ROOT = Path(__file__).resolve().parents[4]
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == "03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


base = load("range60_parent", PARENT)
r = load("range60_candidate", os.environ.get("RULES_NOA60", PARENT))


def car(track, x, lane=0, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class NoARange60Tests(unittest.TestCase):
    def test_fifty_five_metre_front_uses_unchanged_cth_formula_and_state_zero(self):
        ego, front = car(0, 100), car(1, 155)
        action, memory = r.decide(ego, (front,), r.Memory(), "noa", None)
        target = front.x - r.LENGTH - r.STANDSTILL - r.HEADWAY * ego.speed
        self.assertEqual(action.reference, front.track)
        self.assertEqual(action.target_x, target)
        self.assertEqual(action.speed.hex(), r._request(ego, target, front.speed).hex())
        self.assertEqual(action.formation_state, 0)
        self.assertEqual(asdict(memory), asdict(r.Memory()))

    def test_sixty_metre_front_is_inclusive_without_an_adjacent_witness(self):
        ego, front = car(0, 100), car(1, 160)
        speed, target, reference, _ = r._front_following(ego, (front,))
        self.assertEqual(reference, front.track)
        self.assertAlmostEqual(target, 130.)
        self.assertAlmostEqual(speed, 30.6)

    def test_a_slow_fifty_five_metre_front_can_reduce_speed_instead_of_improving_tt(self):
        ego, front = car(0, 100), car(1, 155, speed=15.)
        action, _ = r.decide(ego, (front,), r.Memory(), "noa", None)
        self.assertEqual(action.reference, front.track)
        self.assertAlmostEqual(action.speed, 27.54)
        self.assertLess(action.speed, r.CRUISE)

    def test_front_beyond_sixty_metres_has_no_following_effect(self):
        ego = car(0, 100)
        for dx in (60.001, 75., 150., 200.001):
            with self.subTest(dx=dx):
                rows = (car(1, ego.x + dx, speed=15.),)
                self.assertEqual(r._front_following(ego, rows), base._front_following(ego, rows))
                actual = r.decide(ego, rows, r.Memory(), "noa", None)
                expected = base.decide(ego, rows, base.Memory(), "noa", None)
                self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))

    def test_existing_fifty_metre_front_keeps_priority_over_new_farther_front(self):
        ego = car(0, 100)
        rows = (car(1, 155, speed=10.), car(2, 145, speed=25.))
        self.assertEqual(r._front_following(ego, rows), base._front_following(ego, rows))
        self.assertEqual(r._front_following(ego, rows)[2], 2)

    def test_relabel_reorder_and_remote_cars_preserve_the_actual_front(self):
        ego, front = car(0, 100), car(1, 155)
        expected, memory = r.decide(ego, (front,), r.Memory(), "noa", None)
        actual, moved_memory = r.decide(replace(ego, track=901), (car(77, 1000), replace(front, track=213)),
                                        r.Memory(), "noa", None)
        self.assertEqual((actual.speed.hex(), actual.target_x, actual.lane, actual.reason, actual.formation_state),
                         (expected.speed.hex(), expected.target_x, expected.lane, expected.reason, 0))
        self.assertEqual(actual.reference, 213)
        self.assertEqual(asdict(memory), asdict(moved_memory))

    def test_stopped_front_still_uses_original_physical_safe_speed(self):
        ego, front = car(0, 100, speed=33.3), car(1, 155, speed=0.)
        action, _ = r.decide(ego, (front,), r.Memory(), "noa", None)
        self.assertEqual(r.safe_speed(ego, (front,)).hex(), base.safe_speed(ego, (front,)).hex())
        self.assertLessEqual(action.speed, r.safe_speed(ego, (front,)))
        self.assertEqual(action.formation_state, 0)

    def test_six_hundred_states_with_a_front_inside_fifty_remain_completely_exact(self):
        rng = random.Random(2026110360)
        for _ in range(600):
            ego = car(0, rng.uniform(100, 1200), rng.randrange(3), rng.uniform(0, 33.3))
            rows = [car(1, ego.x + rng.uniform(6, 50), ego.lane, rng.uniform(0, 33.3))]
            rows += [car(i + 2, ego.x + rng.uniform(-100, 200), rng.randrange(3), rng.uniform(0, 33.3))
                     for i in range(8)]
            state = dict(lane_target=rng.choice((None, 0, 1, 2)), gap=rng.choice((None, (1, 2))),
                         joining=bool(rng.randrange(2)))
            actual = r.decide(ego, rows, r.Memory(**state), "noa", None)
            expected = base.decide(ego, rows, base.Memory(**state), "noa", None)
            self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
            self.assertEqual(actual[0].speed.hex(), expected[0].speed.hex())
            self.assertEqual(r._front_following(ego, rows), base._front_following(ego, rows))
            self.assertEqual(r.cf_speed(ego, rows).hex(), base.cf_speed(ego, rows).hex())


if __name__ == "__main__":
    unittest.main()
