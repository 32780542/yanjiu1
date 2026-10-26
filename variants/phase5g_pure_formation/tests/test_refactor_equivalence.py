"""固定重构前的完整输出，检查规则与闭环数值是否保持一致。"""

from dataclasses import asdict
import hashlib
import json
import random
import unittest

from experiments import phase5g, phase5g_cases
from models.vehicle import VehicleState
from noa.controller import decide
from noa.simple_formation import SimpleFormationMemory
from perception.contracts import (
    ControlInput, EgoState, LocalObservation, NeighborDetection, RoadObservation,
)
from perception.road import VisibleRoad
from simulation.phase5g_clock import CLOCK_SCHEMA, Phase5GClock, initial_memory_hash


SIMPLE_PARAMETERS = {
    "simple_formation_component_gap_m": 50.0,
    "simple_formation_middle_offset_m": 15.0,
    "simple_formation_same_lane_gap_m": 30.0,
    "simple_formation_position_tolerance_m": 2.0,
    "simple_formation_speed_tolerance_mps": 1.0,
    "simple_formation_stable_time_s": 1.0,
    "simple_formation_reference_switch_gain_m": 2.0,
    "simple_formation_min_lane_change_speed_mps": 5.0,
    "simple_formation_target_lane_clearance_m": 8.0,
}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def local_decision_digest():
    _, _, parameters = phase5g.parameters(
        "lane_priority", 10.0, simple_rules=True, simple_overrides=SIMPLE_PARAMETERS)
    rng = random.Random(20261026)
    digest = hashlib.sha256()
    for index in range(600):
        lanes = 2 + index % 3
        lane = rng.randrange(lanes)
        speed = rng.uniform(5.0, 20.0)
        ego = EgoState(0.0, 100.0, 3.3 * (lane + 0.5), 0.0,
                       speed, 0.0, 0.0, 0.0, 0.0)
        neighbors = tuple(
            NeighborDetection(
                track, rng.uniform(-90.0, 180.0),
                3.3 * (rng.randrange(lanes) - lane),
                rng.uniform(5.0, 20.0) - speed, 0.0, 0.0, 4.0, 1.8, 0.0,
            )
            for track in range(1, 1 + rng.randrange(9))
        )
        road = RoadObservation(
            0.0, (((-100.0, -ego.y_m), (200.0, -ego.y_m)),
                  ((-100.0, 3.3 * lanes - ego.y_m),
                   (200.0, 3.3 * lanes - ego.y_m))),
            tuple(((-100.0, 3.3 * k - ego.y_m),
                   (200.0, 3.3 * k - ego.y_m)) for k in range(1, lanes)),
        )
        memory = SimpleFormationMemory((), "CRUISE")
        if neighbors and index % 4 == 0:
            memory = SimpleFormationMemory(
                (), "CRUISE", join_phase="JOINING",
                desired_lane_index=rng.randrange(lanes), join_anchor_track_id=1,
            )
        control = ControlInput(ego, LocalObservation(0.0, neighbors, road), memory)
        digest.update(encode(asdict(decide(control, parameters))))
    return digest.hexdigest()


def trajectory_digest(lanes, ticks):
    model, physical, policy = phase5g.parameters(
        "lane_priority", 10.0, simple_rules=True, simple_overrides=SIMPLE_PARAMETERS)
    case = phase5g_cases.demo_case(
        physical, 4 * lanes, 3, lane_count=lanes, straight_road=True,
        depart_interval_min_s=1.0, depart_interval_max_s=1.0)
    memories = phase5g._initial_memories(case, "lane_priority", simple_rules=True)
    clock = Phase5GClock(
        {key: VehicleState(**row) for key, row in case["initial"].items()},
        model, VisibleRoad.from_net(phase5g._road_network(case)), physical, policy,
        case["controlled"], case["scripts"], memories, clock_schema=CLOCK_SCHEMA,
        initial_memories_sha256=initial_memory_hash(memories),
        departures=case["departures"],
    )
    digest = hashlib.sha256()
    for _ in range(ticks):
        digest.update(encode(clock.tick()))
    return digest.hexdigest()


class RefactorEquivalenceTests(unittest.TestCase):
    def test_six_hundred_local_scenes_match_before_refactor(self):
        self.assertEqual(local_decision_digest(),
                         "bda53b882870ee158041b48d57c7d0e632651495de14b23a3716982cce24b6a8")

    def test_multilane_closed_loop_matches_before_refactor(self):
        expected = {
            2: "93448808f0f1e24c18f5a582880d75daee2fd05f1f1d33c3a42c0e4a4345130e",
            3: "deace94dcec17485716644473f90aec05afe342d69400db2ee88f4fdc7337632",
            4: "e68301a556cb988225c029fc74bae807cbf3a589f15a7362701ccbbb53d1f789",
        }
        for lanes, ticks in ((2, 200), (3, 450), (4, 600)):
            with self.subTest(lanes=lanes):
                self.assertEqual(trajectory_digest(lanes, ticks), expected[lanes])


if __name__ == "__main__":
    unittest.main()
