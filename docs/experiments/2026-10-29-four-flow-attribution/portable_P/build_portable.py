"""Build one portable P100 evidence bundle; originals remain byte-for-byte read-only."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile


BASE = Path(__file__).resolve().parent
ORIGINAL = BASE.parent / "P_analysis"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stream_sha(stream):
    digest, size = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
        size += len(block)
    return digest.hexdigest(), size


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def gzip_exact(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as stream, target.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, compresslevel=9, mtime=0) as zipped:
            shutil.copyfileobj(stream, zipped, 1024 * 1024)
    with gzip.open(target, "rb") as stream:
        decoded_sha, decoded_size = stream_sha(stream)
    expected = sha(source)
    if decoded_sha != expected or decoded_size != source.stat().st_size:
        raise ValueError("Lossless gzip verification failed: " + str(source))
    return dict(original=str(source), portable=str(target.relative_to(BASE)).replace("\\", "/"),
                original_sha256=expected, original_bytes=source.stat().st_size,
                compressed_sha256=sha(target), compressed_bytes=target.stat().st_size,
                decoded_sha256=decoded_sha, lossless=True)


def main():
    if (BASE / "bundle_hashes.json").exists():
        raise FileExistsError("Portable bundle already finalized; do not overwrite")
    d_portable = BASE.parent / "portable_D_baseline"
    d_before = {str(p.relative_to(d_portable)): sha(p) for p in d_portable.rglob("*") if p.is_file()}
    attributes = BASE.parents[3] / ".gitattributes"
    attributes_before = sha(attributes)
    before = {str(p.relative_to(ORIGINAL)): sha(p) for p in ORIGINAL.rglob("*") if p.is_file()}
    original_manifest = read(ORIGINAL / "artifact_hashes.json")
    if any(before.get(name) != value for name, value in original_manifest.items()):
        raise ValueError("Original formal evidence hashes do not match")
    audit = read(ORIGINAL / "data_audit.json")
    protocol = audit["protocol"]
    release = read(ORIGINAL / "P_release_freeze.json")
    h_post = read(ORIGINAL / "postverification.json")
    if (not audit["P_release_audit"]["passed"] or not h_post["passed"]
            or protocol.get("jobs") != 4 or release["source_sha256"] != protocol["source_sha256"]
            or protocol["source_sha256"]["noa/native_rules.py"] != "8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864"
            or protocol["source_sha256"]["experiments/native_sumo.py"] != "6a530098146e85a637b4f29d580d61877c7a54b3a7e15858724651d80e8956b0"
            or protocol["wrapper_sha256"] != "cf7a371677a08dd312ae904f410d26070452d464314b12b0a2b5943f0b2d1385"):
        raise ValueError("P release, jobs, wrapper or postverification binding mismatch")
    study = Path(audit["study_dir"])
    attr = read(ORIGINAL / "attribution/summary.json")
    if not audit["passed"] or len(attr["runs"]) != 100 or not all(r["attribution_eligible"] for r in attr["runs"]):
        raise ValueError("Original P100 analysis is not fully eligible")
    lossless = []
    compressed = [
        ("attribution/summary.json", "data/attribution_summary.json.gz"),
        ("attribution/vehicles.csv", "data/vehicles.csv.gz"),
        ("data_audit.json", "provenance/data_audit.json.gz"),
        ("manifest.json", "provenance/original_case_manifest.json.gz"),
        ("run_status.json", "provenance/run_status.json.gz"),
        ("postverification.json", "provenance/original_postverification.json.gz"),
    ]
    for flow in (500, 750, 1000, 1500):
        compressed += [(f"flow_{flow}/native_comparison/summary.json", f"data/native_flow_{flow}.json.gz"),
                       (f"flow_{flow}/recovery/summary.json", f"data/recovery_flow_{flow}.json.gz")]
    for old, new in compressed:
        lossless.append(gzip_exact(ORIGINAL / old, BASE / new))
    existing_gzip = ORIGINAL / "attribution/region_steps.csv.gz"
    region_target = BASE / "data/region_steps.csv.gz"
    shutil.copy2(existing_gzip, region_target)
    if sha(existing_gzip) != sha(region_target):
        raise ValueError("Original region-step gzip changed on copy")
    with gzip.open(region_target, "rb") as stream:
        decoded_sha, decoded_bytes = stream_sha(stream)
    lossless.append(dict(original=str(existing_gzip), portable="data/region_steps.csv.gz",
                         original_sha256=sha(existing_gzip), compressed_sha256=sha(region_target),
                         original_bytes=existing_gzip.stat().st_size, compressed_bytes=region_target.stat().st_size,
                         decoded_sha256=decoded_sha, decoded_bytes=decoded_bytes, lossless=True,
                         note="Already gzip; copied exact compressed bytes without recompression"))
    provenance = BASE / "provenance"
    for old, new in (("protocol.json", "protocol.json"), ("outer_operation_result.json", "outer_operation_result.json"),
                     ("analysis_status.json", "analysis_status.json"), ("artifact_hashes.json", "original_artifact_hashes.json")):
        shutil.copy2(ORIGINAL / old, provenance / new)
    source_manifest = {}
    for name, expected in protocol["source_sha256"].items():
        src, target = study / "source" / name, BASE / "source" / name
        if sha(src) != expected:
            raise ValueError("Controlled source does not match protocol: " + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        source_manifest[name] = dict(sha256=expected, role="One deduplicated copy of the six frozen P controlled modules")
    frozen = ORIGINAL / "source_evaluators"
    for name in ("bottleneck_attribution.py", "native_comparison.py", "native_recovery.py", "__init__.py"):
        src = frozen / "experiments" / name
        target = BASE / "source/experiments" / name
        shutil.copy2(src, target)
        source_manifest["experiments/" + name] = dict(sha256=sha(src), role="Frozen independent evaluator")
    shutil.copy2(ORIGINAL / "run_flow_study.py", BASE / "source/run_flow_study.py")
    source_manifest["run_flow_study.py"] = dict(sha256=sha(BASE / "source/run_flow_study.py"), role="Frozen P100 experiment wrapper")
    shutil.copy2(frozen / "freeze.json", provenance / "evaluator_freeze.json")
    write(provenance / "source_manifest.json", source_manifest)
    cases, archived = [], []
    metadata_names = ("P_release_freeze.json", "P_analysis_expected.json", "parallel_study_equivalence.json", "P_protocol.md",
                      "four_flow_results.csv", "four_flow_results.json", "analyze_four_flow_P.source.py",
                      "postverify_four_flow_P.source.py", "compile_P_results.source.py")
    target = BASE / "data/raw_case_json.tar.gz"
    with target.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, compresslevel=9, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for run in sorted(attr["runs"], key=lambda r: (r["flow_veh_h_lane"], r["seed"], r["scenario"], r["mode"])):
                    case_id = f"f{run['flow_veh_h_lane']:g}_s{run['seed']}_{run['scenario']}_{run['mode']}"
                    path = Path(run["case_dir"])
                    record = dict(case_id=case_id, original_case_dir=str(path),
                                  flow_veh_h_lane=run["flow_veh_h_lane"], seed=run["seed"], scenario=run["scenario"], mode=run["mode"],
                                  positions_sha256=run["positions_sha256"], original_positions_gzip_bytes=(path / "positions.jsonl.gz").stat().st_size,
                                  files={})
                    for filename, field in (("input.json", "input_sha256"), ("result.json", "result_sha256"), ("trips.json", "trips_sha256")):
                        src = path / filename
                        value = sha(src)
                        if value != run[field]:
                            raise ValueError("Raw case JSON no longer matches independent audit: " + str(src))
                        member = "cases/" + case_id + "/" + filename
                        info = tarfile.TarInfo(member)
                        info.size, info.mtime, info.mode = src.stat().st_size, 0, 0o644
                        with src.open("rb") as stream:
                            archive.addfile(info, stream)
                        entry = dict(member=member, original=str(src), sha256=value, bytes=src.stat().st_size)
                        archived.append(entry)
                        record["files"][filename] = entry
                    cases.append(record)
                for filename in metadata_names:
                    src = ORIGINAL / filename
                    member = "analysis_metadata/" + filename
                    info = tarfile.TarInfo(member)
                    info.size, info.mtime, info.mode = src.stat().st_size, 0, 0o644
                    with src.open("rb") as stream:
                        archive.addfile(info, stream)
                    archived.append(dict(member=member, original=str(src), sha256=sha(src),
                                         bytes=src.stat().st_size, role="Exact original P analysis provenance bytes"))
    archived_by_name = {r["member"]: r for r in archived}
    with tarfile.open(target, "r|gz") as archive:
        checked = 0
        for member in archive:
            expected = archived_by_name[member.name]
            with archive.extractfile(member) as stream:
                value, size = stream_sha(stream)
            if value != expected["sha256"] or size != expected["bytes"]:
                raise ValueError("Archive lossless verification failed: " + member.name)
            checked += 1
    case_json_count = sum(r["member"].startswith("cases/") for r in archived)
    if case_json_count != 300 or checked != 300 + len(metadata_names):
        raise ValueError("Expected 300 exact case JSON files plus P provenance originals")
    write(provenance / "case_index.json", cases)
    write(provenance / "lossless_manifest.json", dict(exact_gzip_copies=lossless,
        raw_case_archive=dict(portable="data/raw_case_json.tar.gz", sha256=sha(target), compressed_bytes=target.stat().st_size,
                              original_bytes=sum(r["bytes"] for r in archived), files=archived,
                              checked_files=checked, checked_case_JSON_files=case_json_count,
                              checked_metadata_files=len(metadata_names), lossless=True)))
    spec = importlib.util.spec_from_file_location("portable_tables", BASE / "recompute_tables.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    first = {str(p.relative_to(BASE)): sha(p) for p in (BASE / "tables").iterdir() if p.is_file()}
    module.main()
    second = {str(p.relative_to(BASE)): sha(p) for p in (BASE / "tables").iterdir() if p.is_file()}
    if first != second:
        raise ValueError("Recomputed tables are not byte-for-byte stable")
    after = {str(p.relative_to(ORIGINAL)): sha(p) for p in ORIGINAL.rglob("*") if p.is_file()}
    if before != after:
        raise ValueError("Original P_analysis was modified during packaging")
    if d_before != {str(p.relative_to(d_portable)): sha(p) for p in d_portable.rglob("*") if p.is_file()}:
        raise ValueError("D portable was modified during P packaging")
    if sha(attributes) != attributes_before:
        raise ValueError("gitattributes was modified during P packaging")
    text = """Portable P100 evidence bundle

