"""Recompute native SUMO runs and paired candidate-minus-baseline differences.

Input: JSON path array or {"cases": ["relative/or/absolute/case_directory", ...]}.
Relative paths resolve against the manifest. One run per seed/scenario/mode is
allowed. Saved source bytes, demand, common parameters and SUMO version are checked
before pairing. Incomplete/unsafe/unmatched runs remain visible; an affected mean
group is suppressed rather than averaging only its successful seeds. No ranking
or Cai2024 paper result is inferred. NOA layers are detected geometry only.

Fuel is SUMO fuel_abs mg / actual route distance m, numerically g/km. Geometry is
sample-based, with independent upstream/downstream evaluation to exclude planned
3-to-2 relationship replacement. CSV cells are empty for undefined quantities.
"""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path

from experiments.complete_layers import evaluate_layers

SOURCES = (
    "experiments/native_sumo.py",
    "experiments/global_reference.py",
    "noa/native_rules.py",
    "run_native_flow.py",
    "research/common.py",
)
MODES = ("noa", "formation", "transform", "global", "cooperative")
LABELS = dict(
    noa="NOA (detected geometry only)",
    formation="Formation + ordinary merge",
    transform="Distributed formation + lane-drop transform",
    cooperative="Cooperative merge only; grouping and layer fill disabled",
    global_="Cai-style centralized reference (not full paper reproduction)",
)
TRAFFIC = (
    "mean_entry_wait_s",
    "mean_travel_time_s",
    "mean_system_time_s",
    "exit_flow_veh_h",
    "fuel_g_per_km",
    "merge_completion_before_drop_rate",
)
LAYER_FIELDS = (
    "mean_multilayer_size",
    "peak_multilayer_size",
    "formation_participation_rate",
    "stable_participation_rate",
    "internal_breaks_per_100_formed_vehicle_s",
    "geometry_rms_m",
    "speed_rms_mps",
    "vehicle_seconds",
    "formed_vehicle_seconds",
    "stable_vehicle_seconds",
    "internal_relation_breaks",
    "boundary_censored_relations",
)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _position_evidence(path):
    last_ending, first, previous, max_step = {}, None, None, None
    sample_count = nonempty_frames = 0
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            time_s = frame["time_s"]
            if first is None:
                first = time_s
            if previous is not None:
                max_step = max(max_step or 0.0, time_s - previous)
            previous = time_s
            sample_count += 1
            nonempty_frames += bool(frame["states"])
            for vehicle, state in frame["states"].items():
                if abs(state[1] - 8.25) <= 0.3:
                    last_ending[vehicle] = time_s
    return last_ending, dict(
        first_position_sample_s=first,
        last_position_sample_s=previous,
        max_position_sample_step_s=max_step,
        position_sample_count=sample_count,
        nonempty_position_frames=nonempty_frames,
    )


