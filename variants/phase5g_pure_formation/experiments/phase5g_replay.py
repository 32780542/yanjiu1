"""Semantic Phase 5G replay using sealed local source and per-vehicle memory."""

from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig

from experiments.phase3_replay import compare_tree
from experiments.phase4_replay import replay_readbacks
from experiments.phase5g import Phase5GRunRecord as RunRecord
from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.road import VisibleRoad
from research.common import ROOT, code_manifest, output_path, read_json, sha256
from simulation.noa_clock import ReplayBoundary
from simulation.phase5g_clock import CLOCK_SCHEMA, Phase5GClock, initial_memory_hash


def _file_set(path: Path) -> set[str]:
    return {file.relative_to(path).as_posix() for file in path.rglob("*") if file.is_file()}


def _manifest_differences(path: Path) -> list[str]:
    manifest_path = path / "evidence_hashes.json"
    if not manifest_path.is_file():
        manifest_path = path / "unsealed_evidence_hashes.json"
    if not manifest_path.is_file():
        return ["evidence_hashes.json"]
    hashes = read_json(manifest_path)
    if not isinstance(hashes, dict) or not hashes:
        return ["evidence_hashes.json"]
    differences = []
    for name, digest in hashes.items():
        file = (path / name).resolve()
        if (type(name) is not str or Path(name).is_absolute()
                or not file.is_relative_to(path.resolve()) or not file.is_file()
                or type(digest) is not str or sha256(file) != digest):
            differences.append(name)
    actual = _file_set(path) - {"evidence_hashes.json", "unsealed_evidence_hashes.json"}
    return sorted(set(differences) | (actual ^ set(hashes)))


def _validate_metadata(metadata: dict) -> tuple[KinematicModel, dict, dict]:
    from experiments.phase5g import (
        MODES, _variant_input_sha256, parameters, source_hashes,
    )
    from experiments.phase5g_cases import digest_json, physical_case
    from noa.simple_formation import PARAMETERS

    mode = metadata.get("mode")
    if type(mode) is not str or mode not in MODES:
        raise ValueError("metadata.mode: unknown Phase 5G mode")
    actual_flags = {
        key: metadata.get("parameters", {}).get(key)
        for key in ("formation_enabled", "formation_lane_change_enabled")
    }
    matching = [name for name, flags in MODES.items() if flags == actual_flags]
    if matching == [mode]:
        pass
    elif matching:
        raise ValueError("metadata.mode: disagrees with its exact registered flags")
    else:
        for key, expected in MODES[mode].items():
            if actual_flags.get(key) is not expected:
                raise ValueError(f"metadata.parameters.{key}: mode flag differs")
        raise ValueError("metadata.mode: invalid flag combination")
    saved_parameters = metadata.get("parameters")
    if not isinstance(saved_parameters, dict):
        raise ValueError("metadata.parameters: fields differ")
    simple_rules = saved_parameters.get("simple_formation_enabled")
    if type(simple_rules) is not bool:
        raise ValueError("metadata.parameters.simple_formation_enabled: must be bool")
    if simple_rules:
        try:
            simple_overrides = {name: saved_parameters[name] for name in PARAMETERS}
        except KeyError as error:
            raise ValueError(
                f"metadata.parameters.{error.args[0]}: field missing"
            ) from error
    else:
        simple_overrides = None
    target = saved_parameters.get("noa_target_speed_mps")
    model, physical, policy = parameters(
        mode, target, simple_rules=simple_rules,
        simple_overrides=simple_overrides,
    )
    tolerance = model.p["replay_absolute_tolerance"]
    compare_tree(dict(model.p), metadata.get("model_parameters"), 0.0,
                 "metadata.model_parameters")
    compare_tree(physical, metadata.get("parameters"), 0.0,
                 "metadata.parameters")
    compare_tree(policy, metadata.get("policy_parameters"), 0.0,
                 "metadata.policy_parameters")
    expected_sources = source_hashes()
    stored_sources = metadata.get("source_hashes")
    if not isinstance(stored_sources, dict):
        raise ValueError("metadata.source_hashes: fields differ")
    for name, digest in expected_sources.items():
        if stored_sources.get(name) != digest:
            raise ValueError(f"metadata.source_hashes.{name}: source differs")
    if set(stored_sources) != set(expected_sources):
        raise ValueError("metadata.source_hashes: fields differ")
    if metadata.get("schema") != "phase5g_variant_v1":
        raise ValueError("metadata.schema: value differs")
    if metadata.get("clock_schema") != CLOCK_SCHEMA:
        raise ValueError("metadata.clock_schema: value differs")
    if metadata.get("initial_memories_sha256") != initial_memory_hash(
        metadata.get("initial_memories")
    ):
        raise ValueError("metadata.initial_memories_sha256: hash differs")
    if metadata.get("initial") != metadata.get("case", {}).get("initial"):
        raise ValueError("metadata.initial: differs from case.initial")
    case = metadata.get("case")
    if metadata.get("physical_input_sha256") != digest_json(physical_case(case)):
        raise ValueError("metadata.physical_input_sha256: differs")
    if metadata.get("case_input_sha256") != digest_json(case):
        raise ValueError("metadata.case_input_sha256: differs")
    expected_input_digest = _variant_input_sha256(
        mode, case, model, physical, policy, metadata.get("initial_memories"),
    )
    if metadata.get("parameters_input_sha256") != expected_input_digest:
        raise ValueError("metadata.parameters_input_sha256: differs")
    if tolerance < 0:
        raise ValueError("metadata.model_parameters.replay_absolute_tolerance: invalid")
    return model, physical, policy


