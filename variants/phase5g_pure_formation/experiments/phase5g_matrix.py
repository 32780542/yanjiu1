"""Retained offline validation matrix for the local-tail formation demo."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from experiments.phase5g import (
    _prepare_output_directory,
    _require_output_directory,
    _validated_output_base,
    atomic_json,
    run_phase5g_demo,
)
from experiments.phase5g_replay import replay_run


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
    "seed": 1432,
    "depart_interval_min_s": 2.5,
    "depart_interval_max_s": 20.0,
    "expected_component_count": 2,
}


def _matrix_directory(base: str | Path) -> Path:
    root = _validated_output_base(base)
    _prepare_output_directory(root)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "_" + uuid4().hex[:8]
    )
    return _prepare_output_directory(root / run_id, exclusive=True)


def _retained_run_path(run_base: Path) -> Path | None:
    """Locate only a child artifact retained by the attempted demo call."""
    if not run_base.is_dir():
        return None
    latest = run_base / "latest.json"
    candidates = []
    if latest.is_file():
        try:
            value = json.loads(latest.read_text(encoding="utf-8"))
            candidate = Path(value.get("path", ""))
            if not candidate.is_absolute():
                candidate = run_base / candidate
            candidates.append(candidate)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    candidates.extend(sorted(
        (item for item in run_base.iterdir()
         if item.is_dir() and item.name != ".phase5g-trust"),
        key=lambda item: item.name,
        reverse=True,
    ))
    resolved_base = run_base.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved.parent == resolved_base:
            return resolved
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
        detection = json.loads(
            (run_path / "case" / "detection.json").read_text(encoding="utf-8")
        )
        default = detection["default"]
        success = default["success"]
        reasons = default["failure_reasons"]
        recorded_count = default["parameters"]["expected_component_count"]
        if type(success) is not bool:
            raise ValueError("detection.default.success must be bool")
        if not isinstance(reasons, list) or any(
                type(reason) is not str for reason in reasons):
            raise ValueError("detection.default.failure_reasons must be strings")
        if recorded_count != expected_component_count:
            raise ValueError("detection expected_component_count differs")
        component_members = default.get("expected_component_members", [])
        component_counts = default.get("final_component_lane_counts", [])
        if not isinstance(component_members, list) \
                or not isinstance(component_counts, list):
            raise ValueError("detection component evidence must be lists")
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
            f"{type(error).__name__}: {error}"
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
    try:
        result = replay(run_path, base=replay_base)
        if not isinstance(result, Mapping) or type(result.get("passed")) is not bool:
            raise ValueError("replay result must contain exact bool passed")
        errors = result.get("errors", [])
        if not isinstance(errors, list) or any(type(error) is not str for error in errors):
            raise ValueError("replay result errors must be a string list")
        path = result.get("path")
        if path is not None and not isinstance(path, (str, Path)):
            raise ValueError("replay result path must be a path string or null")
        if path is None:
            if result["passed"]:
                raise ValueError("passed replay result requires its retained path")
            checked_path = None
        else:
            checked_path = _bound_output_child(path, replay_base, "replay")
        status.update(
            attempted=True, passed=result["passed"],
            path=None if checked_path is None else str(checked_path),
            errors=list(errors),
        )
        if not result["passed"] and not status["errors"]:
            status["errors"].append("replay_not_passed")
    except MemoryError:
        raise
    except Exception as error:
        status.update(
            attempted=True,
            errors=[f"{type(error).__name__}: {error}"],
        )
    return status


def _attempt(*, count: int, seed: int, run_base: Path, replay_base: Path,
             expected_component_count: int,
             options: Mapping[str, object],
             demo: Callable[..., Path],
             replay: Callable[..., Mapping[str, object]]) -> dict:
    run_path = None
    execution_error = None
    try:
        returned = demo(
            vehicle_count=count, seed=seed, output_base=run_base, **options,
        )
        run_path = _bound_returned_run_path(returned, run_base)
    except MemoryError:
        raise
    except Exception as error:
        execution_error = f"{type(error).__name__}: {error}"
        run_path = _retained_run_path(run_base)

    scientific = _scientific_status(run_path, expected_component_count)
    replay_status = _replay_status(run_path, replay_base, replay)
    reasons = []
    if execution_error is not None:
        reasons.append(execution_error)
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
