"""Paired Phase 5G pure-formation execution and independent factual summaries."""

from copy import deepcopy
from dataclasses import asdict, fields
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import traceback
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import uuid4

from experiments.phase3 import NET
from experiments.phase3_audit import geometry_report
from experiments.phase4_audit import driving_metrics
from experiments.phase4_bootstrap import bootstrap
from experiments.phase5_detection import detect_frames
from models.vehicle import VehicleState
from noa import simple_formation
from perception.road import VisibleRoad
from research.common import (
    ROOT, code_manifest, native_io_path, output_path, read_json, regular_file,
    settings, sha256,
)
from safety.geometry import RoadEnvelope
from simulation.phase5g_clock import (
    CLOCK_SCHEMA,
    Phase5GClock,
    initial_memory_hash,
    neutral_phase5g_memories,
)


_MODE_SPECS = (
    ("off", False, False),
    ("longitudinal", True, False),
    ("lane_priority", True, True),
)
MODES = MappingProxyType({
    name: MappingProxyType({
        "formation_enabled": formation,
        "formation_lane_change_enabled": lane_change,
    })
    for name, formation, lane_change in _MODE_SPECS
})
SUMMARY_KEYS = (
    "whole_cohort_formation_success", "formed_time_s", "held_time_s",
    "completed_lane_changes", "formation_lane_changes", "final_lane_counts",
    "minimum_speed_mps", "final_speed_spread_mps", "speed_recovered",
    "collision_count", "geometry_passed", "comfort_passed",
)
FORMATION_LANE_REASONS = frozenset((
    "formation_geometry", "simple_formation_balance",
))
SOURCE_FILES = (
    "run.py",
    "configs/phase5g.json",
    "experiments/phase5g.py",
    "experiments/phase5g_cases.py",
    "experiments/phase5g_replay.py",
    "experiments/phase5_detection.py",
    "noa/controller.py",
    "noa/formation.py",
    "noa/formation_lane.py",
    "noa/simple_formation.py",
    "simulation/noa_clock.py",
    "simulation/phase5g_clock.py",
    "docs/superpowers/specs/2026-09-14-phase5g-simple-local-ifelse-formation-design.md",
    "docs/superpowers/plans/2026-09-14-phase5g-simple-local-ifelse-formation.md",
)
INPUTS = (
    "scenarios/cai2024/bottleneck.net.xml",
    "docs/parameter_registry.csv",
    "docs/phase5g_pure_formation_plan.md",
    "docs/superpowers/specs/2026-09-14-phase5g-pure-formation-design.md",
    "docs/superpowers/plans/2026-09-14-phase5g-pure-formation.md",
    "docs/superpowers/specs/2026-09-14-phase5g-simple-local-ifelse-formation-design.md",
    "docs/superpowers/plans/2026-09-14-phase5g-simple-local-ifelse-formation.md",
    "configs/phase5g.json",
)
SIMPLE_DEMO_INPUT_SCHEMA = "phase5g_simple_demo_cases_v1"
SIMPLE_DEMO_EXECUTION_SCHEMA = "phase5g_simple_demo_execution_v1"
SIMPLE_DEMO_INDEX_SCHEMA = "phase5g_simple_demo_index_v1"
SIMPLE_DEMO_COMPLETION_SCHEMA = "phase5g_simple_demo_completion_anchor_v1"
_TRACE_DEPARTURE_FIELDS = frozenset((
    "scheduled_departure_s", "actual_departure_s", "state", "physical_ordinal",
))
_TRACE_STATE_FIELDS = frozenset(field.name for field in fields(VehicleState))
_TRACE_ACTOR_MAP_FIELDS = (
    "inputs", "decisions", "actions", "steps", "diagnostics",
)


def atomic_json(path: str | Path, data: object) -> None:
    """Atomic JSON writer scoped to already validated Phase 5G artifact paths."""
    _atomic_output_json(path, data, ".writing")


def _finalizer_json(path: str | Path, data: object) -> None:
    """Minimal atomic writer kept independent from derived-evidence persistence."""
    _atomic_output_json(path, data, ".finalizing")


def _produced_evidence(path: Path) -> list[str]:
    return sorted(
        file.relative_to(path).as_posix()
        for file in path.rglob("*")
        if file.is_file() and file.name not in {
            "evidence_hashes.json", "unsealed_evidence_hashes.json",
        }
    )


def _write_unsealed_manifest(path: Path) -> None:
    """Bind every raw child file when normal child sealing itself failed."""
    _finalizer_json(path / "unsealed_evidence_hashes.json", {
        name: sha256(path / name)
        for name in _produced_evidence(path)
    })


class Phase5GRunRecord:
    """Append-only record supporting project results and explicit system Temp bases."""
    def __init__(self, base: str | Path, metadata: dict):
        self.base = _validated_output_base(base)
        self.run_id = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                       + "_" + uuid4().hex[:8])
        self.path = self.base / self.run_id
        self.metadata = metadata
        self.finished = False

    def __enter__(self):
        self.base = _prepare_output_directory(self.base)
        _prepare_output_directory(self.base / ".phase5g-trust")
        self.path = _prepare_output_directory(self.path, exclusive=True)
        self._save({"passed": False, "status": "running"})
        try:
            atomic_json(self.path / "metadata.json", {**self.metadata, "run_id": self.run_id})
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise
        return self

    def _save(self, result: dict) -> None:
        atomic_json(self.path / "validation.json", {**result, "run_id": self.run_id})
        atomic_json(self.base / "latest.json", {
            "run_id": self.run_id, "path": str(self.path),
            "status": result["status"], "passed": result["passed"],
        })

    def finish(self, result: dict) -> None:
        self._save({**result, "status": "completed"})
        self.finished = True

    def __exit__(self, kind, error, tb):
        if error is not None:
            self._save({
                "passed": False, "status": "failed",
                "error": f"{kind.__name__}: {error}",
                "traceback": "".join(traceback.format_exception(kind, error, tb)),
            })
        elif not self.finished:
            self._save({"passed": False, "status": "failed", "error": "Run not finalized"})
            raise RuntimeError("Run not finalized")
        return False


RunRecord = Phase5GRunRecord


def _strict_mode(mode: object) -> str:
    if type(mode) is not str or mode not in {item[0] for item in _MODE_SPECS}:
        raise ValueError("mode must be exactly off, longitudinal, or lane_priority")
    return mode


def _mode_flags(mode: str) -> dict[str, bool]:
    checked = _strict_mode(mode)
    return {
        "formation_enabled": next(row[1] for row in _MODE_SPECS if row[0] == checked),
        "formation_lane_change_enabled": next(row[2] for row in _MODE_SPECS if row[0] == checked),
    }


def _mode_registry() -> dict[str, dict[str, bool]]:
    return {name: _mode_flags(name) for name, _, _ in _MODE_SPECS}


def _output_target_and_boundary(value: str | Path) -> tuple[Path, Path]:
    """Normalize one allowed output path lexically, without following it."""
    if not isinstance(value, (str, Path)) or (isinstance(value, str) and not value.strip()):
        raise ValueError("output_base must be a nonempty safe results or temporary directory")
    raw = Path(value)
    if str(raw).strip() in ("", "."):
        raise ValueError("output_base must not be the project directory")
    lexical = ROOT / raw if not raw.is_absolute() else raw
    target = Path(os.path.abspath(lexical))
    if target == Path(target.anchor) or target in (ROOT, ROOT.parent):
        raise ValueError("output_base must not be a filesystem, workspace, or project root")
    temp_roots = {Path(tempfile.gettempdir()).resolve()}
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        temp_roots.add((Path(local_app_data) / "Temp").resolve())
    boundary = None
    if target.is_relative_to(ROOT):
        relative = target.relative_to(ROOT)
        if relative.parts and relative.parts[0] in ("results", "tmp"):
            boundary = ROOT
    if boundary is None and (
            not raw.is_absolute() or lexical.is_relative_to(ROOT)):
        raise ValueError(
            "output_base escaped the project results/tmp boundary")
    if boundary is None:
        boundary = next((root for root in temp_roots
                         if target != root and target.is_relative_to(root)), None)
    if boundary is None:
        raise ValueError("output_base must be under project results/tmp or the system Temp directory")
    return target, boundary


