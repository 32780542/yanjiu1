"""N contracts; frozen L is the default red-stage source."""
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


base = load("release_parent", PARENT)
r = load("release_candidate", os.environ.get("RULES_N", PARENT))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def decide(ego, rows, memory=None, mode="transform"):
    return r.decide(ego, rows, memory or r.Memory(), mode, 1000.)


class LocalConflictReleaseTests(unittest.TestCase):
    def same_as_parent(self, ego, rows, memory=None, mode="transform"):
        state = asdict(memory or r.Memory())
        actual = decide(ego, rows, r.Memory(**state), mode)
        expected = base.decide(ego, rows, base.Memory(**state), mode, 1000.)
        self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
        return actual

    def test_unique_actual_middle_blocker_releases_itself_to_the_clear_left(self):
        ego, incoming = car(0, 700, 1), car(1, 700, 2)
        self.assertTrue(r._clear(ego, (incoming,), 0))
        self.assertFalse(r._clear(incoming, (ego, incoming), 1))
        self.assertTrue(r._clear(incoming, (incoming,), 1))
        action, memory = decide(ego, (incoming,))
        self.assertEqual((action.lane, action.reason), (0, "release_ending"))
        self.assertEqual(action.target_x, ego.x)
        self.assertEqual(memory, r.Memory(lane_target=0, gap=(None, None), joining=True))

    def test_release_uses_the_existing_actual_left_gap_not_an_incoming_slot(self):
        ego, incoming = car(0, 700, 1), car(1, 700, 2)
        front, rear = car(2, 730, 0), car(3, 670, 0)
        action, memory = decide(ego, (incoming, front, rear))
        self.assertEqual((action.lane, action.reason), (0, "release_ending"))
        self.assertEqual(action.target_x, 700.)
        self.assertEqual(memory.gap, (front.track, rear.track))
        self.assertTrue(memory.joining)
        self.assertLessEqual(action.speed, r.safe_speed(ego, (incoming, front, rear)))

    def test_left_obstruction_cannot_be_forced_out_of_the_way(self):
        ego = car(0, 700, 1)
        action, memory = self.same_as_parent(ego, (car(1, 700, 2), car(2, 700, 0)))
        self.assertIsNone(action.lane)
        self.assertIsNone(memory.lane_target)

    def test_an_already_clear_ending_vehicle_does_not_request_release(self):
        ego, incoming = car(0, 700, 1), car(1, 715, 2)
        self.assertTrue(r._clear(incoming, (ego, incoming), 1))
        action, _ = self.same_as_parent(ego, (incoming,))
        self.assertIsNone(action.lane)

    def test_two_current_middle_blockers_are_not_replaced_by_a_helper_election(self):
        ego, incoming, blocker = car(0, 700, 1), car(1, 700, 2), car(2, 695, 1)
        self.assertFalse(r._clear(incoming, (incoming, blocker), 1))
        action, _ = self.same_as_parent(ego, (incoming, blocker))
        self.assertIsNone(action.lane)

    def test_ending_vehicle_must_itself_have_entered_the_preparation_region(self):
        ego, incoming = car(0, 641, 1), car(1, 639, 2)
        self.assertFalse(r._clear(incoming, (ego, incoming), 1))
        self.assertTrue(r._clear(incoming, (incoming,), 1))
        action, _ = self.same_as_parent(ego, (incoming,))
        self.assertIsNone(action.lane)

    def test_no_release_outside_preparation_or_for_a_distant_ending_vehicle(self):
        for ego_x, incoming_x in ((500., 500.), (700., 750.001)):
            with self.subTest(ego_x=ego_x, incoming_x=incoming_x):
                action, _ = self.same_as_parent(car(0, ego_x, 1), (car(1, incoming_x, 2),))
                self.assertNotEqual(action.reason, "release_ending")

    def test_only_the_actual_middle_lane_ego_can_release_left(self):
        for lane in (0, 2):
            with self.subTest(lane=lane):
                action, _ = self.same_as_parent(car(0, 700, lane), (car(1, 700, 1),))
                self.assertNotEqual(action.reason, "release_ending")

    def test_existing_own_execution_keeps_priority(self):
        ego, incoming = car(0, 700, 1), car(1, 700, 2)
        moving = replace(ego, y=4.5, vy=-3.3, pending_lane=0)
        memory = r.Memory(lane_target=0, gap=(None, None), joining=True)
        action, _ = self.same_as_parent(moving, (incoming,), memory)
        self.assertEqual(action.reason, "executing")

    def test_joining_vehicle_is_not_given_a_second_release_role(self):
        action, memory = self.same_as_parent(car(0, 700, 1), (car(1, 700, 2),), r.Memory(joining=True))
        self.assertIsNone(action.lane)
        self.assertTrue(memory.joining)

    def test_measured_lateral_motion_without_memory_does_not_get_a_new_release(self):
        ego = replace(car(0, 700, 1), y=4.5, vy=-3.3)
        action, _ = self.same_as_parent(ego, (car(1, 700, 2),))
        self.assertNotEqual(action.reason, "release_ending")

    def test_failed_release_does_not_disable_the_original_free_fill(self):
        ego = car(0, 755, 1)
        rows = tuple(car(i + 1, x, lane) for i, (x, lane) in enumerate(
            ((770., 1), (740., 1), (710., 1), (785., 0), (725., 0))))
        action, _ = self.same_as_parent(ego, rows)
        self.assertEqual((action.lane, action.reason), (0, "fill_layer"))

    def test_ending_vehicle_waits_for_actual_occupancy_to_disappear(self):
        ego, incoming = car(0, 700, 1), car(1, 700, 2)
        release, _ = decide(ego, (incoming,))
        self.assertEqual(release.reason, "release_ending")
        waiting, _ = decide(incoming, (ego,))
        self.assertIsNone(waiting.lane)
        self.assertEqual(waiting.reason, "approach_gap")
        cleared, _ = decide(incoming, (replace(ego, lane=0, y=1.65),))
        self.assertEqual((cleared.lane, cleared.reason), (1, "merge"))

    def test_relabel_reorder_remote_and_multiple_eligible_incoming_do_not_assign_ids(self):
        ego, rows = car(0, 700, 1), (car(1, 700, 2), car(2, 706, 2))
        expected = decide(ego, rows)
        label = lambda c: replace(c, track=9001 - 17 * c.track)
        actual = decide(label(ego), (car(77777, 1000, 0), *map(label, reversed(rows))))
        self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
        self.assertEqual(expected[0].reason, "release_ending")

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