def load_case(path):
    """Read-only independent per-run audit; failed runs retain counts and geometry."""
    path = Path(path).resolve()
    source, result = _read(path / "input.json"), _read(path / "result.json")
    config, issues = source["case"], []
    arrivals = source["arrivals"]
    if (path / "trips.json").is_file():
        trips_path = path / "trips.json"
        trips = _read(trips_path)
    elif (path / "trips.jsonl.gz").is_file():
        trips_path = path / "trips.jsonl.gz"
        with gzip.open(trips_path, "rt", encoding="utf-8") as stream:
            trips = [json.loads(line) for line in stream]
    else:
        trips, trips_path = [], None
        issues.append("missing_trips")
    hashes = source.get("source_sha256", {})
    if not set(SOURCES).issubset(hashes):
        issues.append("missing_controlled_source_digest")
    for name, expected in hashes.items():
        snapshot = path / "source" / name
        if not snapshot.is_file() or _sha(snapshot) != expected:
            issues.append("source_digest_mismatch:" + name)
    if hashes != result.get("source_sha256"):
        issues.append("input_result_source_mismatch")
    common_case_keys = (
        "flow_veh_h_lane",
        "demand_duration_s",
        "max_time_s",
        "step_s",
        "lane_change_duration_s",
    )
    case_parameters = {key: config[key] for key in common_case_keys}
    # Both absent denotes the legacy actuator, never the shaped actuator's values.
    case_parameters.update(
        {
            key: config.get(key)
            for key in ("request_acceleration_limit_mps2", "request_deceleration_limit_mps2")
        }
    )
    if any(result.get(key) != config[key] for key in ("mode", "seed", "scenario")) or any(
        result.get(key) != value for key, value in case_parameters.items()
    ):
        issues.append("input_result_case_mismatch")
    requested = {a["vehicle_id"]: a for a in arrivals}
    if (
        len(requested) != len(arrivals)
        or {t["vehicle_id"] for t in trips} != set(requested)
        or len(trips) != len(requested)
    ):
        issues.append("trip_request_identity_mismatch")
    for trip in trips:
        if any(
            trip.get(k) != requested.get(trip["vehicle_id"], {}).get(k)
            for k in ("requested_s", "lane", "x", "speed")
        ):
            issues.append("trip_request_mismatch:" + trip["vehicle_id"])
        entered, exited = trip["entered_s"], trip["exited_s"]
        if (
            entered is not None
            and entered < trip["requested_s"]
            or exited is not None
            and (entered is None or exited < entered)
        ):
            issues.append("invalid_trip_times:" + trip["vehicle_id"])
    departed = [t for t in trips if t["entered_s"] is not None]
    completed = [t for t in trips if t["exited_s"] is not None]
    counts = dict(requested=len(arrivals), departed=len(departed), completed=len(completed))
    if any(result.get(key) != value for key, value in counts.items()):
        issues.append("result_trip_counts_mismatch")
    all_completed = bool(arrivals) and len(completed) == len(arrivals)
    if bool(result.get("all_completed")) != all_completed:
        issues.append("result_completion_mismatch")
    safe = bool(result.get("safe")) and not (
        result.get("collisions") or result.get("teleports") or result.get("error")
    )
    common_keys = ("physical", "speed_mode", "lane_change_mode", "insertion", "positions_step_s")
    if any(source.get(key) is None for key in common_keys):
        issues.append("missing_common_parameters")
    parameters = {key: source.get(key) for key in common_keys}
    parameters["case"] = case_parameters
    parameters["sumo_version"] = result.get("sumo_version")
    row = dict(
        case_dir=str(path),
        scenario=config["scenario"],
        mode=config["mode"],
        seed=config["seed"],
        mode_label=LABELS["global_" if config["mode"] == "global" else config["mode"]],
        status=result.get("status"),
        safe=safe,
        all_completed=all_completed,
        **counts,
        completion_fraction=len(completed) / len(arrivals) if arrivals else None,
        pending_final=len(arrivals) - len(departed),
        onroad_final=len(departed) - len(completed),
        collisions=result.get("collisions"),
        teleports=result.get("teleports"),
        error=result.get("error"),
        actual_end_s=result.get("actual_end_s"),
        demand_duration_s=config["demand_duration_s"],
        demand_sha256=_digest(sorted(arrivals, key=lambda a: a["vehicle_id"])),
        source_version_sha256=_digest(hashes),
        parameters_sha256=_digest(parameters),
        cohort_id=_digest(dict(parameters=parameters, source=hashes))[:16],
        input_sha256=_sha(path / "input.json"),
        result_sha256=_sha(path / "result.json"),
        trips_sha256=_sha(trips_path) if trips_path else None,
        audit_issues=issues,
    )
    row.update({field: None for field in TRAFFIC})
    try:
        positions = path / "positions.jsonl.gz"
        ending, evidence = _position_evidence(positions)
        row.update(evidence)
        row["positions_sha256"] = _sha(positions)
        # A valid empty road differs from a missing observation interval.
        tolerance, sample_step = 1e-6, source.get("positions_step_s")
        if not evidence["position_sample_count"]:
            issues.append("empty_position_trace")
        else:
            if sample_step is not None:
                first = evidence["first_position_sample_s"]
                if min(abs(first), abs(first - sample_step)) > tolerance:
                    issues.append("position_trace_start_mismatch")
                max_step = evidence["max_position_sample_step_s"]
                if max_step is not None and max_step > sample_step + tolerance:
                    issues.append("position_sample_gap_exceeds_declared_step")
            if abs(evidence["last_position_sample_s"] - result["actual_end_s"]) > tolerance:
                issues.append("position_trace_end_mismatch")
            if departed and not evidence["nonempty_position_frames"]:
                issues.append("position_trace_has_no_vehicles")
        regions = (
            (("upstream", 3, (0.0, 640.0)), ("downstream", 2, (1000.0, 1200.0)))
            if config["scenario"] == "lane_drop"
            else (("whole", 3, (0.0, 1200.0)),)
        )
        for prefix, lanes, region in regions:
            layers = evaluate_layers(positions, lanes, region=region)
            row.update({prefix + "_" + key: layers[key] for key in LAYER_FIELDS})
        if config["scenario"] == "lane_drop":
            trace = all("lane_completion_events" in t for t in trips)
            merged = {
                t["vehicle_id"]
                for t in trips
                for e in t.get("lane_completion_events", [])
                if e["from_lane"] == 2
                and e["to_lane"] == 1
                and e["x"] < 1000.0
                and abs(e.get("y", float("inf")) - 4.95) < 0.05
                and abs(e.get("vy", float("inf"))) < 0.05
                and t["vehicle_id"] in ending
                and e["time_s"] >= ending[t["vehicle_id"]]
            }
            row.update(
                ending_lane_observed_vehicles=len(ending),
                merge_completed_before_drop=len(merged),
                merge_completion_before_drop_rate=len(merged) / len(ending) if ending and trace else None,
                merge_completion_trace_available=trace,
            )
    except (OSError, ValueError, KeyError) as error:
        issues.append("position_evaluation_error:" + str(error))
    eligible = safe and all_completed and not issues
    row["performance_eligible"] = eligible
    if eligible:
        average = lambda values: sum(values) / len(values)
        row.update(
            mean_entry_wait_s=average([t["entered_s"] - t["requested_s"] for t in trips]),
            mean_travel_time_s=average([t["exited_s"] - t["entered_s"] for t in trips]),
            mean_system_time_s=average([t["exited_s"] - t["requested_s"] for t in trips]),
            fuel_g_per_km=(
                sum(t["fuel_mg"] for t in trips) / sum(t["distance_m"] for t in trips)
                if sum(t["distance_m"] for t in trips)
                else None
            ),
            exit_flow_veh_h=(
                sum(t["exited_s"] <= config["demand_duration_s"] for t in trips)
                * 3600
                / config["demand_duration_s"]
                if result["actual_end_s"] >= config["demand_duration_s"]
                else None
            ),
        )
    return row


