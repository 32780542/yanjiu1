"""GP physical snapshots and independent nominal polynomial checks, no SUMO."""
from dataclasses import asdict, replace
import importlib.util
import itertools
import math
import os
from pathlib import Path
import random
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


s = load("bound_gap_base", BASE)
r = load("bound_gap_candidate", os.environ.get("RULES_GP", BASE))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane+.5)*r.LANE_WIDTH, speed, lane)


def exact(value):
    if hasattr(value, "__dataclass_fields__"):
        return exact(asdict(value))
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(item) for item in value]
    return value


def scene(x=700.):
    return car(0, x, 2), (car(1, 620., 1), car(2, 690., 1), car(3, 720., 1))


class BoundRealGapTests(unittest.TestCase):
    def test_skip_compressed_current_gap_and_do_not_merge_into_wrong_gap(self):
        ego, rows = scene()
        self.assertTrue(r._clear(ego, rows, 1))  # old adjacent gap is clear enough
        command, memory = r.decide(ego, rows, r.Memory(), "transform")
        self.assertEqual(memory.gap, (2, 1))  # real70m gap behind, not current30m
        self.assertIsNone(command.lane)  # ego700 is ahead of selected front690
        self.assertLess(command.speed, ego.speed)
        self.assertAlmostEqual(command.target_x, 660.)

    def test_hold_visible_noncurrent_pair_until_ego_enters_it(self):
        ego, rows = scene()
        held = r.Memory(lane_target=1, gap=(2, 1), joining=True)
        command, memory = r.decide(ego, rows, held, "transform")
        self.assertEqual(memory.gap, (2, 1))
        self.assertIsNone(command.lane)
        entered, rows = scene(680.)
        command, memory = r.decide(entered, rows, memory, "transform")
        self.assertEqual(memory.gap, (2, 1))
        self.assertEqual(command.lane, 1)
        self.assertTrue(r._clear(entered, rows, 1))

    def test_absent_or_compressed_resources_fall_back_to_S_exactly(self):
        for x in (700., 970., 971.2, 999., 1001.):
            ego = car(0, x, 2)
            for rows in ((), (car(1, x+25, 1),),
                         (car(1, x-15, 1), car(2, x+15, 1))):
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(), "transform")),
                                 exact(s.decide(ego, rows, s.Memory(), "transform")))

    def test_noa_formation_straight_and_target0_are_unchanged(self):
        rng = random.Random(202611032130)
        for _ in range(450):
            x = rng.uniform(100., 1100.)
            ego = car(0, x, rng.randrange(3), rng.uniform(0., 33.3))
            rows = tuple(car(i+1, x+dx, lane, rng.uniform(0., 33.3)) for i, (lane, dx)
                         in enumerate(itertools.product(range(3), (-80., -40., 20., 55., 100.))))
            for mode, drop in (("noa", 1000.), ("noa", None), ("formation", 1000.),
                               ("formation", None), ("transform", None)):
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(), mode, drop)),
                                 exact(s.decide(ego, rows, s.Memory(), mode, drop)))
            if ego.lane == 1:
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(lane_target=0), "transform")),
                                 exact(s.decide(ego, rows, s.Memory(lane_target=0), "transform")))

    def test_no_nominal_resource_preserves_S_already_started_lateral_execution(self):
        ego = replace(car(0, 700., 2), vy=-.2, pending_lane=1)
        rows = (car(1, 680., 1), car(2, 704., 1))
        memory = r.Memory(lane_target=1, gap=(2, 1), joining=True)
        self.assertFalse(r._clear(ego, rows, 1))
        self.assertEqual(exact(r.decide(ego, rows, memory, "transform")),
                         exact(s.decide(ego, rows, s.Memory(lane_target=1, gap=(2, 1), joining=True), "transform")))

    def test_pair_labels_permutations_and_invisible_cars_do_not_assign_priority(self):
        ego, rows = scene()
        command, memory = r.decide(ego, rows, r.Memory(), "transform")
        label = lambda c: replace(c, track=500-19*c.track)
        for order in itertools.permutations(rows):
            changed, held = r.decide(label(ego), tuple(label(c) for c in order), r.Memory(), "transform")
            self.assertEqual(exact(changed), exact(command))
            self.assertEqual(held.gap, tuple(500-19*t for t in memory.gap))
        outside = car(90, 901., 1, 0.)
        self.assertEqual(exact(r.decide(ego, (*rows, outside), r.Memory(), "transform")),
                         exact((command, memory)))

    def test_original_safe_speed_and_real_obstruction_are_preserved(self):
        ego, rows = scene(680.)
        rows = (*rows, car(8, 683., 1), car(9, 685., 2, 0.))
        command, _ = r.decide(ego, rows, r.Memory(), "transform")
        self.assertIsNone(command.lane)
        self.assertLessEqual(command.speed, s.safe_speed(ego, rows))
        self.assertEqual(r.safe_speed(ego, rows), s.safe_speed(ego, rows))

    def test_nominal_polynomials_obey_acceleration_peak_speed_and_road_bounds(self):
        self.assertTrue(callable(getattr(r, "_gap_plan", None)), "planner is not implemented")
        rng = random.Random(202611032140)
        accepted = 0
        for _ in range(1600):
            ego = car(0, rng.uniform(640., 960.), 2, rng.choice((0., 33.3, rng.uniform(0., 33.3))))
            rear = car(1, ego.x+rng.uniform(-90., 30.), 1, rng.choice((0., 33.3, rng.uniform(0., 33.3))))
            front = car(2, rear.x+rng.uniform(10., 180.), 1, rng.choice((0., 33.3, rng.uniform(0., 33.3))))
            plan = r._gap_plan(ego, (rear, front), 1, None, 1000.)
            if plan is None:
                continue
            accepted += 1
            g, u, gap, T = plan
            D, E = g+u*T-ego.x-ego.speed*T, u-ego.speed
            A, B = 6*D/T**2-2*E/T, 6*E/T**2-12*D/T**3
            self.assertGreaterEqual(A, -10.-1e-8)
            self.assertLessEqual(A, 5.+1e-8)
            self.assertGreaterEqual(A+B*T, -10.-1e-8)
            self.assertLessEqual(A+B*T, 5.+1e-8)
            times = [T*j/100 for j in range(101)]
            if B and 0 < -A/B < T:
                times.append(-A/B)
            velocities = [ego.speed+A*t+B*t*t/2 for t in times]
            self.assertGreaterEqual(min(velocities), -1e-8)
            self.assertLessEqual(max(velocities), 33.3+1e-8)
            X = g+u*T
            self.assertLessEqual(X+u, 1000.+1e-8)
            self.assertGreaterEqual(X, rear.x+rear.speed*T+5.5+r.HEADWAY*rear.speed-1e-8)
            self.assertLessEqual(X, front.x+front.speed*T-5.5-r.HEADWAY*u+1e-8)
        self.assertGreater(accepted, 25)


if __name__ == "__main__":
    unittest.main()