def _inspect_output_directory(
        target: Path, boundary: Path, *, create: bool,
        require_existing: bool, exclusive: bool = False) -> Path:
    """Best-effort local defense against deterministic path replacement.

    Python on Windows cannot make the whole walk atomic without directory-handle
    relative APIs.  Each existing or newly created component is nevertheless
    lstat-checked and containment-checked immediately before later mutations.
    """
    resolved_boundary = boundary.resolve(strict=True)
    current = boundary
    components = (None, *target.relative_to(boundary).parts)
    for index, part in enumerate(components):
        if part is not None:
            current /= part
        existed = True
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            existed = False
            if not create:
                if require_existing:
                    raise ValueError(f"output_base directory missing: {current}")
                return target
            current.mkdir(exist_ok=False)
            info = os.lstat(current)
        if existed and exclusive and index == len(components) - 1:
            raise FileExistsError(current)
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = bool(
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if current.is_symlink() or reparse:
            raise ValueError(f"output_base reparse point forbidden: {current}")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("output_base must be a directory, not a file")
        resolved_current = current.resolve(strict=True)
        if resolved_current != resolved_boundary \
                and not resolved_current.is_relative_to(resolved_boundary):
            raise ValueError("output_base resolved outside its allowed boundary")
    return target


def _validated_output_base(value: str | Path) -> Path:
    """Validate a narrow output base without creating or resolving its target."""
    target, boundary = _output_target_and_boundary(value)
    return _inspect_output_directory(
        target, boundary, create=False, require_existing=False)


def _prepare_output_directory(
        value: str | Path, *, exclusive: bool = False) -> Path:
    """Create missing output ancestry one checked component at a time."""
    target, boundary = _output_target_and_boundary(value)
    return _inspect_output_directory(
        target, boundary, create=True, require_existing=True,
        exclusive=exclusive)


def _require_output_directory(value: str | Path) -> Path:
    target, boundary = _output_target_and_boundary(value)
    return _inspect_output_directory(
        target, boundary, create=False, require_existing=True)


def _checked_mutation_target(path: str | Path, staging_suffix: str) -> tuple[Path, Path]:
    target = Path(os.path.abspath(path))
    _require_output_directory(target.parent)
    staging = target.with_name(target.name + staging_suffix)
    try:
        info = os.lstat(target)
    except FileNotFoundError:
        pass
    else:
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = bool(
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if target.is_symlink() or reparse or not stat.S_ISREG(info.st_mode):
            raise ValueError(f"output mutation target must be a regular file: {target}")
    try:
        os.lstat(staging)
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError(staging)
    return target, staging


def _file_identity(info) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _cleanup_owned_staging(staging: Path, identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    try:
        info = os.lstat(staging)
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = bool(
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if not staging.is_symlink() and not reparse \
                and stat.S_ISREG(info.st_mode) \
                and _file_identity(info) == identity:
            staging.unlink()
    except OSError:
        pass


def _atomic_output_json(path: str | Path, data: object, staging_suffix: str) -> None:
    payload = json.dumps(
        data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    target, staging = _checked_mutation_target(path, staging_suffix)
    identity = None
    try:
        with open(
            native_io_path(staging), "x", encoding="utf-8", newline="\n"
        ) as stream:
            identity = _file_identity(os.fstat(stream.fileno()))
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _require_output_directory(target.parent)
        info = os.lstat(native_io_path(staging))
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = bool(
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if staging.is_symlink() or reparse or not stat.S_ISREG(info.st_mode) \
                or _file_identity(info) != identity:
            raise ValueError("output staging file changed before atomic replace")
        os.replace(native_io_path(staging), native_io_path(target))
        identity = None
    except BaseException:
        _cleanup_owned_staging(staging, identity)
        raise


def _write_new_output_bytes(path: str | Path, payload: bytes) -> Path:
    target = Path(os.path.abspath(path))
    _require_output_directory(target.parent)
    try:
        os.lstat(target)
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError(target)
    _require_output_directory(target.parent)
    with open(native_io_path(target), "xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return target


def _require_output_regular_file(path: str | Path) -> Path:
    target = Path(os.path.abspath(path))
    _require_output_directory(target.parent)
    try:
        info = os.lstat(target)
    except FileNotFoundError as error:
        raise ValueError(f"output file missing: {target}") from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    if target.is_symlink() or reparse or not stat.S_ISREG(info.st_mode):
        raise ValueError(f"output file must be regular and non-reparse: {target}")
    return target


def _copy_new_output_file(source: str | Path, destination: str | Path) -> Path:
    return _write_new_output_bytes(destination, Path(source).read_bytes())


def _finite(name: str, value: object, *, positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not bool")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number, not bool") from error
    if not math.isfinite(number) or (positive and number <= 0):
        qualifier = "positive finite" if positive else "finite"
        raise ValueError(f"{name} must be a {qualifier} number, not bool")
    return number


def _registered() -> dict:
    path = ROOT / "configs" / "phase5g.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("configs/phase5g.json must contain one parameter object")
    return value


def parameters(mode: str, target_speed_mps: float = 10.0, *,
               simple_rules: bool = False,
               simple_overrides: Mapping[str, object] | None = None):
    """Resolve one formal mode plus an explicitly isolated simple-demo switch."""
    from experiments.phase5 import parameters as phase5_parameters

    mode = _strict_mode(mode)
    if type(simple_rules) is not bool:
        raise ValueError("simple_rules must be an exact bool")
    if simple_overrides is not None and not isinstance(simple_overrides, Mapping):
        raise ValueError("simple_overrides must be a mapping")
    if not simple_rules and simple_overrides:
        raise ValueError("simple_overrides require simple_rules=True")
    target = _finite("target_speed_mps", target_speed_mps, positive=True)
    model, physical, policy = phase5_parameters(mode != "off")
    if target > model.p["max_speed_mps"]:
        raise ValueError("target_speed_mps must not exceed model max_speed_mps")
    registered = _registered()
    if simple_rules:
        if simple_overrides is None or set(simple_overrides) != set(simple_formation.PARAMETERS):
            raise ValueError("simple_overrides must contain exactly the six simple parameters")
        resolved_simple = {
            name: simple_overrides[name] for name in simple_formation.PARAMETERS
        }
    else:
        resolved_simple = {
            name: registered.get(name) for name in simple_formation.PARAMETERS
        }
    simple_formation.validate_parameters(resolved_simple)
    physical.update(settings("phase4"))
    physical.update(settings("phase5"))
    physical.update(deepcopy(registered))
    policy.update(deepcopy(registered))
    common = {
        "phase5g_enabled": True,
        "r5_enabled": False,
        "r5_lane_priority_enabled": False,
        "phase5g_target_speed_mps": target,
        "noa_target_speed_mps": target,
        "simple_formation_enabled": simple_rules,
        **resolved_simple,
        **_mode_flags(mode),
    }
    physical.update(common)
    policy.update(common)
    return model, physical, policy


def source_hashes() -> dict[str, str]:
    result = {}
    for name in SOURCE_FILES:
        path = ROOT / name
        if not regular_file(path):
            raise ValueError(f"required Phase 5G source missing: {name}")
        result[name] = sha256(path)
    return result


def snapshot_manifest(path: str | Path, label: str) -> dict[str, dict[str, str]]:
    """Describe an exact regular-file tree without following Windows reparse points."""
    root = Path(os.path.abspath(path))
    try:
        root_info = os.lstat(root)
    except OSError as error:
        raise ValueError(f"{label}: missing directory") from error
    root_attributes = getattr(root_info, "st_file_attributes", 0)
    if root.is_symlink() or bool(
        root_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ):
        raise ValueError(f"{label}: root reparse point forbidden")
    if not stat.S_ISDIR(root_info.st_mode):
        raise ValueError(f"{label}: missing directory")
    files: dict[str, dict[str, str]] = {}
    folded: dict[str, str] = {}

    def visit(folder: Path) -> None:
        with os.scandir(folder) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                candidate = Path(entry.path)
                relative = candidate.relative_to(root).as_posix()
                info = entry.stat(follow_symlinks=False)
                attributes = getattr(info, "st_file_attributes", 0)
                reparse = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
                if entry.is_symlink() or reparse:
                    raise ValueError(f"{label}.{relative}: reparse point forbidden")
                if stat.S_ISDIR(info.st_mode):
                    visit(candidate)
                elif stat.S_ISREG(info.st_mode):
                    collision = folded.get(relative.casefold())
                    if collision is not None and collision != relative:
                        raise ValueError(
                            f"{label}: case-insensitive path collision: {collision}, {relative}"
                        )
                    folded[relative.casefold()] = relative
                    files[relative] = {"sha256": sha256(candidate), "type": "regular"}
                else:
                    raise ValueError(f"{label}.{relative}: non-regular file forbidden")

    visit(root)
    return files


def expected_snapshot_manifests(case_file: str | Path) -> tuple[dict, dict]:
    """Build caller-held exact manifests for code and immutable runtime inputs."""
    source_case = output_path(case_file)
    source = code_manifest()
    code_names = set(source) | set(INPUTS)
    code = {
        name: {"sha256": sha256(ROOT / name), "type": "regular"}
        for name in sorted(code_names)
    }
    inputs = {
        name: {"sha256": sha256(ROOT / name), "type": "regular"}
        for name in INPUTS
    }
    inputs["phase5g_cases.json"] = {
        "sha256": sha256(source_case), "type": "regular",
    }
    return code, inputs


def seal_directory(path: str | Path) -> None:
    """Seal every current file and replace only the manifest itself."""
    root = _validated_output_base(path)
    atomic_json(root / "evidence_hashes.json", {
        file.relative_to(root).as_posix(): _stream_file_sha256(file)
        for file in sorted(root.rglob("*"))
        if file.is_file() and file != root / "evidence_hashes.json"
    })


def _anchor_digest(value: object) -> str:
    from experiments.phase5g_cases import digest_json

    return digest_json(value)


def _write_trust_anchor(run_path: Path, code_hashes: dict, input_hashes: dict,
                        code_snapshot_manifest: dict, input_snapshot_manifest: dict,
                        case_file_sha256: str, mode_registry: dict) -> Path:
    """Write the caller-side trust root outside the resealable run package."""
    anchor = run_path.parent / ".phase5g-trust" / f"{run_path.name}.json"
    _require_output_directory(run_path)
    _require_output_directory(anchor.parent)
    payload = {
        "schema": "phase5g_external_trust_anchor_v2",
        "run_id": run_path.name,
        "source_manifest_sha256": _anchor_digest(code_snapshot_manifest),
        "input_manifest_sha256": _anchor_digest(input_snapshot_manifest),
        "source_hashes": code_hashes,
        "input_hashes": input_hashes,
        "code_snapshot_manifest": code_snapshot_manifest,
        "input_snapshot_manifest": input_snapshot_manifest,
        "case_file_sha256": case_file_sha256,
        "mode_registry_sha256": _anchor_digest(mode_registry),
    }
    encoded = (json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False) + "\n").encode("utf-8")
    return _write_new_output_bytes(anchor, encoded)


def _write_completion_anchor(run_path: Path) -> Path:
    """Bind finalized simple-demo output after its outer evidence seal succeeds."""
    trust = run_path.parent / ".phase5g-trust"
    _require_output_directory(run_path)
    _require_output_directory(trust)
    source_anchor_path = trust / f"{run_path.name}.json"
    _require_output_regular_file(source_anchor_path)
    source_anchor = json.loads(source_anchor_path.read_text(encoding="utf-8"))
    if source_anchor.get("schema") != "phase5g_external_trust_anchor_v2" \
            or source_anchor.get("run_id") != run_path.name:
        raise ValueError("completion anchor source/input anchor differs")
    evidence_path = run_path / "evidence_hashes.json"
    _require_output_regular_file(evidence_path)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("completion anchor requires sealed outer evidence")
    child_manifest = snapshot_manifest(run_path / "case", "case")
    payload = {
        "schema": SIMPLE_DEMO_COMPLETION_SCHEMA,
        "run_id": run_path.name,
        "outer_schema": "phase5g_simple_demo_v1",
        "source_anchor_schema": source_anchor["schema"],
        "source_anchor_sha256": sha256(source_anchor_path),
        "source_manifest_sha256": source_anchor["source_manifest_sha256"],
        "input_manifest_sha256": source_anchor["input_manifest_sha256"],
        "child_directory": "case",
        "child_manifest": child_manifest,
        "child_manifest_sha256": _anchor_digest(child_manifest),
        "outer_evidence_hashes": evidence,
        "outer_evidence_manifest_sha256": _anchor_digest(evidence),
        "outer_evidence_file_sha256": sha256(evidence_path),
    }
    anchor = trust / f"{run_path.name}.completion.json"
    encoded = (json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False) + "\n").encode("utf-8")
    return _write_new_output_bytes(anchor, encoded)


def _write_replay_materials(run_path: Path, case_payload: bytes, *,
                            case_file_sha256: str, mode_registry: dict) -> None:
    """Freeze code and runtime inputs, then create the contemporaneous trust root."""
    source = code_manifest()
    atomic_json(run_path / "code_hashes.json", source)
    for name in source:
        destination = run_path / "code_snapshot" / name
        _prepare_output_directory(destination.parent)
        _copy_new_output_file(ROOT / name, destination)
    input_hashes = {}
    for name in INPUTS:
        destination = run_path / "input_snapshot" / name
        _prepare_output_directory(destination.parent)
        _copy_new_output_file(ROOT / name, destination)
        input_hashes[name] = sha256(destination)
        runtime_input = run_path / "code_snapshot" / name
        if not runtime_input.exists():
            _prepare_output_directory(runtime_input.parent)
            _copy_new_output_file(ROOT / name, runtime_input)
    frozen = run_path / "input_snapshot" / "phase5g_cases.json"
    _prepare_output_directory(frozen.parent)
    _write_new_output_bytes(frozen, case_payload)
    if sha256(frozen) != case_file_sha256:
        raise ValueError("phase5g_cases.json: frozen input digest differs")
    input_hashes["phase5g_cases.json"] = case_file_sha256
    atomic_json(run_path / "input_hashes.json", input_hashes)
    code_snapshot_manifest = snapshot_manifest(
        run_path / "code_snapshot", "code_snapshot")
    input_snapshot_manifest = snapshot_manifest(
        run_path / "input_snapshot", "input_snapshot")
    atomic_json(run_path / "code_snapshot_manifest.json", code_snapshot_manifest)
    atomic_json(run_path / "input_snapshot_manifest.json", input_snapshot_manifest)
    _write_trust_anchor(
        run_path, source, input_hashes,
        code_snapshot_manifest, input_snapshot_manifest,
        case_file_sha256, mode_registry,
    )


def expected_replay_anchors(case_file: str | Path) -> dict[str, str]:
    """Capture caller-side roots before a run so a whole-package rewrite is rejected."""
    source_case = output_path(case_file)
    if not source_case.is_file():
        raise ValueError("an explicit existing Phase 5G case file is required")
    _load_case_bundle(source_case)
    code_snapshot_manifest, input_snapshot_manifest = expected_snapshot_manifests(source_case)
    return {
        "expected_source_sha256": _anchor_digest(code_snapshot_manifest),
        "expected_input_sha256": _anchor_digest(input_snapshot_manifest),
    }


def expected_variants(cases: Sequence[Mapping[str, object]]) -> dict[str, dict]:
    from experiments.phase5g_cases import digest_json, physical_case

    result = {}
    for case in cases:
        name = case.get("name")
        if type(name) is not str or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("case names must be nonempty filesystem-safe strings")
        digest = digest_json(physical_case(case))
        for mode, _, _ in _MODE_SPECS:
            result[f"{name}_{mode}"] = {
                "case_name": name,
                "mode": mode,
                "vehicle_count": len(case.get("controlled", ())),
                "case_seed": case.get("private_rng_provenance", {}).get("case_seed"),
                "purpose": case.get("purpose"),
                "expected_lane_changes": case.get("expected_lane_changes"),
                "physical_input_sha256": digest,
                "case_input_sha256": digest_json(case),
            }
    return result


def _variant_input_sha256(mode: str, case: Mapping[str, object], model,
                           physical: Mapping[str, object], policy: Mapping[str, object],
                           memories: Mapping[str, object], *,
                           parent_run_id: str | None = None,
                           output_nonce: str | None = None) -> str:
    from experiments.phase5g_cases import digest_json

    payload = {
        "mode": _strict_mode(mode), "case": case,
        "model_parameters": dict(model.p), "parameters": dict(physical),
        "policy_parameters": dict(policy), "initial_memories": memories,
    }
    if parent_run_id is not None:
        if type(parent_run_id) is not str or not re.fullmatch(
            r"\d{8}T\d{12}Z_[0-9a-f]{8}", parent_run_id
        ):
            raise ValueError("parent_run_id must be an exact Phase 5G run id")
        payload["parent_run_id"] = parent_run_id
    if output_nonce is not None:
        if type(output_nonce) is not str or not re.fullmatch(
            r"[0-9a-f]{32}", output_nonce
        ):
            raise ValueError("output_nonce must be an exact lowercase UUID hex value")
        payload["output_nonce"] = output_nonce
    return digest_json(payload)


def _lane_index(y_m: float, width_m: float) -> int | None:
    lane = round(y_m / width_m - 0.5)
    center = width_m * (lane + 0.5)
    return lane if 0 <= lane < 3 and abs(y_m - center) <= 0.15 else None


def _stream_file_sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _iter_jsonl_records(trace_path, *, expected_sha256: str | None,
                        skip_blank: bool, verified_sha256: dict | None = None):
    """Yield decoded rows and verify exact source bytes only after full EOF."""
    if expected_sha256 is not None and (
            type(expected_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None):
        raise ValueError("trace.jsonl sha256: invalid expected digest")
    digest = hashlib.sha256()
    with trace_path.open("rb") as stream:
        for raw_line in stream:
            digest.update(raw_line)
            line = raw_line.decode("utf-8")
            if skip_blank and not line.strip():
                continue
            yield json.loads(line)
        actual = digest.hexdigest()
        if expected_sha256 is not None and actual != expected_sha256:
            raise ValueError(
                "trace.jsonl sha256 differs: "
                f"expected {expected_sha256}, actual {actual}")
        if verified_sha256 is not None:
            verified_sha256["sha256"] = actual


class _PhysicalTraceRecords:
    """Re-openable, bounded-memory view of physical JSONL intervals."""

    def __init__(self, trace_path, keys: Sequence[str], *, live: bool,
                 expected_sha256: str | None, dynamic: bool | None = None):
        if dynamic is not None and type(dynamic) is not bool:
            raise ValueError("dynamic trace mode hint must be bool or None")
        self.trace_path = trace_path
        self.keys = tuple(keys)
        self.live = live
        self.expected_sha256 = expected_sha256
        self.dynamic = dynamic

    def __iter__(self):
        previous = frozenset()
        previous_departures = None
        previous_time = None
        dynamic = self.dynamic
        for record in _iter_jsonl_records(
                self.trace_path, expected_sha256=self.expected_sha256,
                skip_blank=True):
            row_dynamic = _record_has_dynamic_fields(record)
            if dynamic is None:
                dynamic = row_dynamic
            elif row_dynamic is not dynamic:
                if dynamic:
                    raise ValueError("dynamic trace row dropped its dynamic fields")
                raise ValueError("legacy trace row introduced dynamic fields")
            active, time_s, departures = _dynamic_record_details(record, self.keys)
            if not previous.issubset(active):
                raise ValueError("trace active actor set is not monotonic")
            if departures is not None:
                if previous_time is not None and time_s <= previous_time:
                    raise ValueError("dynamic trace times must increase")
                if previous_departures is None:
                    for key in active:
                        if departures[key]["actual"] != time_s:
                            raise ValueError(
                                "first recorded actual departure must equal record time"
                            )
                else:
                    for key in self.keys:
                        before = previous_departures[key]
                        after = departures[key]
                        if before["static"] != after["static"]:
                            raise ValueError(
                                "dynamic departure schedule/template/ordinal changed"
                            )
                        old_actual = before["actual"]
                        new_actual = after["actual"]
                        if old_actual is not None and new_actual != old_actual:
                            raise ValueError("actual departure changed after activation")
                        if old_actual is None and new_actual is not None \
                                and new_actual != time_s:
                            raise ValueError(
                                "new actual departure must equal its first record time"
                            )
                previous_departures = departures
                previous_time = time_s
            previous = active
            if _record_is_physical(record, self.keys, live=self.live):
                yield record


def _readback_facts(record: Mapping[str, object], keys: Sequence[str], *,
                    advances_before: int, advances_after: int) -> dict:
    """Record complete per-actor synchronization coverage and proven commit state."""
    phase = record.get("readback_phase")
    reports = record.get("readback")
    reports = reports if isinstance(reports, dict) else {}
    states = {}
    for key in sorted(keys):
        report = reports.get(key)
        states[key] = (report.get("status", "recorded")
                       if isinstance(report, dict) else "not_read")
    coverage = {
        status: [key for key, value in states.items() if value == status]
        for status in ("recorded", "readback_exception", "not_read")
    }
    return {
        "failure_phase": phase,
        "commit_applied": bool(advances_after > advances_before),
        "failure_readback_states": states,
        "readback_coverage": coverage,
    }


def _record_has_dynamic_fields(record: Mapping[str, object]) -> bool:
    has_active = "active_actors" in record
    has_departures = "departures" in record
    if has_active != has_departures:
        raise ValueError(
            "dynamic trace rows require active_actors and departures together"
        )
    return has_active


def _dynamic_record_details(record: Mapping[str, object], keys: Sequence[str]):
    final_order = tuple(keys)
    final = frozenset(final_order)
    if not _record_has_dynamic_fields(record):
        return final, None, None
    declared = record["active_actors"]
    departures = record["departures"]
    if (not isinstance(declared, (list, tuple))
            or any(type(key) is not str for key in declared)
            or len(declared) != len(set(declared))):
        raise ValueError("trace active_actors must be a unique actor sequence")
    active = frozenset(declared)
    if not active or not active.issubset(final):
        raise ValueError("trace active_actors must be a nonempty controlled subset")
    if not isinstance(departures, dict) or set(departures) != final:
        raise ValueError("trace departures must cover the final controlled cohort")
    initial = record.get("initial")
    if not isinstance(initial, dict) or set(initial) != active:
        raise ValueError("trace initial actors differ from active_actors")
    times = []
    for key, state in initial.items():
        if not isinstance(state, dict) or set(state) != _TRACE_STATE_FIELDS:
            raise ValueError(f"trace initial.{key}: VehicleState fields differ")
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in state.values()):
            raise ValueError(f"trace initial.{key}: state must be finite")
        times.append(state["time_s"])
    time_s = times[0]
    if any(value != time_s for value in times[1:]):
        raise ValueError("dynamic trace initial states do not share one time")

    facts = {}
    ordinals = []
    departed = set()
    for key in final_order:
        row = departures[key]
        if not isinstance(row, dict) or set(row) != _TRACE_DEPARTURE_FIELDS:
            raise ValueError(f"trace departures.{key}: fields differ")
        scheduled = row["scheduled_departure_s"]
        actual = row["actual_departure_s"]
        ordinal = row["physical_ordinal"]
        template = row["state"]
        if (type(scheduled) not in (int, float) or not math.isfinite(scheduled)
                or scheduled < 0):
            raise ValueError(f"trace departures.{key}: invalid scheduled time")
        if actual is not None and (
                type(actual) not in (int, float) or not math.isfinite(actual)
                or actual < scheduled or actual > time_s):
            raise ValueError(f"trace departures.{key}: invalid actual time")
        if type(ordinal) is not int or ordinal < 0:
            raise ValueError(f"trace departures.{key}: invalid physical ordinal")
        if not isinstance(template, dict) or set(template) != _TRACE_STATE_FIELDS \
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in template.values()):
            raise ValueError(f"trace departures.{key}: invalid state template")
        if actual is None:
            if scheduled <= time_s:
                raise ValueError(f"trace departures.{key}: due actor is still pending")
        else:
            departed.add(key)
        ordinals.append(ordinal)
        facts[key] = {
            "static": (scheduled, ordinal, template),
            "actual": actual,
        }
    if sorted(ordinals) != list(range(len(final_order))):
        raise ValueError("trace physical ordinals must be unique and contiguous")
    if active != departed:
        raise ValueError("trace active_actors differ from actual departures")
    expected_order = tuple(sorted(active, key=lambda key: departures[key]["physical_ordinal"]))
    if tuple(declared) != expected_order:
        raise ValueError("trace active_actors are not in physical ordinal order")

    status = record.get("status")
    if status not in ("completed", "failed"):
        raise ValueError("trace status must be completed or failed")
    for name in _TRACE_ACTOR_MAP_FIELDS:
        actor_map = record.get(name, {})
        if not isinstance(actor_map, dict):
            raise ValueError(f"trace {name} must be an actor mapping")
        actor_keys = set(actor_map)
        if not actor_keys.issubset(active):
            raise ValueError(f"trace {name} contains an inactive actor")
        if status == "completed" and actor_keys != active:
            raise ValueError(f"completed trace {name} differs from active_actors")
    return active, time_s, facts


def _record_active_keys(record: Mapping[str, object], keys: Sequence[str]) -> frozenset[str]:
    active, _, _ = _dynamic_record_details(record, keys)
    return active


def _record_is_physical(record: Mapping[str, object], keys: Sequence[str], *,
                        live: bool) -> bool:
    expected = _record_active_keys(record, keys)
    complete = (set(record.get("steps", {})) == expected
                and set(record.get("diagnostics", {})) == expected)
    if not complete:
        return False
    if record.get("status") == "completed" or not live:
        return True
    return record.get("commit_applied") is True


class _LaneChangeAccumulator:
    def __init__(self, case: Mapping[str, object],
                 model_parameters: Mapping[str, object]):
        self.controlled = tuple(case["controlled"])
        self.width = float(model_parameters["lane_width_m"])
        self.actors = {
            key: {"changes": [], "active": None, "stable": None}
            for key in self.controlled
        }

    def consume(self, row: Mapping[str, object]) -> None:
        plan_fields = {"start_s", "y_start_m", "y_target_m", "duration_s", "speed_mps"}
        present = tuple(row.get("active_actors", tuple(row["initial"])))
        for key in present:
            item = self.actors[key]
            if item["stable"] is None:
                item["stable"] = _lane_index(
                    row["initial"][key]["y_m"], self.width)
            before = row["inputs"][key]["memory"]
            after = row["decisions"][key]["memory"]
            submitted = after.get("plan")
            valid_plan = isinstance(submitted, dict) and set(submitted) == plan_fields
            if before.get("plan") is None and valid_plan:
                start_y = submitted.get("y_start_m")
                target_y = submitted.get("y_target_m")
                start_lane = (_lane_index(float(start_y), self.width)
                              if type(start_y) in (int, float) else None)
                target_lane = (_lane_index(float(target_y), self.width)
                               if type(target_y) in (int, float) else None)
                item["active"] = {
                    "plan": json.loads(json.dumps(submitted, allow_nan=False)),
                    "request_reason": after.get("lane_change_reason", ""),
                    "from_lane": item["stable"], "plan_start_lane": start_lane,
                    "target_lane": target_lane,
                }
            active = item["active"]
            before_count = before.get("completed_lane_changes", 0)
            after_count = after.get("completed_lane_changes", 0)
            completion = (active is not None and before.get("plan") == active["plan"]
                          and after.get("plan") is None
                          and type(before_count) is int and type(after_count) is int
                          and after_count == before_count + 1)
            arrival = row["initial"][key]
            target_lane = active["target_lane"] if active is not None else None
            arrival_lane = _lane_index(arrival["y_m"], self.width)
            if (completion and active["from_lane"] is not None
                    and active["plan_start_lane"] == active["from_lane"]
                    and target_lane is not None and active["from_lane"] != target_lane
                    and arrival_lane == target_lane
                    and abs(arrival["heading_rad"]) <= 0.05):
                item["changes"].append({
                    "time_s": arrival["time_s"],
                    "from_lane": active["from_lane"],
                    "to_lane": target_lane,
                    "request_reason": active["request_reason"],
                })
                item["stable"], item["active"] = target_lane, None
            elif completion:
                item["active"] = None

    def result(self) -> dict:
        actors = {key: item["changes"] for key, item in self.actors.items()}
        flattened = [row for rows in actors.values() for row in rows]
        return {
            "actors": actors,
            "completed_lane_changes": len(flattened),
            "formation_lane_changes": sum(
                row["request_reason"] in FORMATION_LANE_REASONS
                for row in flattened),
        }


def _lane_change_facts(records, case: Mapping[str, object],
                       model_parameters: Mapping[str, object]) -> dict:
    accumulator = _LaneChangeAccumulator(case, model_parameters)
    for row in records:
        accumulator.consume(row)
    return accumulator.result()


class _SpeedAccumulator:
    def __init__(self, case: Mapping[str, object]):
        self.controlled = tuple(case["controlled"])
        self.frames = []
        self.minimum_speed_mps = None
        self.final = {}
        self.seen = set()

    def _consume_speed(self, state: Mapping[str, object]) -> None:
        speed = math.hypot(state["vx_mps"], state.get("vy_mps", 0.0))
        self.minimum_speed_mps = (
            speed if self.minimum_speed_mps is None
            else min(self.minimum_speed_mps, speed)
        )

    def consume(self, row: Mapping[str, object]) -> None:
        initial = {key: dict(state) for key, state in row["initial"].items()}
        self.frames.append({
            "time_s": next(iter(initial.values()))["time_s"], "states": initial,
        })
        for key, state in row["initial"].items():
            if key not in self.seen:
                self._consume_speed(state)
                self.seen.add(key)
        for step in row["steps"].values():
            for sample in step["samples"]:
                self._consume_speed(sample)
        self.final = {
            key: dict(step["final"]) for key, step in row["steps"].items()
        }

    def result(self, target_speed_mps: float, tolerance_mps: float, *,
               formed_time_s: float | None, held_time_s: float | None) -> dict:
        frames = list(self.frames)
        if self.seen:
            frames.append({
                "time_s": next(iter(self.final.values()))["time_s"],
                "states": {key: dict(state) for key, state in self.final.items()},
            })
        final_speeds = [
            math.hypot(state["vx_mps"], state.get("vy_mps", 0.0))
            for state in self.final.values()
        ]
        return _speed_facts_from_compact(
            frames, final_speeds, self.minimum_speed_mps,
            self.controlled, target_speed_mps, tolerance_mps,
            formed_time_s=formed_time_s, held_time_s=held_time_s,
        )


def _speed_facts_from_compact(frames: Sequence[dict], final_speeds: Sequence[float],
                              minimum_speed_mps: float | None,
                              controlled: Sequence[str], target_speed_mps: float,
                              tolerance_mps: float, *, formed_time_s: float | None,
                              held_time_s: float | None) -> dict:
    window_end = (formed_time_s + 10.0
                  if type(formed_time_s) in (int, float) else None)
    window_frames = [frame for frame in frames
                     if window_end is not None
                     and formed_time_s - 1e-9 <= frame["time_s"] <= window_end + 1e-9]
    frame_speeds = []
    for frame in window_frames:
        if set(frame["states"]) != set(controlled):
            frame_speeds = []
            break
        frame_speeds.append([
            math.hypot(frame["states"][key]["vx_mps"],
                       frame["states"][key].get("vy_mps", 0.0))
            for key in controlled
        ])
    coverage = bool(
        window_end is not None and held_time_s is not None
        and held_time_s + 1e-9 >= window_end
        and window_frames and window_frames[-1]["time_s"] + 1e-9 >= window_end
    )
    all_speeds = [speed for row in frame_speeds for speed in row]
    max_spread = max((max(row) - min(row) for row in frame_speeds), default=None)
    hold_passed = bool(
        coverage and frame_speeds
        and all(abs(speed - target_speed_mps) <= tolerance_mps + 1e-9
                for speed in all_speeds)
        and max_spread is not None and max_spread <= 1.0 + 1e-9
    )
    hold_window = {
        "formed_time_s": formed_time_s, "required_end_time_s": window_end,
        "detected_held_time_s": held_time_s,
        "frame_count": len(window_frames),
        "observed_start_time_s": window_frames[0]["time_s"] if window_frames else None,
        "observed_end_time_s": window_frames[-1]["time_s"] if window_frames else None,
        "minimum_speed_mps": min(all_speeds) if all_speeds else None,
        "maximum_target_deviation_mps": (
            max(abs(speed - target_speed_mps) for speed in all_speeds)
            if all_speeds else None),
        "maximum_speed_spread_mps": max_spread,
        "coverage_passed": coverage, "speed_recovered": hold_passed,
    }
    return {
        "minimum_speed_mps": minimum_speed_mps,
        "final_speed_spread_mps": (
            max(final_speeds) - min(final_speeds) if final_speeds else None
        ),
        "speed_recovered": hold_passed,
        "final_speeds_mps": final_speeds,
        "hold_window": hold_window,
    }


def _speed_facts(records, case: Mapping[str, object],
                 target_speed_mps: float, tolerance_mps: float, *,
                 formed_time_s: float | None, held_time_s: float | None) -> dict:
    accumulator = _SpeedAccumulator(case)
    for row in records:
        accumulator.consume(row)
    return accumulator.result(
        target_speed_mps, tolerance_mps,
        formed_time_s=formed_time_s, held_time_s=held_time_s,
    )


def _evaluate_record_source(source, case: Mapping[str, object], model,
                            physical: Mapping[str, object]) -> dict:
    """Aggregate a re-openable physical source in three bounded scans."""
    lane_accumulator = _LaneChangeAccumulator(case, model.p)
    speed_accumulator = _SpeedAccumulator(case)
    record_count = 0
    final_all = {}
    for row in source():
        record_count += 1
        lane_accumulator.consume(row)
        speed_accumulator.consume(row)
        final_all = {
            key: dict(step["final"]) for key, step in row["steps"].items()
        }
    frames = list(speed_accumulator.frames)
    if record_count:
        frames.append({
            "time_s": next(iter(final_all.values()))["time_s"],
            "states": final_all,
        })
    detection = {
        "default": detect_frames(frames),
        "sensitivity": {
            str(factor): detect_frames(
                frames, position_tolerance=2.0 * factor, speed_tolerance=factor,
            )
            for factor in (0.5, 1.0, 1.5)
        },
    }
    if record_count:
        geometry = geometry_report(source(), model, RoadEnvelope.from_net(NET))
        metric_rows = source()
        if case.get("departures") is not None:
            final = set(case["controlled"])
            metric_rows = (
                row for row in metric_rows
                if set(row.get("active_actors", row.get("initial", {}))) == final
            )
        metric_rows = iter(metric_rows)
        first_metric_row = next(metric_rows, None)
        if first_metric_row is None:
            metrics = {"actors": {}, "requirements_passed": False,
                       "comfort_passed": False, "tracking_passed": False}
        else:
            def complete_metric_rows():
                yield first_metric_row
                yield from metric_rows

            metrics = driving_metrics(
                complete_metric_rows(), model, physical,
                {**case, "requirements": {}},
            )
    else:
        geometry = {
            "passed": False, "vehicle_substeps": 0, "outside_substeps": 0,
            "collision_substeps": 0, "outside_model_envelope_substeps": 0,
            "outside_events": [], "collision_events": [], "model_envelope_events": [],
            "scope": "No complete physical interval was produced.",
        }
        metrics = {"actors": {}, "requirements_passed": False,
                   "comfort_passed": False, "tracking_passed": False}
    intervals = [row for row in detection["default"]["intervals"]
                 if row["whole_cohort"] and row["success"]]
    first = min(intervals, key=lambda row: row["formed_time_s"]) if intervals else None
    lane_changes = lane_accumulator.result()
    speed = speed_accumulator.result(
        float(physical["noa_target_speed_mps"]),
        float(physical["formation_maintaining_speed_tolerance_mps"]),
        formed_time_s=first["formed_time_s"] if first else None,
        held_time_s=first["held_time_s"] if first else None,
    )
    final_states = speed_accumulator.final
    counts = [0, 0, 0]
    for state in final_states.values():
        lane = _lane_index(state["y_m"], float(model.p["lane_width_m"]))
        if lane is not None:
            counts[lane] += 1
    summary = {
        "whole_cohort_formation_success": detection["default"]["whole_cohort_success"],
        "formed_time_s": first["formed_time_s"] if first else None,
        "held_time_s": first["held_time_s"] if first else None,
        "completed_lane_changes": lane_changes["completed_lane_changes"],
        "formation_lane_changes": lane_changes["formation_lane_changes"],
        "final_lane_counts": counts,
        "minimum_speed_mps": speed["minimum_speed_mps"],
        "final_speed_spread_mps": speed["final_speed_spread_mps"],
        "speed_recovered": speed["speed_recovered"],
        "collision_count": geometry["collision_substeps"],
        "geometry_passed": geometry["passed"],
        "comfort_passed": metrics["comfort_passed"],
    }
    if tuple(summary) != SUMMARY_KEYS:
        raise RuntimeError("Phase 5G summary schema drift")
    return {"detection": detection, "geometry": geometry, "metrics": metrics,
            "lane_changes": lane_changes, "speed_recovery": speed, "summary": summary}


def evaluate_records(records: Sequence[dict], case: Mapping[str, object], model,
                     physical: Mapping[str, object]) -> dict:
    """Small-fixture wrapper over the same streaming aggregation implementation."""
    if isinstance(records, _PhysicalTraceRecords):
        source = lambda: iter(records)
    else:
        committed = tuple(records)
        source = lambda: iter(committed)
    return _evaluate_record_source(source, case, model, physical)


def evaluate_trace(trace_path, case: Mapping[str, object], model,
                   physical: Mapping[str, object], *, live: bool,
                   expected_sha256: str | None = None) -> dict:
    """Evaluate a trace with three sequential scans and no whole-file read."""
    if type(live) is not bool:
        raise ValueError("live must be bool")
    records = _PhysicalTraceRecords(
        trace_path, case["controlled"], live=live,
        expected_sha256=expected_sha256,
        dynamic="departures" in case,
    )
    return evaluate_records(records, case, model, physical)


def variant_acceptance(metadata: Mapping[str, object], derived: Mapping[str, object], *,
                       trace_intervals: int, completed_intervals: int) -> dict:
    """Independently derive the exact runner acceptance fields from produced evidence."""
    status = metadata.get("execution_status")
    if status not in ("completed", "failed"):
        raise ValueError("metadata.execution_status: not finalized")
    recording = type(trace_intervals) is int and trace_intervals > 0
    summary = derived["summary"]
    driving = bool(
        completed_intervals > 0 and status == "completed"
        and derived["geometry"]["passed"]
        and summary["collision_count"] == 0
        and derived["speed_recovery"]["speed_recovered"]
    )
    comfort = bool(derived["metrics"]["comfort_passed"])
    return {
        "status": status,
        "recording_passed": recording,
        "driving_passed": driving,
        "comfort_passed": comfort,
        "passed": bool(recording and driving and comfort),
    }


def scientific_gate(case: Mapping[str, object], mode: str, summary: Mapping[str, object],
                    *, execution_completed: bool,
                    speed_recovery: Mapping[str, object]) -> bool | None:
    """Apply the preregistered main-six gate; keep every other result factual."""
    mode = _strict_mode(mode)
    if case.get("name") != "main_6_3_2_1" or len(case.get("controlled", ())) != 6 \
            or mode != "lane_priority":
        return None
    return bool(
        execution_completed
        and summary["whole_cohort_formation_success"]
        and summary["final_lane_counts"] == [2, 2, 2]
        and summary["formation_lane_changes"] >= 1
        and summary["formed_time_s"] is not None
        and summary["formed_time_s"] <= 30.0 + 1e-9
        and summary["held_time_s"] is not None
        and summary["held_time_s"] - summary["formed_time_s"] >= 10.0 - 1e-9
        and speed_recovery.get("speed_recovered") is True
        and summary["final_speed_spread_mps"] is not None
        and summary["final_speed_spread_mps"] <= 1.0 + 1e-9
        and summary["collision_count"] == 0
        and summary["geometry_passed"]
        and summary["comfort_passed"]
    )


def _scientific_applicable(case: Mapping[str, object], mode: str) -> bool:
    return bool(case.get("name") == "main_6_3_2_1"
                and len(case.get("controlled", ())) == 6
                and mode == "lane_priority")


def _initial_memories(case: Mapping[str, object], mode: str, *,
                      simple_rules: bool = False) -> dict:
    raw = case["initial_memories"]
    if simple_rules:
        result = {}
        accepted = {
            field.name for field in fields(simple_formation.SimpleFormationMemory)
        }
        for key, row in raw.items():
            copied = {
                name: value for name, value in
                json.loads(json.dumps(row, allow_nan=False)).items()
                if name in accepted
            }
            copied.update(
                reference_track_id=None,
                join_anchor_track_id=None,
                desired_lane_index=None,
                join_phase="FREE",
                stable_since_s=None,
            )
            result[key] = asdict(simple_formation.memory_from_dict(copied))
        return result
    return neutral_phase5g_memories(raw) if mode == "off" else json.loads(
        json.dumps(raw, allow_nan=False)
    )


def run_variant(path: str | Path, model, physical: Mapping[str, object],
                 policy: Mapping[str, object], case: Mapping[str, object], mode: str,
                 *, live: bool = True, parent_run_id: str | None = None,
                 output_nonce: str | None = None) -> dict:
    """Run one immutable physical case/mode, retaining any produced prefix."""
    from experiments.phase3_replay import compare_tree
    from experiments.phase5g_cases import digest_json, physical_case

    mode = _strict_mode(mode)
    if type(live) is not bool:
        raise ValueError("live must be bool")
    if live and case.get("departures") is not None:
        raise ValueError("dynamic Phase 5G departures require local live=False execution")
    simple_rules = physical.get("simple_formation_enabled")
    simple_overrides = ({
        name: physical.get(name) for name in simple_formation.PARAMETERS
    } if simple_rules is True else None)
    expected_model, expected_physical, expected_policy = parameters(
        mode, physical.get("noa_target_speed_mps"), simple_rules=simple_rules,
        simple_overrides=simple_overrides,
    )
    compare_tree(dict(expected_model.p), dict(model.p), 0.0, "model_parameters")
    compare_tree(expected_physical, dict(physical), 0.0, "parameters")
    compare_tree(expected_policy, dict(policy), 0.0, "policy_parameters")
    target = _validated_output_base(path)
    target = _prepare_output_directory(target, exclusive=True)
    atomic_json(target / "validation.json", {"passed": False, "status": "running"})
    memories = _initial_memories(case, mode, simple_rules=simple_rules)
    metadata = {
        "schema": "phase5g_variant_v1", "mode": mode, "formal": False,
        "case": case, "parameters": dict(physical), "policy_parameters": dict(policy),
        "model_parameters": dict(model.p), "initial": case["initial"],
        "initial_memories": memories,
        "initial_memories_sha256": initial_memory_hash(memories),
        "private_rng_provenance": case["private_rng_provenance"],
        "physical_input_sha256": digest_json(physical_case(case)),
        "case_input_sha256": digest_json(case),
        "parameters_input_sha256": _variant_input_sha256(
            mode, case, model, physical, policy, memories,
            parent_run_id=parent_run_id,
            output_nonce=output_nonce,
        ),
        "clock_schema": CLOCK_SCHEMA,
        "intervals": round(case["duration_s"] / physical["control_sync_dt_s"]),
        "live": live, "sumo_time_offset_s": None, "execution_status": "running",
        "lifecycle_status": "running",
        "source_hashes": source_hashes(),
    }
    if parent_run_id is not None:
        metadata["parent_run_id"] = parent_run_id
    if output_nonce is not None:
        metadata["output_nonce"] = output_nonce
    atomic_json(target / "metadata.json", metadata)
    # Even pre-clock failures retain an explicit, append-only empty trace prefix.
    _write_new_output_bytes(target / "stdout.log", b"")
    _write_new_output_bytes(target / "trace.jsonl", b"")
    trace_count, completed_count, physical_count = 0, 0, 0
    conn = bridge = clock = None
    failure = None
    pending_interrupt = None
    try:
        if metadata["intervals"] < 1 or not math.isclose(
            metadata["intervals"] * physical["control_sync_dt_s"], case["duration_s"],
            abs_tol=1e-9, rel_tol=0.0,
        ):
            raise ValueError("case.duration_s must contain complete control intervals")
        road = VisibleRoad.from_net(NET)
        metadata["road"] = asdict(road)
        atomic_json(target / "metadata.json", metadata)
        initial = {key: VehicleState(**state) for key, state in case["initial"].items()}
        clock = Phase5GClock(
            initial, model, road, physical, policy, case["controlled"], case["scripts"],
            memories, clock_schema=CLOCK_SCHEMA,
            initial_memories_sha256=metadata["initial_memories_sha256"],
            departures=case.get("departures"),
        )
        stdout_path = _require_output_regular_file(target / "stdout.log")
        trace_path = _require_output_regular_file(target / "trace.jsonl")
        with stdout_path.open("a", encoding="utf-8") as stdout, \
                trace_path.open("a", encoding="utf-8") as trace:
            if live:
                conn, bridge = bootstrap(
                    target, initial, model,
                    {**physical, "phase3_seed": physical["phase4_seed"]}, stdout,
                )
                metadata.update(sumo_time_offset_s=bridge.time_offset,
                                sumo_version=conn.getVersion())
                atomic_json(target / "metadata.json", metadata)
            for _ in range(metadata["intervals"]):
                advances_before = getattr(bridge, "advances", 0)
                try:
                    record = clock.tick(bridge=bridge)
                except BaseException:
                    if clock.last_record:
                        sync = _readback_facts(
                            clock.last_record, case["controlled"],
                            advances_before=advances_before,
                            advances_after=getattr(bridge, "advances", advances_before),
                        )
                        clock.last_record.update(sync)
                        trace.write(json.dumps(clock.last_record, allow_nan=False) + "\n")
                        trace.flush()
                        trace_count += 1
                        if _record_is_physical(
                            clock.last_record, case["controlled"], live=live,
                        ):
                            physical_count += 1
                    raise
                trace.write(json.dumps(record, allow_nan=False) + "\n")
                trace.flush()
                physical_count += 1
                trace_count += 1
                completed_count += 1
        metadata["execution_status"] = "completed"
    except BaseException as error:
        failure = f"{type(error).__name__}: {error}"
        metadata.update(execution_status="failed", failure_error=failure,
                        failure_traceback=traceback.format_exc(),
                        failure_readback_phase=getattr(bridge, "readback_phase", None))
        if not isinstance(error, Exception):
            pending_interrupt = error
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as error:
                failure = f"Close failure: {error}"
                metadata.update(execution_status="failed", close_error=failure)
    last = clock.last_record if clock is not None else None
    physical_intervals = physical_count
    metadata.update(
        recorded_intervals=physical_intervals, trace_intervals=trace_count,
        completed_intervals=completed_count, physical_intervals=physical_intervals,
        partial_tail=trace_count > physical_intervals,
        failure_stage=last.get("failure_stage") if last else None,
        failure_actor=last.get("failure_actor") if last else None,
    )
    if failure and last is not None:
        for name in ("failure_phase", "commit_applied",
                     "failure_readback_states", "readback_coverage"):
            metadata[name] = last.get(name)
    derived = None
    lifecycle_stage = "metadata"
    try:
        atomic_json(target / "metadata.json", metadata)
        lifecycle_stage = "evaluation"
        trace_path = _require_output_regular_file(target / "trace.jsonl")
        trace_sha256 = _stream_file_sha256(trace_path)
        derived = evaluate_trace(
            trace_path, case, model, physical, live=live,
            expected_sha256=trace_sha256,
        )
        for name in ("detection", "geometry", "metrics", "lane_changes", "speed_recovery"):
            lifecycle_stage = f"derived.{name}"
            atomic_json(target / f"{name}.json", derived[name])
        lifecycle_stage = "acceptance"
        scientific = scientific_gate(
            case, mode, derived["summary"],
            execution_completed=metadata["execution_status"] == "completed",
            speed_recovery=derived["speed_recovery"],
        )
        acceptance = variant_acceptance(
            metadata, derived, trace_intervals=trace_count,
            completed_intervals=completed_count,
        )
        result = {
            **acceptance, "error": failure,
            "live": live, "recorded_intervals": physical_intervals,
            "planned_intervals": metadata["intervals"],
            "summary": derived["summary"], "scientific_passed": scientific,
            "failure_stage": metadata.get("failure_stage"),
            "case_index": {"case_name": case["name"], "mode": mode},
            "sealed": True,
        }
        if parent_run_id is not None:
            result["scientific_gate_applicable"] = _scientific_applicable(case, mode)
        lifecycle_stage = "validation"
        metadata["lifecycle_status"] = "finalized"
        atomic_json(target / "metadata.json", metadata)
        result["produced_evidence"] = _produced_evidence(target)
        atomic_json(target / "validation.json", result)
    except BaseException as error:
        if not isinstance(error, Exception):
            pending_interrupt = error
        failure = f"{type(error).__name__}: {error}"
        metadata.update(
            lifecycle_status="failed", failure_stage=lifecycle_stage,
            failure_error=failure, failure_traceback=traceback.format_exc(),
        )
        _finalizer_json(target / "metadata.json", metadata)
        result = {
            "status": "failed", "recording_passed": trace_count > 0,
            "driving_passed": False,
            "comfort_passed": bool(
                derived is not None and derived["metrics"]["comfort_passed"]),
            "passed": False,
            "error": failure, "failure_stage": lifecycle_stage,
            "live": live, "recorded_intervals": physical_intervals,
            "planned_intervals": metadata["intervals"],
            "summary": derived["summary"] if derived is not None else None,
            "scientific_passed": False if _scientific_applicable(case, mode) else None,
            "case_index": {"case_name": case["name"], "mode": mode},
            "produced_evidence": _produced_evidence(target),
            "sealed": True,
        }
        if parent_run_id is not None:
            result["scientific_gate_applicable"] = _scientific_applicable(case, mode)
        _finalizer_json(target / "validation.json", result)
    try:
        seal_directory(target)
    except BaseException as error:
        if not isinstance(error, Exception):
            pending_interrupt = error
        failure = f"{type(error).__name__}: {error}"
        metadata.update(lifecycle_status="failed", failure_stage="sealing",
                        failure_error=failure, failure_traceback=traceback.format_exc())
        result.update(status="failed", passed=False, driving_passed=False,
                      error=failure, failure_stage="sealing", sealed=False)
        result["produced_evidence"] = _produced_evidence(target)
        _finalizer_json(target / "metadata.json", metadata)
        _finalizer_json(target / "validation.json", result)
        _write_unsealed_manifest(target)
    if pending_interrupt is not None:
        raise pending_interrupt
    return result


def _load_case_bundle(case_file: str | Path) -> dict:
    from experiments import phase5g_cases

    path = output_path(case_file)
    if not path.is_file():
        raise ValueError("an explicit existing Phase 5G case file is required")
    raw = path.read_bytes()
    data = phase5g_cases._strict_json(raw)
    if data.get("schema") == "phase5g_execution_cases_v1":
        return _load_development_bundle(raw)
    specs = data.get("case_specs")
    speed_range = data.get("speed_range_mps")
    if not isinstance(specs, list) or not isinstance(speed_range, list) or len(speed_range) != 2:
        raise ValueError("case_file.case_specs/speed_range_mps are required")
    _, physical, _ = parameters("lane_priority")
    return phase5g_cases.load_bundle(
        raw, physical, specs, speed_min_mps=speed_range[0], speed_max_mps=speed_range[1],
    )


def development_case_bundle(case_specs: Sequence[Sequence[int]], duration_s: float,
                            *, speed_min_mps: float = 8.0,
                            speed_max_mps: float = 12.0) -> dict:
    """Build an explicitly timed, non-formal input bundle for replayable tests/demos."""
    from experiments import phase5g_cases

    duration = _finite("duration_s", duration_s, positive=True)
    _, physical, _ = parameters("lane_priority")
    intervals = round(duration / physical["control_sync_dt_s"])
    if intervals < 1 or not math.isclose(
        intervals * physical["control_sync_dt_s"], duration, abs_tol=1e-9, rel_tol=0.0,
    ):
        raise ValueError("duration_s must contain complete control intervals")
    base = phase5g_cases.build_bundle(
        physical, case_specs, speed_min_mps=speed_min_mps,
        speed_max_mps=speed_max_mps,
    )
    cases = [{**case, "duration_s": duration} for case in base["cases"]]
    envelope = {
        "schema": "phase5g_execution_cases_v1",
        "base_schema": base["schema"],
        "base_bundle_sha256": base["bundle_sha256"],
        "source_path": base["source_path"],
        "generator_sha256": base["generator_sha256"],
        "config_sha256": base["config_sha256"],
        "model_parameters_sha256": base["model_parameters_sha256"],
        "development_seeds": base["development_seeds"],
        "holdout_seeds": base["holdout_seeds"],
        "case_specs": base["case_specs"],
        "speed_range_mps": base["speed_range_mps"],
        "duration_s_by_case": {case["name"]: duration for case in cases},
        "physical_sha256": phase5g_cases.digest_json(
            [phase5g_cases.physical_case(case) for case in cases]
        ),
        "initial_state_sha256": phase5g_cases.digest_json(cases),
        "cases": cases,
    }
    return {**envelope, "bundle_sha256": phase5g_cases.digest_json(envelope)}


def _load_development_bundle(raw: bytes) -> dict:
    from experiments import phase5g_cases

    supplied = phase5g_cases._strict_json(raw)
    if raw != phase5g_cases.canonical_json_bytes(supplied):
        raise ValueError("Phase 5G execution case bundle is not canonical JSON bytes")
    speed = supplied.get("speed_range_mps")
    specs = supplied.get("case_specs")
    durations = supplied.get("duration_s_by_case")
    if not isinstance(speed, list) or len(speed) != 2 or not isinstance(specs, list) \
            or not isinstance(durations, dict) or not durations:
        raise ValueError("execution case bundle fields differ")
    values = list(durations.values())
    if not values or any(value != values[0] for value in values):
        raise ValueError("duration_s_by_case must explicitly use one registered duration")
    expected = development_case_bundle(
        specs, values[0], speed_min_mps=speed[0], speed_max_mps=speed[1],
    )
    if phase5g_cases.canonical_json_bytes(supplied) != phase5g_cases.canonical_json_bytes(expected):
        raise ValueError("execution case source, duration, memory, or physical input changed")
    return supplied


def write_development_case_bundle(path: str | Path, *, case_specs: Sequence[Sequence[int]],
                                  duration_s: float) -> dict:
    """Exclusively save a non-formal explicit-duration bundle; never a formal freeze."""
    from experiments.phase5g_cases import canonical_json_bytes

    target = output_path(path)
    if target.exists():
        raise FileExistsError(target)
    bundle = development_case_bundle(case_specs, duration_s)
    payload = canonical_json_bytes(bundle)
    _load_development_bundle(payload)
    _prepare_output_directory(target.parent)
    _write_new_output_bytes(target, payload)
    return bundle


def run_phase5g(case_file: str | Path, *, base: str | Path | None = None,
                live: bool = True, formal: bool = False,
                mode_registry: Mapping[str, Mapping[str, bool]] | None = None) -> Path:
    """Run all three modes against every case in one strict frozen bundle."""
    registered_modes = _mode_registry()
    registry = registered_modes if mode_registry is None else mode_registry
    if registry != registered_modes:
        raise ValueError("mode_registry must equal the exact registered Phase 5G modes")
    if type(live) is not bool or type(formal) is not bool:
        raise ValueError("live and formal must be bool")
    bundle = _load_case_bundle(case_file)
    source_case = output_path(case_file)
    if formal and (source_case.name != "phase5g_cases_frozen.json"
                   or bundle.get("schema") != "phase5g_pure_formation_cases_v1"):
        raise ValueError("formal execution requires the strict Task 5 frozen case bundle")
    output_base = _validated_output_base(base or ROOT / "results/phase5g/runs")
    cases = bundle["cases"]
    specs = expected_variants(cases)
    run = RunRecord(output_base, {
        "purpose": "Phase 5G pure formation paired suite",
        "schema": "phase5g_run_v1", "formal": formal, "live": live,
        "case_file_source": str(source_case), "case_file_sha256": sha256(source_case),
        "mode_registry": registered_modes, "command_line": sys.argv, "python": sys.version,
    })
    variants = {}
    index = {"expected_variants": specs, "started_variants": [],
             "finalized_variants": [], "completed_variants": [],
             "unsealed_variants": []}
    try:
        with run:
            _write_replay_materials(
                run.path, source_case.read_bytes(),
                case_file_sha256=sha256(source_case),
                mode_registry=registered_modes,
            )
            atomic_json(run.path / "frozen_cases.json", cases)
            atomic_json(run.path / "case_index.json", index)
            by_name = {case["name"]: case for case in cases}
            for name, spec in specs.items():
                case = by_name[spec["case_name"]]
                model, physical, policy = parameters(spec["mode"])
                index["started_variants"].append(name)
                atomic_json(run.path / "case_index.json", index)
                variants[name] = run_variant(
                    run.path / "cases" / name, model, physical, policy, case,
                    spec["mode"], live=live,
                )
                index["finalized_variants"].append(name)
                if variants[name]["status"] == "completed":
                    index["completed_variants"].append(name)
                if variants[name].get("sealed") is False:
                    index["unsealed_variants"].append(name)
                atomic_json(run.path / "case_index.json", index)
                atomic_json(run.path / "progress.json", {
                    "last_variant": name,
                    "started_variants": index["started_variants"],
                    "finalized_variants": index["finalized_variants"],
                })
            main_name = "main_6_3_2_1_lane_priority"
            scientific = variants.get(main_name, {}).get("scientific_passed") is True
            result = {
                "passed": all(value["passed"] for value in variants.values()) and scientific,
                "engineering_passed": all(value["recording_passed"] for value in variants.values()),
                "scientific_gate_passed": scientific,
                "complete_execution": set(index["completed_variants"]) == set(specs),
                "retained_partial_package": False, "variants": variants,
                "case_index": "case_index.json", "formal": formal,
            }
            run.finish(result)
    except BaseException:
        if run.path.is_dir() and (run.path / "validation.json").is_file():
            for name in index["started_variants"]:
                path = run.path / "cases" / name / "validation.json"
                if path.is_file():
                    variants[name] = read_json(path)
            failure = read_json(run.path / "validation.json")
            failure.update(
                variants=variants, case_index="case_index.json", formal=formal,
                retained_partial_package=True, passed=False,
                engineering_passed=False, scientific_gate_passed=False,
                complete_execution=False,
            )
            atomic_json(run.path / "validation.json", failure)
        raise
    finally:
        if run.path.is_dir():
            seal_directory(run.path)
    print(json.dumps({"path": str(run.path), "formal": formal}, ensure_ascii=False), flush=True)
    return run.path


def _exact_seed(seed: object) -> int:
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be an exact uint64 integer, not bool")
    return seed


def _demo_case(physical: Mapping[str, object], *, vehicle_count: int, seed: int,
               duration_s: float, live: bool) -> dict:
    """Use scheduled local execution offline; retain only the historical live six."""
    from experiments.phase5g_cases import main_six_case, seeded_case

    seeded = seeded_case(physical, vehicle_count, seed)
    if not live:
        return {**seeded, "duration_s": duration_s}
    if vehicle_count != 6:
        raise ValueError("live historical execution supports only the fixed six-actor case")
    fixed = main_six_case(physical)
    return {
        **fixed,
        "duration_s": duration_s,
        "initial_memories": seeded["initial_memories"],
        "private_rng_provenance": seeded["private_rng_provenance"],
    }


def run_phase5g_demo(*, vehicle_count: int, seed: int, target_speed_mps: float,
                     duration_s: float, output_base: str | Path,
                     mode: str = "lane_priority", formal: bool = False,
                     live: bool = False,
                     local_formation_range_m: float = 90.0,
                     adjacent_lane_gap_m: float = 15.0,
                     same_lane_gap_m: float = 30.0,
                     position_tolerance_m: float = 2.0,
                     formation_accel_limit_mps2: float = 0.5,
                     max_formation_lane_changes: int = 1) -> Path:
    """Generate one non-formal lane-priority trace for later SUMO-GUI playback."""
    from experiments.phase5g_cases import (
        SUPPORTED_COUNTS, canonical_json_bytes, digest_json, physical_case,
    )

    if type(vehicle_count) is not int or vehicle_count not in SUPPORTED_COUNTS:
        raise ValueError("vehicle_count must be exactly 3, 6, or 12")
    seed = _exact_seed(seed)
    target_speed = _finite("target_speed_mps", target_speed_mps, positive=True)
    duration = _finite("duration_s", duration_s, positive=True)
    if _strict_mode(mode) != "lane_priority" or formal is not False:
        raise ValueError("demo is exactly one non-formal lane_priority case")
    if type(live) is not bool:
        raise ValueError("live must be bool")
    resolved_simple = {
        "simple_formation_local_range_m": _finite(
            "local_formation_range_m", local_formation_range_m, positive=True),
        "simple_formation_adjacent_gap_m": _finite(
            "adjacent_lane_gap_m", adjacent_lane_gap_m, positive=True),
        "simple_formation_same_gap_m": _finite(
            "same_lane_gap_m", same_lane_gap_m, positive=True),
        "simple_formation_position_tolerance_m": _finite(
            "position_tolerance_m", position_tolerance_m, positive=True),
        "simple_formation_accel_limit_mps2": _finite(
            "formation_accel_limit_mps2", formation_accel_limit_mps2, positive=True),
        "simple_formation_max_lane_changes": max_formation_lane_changes,
    }
    simple_formation.validate_parameters(resolved_simple)
    model, physical, policy = parameters(
        mode, target_speed, simple_rules=True, simple_overrides=resolved_simple,
    )
    if not math.isclose(round(duration / physical["control_sync_dt_s"])
                        * physical["control_sync_dt_s"], duration, abs_tol=1e-9, rel_tol=0.0):
        raise ValueError("duration_s must contain complete control intervals")
    base = _validated_output_base(output_base)
    case = _demo_case(
        physical, vehicle_count=vehicle_count, seed=seed,
        duration_s=duration, live=live,
    )
    memories = _initial_memories(case, mode, simple_rules=True)
    registered_modes = _mode_registry()
    run_metadata = {
        "purpose": "Non-formal simple local if/else formation GUI source trace",
        "schema": "phase5g_simple_demo_v1",
        "formal": False, "mode": mode, "vehicle_count": vehicle_count,
        "simple_formation_enabled": True,
        "seed": seed, "target_speed_mps": target_speed, "duration_s": duration,
        "simple_parameters": resolved_simple,
    }
    run = RunRecord(base, run_metadata)
    output_nonce = uuid4().hex
    execution = {
        "schema": SIMPLE_DEMO_EXECUTION_SCHEMA,
        "case_directory": "case",
        "parent_run_id": run.run_id,
        "output_nonce": output_nonce,
        "case_name": case["name"],
        "mode": mode,
        "vehicle_count": vehicle_count,
        "case_seed": seed,
        "target_speed_mps": target_speed,
        "duration_s": duration,
        "simple_formation_enabled": True,
        "simple_parameters": resolved_simple,
        "physical_input_sha256": digest_json(physical_case(case)),
        "case_input_sha256": digest_json(case),
        "parameters_input_sha256": _variant_input_sha256(
            mode, case, model, physical, policy, memories,
            parent_run_id=run.run_id,
            output_nonce=output_nonce,
        ),
        "initial_memories_sha256": initial_memory_hash(memories),
    }
    input_bundle = {
        "schema": SIMPLE_DEMO_INPUT_SCHEMA,
        "cases": [case],
        "execution": execution,
    }
    case_payload = canonical_json_bytes(input_bundle)
    case_file_sha256 = digest_json(input_bundle)
    run_metadata.update({
        "case_file_sha256": case_file_sha256,
        "mode_registry": registered_modes,
        "execution": execution,
    })
    index = {
        "schema": SIMPLE_DEMO_INDEX_SCHEMA,
        "execution": execution,
        "started": False,
        "finalized": False,
        "completed": False,
    }
    try:
        with run:
            _write_replay_materials(
                run.path, case_payload,
                case_file_sha256=case_file_sha256,
                mode_registry=registered_modes,
            )
            atomic_json(run.path / "frozen_cases.json", [case])
            atomic_json(run.path / "case_index.json", index)
            index["started"] = True
            atomic_json(run.path / "case_index.json", index)
            result = run_variant(
                run.path / "case", model, physical, policy, case, mode,
                live=live, parent_run_id=run.run_id, output_nonce=output_nonce,
            )
            index["finalized"] = True
            index["completed"] = result.get("status") == "completed"
            atomic_json(run.path / "case_index.json", index)
            engineering = result.get("recording_passed") is True
            complete = index["completed"]
            run.finish({
                "passed": bool(engineering and complete),
                "engineering_passed": engineering,
                "scientific_gate_applicable": _scientific_applicable(case, mode),
                "scientific_gate_passed": result.get("scientific_passed"),
                "complete_execution": complete,
                "formal": False, "mode": mode,
                "case_directory": "case", "case_index": "case_index.json",
                "variant": result,
            })
    finally:
        if run.path.is_dir():
            seal_directory(run.path)
            if run.finished and index["completed"]:
                _write_completion_anchor(run.path)
    print(json.dumps({"path": str(run.path), "formal": False}, ensure_ascii=False), flush=True)
    return run.path
