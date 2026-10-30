"""Local self-reports and direct, threshold-free state statistics."""

from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
from tempfile import TemporaryDirectory
import unittest
from archived_rules_source import load_state_enabled_base

from noa import native_rules as rules
from experiments import native_sumo as native


def car(track, x, lane=0, speed=28.8):
    return rules.Vehicle(track, x, (lane + 0.5) * rules.LANE_WIDTH, speed, lane)


class LocalFormationStateTests(unittest.TestCase):
    def state(self, ego, others=(), mode="transform", drop=None):
        command, _ = rules.decide(ego, others, rules.Memory(), mode, drop)
        self.assertIs(type(command.formation_state), int)
        return command.formation_state

    def test_isolated_vehicle_has_no_relation(self):
        self.assertEqual(self.state(car(0, 100)), 0)

    def test_actual_following_relation_counts_during_adjustment(self):
        self.assertEqual(self.state(car(0, 100), (car(1, 145, speed=25),)), 1)

    def test_leading_vehicle_counts_its_visible_following_chain(self):
        self.assertEqual(self.state(car(0, 100), (car(1, 60),)), 1)

    def test_exactly_aligned_heads_still_report_one(self):
        self.assertEqual(self.state(car(0, 100), (car(1, 85, lane=1),)), 1)

    def test_other_lane_body_is_not_a_mutually_selected_head(self):
        self.assertEqual(self.state(car(0, 90), (car(1, 100, 1), car(2, 145, 1))), 0)

    def test_distant_front_and_rear_do_not_extend_the_relation(self):
        self.assertEqual(self.state(car(0, 100), (car(1, 150.01), car(2, 49.99))), 0)

    def test_noa_does_not_report_formation_even_in_perfect_geometry(self):
        self.assertEqual(self.state(car(0, 100), (car(1, 130), car(2, 85, 1)), "noa"), 0)

    def test_relation_disappearance_resets_without_a_waiting_timer(self):
        ego = car(0, 100)
        command, memory = rules.decide(ego, (car(1, 130),), rules.Memory(), "formation", None)
        self.assertEqual(command.formation_state, 1)
        command, _ = rules.decide(ego, (), memory, "formation", None)
        self.assertEqual(command.formation_state, 0)

    def test_switching_to_noa_clears_the_self_report(self):
        ego, front = car(0, 100), car(1, 130)
        command, memory = rules.decide(ego, (front,), rules.Memory(), "formation", None)
        self.assertEqual(command.formation_state, 1)
        command, _ = rules.decide(ego, (front,), memory, "noa", None)
        self.assertEqual(command.formation_state, 0)


class FormationStateStatisticsTests(unittest.TestCase):
    def test_direct_vehicle_time_and_continuous_one_episodes(self):
        stats = native.FormationStateStats()
        for time, flags in [
            (0, {"a": 1, "b": 0}),
            (1, {"a": 1, "b": 1}),
            (3, {"a": 0, "b": 1}),
            (4, {}),
        ]:
            stats.update(time, flags)
        summary = stats.summary()
        self.assertEqual(summary["vehicle_seconds"], 8)
        self.assertEqual(summary["participating_vehicle_seconds"], 6)
        self.assertEqual(summary["participation_rate"], 0.75)
        self.assertEqual(summary["mean_participants"], 1.5)
        self.assertEqual(summary["peak_participants"], 2)
        self.assertEqual(summary["episodes"], 2)
        self.assertEqual(summary["mean_episode_s"], 3)
        self.assertEqual(summary["max_episode_s"], 3)

    def test_last_frame_is_not_extrapolated_and_snapshot_is_read_only(self):
        stats = native.FormationStateStats()
        stats.update(0, {"a": 1})
        stats.update(2, {"a": 1})
        first = stats.summary()
        self.assertEqual(stats.summary(), first)
        self.assertEqual(first["participating_vehicle_seconds"], 2)
        self.assertEqual(first["mean_episode_s"], 2)
        stats.update(3, {"a": 0})
        stats.update(5, {"a": 1})
        stats.update(6, {})
        summary = stats.summary()
        self.assertEqual(summary["episodes"], 2)
        self.assertEqual(summary["mean_episode_s"], 2)
        self.assertEqual(summary["max_episode_s"], 3)

    def test_zero_is_distinguished_from_absent_vehicle_time(self):
        stats = native.FormationStateStats()
        self.assertIsNone(stats.summary()["participation_rate"])
        stats.update(0, {"a": 0})
        stats.update(1, {})
        summary = stats.summary()
        self.assertEqual(summary["participation_rate"], 0)
        self.assertIsNone(summary["mean_episode_s"])

    def test_invalid_bit_and_backward_time_are_rejected(self):
        stats = native.FormationStateStats()
        with self.assertRaises(ValueError):
            stats.update(0, {"a": 2})
        stats.update(1, {"a": 1})
        with self.assertRaises(ValueError):
            stats.update(0.5, {"a": 1})