def _means(rows, keys, metrics, eligible_key):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key) for key in keys)].append(row)
    summaries = []
    for values, members in groups.items():
        eligible = [r for r in members if r[eligible_key]]
        summary = dict(
            zip(keys, values),
            attempted_n=len(members),
            eligible_n=len(eligible),
            group_eligible=len(eligible) == len(members),
        )
        for metric in metrics:
            numbers = [r[metric] for r in eligible if r.get(metric) is not None]
            summary[metric + "_n"] = len(numbers)
            summary[metric + "_mean"] = (
                sum(numbers) / len(numbers) if numbers and summary["group_eligible"] else None
            )
        summaries.append(summary)
    return summaries


def summarize_cases(manifest_path, output_dir=None):
    """Return runs/pairs/means; optionally save a fresh, never-overwritten report."""
    manifest_path = Path(manifest_path).resolve()
    manifest = _read(manifest_path)
    paths = manifest["cases"] if isinstance(manifest, dict) else manifest
    runs = [load_case(manifest_path.parent / path) for path in paths]
    grouped = defaultdict(dict)
    for run in runs:
        key = run["seed"], run["scenario"]
        if run["mode"] in grouped[key]:
            raise ValueError("Duplicate seed/scenario/mode; separate different probes or versions")
        grouped[key][run["mode"]] = run
    metrics = list(TRAFFIC) + sorted(
        {
            k
            for r in runs
            for k in r
            if any(k == p + "_" + f for p in ("upstream", "downstream", "whole") for f in LAYER_FIELDS)
        }
    )
    pairs = []
    scenario_modes = {
        r["scenario"]: {q["mode"] for q in runs if q["scenario"] == r["scenario"]} for r in runs
    }
    for (seed, scenario), modes in grouped.items():
        for baseline, candidate in combinations([m for m in MODES if m in scenario_modes[scenario]], 2):
            a, b = modes.get(baseline), modes.get(candidate)
            reasons = []
            if a is None:
                reasons.append("missing_baseline")
            if b is None:
                reasons.append("missing_candidate")
            if a is not None and b is not None:
                for key, reason in (
                    ("demand_sha256", "demand_mismatch"),
                    ("parameters_sha256", "parameters_mismatch"),
                    ("source_version_sha256", "source_version_mismatch"),
                ):
                    if a[key] != b[key]:
                        reasons.append(reason)
            if a is not None and not a["performance_eligible"]:
                reasons.append("baseline_ineligible")
            if b is not None and not b["performance_eligible"]:
                reasons.append("candidate_ineligible")
            fallback = next(iter(modes.values()))["cohort_id"]
            pair = dict(
                seed=seed,
                scenario=scenario,
                baseline_mode=baseline,
                candidate_mode=candidate,
                cohort_id=(a["cohort_id"] if a else fallback) + ":" + (b["cohort_id"] if b else fallback),
                pair_eligible=not reasons,
                rejection_reasons=reasons,
                baseline_case_dir=a["case_dir"] if a else None,
                candidate_case_dir=b["case_dir"] if b else None,
            )
            pair.update(
                {
                    "delta_"
                    + key: (
                        b[key] - a[key]
                        if not reasons and a.get(key) is not None and b.get(key) is not None
                        else None
                    )
                    for key in metrics
                }
            )
            pairs.append(pair)
    report = dict(
        metadata=dict(
            manifest_sha256=_sha(manifest_path),
            audit_source_sha256=_sha(__file__),
            evaluator_source_sha256=_sha(__file__),
            layer_evaluator_source_sha256=_sha(Path(__file__).with_name("complete_layers.py")),
            delta_definition="candidate minus baseline; negative time/fuel is improvement",
            fuel_unit="g/km = total fuel_abs mg / total actual routeLength m; no density conversion",
            fuel_reference="https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html",
            throughput_window="[0, demand_duration_s], startup included; completed exits per hour",
            geometry_interpretation="Sample-based physical structures; NOA detections do not establish controlled formation",
            mean_policy="No successful-only performance means: all attempted members must be eligible; per-metric n preserves undefined geometry",
        ),
        runs=runs,
        pairs=pairs,
        run_means=_means(runs, ("scenario", "mode", "cohort_id"), metrics, "performance_eligible"),
        pair_means=_means(
            pairs,
            ("scenario", "baseline_mode", "candidate_mode", "cohort_id"),
            ["delta_" + key for key in metrics],
            "pair_eligible",
        ),
    )
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=False)
        (output_dir / "summary.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        for name in ("runs", "pairs", "run_means", "pair_means"):
            rows = report[name]
            fields = list(dict.fromkeys(key for row in rows for key in row))
            with (output_dir / (name + ".csv")).open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fields)
                writer.writeheader()
                writer.writerows(
                    {
                        k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                        for k, v in row.items()
                    }
                    for row in rows
                )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = summarize_cases(args.manifest, args.output)
    print(
        json.dumps(
            dict(
                output=str(args.output.resolve()),
                runs=len(report["runs"]),
                pairs=len(report["pairs"]),
                eligible_pairs=sum(p["pair_eligible"] for p in report["pairs"]),
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
