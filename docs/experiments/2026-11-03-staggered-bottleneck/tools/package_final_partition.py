"""Partition complete plans by road and fixed flow profile, preserving originals.

The frozen package_stage.py remains unchanged; generated views are explicit.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import package_stage as original
import seal_case
import summarize


def in_profile(row, profile):
    if profile not in ("low", "high"):
        raise ValueError("unknown fixed flow profile")
    return row["flow"] <= 1500 if profile == "low" else row["flow"] >= 2000


def audit_partition(full_protocol, full_manifest, part_protocol, part_manifest, scenario, profile):
    planned, actual = summarize.unique(full_protocol["tasks"]), summarize.unique(full_manifest)
    expected = {key: value for key, value in planned.items() if value["scenario"] == scenario and in_profile(value, profile)}
    selected, rows = summarize.unique(part_protocol["tasks"]), summarize.unique(part_manifest)
    if set(planned) != set(actual) or not expected or selected != expected or set(rows) != set(expected):
        raise ValueError("partition is not the complete planned road group")
    if any(rows[key] != actual[key] for key in expected):
        raise ValueError("partition manifest changed original records")
    return dict(rule="complete preplanned road and fixed flow profile, independent of outcomes", scenario=scenario, profile=profile,
                full_plan_cases=len(planned), partition_cases=len(expected))


def check_extracted(roots):
    report = original.check_extracted(roots)
    partitions = []
    for root in map(Path, roots):
        descriptor = seal_case.read(root / "partition.json")
        partitions.append(audit_partition(seal_case.read(root / "stage/full_protocol.json"),
            seal_case.read(root / "stage/full_manifest.json"), seal_case.read(root / "stage/protocol.json"),
            seal_case.read(root / "stage/manifest.json"), descriptor["scenario"], descriptor["profile"]))
    report["partitions"] = partitions
    return report


def build(batch, scenario, profile, output):
    batch, output = Path(batch).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("output exists")
    full_protocol, full_manifest = (seal_case.read(batch / name) for name in ("protocol.json", "manifest.json"))
    protocol = {**full_protocol, "tasks": [row for row in full_protocol["tasks"] if row["scenario"] == scenario and in_profile(row, profile)]}
    manifest = [row for row in full_manifest if row["scenario"] == scenario and in_profile(row, profile)]
    descriptor = audit_partition(full_protocol, full_manifest, protocol, manifest, scenario, profile)
    descriptor.update(original_batch=str(batch), original_protocol_sha256=seal_case.sha(batch / "protocol.json"),
                      original_manifest_sha256=seal_case.sha(batch / "manifest.json"))
    with tempfile.TemporaryDirectory(prefix="road-view-") as directory:
        temporary = Path(directory)
        view = temporary / (batch.name + "_" + scenario + "_" + profile)
        view.mkdir()
        protocol["arguments"] = {**full_protocol["arguments"], "scenarios": [scenario], "flows": sorted({row["flow"] for row in manifest}), "output": str(view)}
        seal_case.write(view / "protocol.json", protocol)
        seal_case.write(view / "manifest.json", manifest)
        for name in ("runner.py", "seal_case.py", ".staggered-runner-owned"):
            if (batch / name).is_file():
                shutil.copyfile(batch / name, view / name)
        for candidate in protocol["sources"]:
            frozen = seal_case.read(batch / "sources" / candidate / "freeze.json")
            for filename in (*frozen["sha256"], "freeze.json"):
                target = view / "sources" / candidate / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(batch / "sources" / candidate / filename, target)
        interim = temporary / "interim.tar.gz"
        original.build(view, interim)
        extracted = temporary / "extracted"
        index = original.extract_checked(interim, extracted, check_originals=True)
        payload = {name: extracted / name for name in index["members"]}
        additions = {"stage/full_protocol.json": batch / "protocol.json", "stage/full_manifest.json": batch / "manifest.json",
                     "partition.json": original.encoded(descriptor),
                     "repo/" + original.REL + "/package_final_partition.py": Path(__file__).resolve()}
        # The whole batch's outer operation is not found under the generated view path.
        worker_operations = {Path(row["operation"]["path"]).resolve() for row in full_manifest if row.get("operation")}
        outer = [path for path in original.stage_operations(batch, full_manifest) if path not in worker_operations]
        for number, operation in enumerate(outer):
            for name in ("started.json", "result.json", "stdout.log", "stderr.log"):
                if (operation / name).is_file():
                    additions[f"stage/full_batch_operations/{number:04d}/" + name] = operation / name
        additions["README.md"] = ("Complete preplanned road and fixed flow profile partition; no outcome-based selection.\n\n"
            "stage/protocol.json and manifest.json are generated subset views, not replacements for the whole originals.\n"
            "stage/full_protocol.json and full_manifest.json preserve the exact entire original batch bytes.\n"
            "partition.json fixes the selected road/profile and full/selected planned identities. Low is all flows <=1500; high is all flows >=2000. All selected original case evidence remains exact.\n"
            "Use bundled package_stage.py verify: the indexed package_tool invokes package_final_partition.py and audits membership too.\n"
            + original.SCOPE + "\n").encode()
        for name, info in index["members"].items():
            if info.get("original_path") and Path(info["original_path"]).is_relative_to(view):
                relative = Path(info["original_path"]).relative_to(view)
                if relative.as_posix() in ("protocol.json", "manifest.json"):
                    info["original_path"] = None
                    info["generated_partition_view"] = True
                else:
                    info["original_path"] = str(batch / relative)
        for name, value in additions.items():
            payload[name] = value
            index["members"][name] = dict(sha256=seal_case.sha(value) if isinstance(value, Path) else hashlib.sha256(value).hexdigest(),
                bytes=value.stat().st_size if isinstance(value, Path) else len(value),
                original_path=str(value) if isinstance(value, Path) else None)
        index.update(original_batch=str(batch), partition=descriptor,
                     package_tool="repo/" + original.REL + "/package_final_partition.py")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=9) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as archive:
                for name, value in [("index.json", original.encoded(index)), *sorted(payload.items())]:
                    original.safe_member(name)
                    info = tarfile.TarInfo(name)
                    info.size = value.stat().st_size if isinstance(value, Path) else len(value)
                    info.mode = 0o644
                    with (value.open("rb") if isinstance(value, Path) else io.BytesIO(value)) as stream:
                        archive.addfile(info, stream)
        if output.stat().st_size >= original.MAX_BYTES:
            raise ValueError("complete road/profile group still exceeds 20MB; preserve attempt")
        report = original.verify([output], check_originals=True)
        seal_case.write(output.with_suffix(".verification.json"), report)
        summary = dict(archive=output.name, sha256=seal_case.sha(output), bytes=output.stat().st_size,
                       case_count=len(manifest), under_20mb=True, partition=descriptor,
                       index_sha256=hashlib.sha256(original.encoded(index)).hexdigest())
        seal_case.write(output.with_suffix(".manifest.json"), summary)
        print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--batch", type=Path, required=True)
    make.add_argument("--scenario", choices=("straight3", "lane_drop"), required=True)
    make.add_argument("--profile", choices=("low", "high"), required=True)
    make.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("check-extracted")
    check.add_argument("roots", type=Path, nargs="+")
    check.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args.batch, args.scenario, args.profile, args.output)
    else:
        seal_case.write(args.report, check_extracted(args.roots))


if __name__ == "__main__":
    main()
