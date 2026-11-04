"""Reuse the published compact and traffic tools; prune only verified new raw files.

Offline check: python -B seal_case.py verify PATH/TO/CASE/evidence
The two frozen older method files must still match their recorded repository hashes.
The compact bundle contains its own standalone verifier and byte-exact six sources.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import threading

REPO = Path(__file__).resolve().parents[4]
OLD = REPO / "docs/experiments/2026-10-30-rule-trials"
RAW_FILES = ("positions.jsonl.gz", "events.jsonl.gz")
LOCK = threading.Lock()
_TOOLS = None


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tools():
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = (load(OLD / "evidence/compact_evidence.py", "staggered_compact"),
                  load(OLD / "analysis/bottleneck_trials.py", "staggered_traffic"))
    return _TOOLS


def method_hashes(compact, traffic):
    paths = {"compact": Path(compact.__file__), "wrapper": Path(traffic.__file__)}
    paths.update({name: Path(traffic.existing.__file__).with_name(name + ".py")
                  for name in ("bottleneck_attribution", "native_comparison", "complete_layers", "native_sumo")})
    return {name: sha(path) for name, path in paths.items()}


def prune_raw(run, batch, expected, verified=False):
    """No recursive operations; resolve every target and check every hash first."""
    if not verified:
        raise ValueError("raw pruning requires successful archive verification")
    batch, run = Path(batch).resolve(), Path(run).resolve()
    marker = batch / ".staggered-runner-owned"
    if not marker.is_file() or marker.read_text(encoding="utf-8") != str(batch):
        raise ValueError("batch ownership marker mismatch")
    if not run.is_relative_to(batch / "cases") or run == batch / "cases":
        raise ValueError("raw run is outside this owned batch/cases")
    targets = []
    for name in RAW_FILES:
        path = run / name
        resolved = path.resolve()
        if resolved.parent != run or path.is_symlink():
            raise ValueError("raw target resolves outside owned run")
        info = expected[name]
        if info.get("missing"):
            if path.exists():
                raise ValueError("missing raw file changed before pruning")
            continue
        if not path.is_file() or path.stat().st_size != info["bytes"] or sha(path) != info["sha256"]:
            raise ValueError("raw file changed after verification: " + name)
        targets.append((name, path))
    for _, path in targets:
        path.unlink()
    return {"deleted": [name for name, _ in targets], "bytes_released": sum(expected[n]["bytes"] for n, _ in targets)}


def verify(folder, check_originals=False):
    folder = Path(folder).resolve()
    saved = read(folder / "seal.json")
    compact, traffic = tools()
    if method_hashes(compact, traffic) != saved["method_sha256"]:
        raise ValueError("repository evidence methods changed; use the pinned method sources")
    for name, expected in saved["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or sha(folder / relative) != expected:
            raise ValueError("sealed evidence hash mismatch: " + name)
    basic = compact.verify(folder / "compact/bundle.tar.gz", check_originals=check_originals)
    metadata = read(folder / saved["traffic_metadata"])
    ledger = (folder / saved["traffic_metadata"]).parent
    with gzip.open(ledger / "vehicles.json.gz", "rt", encoding="utf-8") as stream:
        vehicles = json.load(stream)
    checks = traffic.verify_ledgers(ledger, metadata["run"], vehicles)
    if checks != metadata["ledger_verification"]:
        raise ValueError("traffic ledger verification differs")
    return {"cases_verified": basic["cases_verified"], "local_originals_checked": check_originals,
            "traffic_checks": checks, "compact": basic}


def seal(record, batch, prune=False):
    """Serial extraction keeps memory/disk bounded while simulations run in parallel."""
    with LOCK:
        run = Path(record["run_dir"]).resolve()
        folder = Path(record["case_output"]) / "evidence"
        folder.mkdir(exist_ok=False)
        compact, traffic = tools()
        write(folder / "manifest.json", [record])
        originals = {name: compact.raw_info(run / name) for name in RAW_FILES}
        compact.build([folder / "manifest.json"], folder / "compact", source_git=record["base_commit"])
        traffic.PROFILES[record["candidate"] + "_" + record["mode"]] = (record["candidate"], record["mode"])
        methods = method_hashes(compact, traffic)
        cached = traffic.case_cache(record, folder / "traffic", methods)
        metadata_path = Path(cached["ledger_dir"]) / "case.json"
        files = {path.relative_to(folder).as_posix(): sha(path)
                 for path in folder.rglob("*") if path.is_file()}
        saved = {"format": "staggered-case-evidence-v1", "record": record, "method_sha256": methods,
                 "files": files, "traffic_metadata": metadata_path.relative_to(folder).as_posix(),
                 "originals": originals, "prune_requested": prune,
                 "scope": "Original JSON/six sources; every 0/1 frame; observed gate brackets; existing region ledger. Full positions/events indexed only."}
        write(folder / "seal.json", saved)
        checked = verify(folder, check_originals=True)
        write(folder / "verification_originals.json", checked)
        offline = verify(folder, check_originals=False)
        write(folder / "verification_offline.json", offline)
        summary = {"evidence_dir": str(folder), "seal_status": "verified", "cases_verified": checked["cases_verified"],
                   "traffic_attribution_eligible": cached["attribution_eligible"],
                   "traffic_audit_issues": cached["audit_issues"]}
        if prune:
            summary["raw_pruning"] = prune_raw(run, batch, originals, verified=True)
        write(folder / "completion.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify",))
    parser.add_argument("folder", type=Path)
    parser.add_argument("--check-originals", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify(args.folder, args.check_originals)
    if args.report:
        write(args.report, result)
    print(json.dumps({key: value for key, value in result.items() if key != "compact"}))


if __name__ == "__main__":
    main()
