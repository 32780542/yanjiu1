"""Own submitted lane requests survive native response latency without intent sharing."""

from dataclasses import replace
from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import native_sumo as native
from noa import native_rules as rules


# Recorded E3 seed1/q500 frames: own request1->2 at372.2, first motion372.4.
# Immutable numeric fixture; tests do not depend on a local results directory.
REAL_FRAMES = {
    float(time_s): frame
    for time_s, frame in json.loads(
        (ROOT / "tests/fixtures/own_lane_request_race.json").read_text(encoding="utf-8")
    ).items()
}


class OwnLaneExecutionTests(unittest.TestCase):
    def frame(self, time_s):
        row = REAL_FRAMES[time_s]
        return rules.Vehicle(**row["ego"]), tuple(rules.Vehicle(**x) for x in row["neighbors"])

    def pending(self, ego, attempt):
        self.assertTrue(hasattr(native, "active_lane_request"), "missing own actuation lifecycle")
        state = native.PhysicalState(ego.x, ego.y, ego.speed, ego.lane, ego.vy, ego.acceleration, ego.time)
        return native.active_lane_request(state, attempt, ego.time)

    def with_pending(self, ego, pending):
        self.assertIn("pending_lane", rules.Vehicle.__dataclass_fields__, "missing own feedback field")
        return replace(ego, pending_lane=pending)

    def test_real_submitted_request_survives_centered_response_and_then_merges(self):
        ego, rows = self.frame(372.2)
        command, memory = rules.decide(ego, rows, rules.Memory(), "transform")
        self.assertEqual(command.lane, 2)
        self.assertTrue(native.lane_request_is_safe(ego, rows, command.lane))
        attempt = (command.lane, ego.time)
        for time_s in (372.3, 372.4, 372.8, 373.3):
            with self.subTest(time_s=time_s):
                ego, rows = self.frame(time_s)
                pending = self.pending(ego, attempt)
                self.assertEqual(pending, 2)
                ego = self.with_pending(ego, pending)
                command, memory = rules.decide(ego, rows, memory, "transform")
                self.assertEqual(memory.lane_target, 2)
                self.assertEqual(command.lane, 2)
        ego, rows = self.frame(373.4)
        self.assertTrue(native.lane_change_is_complete(ego, 2))
        self.assertIsNone(self.pending(ego, attempt))
        command, memory = rules.decide(self.with_pending(ego, None), rows, memory, "transform")
        self.assertEqual((command.reason, command.lane, memory.lane_target), ("merge", 1, 1))

    def test_settled_nonadjacent_helper_memory_cannot_block_necessary_merge(self):
        ego, rows = self.frame(373.4)
        stale = rules.Memory(lane_target=0, gap=(4, 1), joining=True)
        command, memory = rules.decide(ego, rows, stale, "transform")
        self.assertEqual((command.reason, command.lane, memory.lane_target), ("merge", 1, 1))

    def test_submitted_target_corrects_stale_helper_before_native_motion(self):
        ego, rows = self.frame(372.3)
        ego = self.with_pending(ego, 2)
        command, memory = rules.decide(ego, rows, rules.Memory(lane_target=0), "transform")
        self.assertEqual((command.lane, memory.lane_target), (2, 2))

    def test_pending_target_waits_for_strict_completion_not_loose_rule_tolerance(self):
        ego = self.with_pending(rules.Vehicle(0, 700.0, 8.18, 25.0, 2, 0.08), 2)
        self.assertFalse(native.lane_change_is_complete(ego, 2))
        command, memory = rules.decide(ego, (), rules.Memory(lane_target=2), "transform")
        self.assertEqual((command.reason, command.lane, memory.lane_target), ("executing", 2, 2))

    def test_actual_lateral_motion_survives_request_timeout(self):
        ego = rules.Vehicle(0, 700.0, 6.6, 25.0, 1, 3.3, time=5.0)
        self.assertEqual(self.pending(ego, (2, 1.0)), 2)
        paused = replace(ego, vy=0.0)
        self.assertEqual(self.pending(paused, (2, 1.0)), 2)

    def test_completed_request_releases_before_its_time_window_ends(self):
        ego = rules.Vehicle(0, 700.0, 8.25, 25.0, 2, time=1.1)
        self.assertIsNone(self.pending(ego, (2, 1.0)))

    def test_expired_unstarted_request_releases_without_claiming_completion(self):
        ego = rules.Vehicle(0, 700.0, 4.95, 25.0, 1, time=2.3)
        self.assertFalse(native.lane_change_is_complete(ego, 2))
        self.assertIsNone(self.pending(ego, (2, 1.0)))
        self.assertEqual(self.pending(replace(ego, time=1.1), (2, 1.0)), 2)
        self.assertIsNone(self.pending(ego, None))

    def test_only_ego_receives_pending_and_neighbor_reobservation_stays_physical(self):
        states = {"self": native.PhysicalState(640.0, 4.95, 28.8, 1),
                  "other": native.PhysicalState(660.0, 8.25, 28.8, 2)}
        tracks = native.LocalTracks()
        ego, neighbors = tracks.observe("self", states)
        ego = self.with_pending(ego, 2)
        self.assertEqual(ego.pending_lane, 2)
        self.assertTrue(all(car.pending_lane is None for car in neighbors))
        other_ego, other_neighbors = tracks.observe("other", states)
        self.assertIsNone(other_ego.pending_lane)
        self.assertTrue(all(car.pending_lane is None for car in other_neighbors))

    def test_noa_also_keeps_own_submitted_target_during_response_latency(self):
        ego = self.with_pending(rules.Vehicle(0, 640.0, 4.95, 28.8, 1), 2)
        command, memory = rules.decide(ego, (), rules.Memory(lane_target=2), "noa")
        self.assertEqual((command.reason, command.lane, memory.lane_target), ("executing", 2, 2))

    def test_native_adapter_reports_own_request_without_neighbor_intent(self):
        observed = []
        original = rules.decide

        def inspect(ego, neighbors, memory, **kwargs):
            observed.append((ego.time, ego.lane, ego.vy, getattr(ego, "pending_lane", None),
                             tuple(getattr(car, "pending_lane", None) for car in neighbors)))
            return original(ego, neighbors, memory, **kwargs)

        with TemporaryDirectory() as tmp, patch.object(rules, "decide", side_effect=inspect):
            native.run_case(mode="transform", flow=0.0, duration=1.0, max_time=2.0,
                            output_base=tmp, initial=[
                                dict(id="ending", depart=0.0, lane=2, x=700.0, speed=28.8),
                                dict(id="middle", depart=0.0, lane=1, x=730.0, speed=28.8),
                                dict(id="left", depart=0.0, lane=0, x=680.0, speed=28.8)])
        self.assertTrue(observed)
        self.assertTrue(any(pending == 1 and lane == 2
                            for _, lane, vy, pending, _ in observed),
                        "native adapter must report this car's submitted request")
        self.assertTrue(any(others for *_, others in observed))
        self.assertTrue(all(value is None for *_, others in observed for value in others))


if __name__ == "__main__":
    unittest.main()
