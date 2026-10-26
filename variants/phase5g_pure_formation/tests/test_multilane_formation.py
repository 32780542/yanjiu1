"""Two- and four-lane extensions of the same local formation geometry."""

import unittest
import tempfile
from pathlib import Path

from experiments.phase5_detection import detect_frames
from experiments.phase5g_schedule import deterministic_schedule_rows
from experiments import phase5g, phase5g_cases
from noa.simple_formation import LocalVehicle, SimpleFormationMemory, PARAMETERS
from noa.simple_formation import choose_formation_target, choose_layered_fill


P = {
    "simple_formation_component_gap_m": 50.0,
    "simple_formation_middle_offset_m": 15.0,
    "simple_formation_same_lane_gap_m": 30.0,
    "simple_formation_position_tolerance_m": 2.0,
    "simple_formation_speed_tolerance_mps": 1.0,
    "simple_formation_stable_time_s": 1.0,
    "simple_formation_reference_switch_gain_m": 2.0,
    "simple_formation_min_lane_change_speed_mps": 5.0,
    "simple_formation_target_lane_clearance_m": 8.0,
    "noa_target_speed_mps": 10.0,
    "noa_completion_lateral_error_m": 0.15,
}


def car(track, x, lane):
    return LocalVehicle(track, x, 3.3 * (lane + 0.5), 10.0, lane)


def state(time_s, x, lane):
    return {"time_s": time_s, "x_m": x, "y_m": 3.3 * (lane + 0.5),
            "heading_rad": 0.0, "vx_mps": 10.0, "vy_mps": 0.0}


class MultilaneFormationTests(unittest.TestCase):
    def test_four_lane_demo_case_declares_straight_road_and_safe_departures(self):
        _, physical, _ = phase5g.parameters("lane_priority", 10.0,
                                           simple_rules=True,
                                           simple_overrides={key: P[key]
                                                             for key in PARAMETERS})
        case = phase5g_cases.demo_case(
            physical, 8, 1, lane_count=4, straight_road=True,
            depart_interval_min_s=2.0, depart_interval_max_s=2.0)
        self.assertEqual((case["lane_count"], case["road_kind"]), (4, "straight"))
        self.assertEqual(len(case["departures"]), 8)
        self.assertTrue(all(row["state"]["y_m"] <= 11.55
                            for row in case["departures"].values()))

    def test_short_two_and_four_lane_runs_use_constant_width_roads(self):
        model, physical, policy = phase5g.parameters(
            "lane_priority", 10.0, simple_rules=True,
            simple_overrides={key: P[key] for key in PARAMETERS})
        with tempfile.TemporaryDirectory() as temp:
            for lane_count in (2, 4):
                with self.subTest(lane_count=lane_count):
                    case = phase5g_cases.demo_case(
                        physical, 4, 1, lane_count=lane_count,
                        straight_road=True, depart_interval_min_s=0.1,
                        depart_interval_max_s=0.1)
                    case["duration_s"] = 0.4
                    result = phase5g.run_variant(
                        Path(temp) / f"lane-{lane_count}", model, physical,
                        policy, case, "lane_priority", live=False)
                    self.assertEqual(result["status"], "completed", result)
                    self.assertEqual(len(result["summary"]["final_lane_counts"]),
                                     lane_count)

    def test_sealed_demo_accepts_four_lane_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            outer = phase5g.run_phase5g_demo(
                vehicle_count=4, seed=1, target_speed_mps=10.0,
                duration_s=0.4, output_base=Path(temp) / "four-demo",
                live=False, lane_count=4,
                depart_interval_min_s=0.1, depart_interval_max_s=0.1)
            self.assertTrue(outer.is_dir())
            self.assertTrue((outer / "validation.json").is_file())

    def test_seeded_departures_stay_inside_selected_lane_count(self):
        for lane_count in (2, 3, 4):
            with self.subTest(lane_count=lane_count):
                rows = deterministic_schedule_rows(
                    12, 1, depart_interval_min_s=1.0,
                    depart_interval_max_s=1.0, speed_min_mps=8.0,
                    speed_max_mps=12.0, lane_count=lane_count)
                self.assertEqual(len(rows), 12)
                self.assertTrue(all(any(abs(y - 3.3 * (lane + 0.5)) < 1e-9
                                        for lane in range(lane_count))
                                    for _, y, _ in rows))

    def test_two_lane_following_and_four_lane_visible_slot_fill(self):
        two = (1.65, 4.95)
        target = choose_formation_target(
            car(9, 100, 0), (car(1, 130, 1),), two,
            SimpleFormationMemory((), "CRUISE"), P)
        self.assertEqual(target.target_x_m, 115.0)

        four = (1.65, 4.95, 8.25, 11.55)
        decision = choose_layered_fill(
            car(9, 100, 3), (car(1, 130, 3), car(2, 115, 0)),
            four, P)
        self.assertEqual((decision.target_lane_index, decision.target_x_m),
                         (1, 130.0))

    def test_independent_detector_recognizes_ordered_two_and_four_lane_groups(self):
        for lane_count in (2, 4):
            with self.subTest(lane_count=lane_count):
                rows = {
                    f"v{lane}": state(0.0, 300.0 -
                                       (15.0 if (lane_count-1-lane) % 2 else 0.0),
                                       lane)
                    for lane in range(lane_count)
                }
                departures = {key: {"scheduled_departure_s": 0.0,
                                    "actual_departure_s": 0.0}
                              for key in rows}
                frames = [{"time_s": t, "states": {
                    key: {**row, "time_s": t} for key, row in rows.items()},
                    "departures": departures} for t in (0.0, 1.0)]
                result = detect_frames(
                    frames, lane_count=lane_count, formation_deadline_s=None,
                    hold_s=None, max_sample_gap_s=1.0)
                self.assertTrue(result["formation_success"], result["failure_reasons"])
                self.assertEqual(result["final_lane_counts"], [1] * lane_count)


if __name__ == "__main__":
    unittest.main()
