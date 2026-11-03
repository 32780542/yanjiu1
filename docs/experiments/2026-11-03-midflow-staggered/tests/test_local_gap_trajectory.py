"""Local minimum-acceleration gap approach, with the same NOA and hard physics."""
from dataclasses import replace
import os
from pathlib import Path
import random
import unittest
from test_premerge_topology import base, exact, load

ROOT = Path(__file__).resolve().parents[4]
r = load("midflow_local_gap_trajectory", os.environ.get("RULES_C5", ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class LocalGapTrajectoryTests(unittest.TestCase):
    def test_five_second_endpoint_approach_uses_initial_minimum_energy_acceleration(self):
        ego = car(0, 705., 2)
        rows = (car(1, 730., 1), car(2, 670., 1))
        command, memory = r.decide(ego, rows, r.Memory(), "transform")
        self.assertEqual(command.reason, "merge")
        self.assertEqual(command.lane, 1)
        self.assertEqual(command.target_x, 700.)
        # e=-5 m, dv=0: a(0)=6e/5^2=-1.2 m/s2, next speed=28.68.
        self.assertAlmostEqual(command.speed, 28.68)
        self.assertEqual(memory.gap, (1, 2))

    def test_relative_velocity_is_part_of_the_same_endpoint_solution(self):
        ego = car(0, 705., 2)
        rows = (car(1, 730., 1, 20.), car(2, 670., 1, 20.))
        speed, target, memory = r._join_speed(ego, rows, r.Memory(), 1)
        self.assertEqual(target, 700.)
        self.assertAlmostEqual(speed, 27.976)
        self.assertEqual(memory.gap, (1, 2))

    def test_aligned_equal_speed_gap_has_no_tracking_acceleration(self):
        ego = car(0, 700., 2)
        speed, target, _ = r._join_speed(ego, (car(1, 730., 1), car(2, 670., 1)), r.Memory(), 1)
        self.assertEqual(target, ego.x)
        self.assertEqual(speed.hex(), ego.speed.hex())

    def test_labels_and_row_order_preserve_the_real_gap(self):
        ego, rows = car(0, 705., 2), (car(1, 730., 1), car(2, 670., 1))
        before, memory = r.decide(ego, rows, r.Memory(), "transform")
        label = lambda c: replace(c, track=91 - 13 * c.track)
        after, changed = r.decide(label(ego), tuple(label(c) for c in reversed(rows)), r.Memory(), "transform")
        self.assertEqual(exact(before), exact(after))
        self.assertEqual(changed.gap, tuple(91 - 13 * item for item in memory.gap))

    def test_noa_commands_and_physical_safe_speed_stay_exact(self):
        rng = random.Random(202611031910)
        for _ in range(1000):
            x = rng.uniform(100., 990.)
            ego = car(0, x, rng.randrange(3), rng.uniform(0., 33.3))
            rows = tuple(car(i + 1, x + dx, lane, rng.uniform(0., 33.3))
                         for i, (lane, dx) in enumerate((lane, dx) for lane in range(3) for dx in (-80., -40., 20., 55., 100.)))
            for drop in (None, 1000.):
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(), "noa", drop)),
                                 exact(base.decide(ego, rows, base.Memory(), "noa", drop)))
            self.assertEqual(r.safe_speed(ego, rows).hex(), base.safe_speed(ego, rows).hex())


if __name__ == "__main__":
    unittest.main()
