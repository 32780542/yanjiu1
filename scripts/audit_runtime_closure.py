"""Compute the reviewable, repository-relative Phase 5G runtime closure.

The audit is intentionally conservative: local Python imports are followed, the
test launchers' named test modules are included, and the Phase 5G source/input
manifests are treated as hard dependencies.  Generated evidence and historical
variants are never valid closure members.
"""

from __future__ import annotations

import argparse
import ast
from collections import deque
from pathlib import Path, PurePosixPath
import re
import stat


PHASE5G_ROOT = PurePosixPath("variants/phase5g_pure_formation")
MANDATORY_PHASE5G_SEEDS = (
    "runrun.py",
    "demo/__init__.py",
    "demo/sumo_gui.py",
    "configs/tools.json",
    "scripts/run_logged.py",
    "scripts/audit_runtime_closure.py",
    "scenarios/cai2024/bottleneck.net.xml",
    "tests/test_runrun_demo.py",
    "tests/test_phase5g_tracked_baseline.py",
    "variants/phase5g_pure_formation/run.py",
    "variants/phase5g_pure_formation/configs/phase5g.json",
    "variants/phase5g_pure_formation/scenarios/cai2024/bottleneck.net.xml",
)
_MANIFEST_NAMES = frozenset((
    "SOURCE_FILES",
    "INPUTS",
    "TRACKED_BASELINE_FILES",
))
_TEST_MODULE = re.compile(r"^(test_[A-Za-z0-9_]+)\.")
_WINDOWS_REPARSE_POINT = 0x400
_PHASE5G_ENTRY_IMPORTS = frozenset((
    "experiments.phase5g",
    "experiments.phase5g_replay",
))
_PHASE5_UNUSED_IMPORTS = frozenset((
    "experiments.phase5_replay",
    "experiments.phase5_audit",
    "experiments.phase5_r5_audit",
))


