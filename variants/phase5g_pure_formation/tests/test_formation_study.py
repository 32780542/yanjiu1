"""随机车流、物理评价和紧凑推进的可复算算例。"""

from dataclasses import asdict
import math
import unittest


class FormationStudyTests(unittest.TestCase):
    def test_matlab_probability_and_paired_requests(self):
        from experiments.formation_study import bernoulli_requests
        rows = bernoulli_requests(12, 3, 756, 2)
        self.assertEqual(rows, bernoulli_requests(12, 3, 756, 2))
        self.assertEqual(len(rows), 12)
        self.assertGreater(rows[0][0], 0.0)
        self.assertTrue(all(abs(round(t * 10) - t * 10) < 1e-8 for t, _, _ in rows))
        self.assertTrue(all(0 <= lane < 3 and 8 <= speed <= 12
                            for _, lane, speed in rows))
        many = bernoulli_requests(12000, 3, 756, 102)
        observed = (len(many) - 1) / many[-1][0] / 3 * 3600
        self.assertLess(abs(observed - 756), 30)

    def test_entry_waits_for_existing_headway(self):
        from experiments.formation_study import entry_is_clear, study_parameters
        from models.vehicle import VehicleState
        _, physical, _ = study_parameters(10.0, 30.0)
        entry = VehicleState(x_m=100, y_m=1.65, vx_mps=10)
        self.assertFalse(entry_is_clear(entry, {"front": VehicleState(
            x_m=110, y_m=1.65, vx_mps=10)}, physical))
        self.assertTrue(entry_is_clear(entry, {"front": VehicleState(
            x_m=150, y_m=1.65, vx_mps=10)}, physical))
        self.assertTrue(entry_is_clear(entry, {"adjacent": VehicleState(
            x_m=100, y_m=4.95, vx_mps=10)}, physical))

    def test_compact_tick_matches_existing_clock(self):
        from experiments import phase5g, phase5g_cases
        from experiments.formation_study import StudyClock, study_parameters
        from models.vehicle import VehicleState
        from perception.road import VisibleRoad
        from simulation.phase5g_clock import CLOCK_SCHEMA, Phase5GClock, initial_memory_hash
        model, physical, policy = study_parameters(10.0, 30.0)
        case = phase5g_cases.demo_case(physical, 8, 3, lane_count=2,
            straight_road=True, depart_interval_min_s=3, depart_interval_max_s=3)
        memories = phase5g._initial_memories(case, "lane_priority", simple_rules=True)
        args = ({key: VehicleState(**s) for key, s in case["initial"].items()},
                model, VisibleRoad.from_net(phase5g._road_network(case)),
                physical, policy, case["controlled"], {}, memories)
        kwargs = dict(clock_schema=CLOCK_SCHEMA,
                      initial_memories_sha256=initial_memory_hash(memories),
                      departures=case["departures"])
        original = Phase5GClock(*args, **kwargs)
        compact = StudyClock(*args, **kwargs)
        for _ in range(100):
            record = original.tick()
            steps, decisions = compact.tick_compact(queue_entries=False)
            self.assertEqual(dict(original.states), dict(compact.states))
            self.assertEqual(original.memories, compact.memories)
            self.assertEqual(record["steps"], {k: asdict(v) for k, v in steps.items()})
            self.assertEqual(record["decisions"], {k: asdict(v) for k, v in decisions.items()})

    def test_exact_staggered_geometry_and_speed_error(self):
        from experiments.formation_metrics import final_errors
        states = {f"v{lane}_{rank}": dict(x_m=200-rank*30-((2-lane)%2)*15,
            y_m=3.3*(lane+.5), vx_mps=10., vy_mps=0., heading_rad=0.)
            for lane in range(3) for rank in range(4)}
        result = final_errors(states, 3, 30.0)
        self.assertEqual(result["max_geometry_error_m"], 0.)
        self.assertEqual(result["speed_std_mps"], 0.)
        states["v0_3"]["x_m"] += 3
        states["v0_3"]["vx_mps"] = 12
        result = final_errors(states, 3, 30.0)
        self.assertEqual(result["max_geometry_error_m"], 3.)
        self.assertAlmostEqual(result["speed_std_mps"], math.sqrt(11)/6)

    def test_compact_clock_preserves_active_lane_changes(self):
        from experiments.formation_study import StudyClock, make_clock, planned_cases
        from simulation.phase5g_clock import CLOCK_SCHEMA, Phase5GClock, initial_memory_hash
        warmup, _ = make_clock(planned_cases()[5])
        while not any(m.plan is not None for m in warmup.memories.values()):
            self.assertLess(warmup._current_time(), 100.)
            warmup.tick_compact()
        memories = {key: asdict(m) for key, m in warmup.memories.items()}
        args = (dict(warmup.states), warmup.model, warmup._road,
                warmup.p, warmup.policy, tuple(warmup.states), {}, memories)
        kwargs = dict(clock_schema=CLOCK_SCHEMA,
                      initial_memories_sha256=initial_memory_hash(memories))
        original, compact = Phase5GClock(*args, **kwargs), StudyClock(*args, **kwargs)
        active_lane_changes = 0
        for _ in range(60):
            record = original.tick()
            steps, decisions = compact.tick_compact(queue_entries=False)
            self.assertEqual(dict(original.states), dict(compact.states))
            self.assertEqual(original.memories, compact.memories)
            self.assertEqual(record["decisions"], {k: asdict(v) for k, v in decisions.items()})
            active_lane_changes += any(memory.plan is not None for memory in compact.memories.values())
        self.assertGreater(active_lane_changes, 0)

    def test_matrix_has_65_unique_cases(self):
        from experiments.formation_study import planned_cases
        cases = planned_cases()
        self.assertEqual(len(cases), 65)
        self.assertEqual(len({case["name"] for case in cases}), 65)
        self.assertEqual(sum(case["kind"] == "lane_flow" for case in cases), 45)

    def test_missing_lanes_do_not_report_zero_geometry_error(self):
        from experiments.formation_metrics import final_errors
        states = {f"v{i}": dict(x_m=500-i*30., y_m=1.65,
            vx_mps=10., vy_mps=0., heading_rad=0.) for i in range(12)}
        result = final_errors(states, 3, 30.)
        self.assertIsNone(result["max_geometry_error_m"])
        self.assertIsNone(result["max_middle_offset_error_m"])
        self.assertEqual(result["max_same_lane_gap_error_m"], 0.)

    def test_queued_requests_all_enter_with_valid_timestamps(self):
        import tempfile
        from experiments.formation_study import planned_cases, run_case
        case = dict(planned_cases()[10], vehicle_count=4, observation_after_entry_s=1.)
        with tempfile.TemporaryDirectory() as root:
            result = run_case(case, root)
        self.assertTrue(result["recording_valid"])
        self.assertEqual(result["collision_pairs"], 0)
        self.assertGreater(result["max_entry_delay_s"], 0)

    def test_whole_formation_is_confirmed_without_deadline_or_hold(self):
        import gzip
        import json
        from pathlib import Path
        import tempfile
        from experiments.formation_metrics import evaluate_run
        from experiments.formation_study import write_json
        states = {f"v{lane}_{rank}": dict(x_m=200-rank*30-((2-lane)%2)*15,
            y_m=3.3*(lane+.5), vx_mps=10., vy_mps=0., heading_rad=0.)
            for lane in range(3) for rank in range(4)}
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            write_json(root / "input.json", dict(case=dict(lane_count=3,
                same_lane_gap_m=30., target_speed_mps=10.),
                departures={key: dict(scheduled_departure_s=0., actual_departure_s=0.)
                            for key in states}, completed_lane_changes=0))
            write_json(root / "incidents.json", {})
            with gzip.open(root / "trajectory.jsonl.gz", "wt", encoding="utf-8") as stream:
                for tick in range(12):
                    stream.write(json.dumps(dict(time_s=tick*.1, states={key:
                        dict(s, x_m=s["x_m"]+tick) for key, s in states.items()}))+"\n")
            result = evaluate_run(root)
        self.assertTrue(result["formation_success"])
        self.assertEqual(result["formation_delay_s"], 1.)
        self.assertTrue(result["recording_valid"])

    def test_aggregate_preserves_unformed_and_missing_values(self):
        from summarize_formation_study import aggregate
        rows = [dict(kind="parameter", lane_count=3, flow_veh_h_lane=756,
            target_speed_mps=10., same_lane_gap_m=30., formation_success=formed,
            formation_delay_s=delay, max_geometry_error_m=geometry,
            speed_spread_mps=.1, max_target_speed_error_mps=.2, collision_pairs=0)
            for formed, delay, geometry in ((True, 50., .1), (True, 80., .2),
                                             (False, None, None))]
        group = aggregate(rows)[0]
        self.assertEqual(group["attempts"], 3)
        self.assertEqual(group["formed"], 2)
        self.assertEqual(group["median_delay_s"], 65.)
        self.assertEqual(group["geometry_evaluable_runs"], 2)
        self.assertAlmostEqual(group["median_final_geometry_error_m"], .15)


if __name__ == "__main__":
    unittest.main()
