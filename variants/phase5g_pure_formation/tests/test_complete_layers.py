"""Hand-built physical counterexamples for the complete-layer evaluator."""

import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def formation(lanes=3, layers=2, front=300.0, speed=5.0, spacing=30.0):
    return {
        f"v{lane}_{row}": [
            front - spacing * row - 15.0 * ((lanes - 1 - lane) % 2),
            (lane + 0.5) * 3.3,
            speed,
            0.0,
        ]
        for row in range(layers)
        for lane in range(lanes)
    }


class CompleteLayersTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("experiments.complete_layers"),
            "Independent complete-layer evaluator is missing",
        )
        from experiments.complete_layers import evaluate_layers, groups_at

        self.groups = groups_at
        self.evaluate = evaluate_layers
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "positions.jsonl.gz"

    def run_frames(self, frames, lanes=3, **kwargs):
        with gzip.open(self.path, "wt", encoding="utf-8") as stream:
            for time_s, states in frames:
                stream.write(json.dumps(dict(time_s=time_s, states=states)) + "\n")
        return self.evaluate(self.path, lanes, **kwargs)

    def multilayer(self, states, lanes=3):
        return [g for g in self.groups(states, lanes) if g["layer_count"] >= 2]

    def test_parallel_two_cars_are_not_a_complete_layer(self):
        self.assertEqual(self.groups({"a": [100.0, 1.65, 5.0, 0.0], "b": [100.0, 8.25, 5.0, 0.0]}, 3), [])

    def test_three_lane_two_layer_and_two_lane_three_layer_are_six_cars(self):
        for lanes, layers in ((3, 2), (2, 3), (4, 2)):
            with self.subTest(lanes=lanes):
                groups = self.multilayer(formation(lanes, layers), lanes)
                self.assertEqual(len(groups), 1)
                self.assertEqual(groups[0]["size"], lanes * layers)
                self.assertEqual(groups[0]["layer_count"], layers)
                self.assertAlmostEqual(groups[0]["geometry_rms_m"], 0.0)

    def test_single_layer_is_separate_from_main_scale(self):
        states = formation(layers=1)
        self.assertEqual(self.groups(states, 3)[0]["layer_count"], 1)
        result = self.run_frames([(0.0, states), (3.0, states)])
        self.assertEqual(result["raw_single_layer_vehicle_seconds"], 9.0)
        self.assertEqual(result["formed_vehicle_seconds"], 0.0)
        self.assertIsNone(result["mean_multilayer_size"])

    def test_sixty_meter_missing_layer_does_not_connect(self):
        groups = self.groups(formation(spacing=60.0), 3)
        self.assertEqual([g["layer_count"] for g in groups], [1, 1])

    def test_missing_middle_lane_cannot_be_hidden(self):
        states = formation(layers=3)
        del states["v1_1"]
        self.assertEqual(self.multilayer(states), [])

    def test_extra_internal_vehicle_and_crossing_vehicle_cannot_be_hidden(self):
        for y in (1.65, 6.6):
            states = formation()
            states["extra"] = [280.0, y, 5.0, 0.0]
            self.assertEqual(self.multilayer(states), [])

    def test_complete_prefix_does_not_wait_for_unformed_tail(self):
        states = formation()
        states.update(tail0=[249.0, 1.65, 4.0, 0.0], tail1=[235.0, 4.95, 6.0, 0.0])
        groups = self.multilayer(states)
        self.assertEqual([g["size"] for g in groups], [6])

    def test_components_never_overlap(self):
        states = formation(layers=4)
        states["extra"] = [250.0, 6.6, 5.0, 0.0]
        groups = self.groups(states, 3)
        ids = [vehicle for group in groups for vehicle in group["vehicle_ids"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([g["size"] for g in groups if g["layer_count"] >= 2], [6, 6])

    def test_position_speed_and_center_tolerances(self):
        for key, index, delta in (("v0_0", 0, 2.01), ("v0_0", 1, 0.301), ("v0_0", 2, 0.501)):
            states = formation()
            states[key][index] += delta
            self.assertEqual(self.multilayer(states), [])
        states = formation()
        states["v0_0"][0] += 1.0
        states["v0_0"][2] += 0.4
        group = self.multilayer(states)[0]
        self.assertGreater(group["geometry_rms_m"], 0.0)
        self.assertGreater(group["speed_rms_mps"], 0.0)

    def test_irregular_time_weights_and_one_second_confirmation(self):
        states = formation(speed=0.0)
        result = self.run_frames([(t, states) for t in (0.0, 0.5, 1.0, 3.5)])
        self.assertAlmostEqual(result["observation_seconds"], 3.5)
        self.assertAlmostEqual(result["vehicle_seconds"], 21.0)
        self.assertAlmostEqual(result["formed_vehicle_seconds"], 15.0)
        self.assertAlmostEqual(result["formation_participation_rate"], 15.0 / 21.0)
        self.assertAlmostEqual(result["mean_multilayer_size"], 6.0)
        self.assertEqual(result["peak_multilayer_size"], 6)

    def test_threshold_is_integrated_inside_long_sampling_interval(self):
        states = formation(speed=0.0)
        result = self.run_frames([(0.0, states), (7.0, states)])
        self.assertAlmostEqual(result["formed_vehicle_seconds"], 36.0)
        self.assertAlmostEqual(result["stable_vehicle_seconds"], 12.0)
        self.assertEqual(result["internal_relation_breaks"], 0)
        self.assertGreater(result["end_censored_relations"], 0)

    def test_new_tail_does_not_reset_formed_prefix(self):
        short, long = formation(speed=0.0), formation(layers=3, speed=0.0)
        result = self.run_frames([(0.0, short), (1.0, short), (2.0, long), (3.0, long)])
        self.assertAlmostEqual(result["formed_vehicle_seconds"], 12.0)
        self.assertEqual(result["internal_relation_breaks"], 0)

    def test_all_region_vehicles_remain_in_participation_denominator(self):
        states = formation(speed=0.0)
        states["tail"] = [200.0, 6.6, 0.0, 0.0]
        result = self.run_frames([(0.0, states), (3.0, states)])
        self.assertEqual(result["vehicle_seconds"], 21.0)
        self.assertEqual(result["formed_vehicle_seconds"], 12.0)

    def test_actual_boundary_exit_is_censored_not_internal_break(self):
        frames = [(t, formation(front=50.0 + 10.0 * t, speed=10.0)) for t in range(5)]
        result = self.run_frames(frames, region=(0.0, 80.0))
        self.assertEqual(result["internal_relation_breaks"], 0)
        self.assertGreater(result["boundary_censored_relations"], 0)

    def test_missing_vehicle_predicted_to_cross_boundary_is_censored(self):
        states = formation(front=70.0, speed=10.0)
        last = formation(front=80.0, speed=10.0)
        del last["v2_0"]
        del last["v0_0"]
        result = self.run_frames([(0.0, states), (1.0, states), (2.0, last)], region=(0.0, 80.0))
        self.assertEqual(result["internal_relation_breaks"], 0)
        self.assertGreater(result["boundary_censored_relations"], 0)

    def test_internal_physical_break_is_reported(self):
        states = formation(speed=0.0)
        broken = formation(speed=0.0)
        broken["v1_0"][1] = 6.6
        result = self.run_frames([(0.0, states), (2.0, states), (3.0, broken)])
        self.assertGreater(result["internal_relation_breaks"], 0)
        self.assertEqual(result["boundary_censored_relations"], 0)

    def test_unconfirmed_reappearance_does_not_count_a_second_break(self):
        states = formation(speed=0.0)
        broken = formation(speed=0.0)
        broken["v1_0"][1] = 6.6
        first = self.run_frames([(0.0, states), (2.0, states), (3.0, broken)])
        twice = self.run_frames([(0.0, states), (2.0, states), (3.0, broken), (4.0, states), (4.5, broken)])
        self.assertEqual(twice["internal_relation_breaks"], first["internal_relation_breaks"])

    def test_phase_tolerance_applies_between_all_lanes(self):
        states = formation()
        states["v0_0"][0] += 2.0
        states["v1_0"][0] -= 2.0
        self.assertEqual(self.multilayer(states), [])

    def test_largest_closed_block_is_selected_before_forward_pairs(self):
        states = formation(layers=4)
        for row, speed in enumerate((28.8, 29.2, 29.6, 29.6)):
            for lane in range(3):
                states[f"v{lane}_{row}"][2] = speed
        groups = self.groups(states, 3)
        self.assertEqual([g["size"] for g in groups], [3, 9])
        self.assertEqual(groups[1]["layers"][0][0], "v2_1")
        ids = [v for group in groups for v in group["vehicle_ids"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 12)
        frames = [(t / 10, {v: [s[0] + s[2] * t / 10, *s[1:]] for v, s in states.items()}) for t in range(21)]
        result = self.run_frames(frames)
        self.assertEqual(result["peak_multilayer_size"], 9)
        self.assertAlmostEqual(result["mean_multilayer_size"], 9.0)
        self.assertAlmostEqual(result["formed_vehicle_seconds"], 9.0)
        self.assertAlmostEqual(result["vehicle_seconds"], 24.0)
        self.assertAlmostEqual(result["raw_single_layer_vehicle_seconds"], 6.0)
        self.assertAlmostEqual(result["formation_participation_rate"], 9.0 / 24.0)

    def test_equal_largest_blocks_choose_the_front_block(self):
        states = formation(layers=3)
        for row, speed in enumerate((28.8, 29.2, 29.6)):
            for lane in range(3):
                states[f"v{lane}_{row}"][2] = speed
        groups = self.groups(states, 3)
        self.assertEqual([g["size"] for g in groups], [6, 3])
        self.assertEqual(groups[0]["layers"][0][0], "v2_0")

    def test_smaller_unoccupied_blocks_are_selected_after_the_largest(self):
        states = formation(layers=6)
        for row, speed in enumerate((28.8, 29.2, 29.6, 29.6, 30.0, 30.4)):
            for lane in range(3):
                states[f"v{lane}_{row}"][2] = speed
        self.assertEqual([g["size"] for g in self.groups(states, 3)], [3, 9, 6])

    def test_one_second_sampling_can_alias_between_sample_breaks(self):
        states = formation(speed=0.0)
        broken = formation(speed=0.0)
        broken["v1_0"][1] = 6.6
        fine = [(t / 10, broken if t % 10 == 5 else states) for t in range(31)]
        sampled = [(t, states) for t in range(4)]
        self.assertEqual(self.run_frames(fine)["formed_vehicle_seconds"], 0.0)
        self.assertGreater(self.run_frames(sampled)["formed_vehicle_seconds"], 0.0)

    def test_regions_do_not_compare_three_to_two_lane_relations(self):
        states = formation(front=1100.0, speed=0.0)
        result = self.run_frames([(0.0, states), (2.0, states)], region=(0.0, 640.0))
        self.assertEqual(result["vehicle_seconds"], 0.0)
        self.assertIsNone(result["formation_participation_rate"])

    def test_empty_file_and_invalid_time_are_explicit(self):
        result = self.run_frames([])
        self.assertIsNone(result["mean_multilayer_size"])
        self.assertIsNone(result["formation_participation_rate"])
        with self.assertRaises(ValueError):
            self.run_frames([(1.0, {}), (1.0, {})])


if __name__ == "__main__":
    unittest.main()
