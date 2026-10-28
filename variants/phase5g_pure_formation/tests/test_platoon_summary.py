"""稳定时间在已编队车辆中归一化，独立于总体参与率。"""

import unittest
import summarize_traffic_flow as summary


class PlatoonSummaryTests(unittest.TestCase):
    def test_stability_is_conditioned_on_platoon_exposure(self):
        self.assertTrue(hasattr(summary,'conditional_stability'))
        measured = dict(vehicle_seconds=40.,platoon_vehicle_seconds=20.,stable_vehicle_seconds=10.)
        self.assertEqual(summary.conditional_stability(measured),.5)

    def test_no_platoon_has_undefined_conditional_stability(self):
        self.assertTrue(hasattr(summary,'conditional_stability'))
        self.assertIsNone(summary.conditional_stability(dict(
            platoon_vehicle_seconds=0.,stable_vehicle_seconds=0.)))

    def test_group_reports_how_many_seeds_have_a_defined_platoon_size(self):
        base = dict(kind='demand',lane_count=3,flow_veh_h_lane=2000,target_speed_mps=28.8,
            same_lane_gap_m=30.,formation=False,all_completed=True,collision_pairs=0,
            road_departure_vehicles=0,requested=100,completed=100)
        rows = [dict(base,mean_platoon_size=None,participation_rate=0.),
                dict(base,mean_platoon_size=None,participation_rate=0.),
                dict(base,mean_platoon_size=2.,participation_rate=.03)]
        group = summary.group_rows(rows)[0]
        self.assertIn('mean_platoon_size_n',group)
        self.assertEqual(group['mean_platoon_size_n'],1)
        self.assertEqual(group['participation_rate_n'],3)
        self.assertEqual(group['mean_platoon_size_mean'],2.)
        self.assertAlmostEqual(group['participation_rate_mean'],.01)
