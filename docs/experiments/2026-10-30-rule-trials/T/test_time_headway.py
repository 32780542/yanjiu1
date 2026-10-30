"""Behavioral contracts for one-front time-headway following, with real rules."""
import argparse
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[4] / "variants/phase5g_pure_formation/noa/native_rules.py"


class TimeHeadwayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("trial_T_rules", SOURCE)
        cls.r = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.r
        spec.loader.exec_module(cls.r)

    def car(self, key, x, speed=28.8, lane=0):
        return self.r.Vehicle(key, x, (lane + .5) * 3.3, speed, lane)

    def command(self, ego, rows, mode):
        return self.r.decide(ego, rows, self.r.Memory(), mode, None)[0]

    def test_same_speed_equilibrium_at_each_time_headway_distance(self):
        for speed in (5.0, 10.0, 20.0, 28.8, 31.0):
            with self.subTest(speed=speed):
                distance = 5.5 + (30 - 5.5) / 28.8 * speed
                ego, front = self.car(0, 100, speed), self.car(7, 100 + distance, speed)
                self.assertAlmostEqual(self.command(ego, (front,), "transform").speed, speed)

    def test_noa_and_formation_share_longitudinal_following_without_noa_membership(self):
        ego, front = self.car(0, 100, 20), self.car(1, 125, 19)
        noa = self.command(ego, (front,), "noa")
        formation = self.command(ego, (front,), "transform")
        self.assertAlmostEqual(noa.speed, formation.speed)
        self.assertEqual(noa.formation_state, 0)
        self.assertEqual(formation.formation_state, 1)

    def test_spacing_uses_own_speed_and_true_nearest_predecessor(self):
        ego = self.car(0, 100, 20)
        distance = 5.5 + (30 - 5.5) / 28.8 * ego.speed
        front = self.car(8, 100 + distance, 27)
        far = self.car(1, 148, 3)
        command = self.command(ego, (far, front), "transform")
        self.assertEqual(command.reference, front.track)
        self.assertAlmostEqual(command.speed, 20 + .2 * (27 - 20))

    def test_cruise_equilibrium_is_still_thirty_metres(self):
        ego, front = self.car(0, 100), self.car(5, 130)
        self.assertAlmostEqual(self.command(ego, (front,), "transform").speed, 28.8)

    def test_noa_has_no_cross_lane_alignment_and_far_front_is_safety_only(self):
        ego = self.car(0, 100)
        peer, far = self.car(1, 110, lane=1), self.car(2, 170, 0)
        command = self.command(ego, (peer, far), "noa")
        self.assertEqual(command.speed, 28.8)
        self.assertIsNone(command.target_x)
        self.assertIsNone(command.reference)
        self.assertEqual(command.formation_state, 0)

    def test_track_relabeling_and_remote_vehicle_do_not_change_motion(self):
        ego, front = self.car(0, 100, 20), self.car(1, 124, 19)
        expected = self.command(ego, (front,), "transform")
        actual = self.command(ego, (replace(front, track=801), self.car(99, 1000, 0)), "transform")
        self.assertEqual((actual.speed, actual.target_x, actual.lane),
                         (expected.speed, expected.target_x, expected.lane))

    def test_stopped_front_keeps_current_geometric_safety_cap(self):
        ego, front = self.car(0, 100, 20), self.car(1, 108, 0)
        for mode in ("noa", "transform"):
            self.assertLessEqual(self.command(ego, (front,), mode).speed,
                                 self.r.safe_speed(ego, (front,)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=SOURCE)
    args, remaining = parser.parse_known_args()
    SOURCE = args.rules.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
