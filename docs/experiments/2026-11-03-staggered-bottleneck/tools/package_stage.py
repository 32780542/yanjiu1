"""Package sealed stages and verify them using only bundled Python-stdlib methods.

build --batch BATCH --output STAGE.tar.gz
verify STAGE.tar.gz [OTHER.tar.gz ...] --report verification.json
"""
import argparse
import builtins
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seal_case
import summarize

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
REL = HERE.relative_to(REPO).as_posix()
MAX_BYTES = 20_000_000
SCOPE = "Selected direct flags, observed gate brackets and measured-region ledgers; original JSON/six sources exact; full positions/events NOT included."


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()


def safe_member(name):
    path = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or path.is_absolute()
            or any(part in (".", "..") for part in path.parts) or path.as_posix() != name):
        raise ValueError("unsafe archive path: " + name)
    return path


def extract_checked(archive_path, destination, check_originals=False):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    seen, index = set(), None
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            safe_member(member.name)
            if not member.isfile() or member.name in seen:
                raise ValueError("non-file or duplicate archive member")
            seen.add(member.name)
            source = archive.extractfile(member)
            if index is None:
                if member.name != "index.json":
                    raise ValueError("index must be the first archive member")
                raw = source.read()
                index = json.loads(raw)
                if index.get("format") != "staggered-stage-v1":
                    raise ValueError("unsupported stage package")
                (destination / "index.json").write_bytes(raw)
                continue
            if member.name not in index["members"]:
                raise ValueError("unindexed member")
            expected = index["members"][member.name]
            if member.size != expected["bytes"]:
                raise ValueError("member size mismatch")
            target = destination.joinpath(*safe_member(member.name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            original = (Path(expected["original_path"]).open("rb")
                        if check_originals and expected.get("original_path") else None)
            digest, size = hashlib.sha256(), 0
            try:
                with target.open("xb") as stream:
                    while chunk := source.read(1024 * 1024):
                        if original is not None and original.read(len(chunk)) != chunk:
                            raise ValueError("archive/original bytes mismatch: " + member.name)
                        stream.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                if original is not None and original.read(1):
                    raise ValueError("original has additional bytes")
            finally:
                if original is not None:
                    original.close()
            if size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                raise ValueError("member hash or size mismatch: " + member.name)
    if index is None or seen != {"index.json", *index["members"]}:
        raise ValueError("missing indexed member")
    return index


def dependencies():
    old = "docs/experiments/2026-10-30-rule-trials/"
    variant = "variants/phase5g_pure_formation/"
    return [REL + "/" + name for name in ("package_stage.py", "seal_case.py", "summarize.py")] + [
        old + "evidence/compact_evidence.py", old + "analysis/bottleneck_trials.py",
        *(variant + "experiments/" + name + ".py" for name in
          ("bottleneck_attribution", "native_comparison", "complete_layers", "native_sumo", "__init__")),
        variant + "research/common.py", variant + "research/__init__.py"]


def stage_operations(batch, records):
    operations = {Path(row["operation"]["path"]).resolve() for row in records if row.get("operation")}
    output = str(batch.resolve())
    dates = {operation.name[:8] for operation in operations}
    if batch.name[:8].isdigit():
        dates.add(batch.name[:8])
    folders = {folder for date in dates for folder in (REPO / "results/operations").glob(date + "*")}
    for folder in sorted(folders):
        path = folder / "started.json"
        if not path.is_file():
            continue
        command = seal_case.read(path).get("command", [])
        if not any(str(part).endswith("runner.py") for part in command) or "--output" not in command:
            continue
        value = command[command.index("--output") + 1]
        if str((REPO / value).resolve()) == output:
            operations.add(folder.resolve())
    return sorted(operations)


def build(batch, output):
    batch, output = Path(batch).resolve(), Path(output).resolve()
    if output.exists() or output.with_suffix(".manifest.json").exists():
        raise ValueError("publication output already exists")
    records = summarize.protocol_records(batch)
    payload, mappings = {}, []

    def add(name, value):
        safe_member(name)
        if name in payload:
            raise ValueError("duplicate package member: " + name)
        payload[name] = value

    for filename in ("protocol.json", "manifest.json", "runner.py", "seal_case.py", ".staggered-runner-owned"):
        if (batch / filename).is_file():
            add("stage/" + filename, batch / filename)
    before = []
    for number, record in enumerate(records):
        checked = summarize.load_case(record)
        if record.get("seal_status") == "verified" and not (checked["evidence_verified"] and checked["protocol_verified"]):
            raise ValueError("prepack evidence/protocol failure: " + repr(checked.get("protocol_issues")) + str(checked.get("evidence_error")))
        case = Path(record["case_output"])
        base = f"stage/cases/{number:04d}"
        evidence = Path(record.get("evidence_dir", case / "evidence"))
        if evidence.is_dir():
            for path in sorted(evidence.rglob("*")):
                if path.is_file():
                    add(base + "/evidence/" + path.relative_to(evidence).as_posix(), path)
        for name in ("case_record.json", "worker.log", "seal_error.log", "worker_error.log"):
            if (case / name).is_file():
                add(base + "/" + name, case / name)
        mappings.append(dict(identity={name: record[name] for name in summarize.IDENTITY},
                             evidence=base + "/evidence", case=base,
                             original_evidence=str(evidence), original_case=str(case)))
        before.append(dict(identity=mappings[-1]["identity"], evidence_verified=checked["evidence_verified"],
                           protocol_verified=checked["protocol_verified"], status=record.get("status"),
                           safe=record.get("safe"), all_completed=record.get("all_completed")))
    protocol = seal_case.read(batch / "protocol.json")
    for name in protocol["sources"]:
        source = batch / "sources" / name
        frozen = seal_case.read(source / "freeze.json")
        if frozen["sha256"] != protocol["sources"][name]:
            raise ValueError("source freeze/protocol mismatch")
        for filename, digest in frozen["sha256"].items():
            if seal_case.sha(source / filename) != digest:
                raise ValueError("frozen runtime source changed")
            add("stage/sources/" + name + "/" + filename, source / filename)
        add("stage/sources/" + name + "/freeze.json", source / "freeze.json")
    operation_map = []
    for number, operation in enumerate(stage_operations(batch, records)):
        base = f"stage/operations/{number:04d}"
        for name in ("started.json", "result.json", "stdout.log", "stderr.log"):
            if (operation / name).is_file():
                add(base + "/" + name, operation / name)
        snapshot = operation / "runner_snapshot.py"
        if snapshot.is_file():
            digest = seal_case.sha(snapshot)
            name = "stage/run_logged_sources/" + digest + ".py"
            if name not in payload:
                add(name, snapshot)
        operation_map.append(dict(original=str(operation), relative=base))
    for relative in dependencies():
        add("repo/" + relative, REPO / relative)
    add("stage/prepack_verification.json", encoded(before))
    add("README.md", ("Self-contained selected-field SUMO stage evidence.\n\n" + SCOPE + "\n\n"
        "Original protocol/manifest/case JSON are byte-exact; old absolute paths are provenance only.\n"
        "index.json maps each case to a package-relative evidence directory. Runtime methods are bundled under repo/.\n"
        "Verify without original repository or SUMO:\npython -B repo/" + REL + "/package_stage.py verify PATH/TO/THIS.tar.gz --report verification.json\n\n"
        "The standalone compact verifier is also inside every compact bundle. Complete positions/events are hash-indexed only.\n"
        "Hashes alone cannot prove selected-field origin when the original trajectory is absent, or enable full spatial/collision re-auditing.\n"
        "Unsafe, censored and incomplete attempts remain present; successful evidence verification is not performance eligibility.\n").encode())
    members = {}
    for name, value in payload.items():
        if isinstance(value, Path):
            members[name] = dict(sha256=seal_case.sha(value), bytes=value.stat().st_size, original_path=str(value))
        else:
            members[name] = dict(sha256=hashlib.sha256(value).hexdigest(), bytes=len(value), original_path=None)
    index = dict(format="staggered-stage-v1", stage=batch.name, original_batch=str(batch), original_repo=str(REPO),
                 scope=SCOPE, cases=mappings, operations=operation_map, members=members,
                 package_tool="repo/" + REL + "/package_stage.py", case_count=len(records))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name, value in [("index.json", encoded(index)), *sorted(payload.items())]:
                size = value.stat().st_size if isinstance(value, Path) else len(value)
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = size, 0o644, 0
                stream = value.open("rb") if isinstance(value, Path) else io.BytesIO(value)
                with stream:
                    archive.addfile(info, stream)
    manifest = dict(archive=output.name, sha256=seal_case.sha(output), bytes=output.stat().st_size,
                    case_count=len(records), member_count=len(members), index_sha256=hashlib.sha256(encoded(index)).hexdigest(),
                    scope=SCOPE, under_20mb=output.stat().st_size < MAX_BYTES)
    seal_case.write(output.with_suffix(".manifest.json"), manifest)
    if not manifest["under_20mb"]:
        raise ValueError("stage exceeds 20MB; retain this attempt and split by complete planned profile")
    report = verify([output], check_originals=True)
    seal_case.write(output.with_suffix(".verification.json"), report)
    print(json.dumps(manifest), flush=True)
    return manifest


def check_extracted(roots):
    roots = [Path(root).resolve() for root in roots]
    indexes = [seal_case.read(root / "index.json") for root in roots]
    forbidden = [os.path.normcase(str(Path(index["original_repo"]).resolve())) for index in indexes]
    attempts = []
    original_open, original_io_open = builtins.open, io.open

    def guard(function):
        def guarded(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                value = os.path.normcase(os.path.abspath(os.fsdecode(file)))
                if any(value == base or value.startswith(base + os.sep) for base in forbidden):
                    attempts.append(value)
                    raise OSError("offline verifier forbids original-repository reads: " + value)
            return function(file, *args, **kwargs)
        return guarded

    builtins.open, io.open = guard(original_open), guard(original_io_open)
    cases = []
    try:
        for root, index in zip(roots, indexes):
            records = summarize.protocol_records(root / "stage")
            mappings = {tuple(case["identity"][key] for key in summarize.IDENTITY): case for case in index["cases"]}
            if len(records) != index["case_count"] or len(mappings) != len(records):
                raise ValueError("archive case mapping count mismatch")
            for record in records:
                mapping = mappings[tuple(record[key] for key in summarize.IDENTITY)]
                record["evidence_dir"] = str(root / mapping["evidence"])
                checked = summarize.load_case(record)
                if not checked["evidence_verified"] or not checked["protocol_verified"]:
                    raise ValueError("offline case verification failed: " + str(checked.get("evidence_error")) + repr(checked["protocol_issues"]))
                checked["evidence_dir"] = mapping["evidence"]
                checked["worker_log"] = mapping["case"] + "/worker.log"
                checked["archive_stage"] = index["stage"]
                cases.append(checked)
            protocol = seal_case.read(root / "stage/protocol.json")
            for candidate in protocol["sources"]:
                source = root / "stage/sources" / candidate
                frozen = seal_case.read(source / "freeze.json")
                if frozen["sha256"] != protocol["sources"][candidate]:
                    raise ValueError("offline freeze/protocol mismatch")
                for name, digest in frozen["sha256"].items():
                    if seal_case.sha(source / name) != digest:
                        raise ValueError("offline frozen source mismatch")
        pairs = summarize.build_pairs(cases)
        public_cases = [{key: value for key, value in case.items() if not key.startswith("_")} for case in cases]
        return dict(cases_verified=len(cases), protocol_verified=len(cases),
                    original_repository_reads=attempts, original_paths_required=False, simulations_run=False,
                    physical_safe_count=sum(case.get("safe") is True for case in cases),
                    all_completed_count=sum(case.get("all_completed") is True for case in cases),
                    pairs=len(pairs), eligible_pairs=sum(pair["pair_eligible"] for pair in pairs),
                    cases=public_cases, paired=pairs, scope=SCOPE)
    finally:
        builtins.open, io.open = original_open, original_io_open


def verify(archives, check_originals=False):
    with tempfile.TemporaryDirectory(prefix="stage-offline-") as temporary:
        root = Path(temporary)
        roots, indexes = [], []
        for number, archive in enumerate(archives):
            target = root / f"p{number:02d}"
            indexes.append(extract_checked(archive, target, check_originals))
            roots.append(target)
        report_path = root / "offline.json"
        tool = roots[0] / indexes[0]["package_tool"]
        command = [sys.executable, "-I", "-B", str(tool), "check-extracted", *map(str, roots), "--report", str(report_path)]
        env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME")}
        process = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=600)
        if process.returncode:
            raise ValueError("bundled offline verifier failed: " + process.stderr[-4000:])
        report = seal_case.read(report_path)
        report.update(archive_members_verified=sum(len(index["members"]) for index in indexes),
                      archive_original_bytes_compared=check_originals,
                      archives=[dict(path=str(Path(path).resolve()), sha256=seal_case.sha(path), bytes=Path(path).stat().st_size) for path in archives])
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--batch", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("archives", type=Path, nargs="+")
    check.add_argument("--report", type=Path, required=True)
    check.add_argument("--check-originals", action="store_true")
    extracted = commands.add_parser("check-extracted")
    extracted.add_argument("roots", type=Path, nargs="+")
    extracted.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args.batch, args.output)
    else:
        report = check_extracted(args.roots) if args.command == "check-extracted" else verify(args.archives, args.check_originals)
        seal_case.write(args.report, report)
        print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "paired")}), flush=True)


if __name__ == "__main__":
    main()
