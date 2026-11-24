"""Local geometric references and assignment confidence at road changes."""
import unittest
from dataclasses import replace

from noa import native_rules as rules
from noa.staggered import choose_target


def car(x, lane, track=0):
    return rules.Vehicle(track, x, (lane + .5) * rules.LANE_WIDTH, 28.8, lane)


class TransportControlTests(unittest.TestCase):
    def test_local_projection_restores_a_fixed_six_car_shape_after_small_perturbations(self):
        d = rules.desired_spacing(rules.CRUISE)
        offsets = [d * (row + .5 * (lane % 2)) for row in range(2) for lane in range(3)]
        cars = [replace(car(240 - off + .1 * (i-2), i % 3, i), speed=28.6 + .05 * i)
                for i, off in enumerate(offsets)]
        for step in range(100):
            commands = [rules.decide(c, [p for p in cars if p is not c], rules.Memory(),
                                     "transform", None, lane_count=3, downstream=True)[0] for c in cars]
            self.assertTrue(all(cmd.lane is None for cmd in commands))
            cars = [replace(c, speed=cmd.speed, x=c.x + rules.CONTROL_STEP * cmd.speed)
                    for c, cmd in zip(cars, commands)]
        origins = [c.x + off for c, off in zip(cars, offsets)]
        self.assertLess(max(origins) - min(origins), .001)
        self.assertTrue(all(abs(c.speed - rules.CRUISE) < .001 for c in cars))

    def test_cropping_a_long_regular_platoon_preserves_each_ego_equilibrium(self):
        d = rules.desired_spacing(rules.CRUISE)
        for lanes in (2, 3, 4):
            group = [car(900 - d * (row + .5 * (lane % 2)), lane, lanes * row + lane)
                     for row in range(22) for lane in range(lanes)]
            for ego in group:
                others = [other for other in group if other is not ego]
                cmd, _ = rules.decide(ego, others, rules.Memory(), "transform", None, lane_count=lanes)
                with self.subTest(lanes=lanes, track=ego.track):
                    self.assertIn(cmd.proposal_lane, (None, ego.lane))
                    self.assertAlmostEqual(cmd.speed, rules.CRUISE)

    def test_visible_half_layer_and_real_incomplete_tail_can_share_a_lane(self):
        d = rules.desired_spacing(rules.CRUISE)
        for lanes in (2, 4):
            group = [car(900 - d * (row + .5 * (lane % 2)), lane, lanes * row + lane)
                     for row in range(18) for lane in range(lanes)]
            group.append(car(900 - 18.5 * d, 1, 18 * lanes))
            for ego in group:
                cmd, _ = rules.decide(ego, [c for c in group if c is not ego], rules.Memory(),
                                      "transform", None, lane_count=lanes)
                self.assertEqual(cmd.proposal_lane, ego.lane)
                self.assertAlmostEqual(cmd.target_x, ego.x)

    def test_one_sensor_edge_companion_can_disappear_from_a_regular_band(self):
        from math import nextafter, inf
        group = [car(800 - 20 * (row + .5 * (lane % 2)), lane, 4 * row + lane)
                 for row in range(40) for lane in range(4)]
        ego = next(c for c in group if c.x == 480 and c.lane == 2)
        group = [replace(c, x=nextafter(c.x, inf)) if c.x == 680 and c.lane == 2 else c
                 for c in group]
        visible = sorted((c for c in group if -100 <= c.x - ego.x <= 200),
                         key=lambda c: (-c.x, -c.lane))
        target = choose_target(visible.index(ego), visible, 4, 20, head_clipped=True, tail_clipped=True,
                               sensor_bounds=(ego.x - 100, ego.x + 200))
        self.assertEqual(target.lane, ego.lane)
        self.assertAlmostEqual(target.x, ego.x)

    def test_incomplete_four_lane_layer_can_keep_an_occupied_adjacent_slot(self):
        cars = [car(50, 0), car(34, 1, 1)]
        self.assertEqual([choose_target(i, cars, 4, 30).lane for i in (0, 1)], [0, 1])

    def test_three_lane_tail_fills_outer_slots_first(self):
        cars = [car(50, 0), car(34, 1, 1)]
        self.assertEqual(sorted(choose_target(i, cars, 3, 30).lane for i in (0, 1)), [0, 2])

    def test_upstream_car_observes_a_consistent_move_before_crossing(self):
        cars = [car(100, 0), car(85, 1, 1)]
        def observed(t, memory):
            return rules.decide(replace(cars[1], time=t), [cars[0]], memory,
                                "transform", None, lane_count=3)
        first, memory = observed(0., rules.Memory())
        self.assertEqual(first.proposal_lane, 2)
        self.assertIsNone(first.lane)
        later, _ = observed(1.0, memory)
        self.assertEqual(later.lane, 2)

    def test_layer_geometry_balances_all_supported_widths(self):
        cars = [car(120 - i * 8, 0, i) for i in range(12)]
        for lanes in (2, 3, 4):
            choices = [choose_target(i, cars, lanes, 30) for i in range(12)]
            for lane in range(lanes):
                positions = sorted(t.x for t in choices if t.lane == lane)
                self.assertEqual(len(positions), 12 // lanes)
                for a, b in zip(positions, positions[1:]):
                    self.assertAlmostEqual(b - a, 30)

    def test_role_does_not_depend_on_physical_identity(self):
        cars = [car(100, 0, 1), car(89, 1, 2), car(80, 2, 3)]
        before = choose_target(2, cars, 2, 30)
        after = choose_target(2, [replace(c, track=10-c.track, x=c.x+900) for c in cars], 2, 30)
        self.assertEqual(before.lane, after.lane)
        self.assertAlmostEqual(before.x + 900, after.x)
        self.assertEqual(before.certified, after.certified)

    def test_car_cannot_request_unopened_expansion_lane(self):
        cars = [car(944, 1, 1), car(925, 1, 2), car(907, 1, 3)]
        for ego in cars:
            cmd, _ = rules.decide(ego, [c for c in cars if c is not ego], rules.Memory(),
                                  "transform", None, lane_count=2, upcoming_lanes=3)
            self.assertIn(cmd.lane, (None, 0, 1))
