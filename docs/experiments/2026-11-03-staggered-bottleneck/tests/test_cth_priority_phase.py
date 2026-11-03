"""S gives the real front's CTH correction priority over opposite phase speed."""
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


base = load("cth_priority_parent", PARENT)
r = load("cth_priority_candidate", os.environ.get("RULES_S", PARENT))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def exact(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(v) for v in value]
    return value


class CTHPriorityPhaseTests(unittest.TestCase):
    def test_phase_acceleration_cannot_cancel_actual_front_deceleration(self):
        ego, front, peer = car(0, 100, 1), car(1, 124, 1), car(2, 125.5, 0)
        rows = (front, peer)
        cf, old, actual = r._front_following(ego, rows), base._following(ego, rows, 2), r._following(ego, rows, 2)
        self.assertAlmostEqual(cf[0], 28.44)
        self.assertAlmostEqual(old[0], 28.84)
        self.assertEqual(exact(actual), exact(cf))

    def test_phase_deceleration_cannot_cancel_actual_front_acceleration(self):
        ego, front, peer = car(0, 100, 0), car(1, 136, 0), car(2, 75, 1)
        rows = (front, peer)
        cf, old, actual = r._front_following(ego, rows), base._following(ego, rows, 2), r._following(ego, rows, 2)
        self.assertAlmostEqual(cf[0], 29.16)
        self.assertAlmostEqual(old[0], 28.76)
        self.assertEqual(exact(actual), exact(cf))

    def test_same_direction_and_zero_cf_keep_the_entire_L_following_exact(self):
        for lane, front_x, peer_x in ((1, 124., 105.5), (0, 136., 95.), (0, 130., 95.)):
            ego, front, peer = car(0, 100, lane), car(1, front_x, lane), car(2, peer_x, 1-lane)
            rows = (front, peer)
            with self.subTest(lane=lane, front_x=front_x):
                self.assertEqual(exact(r._following(ego, rows, 2)), exact(base._following(ego, rows, 2)))
                self.assertNotEqual(r._following(ego, rows, 2)[0], r._front_following(ego, rows)[0])

    def test_free_heads_are_not_modified(self):
        for speed in (10., 28.8):
            ego, peer = car(0, 100, 0, speed), car(1, 95, 1, speed)
            with self.subTest(speed=speed):
                self.assertIsNone(r._front_following(ego, (peer,))[2])
                self.assertEqual(exact(r._following(ego, (peer,), 2)), exact(base._following(ego, (peer,), 2)))

    def test_relabel_remote_and_reordering_preserve_the_actual_reference(self):
        ego, front, peer = car(0, 100, 1), car(1, 124, 1), car(2, 125.5, 0)
        expected = r._following(ego, (front, peer), 2)
        label = lambda c: replace(c, track=9001-17*c.track)
        actual = r._following(label(ego), (car(77777, 1000, 2), label(peer), label(front)), 2)
        self.assertEqual(exact((actual[0], actual[1], actual[3])), exact((expected[0], expected[1], expected[3])))
        self.assertEqual(actual[2], label(front).track)

    def test_original_hard_safe_cap_still_overrides_an_unsafe_cf_request(self):
        ego, front = car(0, 100, 0, 33.3), car(1, 108, 0, 0.)
        self.assertGreater(r._following(ego, (front,), 2)[0], r.safe_speed(ego, (front,)))
        command, _ = r.decide(ego, (front,), r.Memory(), "formation", None)
        self.assertEqual(command.speed.hex(), r.safe_speed(ego, (front,)).hex())

    def test_three_hundred_saved_states_keep_complete_noa_and_safety_exact(self):
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
                self.assertEqual(r.safe_speed(cars[0], cars[1:]).hex(), base.safe_speed(cars[0], cars[1:]).hex())


if __name__ == "__main__":
    unittest.main()