Start with tables/TT.txt, traffic_and_attribution.csv, formation_quality.csv,
recovery_counts.csv and straight_controls.csv. Column meanings and limitations
are defined in tables/column_definitions.json. All tables preserve the frozen
evaluation measures and the original five-seed grouping.

Run: python -B recompute_tables.py
Verify: python -B verify_portable.py
This regenerates compact tables using only Python's standard library and the
losslessly compressed original evaluator JSON files in data/.

data/vehicles.csv.gz retains the exact original gate/censor CSV bytes.
data/region_steps.csv.gz is the original exact compressed step CSV.
data/recovery_flow_*.json.gz retains original per-vehicle recovery and censoring
without duplicating the equivalent recovery CSV. data/raw_case_json.tar.gz
retains all 100 original input/result/trips JSON files (300 exact files).
Its analysis_metadata/ entries also preserve the exact bytes of P release and
analysis freezes, the real serial/parallel equivalence evidence, the original
four_flow_results CSV/JSON and the P audit/table source scripts. Their byte SHA256
values and compressed archive SHA256 are saved in lossless_manifest.json.
The archive entries and external position traces are bound in
provenance/case_index.json. Every stored compressed original was decoded and
verified against its original SHA256. Source modules common to all 100 cases
are stored once under source/, with the six P hashes and evaluator hashes.

