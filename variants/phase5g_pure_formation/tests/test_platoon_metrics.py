"""Physical, time-weighted platoon measures for open-road position records."""
import gzip
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


class PlatoonMetricsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("experiments.platoon_metrics"),
            "The independent physical platoon metric evaluator is missing",
        )
        from experiments.platoon_metrics import evaluate_platoons
        self.evaluate = evaluate_platoons
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "positions.jsonl.gz"

    def run_frames(self, frames, lanes=3, gap=30., **kwargs):
        with gzip.open(self.path, "wt", encoding="utf-8") as stream:
            for time_s, states in frames:
                stream.write(json.dumps({"time_s": time_s, "states": states}) + "\n")
        return self.evaluate(self.path, lane_count=lanes, gap=gap, **kwargs)

    @staticmethod
    def perfect(time_s, gap=30., speed=5.):
        # Phase is 0, 15, 0 from the highest lane downwards.
        return {
            f"v{lane}{layer}": [300. - layer * gap - (15. if lane == 1 else 0.)
                                  + speed * time_s,
                                  (lane + .5) * 3.3, speed, 0.]
            for lane in range(3) for layer in range(2)
        }

    def test_perfect_three_lane_group_and_confirmed_stable_exposure(self):
        result = self.run_frames([(t, self.perfect(t)) for t in range(11)])
        self.assertAlmostEqual(result["mean_platoon_size"], 6.)
        self.assertEqual(result["max_platoon_size"], 6)
        self.assertAlmostEqual(result["participation_rate"], 1.)
        self.assertAlmostEqual(result["geometry_rms_m"], 0.)
        self.assertAlmostEqual(result["speed_rms_mps"], 0.)
        self.assertAlmostEqual(result["vehicle_seconds"], 60.)
        self.assertAlmostEqual(result["platoon_seconds"], 10.)
        self.assertAlmostEqual(result["stable_vehicle_seconds"], 30.)
        self.assertAlmostEqual(result["stable_participation_rate"], .5)
        self.assertEqual(result["internal_breaks"], 0)
        self.assertEqual(result["internal_breaks_per_100_platoon_vehicle_s"], 0.)

    def test_empty_file_and_empty_road_do_not_report_zero_quality(self):
        for frames in ([], [(0., {}), (1., {})]):
            with self.subTest(frames=frames):
                result = self.run_frames(frames)
                for field in ("mean_platoon_size", "max_platoon_size", "participation_rate",
                              "geometry_rms_m", "speed_rms_mps", "stable_participation_rate",
                              "internal_breaks_per_100_platoon_vehicle_s"):
                    self.assertIsNone(result[field], field)

    def test_single_vehicle_is_observed_but_never_a_platoon(self):
        result = self.run_frames([(t, {"only": [100.+t, 1.65, 1., 0.]})
                                  for t in range(8)])
        self.assertEqual(result["vehicle_seconds"], 7.)
        self.assertEqual(result["participation_rate"], 0.)
        self.assertEqual(result["stable_participation_rate"], 0.)
        self.assertIsNone(result["mean_platoon_size"])
        self.assertIsNone(result["geometry_rms_m"])

    def test_equal_speed_without_geometry_is_not_a_platoon(self):
        states = {"a": [100., 1.65, 5., 0.], "b": [110., 4.95, 5., 0.],
                  "c": [118., 8.25, 5., 0.]}
        result = self.run_frames([(0., states), (1., states)])
        self.assertEqual(result["platoon_vehicle_seconds"], 0.)
        self.assertEqual(result["participation_rate"], 0.)

    def test_diagonal_links_cannot_hide_missing_same_lane_layers(self):
        frames = []
        for t in (0.,1.):
            states = {f'{lane}_{row}':[(270. if lane==0 else 285. if lane==1 else 300.)
                -60*row+5*t,(lane+.5)*3.3,5.,0.]
                for lane in range(3) for row in range(3)}
            frames.append((t,states))
        result = self.run_frames(frames)
        self.assertEqual(result['max_platoon_size'],2)
        self.assertAlmostEqual(result['participation_rate'],6/9)

    def test_nearest_same_lane_pair_uses_center_distance(self):
        result = self.run_frames([(0., {"a": [100., 1.65, 5., 0.],
                                            "b": [130., 1.65, 5., 0.]}),
                                  (1., {"a": [105., 1.65, 5., 0.],
                                            "b": [135., 1.65, 5., 0.]})])
        self.assertEqual(result["mean_platoon_size"], 2.)
        self.assertEqual(result["participation_rate"], 1.)

    def test_normal_exit_and_recording_end_are_censored(self):
        frames = []
        for t in range(5):
            states = {"a": [1165.+10*t, 1.65, 10., 0.]}
            if t < 1:
                states["b"] = [1195., 1.65, 10., 0.]
            frames.append((float(t), states))
        result = self.run_frames(frames)
        self.assertEqual(result["internal_breaks"], 0)
        self.assertEqual(result["censored_edges"], 1)
        # A disappearance is not proof of an internal break, even without a trip table.
        states = {"a": [100., 1.65, 5., 0.], "b": [130., 1.65, 5., 0.]}
        result = self.run_frames([(0., states), (1., states)])
        self.assertEqual(result["censored_edges"], 1)

    def test_boundary_filter_and_new_entry_do_not_create_internal_breaks(self):
        result = self.run_frames([
            (0., {"a": [-1., 1.65, 5., 0.], "b": [29., 1.65, 5., 0.]}),
            (1., {"a": [4., 1.65, 5., 0.], "b": [34., 1.65, 5., 0.]}),
            (2., {"a": [9., 1.65, 5., 0.], "b": [39., 1.65, 5., 0.],
                  "outside": [1200., 4.95, 5., 0.]}),
        ])
        self.assertEqual(result["vehicle_seconds"], 3.)
        self.assertEqual(result["platoon_vehicle_seconds"], 2.)
        self.assertEqual(result["internal_breaks"], 0)

    def test_speed_disturbance_inside_road_is_an_internal_break(self):
        frames = []
        for t in range(8):
            states = {"a": [100.+5*t, 1.65, 5., 0.],
                      "b": [130.+5*t, 1.65, 5. if t < 6 else 6., 0.]}
            frames.append((float(t), states))
        result = self.run_frames(frames)
        self.assertEqual(result["internal_breaks"], 1)
        self.assertEqual(result["platoon_vehicle_seconds"], 12.)
        self.assertAlmostEqual(result["internal_breaks_per_100_platoon_vehicle_s"], 100./12.)
        self.assertAlmostEqual(result["stable_vehicle_seconds"], 2.)

    def test_position_disturbance_inside_road_is_an_internal_break(self):
        before = {"a": [100., 1.65, 5., 0.], "b": [130., 1.65, 5., 0.]}
        after = {"a": [105., 1.65, 5., 0.], "b": [145., 1.65, 5., 0.]}
        result = self.run_frames([(0., before), (1., after)])
        self.assertEqual(result["internal_breaks"], 1)

    def test_gap_and_lane_phase_offset_are_independent(self):
        for gap in (24., 36.):
            with self.subTest(gap=gap):
                result = self.run_frames([(t, self.perfect(t, gap=gap)) for t in range(7)], gap=gap)
                self.assertEqual(result["max_platoon_size"], 6)
                self.assertAlmostEqual(result["geometry_rms_m"], 0.)
                self.assertAlmostEqual(result["participation_rate"], 1.)

    def test_distant_periodic_points_cannot_join_by_modulo_only(self):
        states = {"a": [100., 1.65, 5., 0.], "b": [385., 4.95, 5., 0.]}
        result = self.run_frames([(0., states), (1., states)])
        self.assertEqual(result["platoon_vehicle_seconds"], 0.)

    def test_weights_use_timestamps_and_stability_can_start_between_frames(self):
        for step in (.5, 2.):
            with self.subTest(step=step):
                times = [i*step for i in range(round(10./step)+1)]
                result = self.run_frames([(t, self.perfect(t)) for t in times],
                                         max_sample_gap_s=max(1.01, step+.01))
                self.assertAlmostEqual(result["vehicle_seconds"], 60.)
                self.assertAlmostEqual(result["stable_vehicle_seconds"], 30.)
                self.assertAlmostEqual(result["stable_participation_rate"], .5)

    def test_missing_sampling_interval_is_not_a_five_second_hold(self):
        result = self.run_frames([(0., self.perfect(0.)), (8., self.perfect(8.))])
        self.assertEqual(result["sampling_gap_count"], 1)
        self.assertEqual(result["observed_duration_s"], 0.)
        self.assertIsNone(result["stable_participation_rate"])
        self.assertEqual(result["internal_breaks"], 0)

    def test_connected_candidates_never_double_count_endpoints(self):
        states = {"a": [100., 1.65, 5., 0.], "b": [130., 1.65, 5., 0.],
                  "c": [115., 4.95, 5., 0.], "d": [100., 8.25, 5., 0.]}
        result = self.run_frames([(0., states), (1., states)])
        self.assertEqual(result["max_platoon_size"], 4)
        self.assertLessEqual(result["platoon_vehicle_seconds"], result["vehicle_seconds"])
        self.assertLessEqual(result["stable_vehicle_seconds"], result["vehicle_seconds"])

    def test_lane_changing_vehicle_stays_in_exposure_but_not_in_graph(self):
        states = {"a": [100., 1.65, 5., 0.], "b": [130., 2.5, 5., 0.]}
        result = self.run_frames([(0., states), (1., states)])
        self.assertEqual(result["vehicle_seconds"], 2.)
        self.assertEqual(result["participation_rate"], 0.)

    def test_nonzero_geometric_and_velocity_errors_are_physical(self):
        states = {"a": [100., 1.65, 5., 0.], "b": [131., 1.65, 5.4, 0.]}
        result = self.run_frames([(0., states), (1., states)])
        self.assertAlmostEqual(result["geometry_rms_m"], 1.)
        self.assertAlmostEqual(result["speed_rms_mps"], .2)

    def test_platoon_mean_is_weighted_by_platoon_seconds(self):
        two_groups = {"a": [100., 1.65, 5., 0.], "b": [130., 1.65, 5., 0.],
                      "c": [600., 1.65, 5., 0.], "d": [630., 1.65, 5., 0.],
                      "e": [660., 1.65, 5., 0.]}
        one_group = {k: v for k, v in two_groups.items() if k in ("c", "d", "e")}
        result = self.run_frames([(0., two_groups), (1., one_group), (2., one_group)])
        self.assertAlmostEqual(result["mean_platoon_size"], 8./3.)
        self.assertAlmostEqual(result["vehicle_seconds"], 8.)
        self.assertAlmostEqual(result["platoon_seconds"], 3.)

    def test_invalid_or_repeated_time_and_nonfinite_data_are_rejected(self):
        states = {"a": [100., 1.65, 5., 0.]}
        with self.assertRaises(ValueError):
            self.run_frames([(1., states), (1., states)])
        with self.assertRaises(ValueError):
            self.run_frames([(0., {"a": [math.nan, 1.65, 5., 0.]})])
        with self.assertRaises(ValueError):
            self.run_frames([(0., states)], gap=0.)


if __name__ == "__main__":
    unittest.main()
