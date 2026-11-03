"""Matched planner control: ordinary following/overtaking, no staggered formation."""
from dataclasses import asdict
import os
from pathlib import Path
import random
import unittest
from test_premerge_topology import base, exact, load

ROOT = Path(__file__).resolve().parents[4]
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py"
p = load("matched_gap_parent", PARENT)
r = load("matched_gap_control", os.environ.get("RULES_G0", PARENT))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class MatchedGapControlTests(unittest.TestCase):
    def test_plain_following_and_merging_report_no_formation(self):
        for lane in range(3):
            ego = car(0, 700., lane)
            command, _ = r.decide(ego, (car(1, 730., lane),), r.Memory(), "transform")
            self.assertEqual(command.formation_state, 0)

    def test_ordinary_slow_front_overtaking_remains_available(self):
        ego = car(0, 700., 0, 20.)
        rows = (car(1, 720., 0, 20.), car(2, 800., 1))
        command, _ = r.decide(ego, rows, r.Memory(), "transform")
        self.assertEqual(command.lane, 1)
        self.assertEqual(command.reason, "normal_overtake")
        self.assertEqual(command.formation_state, 0)

    def test_necessary_gap_planning_and_admission_match_parent(self):
        for x in (705., 719., 755.):
            ego, rows = car(0, x, 2), (car(1, 770., 1), car(2, 690., 1))
            actual, actual_memory = r.decide(ego, rows, r.Memory(), "transform")
            expected, expected_memory = p.decide(ego, rows, p.Memory(), "transform")
            a, b = asdict(actual), asdict(expected)
            a.pop("formation_state")
            b.pop("formation_state")
            self.assertEqual(exact(a), exact(b))
            self.assertEqual(exact(actual_memory), exact(expected_memory))
            self.assertEqual(actual.formation_state, 0)

    def test_noa_and_hard_safety_are_exact_original_S(self):
        rng = random.Random(202611032020)
        for _ in range(1000):
            x = rng.uniform(100., 980.)
            ego = car(0, x, rng.randrange(3), rng.uniform(0., 33.3))
            rows = tuple(car(i + 1, x + dx, lane, rng.uniform(0., 33.3))
                         for i, (lane, dx) in enumerate((lane, dx) for lane in range(3) for dx in (-80., -40., 20., 55., 100.)))
            self.assertEqual(exact(r.decide(ego, rows, r.Memory(), "noa")),
                             exact(base.decide(ego, rows, base.Memory(), "noa")))
            self.assertEqual(r.safe_speed(ego, rows).hex(), base.safe_speed(ego, rows).hex())


if __name__ == "__main__":
    unittest.main()