class StateOnlyChangeTests(unittest.TestCase):
    def test_control_and_memory_match_frozen_P_across_local_states(self):
        """Keep the published state-only change tied to its original controller."""
        archived = load_state_enabled_base("state_only_P")
        def archived_car(track, x, lane=0, speed=28.8):
            return archived.Vehicle(track, x, (lane + 0.5) * archived.LANE_WIDTH, speed, lane)

        path = (
            Path(__file__).resolve().parents[3]
            / "docs/experiments/2026-10-29-four-flow-attribution/portable_P/source/noa/native_rules.py"
        )
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864",
        )
        spec = importlib.util.spec_from_file_location("state_output_P_reference", path)
        old = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = old
        spec.loader.exec_module(old)
        rng = random.Random(20261029)
        for mode in ("noa", "formation", "transform"):
            for _ in range(300):
                ego = archived_car(0, rng.uniform(0, 1200), rng.randrange(3), rng.uniform(0, 33.3))
                rows = tuple(
                    archived_car(i + 1, ego.x + rng.uniform(-120, 220),
                                 rng.randrange(3), rng.uniform(0, 33.3))
                    for i in range(7)
                )
                memory = archived.Memory(
                    lane_target=rng.choice((None, 0, 1, 2)),
                    gap=rng.choice((None, (1, 2))),
                    joining=rng.choice((True, False)),
                )
                boundary = rng.choice((None, 1000.0))
                actual, after = archived.decide(ego, rows, memory, mode, boundary)
                expected, old_after = old.decide(
                    old.Vehicle(**asdict(ego)),
                    tuple(old.Vehicle(**asdict(c)) for c in rows),
                    old.Memory(**asdict(memory)),
                    mode,
                    boundary,
                )
                control = asdict(actual)
                control.pop("formation_state")
                self.assertEqual(control, asdict(expected))
                self.assertEqual(asdict(after), asdict(old_after))

    def test_real_sumo_records_every_local_state_without_exposing_it_to_neighbors(self):
        initial = [
            dict(id="front", depart=0, lane=0, x=130, speed=28.8),
            dict(id="back", depart=0, lane=0, x=100, speed=28.8),
        ]
        with TemporaryDirectory() as tmp:
            path = native.run_case(
                mode="formation",
                scenario="straight3",
                initial=initial,
                duration=3.0,
                max_time=3.0,
                output_base=tmp,
                diagnostic=True,
            )
            with gzip.open(path / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
                frames = [json.loads(line) for line in stream]
            result = json.loads((path / "result.json").read_bytes())
            self.assertEqual(len(frames), 30)
            self.assertTrue(all(f["formation_states"] == {"front": 1, "back": 1} for f in frames))
            self.assertEqual(result["formation_state"]["participation_rate"], 1)
            self.assertEqual(result["formation_state"]["peak_participants"], 2)
            with gzip.open(path / "diagnostic.jsonl.gz", "rt", encoding="utf-8") as stream:
                self.assertTrue(
                    all(
                        a["formation_state"] == 1
                        for line in stream
                        for a in json.loads(line)["actions"].values()
                    )
                )
        self.assertNotIn("formation_state", rules.Vehicle.__dataclass_fields__)


if __name__ == "__main__":
    unittest.main()
