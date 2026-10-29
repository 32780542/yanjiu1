"""Verify the portable artifact hashes and tables against bundled raw evidence."""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import tarfile


BASE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8-sig") as stream:
        return json.load(stream)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(actual, expected, name):
    if actual is None or expected is None:
        if actual != expected:
            raise ValueError(name)
    elif not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8):
        raise ValueError(f"{name}: {actual} != {expected}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    manifest = read(BASE / "bundle_hashes.json")
    if any(sha(BASE / name) != value for name, value in manifest.items()):
        raise ValueError("Portable artifact hash mismatch")
    root_digest = (BASE / "bundle_sha256.txt").read_text().split()[0]
    if sha(BASE / "bundle_hashes.json") != root_digest:
        raise ValueError("Portable root checksum mismatch")
    case_index = read(BASE / "provenance/case_index.json")
    by_id = {r["case_id"]: r for r in case_index}
    by_path = {r["original_case_dir"]: r for r in case_index}
    by_key = {(r["flow_veh_h_lane"], r["seed"], r["scenario"], r["mode"]): r for r in case_index}
    case_metrics = {}
    lossless = read(BASE / "provenance/lossless_manifest.json")
    for record in lossless["exact_gzip_copies"]:
        path = BASE / record["portable"]
        if sha(path) != record["compressed_sha256"]:
            raise ValueError("Compressed gzip byte SHA mismatch")
        digest = hashlib.sha256()
        with gzip.open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != record["decoded_sha256"]:
            raise ValueError("Lossless gzip decoded byte SHA mismatch")
    archived = {r["member"]: r for r in lossless["raw_case_archive"]["files"]}
    metadata = {}
    with tarfile.open(BASE / "data/raw_case_json.tar.gz", "r|gz") as archive:
        archive_count = 0
        metadata_count = 0
        for member in archive:
            entry = archived[member.name]
            content = archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest() != entry["sha256"] or len(content) != entry["bytes"]:
                raise ValueError("Archived original JSON mismatch: " + member.name)
            if member.name.startswith("analysis_metadata/"):
                metadata[member.name.split("/", 1)[1]] = content
                metadata_count += 1
                continue
            _, case_id, filename = member.name.split("/")
            archive_count += 1
            if filename == "trips.json":
                trips = json.loads(content)
                case_metrics[case_id] = dict(
                    TT_s=sum(t["exited_s"] - t["entered_s"] for t in trips) / len(trips),
                    fuel_g_km=sum(t["fuel_mg"] for t in trips) / sum(t["distance_m"] for t in trips))
    gates = defaultdict(lambda: dict(duration_sum=0.0, n=0, crossings=0))
    with gzip.open(BASE / "data/vehicles.csv.gz", "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            case = by_path[row["case_dir"]]
            values = gates[case["case_id"]]
            values["duration_sum"] += float(row["gate_1100_s"]) - float(row["gate_640_s"])
            values["n"] += 1
            values["crossings"] += 100 <= float(row["gate_1000_s"]) <= 600
    for case_id, values in gates.items():
        case_metrics[case_id]["main_s"] = values["duration_sum"] / values["n"]
        case_metrics[case_id]["flow_veh_h"] = values["crossings"] * 7.2
    regions = defaultdict(lambda: dict(low_s=0.0, vehicle_s=0.0, speed_m=0.0))
    with gzip.open(BASE / "data/region_steps.csv.gz", "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            dt = max(0.0, min(float(row["end_s"]), 600.0) - max(float(row["time_s"]), 100.0))
            if dt:
                values = regions[by_path[row["case_dir"]]["case_id"]]
                values["low_s"] += int(row["low_speed_n"]) * dt
                values["vehicle_s"] += int(row["n"]) * dt
                values["speed_m"] += float(row["speed_sum_mps"]) * dt
    for case_id, values in regions.items():
        case_metrics[case_id]["low_s"] = values["low_s"]
        case_metrics[case_id]["speed_mps"] = values["speed_m"] / values["vehicle_s"]
    tables = read(BASE / "tables/results.json")
    traffic_checks = 0
    for row in tables["traffic_and_attribution"]:
        flow, mode = row["flow_veh_h_lane"], row["mode"]
        cases = [by_key[(flow, seed, "lane_drop", mode)] for seed in range(6, 11)]
        for field, evidence in (("drop_TT_s", "TT_s"), ("drop_fuel_g_km", "fuel_g_km"),
                                ("drop_main_640_1100_s", "main_s"), ("region_low_speed_vehicle_s", "low_s"),
                                ("region_window_speed_mps", "speed_mps"), ("flow_1000m_veh_h", "flow_veh_h")):
            expected = sum(case_metrics[c["case_id"]][evidence] for c in cases) / 5
            check(row[field], expected, f"flow{flow}/{mode}/{field}")
            traffic_checks += 1
        if mode in ("noa", "transform"):
            differences = [case_metrics[by_key[(flow, seed, "lane_drop", mode)]["case_id"]]["main_s"]
                           - case_metrics[by_key[(flow, seed, "straight3", mode)]["case_id"]]["main_s"] for seed in range(6, 11)]
            check(row["main_drop_minus_straight_s"], sum(differences) / 5, "main same-mode difference")
        else:
            check(row["main_drop_minus_straight_s"], None, "formation missing straight")
    recovery_checks = 0
    for row in tables["recovery_counts"]:
        flow, mode = row["flow_veh_h_lane"], row["mode"]
        report = read_gz(BASE / f"data/recovery_flow_{flow}.json.gz")
        events = [v for r in report["runs"] if r["scenario"] == "lane_drop" and r["mode"] == mode for v in r["per_vehicle"]]
        for prefix, values in (("all_adjusting", events), ("upstream_formed", [v for v in events if v["upstream_formed"]])):
            counts = dict(subjects=len(values), recovered=sum(v["delay_s"] is not None for v in values),
                          censored=sum(v["delay_s"] is None for v in values))
            for key, expected in counts.items():
                check(row[prefix + "_" + key], expected, "recovery raw-event count")
                recovery_checks += 1
    protocol = read(BASE / "provenance/protocol.json")
    release = json.loads(metadata["P_release_freeze.json"])
    anchor = json.loads(metadata["P_analysis_expected.json"])
    parallel = json.loads(metadata["parallel_study_equivalence.json"])
    if (protocol.get("jobs") != 4 or release["source_sha256"] != protocol["source_sha256"]
            or release["wrapper_sha256"] != protocol["wrapper_sha256"]
            or protocol["source_sha256"]["noa/native_rules.py"] != "8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864"
            or protocol["source_sha256"]["experiments/native_sumo.py"] != "6a530098146e85a637b4f29d580d61877c7a54b3a7e15858724651d80e8956b0"
            or protocol["wrapper_sha256"] != "cf7a371677a08dd312ae904f410d26070452d464314b12b0a2b5943f0b2d1385"
            or not parallel["all_twenty_cases_drained"] or not parallel["all_ten_case_pairs_physically_identical"]
            or hashlib.sha256(metadata["parallel_study_equivalence.json"]).hexdigest() != anchor["parallel_equivalence_sha256"]
            or not release["formatting_ast_identical"] or set(protocol["seeds"]) != {6,7,8,9,10}
            or any(type(flow) is not float for flow in protocol["flows"])):
        raise ValueError("P release/parallel evidence binding mismatch")
    for name, value in protocol["source_sha256"].items():
        if sha(BASE / "source" / name) != value:
            raise ValueError("Controlled source differs from study protocol: " + name)
    result = dict(passed=True, bundle_artifacts_checked=len(manifest),
                  archived_original_JSON_files_checked=archive_count, raw_trip_cases_checked=len(case_metrics),
                  original_P_metadata_files_checked=metadata_count,
                  gzip_compressed_and_decoded_SHA_verified=len(lossless["exact_gzip_copies"]),
                  P_release_and_jobs4_parallel_evidence_verified=True,
                  traffic_measure_cells_checked_from_raw_trips_gates_steps=traffic_checks,
                  recovery_count_cells_checked_from_per_vehicle_events=recovery_checks,
                  six_controlled_sources_match_protocol=True, root_checksum=root_digest,
                  position_trace_recomputation="External original positions remain required for gate/layer reruns; package table checks use exact bundled measured gate/step records")
    if args.write:
        saved = {k: v for k, v in result.items() if k != "root_checksum"}
        saved["artifact_checksum_check_passed_before_final_manifest"] = True
        (BASE / "independent_verification.json").write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
