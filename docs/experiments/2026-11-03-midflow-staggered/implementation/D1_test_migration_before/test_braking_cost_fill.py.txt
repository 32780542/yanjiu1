from dataclasses import replace
import unittest
from noa import native_rules as r


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + 0.5) * r.LANE_WIDTH, speed, lane)


class BrakingCostFillTests(unittest.TestCase):
    def useful_fill(self):
        return car(0, 285.0, 0), [car(1, 300.0, 2), car(2, 270.0, 2),
                                 car(3, 255.0, 1), car(4, 300.0, 0), car(5, 270.0, 0)]

    def test_equal_speed_useful_fill_is_still_accepted(self):
        ego, rows = self.useful_fill()
        self.assertEqual(r._fill(ego, rows, 3), 1)
        command, _ = r.decide(ego, rows, r.Memory(), "formation", None)
        self.assertEqual((command.lane, command.reason), (1, "fill_layer"))

    def test_target_follower_severe_braking_rejects_discretionary_fill(self):
        ego, rows = self.useful_fill()
        ego = replace(ego, speed=20.0)
        rows[2] = car(3, 265.0, 1, 31.0)
        # An extra old-lane follower obtains a large release benefit. It must
        # not compensate for the new follower's >10 m/s2 requested deceleration.
        rows.append(car(6, 275.0, 0, 31.0))
        self.assertTrue(r._clear(ego, rows, 1))
        self.assertIsNone(r._fill(ego, rows, 3))

    def test_a_lower_braking_alternative_wins_equal_formation_benefit(self):
        ego, rows = self.useful_fill()
        # Geometry ties favour lane 2 in the baseline. Both options meet the
        # 10 m/s2 follower bound, but lane 2 adds 0.76 m/s response loss.
        rows.append(car(6, 285.0, 2, 25.0))
        self.assertEqual(r._fill(ego, rows, 3), 1)

    def test_severe_follower_bound_cannot_be_offset_by_large_old_lane_release(self):
        helper = getattr(r, "cf_speed", None)
        self.assertTrue(callable(helper), "missing public same-frame CF estimator")
        ego, rows = self.useful_fill()
        ego = replace(ego, speed=20.0)
        rows[2] = car(3, 265.0, 1, 31.0)
        old_rear = car(6, 275.0, 0, 31.0)
        observed = [ego, *rows, old_rear]
        moved = replace(ego, lane=1, y=4.95)
        after = [moved, *rows, old_rear]
        affected = [ego, rows[2], old_rear]
        before_speeds = [helper(c, observed) for c in affected]
        after_speeds = [helper(moved if c is ego else c, after) for c in affected]
        # A signed aggregate gain would accept this move, but the target
        # follower would need much more braking than the physical 10 m/s2.
        self.assertGreater(sum(after_speeds) - sum(before_speeds), 0.0)
        self.assertLess(after_speeds[1], rows[2].speed - r.BRAKING * 0.1)
        self.assertIsNone(r._fill(ego, [*rows, old_rear], 3))

    def test_cost_ranking_alternative_is_below_separate_severe_braking_bound(self):
        helper = getattr(r, "cf_speed", None)
        self.assertTrue(callable(helper), "missing public same-frame CF estimator")
        ego, rows = self.useful_fill()
        alternative = car(6, 285.0, 2, 25.0)
        moved = replace(alternative, lane=1, y=4.95)
        new_rear = rows[2]
        after_speed = helper(new_rear, [ego, *rows, moved])
        self.assertGreaterEqual(after_speed, new_rear.speed - r.BRAKING * 0.1)
        self.assertAlmostEqual(new_rear.speed - after_speed, 0.76)
        self.assertEqual(r._fill(ego, [*rows, alternative], 3), 1)

    def test_mandatory_merge_remains_available_despite_severe_follower_cost(self):
        ego = car(0, 700.0, 2, 20.0)
        rows = [car(1, 680.0, 1, 31.0), car(2, 750.0, 1, 28.8)]
        for mode in ("formation", "transform", "noa"):
            with self.subTest(mode=mode):
                command, _ = r.decide(ego, rows, r.Memory(), mode, 1000.0)
                self.assertEqual((command.lane, command.reason), (1, "merge"))

    def test_complete_layers_are_not_dismantled(self):
        cars = [car(i, x, lane) for i, (x, lane) in enumerate(
            ((300.0, 2), (270.0, 2), (285.0, 1), (255.0, 1), (300.0, 0), (270.0, 0)))]
        for ego in cars:
            self.assertIsNone(r._fill(ego, [c for c in cars if c is not ego], 3))

    def test_track_renaming_and_observation_order_do_not_change_selection(self):
        ego, rows = self.useful_fill()
        rows.append(car(6, 285.0, 2, 25.0))
        expected = r._fill(ego, rows, 3)
        rows = [replace(c, track=130 - 7 * c.track) for c in reversed(rows)]
        self.assertEqual(r._fill(replace(ego, track=130), rows, 3), expected)

    def test_neighbor_private_actuation_fields_do_not_change_fill(self):
        ego, rows = self.useful_fill()
        rows.append(car(6, 285.0, 2, 25.0))
        expected = r._fill(ego, rows, 3)
        changed = [replace(c, acceleration=1000 - c.track, time=-400 + c.track,
                           pending_lane=(c.lane + 1) % 3) for c in rows]
        self.assertEqual(r._fill(ego, changed, 3), expected)
        self.assertNotIn("formation_state", r.Vehicle.__dataclass_fields__)

    def test_remote_cars_outside_ego_perception_do_not_change_decision(self):
        ego, rows = self.useful_fill()
        expected = r.decide(ego, rows, r.Memory(), "formation", None)
        actual = r.decide(ego, [*rows, car(90, ego.x - 100.01, 1, 0),
                               car(91, ego.x + 200.01, 1, 0)],
                          r.Memory(), "formation", None)
        self.assertEqual(actual, expected)

    def test_cf_model_uses_actual_same_lane_front_and_existing_public_limits(self):
        helper = getattr(r, "cf_speed", None)
        self.assertTrue(callable(helper), "missing public same-frame CF estimator")
        ego = car(0, 100.0, 0, 28.8)
        front = car(1, 120.0, 0, 26.0)
        expected = min(r._front_following(ego, [front])[0],
                       r.safe_speed(ego, [front]))
        self.assertAlmostEqual(helper(ego, [front]), expected)
        self.assertAlmostEqual(helper(ego, [car(2, 110.0, 1, 0.0)]), r.CRUISE)

    def test_cf_model_keeps_safety_for_front_outside_formation_chain(self):
        helper = getattr(r, "cf_speed", None)
        self.assertTrue(callable(helper), "missing public same-frame CF estimator")
        ego = car(0, 100.0, 0, 28.8)
        front = car(1, 151.0, 0, 0.0)
        self.assertAlmostEqual(helper(ego, [front]), r.safe_speed(ego, [front]))
        self.assertLess(helper(ego, [front]), r.CRUISE)
