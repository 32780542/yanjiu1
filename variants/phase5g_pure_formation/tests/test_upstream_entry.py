"""物理上游段、测量边界和移动入场的独立验收。"""

import unittest

from experiments.traffic_flow import OpenTraffic
from models.kinematic import kinematic_state


def clock(tape):
    return OpenTraffic(dict(lane_count=3,target_speed_mps=28.8,same_lane_gap_m=30.,
        formation=False,demand_duration_s=1.,max_time_s=70.),tape)


class UpstreamEntryTests(unittest.TestCase):
    def test_new_vehicle_is_moving_upstream_before_measurement_entry(self):
        run = clock([dict(vehicle_id='one',requested_s=0.,lane=0)])
        event = run.tick()
        self.assertLess(run.states['one'].x_m,0.)
        self.assertGreater(run.states['one'].vx_mps,0.)
        self.assertIsNone(run.trips['one']['entered_s'])
        self.assertEqual(event['active'],0)
        self.assertEqual(event['vehicle_seconds'],0.)

    def test_source_speed_matches_local_moving_leader(self):
        run = clock([dict(vehicle_id='new',requested_s=0.,lane=0)])
        run.states['front'] = kinematic_state(run.p,x_m=-230.,y_m=1.65,vx_mps=5.)
        run._admit()
        self.assertIn('new',run.states)
        self.assertAlmostEqual(run.states['new'].vx_mps,5.)
        self.assertEqual(run.trips['new']['inserted_s'],0.)

    def test_short_gap_waits_outside_instead_of_inserting_an_artificial_slow_car(self):
        run = clock([dict(vehicle_id='new',requested_s=0.,lane=0)])
        run.states['front'] = kinematic_state(run.p,x_m=-290.,y_m=1.65,vx_mps=28.8)
        run._admit()
        self.assertNotIn('new',run.states)
        self.assertEqual(run.states['front'].vx_mps,28.8)
        self.assertEqual(len(run.queues[0]),1)

    def test_only_1200_metres_and_measurement_time_enter_the_ledger(self):
        run = clock([dict(vehicle_id='one',requested_s=0.,lane=0)])
        while run.trips['one']['exited_s'] is None:
            run.tick()
        row = run.trips['one']
        self.assertAlmostEqual(row['entered_s'],300/28.8,places=6)
        self.assertAlmostEqual(row['exited_s'],1500/28.8,places=6)
        self.assertAlmostEqual(row['distance_m'],1200.,places=6)
        self.assertAlmostEqual(row['onroad_s'],1200/28.8,places=6)
        self.assertEqual(run.inserted_count,run.entered_count)
        self.assertEqual(run.entered_count,run.exited_count)

    def test_source_wait_excludes_physical_upstream_travel(self):
        from experiments.traffic_metrics import summarize_trips
        row = dict(requested_s=0.,inserted_s=1.,entered_s=11.,exited_s=51.,
                   distance_m=1200.,onroad_s=40.,fuel_mg=80000.)
        result = summarize_trips([row],600.,600.)
        self.assertEqual(result['mean_entry_wait_s'],1.)
        self.assertEqual(result['mean_upstream_travel_s'],10.)
        self.assertEqual(result['mean_entry_delay_s'],11.)
        self.assertEqual(result['mean_travel_time_s'],40.)
        self.assertEqual(result['mean_system_time_s'],51.)
        from summarize_traffic_flow import independent_metrics
        other = independent_metrics([row],600.,600.)
        self.assertEqual(other['mean_entry_wait_s'],1.)
        self.assertEqual(other['mean_upstream_travel_s'],10.)


if __name__=='__main__':
    unittest.main()
