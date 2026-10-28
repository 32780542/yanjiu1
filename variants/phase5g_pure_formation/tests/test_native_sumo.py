"""Native SUMO demand, local observations and physical execution contracts."""

from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import random
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class LocalVehicle:
    track: int
    x: float
    y: float
    speed: float
    lane: int
    vy: float = 0.0
    acceleration: float = 0.0
    time: float = 0.0


class NativeDemandTests(unittest.TestCase):
    def test_lane_completion_uses_center_and_stopped_lateral_motion(self):
        from experiments import native_sumo as native

        self.assertTrue(hasattr(native, "lane_change_is_complete"))
        self.assertFalse(native.lane_change_is_complete(native.PhysicalState(700.0, 6.6, 28.8, 1, -3.3), 1))
        self.assertFalse(native.lane_change_is_complete(native.PhysicalState(710.0, 4.95, 28.8, 1, -0.1), 1))
        self.assertFalse(native.lane_change_is_complete(native.PhysicalState(710.0, 8.25, 28.8, 2), 1))
        self.assertTrue(native.lane_change_is_complete(native.PhysicalState(715.0, 4.95, 28.8, 1), 1))

    def test_unfinished_cohort_exposes_only_explicit_completed_subset_means(self):
        from experiments.native_sumo import _summary

        trips = [
            dict(requested_s=0.0, entered_s=1.0, exited_s=11.0, distance_m=1200.0, fuel_mg=1000.0),
            dict(requested_s=0.0, entered_s=2.0, exited_s=None, distance_m=500.0, fuel_mg=500.0),
        ]
        result = _summary(trips, 20.0, 10.0)
        self.assertIn("status", result, "the runner must distinguish time limits from drained runs")
        self.assertEqual(result["status"], "time_limit")
        self.assertFalse(result["all_completed"])
        self.assertTrue(result["safe"])
        self.assertFalse(result["performance_comparison_eligible"])
        self.assertIsNone(result["mean_travel_time_s"])
        self.assertIsNone(result["mean_system_time_s"])
        self.assertIsNone(result["fuel_g_per_km"])
        self.assertEqual(result["completed_subset_mean_travel_time_s"], 10.0)

    def test_recorded_collision_and_incomplete_noa_cannot_be_reported_as_completed(self):
        from experiments.native_sumo import _summary

        index = ROOT.parents[1] / "tmp/native_probe_v1_summary.json"
        if not index.is_file():
            self.skipTest("local recorded counterexamples are not distributed with source")
        rows = json.loads(index.read_text(encoding="utf-8"))
        selected = [
            r
            for r in rows
            if r["result"]["collisions"] or r["result"]["completed"] < r["result"]["requested"]
        ]
        self.assertTrue(selected)
        for row in selected:
            old = row["result"]
            trips = json.loads((Path(row["path"]) / "trips.json").read_text(encoding="utf-8"))
            summary = _summary(trips, old["actual_end_s"], old["demand_duration_s"])
            self.assertIn("status", summary)
            summary = _summary(
                trips,
                old["actual_end_s"],
                old["demand_duration_s"],
                collisions=old["collisions"],
                teleports=old["teleports"],
            )
            self.assertEqual(summary["status"], "unsafe" if old["collisions"] else "time_limit")
            self.assertFalse(summary["performance_comparison_eligible"])
            self.assertIsNone(summary["mean_travel_time_s"])

    def test_native_runner_module_exists(self):
        self.assertTrue(
            (ROOT / "experiments/native_sumo.py").is_file(), "native SUMO runner has not been implemented"
        )

    def test_independent_bernoulli_streams_exactly_use_1250_probability(self):
        from experiments.native_sumo import arrival_tape

        rows = arrival_tape(seed=7, flow=1250.0, duration=100.0)
        expected = []
        streams = [random.Random(f"continuous-arrival:7:{lane}") for lane in range(3)]
        for tick in range(1000):
            for lane in range(3):
                if streams[lane].random() < 1250 * 0.1 / 3600:
                    expected.append((tick / 10, lane))
        self.assertEqual([(r["requested_s"], r["lane"]) for r in rows], expected)
        self.assertEqual(rows, arrival_tape(seed=7, flow=1250.0, duration=100.0))
        self.assertTrue(all(r["x"] == 0.0 and r["speed"] == 28.8 for r in rows))
        self.assertEqual(len({r["vehicle_id"] for r in rows}), len(rows))

    def test_zero_flow_and_invalid_time_are_explicit(self):
        from experiments.native_sumo import arrival_tape

        self.assertEqual(arrival_tape(seed=1, flow=0.0, duration=1.0), [])
        for args in ({"flow": -1.0}, {"flow": 36001.0}, {"duration": 0.15}):
            with self.assertRaises(ValueError):
                arrival_tape(**dict(seed=1, flow=1250.0, duration=1.0, **{}) | args)

    def test_local_observations_are_clipped_and_use_private_tracks(self):
        from experiments.native_sumo import LocalTracks, PhysicalState

        states = {
            "ego": PhysicalState(300.0, 4.95, 20.0, 1, 0.4, -1.0, 2.0),
            "behind": PhysicalState(200.0, 1.65, 21.0, 0),
            "ahead": PhysicalState(500.0, 8.25, 22.0, 2),
            "far_back": PhysicalState(199.99, 4.95, 10.0, 1),
            "far_front": PhysicalState(500.01, 4.95, 10.0, 1),
        }
        tracks = LocalTracks(vehicle_type=LocalVehicle)
        ego, neighbors = tracks.observe("ego", states)
        self.assertEqual(ego.track, 0)
        self.assertEqual((ego.y, ego.vy, ego.acceleration, ego.time), (4.95, 0.4, -1.0, 2.0))
        self.assertEqual({v.x for v in neighbors}, {200.0, 500.0})
        self.assertEqual(len({v.track for v in neighbors}), 2)
        self.assertTrue(all(isinstance(v.track, int) and v.track > 0 for v in neighbors))
        self.assertFalse(any(hasattr(v, "vehicle_id") for v in (ego,) + neighbors))
        labels = {v.x: v.track for v in neighbors}
        _, again = tracks.observe("ego", states)
        self.assertEqual({v.x: v.track for v in again}, labels)
        other_ego, _ = tracks.observe("ahead", states)
        self.assertEqual(other_ego.track, 0)
        self.assertIsNot(tracks.tracks["ego"], tracks.tracks["ahead"])

    def test_routes_submit_every_request_without_a_python_entry_gate(self):
        from experiments.native_sumo import write_routes

        requests = [
            {"vehicle_id": "a", "requested_s": 0.0, "lane": 1, "x": 0.0, "speed": 28.8},
            {"vehicle_id": "b", "requested_s": 0.1, "lane": 1, "x": 0.0, "speed": 28.8},
        ]
        with TemporaryDirectory() as tmp:
            path = write_routes(Path(tmp), requests)
            root = ET.parse(path).getroot()
        vehicles = root.findall("vehicle")
        self.assertEqual(
            [(v.get("depart"), v.get("departPos")) for v in vehicles], [("0.0", "0.0"), ("0.1", "0.0")]
        )
        model = root.find("vType").attrib
        for key, value in {
            "length": "4.0",
            "minGap": "1.5",
            "tau": "0.2",
            "accel": "5.0",
            "decel": "10.0",
            "emergencyDecel": "30.0",
            "maxSpeed": "33.3",
            "speedFactor": "1.0",
            "speedDev": "0.0",
            "sigma": "0.0",
            "carFollowModel": "IDM",
        }.items():
            self.assertEqual(model[key], value)

    def test_generated_network_really_drops_lane_two_at_1000m(self):
        from experiments.native_sumo import build_network

        with TemporaryDirectory() as tmp:
            net = ET.parse(build_network(Path(tmp), "lane_drop")).getroot()
            edges = {e.get("id"): e for e in net.findall("edge") if not e.get("id").startswith(":")}
            self.assertEqual(len(edges["upstream"].findall("lane")), 3)
            self.assertEqual(len(edges["downstream"].findall("lane")), 2)
            links = {(c.get("fromLane"), c.get("toLane")) for c in net.findall("connection")}
            self.assertEqual(links, {("0", "0"), ("1", "1")})
            for name, count, length, start in (
                ("upstream", 3, 1000.0, 0.0),
                ("downstream", 2, 200.0, 1000.0),
            ):
                for lane in edges[name].findall("lane"):
                    self.assertEqual(float(lane.get("length")), length)
                    points = [tuple(map(float, p.split(","))) for p in lane.get("shape").split()]
                    self.assertAlmostEqual(points[0][0], start)
                    self.assertAlmostEqual(points[-1][0], start + length)
                    self.assertAlmostEqual(points[0][1], 1.65 + 3.3 * int(lane.get("index")))

    def test_straight_network_preserves_all_three_lanes(self):
        from experiments.native_sumo import build_network

        with TemporaryDirectory() as tmp:
            net = ET.parse(build_network(Path(tmp), "straight3")).getroot()
        downstream = next(e for e in net.findall("edge") if e.get("id") == "downstream")
        self.assertEqual(len(downstream.findall("lane")), 3)
        self.assertEqual({c.get("fromLane") for c in net.findall("connection")}, {"0", "1", "2"})

    def test_common_lane_execution_guard_uses_current_physical_neighborhood(self):
        from experiments.native_sumo import lane_request_is_safe, PhysicalState

        ego = PhysicalState(100.0, 8.25, 28.8, 2)
        self.assertTrue(lane_request_is_safe(ego, (PhysicalState(108.0, 4.95, 28.8, 1),), 1))
        self.assertFalse(lane_request_is_safe(ego, (PhysicalState(107.99, 4.95, 28.8, 1),), 1))
        self.assertFalse(lane_request_is_safe(ego, (), 0))
        self.assertFalse(lane_request_is_safe(ego, (PhysicalState(100.0, 6.55, 28.8, 2),), 1))


class NativeIntegrationTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "noa/native_rules.py").is_file(), "main agent is implementing native rules")
    def test_failed_simulation_preserves_original_error_and_partial_accounting(self):
        from experiments import native_sumo as native

        real_traci = native.lock_traci()

        class BrokenConnection:
            def getVersion(self):
                return 0, "test interrupted SUMO"

            def simulationStep(self):
                raise RuntimeError("original step failure")

            def close(self):
                raise RuntimeError("secondary close failure")

        class BrokenTraci:
            constants = real_traci.constants

            def start(self, command, **unused):
                path = Path(command[command.index("--tripinfo-output") + 1])
                path.write_text("<tripinfos><tripinfo", encoding="utf-8")

            def getConnection(self, unused):
                return BrokenConnection()

        with (
            TemporaryDirectory() as tmp,
            patch.object(native, "lock_traci", return_value=BrokenTraci()),
            patch.object(native, "build_network", return_value=Path(tmp) / "unused.net.xml"),
        ):
            with self.assertRaisesRegex(RuntimeError, "^original step failure$"):
                native.run_case(
                    mode="noa",
                    flow=0.0,
                    duration=1.0,
                    max_time=1.0,
                    output_base=tmp,
                    initial=[dict(id="not_departed", depart=0.0, lane=0)],
                )
            directory = next(Path(tmp).iterdir())
            result = json.loads((directory / "result.json").read_text())
            self.assertEqual(result["status"], "error")
            self.assertIn("original step failure", result["error"])
            self.assertIn("secondary close failure", result["cleanup_error"])
            self.assertIsNotNone(result["tripinfo_error"])
            self.assertEqual((result["departed"], result["completed"]), (0, 0))
            self.assertTrue((directory / "trips.json").is_file())

    def test_first_collision_or_teleport_stops_and_saves_the_current_frame(self):
        from experiments import native_sumo as native

        tc = native.lock_traci().constants
        for kind in ("collision", "teleport"):
            with self.subTest(kind=kind), TemporaryDirectory() as tmp:

                class ReplayConnection:
                    steps = 0

                    def __init__(self):
                        self.simulation = SimpleNamespace(
                            getTime=lambda: self.steps * 0.1,
                            getDepartedIDList=lambda: (),
                            getArrivedIDList=lambda: (),
                            getCollisions=lambda: (
                                (
                                    SimpleNamespace(
                                        collider="a",
                                        victim="b",
                                        colliderSpeed=6.0,
                                        victimSpeed=0.2,
                                        type="collision",
                                        lane="upstream_2",
                                        pos=996.18,
                                    ),
                                )
                                if kind == "collision"
                                else ()
                            ),
                            getStartingTeleportIDList=lambda: ("a",) if kind == "teleport" else (),
                            getMinExpectedNumber=lambda: 1,
                        )
                        self.vehicle = SimpleNamespace(getAllSubscriptionResults=lambda: {})

                    def getVersion(self):
                        return 0, "test replay"

                    def simulationStep(self):
                        self.steps += 1

                    def close(self):
                        pass

                conn = ReplayConnection()

                class ReplayTraci:
                    constants = tc

                    def start(self, command, **unused):
                        Path(command[command.index("--tripinfo-output") + 1]).write_text("<tripinfos/>")

                    def getConnection(self, unused):
                        return conn

                with (
                    patch.object(native, "lock_traci", return_value=ReplayTraci()),
                    patch.object(native, "build_network", return_value=Path(tmp) / "unused.net.xml"),
                ):
                    directory = native.run_case(
                        mode="noa", flow=0.0, duration=1.0, max_time=1.0, output_base=tmp, diagnostic=True
                    )
                self.assertEqual(
                    conn.steps, 1, "unsafe events must not be replayed for hundreds of later steps"
                )
                result = json.loads((directory / "result.json").read_text())
                self.assertEqual(result["status"], "unsafe")
                self.assertFalse(result["safe"])
                self.assertFalse(result["performance_comparison_eligible"])
                with gzip.open(directory / "positions.jsonl.gz", "rt") as stream:
                    frames = [json.loads(line) for line in stream]
                self.assertEqual(frames[-1]["time_s"], 0.1)

    def test_global_strategy_uses_full_state_and_local_execution_safety(self):
        from experiments import native_sumo as native
        from experiments.global_reference import GlobalPlanner

        self.assertIn("global", native.MODES)
        original_observe, original_commands = native.LocalTracks.observe, GlobalPlanner.commands
        with (
            TemporaryDirectory() as tmp,
            patch.object(
                native.LocalTracks, "observe", autospec=True, side_effect=original_observe
            ) as observations,
            patch.object(GlobalPlanner, "commands", autospec=True, side_effect=original_commands) as planning,
        ):
            directory = native.run_case(
                mode="global",
                flow=0.0,
                duration=1.0,
                max_time=2.0,
                output_base=tmp,
                initial=[
                    dict(id="global_one", depart=0.0, lane=1, x=600.0, speed=28.8),
                    dict(id="global_far", depart=0.0, lane=0, x=100.0, speed=28.8),
                ],
            )
            result = json.loads((directory / "result.json").read_text())
            self.assertTrue(observations.called)
            self.assertTrue(planning.called)
            self.assertEqual(set(planning.call_args_list[0].args[1]), {"global_one", "global_far"})
            self.assertEqual(result["status"], "time_limit")
            self.assertTrue(result["safe"])
            self.assertIn("experiments/global_reference.py", result["source_sha256"])
            self.assertFalse(result["reference_is_full_paper_reproduction"])
            self.assertEqual(result["observation_scope"], "privileged full physical state")

    def test_all_modes_apply_the_same_public_safe_speed_to_execution(self):
        from experiments import native_sumo as native
        from noa import native_rules

        for mode in native.MODES:
            with (
                self.subTest(mode=mode),
                TemporaryDirectory() as tmp,
                patch.object(native_rules, "safe_speed", return_value=7.0) as common_guard,
            ):
                directory = native.run_case(
                    mode=mode,
                    flow=0.0,
                    duration=1.0,
                    max_time=0.1,
                    output_base=tmp,
                    initial=[dict(id="guarded", depart=0.0, lane=1, x=600.0, speed=28.8)],
                    diagnostic=True,
                )
                self.assertTrue(common_guard.called)
                with gzip.open(directory / "diagnostic.jsonl.gz", "rt") as stream:
                    action = json.loads(next(stream))["actions"]["guarded"]
                self.assertIn("safe_speed_cap_mps", action)
                self.assertEqual(action["safe_speed_cap_mps"], 7.0)
                self.assertLessEqual(action["speed"], 7.0)

    def test_actual_lane_completion_is_later_than_lane_index_flip(self):
        from experiments import native_sumo as native
        from noa import native_rules

        def change(ego, neighbors, memory, **unused):
            return native_rules.Command(28.8, 1, "test_physical_change"), memory

        with TemporaryDirectory() as tmp, patch.object(native_rules, "decide", side_effect=change):
            directory = native.run_case(
                mode="noa",
                flow=0.0,
                duration=1.0,
                max_time=2.0,
                output_base=tmp,
                initial=[dict(id="changing", depart=0.0, lane=2, x=600.0, speed=28.8)],
                diagnostic=True,
            )
            trip = json.loads((directory / "trips.json").read_text())[0]
            self.assertIn("lane_completion_events", trip)
            self.assertEqual(len(trip["lane_completion_events"]), 1)
            midpoint, complete = trip["lane_events"][0], trip["lane_completion_events"][0]
            self.assertGreater(complete["time_s"], midpoint["time_s"])
            self.assertGreater(complete["x"], midpoint["x"])
            self.assertAlmostEqual(complete["y"], 4.95)
            self.assertAlmostEqual(complete["vy"], 0.0)
            result = json.loads((directory / "result.json").read_text())
            self.assertEqual(result["ending_lane_completion_before_drop_rate"], 1.0)

    @unittest.skipUnless((ROOT / "noa/native_rules.py").is_file(), "main agent is implementing native rules")
    def test_ten_second_native_smoke_keeps_every_request_and_records_physics(self):
        from experiments.native_sumo import run_case

        initial = [
            {"depart": 0.0, "lane": 0, "x": 0.0, "speed": 28.8, "id": "first"},
            {"depart": 0.1, "lane": 0, "x": 0.0, "speed": 28.8, "id": "second"},
        ]
        with TemporaryDirectory() as tmp:
            directory = run_case(
                mode="noa",
                seed=1,
                flow=0.0,
                duration=10.0,
                scenario="lane_drop",
                output_base=tmp,
                max_time=10.0,
                initial=initial,
                diagnostic=True,
            )
            result = json.loads((directory / "result.json").read_text())
            trips = json.loads((directory / "trips.json").read_text())
            with gzip.open(directory / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
                positions = [json.loads(line) for line in stream]
            self.assertEqual(result["requested"], 2)
            self.assertEqual(result["departed"], 2)
            self.assertEqual(result["collisions"], 0)
            self.assertEqual(result["teleports"], 0)
            self.assertEqual(result["onroad_final"], 2)
            self.assertEqual(len(positions), 100)
            self.assertEqual(positions[-1]["time_s"], 10.0)
            self.assertTrue(
                all(abs(b["time_s"] - a["time_s"] - 0.1) < 1e-8 for a, b in zip(positions, positions[1:]))
            )
            inputs = json.loads((directory / "input.json").read_text())
            self.assertEqual(inputs["positions_step_s"], 0.1)
            self.assertTrue(
                all(t["speed_factor"] == 1.0 and t["speed_factor_tripinfo"] == 1.0 for t in trips)
            )
            self.assertGreater(trips[1]["entered_s"], trips[1]["requested_s"])
            self.assertGreater(sum(t["fuel_mg"] for t in trips), 0.0)
            self.assertTrue(all(v[0] >= 0.0 for row in positions for v in row["states"].values()))
            self.assertIn("source_sha256", result)
            self.assertIn("1.27.1", result["sumo_version"])


if __name__ == "__main__":
    unittest.main()
