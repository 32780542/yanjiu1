from copy import deepcopy
import unittest

from experiments.phase5_detection import detect_frames
from experiments.phase5g import _SpeedAccumulator


LANE_Y = (1.65, 4.95, 8.25)


def state(x_m, lane, speed=10.0):
    return {
        "time_s": 0.0,
        "x_m": float(x_m),
        "y_m": LANE_Y[lane],
        "heading_rad": 0.0,
        "vx_mps": float(speed),
        "vy_mps": 0.0,
        "yaw_rate_radps": 0.0,
        "steering_rad": 0.0,
    }


def formation(count, *, origin=300.0, speed=10.0, prefix="v"):
    rows = {}
    for ordinal in range(count):
        cycle, phase = divmod(ordinal, 3)
        lane = (2, 0, 1)[phase]
        x_m = origin - 30.0 * cycle - (15.0 if phase == 2 else 0.0)
        rows[f"{prefix}{ordinal}"] = state(x_m, lane, speed)
    return rows


def departure_rows(count, actual=0.0, *, prefix="v"):
    return {
        f"{prefix}{ordinal}": {
            "scheduled_departure_s": float(
                ordinal if actual is None or actual >= ordinal else actual
            ),
            "actual_departure_s": actual,
        }
        for ordinal in range(count)
    }


def frame(time_s, states, departures=None, join_diagnostics=None, **facts):
    copied = deepcopy(states)
    for row in copied.values():
        row["time_s"] = float(time_s)
    result = {"time_s": float(time_s), "states": copied}
    if departures is not None:
        result["departures"] = deepcopy(departures)
    if join_diagnostics is not None:
        result["join_diagnostics"] = deepcopy(join_diagnostics)
    result.update(facts)
    return result


