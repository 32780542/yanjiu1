"""Retained offline validation matrix for the local-tail formation demo."""

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from experiments.phase5g import (
    SIMPLE_DEMO_COMPLETION_SCHEMA,
    _prepare_output_directory,
    _require_output_directory,
    _require_output_regular_file,
    _validated_output_base,
    atomic_json,
    run_phase5g_demo,
)
from experiments.phase5g_replay import replay_run
from research.common import native_io_path, sha256


MATRIX_COUNTS = (3, 6, 12)
MATRIX_SEEDS = (1, 2, 3, 4, 5)
MATRIX_SPECS = tuple(
    (count, seed) for count in MATRIX_COUNTS for seed in MATRIX_SEEDS
)

_DEFAULT_RUN = {
    "target_speed_mps": 10.0,
    "duration_s": 90.0,
    "depart_interval_min_s": 2.5,
    "depart_interval_max_s": 4.0,
    "initial_speed_min_mps": 8.0,
    "initial_speed_max_mps": 12.0,
    "formation_join_range_m": 50.0,
    "middle_lane_offset_m": 15.0,
    "same_lane_gap_m": 30.0,
    "position_tolerance_m": 2.0,
    "speed_tolerance_mps": 1.0,
    "stable_time_s": 1.0,
    "reference_switch_gain_m": 2.0,
    "min_formation_lane_change_speed_mps": 5.0,
    "hard_lane_change_gap_m": 8.0,
    "mode": "lane_priority",
    "formal": False,
    "live": False,
}

_GAP_RUN = {
    **_DEFAULT_RUN,
    "vehicle_count": 6,
    "seed": 627052,
    "depart_interval_min_s": 2.5,
    "depart_interval_max_s": 20.0,
    "expected_component_count": 2,
}

_MAX_LATEST_JSON_BYTES = 64 * 1024
_MAX_DETECTION_JSON_BYTES = 64 * 1024 * 1024
_MAX_TRUST_JSON_BYTES = 1024 * 1024
_MAX_ERROR_TEXT_CHARS = 4096


def _matrix_directory(base: str | Path) -> Path:
    root = _validated_output_base(base)
    _prepare_output_directory(root)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "_" + uuid4().hex[:8]
    )
    return _prepare_output_directory(root / run_id, exclusive=True)