def _repo_path(root: Path, raw: str | Path) -> tuple[str, Path]:
    text = str(raw).replace("\\", "/")
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"closure path must be repo-relative: {raw}")
    relative = pure.as_posix()
    _reject_forbidden(relative)
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, OSError, ValueError) as error:
        raise ValueError(f"missing or escaped closure path: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"closure path is not a regular file: {relative}")
    info = candidate.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or attributes & _WINDOWS_REPARSE_POINT:
        raise ValueError(f"closure path is a reparse point: {relative}")
    return relative, candidate


def _reject_forbidden(relative: str) -> None:
    pure = PurePosixPath(relative)
    lowered = relative.lower()
    parts = tuple(part.lower() for part in pure.parts)
    forbidden = (
        "results" in parts
        or "tmp" in parts
        or lowered.endswith(".pdf")
        or parts[:2] == ("docs", "archive")
        or pure.name.lower() in {".env", "id_rsa", "id_ed25519"}
        or lowered.endswith((".pem", ".p12", ".pfx", ".key"))
    )
    if pure.parts[:1] == ("variants",):
        forbidden = forbidden or pure.parts[:2] != tuple(PHASE5G_ROOT.parts)
    if forbidden:
        raise ValueError(f"forbidden closure path: {relative}")


def _search_root(root: Path, relative: str) -> Path:
    if relative == PHASE5G_ROOT.as_posix() or relative.startswith(
        PHASE5G_ROOT.as_posix() + "/"
    ):
        return root.joinpath(*PHASE5G_ROOT.parts)
    return root


def _relative_to_root(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _package_inits(root: Path, search_root: Path, path: Path) -> tuple[str, ...]:
    found = []
    parent = path.parent
    while parent != search_root and search_root in parent.parents:
        init = parent / "__init__.py"
        if init.is_file():
            found.append(_relative_to_root(root, init))
        parent = parent.parent
    return tuple(found)


def _module_candidate(search_root: Path, module: str) -> tuple[Path | None, bool]:
    parts = module.split(".") if module else []
    if not parts:
        return None, False
    module_file = search_root.joinpath(*parts).with_suffix(".py")
    if module_file.is_file():
        return module_file, False
    package_init = search_root.joinpath(*parts, "__init__.py")
    if package_init.is_file():
        return package_init, True
    return None, False


def _local_top_exists(search_root: Path, module: str) -> bool:
    top = module.split(".", 1)[0]
    return (search_root / f"{top}.py").is_file() or (search_root / top).is_dir()


def _defined_names(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
    return frozenset(names)


def _relative_import_module(path: Path, search_root: Path, node: ast.ImportFrom) -> str:
    relative = path.relative_to(search_root)
    package = list(relative.parent.parts)
    if path.name == "__init__.py":
        package = list(relative.parent.parts)
    climb = node.level - 1
    if climb > len(package):
        return ""
    if climb:
        package = package[:-climb]
    if node.module:
        package.extend(node.module.split("."))
    return ".".join(package)


def _python_dependencies(root: Path, relative: str, path: Path) -> set[str]:
    search_root = _search_root(root, relative)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    dependencies = set(_package_inits(root, search_root, path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                candidate, _ = _module_candidate(search_root, module)
                if candidate is not None:
                    dependencies.add(_relative_to_root(root, candidate))
                elif _local_top_exists(search_root, module):
                    raise ValueError(
                        f"unresolved local import {module!r} in {relative}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = (
                _relative_import_module(path, search_root, node)
                if node.level
                else (node.module or "")
            )
            if (
                relative == f"{PHASE5G_ROOT.as_posix()}/run.py"
                and module
                and module.split(".", 1)[0] in {"experiments", "research"}
                and module not in _PHASE5G_ENTRY_IMPORTS
            ):
                continue
            if (
                relative == f"{PHASE5G_ROOT.as_posix()}/experiments/phase5.py"
                and module in _PHASE5_UNUSED_IMPORTS
            ):
                continue
            candidate, is_package = _module_candidate(search_root, module)
            if candidate is None:
                if module and _local_top_exists(search_root, module):
                    raise ValueError(
                        f"unresolved local import {module!r} in {relative}"
                    )
                continue
            dependencies.add(_relative_to_root(root, candidate))
            if is_package:
                definitions = _defined_names(candidate)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    child_name = f"{module}.{alias.name}" if module else alias.name
                    child, _ = _module_candidate(search_root, child_name)
                    if child is not None:
                        dependencies.add(_relative_to_root(root, child))
                    elif alias.name not in definitions:
                        raise ValueError(
                            f"unresolved local import {child_name!r} in {relative}"
                        )
    dependencies.update(_manifest_dependencies(root, search_root, tree, relative))
    return dependencies


def _string_items(node: ast.AST) -> tuple[str, ...]:
    try:
        value = ast.literal_eval(node)
    except (TypeError, ValueError):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list, set)) and all(
        isinstance(item, str) for item in value
    ):
        return tuple(value)
    return ()


def _manifest_dependencies(
    root: Path, search_root: Path, tree: ast.AST, relative: str
) -> set[str]:
    dependencies: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            value = node.value
            if any(
                isinstance(target, ast.Name) and target.id in _MANIFEST_NAMES
                for target in targets
            ):
                for raw in _string_items(value):
                    candidate = search_root / Path(raw)
                    if not candidate.is_file():
                        raise ValueError(
                            f"missing manifest dependency {raw!r} in {relative}"
                        )
                    dependencies.add(_relative_to_root(root, candidate))
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name == "settings" and node.args:
                values = _string_items(node.args[0])
                if values:
                    candidate = search_root / "configs" / f"{values[0]}.json"
                    if not candidate.is_file():
                        raise ValueError(
                            f"missing settings dependency {values[0]!r} in {relative}"
                        )
                    dependencies.add(_relative_to_root(root, candidate))
    return dependencies


def _launcher_dependencies(root: Path, relative: str, path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    dependencies = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        match = _TEST_MODULE.match(node.value)
        if not match:
            continue
        test_path = path.parent / f"{match.group(1)}.py"
        if not test_path.is_file():
            raise ValueError(
                f"unresolved launcher test {match.group(1)!r} in {relative}"
            )
        dependencies.add(_relative_to_root(root, test_path))
    return dependencies


def compute_runtime_closure(
    repo_root: str | Path,
    entries: tuple[str, ...] | list[str],
    launchers: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Return a sorted, validated closure without consulting Git state."""
    root = Path(repo_root).resolve(strict=True)
    requested = list(entries) + list(launchers)
    if (root / "runrun.py").is_file() and (
        root.joinpath(*PHASE5G_ROOT.parts, "run.py")
    ).is_file():
        requested.extend(MANDATORY_PHASE5G_SEEDS)
    queue = deque(requested)
    launcher_set = {str(item).replace("\\", "/") for item in launchers}
    selected: set[str] = set()
    while queue:
        raw = queue.popleft()
        relative, path = _repo_path(root, raw)
        if relative in selected:
            continue
        selected.add(relative)
        if path.suffix.lower() != ".py":
            continue
        dependencies = _python_dependencies(root, relative, path)
        if relative in launcher_set:
            dependencies.update(_launcher_dependencies(root, relative, path))
        queue.extend(sorted(dependencies))
    return tuple(sorted(selected))


def write_closure(path: str | Path, closure: tuple[str, ...]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(f"{item}\n" for item in closure), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--entry", action="append", default=[])
    parser.add_argument("--launcher", action="append", default=[])
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    closure = compute_runtime_closure(root, args.entry, args.launcher)
    write_closure(root / args.output, closure)
    for item in closure:
        print(item)
    print(f"closure_count={len(closure)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
