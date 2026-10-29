"""Real E10 mismatch frame and exact formation invariants for E11."""

import json
from pathlib import Path
import unittest

from noa import native_rules as r


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + 0.5) * 3.3, speed, lane)


class E11RulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/e10_actual_34_7s.json").read_text(
                encoding="utf-8"
            )
        )
        cls.cars = {
            s["id"]: r.Vehicle(i, s["x"], s["y"], s["v"], s["lane"], time=fixture["time_s"])
            for i, s in enumerate(fixture["states"])
        }

    def command(self, name):
        ego = self.cars[name]
        return ego, r._following(
            ego, tuple(c for c in self.cars.values() if c.track != ego.track), 2
        )

    def test_real_lane_zero_head_c1_shares_phase_by_slowing(self):
        ego, (speed, target, reference) = self.command("C1")
        self.assertIsNone(reference)
        self.assertAlmostEqual(target, ego.x - 2.0 / 0.3)
        self.assertLess(speed, ego.speed - 0.1)

    def test_real_lane_one_head_a1_shares_phase_by_accelerating(self):
        ego, (speed, target, reference) = self.command("A1")
        self.assertIsNone(reference)
        self.assertAlmostEqual(target, ego.x + 2.0 / 0.3)
        self.assertAlmostEqual(speed, r._request(ego, target, r.CRUISE))
        self.assertGreater(speed, ego.speed)

    def test_internal_b1_follows_only_its_physical_front_c1(self):
        ego, (speed, target, reference) = self.command("B1")
        front = self.cars["C1"]
        self.assertEqual(reference, front.track)
        self.assertAlmostEqual(target, front.x - 30.0)
        self.assertAlmostEqual(speed, r._request(ego, front.x - 30.0, front.speed))

    def test_internal_a2_follows_only_its_physical_front_a1(self):
        ego, (speed, target, reference) = self.command("A2")
        front = self.cars["A1"]
        self.assertEqual(reference, front.track)
        self.assertAlmostEqual(target, front.x - 30.0)
        self.assertAlmostEqual(speed, r._request(ego, front.x - 30.0, front.speed))

    def check_lattice(self, positions, lanes):
        cars = tuple(car(i, x, lane) for i, (x, lane) in enumerate(positions))
        for ego in cars:
            speed, target, _ = r._following(
                ego, tuple(c for c in cars if c.track != ego.track), lanes
            )
            self.assertAlmostEqual(speed, 28.8)
            self.assertAlmostEqual(target, ego.x)

    def test_three_lane_two_layer_perfect_lattice_is_steady(self):
        self.check_lattice(((100, 2), (70, 2), (85, 1), (55, 1), (100, 0), (70, 0)), 3)

    def test_two_lane_three_layer_perfect_lattice_is_steady(self):
        self.check_lattice(((100, 0), (70, 0), (40, 0), (115, 1), (85, 1), (55, 1)), 2)

    def test_head_seventy_meters_away_is_outside_the_mutual_group(self):
        ego, peer = car(0, 100, 0), car(1, 170, 1)
        speed, target, reference = r._following(ego, (peer,), 3)
        self.assertIsNone(reference)
        self.assertAlmostEqual(target, ego.x)
        self.assertAlmostEqual(speed, 28.8)

    def test_same_lane_front_seventy_meters_away_is_still_not_a_formation_link(self):
        ego, front = car(0, 100, 0), car(1, 170, 0)
        speed, target, reference = r._following(ego, (front,), 3)
        self.assertIsNone(reference)
        self.assertAlmostEqual(speed, 28.8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