class DynamicComponentDetectorTests(unittest.TestCase):
    def test_trace_accumulator_forwards_dynamic_facts_to_offline_detector(self):
        initial = formation(2)
        departures = departure_rows(2, None)
        departures["v0"]["actual_departure_s"] = 0.0
        for ordinal, key in enumerate(("v0", "v1")):
            departures[key].update(
                physical_ordinal=ordinal,
                state=deepcopy(initial[key]),
            )
        record = {
            "initial": {"v0": deepcopy(initial["v0"])},
            "steps": {"v0": {
                "samples": [deepcopy(initial["v0"])],
                "final": deepcopy(initial["v0"]),
            }},
            "decisions": {"v0": {"diagnostics": {"simple_formation": {
                "join_phase": "JOINING", "final_desired_lane_index": 2,
            }}}},
            "departures": departures,
            "readback": {"v0": {"teleport_starts": 1}},
        }
        accumulator = _SpeedAccumulator({"controlled": ["v0", "v1"]})

        accumulator.consume(record)

        evidence = accumulator.frames[0]
        self.assertEqual(evidence["departures"], departures)
        self.assertEqual(evidence["join_diagnostics"]["v0"]["join_phase"], "JOINING")
        self.assertEqual(evidence["teleport_starts"], 1)
        detection = detect_frames(accumulator.frames, persistence_s=1.0)
        self.assertEqual(detection["cohort_members"], ["v0", "v1"])
        self.assertNotIn("member_missing", detection["failure_reasons"])

    def test_future_actors_are_not_missing_before_their_actual_departure(self):
        rows = departure_rows(3, None)
        rows["v0"]["actual_departure_s"] = 0.0
        at_zero = frame(0.0, {"v0": formation(3)["v0"]}, rows)
        rows["v1"]["actual_departure_s"] = 5.0
        at_five = frame(5.0, {key: formation(3)[key] for key in ("v0", "v1")}, rows)
        rows["v2"]["actual_departure_s"] = 10.0
        at_ten = frame(10.0, formation(3), rows)

        result = detect_frames([at_zero, at_five, at_ten], persistence_s=1.0)

        early = [row for row in result["component_history"] if row["time_s"] < 10.0]
        self.assertTrue(early)
        self.assertNotIn("member_missing", {
            reason
            for row in early
            for component in row["components"]
            for reason in component["failure_reasons"]
        })
        self.assertEqual(result["scheduled_departures"], {
            "v0": 0.0, "v1": 1.0, "v2": 2.0,
        })
        self.assertEqual(result["actual_departures"], {
            "v0": 0.0, "v1": 5.0, "v2": 10.0,
        })

    def test_components_join_at_50_metres_and_split_above_50(self):
        joined = {
            "a": state(100.0, 2), "b": state(50.0, 0), "c": state(0.0, 1),
        }
        split = deepcopy(joined)
        split["c"]["x_m"] = -0.01

        joined_result = detect_frames([frame(0.0, joined)], persistence_s=1.0)
        split_result = detect_frames([frame(0.0, split)], persistence_s=1.0)

        self.assertEqual(
            [row["members"] for row in joined_result["component_history"][0]["components"]],
            [["a", "b", "c"]],
        )
        self.assertEqual(
            [row["members"] for row in split_result["component_history"][0]["components"]],
            [["a", "b"], ["c"]],
        )

    def test_approved_lane_distributions_for_all_supported_counts(self):
        expected = {
            3: [1, 1, 1], 4: [1, 1, 2], 5: [2, 1, 2],
            6: [2, 2, 2], 7: [2, 2, 3], 8: [3, 2, 3],
            12: [4, 4, 4],
        }
        for count, counts in expected.items():
            with self.subTest(count=count):
                result = detect_frames(
                    [frame(0.0, formation(count), departure_rows(count))],
                    persistence_s=1.0,
                )
                component = result["component_history"][0]["components"][0]
                self.assertEqual(component["lane_counts"], counts)
                self.assertNotIn("lane_distribution_invalid", component["failure_reasons"])

    def test_physical_geometry_and_speed_boundaries_are_inclusive(self):
        rows = formation(6)
        rows["v1"]["x_m"] += 2.0
        rows["v2"]["x_m"] -= 2.0
        rows["v3"]["x_m"] -= 2.0
        rows["v5"]["x_m"] -= 2.0
        rows["v5"]["vx_mps"] = 11.0
        result = detect_frames(
            [frame(0.0, rows, departure_rows(6))], persistence_s=1.0,
        )
        component = result["component_history"][0]["components"][0]
        self.assertEqual(component["failure_reasons"], [])
        self.assertLessEqual(component["max_outer_alignment_error_m"], 2.0)
        self.assertLessEqual(component["max_middle_offset_error_m"], 2.0)
        self.assertLessEqual(component["max_same_lane_gap_error_m"], 2.0)
        self.assertEqual(component["speed_spread_mps"], 1.0)

    def test_each_geometric_or_speed_excess_has_a_specific_reason(self):
        mutations = {
            "outer_alignment_error_exceeded": ("v1", "x_m", 2.01),
            "middle_offset_error_exceeded": ("v2", "x_m", -2.01),
            "same_lane_gap_error_exceeded": ("v3", "x_m", -2.01),
            "speed_spread_exceeded": ("v5", "vx_mps", 1.01),
        }
        for reason, (actor, field, delta) in mutations.items():
            with self.subTest(reason=reason):
                rows = formation(6)
                rows[actor][field] += delta
                result = detect_frames(
                    [frame(0.0, rows, departure_rows(6))], persistence_s=1.0,
                )
                component = result["component_history"][0]["components"][0]
                self.assertIn(reason, component["failure_reasons"])

    def test_deadline_uses_last_actual_departure_and_hold_is_continuous(self):
        departures = departure_rows(3, 100.0)
        frames = [frame(time_s, formation(3), departures)
                  for time_s in range(120, 133)]
        result = detect_frames(frames, persistence_s=1.0)
        self.assertTrue(result["whole_cohort_success"])
        self.assertEqual(result["last_actual_departure_s"], 100.0)
        self.assertEqual(result["formed_time_s"], 121.0)
        self.assertEqual(result["held_time_s"], 131.0)

        late = [frame(time_s, formation(3), departures)
                for time_s in range(131, 144)]
        late_result = detect_frames(late, persistence_s=1.0)
        self.assertFalse(late_result["whole_cohort_success"])
        self.assertIn("formation_deadline_missed", late_result["failure_reasons"])

        broken = [frame(time_s, formation(3), departures)
                  for time_s in range(120, 131) if time_s != 125]
        broken_result = detect_frames(broken, persistence_s=1.0)
        self.assertFalse(broken_result["whole_cohort_success"])
        self.assertIn("hold_after_confirmation_too_short", broken_result["failure_reasons"])

    def test_conflicting_admission_is_scoped_to_one_component(self):
        rows = formation(6)
        diagnostics = {
            "v4": {"join_phase": "JOINING", "final_desired_lane_index": 0},
            "v5": {"join_phase": "STABILIZING", "final_desired_lane_index": 1},
        }
        result = detect_frames([
            frame(0.0, rows, departure_rows(6), diagnostics),
        ], persistence_s=1.0)
        self.assertEqual(len(result["admission_conflicts"]), 1)
        self.assertIn("simultaneous_admission_conflict", result["failure_reasons"])

        independent = {
            **formation(3, origin=300.0, prefix="a"),
            **formation(3, origin=100.0, prefix="b"),
        }
        independent_diagnostics = {
            "a2": {"join_phase": "JOINING"},
            "b2": {"join_phase": "JOINING"},
        }
        result = detect_frames([
            frame(0.0, independent, departure_rows(3, prefix="a") |
                  departure_rows(3, prefix="b"), independent_diagnostics),
        ], persistence_s=1.0)
        self.assertEqual(result["admission_conflicts"], [])

    def test_empty_partial_missing_collision_road_teleport_and_jump_fail_explicitly(self):
        empty = detect_frames([], persistence_s=1.0)
        self.assertIn("empty_recording", empty["failure_reasons"])

        partial_departures = departure_rows(3, 0.0)
        partial_departures["v2"]["actual_departure_s"] = None
        partial = detect_frames([
            frame(0.0, {key: formation(3)[key] for key in ("v0", "v1")},
                  partial_departures),
        ], persistence_s=1.0)
        self.assertIn("partial_departure_cohort", partial["failure_reasons"])

        missing = detect_frames([
            frame(0.0, formation(3), departure_rows(3)),
            frame(1.0, {key: formation(3)[key] for key in ("v0", "v1")},
                  departure_rows(3)),
        ], persistence_s=1.0)
        self.assertIn("member_missing", missing["failure_reasons"])

        collided_rows = formation(3)
        collided_rows["v1"] = deepcopy(collided_rows["v0"])
        collided_rows["v1"]["y_m"] = collided_rows["v0"]["y_m"]
        collided = detect_frames([
            frame(0.0, collided_rows, departure_rows(3)),
        ], persistence_s=1.0)
        self.assertIn("collision_detected", collided["failure_reasons"])

        outside_rows = formation(3)
        outside_rows["v1"]["y_m"] = 20.0
        outside = detect_frames([
            frame(0.0, outside_rows, departure_rows(3)),
        ], persistence_s=1.0)
        self.assertIn("road_departure_detected", outside["failure_reasons"])

        teleported = detect_frames([
            frame(0.0, formation(3), departure_rows(3), teleport_starts=1),
        ], persistence_s=1.0)
        self.assertIn("teleport_detected", teleported["failure_reasons"])

        jumped = deepcopy(formation(3))
        jumped["v0"]["x_m"] += 100.0
        jump = detect_frames([
            frame(0.0, formation(3), departure_rows(3)),
            frame(1.0, jumped, departure_rows(3)),
        ], persistence_s=1.0)
        self.assertIn("nonphysical_jump_detected", jump["failure_reasons"])


if __name__ == "__main__":
    unittest.main()
