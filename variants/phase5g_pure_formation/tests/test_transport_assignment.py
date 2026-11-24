"""Static, anonymous transport against an independent permutation oracle."""
import itertools
import math
import random
import unittest

from noa.transport import lane_bounds, solve_transport


def permutation_cost(vehicles, slots, assignment):
    crossings = [abs(lane - slots[j][0]) for (lane, _), j in zip(vehicles, assignment)]
    squared = sum((x - slots[j][1]) ** 2 for (_, x), j in zip(vehicles, assignment))
    return max(crossings), sum(crossings), squared


class LocalTransportTests(unittest.TestCase):
    def assert_agrees_with_permutations(self, vehicles, slots, ego):
        candidates = [(permutation_cost(vehicles, slots, p), p)
                      for p in itertools.permutations(range(len(vehicles)))]
        expected = min(cost for cost, _ in candidates)
        result = solve_transport(vehicles, slots, ego_index=ego)
        reported = result.max_crossings, result.total_crossings, result.squared_displacement
        self.assertEqual(reported, expected)
        self.assertEqual(permutation_cost(vehicles, slots, result.assignment), expected)
        self.assertEqual(lane_bounds([v[0] for v in vehicles], [s[0] for s in slots]), expected[:2])
        alternative = min((cost[2] for cost, p in candidates
                           if cost[:2] == expected[:2] and p[ego] != result.assignment[ego]),
                          default=math.inf)
        self.assertEqual(result.ego_gap, alternative - expected[2])

    def test_path_bounds_ties_and_ego_gap_against_permutations(self):
        rng = random.Random(1125)
        for n in range(1, 7):
            for _ in range(12):
                vehicles = [(rng.randrange(4), rng.randrange(-3, 4)) for _ in range(n)]
                slots = [(rng.randrange(4), rng.randrange(-3, 4)) for _ in range(n)]
                self.assert_agrees_with_permutations(vehicles, slots, rng.randrange(n))

    def test_one_crossing_condition_accounts_for_lane_relay(self):
        # Sorted pairing can pass flow along the lane path using different cars.
        self.assertEqual(lane_bounds([0, 1], [1, 2]), (1, 2))
        self.assertEqual(lane_bounds([0, 0], [1, 2]), (2, 3))

    def test_slot_tie_still_protects_the_final_lane(self):
        cars = [(0, -10), (0, 0), (1, -10)]
        slots = [(0, 10), (1, -10), (1, 0)]
        r = solve_transport(cars, slots, ego_index=0, action="target_lane")
        self.assertEqual((r.ego_gap, r.action_lane, r.action_gap), (0, 1, 200))
        dx = dy = .25
        bound = 2*len(cars)*(dx*20 + dy*10 + 2*dx*dy)
        self.assertLess(bound, r.action_gap)
        # Independently examine all 64 corners of simultaneous car/slot noise.
        for signs in itertools.product((-1,1), repeat=6):
            observed = [(lane, x+d*dx) for (lane,x),d in zip(cars,signs)]
            targets = [(lane, y+d*dy) for (lane,y),d in zip(slots,signs[3:])]
            costs = [(permutation_cost(observed,targets,p),p) for p in itertools.permutations(range(3))]
            best = min(c for c,_ in costs)
            self.assertEqual({targets[p[0]][0] for c,p in costs if c == best}, {1})

    def test_different_final_lanes_can_require_the_same_next_lane(self):
        cars = [(0, 10), (0, 10)]
        slots = [(1, 0), (2, 20)]
        final = solve_transport(cars, slots, ego_index=0, action="target_lane")
        step = solve_transport(cars, slots, ego_index=0, action="next_lane")
        self.assertEqual((final.ego_gap, final.action_gap), (0, 0))
        self.assertEqual((step.ego_gap, step.action_lane, step.action_gap), (0, 1, math.inf))

    def test_equally_good_opposite_directions_are_ambiguous(self):
        r = solve_transport([(1, 0), (1, 0)], [(0, -10), (2, 10)], ego_index=0, action="next_lane")
        self.assertEqual(r.action_gap, 0)

    def test_optional_action_requires_valid_mode_and_ego(self):
        one = [(0, 0)]
        self.assertIsNone(solve_transport(one, one, ego_index=0).action_gap)
        with self.assertRaises(ValueError):
            solve_transport(one, one, action="next_lane")
        with self.assertRaises(ValueError):
            solve_transport(one, one, ego_index=0, action="unknown")

    def test_box_action_margin_can_rescue_a_move_and_detect_its_exact_tie(self):
        cars = [(0,0),(0,10),(3,100)]
        slots = [(1,0),(0,10),(3,100)]
        for eps,lower in ((.5,180.),(5.,0.),(6.,-40.)):
            r = solve_transport(cars,slots,ego_index=0,action="next_lane",position_error=eps)
            self.assertEqual((r.action_lane,r.action_gap,r.action_lower_bound),(1,200.,lower))
        nominal = solve_transport(cars,slots,ego_index=0,action="next_lane")
        self.assertIsNone(nominal.action_lower_bound)

    def test_box_action_uses_coarse_or_forced_certificate_when_available(self):
        cars = [(0,0),(0,10),(3,100)]
        slots = [(1,0),(0,10),(3,100)]
        r = solve_transport(cars,slots,ego_index=0,action="next_lane",position_error=.125)
        self.assertEqual(r.action_lower_bound,125.)
        forced = solve_transport(cars,cars,ego_index=0,action="next_lane",position_error=.5)
        self.assertEqual(forced.action_lower_bound,math.inf)
        for eps in (-1,math.nan,math.inf):
            with self.assertRaises(ValueError):
                solve_transport(cars,slots,ego_index=0,action="next_lane",position_error=eps)

    def test_equal_diagonal_cost_and_fixed_lane_infeasibility(self):
        cars = [(1, 25), (1, 5), (0, 25)]
        slots = [(2, 15), (0, 15), (0, 40)]
        self.assertEqual(solve_transport(cars, slots, ego_index=0).ego_gap, 0)
        # Others can exchange equal-x slots while the ego retains its unique lane.
        self.assertEqual(solve_transport([(0, 0), (1, 10), (1, 10)],
                                    [(0, 0), (1, 5), (1, 15)], ego_index=0).ego_gap, math.inf)

    def test_anonymous_geometry_is_equivariant_under_permutation_and_translation(self):
        cars = [(2, 20), (0, 10), (1, -10), (0, -20)]
        slots = [(0, 25), (1, 12), (0, -15), (2, -18)]
        original = solve_transport(cars, slots)
        self.assertIsNone(original.ego_gap)
        shifted = lambda rows: [(lane, x + 10**7) for lane, x in reversed(rows)]
        other = solve_transport(shifted(cars), shifted(slots))
        self.assertEqual(original.assignment, tuple(3 - s for s in reversed(other.assignment)))
        self.assertEqual(original.squared_displacement, other.squared_displacement)

    def test_strict_gap_dominates_bounded_position_noise(self):
        cars = [(0, 2), (0, 11), (0, 20)]
        slots = [(0, 0), (0, 10), (0, 20)]
        result = solve_transport(cars, slots, ego_index=1)
        eps = 0.5
        self.assertGreater(result.ego_gap, 2 * len(cars) * eps * 20)
        for signs in itertools.product((-eps, eps), repeat=len(cars)):
            perturbed = [(lane, x + d) for (lane, x), d in zip(cars, signs)]
            self.assertEqual(solve_transport(perturbed, slots).assignment[1], result.assignment[1])

    def test_changing_the_lane_phase_can_change_the_preferred_vehicle(self):
        cars = [(0, 10), (0, 0)]
        for slots, target in (([(0, 10), (1, 0)], 0), ([(0, 0), (1, 10)], 1)):
            self.assertEqual(solve_transport(cars, slots).assignment[0], target)

    def test_resolves_representable_longitudinal_differences_close_to_a_tie(self):
        delta = 2.**-33
        cars = [(1, 100.), (1, 100. + delta), (0, 0.), (1, 100.)]
        slots = [(1, 100. + delta), (0, 0.), (0, 100.), (0, 100. + delta)]
        result = solve_transport(cars, slots, ego_index=1)
        self.assertEqual(result.squared_displacement, delta**2)
        self.assertEqual(result.ego_gap, 0.)  # distinct equidistant diagonal slots

    def test_invalid_bijections_are_rejected(self):
        for cars, slots in (([], []), ([(0, 0)], []), ([(0, math.nan)], [(0, 0)])):
            with self.assertRaises(ValueError):
                solve_transport(cars, slots)
        with self.assertRaises(IndexError):
            solve_transport([(0, 0)], [(0, 0)], ego_index=-1)


if __name__ == "__main__":
    unittest.main()
