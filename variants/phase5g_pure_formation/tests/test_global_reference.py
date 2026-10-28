"""Cai-style reference contract; run from the isolated phase5g variant."""

from dataclasses import replace
import importlib.util
import unittest


class GlobalReferenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("experiments.global_reference"),
            "Cai-style centralized target reference is missing",
        )
        from experiments.global_reference import GlobalPlanner
        from noa.native_rules import Vehicle

        self.planner, self.Vehicle = GlobalPlanner(), Vehicle

    def car(self, track, x, lane, speed=28.8, **kwargs):
        return self.Vehicle(track, x, (lane + 0.5) * 3.3, speed, lane, **kwargs)

    def six(self, front=300.0):
        return {
            str(i): self.car(i, front - offset, lane)
            for i, (offset, lane) in enumerate(
                ((0.0, 2), (30.0, 2), (15.0, 1), (45.0, 1), (0.0, 0), (30.0, 0))
            )
        }

    def test_empty_input_has_no_commands_or_assignments(self):
        self.assertEqual(self.planner.commands({}, 0.0), {})
        self.assertEqual(self.planner.assignments, {})

    def test_three_lane_six_targets_have_same_lane_30_and_cross_lane_15(self):
        commands = self.planner.commands(self.six(), 0.0, None)
        slots = set(self.planner.assignments.values())
        self.assertEqual(slots, {(300.0, 2), (300.0, 0), (285.0, 1), (270.0, 2), (270.0, 0), (255.0, 1)})
        self.assertEqual(len(commands), 6)
        self.assertTrue(all(c.speed == 28.8 for c in commands.values()))

    def test_incomplete_layer_fills_front_slots_before_rear_slots(self):
        states = {str(i): self.car(i, 300.0 - i * 4.0, i % 3) for i in range(5)}
        self.planner.commands(states, 0.0, None)
        self.assertEqual(
            set(self.planner.assignments.values()),
            {(300.0, 2), (300.0, 0), (285.0, 1), (270.0, 2), (270.0, 0)},
        )

    def test_six_cars_switch_from_three_lanes_two_layers_to_two_lanes_three(self):
        self.planner.commands(self.six(700.0), 0.0)
        self.assertEqual(
            set(self.planner.assignments.values()),
            {(700.0, 1), (685.0, 0), (670.0, 1), (655.0, 0), (640.0, 1), (625.0, 0)},
        )

    def test_preparation_starts_at_640_and_none_keeps_three_lanes(self):
        for front, drop, lanes in (
            (639.9, 1000.0, 3),
            (640.0, 1000.0, 2),
            (1001.0, 1000.0, 2),
            (700.0, None, 3),
        ):
            with self.subTest(front=front, drop=drop):
                self.planner = type(self.planner)()
                self.planner.commands(self.six(front), 0.0, drop)
                self.assertEqual({lane for _, lane in self.planner.assignments.values()}, set(range(lanes)))

    def test_one_to_one_assignment_preserves_source_lane_front_to_rear_order(self):
        states = {str(i): self.car(i, 700.0 - i * 5.0, 2) for i in range(8)}
        self.planner.commands(states, 0.0)
        slots = list(self.planner.assignments.values())
        self.assertEqual(len(set(slots)), len(states))
        self.assertEqual(
            [self.planner.assignments[str(i)][0] for i in range(8)],
            sorted((x for x, _ in slots), reverse=True),
        )

    def test_physical_order_makes_results_independent_of_ids_and_input_order(self):
        states = self.six(700.0)
        expected = self.planner.commands(states, 0.0)
        other = type(self.planner)()
        renamed = {f"new{k}": replace(v, track=100 - int(k)) for k, v in reversed(list(states.items()))}
        actual = other.commands(renamed, 0.0)
        self.assertEqual(
            [(expected[k].speed, expected[k].lane, expected[k].target_x) for k in states],
            [(actual[f"new{k}"].speed, actual[f"new{k}"].lane, actual[f"new{k}"].target_x) for k in states],
        )

    def test_plan_is_fixed_for_five_seconds_and_targets_move_at_cruise(self):
        states = self.six()
        first = self.planner.commands(states, 10.0, None)
        assignments = self.planner.assignments.copy()
        moved = {k: replace(v, x=v.x + 28.8 * 0.1) for k, v in states.items()}
        second = self.planner.commands(moved, 10.1, None)
        self.assertEqual(self.planner.assignments, assignments)
        self.assertEqual(self.planner.planned_at, 10.0)
        for key in states:
            self.assertAlmostEqual(second[key].target_x - first[key].target_x, 2.88)
            self.assertAlmostEqual(second[key].speed, 28.8)
        self.planner.commands(moved, 15.0, None)
        self.assertEqual(self.planner.planned_at, 15.0)

    def test_new_arrival_cruises_until_next_structural_plan(self):
        states = {"a": self.car(0, 300.0, 2)}
        self.planner.commands(states, 0.0, None)
        states["b"] = self.car(1, 280.0, 1)
        command = self.planner.commands(states, 0.1, None)["b"]
        self.assertEqual(command.speed, 28.8)
        self.assertIsNone(command.target_x)
        self.planner.commands(states, 5.0, None)
        self.assertIn("b", self.planner.assignments)

    def test_groups_split_only_above_50m_longitudinal_neighbour_distance(self):
        states = {"a": self.car(0, 300.0, 2), "b": self.car(1, 250.0, 1), "c": self.car(2, 199.9, 0)}
        self.planner.commands(states, 0.0, None)
        self.assertEqual(self.planner.groups, (("a", "b"), ("c",)))

    def test_speed_is_capped_and_each_lane_request_is_one_adjacent_step(self):
        states = self.six(700.0)
        self.planner.commands(states, 0.0)
        behind = {k: replace(v, x=v.x - 200.0) for k, v in states.items()}
        commands = self.planner.commands(behind, 0.1)
        self.assertTrue(any(c.speed == 33.3 for c in commands.values()))
        for key, command in commands.items():
            self.assertTrue(0.0 <= command.speed <= 33.3)
            if command.lane is not None:
                self.assertLessEqual(abs(command.lane - states[key].lane), 1)

    def test_lane_request_requires_current_and_one_second_8m_clearance(self):
        for blocker_x, blocker_speed in ((706.0, 28.8), (710.0, 18.8)):
            with self.subTest(blocker_x=blocker_x):
                self.planner = type(self.planner)()
                states = {"ego": self.car(0, 700.0, 2), "block": self.car(1, blocker_x, 1, blocker_speed)}
                command = self.planner.commands(states, 0.0)["ego"]
                self.assertIsNone(command.lane)

    def test_private_track_labels_do_not_bypass_central_clearance(self):
        states = {"ego": self.car(0, 700.0, 2), "block": self.car(0, 706.0, 1)}
        self.assertIsNone(self.planner.commands(states, 0.0)["ego"].lane)

    def test_departures_are_pruned_without_restarting_the_structural_clock(self):
        states = self.six()
        self.planner.commands(states, 0.0, None)
        del states["0"]
        self.planner.commands(states, 0.1, None)
        self.assertNotIn("0", self.planner.assignments)
        self.assertEqual(self.planner.planned_at, 0.0)
        self.planner.commands({}, 0.2)
        self.assertEqual(self.planner.groups, ())
        self.assertIsNone(self.planner.planned_at)

    def test_started_adjacent_change_is_held_until_lateral_completion(self):
        ego = self.car(0, 700.0, 2)
        self.assertEqual(self.planner.commands({"ego": ego}, 0.0)["ego"].lane, 1)
        moving = replace(ego, lane=1, y=6.0, vy=-1.0)
        command = self.planner.commands({"ego": moving}, 0.5)["ego"]
        self.assertEqual((command.lane, command.reason), (1, "global_executing"))
        arrived = replace(moving, y=4.95, vy=0.0)
        self.assertIsNone(self.planner.commands({"ego": arrived}, 1.0)["ego"].lane)


if __name__ == "__main__":
    unittest.main()
