"""Physical snapshots for future-resource lane selection; no traffic simulation."""
from dataclasses import asdict, replace
import importlib.util
import itertools
import os
from pathlib import Path
import random
import sys
import unittest
from test_premerge_topology import base as s

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


r = load("future_resources_candidate", os.environ.get("RULES_F", BASE))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane+.5)*r.LANE_WIDTH, speed, lane)


def exact(value):
    if hasattr(value, "__dataclass_fields__"):
        return exact(asdict(value))
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {key: exact(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(item) for item in value]
    return value


def overloaded_scene():
    # Current 0/1 layer q=715 is complete. Three ending-lane vehicles will use 1.
    ego = car(0, 700., 1)
    rows = (car(1, 715., 0), car(2, 700., 2), car(3, 670., 2), car(4, 640., 2))
    return ego, rows


class FutureResourceTests(unittest.TestCase):
    def test_ending_load_releases_current_full_layer_for_safe_future_balance(self):
        ego, rows = overloaded_scene()
        old, _ = s.decide(ego, rows, s.Memory(), "transform")
        self.assertIsNone(old.lane, "S already moved: the stated missed-resource scene is invalid")
        command, _ = r.decide(ego, rows, r.Memory(), "transform")
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reason, "fill_layer")
        self.assertTrue(r._clear(ego, rows, 0))
        # Future load changes 1:4 -> 2:3. This checks assignment, not slot capture.
        counts = [sum(min(c.lane, 1) == lane for c in (ego, *rows)) for lane in (0, 1)]
        self.assertEqual(counts, [1, 4])
        self.assertLess(abs((counts[0]+1)-(counts[1]-1)), abs(counts[0]-counts[1]))

    def test_ending_vehicle_still_uses_original_mandatory_merge(self):
        _, rows = overloaded_scene()
        ego = replace(rows[1], track=0)
        others = tuple(replace(c, track=i+1) for i, c in enumerate((car(8, 700., 1), rows[0], *rows[2:])))
        self.assertEqual(exact(r.decide(ego, others, r.Memory(), "transform")),
                         exact(s.decide(ego, others, s.Memory(), "transform")))

    def test_physical_target_obstruction_still_blocks_the_new_fill(self):
        ego, rows = overloaded_scene()
        # 4m separation in actual target lane cannot be made safe by future pi.
        command, _ = r.decide(ego, (*rows, car(90, 704., 0)), r.Memory(), "transform")
        self.assertIsNone(command.lane)

    def test_modes_straight_and_outside_preparation_are_identical(self):
        rng = random.Random(202611032100)
        for index in range(700):
            x = rng.uniform(0., 1250.)
            ego = car(0, x, rng.randrange(3), rng.uniform(8., 30.))
            rows = tuple(car(i+1, x+dx, lane, rng.uniform(8., 30.))
                         for i, (dx, lane) in enumerate(itertools.product((-90., -45., 18., 48., 85., 150.), range(3)))
                         if not (lane == ego.lane and abs(dx) < 8.))
            cases = [(mode, drop) for mode in ("noa", "formation") for drop in (None, 1000.)]
            cases.append(("transform", None))
            if not (640. <= x < 1000. or x >= 1000. and ego.lane == 2):
                cases.append(("transform", 1000.))
            for mode, drop in cases:
                with self.subTest(index=index, mode=mode, drop=drop):
                    self.assertEqual(exact(r.decide(ego, rows, r.Memory(), mode, drop)),
                                     exact(s.decide(ego, rows, s.Memory(), mode, drop)))

    def test_ids_and_all_row_permutations_do_not_allocate_priority(self):
        ego, rows = overloaded_scene()
        expected, memory = r.decide(ego, rows, r.Memory(), "transform")
        label = lambda c: replace(c, track=400-17*c.track)
        for order in itertools.permutations(rows):
            command, changed = r.decide(label(ego), tuple(label(c) for c in order), r.Memory(), "transform")
            self.assertEqual((command.speed.hex(), command.lane, command.reason, command.target_x),
                             (expected.speed.hex(), expected.lane, expected.reason, expected.target_x))
            self.assertEqual(changed.lane_target, memory.lane_target)
            # Gap labels are local associations, so compare under the same bijection.
            self.assertEqual(changed.gap, tuple(None if t is None else 400-17*t for t in memory.gap)
                             if memory.gap is not None else None)

    def test_scored_future_slot_is_not_the_executed_gap_target(self):
        ego, rows = overloaded_scene()
        command, _ = r.decide(ego, rows, r.Memory(), "transform")
        self.assertEqual(command.lane, 0)
        # Empty future q=685 is witnessed by ending-lane x=670, pi=1, phi=15.
        scored_future_target = 670.+15.
        self.assertEqual(command.target_x, 700.)  # actual front715 minus real15m gap
        self.assertNotEqual(command.target_x, scored_future_target,
                            "The old lane-only interface silently became a slot tracker")


if __name__ == "__main__":
    unittest.main()
