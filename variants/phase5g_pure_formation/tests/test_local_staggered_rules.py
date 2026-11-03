"""Physical regression examples for local staggered following and CTH priority."""
from dataclasses import replace
import unittest

from noa import native_rules as r


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


class LocalStaggeredRulesTests(unittest.TestCase):
    def test_adjacent_real_vehicle_bridges_one_missing_cell(self):
        ego, front, witness = car(0, 100, 1), car(1, 160, 1), car(2, 145, 0)
        self.assertIsNone(r._front_following(ego, (front, witness))[2])
        speed, target, reference, state = r._following(ego, (front, witness), 2)
        self.assertEqual(reference, front.track)
        self.assertAlmostEqual(target, 130.)
        self.assertAlmostEqual(speed, 30.6)
        self.assertEqual(state, 1)

    def test_same_lane_count_does_not_prove_an_adjacent_cell(self):
        ego = car(0, 100, 1)
        rows = (car(1, 158, 1), car(2, 188, 1), car(3, 218, 1))
        self.assertIsNone(r._following(ego, rows, 2)[2])

    def test_misaligned_or_distant_front_does_not_create_a_bridge(self):
        ego = car(0, 100, 1)
        for front_x, witness_x in ((160., 150.), (161., 146.)):
            with self.subTest(front_x=front_x, witness_x=witness_x):
                rows = (car(1, front_x, 1), car(2, witness_x, 0))
                self.assertIsNone(r._following(ego, rows, 2)[2])

    def test_phase_cannot_reverse_the_actual_fronts_speed_correction(self):
        for lane, front_x, peer_x in ((1, 124., 125.5), (0, 136., 75.)):
            ego = car(0, 100, lane)
            rows = (car(1, front_x, lane), car(2, peer_x, 1 - lane))
            with self.subTest(lane=lane):
                actual = r._following(ego, rows, 2)
                expected = r._front_following(ego, rows)
                self.assertEqual(actual, expected)

    def test_compatible_phase_acceleration_is_preserved(self):
        ego = car(0, 100, 0)
        rows = (car(1, 136, 0), car(2, 95, 1))
        actual = r._following(ego, rows, 2)
        self.assertAlmostEqual(actual[0], 29.56)
        self.assertEqual(actual[1:3], r._front_following(ego, rows)[1:3])

    def test_parallel_bodies_act_on_the_real_cross_lane_pair(self):
        cars = (car(0, 100, 0), car(1, 130, 0), car(2, 100, 1), car(3, 130, 1))
        for index, speed in ((0, 29.2), (2, 28.4)):
            ego = cars[index]
            rows = tuple(c for c in cars if c.track != ego.track)
            with self.subTest(lane=ego.lane):
                self.assertAlmostEqual(r._following(ego, rows, 3)[0], speed)

    def test_track_labels_and_observation_order_do_not_choose_the_reference(self):
        ego, front, witness = car(0, 100, 1), car(1, 160, 1), car(2, 145, 0)
        expected = r._following(ego, (front, witness), 2)
        relabel = lambda c: replace(c, track=9001 - 17 * c.track)
        actual = r._following(relabel(ego), (car(7777, 1000, 2), relabel(witness), relabel(front)), 2)
        self.assertEqual((actual[0], actual[1], actual[3]), (expected[0], expected[1], expected[3]))
        self.assertEqual(actual[2], relabel(front).track)

    def test_noa_always_reports_zero_and_uses_the_shared_safe_cap(self):
        ego, front = car(0, 100, 0, 33.3), car(1, 108, 0, 0.)
        command, _ = r.decide(ego, (front,), r.Memory(), 'noa', None)
        self.assertEqual(command.formation_state, 0)
        self.assertEqual(command.speed, min(r._front_following(ego, (front,))[0], r.safe_speed(ego, (front,))))


if __name__ == '__main__':
    unittest.main()