P outcomes are retained, including longer transform travel times at all four
flows and higher fuel than NOA. At flow1500, the main-segment additional-time
reduction is +0.161616s, while the whole-trip reduction is -0.815962s. Full
participation and recovery censoring remain explicit in the four result tables.

The 416.4 MB original positions.jsonl.gz files are not duplicated here.
Gate/layer re-evaluation requires those external raw traces referenced by the
case index. The bundled gate records, regional step records, original trips,
and evaluator output retain the evidence needed to recompute reported tables,
travel/fuel measures and all five-seed summaries without a SUMO rerun.

bundle_hashes.json binds every bundle artifact except itself and its root
checksum file. bundle_sha256.txt is SHA256(bundle_hashes.json). The lossless
and original-readonly checks are saved in verification.json.
"""
    (BASE / "PACKAGE.txt").write_text(text, encoding="utf-8")
    write(BASE / "verification.json", dict(passed=True, original_P_analysis_unchanged=True,
        D_portable_unchanged=True, D_portable_bundle_manifest_sha256=sha(d_portable / "bundle_hashes.json"),
        gitattributes_unchanged=True, gitattributes_sha256=attributes_before,
        original_artifact_hashes_verified=len(original_manifest), lossless_gzip_files=len(lossless),
        raw_case_JSON_files_verified=case_json_count, original_P_metadata_files_verified=len(metadata_names),
        P_release_rules_sha256=protocol["source_sha256"]["noa/native_rules.py"],
        P_release_wrapper_sha256=protocol["wrapper_sha256"], parallel_jobs=protocol["jobs"],
        P_postverification_passed=h_post["passed"],
        cases=100, all_eligible=True, table_recompute_byte_identical=True,
        table_artifacts_checked=len(first), controlled_source_modules=6,
        evaluator_sha256=sha(BASE / "source/experiments/bottleneck_attribution.py"),
        position_traces_external_bytes=sum(r["original_positions_gzip_bytes"] for r in cases),
        original_P_analysis_bytes=sum(p.stat().st_size for p in ORIGINAL.rglob("*") if p.is_file())))
    hashes = {str(p.relative_to(BASE)).replace("\\", "/"): sha(p) for p in sorted(BASE.rglob("*"))
              if p.is_file() and p.name not in ("bundle_hashes.json", "bundle_sha256.txt")}
    write(BASE / "bundle_hashes.json", hashes)
    root_digest = sha(BASE / "bundle_hashes.json")
    (BASE / "bundle_sha256.txt").write_text(root_digest + "  bundle_hashes.json\n", encoding="ascii")
    if any(sha(BASE / name) != value for name, value in hashes.items()):
        raise ValueError("Final portable artifact hash mismatch")
    print(json.dumps(dict(output=str(BASE), files=len(hashes) + 2,
                          portable_bytes=sum(p.stat().st_size for p in BASE.rglob("*") if p.is_file()),
                          bundle_sha256=root_digest, lossless=True, original_unchanged=True)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
