"""G0/G0N keep gap execution and autonomous overtaking, remove formation."""
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
SOURCES = {
    "G0": ("local_phase_velocity_damping", "a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762"),
    "G0N": ("local_conflict_release", "5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6"),
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


parents, variants = {}, {}
for label, (directory, expected) in SOURCES.items():
    path = ROOT / "tmp/staggered_bottleneck/candidates" / directory / "native_rules.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    parents[label] = load("matched_parent_" + label, path)
    variants[label] = load("matched_candidate_" + label, os.environ.get("RULES_" + label, path))


def car(r, track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def control(command):
    value = asdict(command)
    value.pop("formation_state")
    return value


class MatchedNonformationTests(unittest.TestCase):
    def test_cross_lane_phase_does_not_change_the_original_front_following(self):
        for label, r in variants.items():
            ego, peer = car(r, 0, 100, 0), car(r, 1, 100, 1, 20.)
            with self.subTest(candidate=label):
                self.assertEqual(r._following(ego, (peer,), 3), (r.CRUISE, None, None, 0))

    def test_witness_cannot_bridge_a_front_outside_the_original_fifty_metres(self):
        for label, r in variants.items():
            ego, front, witness = car(r, 0, 100, 1), car(r, 1, 160, 1), car(r, 2, 145, 0)
            with self.subTest(candidate=label):
                self.assertEqual(r._following(ego, (front, witness), 2, 640.), (r.CRUISE, None, None, 0))

    def test_true_front_cth_is_exact_but_relation_flag_is_zero(self):
        for label, r in variants.items():
            ego, front, peer = car(r, 0, 100, 0, 20.), car(r, 1, 130, 0, 10.), car(r, 2, 100, 1)
            rows = (front, peer)
            with self.subTest(candidate=label):
                self.assertEqual(r._following(ego, rows, 3), (*r._front_following(ego, rows)[:3], 0))

    def test_slow_front_overtaking_keeps_the_noa_empty_corridor_choice(self):
        for label, r in variants.items():
            ego, front = car(r, 0, 500, 1, 20.), car(r, 1, 530, 1, 10.)
            for lane0_x, lane2_x, expected in ((None, None, 0), (550., 580., 2)):
                rows = [front]
                if lane0_x is not None:
                    rows += [car(r, 2, lane0_x, 0), car(r, 3, lane2_x, 2)]
                with self.subTest(candidate=label, left=lane0_x):
                    noa = parents[label].decide(ego, rows, parents[label].Memory(), "noa", None)[0]
                    self.assertEqual(noa.lane, expected)
                    self.assertEqual(r._fill(ego, rows, 3), expected)
                    command, _ = r.decide(ego, rows, r.Memory(), "transform", 1000.)
                    self.assertEqual(command.lane, expected)
                    self.assertEqual(command.formation_state, 0)

    def test_preparation_excludes_the_closing_lane_and_preserves_mandatory_priority(self):
        for label, r in variants.items():
            ego = car(r, 0, 700, 1, 20.)
            rows = (car(r, 1, 730, 1, 10.), car(r, 2, 705, 0))
            with self.subTest(candidate=label, case="closing"):
                self.assertIsNone(r.decide(ego, rows, r.Memory(), "transform", 1000.)[0].lane)
            ego = car(r, 0, 700, 0, 20.)
            rows = (car(r, 1, 730, 0, 10.), car(r, 2, 700, 2, 20.))
            with self.subTest(candidate=label, case="mandatory"):
                self.assertTrue(r._mandatory_priority(ego, rows, 1, 1000.))
                self.assertIsNone(r.decide(ego, rows, r.Memory(), "transform", 1000.)[0].lane)

    def test_cruise_geometry_does_not_trigger_formation_cell_filling(self):
        for label, r in variants.items():
            ego = car(r, 0, 755, 1)
            rows = tuple(car(r, i + 1, x, lane) for i, (x, lane) in enumerate(
                ((770., 1), (740., 1), (710., 1), (785., 0), (725., 0))))
            with self.subTest(candidate=label):
                self.assertIsNone(r._fill(ego, rows, 2))
                self.assertIsNone(r.decide(ego, rows, r.Memory(), "transform", 1000.)[0].lane)

    def test_actual_gap_merge_and_approach_keep_parent_execution(self):
        for label, r in variants.items():
            parent = parents[label]
            for ego_x, middle in ((718., (730., 706.)), (700., (705., 690.))):
                ego = car(r, 0, ego_x, 2)
                rows = tuple(car(r, i + 1, x, 1) for i, x in enumerate(middle))
                actual = r.decide(ego, rows, r.Memory(), "transform", 1000.)
                expected = parent.decide(ego, rows, parent.Memory(), "transform", 1000.)
                with self.subTest(candidate=label, ego_x=ego_x):
                    self.assertEqual((control(actual[0]), asdict(actual[1])), (control(expected[0]), asdict(expected[1])))
                    self.assertEqual(actual[0].formation_state, 0)

    def test_own_moving_gap_execution_remains_exact_except_disabled_flag(self):
        for label, r in variants.items():
            parent = parents[label]
            ego = replace(car(r, 0, 700, 1), y=4.5, vy=-3.3, pending_lane=0)
            rows = (car(r, 1, 730, 0), car(r, 2, 670, 0), car(r, 3, 700, 2))
            state = dict(lane_target=0, gap=(1, 2), joining=True)
            actual = r.decide(ego, rows, r.Memory(**state), "transform", 1000.)
            expected = parent.decide(ego, rows, parent.Memory(**state), "transform", 1000.)
            with self.subTest(candidate=label):
                self.assertEqual((control(actual[0]), asdict(actual[1])), (control(expected[0]), asdict(expected[1])))
                self.assertEqual(actual[0].reason, "executing")
                self.assertEqual(actual[0].formation_state, 0)

    def test_only_g0n_retains_the_independent_unique_blocker_release(self):
        for label, r in variants.items():
            ego, incoming = car(r, 0, 700, 1), car(r, 1, 700, 2)
            action, memory = r.decide(ego, (incoming,), r.Memory(), "transform", 1000.)
            with self.subTest(candidate=label):
                self.assertEqual(action.formation_state, 0)
                if label == "G0N":
                    self.assertEqual((action.lane, action.reason), (0, "release_ending"))
                    self.assertEqual(memory, r.Memory(lane_target=0, gap=(None, None), joining=True))
                    wait, _ = r.decide(incoming, (ego,), r.Memory(), "transform", 1000.)
                    self.assertIsNone(wait.lane)
                else:
                    self.assertIsNone(action.lane)
                    self.assertIsNone(memory.lane_target)

    def test_g0n_does_not_release_when_left_or_another_middle_car_still_blocks(self):
        r = variants["G0N"]
        ego, incoming = car(r, 0, 700, 1), car(r, 1, 700, 2)
        for other in (car(r, 2, 700, 0), car(r, 2, 695, 1)):
            with self.subTest(blocker_lane=other.lane):
                command, _ = r.decide(ego, (incoming, other), r.Memory(), "transform", 1000.)
                self.assertNotEqual(command.reason, "release_ending")

    def test_remote_and_relabel_do_not_change_the_matched_overtake(self):
        for label, r in variants.items():
            ego, front = car(r, 0, 500, 1, 20.), car(r, 1, 530, 1, 10.)
            expected = r.decide(ego, (front,), r.Memory(), "transform", 1000.)
            actual = r.decide(replace(ego, track=991), (car(r, 7777, 1500, 2), replace(front, track=17)),
                              r.Memory(), "transform", 1000.)
            with self.subTest(candidate=label):
                self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))

    def test_six_hundred_states_preserve_complete_noa_and_disable_all_formation_flags(self):
        oracle = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz"
        with gzip.open(oracle, "rt", encoding="utf-8") as stream:
            for index, line in enumerate(stream):
                if index == 600:
                    break
                state = json.loads(line)["state"]
                memory = state["memory"]
                if memory["gap"] is not None:
                    memory["gap"] = tuple(memory["gap"])
                for label, r in variants.items():
                    parent = parents[label]
                    cars = [r.Vehicle(**c) for c in state["cars"]]
                    actual = r.decide(cars[0], cars[1:], r.Memory(**memory), "noa", state["drop_x"])
                    expected = parent.decide(cars[0], cars[1:], parent.Memory(**memory), "noa", state["drop_x"])
                    self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))
                    self.assertEqual(actual[0].speed.hex(), expected[0].speed.hex())
                    self.assertEqual(r.safe_speed(cars[0], cars[1:]).hex(), parent.safe_speed(cars[0], cars[1:]).hex())
                    for mode in ("formation", "transform"):
                        command, _ = r.decide(cars[0], cars[1:], r.Memory(**memory), mode, state["drop_x"])
                        self.assertEqual(command.formation_state, 0)
                        self.assertLessEqual(command.speed, r.safe_speed(cars[0], cars[1:]))


if __name__ == "__main__":
    unittest.main()
