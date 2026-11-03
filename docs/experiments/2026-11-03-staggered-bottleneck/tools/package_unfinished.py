"""Thin archival wrapper for TM_long600_16: 13 sealed, 3 unfinalized timeouts.

Partial raw files remain local and are hash-indexed, never parsed or deleted.
"""
import argparse
import builtins
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import package_stage as sealed
import seal_case
import summarize

REPO, REL = sealed.REPO, sealed.REL
SCOPE = "13 sealed cases independently verified; 3 unfinalized compute timeouts archived as metadata only. All extant partial raw files remain local, SHA/bytes indexed only. No physical completion conclusion for these 3 cases."


def classify(row):
    if row.get("seal_status") == "verified":
        return "sealed"
    if row.get("returncode") == 124 and row.get("status") == "starting":
        return "unverified_compute_timeout"
    raise ValueError("unsupported unfinalized case; do not relabel its outcome")


def case_files(case):
    stored, raw = [], []
    for path in sorted(Path(case).rglob("*")):
        if not path.is_file():
            continue
        if path.name in seal_case.RAW_FILES:
            raw.append(dict(name=path.name, relative=path.relative_to(case).as_posix(), local_path=str(path.resolve()),
                            sha256=seal_case.sha(path), bytes=path.stat().st_size, included=False))
        else:
            stored.append(path)
    return stored, raw


def write_archive(output, index, payload):
    output = Path(output)
    if output.exists():
        raise ValueError("output exists")
    members = {}
    for name, value in payload.items():
        sealed.safe_member(name)
        members[name] = dict(sha256=seal_case.sha(value) if isinstance(value, Path) else hashlib.sha256(value).hexdigest(),
            bytes=value.stat().st_size if isinstance(value, Path) else len(value),
            original_path=str(value.resolve()) if isinstance(value, Path) else None)
    index.update(format="staggered-stage-v1", members=members)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=9) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for name, value in [("index.json", sealed.encoded(index)), *sorted(payload.items())]:
                info = tarfile.TarInfo(name)
                info.size = value.stat().st_size if isinstance(value, Path) else len(value)
                info.mode = 0o644
                with (value.open("rb") if isinstance(value, Path) else io.BytesIO(value)) as stream:
                    archive.addfile(info, stream)
    if output.stat().st_size >= sealed.MAX_BYTES:
        raise ValueError("archive exceeds 20MB; preserve this attempt, do not select successful cases")


