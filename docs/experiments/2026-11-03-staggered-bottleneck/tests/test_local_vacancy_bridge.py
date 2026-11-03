"""L contracts; default is frozen J2fast for the red stage."""
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
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py"
PARENT_SHA = "03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


base = load("vacancy_parent", PARENT)
r = load("vacancy_candidate", os.environ.get("RULES_L", PARENT))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def following(ego, rows):
    return r._following(ego, rows, 2, 640.)


def parent_following(ego, rows):
    return base._following(base.Vehicle(**asdict(ego)), [base.Vehicle(**asdict(c)) for c in rows], 2, 640.)


class LocalVacancyBridgeTests(unittest.TestCase):
    def test_adjacent_witness_binds_the_real_sixty_metre_front(self):
        ego, front, witness = car(0, 100, 1), car(1, 160, 1), car(2, 145, 0)
        actual = following(ego, (front, witness))
        self.assertEqual(actual[2], front.track)
        distance = r.LENGTH + r.STANDSTILL + r.HEADWAY * ego.speed
        self.assertAlmostEqual(actual[1], front.x - distance)
        # The witness has |phase error|=30 to both; it selects the 15m front,
        # not the 45m ego, so this ego has no reciprocal phase edge.
        self.assertAlmostEqual(actual[0], r._request(ego, front.x - distance, front.speed))
        self.assertEqual(actual[3], 1)

    def test_reported_58m_gap_is_a_single_geometric_vacancy(self):
        ego, front = car(0, 1674.374, 1), car(1, 1733.167, 1)
        witness = car(2, 1718.228, 0)
        self.assertGreater(front.x - ego.x, 50.)
        projected = witness.x + r._physical_phase(witness, 3) - r._physical_phase(ego, 3)
        self.assertLess(abs(projected - (front.x - r.GAP)), .1)
        actual = following(ego, (front, witness))
        self.assertEqual(actual[2], front.track)
        self.assertAlmostEqual(actual[1], front.x - r.GAP)

    def test_witness_tolerance_uses_existing_two_metre_layer_tolerance(self):
        ego, front = car(0, 100, 1), car(1, 160, 1)
        for witness_x in (143., 147.):
            with self.subTest(witness_x=witness_x):
                self.assertEqual(following(ego, (front, car(2, witness_x, 0)))[2], front.track)

    def test_no_or_misaligned_witness_keeps_the_original_fifty_metre_rule(self):
        ego, front = car(0, 100, 1), car(1, 160, 1)
        for extra in ((), (car(2, 142.999, 0),), (car(2, 147.001, 0),)):
            with self.subTest(extra=extra):
                self.assertEqual(following(ego, (front, *extra)), parent_following(ego, (front, *extra)))
                self.assertIsNone(following(ego, (front, *extra))[2])

    def test_same_lane_count_cannot_replace_an_adjacent_witness(self):
        ego = car(0, 100, 1)
        rows = (car(1, 160, 1), car(2, 190, 1), car(3, 220, 1), car(4, 70, 1))
        self.assertEqual(following(ego, rows), parent_following(ego, rows))
        self.assertIsNone(following(ego, rows)[2])

    def test_nonadjacent_lane_cannot_prove_the_projected_vacancy(self):
        ego, front, remote_lane = car(0, 100, 0), car(1, 160, 0), car(2, 130, 2)
        self.assertEqual(following(ego, (front, remote_lane)), parent_following(ego, (front, remote_lane)))
        self.assertIsNone(following(ego, (front, remote_lane))[2])

    def test_front_beyond_sixty_metres_is_not_chased(self):
        ego, front, witness = car(0, 100, 1), car(1, 160.001, 1), car(2, 145.001, 0)
        self.assertEqual(following(ego, (front, witness)), parent_following(ego, (front, witness)))
        self.assertIsNone(following(ego, (front, witness))[2])

    def test_existing_fifty_metre_front_remains_first(self):
        ego, front, farther = car(0, 100, 1), car(1, 145, 1), car(2, 160, 1)
        rows = (farther, car(3, 145, 0), front)
        self.assertEqual(following(ego, rows), parent_following(ego, rows))
        self.assertEqual(following(ego, rows)[2], front.track)

    def test_a_farther_witness_cannot_skip_the_nearest_extended_front(self):
        ego = car(0, 100, 1)
        rows = (car(1, 155, 1), car(2, 160, 1), car(3, 145, 0))
        self.assertIsNone(following(ego, rows)[2])
        self.assertEqual(following(ego, rows), parent_following(ego, rows))

    def test_bridge_target_uses_real_front_headway_at_current_speed(self):
        ego, front, witness = car(0, 100, 1, 10.), car(1, 160, 1, 10.), car(2, 145, 0, 10.)
        actual = following(ego, (front, witness))
        self.assertEqual(actual[2], front.track)
        self.assertAlmostEqual(actual[1], front.x - r.LENGTH - r.STANDSTILL - r.HEADWAY * ego.speed)
        self.assertNotAlmostEqual(actual[1], front.x - r.GAP)

    def test_noa_and_cf_front_lookup_still_default_to_fifty_metres(self):
        ego, front, witness = car(0, 100, 1), car(1, 160, 1), car(2, 145, 0)
        rows = (front, witness)
        self.assertIsNone(r._front_following(ego, rows)[2])
        self.assertEqual(r._front_following(ego, rows), base._front_following(ego, rows))
        actual = r.decide(ego, rows, r.Memory(), "noa", 1000.)
        expected = base.decide(ego, rows, base.Memory(), "noa", 1000.)
        self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
        self.assertEqual(r.cf_speed(ego, rows).hex(), base.cf_speed(ego, rows).hex())

    def test_relabel_reorder_and_far_traffic_preserve_real_front_geometry(self):
        ego, front, witness = car(0, 100, 1), car(1, 160, 1), car(2, 145, 0)
        expected = following(ego, (front, witness))
        relabel = lambda c: replace(c, track=9001 - c.track * 13)
        actual = following(relabel(ego), (car(77777, 1000, 2), relabel(witness), relabel(front)))
        self.assertEqual((actual[0], actual[1], actual[3]), (expected[0], expected[1], expected[3]))
        self.assertEqual(actual[2], relabel(front).track)

    def test_original_hard_safe_cap_still_overrides_the_bridge(self):
        ego, front, witness = car(0, 100, 1, 33.3), car(1, 150.1, 1, 0.), car(2, 135.1, 0)
        rows = (front, witness)
        self.assertEqual(following(ego, rows)[2], front.track)
        self.assertGreater(following(ego, rows)[0], r.safe_speed(ego, rows))
        command, _ = r.decide(ego, rows, r.Memory(), "formation", None)
        self.assertEqual(command.speed.hex(), r.safe_speed(ego, rows).hex())

    def test_saved_six_hundred_local_states_keep_noa_command_memory_cf_and_safety_exact(self):
        oracle = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz"
        with gzip.open(oracle, "rt", encoding="utf-8") as stream:
            for index, line in enumerate(stream):
                if index == 600:
                    break
                state = json.loads(line)["state"]
                cars, old = [r.Vehicle(**c) for c in state["cars"]], [base.Vehicle(**c) for c in state["cars"]]
                memory = state["memory"]
                if memory["gap"] is not None:
                    memory["gap"] = tuple(memory["gap"])
                actual = r.decide(cars[0], cars[1:], r.Memory(**memory), "noa", state["drop_x"])
                expected = base.decide(old[0], old[1:], base.Memory(**memory), "noa", state["drop_x"])
                self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
                self.assertEqual(actual[0].speed.hex(), expected[0].speed.hex())
                self.assertEqual(r.cf_speed(cars[0], cars[1:]).hex(), base.cf_speed(old[0], old[1:]).hex())
                self.assertEqual(r.safe_speed(cars[0], cars[1:]).hex(), base.safe_speed(old[0], old[1:]).hex())


if __name__ == "__main__":
    unittest.main()
