"""Fixed geometry with a symmetric speed weight on actual phase feedback."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("speed_weighted_rules", Path(os.environ.get(
    "RULES_PATH", "tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py")))
rules = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rules
spec.loader.exec_module(rules)


class SpeedWeightedPhaseTests(unittest.TestCase):
    def car(self, key, x, lane, speed):
        return rules.Vehicle(key, x, (lane + .5) * rules.LANE_WIDTH, speed, lane)

    def frame(self, speed, peer_speed=None, offset=13):
        peer_speed = speed if peer_speed is None else peer_speed
        ego, peer = self.car(0, 700, 1, speed), self.car(1, 700 + offset, 0, peer_speed)
        front = self.car(2, 700 + 5.5 + rules.HEADWAY * speed, 1, speed)
        other_front = self.car(3, peer.x + 5.5 + rules.HEADWAY * peer_speed, 0, peer_speed)
        return ego, peer, front, other_front

    def test_low_speed_body_uses_a_weaker_phase_response(self):
        for speed in (10, 20):
            with self.subTest(speed=speed):
                ego, peer, front, other = self.frame(speed)
                command = rules._following(ego, (peer, front, other), 2, 640)
                self.assertAlmostEqual(command[0], speed - .12 * speed / 28.8)
                self.assertEqual(command[2], front.track)
                self.assertAlmostEqual(command[1], ego.x)

    def test_two_speeds_use_the_same_edge_weight_in_reverse(self):
        ego, peer, front, other = self.frame(10, 20)
        a = rules._following(ego, (peer, front, other), 2, 640)
        b = rules._following(peer, (ego, front, other), 2, 640)
        self.assertAlmostEqual(a[0] - 10, -.12 * 15 / 28.8)
        self.assertAlmostEqual(b[0] - 20, +.12 * 15 / 28.8)

    def test_cruise_response_and_existing_limits_are_unchanged(self):
        ego, peer, front, other = self.frame(28.8)
        self.assertAlmostEqual(rules._following(ego, (peer, front, other), 2, 640)[0], 28.68)
        ego, peer, front, other = self.frame(33.3)
        self.assertAlmostEqual(rules._following(ego, (peer, front, other), 2, 640)[0], 33.18)

    def test_zero_phase_error_keeps_actual_cth_equilibrium(self):
        for speed in (10, 28.8):
            with self.subTest(speed=speed):
                ego, peer, front, other = self.frame(speed, offset=15)
                self.assertAlmostEqual(rules._following(ego, (peer, front, other), 2, 640)[0], speed)

    def test_noa_and_final_physical_speed_cap_remain(self):
        ego, peer, front, other = self.frame(10)
        rows = (peer, front, other)
        command, _ = rules.decide(ego, rows, rules.Memory(), "noa")
        self.assertEqual(command.formation_state, 0)
        self.assertAlmostEqual(command.speed, 10)
        stopped = self.car(7, 706, 1, 0)
        command, _ = rules.decide(ego, (stopped, peer, other), rules.Memory(), "transform")
        self.assertLessEqual(command.speed, rules.safe_speed(ego, (stopped, peer, other)))


if __name__ == "__main__":
    unittest.main()