def check_extracted(roots):
    if len(roots) != 1:
        raise ValueError("one whole unfinished stage per verification")
    root = Path(roots[0]).resolve()
    index = seal_case.read(root / "index.json")
    if index.get("kind") != "TM_long600_16_unfinished_metadata":
        raise ValueError("unsupported unfinished archive")
    original_repo = os.path.normcase(index["original_repo"])
    original_open, original_io_open, attempts = builtins.open, io.open, []

    def guard(function):
        def guarded(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                value = os.path.normcase(os.path.abspath(os.fsdecode(file)))
                if value == original_repo or value.startswith(original_repo + os.sep):
                    attempts.append(value)
                    raise OSError("original repository reads forbidden")
            return function(file, *args, **kwargs)
        return guarded

    builtins.open, io.open = guard(original_open), guard(original_io_open)
    try:
        records = summarize.protocol_records(root / "stage")
        mappings = {tuple(row["identity"][key] for key in summarize.IDENTITY): row for row in index["cases"]}
        if len(records) != 16 or len(mappings) != 16:
            raise ValueError("whole 16-case plan required")
        verified, unfinished = 0, []
        for record in records:
            mapping = mappings[tuple(record[key] for key in summarize.IDENTITY)]
            kind = classify(record)
            if kind == "sealed":
                record["evidence_dir"] = str(root / mapping["evidence"])
                checked = summarize.load_case(record)
                if not checked["evidence_verified"] or not checked["protocol_verified"]:
                    raise ValueError("sealed member failed archive/protocol verification")
                verified += 1
                continue
            run = root / mapping["run"]
            inp, result = (seal_case.read(run / name) for name in ("input.json", "result.json"))
            if result.get("status") != "starting":
                raise ValueError("unfinalized result is no longer starting")
            task, protocol = record["_task"], record["_protocol"]
            for field, key in dict(mode="mode", seed="seed", scenario="scenario", flow_veh_h_lane="flow",
                                   demand_duration_s="duration", max_time_s="max_time").items():
                if inp["case"][field] != task[key]:
                    raise ValueError("unfinalized input/protocol mismatch: " + field)
            expected = protocol["sources"][record["candidate"]]
            if result.get("source_sha256") != inp["source_sha256"]:
                raise ValueError("starting input/result source mismatch")
            for name, digest in inp["source_sha256"].items():
                if expected.get(name) != digest or seal_case.sha(run / "source" / name) != digest:
                    raise ValueError("unfinalized frozen source mismatch")
            operation = root / mapping["operation"]
            execution = seal_case.read(operation / "result.json")
            if execution["returncode"] != 124 or execution["status"] != "timeout":
                raise ValueError("wall-clock timeout evidence mismatch")
            unfinished.append(dict(identity=mapping["identity"], classification=kind, returncode=124,
                original_result_status="starting", physical_completion="undetermined", eligible=False,
                trips_present=(run / "trips.json").is_file(), raw_payload_included=False))
        if verified != 13 or len(unfinished) != 3:
            raise ValueError("expected 13 sealed and 3 unfinalized attempts")
        return dict(planned_cases=16, sealed_cases_verified=verified, unverified_compute_timeouts=unfinished,
                    original_repository_reads=attempts, original_paths_required=False, raw_contents_verified=False,
                    raw_index=index["raw_index"], simulations_run=False, scope=SCOPE)
    finally:
        builtins.open, io.open = original_open, original_io_open


def build(batch, output):
    batch, output = Path(batch).resolve(), Path(output).resolve()
    if batch.name != "20261103_TM_long600_16":
        raise ValueError("this wrapper is only for TM_long600_16")
    records = summarize.protocol_records(batch)
    if len(records) != 16 or sum(classify(row) == "sealed" for row in records) != 13:
        raise ValueError("expected the complete original 16-case matrix")
    payload, cases, raw_index = {}, [], []
    for name in ("protocol.json", "manifest.json", "runner.py", "seal_case.py", ".staggered-runner-owned"):
        if (batch / name).is_file():
            payload["stage/" + name] = batch / name
    operations = sealed.stage_operations(batch, records)
    operation_map = {str(path): f"stage/operations/{i:04d}" for i, path in enumerate(operations)}
    for number, row in enumerate(records):
        case, base = Path(row["case_output"]), f"stage/cases/{number:04d}"
        stored, raw = case_files(case)
        for path in stored:
            payload[base + "/" + path.relative_to(case).as_posix()] = path
        identity = {key: row[key] for key in summarize.IDENTITY}
        raw_index.extend({**entry, "identity": identity} for entry in raw)
        cases.append(dict(identity=identity, case=base, evidence=base + "/evidence",
            run=base + "/" + Path(row["run_dir"]).name,
            operation=operation_map[str(Path(row["operation"]["path"]).resolve())], classification=classify(row)))
    for path in sorted((batch / "sources").rglob("*")):
        if path.is_file() and "tmp" not in path.relative_to(batch / "sources").parts:
            payload["stage/sources/" + path.relative_to(batch / "sources").as_posix()] = path
    for operation in operations:
        base = operation_map[str(operation)]
        for name in ("started.json", "result.json", "stdout.log", "stderr.log"):
            if (operation / name).is_file():
                payload[base + "/" + name] = operation / name
        snapshot = operation / "runner_snapshot.py"
        if snapshot.is_file():
            payload["stage/run_logged_sources/" + seal_case.sha(snapshot) + ".py"] = snapshot
    for relative in [*sealed.dependencies(), REL + "/package_unfinished.py"]:
        payload["repo/" + relative] = REPO / relative
    payload["README.md"] = (SCOPE + "\n\nThis archive preserves the full original 16-case protocol/manifest and every extant non-positions/events file.\n"
        "The 13 sealed cases retain their complete evidence. Missing trips in unfinalized cases remain missing.\n"
        "Partial raw SHA/bytes/local paths are inventory only; raw remains local, is not reconstructed or parsed here.\n"
        "Return 124 and result=starting show a computation timeout, not a physical time_limit or inability to drain.\n").encode()
    index = dict(kind="TM_long600_16_unfinished_metadata", original_repo=str(REPO), original_batch=str(batch),
                 stage=batch.name, case_count=16, cases=cases, raw_index=raw_index, scope=SCOPE,
                 package_tool="repo/" + REL + "/package_unfinished.py")
    write_archive(output, index, payload)
    report = sealed.verify([output], check_originals=True)
    seal_case.write(output.with_suffix(".verification.json"), report)
    seal_case.write(output.with_suffix(".manifest.json"), dict(archive=output.name, sha256=seal_case.sha(output),
        bytes=output.stat().st_size, planned_cases=16, sealed_cases=13, unverified_compute_timeouts=3,
        raw_payload_included=False, raw_index_bytes=sum(row["bytes"] for row in raw_index), scope=SCOPE))
    print(json.dumps(dict(archive=str(output), bytes=output.stat().st_size, sealed=13, unverified=3)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--batch", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("check-extracted")
    check.add_argument("roots", type=Path, nargs="+")
    check.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args.batch, args.output)
    else:
        seal_case.write(args.report, check_extracted(args.roots))


if __name__ == "__main__":
    main()