def _clock(metadata: dict, model, physical: dict, policy: dict) -> Phase5GClock:
    road_raw = metadata["road"]
    road = VisibleRoad(
        tuple(tuple(tuple(point) for point in line) for line in road_raw["boundaries"]),
        tuple(tuple(tuple(point) for point in line) for line in road_raw["markings"]),
    )
    initial = {key: VehicleState(**state) for key, state in metadata["initial"].items()}
    return Phase5GClock(
        initial, model, road, physical, policy, metadata["case"]["controlled"],
        metadata["case"]["scripts"], metadata["initial_memories"],
        clock_schema=CLOCK_SCHEMA,
        initial_memories_sha256=metadata["initial_memories_sha256"],
    )


def _replay_trace(metadata: dict, trace_path: Path, model, physical: dict,
                  policy: dict) -> dict:
    count = completed = physical_count = samples = 0
    maximum = 0.0
    errors = []
    try:
        status = metadata.get("execution_status")
        if status not in ("completed", "failed"):
            raise ValueError("metadata.execution_status: not finalized")
        partial = status == "failed"
        expected_count = metadata["trace_intervals"] if partial else metadata["intervals"]
        if type(expected_count) is not int or expected_count < 0 \
                or expected_count > metadata["intervals"]:
            raise ValueError("metadata.trace_intervals: invalid count")
        if not partial and expected_count == 0:
            raise ValueError("metadata.trace_intervals: completed source is empty")
        clock = _clock(metadata, model, physical, policy) if expected_count else None
        saw_failed_tail = False
        with trace_path.open(encoding="utf-8") as stream:
            for count, line in enumerate(stream, 1):
                if count > expected_count:
                    raise ValueError(f"trace[{count - 1}]: extra interval")
                stored = json.loads(line)
                failed_tail = partial and count == expected_count and stored.get("status") == "failed"
                boundary = ((metadata.get("failure_stage"), metadata.get("failure_actor"))
                            if failed_tail else None)
                if failed_tail and not boundary[0]:
                    raise ValueError(f"trace[{count - 1}]: failed tail lacks boundary")
                if boundary:
                    try:
                        clock.tick(stop_before=boundary)
                    except ReplayBoundary:
                        expected = clock.last_record
                        expected["error"] = metadata["failure_error"]
                    else:
                        raise ValueError(f"trace[{count - 1}]: failure boundary not reached")
                else:
                    expected = clock.tick()
                sync_facts = None
                if failed_tail:
                    from experiments.phase5g import _readback_facts

                    phase = stored.get("readback_phase")
                    committed = phase == "postcommit"
                    sync_facts = _readback_facts(
                        stored, metadata["initial"], advances_before=0,
                        advances_after=1 if committed else 0,
                    )
                    for field, value in sync_facts.items():
                        compare_tree(value, metadata.get(field), 0.0,
                                     f"metadata.{field}")
                    if metadata.get("failure_readback_phase") != phase:
                        raise ValueError("metadata.failure_readback_phase: differs")
                    expected.update(sync_facts)
                if metadata["live"] and (not boundary or boundary[0] in ("synchronization", "commit")):
                    if failed_tail and stored.get("readback_phase") in (
                        "integration_validation", "commit",
                    ):
                        if stored.get("readback") != {}:
                            raise ValueError(f"trace[{count - 1}].readback: unexpected")
                        expected["readback"] = {}
                    else:
                        expected["readback"] = replay_readbacks(
                            metadata, stored, expected, model, failed_tail,
                        )
                if failed_tail:
                    saw_failed_tail = True
                    if stored.get("error") != metadata.get("failure_error"):
                        raise ValueError(f"trace[{count - 1}].error: differs")
                    expected.update(status="failed", error=stored["error"])
                    if metadata["live"] and boundary[0] == "synchronization":
                        expected["readback_phase"] = metadata["failure_readback_phase"]
                maximum = max(maximum, compare_tree(
                    expected, stored, model.p["replay_absolute_tolerance"],
                    f"trace[{count - 1}]",
                ))
                completed += stored.get("status") == "completed"
                from experiments.phase5g import _record_is_physical
                is_physical = _record_is_physical(
                    stored, metadata["initial"], live=metadata["live"],
                )
                physical_count += is_physical
                samples += sum(len(step["samples"]) for step in expected.get("steps", {}).values())
        if count != expected_count:
            raise ValueError(f"trace: truncated {count}/{expected_count}")
        if partial and expected_count and not saw_failed_tail and not metadata.get("close_error"):
            raise ValueError("trace: failed source lacks failed tail")
        expected_counts = {
            "trace_intervals": count, "completed_intervals": completed,
            "physical_intervals": physical_count, "recorded_intervals": physical_count,
            "partial_tail": count > physical_count,
        }
        for key, value in expected_counts.items():
            if metadata.get(key) != value:
                raise ValueError(f"metadata.{key}: {metadata.get(key)}/{value}")
    except Exception as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {
        "passed": not errors, "errors": errors, "intervals": count,
        "completed_intervals": completed, "physical_intervals": physical_count,
        "vehicle_substeps": samples, "max_numeric_error": maximum,
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def replay_variant(variant_dir: str | Path, *, require_manifest: bool = True) -> dict:
    """Rebuild a complete or failed-prefix variant and every derived outcome."""
    path = Path(variant_dir).resolve()
    result = {
        "passed": False, "errors": [], "partial_source": False,
        "decision_replay_passed": False, "integration_replay_passed": False,
        "detection_replay_passed": False, "lane_change_replay_passed": False,
        "speed_recovery_replay_passed": False, "acceptance_replay_passed": False,
    }
    try:
        metadata = read_json(path / "metadata.json")
        model, physical, policy = _validate_metadata(metadata)
        if require_manifest:
            differences = _manifest_differences(path)
            if differences:
                raise ValueError(f"evidence_hashes: files differ: {differences}")
        saved = read_json(path / "validation.json")
        produced = saved.get("produced_evidence")
        if not isinstance(produced, list) or len(produced) != len(set(produced)):
            raise ValueError("validation.produced_evidence: invalid")
        actual_produced = _file_set(path) - {
            "evidence_hashes.json", "unsealed_evidence_hashes.json",
        }
        if set(produced) != actual_produced:
            raise ValueError("validation.produced_evidence: differs from actual prefix")
        trace = _replay_trace(metadata, path / "trace.jsonl", model, physical, policy)
        if not trace["passed"]:
            raise ValueError("; ".join(trace["errors"]))
        rows = _records(path / "trace.jsonl")
        from experiments.phase5g import (_record_is_physical, _scientific_applicable,
                                         evaluate_records, scientific_gate,
                                         variant_acceptance)
        physical_rows = [row for row in rows if _record_is_physical(
            row, metadata["initial"], live=metadata["live"])]
        derived = evaluate_records(physical_rows, metadata["case"], model, physical)
        tolerance = model.p["replay_absolute_tolerance"]
        derived_names = ("detection", "geometry", "metrics", "lane_changes",
                         "speed_recovery")
        failure_stage = metadata.get("failure_stage")
        lifecycle_failed = metadata.get("lifecycle_status") == "failed"
        if lifecycle_failed and failure_stage == "evaluation":
            required_derived = ()
        elif lifecycle_failed and isinstance(failure_stage, str) \
                and failure_stage.startswith("derived."):
            stopped = failure_stage.split(".", 1)[1]
            required_derived = derived_names[:derived_names.index(stopped)]
        else:
            required_derived = derived_names
        for name in derived_names:
            artifact = path / f"{name}.json"
            if name in required_derived:
                compare_tree(derived[name], read_json(artifact), tolerance, name)
            elif artifact.exists():
                raise ValueError(f"{name}: unexpected after {failure_stage} failure")
        if saved.get("summary") is not None:
            compare_tree(derived["summary"], saved["summary"], tolerance,
                         "validation.summary")
        if lifecycle_failed:
            recomputed = {
                "status": "failed", "recording_passed": trace["intervals"] > 0,
                "driving_passed": False,
                "comfort_passed": bool(
                    saved.get("summary") is not None
                    and derived["metrics"]["comfort_passed"]),
                "passed": False,
            }
        else:
            recomputed = variant_acceptance(
                metadata, derived, trace_intervals=trace["intervals"],
                completed_intervals=trace["completed_intervals"],
            )
        for field in ("status", "recording_passed", "driving_passed",
                      "comfort_passed", "passed"):
            compare_tree(recomputed[field], saved.get(field), 0.0,
                         f"validation.{field}")
        acceptance = ((False if _scientific_applicable(
            metadata["case"], metadata["mode"]) else None) if lifecycle_failed
            else scientific_gate(
            metadata["case"], metadata["mode"], derived["summary"],
            execution_completed=metadata["execution_status"] == "completed",
            speed_recovery=derived["speed_recovery"],
        ))
        compare_tree(acceptance, saved["scientific_passed"], 0.0,
                     "validation.scientific_passed")
        result.update(
            passed=True, partial_source=recomputed["status"] == "failed",
            execution_completed=recomputed["status"] == "completed",
            recomputed_status=recomputed["status"],
            recomputed_recording_passed=recomputed["recording_passed"],
            recomputed_driving_passed=recomputed["driving_passed"],
            recomputed_comfort_passed=recomputed["comfort_passed"],
            recomputed_passed=recomputed["passed"],
            source_status=saved.get("status"), source_passed=saved.get("passed"),
            decision_replay_passed=True, integration_replay_passed=True,
            detection_replay_passed=True, lane_change_replay_passed=True,
            speed_recovery_replay_passed=True, acceptance_replay_passed=True,
            trace=trace, summary=derived["summary"], scientific_passed=acceptance,
        )
    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
    return result


def _validate_source_run(path: Path, anchor: dict) -> tuple[dict, dict, dict]:
    from experiments.phase5g import (INPUTS, _anchor_digest, _mode_registry,
                                     parameters, snapshot_manifest)
    from experiments import phase5g_cases

    differences = _manifest_differences(path)
    if differences:
        raise ValueError(f"evidence_hashes: files differ: {differences}")
    metadata = read_json(path / "metadata.json")
    if metadata.get("schema") != "phase5g_run_v1":
        raise ValueError("metadata.schema: not a Phase 5G run")
    registered_modes = _mode_registry()
    compare_tree(registered_modes, metadata.get("mode_registry"), 0.0,
                 "metadata.mode_registry")
    if _anchor_digest(registered_modes) != anchor.get("mode_registry_sha256"):
        raise ValueError("metadata.mode_registry: trusted registry differs")
    stored_code = read_json(path / "code_hashes.json")
    anchored_code = anchor.get("source_hashes")
    if not isinstance(anchored_code, dict):
        raise ValueError("trust_anchor.source_hashes: missing")
    for name in sorted(set(stored_code) | set(anchored_code)):
        if stored_code.get(name) != anchored_code.get(name):
            raise ValueError(f"code_hashes.{name}: differs from trusted source")
    stored_snapshot = read_json(path / "code_snapshot_manifest.json")
    compare_tree(anchor.get("code_snapshot_manifest"), stored_snapshot, 0.0,
                 "code_snapshot_manifest")
    if _anchor_digest(stored_snapshot) != anchor.get("source_manifest_sha256"):
        raise ValueError("code_snapshot_manifest: trusted source manifest differs")
    compare_tree(stored_snapshot,
                 snapshot_manifest(path / "code_snapshot", "code_snapshot"),
                 0.0, "code_snapshot")
    for name, digest in stored_code.items():
        file = path / "code_snapshot" / name
        if not file.is_file() or sha256(file) != digest:
            raise ValueError(f"code_snapshot.{name}: source differs")
    current = code_manifest()
    compare_tree(current, stored_code, 0.0, "code_hashes")
    stored_inputs = read_json(path / "input_hashes.json")
    anchored_inputs = anchor.get("input_hashes")
    if not isinstance(anchored_inputs, dict):
        raise ValueError("trust_anchor.input_hashes: missing")
    for name in sorted(set(stored_inputs) | set(anchored_inputs)):
        if stored_inputs.get(name) != anchored_inputs.get(name):
            raise ValueError(f"input_hashes.{name}: differs from trusted input")
    stored_input_snapshot = read_json(path / "input_snapshot_manifest.json")
    compare_tree(anchor.get("input_snapshot_manifest"), stored_input_snapshot, 0.0,
                 "input_snapshot_manifest")
    if _anchor_digest(stored_input_snapshot) != anchor.get("input_manifest_sha256"):
        raise ValueError("input_snapshot_manifest: trusted input manifest differs")
    compare_tree(stored_input_snapshot,
                 snapshot_manifest(path / "input_snapshot", "input_snapshot"),
                 0.0, "input_snapshot")
    if set(stored_inputs) != set(INPUTS) | {"phase5g_cases.json"}:
        raise ValueError("input_hashes: fields differ")
    for name, digest in stored_inputs.items():
        file = path / "input_snapshot" / name
        if not file.is_file() or sha256(file) != digest:
            raise ValueError(f"input_snapshot.{name}: differs")
    raw = (path / "input_snapshot" / "phase5g_cases.json").read_bytes()
    if metadata.get("case_file_sha256") != anchor.get("case_file_sha256"):
        raise ValueError("metadata.case_file_sha256: differs from trusted case input")
    if sha256(path / "input_snapshot" / "phase5g_cases.json") != anchor.get(
        "case_file_sha256"
    ):
        raise ValueError("input_snapshot.phase5g_cases.json: trusted case input differs")
    from experiments.phase5g import _load_development_bundle
    envelope = phase5g_cases._strict_json(raw)
    if envelope.get("schema") == "phase5g_execution_cases_v1":
        bundle = _load_development_bundle(raw)
    else:
        _, physical, _ = parameters("lane_priority")
        speed = envelope["speed_range_mps"]
        bundle = phase5g_cases.load_bundle(
            raw, physical, envelope["case_specs"],
            speed_min_mps=speed[0], speed_max_mps=speed[1],
        )
    compare_tree(bundle["cases"], read_json(path / "frozen_cases.json"), 0.0,
                 "frozen_cases")
    return metadata, bundle, stored_code


def _validate_variant_binding(folder: Path, expected_name: str, expected: dict,
                              case: dict, stored_code: dict) -> None:
    """Bind a physical child to its exact frozen case/mode, independent of seals."""
    from experiments.phase5g import (_initial_memories, _variant_input_sha256,
                                     parameters, source_hashes)
    from experiments.phase5g_cases import digest_json, physical_case

    prefix = f"cases.{expected_name}"
    if folder.name != expected_name:
        raise ValueError(f"{prefix}.directory_name: differs")
    metadata = read_json(folder / "metadata.json")
    stored_case = metadata.get("case", {})
    for field in ("name", "purpose", "expected_lane_changes"):
        if stored_case.get(field) != case.get(field):
            raise ValueError(f"{prefix}.metadata.case.{field}: differs")
    if len(stored_case.get("controlled", ())) != len(case.get("controlled", ())):
        raise ValueError(f"{prefix}.metadata.case.controlled: vehicle count differs")
    stored_seed = stored_case.get("private_rng_provenance", {}).get("case_seed")
    expected_seed = case.get("private_rng_provenance", {}).get("case_seed")
    if stored_seed != expected_seed:
        raise ValueError(f"{prefix}.metadata.case.private_rng_provenance.case_seed: differs")
    compare_tree(case, metadata.get("case"), 0.0, f"{prefix}.metadata.case")
    compare_tree(expected["mode"], metadata.get("mode"), 0.0,
                 f"{prefix}.metadata.mode")
    compare_tree(case["initial"], metadata.get("initial"), 0.0,
                 f"{prefix}.metadata.initial")
    expected_memories = _initial_memories(case, expected["mode"])
    compare_tree(expected_memories, metadata.get("initial_memories"), 0.0,
                 f"{prefix}.metadata.initial_memories")
    compare_tree(case["private_rng_provenance"],
                 metadata.get("private_rng_provenance"), 0.0,
                 f"{prefix}.metadata.private_rng_provenance")
    if metadata.get("physical_input_sha256") != digest_json(physical_case(case)):
        raise ValueError(f"{prefix}.metadata.physical_input_sha256: differs")
    if metadata.get("case_input_sha256") != digest_json(case):
        raise ValueError(f"{prefix}.metadata.case_input_sha256: differs")
    target = metadata.get("parameters", {}).get("noa_target_speed_mps")
    model, physical, policy = parameters(expected["mode"], target)
    compare_tree(dict(model.p), metadata.get("model_parameters"), 0.0,
                 f"{prefix}.metadata.model_parameters")
    compare_tree(physical, metadata.get("parameters"), 0.0,
                 f"{prefix}.metadata.parameters")
    compare_tree(policy, metadata.get("policy_parameters"), 0.0,
                 f"{prefix}.metadata.policy_parameters")
    expected_digest = _variant_input_sha256(
        expected["mode"], case, model, physical, policy, expected_memories,
    )
    if metadata.get("parameters_input_sha256") != expected_digest:
        raise ValueError(f"{prefix}.metadata.parameters_input_sha256: differs")
    expected_sources = source_hashes()
    compare_tree(expected_sources, metadata.get("source_hashes"), 0.0,
                 f"{prefix}.metadata.source_hashes")


def validate_execution_index(expected: dict, started: list, finalized: list,
                             completed: list, *, partial: bool) -> None:
    """Validate attempt coverage without relabeling a finalized physical failure."""
    planned = list(expected)
    for name, values in (("started", started), ("finalized", finalized),
                         ("completed", completed)):
        if not isinstance(values, list) or len(values) != len(set(values)):
            raise ValueError(f"case_index.{name}_variants: duplicate or invalid list")
    if started != planned[:len(started)]:
        raise ValueError("case_index.started_variants: not an execution prefix")
    if finalized != started[:len(finalized)]:
        raise ValueError("case_index.finalized_variants: not a started prefix")
    if any(name not in finalized for name in completed):
        raise ValueError("case_index.completed_variants: contains an unfinalized variant")
    if partial:
        if len(started) - len(finalized) > 1:
            raise ValueError("case_index.finalized_variants: more than one interrupted tail")
    elif started != planned or finalized != planned:
        raise ValueError("case_index.finalized_variants: incomplete declared matrix")


def aggregate_replay_results(expected: dict, cases: list[dict]) -> dict:
    """Separate faithful prefix replay from the complete scientific execution gate."""
    by_name = {row.get("case"): row for row in cases}
    semantic = (len(by_name) == len(cases)
                and set(by_name).issubset(expected)
                and all(row.get("passed") is True for row in cases))
    complete = bool(semantic and set(by_name) == set(expected) and all(
        not row.get("partial_source") and row.get("execution_completed") is True
        for row in cases
    ))
    main = by_name.get("main_6_3_2_1_lane_priority")
    scientific = bool(main and main.get("scientific_passed") is True)
    variant_acceptance_passed = bool(
        set(by_name) == set(expected)
        and all(row.get("recomputed_passed") is True for row in cases)
    )
    source_report_matches = bool(
        semantic and all(
            row.get("source_status") == row.get("recomputed_status")
            and row.get("source_passed") == row.get("recomputed_passed")
            for row in cases
        )
    )
    execution_gate = bool(complete and variant_acceptance_passed and scientific)
    return {
        "semantic_replay_passed": semantic,
        "complete_execution": complete,
        "variant_acceptance_passed": variant_acceptance_passed,
        "source_validation_passed": source_report_matches,
        "execution_gate_passed": execution_gate,
        "scientific_gate_passed": scientific,
        "passed": bool(semantic and execution_gate),
    }


def _replay_run_local(run_dir: str | Path, anchor: dict) -> dict:
    """Execute semantic replay inside the saved code snapshot import namespace."""
    source = Path(run_dir).resolve()
    result = {
        "passed": False, "semantic_replay_passed": False,
        "complete_execution": False, "variant_acceptance_passed": False,
        "source_validation_passed": False,
        "execution_gate_passed": False,
        "scientific_gate_passed": False, "source_run": str(source),
        "errors": [], "cases": [],
    }
    try:
        metadata, bundle, stored_code = _validate_source_run(source, anchor)
        gate = read_json(source / "validation.json")
        from experiments.phase5g import expected_variants
        expected = expected_variants(bundle["cases"])
        index = read_json(source / "case_index.json")
        compare_tree(expected, index.get("expected_variants"), 0.0,
                     "case_index.expected_variants")
        started = index.get("started_variants")
        finalized = index.get("finalized_variants")
        completed = index.get("completed_variants")
        unsealed = index.get("unsealed_variants")
        if not isinstance(unsealed, list) or len(unsealed) != len(set(unsealed)) \
                or any(name not in finalized for name in unsealed):
            raise ValueError("case_index.unsealed_variants: invalid")
        partial = (started != list(expected) or finalized != list(expected))
        validate_execution_index(expected, started, finalized, completed, partial=partial)
        cases_root = source / "cases"
        actual = ({entry.name for entry in cases_root.iterdir() if entry.is_dir()}
                  if cases_root.is_dir() else set())
        required = set(started)
        if actual - required:
            raise ValueError(f"cases: extra variants: {sorted(actual - required)}")
        if required - actual:
            raise ValueError(f"cases: missing variants: {sorted(required - actual)}")
        by_name = {case["name"]: case for case in bundle["cases"]}
        replayed_unsealed = []
        for name in started:
            folder = cases_root / name
            spec = expected[name]
            _validate_variant_binding(folder, name, spec, by_name[spec["case_name"]], stored_code)
            report = replay_variant(folder)
            result["cases"].append({"case": name, **report})
            if read_json(folder / "validation.json").get("sealed") is False:
                replayed_unsealed.append(name)
            if not report["passed"]:
                raise ValueError(f"cases.{name}: {'; '.join(report['errors'])}")
            if name not in gate.get("variants", {}):
                raise ValueError(f"validation.variants.{name}: missing")
            compare_tree(read_json(folder / "validation.json"), gate["variants"][name],
                         0.0, f"validation.variants.{name}")
        if set(gate.get("variants", {})) != set(started):
            raise ValueError("validation.variants: missing or extra variant")
        compare_tree(replayed_unsealed, unsealed, 0.0,
                     "case_index.unsealed_variants")
        aggregate = aggregate_replay_results(expected, result["cases"])
        full_coverage = set(row["case"] for row in result["cases"]) == set(expected)
        engineering = bool(
            not partial and full_coverage
            and all(row.get("recomputed_recording_passed") is True
                    for row in result["cases"])
        )
        scientific = bool(not partial and aggregate["scientific_gate_passed"])
        outer = {
            "status": "failed" if partial else "completed",
            "complete_execution": aggregate["complete_execution"],
            "passed": bool(not partial and aggregate["passed"]),
            "engineering_passed": engineering,
            "scientific_gate_passed": scientific,
            "retained_partial_package": partial,
            "formal": metadata["formal"],
        }
        for field in ("status", "complete_execution", "passed",
                      "engineering_passed", "scientific_gate_passed",
                      "retained_partial_package", "formal"):
            compare_tree(outer[field], gate.get(field), 0.0, f"validation.{field}")
        result.update(aggregate)
        result.update(
            passed=outer["passed"], complete_execution=outer["complete_execution"],
            scientific_gate_passed=outer["scientific_gate_passed"],
            engineering_passed=outer["engineering_passed"],
            partial_source=partial, formal=metadata["formal"],
            unstarted_variants=[name for name in expected if name not in started],
        )
    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
    return result


def _trusted_anchor(source: Path, expected_source_sha256: str | None,
                    expected_input_sha256: str | None) -> dict:
    anchor_path = source.parent / ".phase5g-trust" / f"{source.name}.json"
    if not anchor_path.is_file():
        raise ValueError(f"trust_anchor: missing explicit anchor {anchor_path}")
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    if anchor.get("schema") != "phase5g_external_trust_anchor_v2" \
            or anchor.get("run_id") != source.name:
        raise ValueError("trust_anchor: schema or run_id differs")
    if (expected_source_sha256 is not None
            and anchor.get("source_manifest_sha256") != expected_source_sha256):
        raise ValueError("trust_anchor.source_manifest_sha256: differs from caller anchor")
    if (expected_input_sha256 is not None
            and anchor.get("input_manifest_sha256") != expected_input_sha256):
        raise ValueError("trust_anchor.input_manifest_sha256: differs from caller anchor")
    return anchor


def _preflight_snapshot(source: Path, anchor: dict) -> None:
    """Reject every untrusted snapshot path before it can enter ``sys.path``."""
    from experiments.phase5g import _anchor_digest, snapshot_manifest

    for folder_name, manifest_name, root_name in (
        ("code_snapshot", "code_snapshot_manifest", "source_manifest_sha256"),
        ("input_snapshot", "input_snapshot_manifest", "input_manifest_sha256"),
    ):
        expected = anchor.get(manifest_name)
        if not isinstance(expected, dict):
            raise ValueError(f"trust_anchor.{manifest_name}: missing")
        if _anchor_digest(expected) != anchor.get(root_name):
            raise ValueError(f"trust_anchor.{manifest_name}: root differs")
        actual = snapshot_manifest(source / folder_name, folder_name)
        extra = sorted(set(actual) - set(expected))
        if extra:
            raise ValueError(f"{folder_name} unexpected file: {extra[0]}")
        missing = sorted(set(expected) - set(actual))
        if missing:
            raise ValueError(f"{folder_name} missing file: {missing[0]}")
        for name in sorted(expected):
            if actual[name].get("type") != expected[name].get("type"):
                raise ValueError(f"{folder_name}.{name}: file type differs")
            if actual[name].get("sha256") != expected[name].get("sha256"):
                if folder_name == "code_snapshot" and name in anchor.get("source_hashes", {}):
                    raise ValueError(f"code_hashes.{name}: differs from trusted source")
                if folder_name == "input_snapshot":
                    raise ValueError(f"input_hashes.{name}: differs from trusted input")
                raise ValueError(f"{folder_name}.{name}: hash differs")


def replay_run(run_dir: str | Path, *, base: str | Path | None = None,
               expected_source_sha256: str | None = None,
               expected_input_sha256: str | None = None) -> dict:
    """Launch replay from the run's saved source, anchored outside the resealable package."""
    if run_dir is None:
        raise ValueError("phase5g replay requires an explicit run_dir")
    if bool(expected_source_sha256) != bool(expected_input_sha256):
        raise ValueError("expected source/input SHA-256 roots must be supplied together")
    source = Path(run_dir).resolve()
    if not source.is_dir():
        raise ValueError("phase5g replay requires an explicit existing run_dir")
    from experiments.phase5g import _validated_output_base, seal_directory
    destination = _validated_output_base(base or ROOT / "results/phase5g/replays")
    if destination.is_relative_to(source):
        raise ValueError("replay output must be outside its sealed source")
    anchor = _trusted_anchor(source, expected_source_sha256, expected_input_sha256)
    trust_model = ("caller_supplied_source_and_input_roots"
                   if expected_source_sha256 else
                   "sibling_anchor_only_not_whole-package-tamper-resistant")
    result = {
        "passed": False, "semantic_replay_passed": False,
        "complete_execution": False, "variant_acceptance_passed": False,
        "source_validation_passed": False,
        "execution_gate_passed": False,
        "scientific_gate_passed": False, "source_run": str(source),
        "errors": [], "cases": [], "trust_model": trust_model,
    }
    try:
        _preflight_snapshot(source, anchor)
    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
        result["path"] = None
        return result
    replay = RunRecord(destination, {
        "purpose": "Phase 5G saved-snapshot semantic replay",
        "schema": "phase5g_replay_v2", "source_run": str(source),
        "source_manifest_sha256": anchor["source_manifest_sha256"],
        "input_manifest_sha256": anchor["input_manifest_sha256"],
        "trust_model": trust_model,
        "command_line": sys.argv, "python": sys.version,
    })
    try:
        with replay:
            shutil.copy2(Path(__file__), replay.path / "launcher_snapshot.py")
            output = replay.path / "snapshot_result.json"
            anchor_copy = replay.path / "trusted_anchor.json"
            atomic_anchor = json.dumps(anchor, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":"), allow_nan=False)
            anchor_copy.write_text(atomic_anchor + "\n", encoding="utf-8")
            snapshot = source / "code_snapshot"
            purelib = sysconfig.get_path("purelib")
            driver = (
                "import json,sys;from pathlib import Path;"
                f"sys.path.insert(0,{str(snapshot)!r});sys.path.append({purelib!r});"
                "from experiments.phase5g_replay import _replay_run_local;"
                f"a=json.loads(Path({str(anchor_copy)!r}).read_text(encoding='utf-8'));"
                f"r=_replay_run_local(Path({str(source)!r}),a);"
                f"Path({str(output)!r}).write_text(json.dumps(r,allow_nan=False),encoding='utf-8')"
            )
            completed = subprocess.run(
                [sys.executable, "-I", "-B", "-S", "-c", driver],
                cwd=snapshot, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300,
            )
            (replay.path / "snapshot_stdout.log").write_text(completed.stdout, encoding="utf-8")
            (replay.path / "snapshot_stderr.log").write_text(completed.stderr, encoding="utf-8")
            if completed.returncode:
                result["errors"].append(
                    f"snapshot_process: exit {completed.returncode}: {completed.stderr[-1000:]}"
                )
            elif not output.is_file():
                result["errors"].append("snapshot_process: result missing")
            else:
                result = json.loads(output.read_text(encoding="utf-8"))
                result["trust_model"] = trust_model
            replay.finish(result)
    finally:
        if replay.path.is_dir():
            seal_directory(replay.path)
    result["path"] = str(replay.path)
    print(json.dumps({"path": result["path"], "passed": result["passed"],
                      "semantic_replay_passed": result["semantic_replay_passed"],
                      "scientific_gate_passed": result["scientific_gate_passed"]}), flush=True)
    return result
