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
        )[:3]

    def test_real_lane_zero_head_c1_uses_fixed_phase_of_actual_a1(self):
        ego, (speed, target, reference) = self.command("C1")
        peer = self.cars["A1"]
        # The existing 11.537m separation needs +3.463m in fixed 0/15 geometry.
        error = peer.x - ego.x + 15.0
        self.assertIsNone(reference)
        self.assertLess(abs(r.POSITION_GAIN * error), 2.0)
        self.assertAlmostEqual(target, ego.x + error)
        self.assertAlmostEqual(speed, r._request(ego, target, r.CRUISE))
        self.assertGreater(speed, ego.speed)

    def test_real_lane_one_head_a1_uses_fixed_phase_of_actual_c1(self):
        ego, (speed, target, reference) = self.command("A1")
        peer = self.cars["C1"]
        error = peer.x - ego.x - 15.0
        self.assertIsNone(reference)
        self.assertLess(abs(r.POSITION_GAIN * error), 2.0)
        self.assertAlmostEqual(target, ego.x + error)
        self.assertAlmostEqual(speed, r._request(ego, target, r.CRUISE))
        self.assertLess(speed, ego.speed)

    def test_internal_b1_keeps_front_c1_and_couples_to_actual_body_a2(self):
        ego, (speed, target, reference) = self.command("B1")
        front, peer = self.cars["C1"], self.cars["A2"]
        distance = 5.5 + (30.0 - 5.5) / 28.8 * ego.speed
        self.assertEqual(reference, front.track)
        self.assertAlmostEqual(target, front.x - distance)
        # The mutual B1/A2 body edge has e=+0.728852m, independently of CTH.
        error = peer.x - ego.x + 15.0
        phase_speed = max(-2.0, min(2.0, r.POSITION_GAIN * error))
        cf = r._request(ego, front.x - distance, front.speed)
        self.assertLess(phase_speed * (cf - ego.speed), 0.0)
        # In these measured body states phase opposes the real-front CTH action.
        self.assertEqual(speed.hex(), cf.hex())

    def test_internal_a2_keeps_front_a1_and_couples_to_actual_body_b1(self):
        ego, (speed, target, reference) = self.command("A2")
        front, peer = self.cars["A1"], self.cars["B1"]
        distance = 5.5 + (30.0 - 5.5) / 28.8 * ego.speed
        self.assertEqual(reference, front.track)
        self.assertAlmostEqual(target, front.x - distance)
        error = peer.x - ego.x - 15.0
        phase_speed = max(-2.0, min(2.0, r.POSITION_GAIN * error))
        cf = r._request(ego, front.x - distance, front.speed)
        self.assertLess(phase_speed * (cf - ego.speed), 0.0)
        # In these measured body states phase opposes the real-front CTH action.
        self.assertEqual(speed.hex(), cf.hex())

    def check_lattice(self, positions, lanes):
        cars = tuple(car(i, x, lane) for i, (x, lane) in enumerate(positions))
        for ego in cars:
            speed, target, _, _ = r._following(
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
        speed, target, reference, _ = r._following(ego, (peer,), 3)
        self.assertIsNone(reference)
        self.assertAlmostEqual(target, ego.x)
        self.assertAlmostEqual(speed, 28.8)

    def test_same_lane_front_seventy_meters_away_is_still_not_a_formation_link(self):
        ego, front = car(0, 100, 0), car(1, 170, 0)
        speed, target, reference, _ = r._following(ego, (front,), 3)
        self.assertIsNone(reference)
        self.assertAlmostEqual(speed, 28.8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
