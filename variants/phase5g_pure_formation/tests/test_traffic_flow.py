"""持续交通、油耗及统计口径的独立算例。"""

from dataclasses import replace
import json
from pathlib import Path
import unittest


class TrafficFlowTests(unittest.TestCase):
    def test_fuel_matches_sumo_and_has_correct_time_units(self):
        from models.fuel import fuel_rate_mg_s
        self.assertAlmostEqual(fuel_rate_mg_s(0., 0.), 837.2222222222222)
        self.assertAlmostEqual(fuel_rate_mg_s(10., 0.), 673.7222222222222)
        self.assertAlmostEqual(fuel_rate_mg_s(10., 1.), 1505.111111111111)
        self.assertAlmostEqual(fuel_rate_mg_s(10., -.2), 507.4444444444444)
        self.assertEqual(fuel_rate_mg_s(10., -2.), 0.)
        self.assertAlmostEqual(sum(fuel_rate_mg_s(20., 0.)*.01 for _ in range(100)), 1011.)

    def test_fuel_matches_the_official_tool_over_47_recorded_points(self):
        from models.fuel import fuel_rate_mg_s
        rows = json.loads((Path(__file__).parent/"fixtures/hbefa3_pc_g_eu4_sumo_1_27_1.json").read_text())
        self.assertEqual(len(rows),47)
        for row in rows:
            self.assertLessEqual(abs(fuel_rate_mg_s(row["speed_mps"],row["acceleration_mps2"])
                                     -row["sumo_fuel_mg_s"]), .005000001)

    def test_continuous_arrivals_are_duration_limited_and_paired(self):
        from experiments.traffic_flow import arrival_tape
        rows = arrival_tape(3, 2000, 2, 600)
        self.assertEqual(rows, arrival_tape(3, 2000, 2, 600))
        self.assertGreater(len(rows), 900)
        self.assertTrue(all(0 <= r["requested_s"] < 600 for r in rows))
        self.assertEqual(len({r["vehicle_id"] for r in rows}), len(rows))

    def test_efficiency_and_fuel_are_computed_from_same_cohort(self):
        from experiments.traffic_metrics import summarize_trips
        trips = [dict(requested_s=0., entered_s=2., exited_s=122.,
                      distance_m=1200., onroad_s=120., fuel_mg=60000.),
                 dict(requested_s=0., entered_s=4., exited_s=124.,
                      distance_m=1200., onroad_s=120., fuel_mg=120000.)]
        result = summarize_trips(trips, 600., 600.)
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["mean_entry_wait_s"], 3.)
        self.assertEqual(result["mean_travel_time_s"], 120.)
        self.assertEqual(result["mean_system_time_s"], 123.)
        self.assertEqual(result["fuel_g_per_km"], 75.)
        self.assertEqual(result["exit_flow_veh_h"], 12.)

    def test_unfinished_requests_remain_in_counts(self):
        from experiments.traffic_metrics import summarize_trips
        trips = [dict(requested_s=0., entered_s=None, exited_s=None,
                      distance_m=0., onroad_s=0., fuel_mg=0.),
                 dict(requested_s=1., entered_s=2., exited_s=None,
                      distance_m=200., onroad_s=20., fuel_mg=1000.)]
        result = summarize_trips(trips, 600., 600.)
        self.assertEqual(result["completed"], 0)
        self.assertEqual(result["pending_final"], 1)
        self.assertEqual(result["onroad_final"], 1)
        self.assertIsNone(result["mean_system_time_s"])
        self.assertIsNone(result["clearance_after_600s_s"])

    def test_spatial_candidates_preserve_rotated_sensor_observations(self):
        from experiments.traffic_flow import FrameIndex
        from experiments.formation_study import study_parameters
        from models.vehicle import VehicleState
        from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
        from perception.road import VisibleRoad
        _, p, _ = study_parameters(28.8, 30.)
        road = VisibleRoad((((-500., 0.), (3000., 0.)), ((-500., 9.9), (3000., 9.9))), ())
        vehicles = tuple(TruthVehicle(f"v{i}", VehicleState(x_m=i*10., y_m=4.95,
            heading_rad=.2 if i == 20 else 0., vx_mps=10.), 4., 1.8) for i in range(70))
        full = WorldFrame(vehicles)
        a, b = IdealSensor(p, road), IdealSensor(p, road)
        self.assertEqual(a.sample("v20", full), b.sample("v20", FrameIndex(full).around("v20")))

    def test_open_exit_is_interpolated_without_end_of_road_braking(self):
        from experiments.traffic_flow import OpenTraffic
        tape = [dict(vehicle_id="one", requested_s=0., lane=0)]
        clock = OpenTraffic(dict(lane_count=3, target_speed_mps=28.8,
            same_lane_gap_m=30., formation=False, demand_duration_s=1., max_time_s=60.), tape)
        while clock.trips["one"]["exited_s"] is None:
            clock.tick()
        trip = clock.trips["one"]
        self.assertAlmostEqual(trip["exited_s"], 1200/28.8, places=6)
        self.assertAlmostEqual(trip["distance_m"], 1200., places=6)
        self.assertEqual(len(clock.states), 0)
        empty = clock.tick()
        self.assertEqual(empty["entered"], 1)
        self.assertEqual(empty["exited"], 1)

    def test_matrix_contains_all_paired_main_cases(self):
        from experiments.traffic_flow import planned_cases
        rows = planned_cases()
        self.assertEqual(len(rows), 54)
        self.assertEqual(len({r["name"] for r in rows}), 54)
        main = [r for r in rows if r["kind"] == "demand"]
        self.assertEqual(len(main), 24)
        self.assertEqual({r["flow_veh_h_lane"] for r in main}, {1250,1500,1750,2000})

    def test_both_modes_use_lane_keeping_as_the_common_driving_baseline(self):
        from experiments.traffic_flow import OpenTraffic, planned_cases
        for case in planned_cases()[:2]:
            clock = OpenTraffic(case, [])
            self.assertGreater(clock.policy["noa_overtake_speed_deficit_mps"],
                               2*clock.policy["max_speed_mps"])

    def test_entry_respects_actual_braking_distance_before_a_slow_queue(self):
        from experiments.traffic_flow import entry_is_clear
        from experiments.formation_study import study_parameters
        from models.kinematic import kinematic_state
        _, p, _ = study_parameters(28.8,30.)
        entrant = kinematic_state(p,x_m=0.,y_m=1.65,vx_mps=28.8)
        front = kinematic_state(p,x_m=70.,y_m=1.65,vx_mps=5.)
        self.assertFalse(entry_is_clear(entrant,{"front":front},p))
        self.assertTrue(entry_is_clear(entrant,{"front":replace(front,x_m=220.)},p))

    def test_vehicle_stops_participating_in_audit_after_exit(self):
        from experiments.traffic_flow import OpenTraffic
        from models.kinematic import kinematic_state
        from noa.contracts import NoaMemory
        from perception.ideal import IdealSensor
        tape = [dict(vehicle_id=key, requested_s=0., lane=0) for key in ("front", "rear")]
        clock = OpenTraffic(dict(lane_count=3, target_speed_mps=28.8,
            same_lane_gap_m=30., formation=False, demand_duration_s=1., max_time_s=60.), tape)
        clock.cursor = clock.entered_count = 2
        clock.states = {"front":kinematic_state(clock.p,x_m=1199.9,y_m=1.65,vx_mps=28.8),
                        "rear":kinematic_state(clock.p,x_m=1195.8,y_m=1.65,vx_mps=32.)}
        clock.sensors = {key:IdealSensor(clock.p,clock.road) for key in clock.states}
        clock.memories = {key:NoaMemory((),"CRUISE") for key in clock.states}
        for row in clock.trips.values():
            row["entered_s"] = 0.
        clock.tick()
        self.assertLess(clock.trips["front"]["exited_s"], .01)
        self.assertEqual(clock.incidents["collision_events"], [])

    def test_report_preserves_fuel_increase_and_reuses_only_matching_baseline(self):
        from summarize_traffic_flow import paired_rows
        base = dict(lane_count=3,flow_veh_h_lane=1500,seed=1,target_speed_mps=28.8,
            same_lane_gap_m=30.,kind="demand",formation=False,name="base",
            all_completed=True,collision_pairs=0,road_departure_vehicles=0,mean_system_time_s=100.,
            mean_travel_time_s=50.,fuel_g_per_km=80.,exit_flow_veh_h=4000.)
        treatment = dict(base, formation=True,kind="gap",name="gap24",same_lane_gap_m=24.,
            mean_system_time_s=80.,mean_travel_time_s=40.,fuel_g_per_km=88.,exit_flow_veh_h=4200.)
        pair = paired_rows([base,treatment])[0]
        self.assertEqual(pair["baseline_name"],"base")
        self.assertEqual(pair["system_time_reduction_pct"],20.)
        self.assertAlmostEqual(pair["fuel_reduction_pct"],-10.)
        self.assertEqual(pair["exit_flow_change_pct"],5.)

    def test_report_retains_incomplete_pair_without_claiming_an_improvement(self):
        from summarize_traffic_flow import paired_rows
        base = dict(lane_count=3,flow_veh_h_lane=1500,seed=1,target_speed_mps=28.8,
            same_lane_gap_m=30.,kind="demand",formation=False,name="base",
            all_completed=False,collision_pairs=0,road_departure_vehicles=0,mean_system_time_s=None,
            mean_travel_time_s=None,fuel_g_per_km=80.,exit_flow_veh_h=4000.)
        pair = paired_rows([base,dict(base,name="on",formation=True)])[0]
        self.assertFalse(pair["comparison_valid"])
        self.assertIsNone(pair["system_time_reduction_pct"])

    def test_road_departure_is_not_an_effectiveness_improvement(self):
        from summarize_traffic_flow import paired_rows,group_rows
        base = dict(lane_count=3,flow_veh_h_lane=1500,seed=1,target_speed_mps=28.8,
            same_lane_gap_m=30.,kind="demand",formation=False,name="base",
            all_completed=True,collision_pairs=0,road_departure_vehicles=0,
            mean_system_time_s=100.,mean_travel_time_s=50.,fuel_g_per_km=80.,exit_flow_veh_h=4000.)
        treatment = dict(base,name="offroad",formation=True,road_departure_vehicles=1)
        pair = paired_rows([base,treatment])[0]
        self.assertFalse(pair["comparison_valid"])
        self.assertIsNone(pair["fuel_reduction_pct"])
        self.assertEqual(group_rows([treatment])[0]["valid_runs"],0)


if __name__ == "__main__":
    unittest.main()
