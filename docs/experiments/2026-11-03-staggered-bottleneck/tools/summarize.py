"""Verify sealed batches and export existing per-case metrics and raw paired deltas.

No new window, eligibility threshold, aggregate statistic or evaluator is used.
Duplicate candidate/flow/seed/scenario/mode keys across batches are errors.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

import seal_case

IDENTITY = ("candidate", "flow", "seed", "scenario", "mode")


def unique(records):
    index = {}
    for record in records:
        key = tuple(record[name] for name in IDENTITY)
        if key in index:
            raise ValueError("duplicate candidate/flow/seed/scenario/mode: " + repr(key))
        index[key] = record
    return index


def fallback(record):
    return dict(candidate=record["candidate"], flow_veh_h_lane=record["flow"], seed=record["seed"],
                scenario=record["scenario"], attribution_eligible=False, case_dir=record.get("run_dir"),
                rules_sha256=None, nonrule_source_sha256=None, demand_sha256=None,
                parameters_sha256=None, source_sha256={})


def protocol_records(batch):
    batch = Path(batch)
    protocol = seal_case.read(batch / "protocol.json")
    manifest = seal_case.read(batch / "manifest.json") if (batch / "manifest.json").is_file() else []
    planned, actual = unique(protocol["tasks"]), unique(manifest)
    rows = []
    for key in sorted(planned.keys() | actual.keys()):
        task, record = planned.get(key), actual.get(key)
        issues = []
        if record is None:
            record = {**{name: task[name] for name in (*IDENTITY, "stage")},
                      "case_output": task["output"], "run_dir": None, "returncode": None,
                      "base_commit": protocol["base_commit"], "status": "missing_manifest",
                      "safe": False, "all_completed": False, "seal_status": "not_available_raw_retained"}
            issues.append("missing_manifest_case")
        if task is None:
            issues.append("unplanned_manifest_case")
        rows.append({**record, "_task": task, "_protocol": protocol, "_protocol_issues": issues,
                     "_batch": str(batch.resolve())})
    return rows


def archived_originals(folder):
    with tarfile.open(Path(folder) / "compact/bundle.tar.gz", "r:gz") as archive:
        index = json.load(archive.extractfile("index.json"))
        if len(index["cases"]) != 1:
            raise ValueError("one sealed case per evidence directory required")
        case = index["cases"][0]
        originals = {}
        for name in ("input.json", "result.json", "trips.json"):
            raw = archive.extractfile("blobs/" + case["files"][name]).read()
            if hashlib.sha256(raw).hexdigest() != case["files"][name]:
                raise ValueError("original JSON blob hash mismatch: " + name)
            originals[name] = json.loads(raw)
    return originals, case["files"]


def audit_protocol(record, task, protocol, originals, hashes, cached):
    if task is None or protocol is None:
        return ["unplanned_manifest_case"]
    issues = []
    if record.get("base_commit") != protocol["base_commit"]:
        issues.append("protocol_base_commit_mismatch")
    for key in (*IDENTITY, "stage"):
        if record.get(key) != task.get(key):
            issues.append("protocol_manifest_mismatch:" + key)
    if Path(record["case_output"]).resolve() != Path(task["output"]).resolve():
        issues.append("protocol_case_output_mismatch")
    if (Path(record["run_dir"]).resolve().parent != Path(task["output"]).resolve()
            or Path(cached["case_dir"]).resolve() != Path(record["run_dir"]).resolve()):
        issues.append("protocol_run_path_mismatch")
    inp, result, trips = (originals[name] for name in ("input.json", "result.json", "trips.json"))
    fields = dict(flow_veh_h_lane="flow", seed="seed", scenario="scenario", mode="mode",
                  demand_duration_s="duration", max_time_s="max_time")
    for original_key, task_key in fields.items():
        if inp["case"].get(original_key) != task.get(task_key):
            issues.append("protocol_input_mismatch:" + original_key)
        if result.get(original_key) != inp["case"].get(original_key):
            issues.append("original_result_input_mismatch:" + original_key)
    expected = protocol["sources"].get(task["candidate"], {})
    for name in seal_case.tools()[0].SOURCES:
        if inp["source_sha256"].get(name) != expected.get(name) or name not in expected:
            issues.append("protocol_source_hash_mismatch:" + name)
    if result.get("source_sha256") != inp["source_sha256"] or cached.get("source_sha256") != inp["source_sha256"]:
        issues.append("original_cached_source_hash_mismatch")
    for name, key in (("input.json", "input_sha256"), ("result.json", "result_sha256"), ("trips.json", "trips_sha256")):
        if cached.get(key) != hashes[name]:
            issues.append("original_cached_hash_mismatch:" + name)
    requests = inp["arrivals"]
    demand_hash = seal_case.tools()[1].obj_sha(sorted(requests, key=lambda row: row["vehicle_id"]))
    if cached.get("demand_sha256") != demand_hash:
        issues.append("original_request_hash_mismatch")
    requested = {row["vehicle_id"]: row for row in requests}
    if len(requested) != len(requests) or len(trips) != len(requested) or {row["vehicle_id"] for row in trips} != set(requested):
        issues.append("original_request_trip_identity_mismatch")
    for trip in trips:
        request = requested.get(trip["vehicle_id"], {})
        if any(trip.get(key) != request.get(key) for key in ("requested_s", "lane", "x", "speed")):
            issues.append("original_request_trip_mismatch:" + trip["vehicle_id"])
    return issues


def load_case(record):
    row = {key: value for key, value in record.items() if key not in ("operation", "raw_pruning")}
    row["evidence_verified"] = False
    row["protocol_verified"] = False
    row["protocol_issues"] = list(record.get("_protocol_issues", []))
    row["_run"] = fallback(record)
    if record.get("seal_status") != "verified":
        row["evidence_error"] = record.get("seal_error", "case was not sealed")
        row["protocol_issues"].append("original_evidence_unavailable")
        return row
    try:
        folder = Path(record["evidence_dir"])
        checked = seal_case.verify(folder)
        compact = checked["compact"]["cases"][0]
        if any(compact["record"].get(key) != record.get(key) for key in IDENTITY):
            raise ValueError("manifest/sealed case identity mismatch")
        saved = seal_case.read(folder / "seal.json")
        cached = seal_case.read(folder / saved["traffic_metadata"])["run"]
        originals, hashes = archived_originals(folder)
        row["protocol_issues"].extend(audit_protocol(record, record.get("_task"), record.get("_protocol"), originals, hashes, cached))
        run = dict(cached)
        run.update({"flag_" + key: value for key, value in compact["formation_state"].items()})
        row.update({key: value for key, value in cached.items() if key not in ("case_dir", "ledger_dir")})
        row.update(compact["traffic"])
        row.update({"flag_" + key: value for key, value in compact["formation_state"].items()})
        row.update(evidence_verified=True, _run=run)
        row["protocol_verified"] = not row["protocol_issues"]
        if not row["protocol_verified"]:
            run["attribution_eligible"] = False
            row["attribution_eligible"] = False
            row["performance_comparison_eligible"] = False
    except Exception as error:
        row["evidence_error"] = f"{type(error).__name__}: {error}"
    return row


def build_pairs(cases, reference="TM"):
    _, traffic = seal_case.tools()
    index = unique(cases)
    specifications = []
    contexts = sorted({(row["flow"], row["seed"], row["scenario"]) for row in cases if row["candidate"] == reference})
    for flow, seed, scenario in contexts:
        specifications.append(((reference, flow, seed, scenario, "noa"),
                               (reference, flow, seed, scenario, "transform"),
                               reference + "_transform-minus-noa", "complete_strategy_same_following"))
    for key in sorted(index):
        candidate, flow, seed, scenario, mode = key
        if candidate != reference:
            specifications.append(((reference, flow, seed, scenario, mode), key,
                                   candidate + "-minus-" + reference + "_" + mode, "candidate_rule_change_same_mode"))
    pairs = []
    for reference_key, candidate_key, name, meaning in specifications:
        left, right = index.get(reference_key), index.get(candidate_key)
        a, b = left.get("_run") if left else None, right.get("_run") if right else None
        pair = traffic.pair(a, b, name, meaning)
        pair.update(reference_candidate=reference_key[0], candidate=candidate_key[0],
                    reference_mode=reference_key[-1], mode=candidate_key[-1],
                    reference_protocol_issues=left.get("protocol_issues", []) if left else ["missing_pair_member"],
                    candidate_protocol_issues=right.get("protocol_issues", []) if right else ["missing_pair_member"])
        metrics = (*traffic.METRICS, *("flag_" + key for key in seal_case.tools()[0].FLAGS))
        for metric in metrics:
            pair["reference_" + metric] = a.get(metric) if a else None
            pair["candidate_" + metric] = b.get(metric) if b else None
            pair["delta_" + metric] = traffic.existing._difference(a, b, metric, pair["pair_eligible"])
        pairs.append(pair)
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", default="TM")
    args = parser.parse_args()
    records = []
    for batch in args.batch:
        records.extend(protocol_records(batch))
    try:
        unique(records)
    except ValueError as error:
        parser.error(str(error))
    if args.output.exists():
        parser.error("output already exists: " + str(args.output))
    cases = []
    for i, record in enumerate(sorted(records, key=lambda r: tuple(r[k] for k in IDENTITY)), 1):
        row = load_case(record)
        cases.append(row)
        print(json.dumps(dict(verified=i, total=len(records), evidence_verified=row["evidence_verified"])), flush=True)
    pairs = build_pairs(cases, args.reference)
    _, traffic = seal_case.tools()
    args.output.mkdir(parents=True, exist_ok=False)
    traffic.write_rows(args.output / "per_case.csv", [{k: v for k, v in row.items() if not k.startswith("_")} for row in cases])
    traffic.write_rows(args.output / "paired.csv", pairs)
    bad = [row for row in cases if not row["evidence_verified"] or not row["protocol_verified"] or row.get("safe") is not True
           or row.get("all_completed") is not True or row.get("status") != "drained" or row.get("returncode") != 0]
    low = [row for row in cases if row.get("region_window", {}).get("low_speed_vehicle_s", 0) > 0]
    summary = dict(batches=[str(batch.resolve()) for batch in args.batch], case_count=len(cases),
        evidence_verified_count=sum(row["evidence_verified"] for row in cases),
        protocol_verified_count=sum(row["protocol_verified"] for row in cases),
        planned_task_count=sum(len(seal_case.read(batch / "protocol.json")["tasks"]) for batch in args.batch),
        protocol_sha256={str(batch.resolve()): seal_case.sha(batch / "protocol.json") for batch in args.batch},
        physical_safe_count=sum(row.get("safe") is True for row in cases),
        drained_count=sum(row.get("status") == "drained" and row.get("all_completed") is True for row in cases),
        pair_count=len(pairs), pair_eligible_count=sum(row["pair_eligible"] for row in pairs),
        fixed_window_complete_count=sum(row.get("region_window", {}).get("window_complete", False) for row in cases),
        fixed_traffic_window_s=[100, 600],
        window_policy="Unchanged original [100,600) region ledger; partial observed exposure retained in region_window, formal incomplete-window metrics stay null.",
        failed_cases=[{key: row.get(key) for key in (*IDENTITY, "status", "safe", "all_completed", "returncode", "seal_status", "evidence_error", "protocol_issues", "error")} for row in bad],
        low_speed_cases=[{**{key: row[key] for key in IDENTITY}, "region_window": row["region_window"]} for row in low],
        original_raw_bytes_pruned=sum(row.get("raw_pruning", {}).get("bytes_released", 0) for row in records),
        method_sha256=seal_case.method_hashes(*seal_case.tools()),
        delta_definition="candidate minus reference; source/demand/parameter/eligibility checks and differences reuse published tools")
    seal_case.write(args.output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return 0 if len(cases) == summary["evidence_verified_count"] == summary["protocol_verified_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
