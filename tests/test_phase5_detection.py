"""Fixed offline trajectories; no controller state is part of detection."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
import unittest

from models.vehicle import VehicleState


def trajectory(positions, duration=16., velocities=None):
    velocities = velocities or {}
    return [
        {'time_s': round(i / 10, 10), 'states': {
            key: asdict(VehicleState(time_s=i / 10, x_m=x + 5 * i / 10,
                                     y_m=(lane + .5) * 3.3,
                                     vx_mps=velocities.get(key, 5.)))
            for key, (x, lane) in positions.items()}}
        for i in range(round(duration * 10) + 1)]


TRIPLE = {'a': (0., 0), 'b': (15., 1), 'c': (30., 0)}


class Phase5DetectionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase5_detection'),
                             'Independent phase5 detector has not been implemented')
        from experiments.phase5_detection import detect_frames
        self.detect = detect_frames

    def test_exact_staggered_group_is_confirmed_then_held(self):
        result = self.detect(trajectory(TRIPLE))
        self.assertTrue(result['success'])
        interval = result['intervals'][0]
        self.assertEqual(interval['members'], ['a', 'b', 'c'])
        self.assertEqual(interval['formed_time_s'], 5.)
        self.assertEqual(interval['held_time_s'], 15.)
        self.assertEqual(interval['end_time_s'], 16.)
        self.assertEqual(interval['end_reason'], 'recording_end')
        self.assertEqual(result['frames'][0]['fleet_coverage_fraction'], 1.)
        self.assertEqual(result['frames'][0]['groups'][0]['adjacency_occupancy_completeness'], 1.)
        self.assertEqual(result['frames'][0]['groups'][0]['occupancy_edges_denominator'], 3)
        self.assertEqual(result['frames'][0]['fleet_road_span_m'], 34.)

    def test_six_vehicle_three_lane_geometry(self):
        positions = {f'v{lane}{column}': (column * 30. + lane % 2 * 15., lane)
                     for lane in range(3) for column in range(2)}
        result = self.detect(trajectory(positions))
        self.assertTrue(result['success'])
        self.assertEqual(result['frames'][0]['groups'][0]['occupied_slots'], 6)
        self.assertEqual(result['frames'][0]['groups'][0]['possible_slots'], 6)

    def test_sparse_distant_lattice_points_do_not_form(self):
        result = self.detect(trajectory({'a': (0., 0), 'b': (60., 0), 'c': (75., 1)}))
        self.assertFalse(result['success'])
        self.assertFalse(result['intervals'])
        self.assertIn('disconnected_occupied_slots', result['frames'][0]['fleet_failure_reasons'])

    def test_whole_group_speed_range_excludes_transitive_speed_chain(self):
        result = self.detect(trajectory(TRIPLE, velocities={'a': 5., 'b': 5.75, 'c': 6.5}))
        self.assertFalse(result['intervals'])
        self.assertIn('speed_spread_exceeded', result['frames'][0]['fleet_failure_reasons'])

    def test_single_lane_is_not_staggered(self):
        result = self.detect(trajectory({'a': (0., 0), 'b': (30., 0), 'c': (60., 0)}))
        self.assertFalse(result['intervals'])

    def test_nonadjacent_lanes_cannot_be_joined(self):
        result = self.detect(trajectory({'a': (0., 0), 'b': (30., 0), 'c': (30., 2)}))
        self.assertFalse(result['intervals'])

    def test_duplicate_slot_cannot_inflate_vehicle_count(self):
        result = self.detect(trajectory({'a': (0., 0), 'b': (.1, 0), 'c': (15., 1)}))
        self.assertFalse(result['intervals'])
        self.assertIn('duplicate_occupied_slot', result['frames'][0]['fleet_failure_reasons'])

    def test_member_changes_cannot_be_stitched_into_five_seconds(self):
        frames = trajectory(TRIPLE, duration=8.)
        for frame in frames:
            if frame['time_s'] >= 4.:
                frame['states']['d'] = frame['states'].pop('c')
        result = self.detect(frames)
        self.assertFalse(result['intervals'])
        self.assertTrue(result['candidate_intervals'])
        self.assertTrue(all(row['duration_s'] < 5 for row in result['candidate_intervals']))

    def test_joining_member_does_not_erase_existing_group_persistence(self):
        frames = trajectory(TRIPLE, duration=16.)
        for frame in frames:
            if frame['time_s'] >= 3.:
                frame['states']['d'] = asdict(VehicleState(x_m=45 + frame['time_s'] * 5,
                                                          y_m=4.95, vx_mps=5))
        result = self.detect(frames)
        original = next(row for row in result['intervals'] if row['members'] == ['a', 'b', 'c'])
        self.assertEqual(original['formed_time_s'], 5.)
        self.assertEqual(original['duration_s'], 16.)
        self.assertFalse(result['success'])  # all four have only 13 s together
        self.assertTrue(result['local_success'])

    def test_subgroup_success_never_becomes_whole_fleet_success(self):
        positions = {**TRIPLE, 'far': (500., 2)}
        result = self.detect(trajectory(positions))
        self.assertTrue(result['local_success'])
        self.assertFalse(result['success'])
        self.assertEqual(result['frames'][0]['fleet_coverage_fraction'], .75)
        self.assertEqual(result['cohort_size'], 4)

    def test_short_recording_does_not_extrapolate_hold(self):
        result = self.detect(trajectory(TRIPLE, duration=14.9))
        self.assertFalse(result['success'])
        self.assertEqual(result['intervals'][0]['held_time_s'], None)
        self.assertIn('hold_after_confirmation_too_short', result['intervals'][0]['failure_reasons'])

    def test_dropout_ends_interval_and_recovery_starts_new_interval(self):
        frames = trajectory(TRIPLE, duration=22.)
        frames[70]['states']['c']['x_m'] += 10
        result = self.detect(frames)
        self.assertEqual(len(result['intervals']), 2)
        self.assertEqual(result['intervals'][0]['end_time_s'], 6.9)
        self.assertEqual(result['intervals'][0]['end_reason'], 'geometry_or_membership_lost')
        self.assertEqual(result['intervals'][1]['start_time_s'], 7.1)
        self.assertEqual(result['intervals'][1]['formed_time_s'], 12.1)

    def test_missing_sample_breaks_persistence(self):
        frames = trajectory(TRIPLE, duration=8.)
        del frames[40]
        result = self.detect(frames)
        self.assertFalse(result['intervals'])
        self.assertEqual(result['sampling_gap_count'], 1)

    def test_missing_fine_control_sample_also_breaks_persistence(self):
        frames = trajectory(TRIPLE, duration=16.)
        for frame in frames:
            frame['time_s'] /= 2
        del frames[80]
        result = self.detect(frames)
        self.assertFalse(result['intervals'])
        self.assertEqual(result['sampling_gap_count'], 1)
        self.assertAlmostEqual(result['parameters']['max_sample_gap_s'], .05)

    def test_disjoint_groups_covering_all_vehicles_are_not_one_fleet_formation(self):
        positions = {**TRIPLE, **{key + '2': (x + 300, lane) for key, (x, lane) in TRIPLE.items()}}
        result = self.detect(trajectory(positions))
        self.assertEqual(result['frames'][0]['fleet_coverage_fraction'], 1.)
        self.assertEqual(result['frames'][0]['largest_group_fraction'], .5)
        self.assertTrue(result['local_success'])
        self.assertFalse(result['success'])

    def test_missing_sites_are_in_completeness_denominator(self):
        result = self.detect(trajectory({'a': (0, 0), 'b': (15, 1), 'c': (30, 2)}))
        measurement = result['frames'][0]['groups'][0]
        self.assertEqual(measurement['occupied_slots'], 3)
        self.assertEqual(measurement['possible_slots'], 5)
        self.assertEqual(measurement['occupancy_edges_numerator'], 2)
        self.assertEqual(measurement['occupancy_edges_denominator'], 6)
        self.assertAlmostEqual(measurement['adjacency_occupancy_completeness'], 1 / 3)

    def test_exact_twelve_vehicle_group_does_not_need_subset_enumeration(self):
        positions = {f'v{lane}{column}': (column * 30. + lane % 2 * 15., lane)
                     for lane in range(3) for column in range(4)}
        result = self.detect(trajectory(positions))
        self.assertTrue(result['success'])
        self.assertEqual(len(result['intervals']), 1)
        self.assertEqual(result['intervals'][0]['members'], sorted(positions))

    def test_duplicate_or_reversed_timestamps_are_rejected(self):
        frames = trajectory(TRIPLE, duration=.1)
        with self.assertRaisesRegex(ValueError, 'strictly increasing'):
            self.detect([frames[1], frames[0]])
        with self.assertRaisesRegex(ValueError, 'strictly increasing'):
            self.detect([frames[0], frames[0]])

    def test_position_threshold_sensitivity_and_circular_phase_fit(self):
        positions = {'a': (-1.5, 0), 'b': (15., 1), 'c': (31.5, 0)}
        frames = trajectory(positions)
        self.assertTrue(self.detect(frames)['success'])
        self.assertFalse(self.detect(frames, position_tolerance=1.)['local_success'])
        self.assertTrue(self.detect(frames, position_tolerance=3.)['success'])

    def test_speed_threshold_sensitivity(self):
        frames = trajectory(TRIPLE, velocities={'a': 5., 'c': 5.75})
        self.assertTrue(self.detect(frames)['success'])
        self.assertFalse(self.detect(frames, speed_tolerance=.5)['success'])

    def test_late_confirmation_misses_deadline(self):
        frames = trajectory(TRIPLE, duration=42.)
        for frame in frames:
            if frame['time_s'] < 27.:
                frame['states']['c']['x_m'] += 10
        result = self.detect(frames)
        self.assertFalse(result['success'])
        self.assertEqual(result['intervals'][0]['formed_time_s'], 32.)
        self.assertIn('formation_deadline_missed', result['intervals'][0]['failure_reasons'])

    def test_input_is_immutable_and_hidden_fields_do_not_change_detection(self):
        frames = trajectory(TRIPLE, duration=5.)
        original = deepcopy(frames)
        result = self.detect(frames)
        self.assertEqual(frames, original)
        for frame in frames:
            for state in frame['states'].values():
                state.update(vehicle_type='adversarial', target_slot=999, future_plan=[1, 2])
        self.assertEqual(result, self.detect(frames))
        json.dumps(result, allow_nan=False)

    def test_empty_recording_and_invalid_parameters_are_explicit(self):
        result = self.detect([])
        self.assertFalse(result['success'])
        self.assertIn('empty_recording', result['failure_reasons'])
        with self.assertRaises(ValueError):
            self.detect(trajectory(TRIPLE, duration=0.), d=0)
        frames = trajectory(TRIPLE, duration=0.)
        frames[0]['states']['a']['x_m'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite'):
            self.detect(frames)


if __name__ == '__main__':
    unittest.main()