def _read_strict_json_object(path: Path, *, limit: int, label: str) -> dict:
    checked = _require_output_regular_file(path)
    with open(native_io_path(checked), "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"{label} exceeds size limit of {limit} bytes")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(token):
        raise ValueError(f"{label} contains nonfinite JSON constant: {token}")

    def finite_float(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError(f"{label} contains nonfinite JSON number: {token}")
        return value

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique,
            parse_constant=reject_constant, parse_float=finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be one JSON object")
    return value


def _is_json_text(value: object, *, nonempty: bool = False) -> bool:
    if type(value) is not str or (nonempty and not value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _safe_text(value: object, *, fallback: str = "<unprintable value>") -> str:
    try:
        rendered = str(value)
    except MemoryError:
        raise
    except Exception:
        try:
            rendered = repr(value)
        except MemoryError:
            raise
        except Exception:
            rendered = fallback
    if type(rendered) is not str:
        rendered = fallback
    rendered = rendered[:_MAX_ERROR_TEXT_CHARS]
    return rendered.encode("utf-8", "backslashreplace").decode("utf-8")


def _safe_exception_text(error: Exception, *, label: object | None = None) -> str:
    type_name = _safe_text(type(error).__name__, fallback="Exception")
    detail = _safe_text(error, fallback="<unprintable exception>")
    message = type_name + ": " + detail
    if label is not None:
        message = _safe_text(label) + ": " + message
    return message


def _recovery_error(errors: list[str], label: str, error: Exception) -> None:
    errors.append(_safe_exception_text(error, label=label))


def _trusted_recovery_artifact(run_path: Path, run_base: Path) -> Path:
    """Accept a sealed completed or explicitly finalized failed run only."""
    checked = _bound_output_child(run_path, run_base, "retained demo")
    trust = _require_output_directory(run_base / ".phase5g-trust")
    source = _read_strict_json_object(
        trust / f"{checked.name}.json", limit=_MAX_TRUST_JSON_BYTES,
        label="retained source anchor",
    )
    if source.get("schema") != "phase5g_external_trust_anchor_v2" \
            or source.get("run_id") != checked.name:
        raise ValueError("retained source anchor schema/run_id differs")

    validation_path = checked / "validation.json"
    validation = _read_strict_json_object(
        validation_path, limit=_MAX_TRUST_JSON_BYTES,
        label="retained validation",
    )
    if validation.get("run_id") != checked.name \
            or validation.get("status") not in {"completed", "failed"} \
            or type(validation.get("passed")) is not bool:
        raise ValueError("retained validation is not explicitly finalized")
    if validation["status"] == "failed" and validation["passed"] is not False:
        raise ValueError("failed retained validation must not pass")

    evidence = _read_strict_json_object(
        checked / "evidence_hashes.json", limit=_MAX_TRUST_JSON_BYTES,
        label="retained evidence seal",
    )
    validation_digest = evidence.get("validation.json")
    if type(validation_digest) is not str \
            or validation_digest != sha256(validation_path):
        raise ValueError("retained evidence seal does not bind validation.json")

    if validation["status"] == "completed":
        completion = _read_strict_json_object(
            trust / f"{checked.name}.completion.json",
            limit=_MAX_TRUST_JSON_BYTES, label="retained completion anchor",
        )
        if completion.get("schema") != SIMPLE_DEMO_COMPLETION_SCHEMA \
                or completion.get("run_id") != checked.name:
            raise ValueError("retained completion anchor schema/run_id differs")
    return checked


def _retained_run_path(run_base: Path,
                       errors: list[str] | None = None) -> Path | None:
    """Best-effort recovery of one safe finalized child; ordinary errors stay local."""
    diagnostics = [] if errors is None else errors
    try:
        checked_base = _require_output_directory(run_base)
    except MemoryError:
        raise
    except Exception as error:
        _recovery_error(diagnostics, "run base", error)
        return None

    candidates = []
    latest = checked_base / "latest.json"
    try:
        os.lstat(native_io_path(latest))
    except FileNotFoundError:
        pass
    except MemoryError:
        raise
    except Exception as error:
        _recovery_error(diagnostics, "latest", error)
    else:
        try:
            value = _read_strict_json_object(
                latest, limit=_MAX_LATEST_JSON_BYTES, label="latest",
            )
            candidate_value = value.get("path")
            if type(candidate_value) is not str or not candidate_value.strip():
                raise ValueError("latest.path must be a nonempty string")
            candidates.append(Path(candidate_value))
        except MemoryError:
            raise
        except Exception as error:
            _recovery_error(diagnostics, "latest", error)

    try:
        children = sorted(
            checked_base.iterdir(), key=lambda item: item.name, reverse=True,
        )
    except MemoryError:
        raise
    except Exception as error:
        _recovery_error(diagnostics, "run directory enumeration", error)
        children = []
    candidates.extend(
        item for item in children
        if item.name not in {".phase5g-trust", "latest.json"}
    )

    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            return _trusted_recovery_artifact(candidate, checked_base)
        except MemoryError:
            raise
        except Exception as error:
            _recovery_error(diagnostics, f"retained candidate {candidate}", error)
    return None


def _bound_output_child(value: object, base: Path, label: str) -> Path:
    if not isinstance(value, (str, Path)):
        raise ValueError(f"{label} returned path must be a path string")
    candidate = Path(value)
    checked_base = _require_output_directory(base)
    if candidate.is_absolute():
        lexical_candidate = Path(candidate)
    else:
        lexical_candidate = checked_base / candidate
    if lexical_candidate.parent != checked_base:
        raise ValueError(f"{label} returned path outside its unique output base")
    checked = _require_output_directory(lexical_candidate)
    if checked.resolve().parent != checked_base.resolve():
        raise ValueError(f"{label} returned path escaped its unique output base")
    return checked


def _bound_returned_run_path(value: object, run_base: Path) -> Path:
    return _bound_output_child(value, run_base, "demo")


def _scientific_status(run_path: Path | None,
                       expected_component_count: int) -> dict:
    status = {
        "evaluated": False,
        "passed": False,
        "expected_component_count": expected_component_count,
        "expected_component_members": [],
        "final_component_lane_counts": [],
        "failure_reasons": [],
    }
    if run_path is None:
        status["failure_reasons"].append("run_artifact_missing")
        return status
    try:
        detection = _read_strict_json_object(
            run_path / "case" / "detection.json",
            limit=_MAX_DETECTION_JSON_BYTES, label="detection",
        )
        default = detection.get("default")
        if not isinstance(default, dict):
            raise ValueError("detection.default must be an object")
        success = default["success"]
        reasons = default["failure_reasons"]
        parameters = default.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError("detection.default.parameters must be an object")
        recorded_count = parameters.get("expected_component_count")
        if type(success) is not bool:
            raise ValueError("detection.default.success must be bool")
        if not isinstance(reasons, list) or any(
                not _is_json_text(reason) for reason in reasons):
            raise ValueError(
                "detection.default.failure_reasons must be UTF-8 strings"
            )
        if success and reasons:
            raise ValueError("successful detection must have no failure reasons")
        if type(recorded_count) is not int or recorded_count <= 0:
            raise ValueError(
                "detection expected_component_count must be an exact positive int"
            )
        if recorded_count != expected_component_count:
            raise ValueError("detection expected_component_count differs")
        component_members = default.get("expected_component_members")
        component_counts = default.get("final_component_lane_counts")
        if not isinstance(component_members, list):
            raise ValueError("detection component members must be a list")
        if not isinstance(component_counts, list):
            raise ValueError("detection lane counts must be a list")
        if len(component_members) != len(component_counts):
            raise ValueError(
                "detection component members and lane counts must align"
            )
        if success and len(component_members) != expected_component_count:
            raise ValueError(
                "successful detection components must match expected count"
            )
        all_members = []
        for index, (members, counts) in enumerate(zip(
                component_members, component_counts)):
            if not isinstance(members, list) or not members \
                    or any(not _is_json_text(member, nonempty=True)
                           for member in members):
                raise ValueError(
                    f"detection component {index} members must be nonempty "
                    "UTF-8 strings"
                )
            if len(set(members)) != len(members):
                raise ValueError(
                    f"detection component {index} contains duplicate members"
                )
            if not isinstance(counts, list) or len(counts) != 3 \
                    or any(type(count) is not int or count < 0
                           for count in counts):
                raise ValueError(
                    f"detection component {index} lane counts must be "
                    "three nonnegative exact integers"
                )
            if sum(counts) != len(members):
                raise ValueError(
                    f"detection component {index} member/lane totals differ"
                )
            all_members.extend(members)
        if len(set(all_members)) != len(all_members):
            raise ValueError("detection members overlap between components")
        status.update(
            evaluated=True, passed=success,
            expected_component_members=component_members,
            final_component_lane_counts=component_counts,
            failure_reasons=list(reasons),
        )
        if not success and not status["failure_reasons"]:
            status["failure_reasons"].append(
                "scientific_evaluation_not_passed"
            )
    except MemoryError:
        raise
    except Exception as error:
        status["failure_reasons"].append(
            _safe_exception_text(error)
        )
    return status


def _replay_status(run_path: Path | None, replay_base: Path,
                   replay: Callable[..., Mapping[str, object]]) -> dict:
    status = {
        "attempted": False, "passed": False, "path": None, "errors": [],
    }
    if run_path is None:
        status["errors"].append("run_artifact_missing")
        return status
    reported_errors = []
    try:
        result = replay(run_path, base=replay_base)
        if not isinstance(result, Mapping) or type(result.get("passed")) is not bool:
            raise ValueError("replay result must contain exact bool passed")
        errors = result.get("errors", [])
        if not isinstance(errors, list) or any(
                not _is_json_text(error) for error in errors):
            raise ValueError("replay result errors must be a UTF-8 string list")
        reported_errors = list(errors)
        path = result.get("path")
        if path is not None and not isinstance(path, (str, Path)):
            raise ValueError("replay result path must be a path string or null")
        if path is None:
            if result["passed"]:
                raise ValueError("passed replay result requires its retained path")
            checked_path = None
        else:
            checked_path = _bound_output_child(path, replay_base, "replay")
        if result["passed"] and reported_errors:
            raise ValueError("passed replay result must have no errors")
        status.update(
            attempted=True, passed=result["passed"],
            path=None if checked_path is None else str(checked_path),
            errors=reported_errors,
        )
        if not result["passed"] and not status["errors"]:
            status["errors"].append("replay_not_passed")
    except MemoryError:
        raise
    except Exception as error:
        status.update(
            attempted=True, passed=False,
            errors=[
                *reported_errors,
                _safe_exception_text(error),
            ],
        )
    return status


def _attempt(*, count: int, seed: int, run_base: Path, replay_base: Path,
             expected_component_count: int,
             options: Mapping[str, object],
             demo: Callable[..., Path],
             replay: Callable[..., Mapping[str, object]]) -> dict:
    run_path = None
    execution_error = None
    recovery_errors = []
    try:
        returned = demo(
            vehicle_count=count, seed=seed, output_base=run_base, **options,
        )
        run_path = _bound_returned_run_path(returned, run_base)
    except MemoryError:
        raise
    except Exception as error:
        execution_error = _safe_exception_text(error)
        try:
            run_path = _retained_run_path(run_base, recovery_errors)
        except MemoryError:
            raise
        except Exception as recovery_error:
            recovery_errors.append(
                _safe_exception_text(recovery_error)
            )

    scientific = _scientific_status(run_path, expected_component_count)
    replay_status = _replay_status(run_path, replay_base, replay)
    reasons = []
    if execution_error is not None:
        reasons.append(execution_error)
    reasons.extend(recovery_errors)
    reasons.extend(scientific["failure_reasons"])
    reasons.extend(replay_status["errors"])
    passed = bool(
        execution_error is None
        and scientific["passed"] is True
        and replay_status["passed"] is True
    )
    return {
        "count": count,
        "seed": seed,
        "run_path": None if run_path is None else str(run_path),
        "execution_error": execution_error,
        "recovery_errors": recovery_errors,
        "replay_status": replay_status,
        "scientific_status": scientific,
        "passed": passed,
        "failure_reasons": reasons,
    }


def _failure_rows(runs: list[dict], gap_case: dict) -> list[dict]:
    rows = []
    for kind, items in (("matrix", runs), ("gap_case", [gap_case])):
        for item in items:
            execution_error = item.get("execution_error")
            if execution_error is not None:
                rows.append({
                    "kind": kind, "count": item["count"], "seed": item["seed"],
                    "source": "execution", "reason": execution_error,
                })
            for reason in item.get("recovery_errors", []):
                rows.append({
                    "kind": kind, "count": item["count"], "seed": item["seed"],
                    "source": "recovery", "reason": reason,
                })
            for reason in item["scientific_status"]["failure_reasons"]:
                rows.append({
                    "kind": kind, "count": item["count"], "seed": item["seed"],
                    "source": "scientific", "reason": reason,
                })
            for reason in item["replay_status"]["errors"]:
                rows.append({
                    "kind": kind, "count": item["count"], "seed": item["seed"],
                    "source": "replay", "reason": reason,
                })
    return rows


def run_matrix(output_base: str | Path, *, live: bool = False,
               demo_runner: Callable[..., Path] | None = None,
               replay_runner: Callable[..., Mapping[str, object]] | None = None
               ) -> Path:
    """Run and replay the immutable 15-case matrix plus one two-component case."""
    if live is not False:
        raise ValueError("phase5g-simple-matrix requires live=false/offline execution")
    demo = run_phase5g_demo if demo_runner is None else demo_runner
    replay = replay_run if replay_runner is None else replay_runner
    if not callable(demo) or not callable(replay):
        raise ValueError("demo_runner and replay_runner must be callable")

    matrix_path = _matrix_directory(output_base)
    runs = []
    for count, seed in MATRIX_SPECS:
        label = f"count-{count:02d}-seed-{seed:02d}"
        runs.append(_attempt(
            count=count, seed=seed,
            run_base=matrix_path / "runs" / label,
            replay_base=matrix_path / "replays" / label,
            expected_component_count=1,
            options=_DEFAULT_RUN,
            demo=demo, replay=replay,
        ))

    gap_case = _attempt(
        count=_GAP_RUN["vehicle_count"], seed=_GAP_RUN["seed"],
        run_base=matrix_path / "gap_case" / "two-components",
        replay_base=matrix_path / "gap_replay" / "two-components",
        expected_component_count=_GAP_RUN["expected_component_count"],
        options={key: value for key, value in _GAP_RUN.items()
                 if key not in {"vehicle_count", "seed"}},
        demo=demo, replay=replay,
    )
    pass_count = sum(item["passed"] for item in runs)
    total_count = len(MATRIX_SPECS)
    aggregate = {
        "schema": "phase5g_local_tail_matrix_v1",
        "matrix_specs": [list(spec) for spec in MATRIX_SPECS],
        "runs": runs,
        "gap_case": gap_case,
        "pass_count": pass_count,
        "total_count": total_count,
        "pass_rate": pass_count / total_count,
        "matrix_passed": pass_count == total_count,
        "gap_case_passed": gap_case["passed"],
        "passed": bool(pass_count == total_count and gap_case["passed"]),
        "failure_reasons": _failure_rows(runs, gap_case),
    }
    atomic_json(matrix_path / "aggregate.json", aggregate)
    return matrix_path
