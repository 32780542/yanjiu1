"""Independently match an offline verification report to exact manifest/analysis files."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import tarfile


def file_info(path):
    path = Path(path)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"sha256": digest, "bytes": path.stat().st_size}


def audit(bundle, manifest, analyzer_csv, verification):
    report = json.loads(Path(verification).read_bytes())
    with tarfile.open(bundle, "r:gz") as tar:
        index = json.load(tar.extractfile("index.json"))
        tool = tar.extractfile("compact_evidence.py").read()
    original = json.loads(Path(manifest).read_bytes())
    packed = [case["record"] for case in index["cases"]]
    recomputed = [case["record"] for case in report["cases"]]

    def keyed(rows):
        values = {row["run_dir"]: row for row in rows}
        if len(values) != len(rows):
            raise ValueError("duplicate run_dir")
        return values

    if keyed(original) != keyed(packed) or keyed(original) != keyed(recomputed):
        raise ValueError("manifest case data/count mismatch")
    archive_info = file_info(bundle)
    if any(report["archive"][key] != value for key, value in archive_info.items()):
        raise ValueError("verification archive hash/bytes mismatch")
    if hashlib.sha256(tool).hexdigest() != index["tool_sha256"]:
        raise ValueError("standalone tool hash mismatch")
    with Path(analyzer_csv).open(encoding="utf-8-sig", newline="") as stream:
        csv_rows = keyed(list(csv.DictReader(stream)))
    if set(csv_rows) != set(keyed(original)):
        raise ValueError("analyzer case coverage mismatch")
    comparisons = 0
    for case in report["cases"]:
        expected = csv_rows[case["record"]["run_dir"]]
        values = {**case["traffic"], "positions_frames": case["frames"]}
        values.update({"flag_" + key: value for key, value in case["formation_state"].items()})
        values.update({"flag_recomputed_" + key: value for key, value in case["formation_state"].items()})
        for name, segment in case["segments"].items():
            values.update({name + "_" + key: value for key, value in segment.items() if key != "vehicles"})
        for key in values.keys() & expected.keys():
            actual, saved = values[key], expected[key]
            if saved == "":
                parsed = None
            elif saved in ("True", "False"):
                parsed = saved == "True"
            else:
                parsed = float(saved)
            matched = (math.isclose(actual, parsed, abs_tol=1e-7, rel_tol=1e-9)
                       if type(actual) in (float, int) and type(parsed) in (float, int)
                       else actual == parsed)
            if not matched:
                raise ValueError(f"analyzer mismatch {case['record']['run_dir']} {key}: {actual} != {parsed}")
            comparisons += 1
    return {"cases_verified": len(packed), "manifest_records_exact": True,
            "analyzer_cases_compared": len(csv_rows), "numeric_or_count_comparisons": comparisons,
            "frames_verified": sum(case["frames"] for case in report["cases"]),
            "requested_vehicle_runs": sum(case["traffic"]["requested"] for case in report["cases"]),
            "unique_source_blobs": len({digest for case in index["cases"] for name, digest in case["files"].items() if name.startswith("source/")}),
            "full_original_positions_bytes_indexed": sum(case["originals"]["positions.jsonl.gz"]["bytes"] for case in index["cases"]),
            "full_original_events_bytes_indexed": sum(case["originals"]["events.jsonl.gz"].get("bytes", 0) for case in index["cases"]),
            "archive": archive_info, "manifest": file_info(manifest),
            "analyzer_csv": file_info(analyzer_csv), "verification_report": file_info(verification)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "manifest", "analyzer-csv", "verification", "report"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.bundle, args.manifest, args.analyzer_csv, args.verification)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
