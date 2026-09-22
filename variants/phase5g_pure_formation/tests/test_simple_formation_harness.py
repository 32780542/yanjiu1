"""Task 3 contracts for the replayable non-formal simple-formation demo."""

from copy import deepcopy
from dataclasses import asdict, fields
import importlib
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
import uuid
from types import MappingProxyType
from unittest.mock import patch

from experiments import phase5g_cases
from models.bezier import QuadraticLaneChange
from noa.simple_formation import PARAMETERS, SimpleFormationMemory


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_TEMP_ROOT = Path(tempfile.gettempdir())

SIMPLE_DEFAULTS = {
    "simple_formation_local_range_m": 90.0,
    "simple_formation_adjacent_gap_m": 15.0,
    "simple_formation_same_gap_m": 30.0,
    "simple_formation_position_tolerance_m": 2.0,
    "simple_formation_accel_limit_mps2": 0.5,
    "simple_formation_max_lane_changes": 1,
}
SIMPLE_NONDEFAULTS = {
    "simple_formation_local_range_m": 78.0,
    "simple_formation_adjacent_gap_m": 14.0,
    "simple_formation_same_gap_m": 28.0,
    "simple_formation_position_tolerance_m": 1.5,
    "simple_formation_accel_limit_mps2": 0.4,
    "simple_formation_max_lane_changes": 1,
}
DYNAMIC_SIMPLE_DEFAULTS = {
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
EXPECTED_MODES = {
    "off": {"formation_enabled": False, "formation_lane_change_enabled": False},
    "longitudinal": {"formation_enabled": True, "formation_lane_change_enabled": False},
    "lane_priority": {"formation_enabled": True, "formation_lane_change_enabled": True},
}
MAIN_SIX_EXPECTED = (
    ("v0", 100.0, 1.65, 10.0),
    ("v1", 145.0, 1.65, 9.5),
    ("v2", 190.0, 1.65, 10.5),
    ("v3", 122.0, 4.95, 10.5),
    ("v4", 167.0, 4.95, 9.5),
    ("v5", 108.0, 8.25, 10.0),
)


def make_directory_reparse(link, target):
    if os.name == "nt":
        subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def mutable_ids(value):
    """Collect every recursively reachable mutable container identity."""
    if isinstance(value, dict):
        result = {id(value)}
        for item in value.values():
            result.update(mutable_ids(item))
        return result
    if isinstance(value, (list, set, bytearray)):
        result = {id(value)}
        for item in value:
            result.update(mutable_ids(item))
        return result
    if isinstance(value, tuple):
        result = set()
        for item in value:
            result.update(mutable_ids(item))
        return result
    return set()


def add_first_line_json_whitespace(path):
    path = Path(path)
    payload = path.read_bytes()
    line_end = payload.find(b"\n")
    if line_end < 0:
        raise AssertionError("trace fixture lacks a complete line")
    if line_end and payload[line_end - 1:line_end] == b"\r":
        line_end -= 1
    path.write_bytes(payload[:line_end] + b" " + payload[line_end:])


class GeneratedBoundedTrace:
    """Re-openable JSONL index stream with unique per-record memory payloads."""

    def __init__(self, template, *, intervals=48,
                 retained_test_bytes=24 * 1024 * 1024):
        self.template = deepcopy(template)
        self.intervals = intervals
        self.retained_test_bytes = retained_test_bytes
        self.record_payload_bytes = (
            retained_test_bytes + intervals - 1) // intervals
        self.scan_bytes = []
        self.original_loads = json.loads

    def open(self, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if mode not in ("r", "rt", "rb"):
            raise AssertionError(f"unexpected generated trace mode: {args[0]}")
        owner = self
        scan = len(self.scan_bytes)
        self.scan_bytes.append(0)

        class Stream:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def __iter__(self):
                for index in range(owner.intervals):
                    line = json.dumps({"generated_index": index}) + "\n"
                    owner.scan_bytes[scan] += owner.record_payload_bytes
                    yield line.encode("utf-8") if "b" in mode else line

        return Stream()

    def read_text(self, *args, **kwargs):
        raise AssertionError("trace.jsonl must not be read wholesale")

    def loads(self, payload, *args, **kwargs):
        marker = self.original_loads(payload, *args, **kwargs)
        if not isinstance(marker, dict) or set(marker) != {"generated_index"}:
            return marker
        index = marker["generated_index"]
        row = deepcopy(self.template)
        base_time = next(iter(row["initial"].values()))["time_s"]
        offset = index * 0.1 - base_time
        for state in row["initial"].values():
            state["time_s"] += offset
        for step in row["steps"].values():
            step["initial"]["time_s"] += offset
            for state in step["samples"]:
                state["time_s"] += offset
            step["final"]["time_s"] += offset
        # Unique mutable storage makes any accidental list(records) exceed the
        # scaled test threshold while the stream releases one row at a time.
        row["synthetic_record_payload"] = bytearray(self.record_payload_bytes)
        return row


class SimpleFormationHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = importlib.import_module("experiments.phase5g")
        cls.replay = importlib.import_module("experiments.phase5g_replay")
        cls.entry = importlib.import_module("run")

    def short_case(self, physical, *, count=3, seed=101, duration_s=0.1):
        case = phase5g_cases.seeded_case(physical, count, seed)
        return {**case, "duration_s": duration_s}

    def simple_parameters(self, overrides=None):
        resolved = SIMPLE_NONDEFAULTS if overrides is None else overrides
        return self.harness.parameters(
            "lane_priority", 10.0,
            simple_rules=True, simple_overrides=resolved,
        )

    def dynamic_parameters(self):
        return self.harness.parameters(
            "lane_priority", 10.0,
            simple_rules=True, simple_overrides=DYNAMIC_SIMPLE_DEFAULTS,
        )

    def exact_dynamic_case(self, physical, *, duration_s=3.1):
        case = phase5g_cases.seeded_case(physical, 3, 101)
        scheduled = (0.0, 2.5, 3.0)
        for ordinal, actor in enumerate(case["controlled"]):
            row = case["departures"][actor]
            row["scheduled_departure_s"] = scheduled[ordinal]
            row["actual_departure_s"] = None
            row["state"].update(
                x_m=100.0,
                y_m=phase5g_cases.LANE_CENTERS_M[ordinal],
                vx_mps=10.0,
                vy_mps=0.0,
                time_s=0.0,
            )
        first = case["controlled"][0]
        return {
            **case,
            "duration_s": duration_s,
            "initial": {first: deepcopy(case["departures"][first]["state"])},
        }

    def dynamic_trace_rows(self, root):
        model, physical, policy = self.dynamic_parameters()
        case = self.exact_dynamic_case(physical)
        source = Path(root) / "dynamic-validator-source"
        result = self.harness.run_variant(
            source, model, physical, policy, case, "lane_priority", live=False,
        )
        self.assertEqual(result["status"], "completed", result)
        rows = [
            json.loads(line)
            for line in (source / "trace.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        return case, rows

    def assert_dynamic_rows_rejected(self, root, case, rows):
        trace = Path(root) / f"malicious-{uuid.uuid4().hex}.jsonl"
        trace.write_text(
            "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        records = self.harness._PhysicalTraceRecords(
            trace, case["controlled"], live=False, expected_sha256=None,
        )
        with self.assertRaises(ValueError):
            list(records)

    def call_cli(self, argv):
        with patch.object(sys, "argv", ["run.py", *argv]):
            return self.entry.main()

    def make_short_demo(self, base, *, seed=11, count=3):
        return self.harness.run_phase5g_demo(
            vehicle_count=count, seed=seed, target_speed_mps=10.0,
            duration_s=0.1, output_base=base, live=False,
            local_formation_range_m=78.0,
            adjacent_lane_gap_m=14.0,
            same_lane_gap_m=28.0,
            position_tolerance_m=1.5,
            formation_accel_limit_mps2=0.4,
            max_formation_lane_changes=1,
        )

    def copy_demo_with_anchor(self, source, parent):
        destination = Path(parent) / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        original = source.parent / ".phase5g-trust" / f"{source.name}.json"
        copied = destination.parent / ".phase5g-trust" / f"{destination.name}.json"
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, copied)
        original_completion = original.with_name(f"{source.name}.completion.json")
        if original_completion.is_file():
            shutil.copy2(
                original_completion,
                copied.with_name(f"{destination.name}.completion.json"),
            )
        return destination

    def test_standard_review_temp_root_supports_snapshot_and_replay(self):
        review_root = (
            SYSTEM_TEMP_ROOT / f"phase5g-review-{uuid.uuid4()}"
        )
        output = (
            review_root / "variants" / "phase5g_pure_formation" / "tmp" / "demos"
        )
        try:
            source = self.make_short_demo(output)
            report = self.replay.replay_run(
                source, base=review_root / "replays"
            )
            self.assertTrue(report["passed"], report)
        finally:
            shutil.rmtree(
                self.harness.native_io_path(review_root), ignore_errors=True
            )

    def test_dynamic_trace_and_replay_preserve_activation_decisions_and_records(self):
        model, physical, policy = self.dynamic_parameters()
        case = self.exact_dynamic_case(physical)
        actors = tuple(case["controlled"])
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "dynamic-trace"
            result = self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            rows = [
                json.loads(line)
                for line in (source / "trace.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            replay = self.replay.replay_variant(source, require_manifest=False)

        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(len(rows), 31)
        actor_sets = [tuple(row["active_actors"]) for row in rows]
        self.assertTrue(all(
            set(before).issubset(after)
            for before, after in zip(actor_sets, actor_sets[1:])
        ))
        for row in rows:
            time_s = next(iter(row["initial"].values()))["time_s"]
            expected = actors[:1] if time_s < 2.5 - 1e-9 else (
                actors[:2] if time_s < 3.0 - 1e-9 else actors
            )
            self.assertEqual(tuple(row["active_actors"]), expected)
            self.assertEqual(set(row["inputs"]), set(expected))
            self.assertEqual(set(row["decisions"]), set(expected))
            for pending in set(actors) - set(expected):
                self.assertNotIn(pending, row["inputs"])
                self.assertNotIn(pending, row["decisions"])
        self.assertAlmostEqual(
            rows[-1]["departures"][actors[1]]["actual_departure_s"], 2.5,
        )
        self.assertAlmostEqual(
            rows[-1]["departures"][actors[2]]["actual_departure_s"], 3.0,
        )
        self.assertTrue(replay["passed"], replay)
        self.assertTrue(replay["decision_replay_passed"], replay)
        self.assertTrue(replay["integration_replay_passed"], replay)

    def test_dynamic_replay_restores_activation_before_a_failed_tick_boundary(self):
        model, physical, policy = self.dynamic_parameters()
        case = self.exact_dynamic_case(physical)
        original = type(model).advance
        calls = 0

        def fail_first_due_interval(instance, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 26:
                raise RuntimeError("injected dynamic integration boundary")
            return original(instance, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "dynamic-failed-boundary"
            with patch.object(type(model), "advance", fail_first_due_interval):
                result = self.harness.run_variant(
                    source, model, physical, policy, case,
                    "lane_priority", live=False,
                )
            rows = [
                json.loads(line)
                for line in (source / "trace.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            metadata = json.loads(
                (source / "metadata.json").read_text(encoding="utf-8")
            )
            replay = self.replay.replay_variant(source, require_manifest=False)

        actors = tuple(case["controlled"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(metadata["failure_stage"], "integration")
        self.assertEqual(metadata["failure_actor"], actors[0])
        self.assertEqual(rows[-1]["status"], "failed")
        self.assertEqual(tuple(rows[-1]["active_actors"]), actors[:2])
        self.assertAlmostEqual(
            rows[-1]["departures"][actors[1]]["actual_departure_s"], 2.5,
        )
        self.assertTrue(replay["passed"], replay)
        self.assertTrue(replay["partial_source"], replay)
        self.assertEqual(replay["trace"]["intervals"], len(rows))

    def test_demo_case_selection_uses_dynamic_offline_and_keeps_fixed_live_history(self):
        _, physical, _ = self.dynamic_parameters()
        offline = self.harness._demo_case(
            physical, vehicle_count=6, seed=101, duration_s=45.0, live=False,
        )
        live = self.harness._demo_case(
            physical, vehicle_count=6, seed=101, duration_s=45.0, live=True,
        )
        self.assertIn("departures", offline)
        self.assertEqual(len(offline["initial"]), 1)
        self.assertEqual(offline["name"], "seeded_6_seed101")
        self.assertNotIn("departures", live)
        self.assertEqual(live["name"], "main_6_3_2_1")
        self.assertEqual(set(live["initial"]), set(live["controlled"]))
        with self.assertRaisesRegex(ValueError, "fixed six-actor"):
            self.harness._demo_case(
                physical, vehicle_count=3, seed=101,
                duration_s=45.0, live=True,
            )

    def test_dynamic_record_rejects_pending_actor_declared_active_before_schedule(self):
        with tempfile.TemporaryDirectory() as temp:
            case, rows = self.dynamic_trace_rows(temp)
            actors = tuple(case["controlled"])
            malicious = deepcopy(rows[:1])
            row = malicious[0]
            row["active_actors"] = list(actors[:2])
            for field in (
                "initial", "inputs", "decisions", "actions", "steps", "diagnostics",
            ):
                row[field][actors[1]] = deepcopy(row[field][actors[0]])
            self.assert_dynamic_rows_rejected(temp, case, malicious)

    def test_dynamic_completed_record_rejects_pending_or_unknown_actor_maps(self):
        with tempfile.TemporaryDirectory() as temp:
            case, rows = self.dynamic_trace_rows(temp)
            actor = case["controlled"][0]
            pending = case["controlled"][1]
            for field in ("inputs", "decisions", "actions", "steps", "diagnostics"):
                for intruder in (pending, "evil"):
                    with self.subTest(field=field, intruder=intruder):
                        malicious = deepcopy(rows)
                        malicious[0][field][intruder] = deepcopy(
                            malicious[0][field][actor]
                        )
                        self.assert_dynamic_rows_rejected(temp, case, malicious)

    def test_dynamic_record_rejects_rewritten_actual_departure(self):
        with tempfile.TemporaryDirectory() as temp:
            case, rows = self.dynamic_trace_rows(temp)
            actor = case["controlled"][1]
            activation = next(
                index for index, row in enumerate(rows)
                if row["departures"][actor]["actual_departure_s"] is not None
            )
            malicious = deepcopy(rows)
            malicious[activation + 1]["departures"][actor][
                "actual_departure_s"
            ] += 0.1
            self.assert_dynamic_rows_rejected(temp, case, malicious)

    def test_dynamic_case_rejects_a_late_trace_row_that_drops_dynamic_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            case, rows = self.dynamic_trace_rows(temp)
            model, physical, _ = self.dynamic_parameters()
            malicious = deepcopy(rows)
            malicious[-1].pop("active_actors")
            malicious[-1].pop("departures")
            trace = Path(temp) / "dynamic-switches-to-legacy.jsonl"
            trace.write_text(
                "".join(json.dumps(row, allow_nan=False) + "\n" for row in malicious),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "dynamic trace"):
                self.harness.evaluate_trace(
                    trace, case, model, physical, live=False,
                )

    def test_legacy_fixed_trace_without_dynamic_fields_is_still_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            case, rows = self.dynamic_trace_rows(temp)
            model, physical, _ = self.dynamic_parameters()
            row = deepcopy(rows[-1])
            row.pop("active_actors")
            row.pop("departures")
            trace = Path(temp) / "legacy-fixed.jsonl"
            trace.write_text(
                json.dumps(row, allow_nan=False) + "\n", encoding="utf-8",
            )
            legacy_case = deepcopy(case)
            legacy_case.pop("departures")
            legacy_case["initial"] = deepcopy(row["initial"])
            derived = self.harness.evaluate_trace(
                trace, legacy_case, model, physical, live=False,
            )
            self.assertIn("summary", derived)

    def test_trace_evaluation_matches_small_record_wrapper_without_whole_file_reads(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.2)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "stream-evaluation-source"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            trace_path = source / "trace.jsonl"
            with trace_path.open(encoding="utf-8") as stream:
                rows = [json.loads(line) for line in stream if line.strip()]
            expected = self.harness.evaluate_records(rows, case, model, physical)
            original_read_text = Path.read_text

            def reject_trace_read_text(candidate, *args, **kwargs):
                if Path(candidate).resolve() == trace_path.resolve():
                    raise AssertionError("trace.jsonl must not be read wholesale")
                return original_read_text(candidate, *args, **kwargs)

            with patch.object(Path, "read_text", new=reject_trace_read_text):
                actual = self.harness.evaluate_trace(
                    trace_path, case, model, physical, live=False,
                )
        self.assertEqual(actual, expected)

    def test_evaluate_trace_memory_does_not_retain_the_full_generated_input(self):
        """Scaled retention test; production 342.30 MiB is verified separately."""
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=12, duration_s=0.1)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "large-stream-template"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            with (source / "trace.jsonl").open(encoding="utf-8") as stream:
                template = json.loads(next(stream))
        generated = GeneratedBoundedTrace(template)
        tracemalloc.start()
        try:
            with patch.object(self.harness.json, "loads", new=generated.loads):
                derived = self.harness.evaluate_trace(
                    generated, case, model, physical, live=False,
                )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(
            derived["detection"]["default"]["frame_count"],
            generated.intervals + 1,
        )
        self.assertLessEqual(len(generated.scan_bytes), 3)
        self.assertTrue(generated.scan_bytes)
        self.assertGreaterEqual(min(generated.scan_bytes), generated.retained_test_bytes)
        self.assertLess(peak, 16 * 1024 * 1024, peak)
        print(json.dumps({
            "scaled_stream_input_bytes": generated.retained_test_bytes,
            "peak_tracemalloc_bytes": peak,
            "production_trace_reference_mib": 342.30,
            "scope": "bounded-retention regression; production size is extrapolated",
        }, sort_keys=True))

    def test_replay_trace_reads_are_bounded_and_never_use_read_text(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.2)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "stream-replay-source"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            trace_path = source / "trace.jsonl"
            original_read_text = Path.read_text
            original_open = Path.open
            scans = 0

            def reject_trace_read_text(candidate, *args, **kwargs):
                if Path(candidate).resolve() == trace_path.resolve():
                    raise AssertionError("trace.jsonl must not be read wholesale")
                return original_read_text(candidate, *args, **kwargs)

            def count_trace_open(candidate, *args, **kwargs):
                nonlocal scans
                if Path(candidate).resolve() == trace_path.resolve():
                    scans += 1
                return original_open(candidate, *args, **kwargs)

            with patch.object(Path, "read_text", new=reject_trace_read_text), \
                    patch.object(Path, "open", new=count_trace_open):
                tracemalloc.start()
                try:
                    report = self.replay.replay_variant(
                        source, require_manifest=False,
                    )
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
        self.assertTrue(report["passed"], report)
        self.assertLessEqual(scans, 4)
        self.assertLess(peak, 64 * 1024 * 1024, peak)

    def test_replay_reads_the_evidence_manifest_once(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.2)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "single-manifest-snapshot"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            manifest_path = (source / "evidence_hashes.json").resolve()
            original_open = Path.open
            manifest_reads = 0

            def count_manifest_reads(candidate, *args, **kwargs):
                nonlocal manifest_reads
                mode = args[0] if args else kwargs.get("mode", "r")
                if Path(candidate).resolve() == manifest_path and "r" in mode:
                    manifest_reads += 1
                return original_open(candidate, *args, **kwargs)

            with patch.object(Path, "open", new=count_manifest_reads):
                report = self.replay.replay_variant(source)
        self.assertTrue(report["passed"], report)
        self.assertEqual(manifest_reads, 1)

    def test_replay_cannot_inject_a_second_manifest_snapshot(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.2)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "between-manifest-read"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            manifest_path = (source / "evidence_hashes.json").resolve()
            original_open = Path.open
            manifest_reads = 0
            mutation_injected = False

            def mutate_on_second_manifest_read(candidate, *args, **kwargs):
                nonlocal manifest_reads, mutation_injected
                mode = args[0] if args else kwargs.get("mode", "r")
                if Path(candidate).resolve() == manifest_path and "r" in mode:
                    manifest_reads += 1
                    if manifest_reads == 2:
                        with original_open(manifest_path, encoding="utf-8") as reader:
                            hashes = json.load(reader)
                        hashes["trace.jsonl"] = "0" * 64
                        with original_open(manifest_path, "w", encoding="utf-8") as writer:
                            json.dump(hashes, writer, sort_keys=True)
                        mutation_injected = True
                return original_open(candidate, *args, **kwargs)

            with patch.object(Path, "open", new=mutate_on_second_manifest_read):
                report = self.replay.replay_variant(source)
        self.assertTrue(report["passed"], report)
        self.assertEqual(manifest_reads, 1)
        self.assertFalse(mutation_injected)

    def test_optional_manifest_still_binds_all_trace_scans_to_the_first(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.2)
        for manifest_state in ("absent", "invalid"):
            with self.subTest(manifest_state=manifest_state), \
                    tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / f"optional-manifest-{manifest_state}"
                self.harness.run_variant(
                    source, model, physical, policy, case, "lane_priority", live=False,
                )
                manifest_path = source / "evidence_hashes.json"
                if manifest_state == "absent":
                    manifest_path.unlink()
                else:
                    manifest_path.write_text("{", encoding="utf-8")
                trace_path = (source / "trace.jsonl").resolve()
                original_open = Path.open
                trace_reads = 0

                class MutateAfterClose:
                    def __init__(self, stream):
                        self.stream = stream

                    def __enter__(self):
                        self.stream.__enter__()
                        return self

                    def __exit__(self, *args):
                        result = self.stream.__exit__(*args)
                        with original_open(trace_path, "rb") as reader:
                            payload = reader.read()
                        line_end = payload.find(b"\n")
                        if line_end and payload[line_end - 1:line_end] == b"\r":
                            line_end -= 1
                        with original_open(trace_path, "wb") as writer:
                            writer.write(
                                payload[:line_end] + b" " + payload[line_end:])
                        return result

                    def __iter__(self):
                        return iter(self.stream)

                def mutate_after_first_trace_scan(candidate, *args, **kwargs):
                    nonlocal trace_reads
                    stream = original_open(candidate, *args, **kwargs)
                    mode = args[0] if args else kwargs.get("mode", "r")
                    if Path(candidate).resolve() == trace_path and "r" in mode:
                        trace_reads += 1
                        if trace_reads == 1:
                            return MutateAfterClose(stream)
                    return stream

                with patch.object(Path, "open", new=mutate_after_first_trace_scan):
                    report = self.replay.replay_variant(
                        source, require_manifest=False,
                    )
            self.assertFalse(report["passed"], report)
            self.assertGreaterEqual(trace_reads, 2)
            self.assertLessEqual(trace_reads, 4)
            error_text = "\n".join(report["errors"])
            self.assertIn("trace.jsonl", error_text)
            self.assertIn("sha256", error_text)

    def test_replay_rejects_json_whitespace_mutated_after_manifest_validation(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.2)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "post-manifest-whitespace"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            original = self.replay._manifest_differences

            def validate_then_mutate(path, *args, **kwargs):
                differences = original(path, *args, **kwargs)
                add_first_line_json_whitespace(Path(path) / "trace.jsonl")
                return differences

            with patch.object(
                self.replay, "_manifest_differences",
                side_effect=validate_then_mutate,
            ):
                report = self.replay.replay_variant(source)
        self.assertFalse(report["passed"], report)
        self.assertIn("trace.jsonl", "\n".join(report["errors"]))
        self.assertIn("sha256", "\n".join(report["errors"]))

    def test_replay_rejects_trace_mutation_between_streamed_scans(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.2)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "between-scan-whitespace"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            trace_path = (source / "trace.jsonl").resolve()
            original_open = Path.open
            trace_reads = 0

            class MutateAfterClose:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    self.stream.__enter__()
                    return self

                def __exit__(self, *args):
                    result = self.stream.__exit__(*args)
                    with original_open(trace_path, "rb") as reader:
                        payload = reader.read()
                    line_end = payload.find(b"\n")
                    if line_end and payload[line_end - 1:line_end] == b"\r":
                        line_end -= 1
                    with original_open(trace_path, "wb") as writer:
                        writer.write(
                            payload[:line_end] + b" " + payload[line_end:])
                    return result

                def __iter__(self):
                    return iter(self.stream)

            def mutate_after_first_trace_scan(candidate, *args, **kwargs):
                nonlocal trace_reads
                stream = original_open(candidate, *args, **kwargs)
                mode = args[0] if args else kwargs.get("mode", "r")
                if Path(candidate).resolve() == trace_path and "r" in mode:
                    trace_reads += 1
                    if trace_reads == 1:
                        return MutateAfterClose(stream)
                return stream

            with patch.object(Path, "open", new=mutate_after_first_trace_scan):
                report = self.replay.replay_variant(
                    source, require_manifest=False,
                )
        self.assertFalse(report["passed"], report)
        self.assertIn("trace.jsonl", "\n".join(report["errors"]))
        self.assertIn("sha256", "\n".join(report["errors"]))

    def test_committed_failed_tail_is_included_in_streamed_physical_evidence(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical, count=3, duration_s=0.1)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "failed-tail-template"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            with (source / "trace.jsonl").open(encoding="utf-8") as stream:
                row = json.loads(next(stream))
            row.update(status="failed", commit_applied=True)
            trace_path = Path(temp) / "failed-tail.jsonl"
            with trace_path.open("w", encoding="utf-8") as stream:
                stream.write(json.dumps(row, allow_nan=False) + "\n")
            expected = self.harness.evaluate_records([row], case, model, physical)
            actual = self.harness.evaluate_trace(
                trace_path, case, model, physical, live=True,
            )
        self.assertEqual(actual, expected)

    def test_generation_source_does_not_retain_written_trace_records(self):
        source = inspect.getsource(self.harness.run_variant)
        self.assertNotIn("records.append", source)
        evaluator = inspect.getsource(self.harness.evaluate_records)
        evaluator += inspect.getsource(self.harness._evaluate_record_source)
        self.assertNotIn("list(records)", evaluator)

    def test_frames_from_records_consumes_and_freezes_each_iterable_row_immediately(self):
        from experiments.phase5 import frames_from_records

        first = {"time_s": 0.0, "x_m": 1.0}
        second = {"time_s": 0.1, "x_m": 2.0}
        final = {"time_s": 0.2, "x_m": 3.0}

        def rows():
            yield {
                "status": "completed", "initial": {"v0": first},
                "steps": {"v0": {"final": second}},
            }
            first["x_m"] = 999.0
            yield {
                "status": "completed", "initial": {"v0": second},
                "steps": {"v0": {"final": final}},
            }

        frames = frames_from_records(rows())
        second["x_m"] = 888.0
        final["x_m"] = 777.0
        self.assertEqual(
            [frame["states"]["v0"]["x_m"] for frame in frames],
            [1.0, 2.0, 3.0],
        )

    def test_registered_simple_defaults_and_formal_modes_are_exact(self):
        registered = json.loads(
            (ROOT / "configs" / "phase5g.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {key: registered[key] for key in PARAMETERS}, SIMPLE_DEFAULTS,
        )
        self.assertIs(registered["simple_formation_enabled"], False)
        self.assertEqual(dict(self.harness.MODES), EXPECTED_MODES)
        self.assertEqual(tuple(self.harness.MODES), ("off", "longitudinal", "lane_priority"))

    def test_approved_simple_rules_bind_the_exact_unformed_main_six_input(self):
        _, physical, policy = self.harness.parameters(
            "lane_priority", 10.0,
            simple_rules=True, simple_overrides=SIMPLE_DEFAULTS,
        )
        self.assertEqual(
            {key: physical[key] for key in PARAMETERS}, SIMPLE_DEFAULTS,
        )
        self.assertEqual(
            {key: policy[key] for key in PARAMETERS}, SIMPLE_DEFAULTS,
        )
        self.assertIs(physical["simple_formation_enabled"], True)
        self.assertEqual(phase5g_cases.MAIN_SIX, MAIN_SIX_EXPECTED)

        case = phase5g_cases.main_six_case(physical)
        self.assertEqual(len(case["initial"]), 6)
        self.assertEqual(set(case["controlled"]), set(case["initial"]))
        self.assertEqual(case["scripts"], {})
        self.assertEqual(
            tuple(
                (key, state["x_m"], state["y_m"], state["vx_mps"])
                for key, state in case["initial"].items()
            ),
            MAIN_SIX_EXPECTED,
        )
        self.assertEqual(
            [
                sum(state["y_m"] == center for state in case["initial"].values())
                for center in phase5g_cases.LANE_CENTERS_M
            ],
            [3, 2, 1],
        )
        audit = phase5g_cases.validate_initial(case["initial"], physical)
        self.assertTrue(audit["passed"], audit)
        self.assertFalse(audit["detector"]["success"], audit["detector"])
        self.assertTrue(
            audit["detector"]["frames"][0]["fleet_failure_reasons"],
            audit["detector"],
        )

    def test_seeded_small_cases_contain_only_controlled_normal_vehicles(self):
        _, physical, _ = self.harness.parameters(
            "lane_priority", 10.0,
            simple_rules=True, simple_overrides=SIMPLE_DEFAULTS,
        )
        expected_lane_counts = {3: [1, 1, 1], 6: [3, 2, 1], 12: [4, 4, 4]}
        for count in (3, 6, 12):
            with self.subTest(count=count):
                case = phase5g_cases.seeded_case(physical, count, 1)
                self.assertEqual(len(case["initial"]), count)
                self.assertEqual(len(case["controlled"]), count)
                self.assertEqual(set(case["controlled"]), set(case["initial"]))
                self.assertEqual(case["scripts"], {})
                self.assertEqual(
                    [
                        sum(
                            state["y_m"] == center
                            for state in case["initial"].values()
                        )
                        for center in phase5g_cases.LANE_CENTERS_M
                    ],
                    expected_lane_counts[count],
                )
                audit = phase5g_cases.validate_initial(case["initial"], physical)
                self.assertTrue(audit["passed"], audit)

    def test_simple_parameters_change_only_switch_and_six_resolved_values(self):
        base_model, base_physical, base_policy = self.harness.parameters("lane_priority")
        model, physical, policy = self.simple_parameters()
        expected_differences = {
            "simple_formation_enabled",
            *(key for key in PARAMETERS
              if SIMPLE_NONDEFAULTS[key] != SIMPLE_DEFAULTS[key]),
        }
        self.assertEqual(dict(model.p), dict(base_model.p))
        self.assertEqual(
            {key for key in physical if physical[key] != base_physical[key]},
            expected_differences,
        )
        self.assertEqual(
            {key for key in policy if policy[key] != base_policy[key]},
            expected_differences,
        )
        self.assertIs(base_physical["simple_formation_enabled"], False)
        self.assertIs(base_policy["simple_formation_enabled"], False)
        self.assertIs(physical["simple_formation_enabled"], True)
        self.assertIs(policy["simple_formation_enabled"], True)
        self.assertIs(physical["r5_enabled"], False)
        self.assertIs(policy["r5_enabled"], False)
        self.assertEqual({key: physical[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)
        self.assertEqual({key: policy[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)

    def test_parameter_trees_share_no_mutable_identity_in_legacy_or_simple_mode(self):
        for simple_rules in (False, True):
            overrides = SIMPLE_NONDEFAULTS if simple_rules else None
            with self.subTest(simple_rules=simple_rules):
                model, physical, policy = self.harness.parameters(
                    "lane_priority", simple_rules=simple_rules,
                    simple_overrides=overrides,
                )
                physical_ids = mutable_ids(physical)
                policy_ids = mutable_ids(policy)
                model_ids = mutable_ids(dict(model.p))
                self.assertTrue(physical_ids.isdisjoint(policy_ids))
                self.assertTrue(physical_ids.isdisjoint(model_ids))
                self.assertTrue(policy_ids.isdisjoint(model_ids))

                policy_before = deepcopy(policy)
                model_before = deepcopy(dict(model.p))
                physical["formation_lane_duration_candidates_s"].append(12.5)
                self.assertEqual(policy, policy_before)
                self.assertEqual(dict(model.p), model_before)

                _, later_physical, later_policy = self.harness.parameters(
                    "lane_priority", simple_rules=simple_rules,
                    simple_overrides=overrides,
                )
                self.assertNotIn(
                    12.5, later_physical["formation_lane_duration_candidates_s"],
                )
                self.assertNotIn(
                    12.5, later_policy["formation_lane_duration_candidates_s"],
                )
                self.assertTrue(mutable_ids(later_physical).isdisjoint(
                    mutable_ids(later_policy)
                ))

    def test_parameters_require_exact_boolean_and_override_contract(self):
        for value in (None, 0, 1, "true", [], {}):
            if value is False:
                continue
            with self.subTest(simple_rules=value), self.assertRaisesRegex(
                ValueError, "simple_rules"
            ):
                self.harness.parameters(
                    "lane_priority", simple_rules=value,
                    simple_overrides=SIMPLE_NONDEFAULTS,
                )
        self.harness.parameters("lane_priority", simple_rules=False)
        self.harness.parameters(
            "lane_priority", simple_rules=False,
            simple_overrides=MappingProxyType({}),
        )
        with self.assertRaisesRegex(ValueError, "simple_overrides"):
            self.harness.parameters(
                "lane_priority", simple_rules=False,
                simple_overrides={"simple_formation_local_range_m": 90.0},
            )
        for invalid in (None, [], (), "mapping"):
            with self.subTest(overrides=invalid), self.assertRaisesRegex(
                ValueError, "simple_overrides"
            ):
                self.harness.parameters(
                    "lane_priority", simple_rules=True, simple_overrides=invalid,
                )
        self.simple_parameters(MappingProxyType(SIMPLE_NONDEFAULTS))

    def test_simple_overrides_reject_missing_extra_and_invalid_values(self):
        invalid = []
        missing = dict(SIMPLE_NONDEFAULTS)
        missing.pop("simple_formation_same_gap_m")
        invalid.append(missing)
        invalid.append({**SIMPLE_NONDEFAULTS, "extra": 1})
        for key in PARAMETERS[:-1]:
            for value in (True, 0, -1.0, float("nan"), float("inf")):
                invalid.append({**SIMPLE_NONDEFAULTS, key: value})
        for value in (True, 0, 2, 1.0, float("nan")):
            invalid.append({**SIMPLE_NONDEFAULTS,
                            "simple_formation_max_lane_changes": value})
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.harness.parameters(
                    "lane_priority", simple_rules=True,
                    simple_overrides=overrides,
                )

    def test_demo_writes_exact_simple_metadata_and_forwards_resolved_parameters(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(
            self.harness, "run_variant",
            return_value={"recording_passed": True},
        ) as run_variant:
            output = Path(temp) / "simple-demo"
            result = self.harness.run_phase5g_demo(
                vehicle_count=6, seed=7, target_speed_mps=9.5,
                duration_s=0.1, output_base=output, live=False,
                local_formation_range_m=78.0,
                adjacent_lane_gap_m=14.0,
                same_lane_gap_m=28.0,
                position_tolerance_m=1.5,
                formation_accel_limit_mps2=0.4,
                max_formation_lane_changes=1,
            )
            self.assertTrue(result.is_dir())
            metadata = json.loads((result / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["purpose"],
                             "Non-formal simple local if/else formation GUI source trace")
            self.assertEqual(metadata["schema"], "phase5g_simple_demo_v1")
            self.assertIs(metadata["formal"], False)
            self.assertEqual(metadata["mode"], "lane_priority")
            self.assertIs(metadata["simple_formation_enabled"], True)
            self.assertEqual(metadata["vehicle_count"], 6)
            self.assertEqual(metadata["seed"], 7)
            self.assertEqual(metadata["target_speed_mps"], 9.5)
            self.assertEqual(metadata["duration_s"], 0.1)
            self.assertEqual(metadata["simple_parameters"], SIMPLE_NONDEFAULTS)
            run_variant.assert_called_once()
            args = run_variant.call_args.args
            self.assertEqual(args[5], "lane_priority")
            physical, policy = args[2], args[3]
            self.assertIs(physical["simple_formation_enabled"], True)
            self.assertIs(policy["simple_formation_enabled"], True)
            self.assertEqual({key: physical[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)
            self.assertEqual({key: policy[key] for key in PARAMETERS}, SIMPLE_NONDEFAULTS)

    def test_demo_rejects_every_invalid_value_before_creating_result_base(self):
        valid = {
            "vehicle_count": 3, "seed": 1, "target_speed_mps": 10.0,
            "duration_s": 0.1, "live": False,
            "local_formation_range_m": 90.0,
            "adjacent_lane_gap_m": 15.0,
            "same_lane_gap_m": 30.0,
            "position_tolerance_m": 2.0,
            "formation_accel_limit_mps2": 0.5,
            "max_formation_lane_changes": 1,
        }
        invalid = [
            ("vehicle_count", True), ("vehicle_count", 5),
            ("seed", True), ("seed", -1),
            ("target_speed_mps", True), ("target_speed_mps", 0),
            ("target_speed_mps", float("nan")),
            ("duration_s", True), ("duration_s", 0),
            ("duration_s", float("inf")), ("duration_s", 0.15),
        ]
        for name in (
            "local_formation_range_m", "adjacent_lane_gap_m", "same_lane_gap_m",
            "position_tolerance_m", "formation_accel_limit_mps2",
        ):
            invalid.extend((name, value) for value in
                           (True, 0, -1.0, float("nan"), float("inf")))
        invalid.extend(("max_formation_lane_changes", value)
                       for value in (True, 0, 2, 1.0))
        with tempfile.TemporaryDirectory() as temp:
            for index, (name, value) in enumerate(invalid):
                output = Path(temp) / f"invalid-{index}"
                kwargs = {**valid, name: value, "output_base": output}
                with self.subTest(name=name, value=value), patch.object(
                    self.harness, "run_variant"
                ) as runner, self.assertRaises(ValueError):
                    self.harness.run_phase5g_demo(**kwargs)
                runner.assert_not_called()
                self.assertFalse(output.exists())

    def test_demo_creates_missing_safe_output_ancestry_after_validation(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(
            self.harness, "run_variant", return_value={"recording_passed": True},
        ):
            output = Path(temp) / "missing" / "nested" / "simple-demo"
            self.assertFalse(output.parent.exists())
            result = self.make_short_demo(output)
            self.assertTrue(output.is_dir())
            self.assertEqual(result.parent, output.resolve())
            self.assertTrue((output / "latest.json").is_file())

    def test_demo_rejects_unsafe_output_bases_before_any_write(self):
        outside = ROOT / "escaped-output-base-test"
        self.assertFalse(outside.exists())
        with patch.object(self.harness, "run_variant") as runner, \
                self.assertRaisesRegex(ValueError, "output_base"):
            self.make_short_demo(ROOT / "results" / ".." / outside.name)
        runner.assert_not_called()
        self.assertFalse(outside.exists())

        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            output_file = temp_root / "output-file"
            output_file.write_text("unchanged", encoding="utf-8")
            before = sorted(item.relative_to(temp_root).as_posix()
                            for item in temp_root.rglob("*"))
            for unsafe in (output_file, ROOT):
                with self.subTest(unsafe=unsafe), patch.object(
                    self.harness, "run_variant",
                ) as runner, self.assertRaisesRegex(ValueError, "output_base"):
                    self.make_short_demo(unsafe)
                runner.assert_not_called()
                self.assertEqual(
                    sorted(item.relative_to(temp_root).as_posix()
                           for item in temp_root.rglob("*")), before)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "unchanged")

    def test_project_results_escape_is_not_reclassified_as_system_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp) / "checkout"
            checkout.mkdir()
            escaped = checkout / "escaped-output"
            with patch.object(self.harness, "ROOT", checkout), \
                    self.assertRaisesRegex(ValueError, "output_base"):
                self.harness._validated_output_base(
                    checkout / "results" / ".." / escaped.name
                )
            self.assertFalse(escaped.exists())

    def test_demo_rejects_reparse_output_base_before_writing_target(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            target = temp_root / "target"
            target.mkdir()
            link = temp_root / "output-link"
            make_directory_reparse(link, target)
            before = sorted(item.relative_to(temp_root).as_posix()
                            for item in temp_root.rglob("*"))
            with patch.object(self.harness, "run_variant") as runner, \
                    self.assertRaisesRegex(ValueError, "reparse"):
                self.make_short_demo(link)
            after = sorted(item.relative_to(temp_root).as_posix()
                           for item in temp_root.rglob("*"))
            runner.assert_not_called()
            self.assertEqual(before, after)
            self.assertEqual(list(target.iterdir()), [])

    def test_run_record_rechecks_ancestor_swapped_after_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            ancestor = temp_root / "verified-ancestor"
            ancestor.mkdir()
            validated = self.harness._validated_output_base(ancestor / "output")
            outside = temp_root / "outside"
            outside.mkdir()
            ancestor.rmdir()
            make_directory_reparse(ancestor, outside)
            with self.assertRaisesRegex(ValueError, "reparse"):
                with self.harness.RunRecord(validated, {"purpose": "swap test"}):
                    pass
            self.assertEqual(list(outside.rglob("*")), [])

    def test_demo_rejects_trust_junction_before_any_json_or_anchor_write(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            output = temp_root / "simple-demo"
            output.mkdir()
            outside = temp_root / "outside"
            outside.mkdir()
            make_directory_reparse(output / ".phase5g-trust", outside)
            with patch.object(
                self.harness, "run_variant",
                return_value={
                    "status": "completed", "recording_passed": True,
                    "scientific_passed": False,
                },
            ) as runner, self.assertRaisesRegex(ValueError, "reparse"):
                self.make_short_demo(output)
            runner.assert_not_called()
            self.assertEqual(list(outside.rglob("*")), [])
            self.assertEqual(
                [item.name for item in output.iterdir()], [".phase5g-trust"])

    def test_atomic_staging_hardlink_is_rejected_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            writers = (
                (self.harness.atomic_json, ".writing"),
                (self.harness._finalizer_json, ".finalizing"),
            )
            for index, (writer, suffix) in enumerate(writers):
                target = output / f"latest-{index}.json"
                staging = target.with_name(target.name + suffix)
                victim = output / f"victim-{index}.txt"
                original = f"do not truncate victim {index}"
                victim.write_text(original, encoding="utf-8")
                os.link(victim, staging)
                with self.subTest(suffix=suffix), self.assertRaises(FileExistsError):
                    writer(target, {"status": "completed"})
                self.assertEqual(victim.read_text(encoding="utf-8"), original)
                self.assertTrue(staging.exists())
                self.assertTrue(os.path.samefile(victim, staging))

    def test_atomic_replace_does_not_write_through_destination_hardlink(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            victim = output / "victim.txt"
            victim.write_text("unchanged victim", encoding="utf-8")
            target = output / "latest.json"
            os.link(victim, target)
            self.harness.atomic_json(target, {"status": "completed"})
            self.assertEqual(
                victim.read_text(encoding="utf-8"), "unchanged victim")
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")),
                {"status": "completed"},
            )
            self.assertFalse(os.path.samefile(victim, target))

    def test_cli_forwards_every_demo_value_exactly_once(self):
        with patch("experiments.phase5g.run_phase5g_demo",
                   return_value=Path("literal-demo")) as demo:
            self.call_cli([
                "phase5g-demo", "--vehicle-count", "12", "--seed", "9",
                "--target-speed-mps", "9.5", "--duration-s", "40",
                "--output-base", "results/phase5g/custom-demo", "--offline",
                "--local-formation-range-m", "81",
                "--adjacent-lane-gap-m", "13",
                "--same-lane-gap-m", "29",
                "--position-tolerance-m", "1.25",
                "--formation-accel-limit-mps2", "0.35",
                "--max-formation-lane-changes", "1",
            ])
        demo.assert_called_once_with(
            vehicle_count=12, seed=9, target_speed_mps=9.5, duration_s=40.0,
            output_base="results/phase5g/custom-demo", mode="lane_priority",
            formal=False, live=False, local_formation_range_m=81.0,
            adjacent_lane_gap_m=13.0, same_lane_gap_m=29.0,
            position_tolerance_m=1.25, formation_accel_limit_mps2=0.35,
            max_formation_lane_changes=1,
        )

    def test_cli_rejects_invalid_simple_values_without_calling_demo(self):
        invalid = (
            ("--local-formation-range-m", "0"),
            ("--adjacent-lane-gap-m", "nan"),
            ("--same-lane-gap-m", "-1"),
            ("--position-tolerance-m", "inf"),
            ("--formation-accel-limit-mps2", "0"),
            ("--max-formation-lane-changes", "2"),
        )
        for flag, value in invalid:
            with self.subTest(flag=flag), patch(
                "experiments.phase5g.run_phase5g_demo"
            ) as demo, self.assertRaises(SystemExit):
                self.call_cli(["phase5g-demo", flag, value])
            demo.assert_not_called()

    def test_run_variant_reconstructs_nondefault_rules_and_neutral_private_memories(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "simple-variant"
            result = self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            self.assertEqual(result["status"], "completed")
            metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        expected_fields = {field.name for field in fields(SimpleFormationMemory)}
        self.assertEqual(set(metadata["initial_memories"]), set(case["controlled"]))
        for memory in metadata["initial_memories"].values():
            self.assertEqual(set(memory), expected_fields)
            self.assertIsNone(memory["reference_track_id"])
            self.assertIsNone(memory["join_anchor_track_id"])
            self.assertIsNone(memory["desired_lane_index"])
            self.assertEqual(memory["join_phase"], "FREE")
            self.assertIsNone(memory["stable_since_s"])
        self.assertEqual({key: metadata["parameters"][key] for key in PARAMETERS},
                         SIMPLE_NONDEFAULTS)

    def test_replay_rebuilds_from_saved_simple_values_not_current_defaults(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "simple-replay-source"
            self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            exact_replay = self.replay.replay_variant(path)
            self.assertTrue(exact_replay["passed"], exact_replay)
            self.assertTrue(exact_replay["decision_replay_passed"])
            self.assertTrue(exact_replay["integration_replay_passed"])
        changed_defaults = self.harness._registered()
        changed_defaults.update(SIMPLE_DEFAULTS)
        with patch.object(self.harness, "_registered", return_value=changed_defaults):
            restored_model, restored_physical, restored_policy = (
                self.replay._validate_metadata(metadata)
            )
        self.assertEqual(dict(restored_model.p), metadata["model_parameters"])
        self.assertEqual(restored_physical, metadata["parameters"])
        self.assertEqual(restored_policy, metadata["policy_parameters"])

        missing = deepcopy(metadata)
        del missing["parameters"]["simple_formation_same_gap_m"]
        with self.assertRaises(ValueError):
            self.replay._validate_metadata(missing)
        tampered = deepcopy(metadata)
        tampered["parameters"]["simple_formation_adjacent_gap_m"] = 12.0
        with self.assertRaises(ValueError):
            self.replay._validate_metadata(tampered)

    def test_replay_rejects_resealed_bilateral_parameter_tampering_by_input_digest(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bilateral-parameter-tampering"
            self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            metadata_path = path / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIn("parameters_input_sha256", metadata)
            metadata["parameters"]["simple_formation_local_range_m"] = 79.0
            metadata["policy_parameters"]["simple_formation_local_range_m"] = 79.0
            self.harness.atomic_json(metadata_path, metadata)
            self.harness.seal_directory(path)
            replay = self.replay.replay_variant(path)
        self.assertFalse(replay["passed"], replay)
        self.assertIn("metadata.parameters_input_sha256", "\n".join(replay["errors"]))

    def test_replay_rejects_missing_parameter_input_digest_by_exact_field_name(self):
        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing-parameter-input-digest"
            self.harness.run_variant(
                path, model, physical, policy, case, "lane_priority", live=False,
            )
            metadata_path = path / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            del metadata["parameters_input_sha256"]
            self.harness.atomic_json(metadata_path, metadata)
            self.harness.seal_directory(path)
            replay = self.replay.replay_variant(path)
        self.assertFalse(replay["passed"], replay)
        self.assertIn("metadata.parameters_input_sha256", "\n".join(replay["errors"]))

    def test_replay_rejects_missing_or_changed_case_input_digests_by_field_name(self):
        from experiments.phase5g_cases import digest_json, physical_case

        model, physical, policy = self.simple_parameters()
        case = self.short_case(physical)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "digest-source"
            self.harness.run_variant(
                source, model, physical, policy, case, "lane_priority", live=False,
            )
            original = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(
                original["physical_input_sha256"], digest_json(physical_case(case)),
            )
            self.assertEqual(original["case_input_sha256"], digest_json(case))
            for index, (field, operation) in enumerate((
                ("physical_input_sha256", "delete"),
                ("physical_input_sha256", "change"),
                ("case_input_sha256", "delete"),
                ("case_input_sha256", "change"),
            )):
                path = Path(temp) / f"digest-tamper-{index}"
                shutil.copytree(source, path)
                metadata_path = path / "metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if operation == "delete":
                    del metadata[field]
                else:
                    metadata[field] = "0" * 64
                self.harness.atomic_json(metadata_path, metadata)
                self.harness.seal_directory(path)
                with self.subTest(field=field, operation=operation):
                    replay = self.replay.replay_variant(path)
                    self.assertFalse(replay["passed"], replay)
                    self.assertIn(f"metadata.{field}", "\n".join(replay["errors"]))

    def test_lane_change_facts_count_both_formation_reasons_only(self):
        state0 = {
            "time_s": 0.0, "x_m": 0.0, "y_m": 1.65, "heading_rad": 0.0,
            "vx_mps": 10.0, "vy_mps": 0.0, "yaw_rate_radps": 0.0,
            "a_drive_mps2": 0.0, "steering_rad": 0.0,
        }
        state1 = {**state0, "time_s": 0.1}
        state2 = {**state0, "time_s": 0.2, "y_m": 4.95}
        plan = asdict(QuadraticLaneChange(
            start_s=0.0, y_start_m=1.65, y_target_m=4.95,
            duration_s=0.2, speed_mps=10.0,
        ))

        def records(reason):
            return [{
                "status": "completed", "initial": {"v0": state0},
                "inputs": {"v0": {"memory": {
                    "plan": None, "completed_lane_changes": 0,
                }}},
                "decisions": {"v0": {"memory": {
                    "plan": plan, "lane_change_reason": reason,
                    "completed_lane_changes": 0,
                }}},
                "steps": {"v0": {"samples": [state1], "final": state1}},
            }, {
                "status": "completed", "initial": {"v0": state2},
                "inputs": {"v0": {"memory": {
                    "plan": plan, "completed_lane_changes": 0,
                }}},
                "decisions": {"v0": {"memory": {
                    "plan": None, "lane_change_reason": "",
                    "completed_lane_changes": 1,
                }}},
                "steps": {"v0": {"samples": [state2], "final": state2}},
            }]

        self.assertEqual(
            self.harness.FORMATION_LANE_REASONS,
            frozenset({"formation_geometry", "simple_formation_balance"}),
        )
        for reason in self.harness.FORMATION_LANE_REASONS | {"slower_visible_lead"}:
            rows = records(reason)
            facts = self.harness._lane_change_facts(
                rows, {"controlled": ["v0"]},
                {"lane_width_m": 3.3},
            )
            expected = 0 if reason == "slower_visible_lead" else 1
            self.assertEqual(facts["completed_lane_changes"], 1)
            self.assertEqual(facts["formation_lane_changes"], expected)

    def test_source_hashes_bind_simple_rules_and_approved_documents(self):
        required = {
            "noa/simple_formation.py",
            "docs/superpowers/specs/2026-09-14-phase5g-simple-local-ifelse-formation-design.md",
            "docs/superpowers/plans/2026-09-14-phase5g-simple-local-ifelse-formation.md",
        }
        self.assertTrue(required.issubset(self.harness.SOURCE_FILES))
        self.assertTrue((required - {"noa/simple_formation.py"}).issubset(
            self.harness.INPUTS
        ))
        hashes = self.harness.source_hashes()
        self.assertTrue(required.issubset(hashes))
        self.assertTrue(all(len(hashes[name]) == 64 for name in required))

    def test_demo_builds_complete_trusted_single_execution_package(self):
        from experiments.phase5g_cases import digest_json, physical_case
        from research.common import sha256

        with tempfile.TemporaryDirectory() as temp:
            source = self.make_short_demo(Path(temp) / "demos")
            required = {
                "code_hashes.json", "input_hashes.json",
                "code_snapshot_manifest.json", "input_snapshot_manifest.json",
                "frozen_cases.json", "case_index.json",
            }
            self.assertTrue(all((source / name).is_file() for name in required))
            self.assertTrue((source / "code_snapshot").is_dir())
            self.assertTrue((source / "input_snapshot").is_dir())
            anchor_path = source.parent / ".phase5g-trust" / f"{source.name}.json"
            self.assertTrue(anchor_path.is_file())
            completion_path = (
                source.parent / ".phase5g-trust" / f"{source.name}.completion.json"
            )
            self.assertTrue(completion_path.is_file())

            metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
            execution = metadata["execution"]
            bundle_path = source / "input_snapshot" / "phase5g_cases.json"
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            frozen = json.loads((source / "frozen_cases.json").read_text(encoding="utf-8"))
            index = json.loads((source / "case_index.json").read_text(encoding="utf-8"))
            child = json.loads((source / "case" / "metadata.json").read_text(encoding="utf-8"))
            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
            completion = json.loads(completion_path.read_text(encoding="utf-8"))

            self.assertEqual(set(bundle), {"schema", "cases", "execution"})
            self.assertEqual(bundle["schema"], "phase5g_simple_demo_cases_v1")
            self.assertEqual(bundle["cases"], frozen)
            self.assertEqual(len(frozen), 1)
            self.assertEqual(bundle["execution"], execution)
            self.assertEqual(index["execution"], execution)
            self.assertEqual(index["schema"], "phase5g_simple_demo_index_v1")
            self.assertIs(index["started"], True)
            self.assertIs(index["finalized"], True)
            self.assertIs(index["completed"], True)
            self.assertEqual(execution["case_directory"], "case")
            self.assertEqual(execution["parent_run_id"], source.name)
            self.assertEqual(child["parent_run_id"], source.name)
            self.assertEqual(execution["output_nonce"], child["output_nonce"])
            self.assertEqual(len(execution["output_nonce"]), 32)
            self.assertEqual(execution["mode"], "lane_priority")
            self.assertIs(execution["simple_formation_enabled"], True)
            self.assertEqual(execution["simple_parameters"], SIMPLE_NONDEFAULTS)
            self.assertEqual(execution["case_input_sha256"], digest_json(frozen[0]))
            self.assertEqual(
                execution["physical_input_sha256"], digest_json(physical_case(frozen[0])),
            )
            for field in (
                "case_input_sha256", "physical_input_sha256",
                "parameters_input_sha256", "initial_memories_sha256",
            ):
                self.assertEqual(execution[field], child[field])
            self.assertEqual(
                {key: child["parameters"][key] for key in PARAMETERS},
                SIMPLE_NONDEFAULTS,
            )
            self.assertEqual(
                {key: child["policy_parameters"][key] for key in PARAMETERS},
                SIMPLE_NONDEFAULTS,
            )

            code_manifest = json.loads(
                (source / "code_snapshot_manifest.json").read_text(encoding="utf-8")
            )
            input_manifest = json.loads(
                (source / "input_snapshot_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                code_manifest,
                self.harness.snapshot_manifest(source / "code_snapshot", "code_snapshot"),
            )
            self.assertEqual(
                input_manifest,
                self.harness.snapshot_manifest(source / "input_snapshot", "input_snapshot"),
            )
            self.assertEqual(anchor["source_manifest_sha256"],
                             self.harness._anchor_digest(code_manifest))
            self.assertEqual(anchor["input_manifest_sha256"],
                             self.harness._anchor_digest(input_manifest))
            self.assertEqual(anchor["case_file_sha256"], sha256(bundle_path))
            self.assertEqual(metadata["case_file_sha256"], sha256(bundle_path))
            self.assertEqual(completion["schema"],
                             "phase5g_simple_demo_completion_anchor_v1")
            self.assertEqual(completion["run_id"], source.name)
            self.assertEqual(completion["source_manifest_sha256"],
                             anchor["source_manifest_sha256"])
            self.assertEqual(completion["input_manifest_sha256"],
                             anchor["input_manifest_sha256"])
            self.assertEqual(completion["child_directory"], "case")
            self.assertEqual(
                completion["child_manifest"],
                self.harness.snapshot_manifest(source / "case", "case"),
            )
            evidence = json.loads(
                (source / "evidence_hashes.json").read_text(encoding="utf-8")
            )
            self.assertEqual(completion["outer_evidence_hashes"], evidence)

    def test_demo_outer_replay_uses_sibling_anchor_and_keeps_science_factual(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.make_short_demo(Path(temp) / "demos")
            metadata = json.loads(
                (source / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["schema"], "phase5g_simple_demo_v1")
            real_run = self.replay.subprocess.run
            launches = []

            def record_snapshot_launch(*args, **kwargs):
                launches.append((args, kwargs))
                return real_run(*args, **kwargs)

            with patch.object(
                self.replay.subprocess, "run", side_effect=record_snapshot_launch,
            ):
                report = self.replay.replay_run(
                    source, base=Path(temp) / "replays",
                )
            self.assertEqual(len(launches), 1)
            command = launches[0][0][0]
            self.assertEqual(Path(launches[0][1]["cwd"]),
                             source / "code_snapshot")
            self.assertEqual(command[:5], [sys.executable, "-I", "-B", "-S", "-c"])
            self.assertIn(
                f"sys.path.insert(0,{str(source / 'code_snapshot')!r})",
                command[5],
            )
            self.assertIn(
                "from experiments.phase5g_replay import _replay_run_local",
                command[5],
            )
        self.assertTrue(report["passed"], report)
        self.assertTrue(report["semantic_replay_passed"], report)
        self.assertTrue(report["complete_execution"], report)
        self.assertTrue(report["engineering_passed"], report)
        self.assertFalse(report["scientific_gate_applicable"], report)
        self.assertIsNone(report["scientific_gate_passed"], report)
        self.assertEqual(report["trust_model"],
                         "sibling_anchor_only_not_whole-package-tamper-resistant")

    def test_demo_scientific_gate_tri_state_is_explicit_for_three_and_six(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for count, applicable, scientific in (
                (3, False, None), (6, True, False), (12, False, None),
            ):
                with self.subTest(count=count):
                    source = self.make_short_demo(
                        root / f"demo-{count}", count=count, seed=11,
                    )
                    child = json.loads(
                        (source / "case" / "validation.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    outer = json.loads(
                        (source / "validation.json").read_text(encoding="utf-8")
                    )
                    child_metadata = json.loads(
                        (source / "case" / "metadata.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    if count == 6:
                        self.assertEqual(child_metadata["case"]["name"],
                                         "main_6_3_2_1")
                    self.assertIs(child["scientific_gate_applicable"], applicable)
                    self.assertIs(child["scientific_passed"], scientific)
                    self.assertIs(outer["scientific_gate_applicable"], applicable)
                    self.assertIs(outer["scientific_gate_passed"], scientific)
                    replay = self.replay.replay_run(
                        source, base=root / f"replay-{count}",
                    )
                    self.assertTrue(replay["passed"], replay)
                    self.assertIs(replay["scientific_gate_applicable"], applicable)
                    self.assertIs(replay["scientific_gate_passed"], scientific)

    def test_demo_outer_replay_rejects_snapshot_binding_and_child_swap_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_short_demo(root / "source", seed=11)
            other = self.make_short_demo(root / "other", seed=11)
            attacks = []

            code = self.copy_demo_with_anchor(source, root / "attack-code")
            changed = code / "code_snapshot" / "experiments" / "phase5g.py"
            changed.write_text(changed.read_text(encoding="utf-8") + "\n# attack\n",
                               encoding="utf-8")
            self.harness.seal_directory(code)
            attacks.append(("code_hashes.experiments/phase5g.py", code))

            inputs = self.copy_demo_with_anchor(source, root / "attack-input")
            changed = inputs / "input_snapshot" / "phase5g_cases.json"
            value = json.loads(changed.read_text(encoding="utf-8"))
            value["cases"][0]["purpose"] = "tampered frozen case"
            changed.write_bytes(phase5g_cases.canonical_json_bytes(value))
            self.harness.seal_directory(inputs)
            attacks.append(("input_hashes.phase5g_cases.json", inputs))

            binding = self.copy_demo_with_anchor(source, root / "attack-binding")
            changed = binding / "case_index.json"
            value = json.loads(changed.read_text(encoding="utf-8"))
            value["execution"]["case_name"] = "different_case"
            self.harness.atomic_json(changed, value)
            self.harness.seal_directory(binding)
            attacks.append(("completion_anchor", binding))

            child_swap = self.copy_demo_with_anchor(source, root / "attack-child")
            shutil.rmtree(child_swap / "case")
            shutil.copytree(other / "case", child_swap / "case")
            self.harness.seal_directory(child_swap)
            attacks.append(("completion_anchor", child_swap))

            for expected, attack in attacks:
                with self.subTest(expected=expected):
                    report = self.replay.replay_run(
                        attack, base=attack.parent / "replays",
                    )
                    self.assertFalse(report["passed"], report)
                    self.assertIn(expected, "\n".join(report["errors"]))

    def test_demo_completion_anchor_rejects_deep_same_input_child_swap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_short_demo(root / "source", seed=11)
            other = self.make_short_demo(root / "other", seed=11)
            attack = self.copy_demo_with_anchor(source, root / "attack")
            shutil.rmtree(attack / "case")
            shutil.copytree(other / "case", attack / "case")
            execution = json.loads(
                (attack / "metadata.json").read_text(encoding="utf-8")
            )["execution"]
            child_metadata_path = attack / "case" / "metadata.json"
            child_metadata = json.loads(child_metadata_path.read_text(encoding="utf-8"))
            child_metadata["parent_run_id"] = attack.name
            child_metadata["parameters_input_sha256"] = execution[
                "parameters_input_sha256"
            ]
            self.harness.atomic_json(child_metadata_path, child_metadata)
            self.harness.seal_directory(attack / "case")
            self.harness.seal_directory(attack)

            report = self.replay.replay_run(
                attack, base=attack.parent / "replays",
            )
        self.assertFalse(report["passed"], report)
        self.assertFalse(report["cases"], report)
        self.assertIn("completion_anchor", "\n".join(report["errors"]))

    def test_demo_outer_replay_rejects_missing_trust_material_without_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_short_demo(root / "source")
            no_anchor = root / "no-anchor" / source.name
            no_anchor.parent.mkdir(parents=True)
            shutil.copytree(source, no_anchor)
            with self.assertRaisesRegex(ValueError, "trust_anchor"):
                self.replay.replay_run(no_anchor, base=root / "replays-no-anchor")

            no_snapshot = self.copy_demo_with_anchor(source, root / "no-snapshot")
            shutil.rmtree(no_snapshot / "code_snapshot")
            self.harness.seal_directory(no_snapshot)
            report = self.replay.replay_run(
                no_snapshot, base=root / "replays-no-snapshot",
            )
            self.assertFalse(report["passed"], report)
            self.assertIn("code_snapshot: missing directory", "\n".join(report["errors"]))

            no_completion = self.copy_demo_with_anchor(source, root / "no-completion")
            completion = (
                no_completion.parent / ".phase5g-trust"
                / f"{no_completion.name}.completion.json"
            )
            if completion.exists():
                completion.unlink()
            report = self.replay.replay_run(
                no_completion, base=root / "replays-no-completion",
            )
            self.assertFalse(report["passed"], report)
            self.assertIn("completion_anchor: missing", "\n".join(report["errors"]))

    def test_demo_outer_replay_rejects_missing_and_extra_schema_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_short_demo(root / "source")
            attacks = {}
            missing = self.copy_demo_with_anchor(source, root / "missing-field")
            metadata_path = missing / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            del metadata["purpose"]
            self.harness.atomic_json(metadata_path, metadata)
            self.harness.seal_directory(missing)
            attacks["metadata.fields"] = missing

            extra = self.copy_demo_with_anchor(source, root / "extra-field")
            index_path = extra / "case_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["unexpected"] = True
            self.harness.atomic_json(index_path, index)
            self.harness.seal_directory(extra)
            attacks["completion_anchor.outer_evidence_hashes.case_index.json"] = extra

            for expected, attack in attacks.items():
                with self.subTest(expected=expected):
                    report = self.replay.replay_run(
                        attack, base=attack.parent / "replays",
                    )
                    self.assertFalse(report["passed"], report)
                    self.assertIn(expected, "\n".join(report["errors"]))

    def test_outer_replay_schema_dispatch_rejects_unknown_and_corrupt_without_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attacks = {
                "unknown": ('{"schema":"unknown_outer_v1"}', "metadata.schema"),
                "corrupt": ('{"schema":', "metadata.json"),
            }
            for name, (payload, expected) in attacks.items():
                with self.subTest(name=name):
                    source = root / name
                    source.mkdir()
                    (source / "metadata.json").write_text(payload, encoding="utf-8")
                    with patch.object(
                        self.replay, "_validate_source_run",
                        side_effect=AssertionError("unexpected formal fallback"),
                    ) as formal, patch.object(
                        self.replay, "_validate_simple_source_run",
                        side_effect=AssertionError("unexpected simple fallback"),
                    ) as simple:
                        report = self.replay._replay_run_local(source, {})
                    self.assertFalse(report["passed"], report)
                    errors = "\n".join(report["errors"])
                    self.assertIn(expected, errors)
                    self.assertNotIn("unexpected", errors)
                    formal.assert_not_called()
                    simple.assert_not_called()

    def test_cli_demo_replay_exit_depends_on_engineering_pass_only(self):
        with patch(
            "experiments.phase5g_replay.replay_run",
            return_value={"passed": True, "scientific_gate_passed": False},
        ) as replay, self.assertRaises(SystemExit) as exited:
            self.call_cli(["phase5g-replay", "--run-dir", "simple-demo"])
        self.assertEqual(exited.exception.code, 0)
        replay.assert_called_once_with("simple-demo")


if __name__ == "__main__":
    unittest.main()
