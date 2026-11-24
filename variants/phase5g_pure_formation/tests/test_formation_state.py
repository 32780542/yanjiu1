"""Actual selected relations and direct, threshold-free state statistics."""

from dataclasses import asdict, replace
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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

    def test_actual_cross_lane_body_relation_counts_without_a_head_flag(self):
        ego = car(0, 90)
        body, front = car(1, 100, 1), car(2, 145, 1)
        self.assertEqual(rules._front_following(body, (ego, front))[2], front.track)
        self.assertEqual(self.state(ego, (body, front)), 1)

    def test_selected_forward_cth_reference_counts_beyond_the_near_phase_graph(self):
        for x in (150., 150.01, 300.):
            with self.subTest(front_x=x):
                command, memory = rules.decide(
                    car(0, 100), (car(1, x),), rules.Memory(front=9), 'transform', None)
                self.assertEqual(command.reference, 1)
                self.assertEqual(memory.front, 1)
                self.assertEqual(command.formation_state, 1)
        self.assertEqual(self.state(car(0, 100), (car(1, 300.01),)), 0)
        self.assertEqual(self.state(car(0, 100), (car(1, 49.99),)), 0)
        self.assertEqual(self.state(car(0, 100), (car(1, 50),)), 1)

    def test_selected_real_slot_anchor_counts_without_a_same_lane_or_phase_front(self):
        ego, anchor = car(0, 900, lane=1), car(1, 960, lane=0)
        for pending in (None, 0):
            with self.subTest(own_pending=pending):
                command, memory = rules.decide(
                    replace(ego, pending_lane=pending), (anchor,),
                    rules.Memory(lane_target=0, front=anchor.track), 'transform', 1000.)
                self.assertEqual(command.lane, 0)
                self.assertEqual(command.reference, anchor.track)
                self.assertAlmostEqual(command.target_x, 930.02)
                self.assertAlmostEqual(command.speed, 30.6012)
                self.assertEqual(memory, rules.Memory(lane_target=0, front=anchor.track))
                self.assertEqual(command.formation_state, 1)

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


class InstalledStateRecordingTests(unittest.TestCase):
    def archived_cases(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/c8_before_state_reporting.json').read_text())
        return {row['name']: row for row in fixture['cases']}

    def archived_command(self, row):
        return rules.decide(
            rules.Vehicle(**row['ego']), tuple(rules.Vehicle(**c) for c in row['neighbors']),
            rules.Memory(**row['memory']), row['mode'], row['drop_x'])

    def test_archived_C8_noa_and_real_slot_controls_and_memory_remain_unchanged(self):
        cases = self.archived_cases()
        for name in ('noa_visible_remote_front', 'left_real_slot'):
            row = cases[name]
            with self.subTest(case=row['name']):
                command, after = self.archived_command(row)
                control = asdict(command)
                state = control.pop('formation_state')
                self.assertEqual(control, row['control'])
                self.assertEqual(asdict(after), row['after'])
                self.assertEqual(state, 0 if row['mode'] == 'noa' else 1)

    def test_archived_C8_near_following_keeps_control_but_now_remembers_its_reference(self):
        row = self.archived_cases()['ordinary_following']
        command, after = self.archived_command(row)
        control = asdict(command)
        self.assertEqual(control.pop('formation_state'), 1)
        self.assertEqual(control, row['control'])
        self.assertIsNone(row['after']['front'])
        self.assertEqual(after, rules.Memory(front=command.reference))
        self.assertEqual(after.front, 1)

    def test_archived_C8_fresh_far_inputs_now_need_a_previously_established_chain(self):
        cases = self.archived_cases()
        for name, phase_speed in (('stopped_far_front', 0.), ('slow_far_front_with_phase', -1.1625)):
            row = cases[name]
            with self.subTest(case=name):
                command, after = self.archived_command(row)
                ego = rules.Vehicle(**row['ego'])
                self.assertIsNone(command.reference)
                self.assertEqual(after, rules.Memory())
                self.assertAlmostEqual(command.target_x, ego.x + phase_speed / .3)
                self.assertAlmostEqual(command.speed, .2 * (28.8 + phase_speed))
                self.assertEqual(command.formation_state, int(name == 'slow_far_front_with_phase'))
                # Preserve the historical behavior as evidence of the intentional method change.
                self.assertEqual(row['control']['reference'], 1)
                self.assertNotEqual(command.speed, row['control']['speed'])

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
