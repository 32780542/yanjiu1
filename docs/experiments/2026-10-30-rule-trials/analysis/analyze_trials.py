"""Independent, standard-library analysis of saved native SUMO literature trials.

Run: python analyze_trials.py --manifest manifest.json --output analysis_output
No simulator, controller import, historical complete-layer detector or rerun is used.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import mean


RULE_SOURCE = "noa/native_rules.py"
REQUIRED_SOURCES = {"experiments/native_sumo.py", "experiments/global_reference.py",
                    "experiments/complete_layers.py", RULE_SOURCE,
                    "run_native_flow.py", "research/common.py"}
PHYSICAL_KEYS = {"length", "width", "minGap", "tau", "accel", "decel", "emergencyDecel",
                 "maxSpeed", "speedFactor", "speedDev", "sigma", "carFollowModel", "emissionClass"}
FLAGS = ("vehicle_seconds", "participating_vehicle_seconds", "participation_rate",
         "mean_participants", "peak_participants", "episodes", "mean_episode_s", "max_episode_s")
DIRECT = ("mean_travel_time_s", "mean_system_time_s", "mean_entry_wait_s", "fuel_g_per_km",
          "exit_flow_veh_h", "clearance_after_demand_s", "lane_changes", "lane_change_completions")
SEGMENTS = {"upstream": (100.0, 600.0), "bottleneck": (640.0, 1100.0)}
METRICS = DIRECT + tuple("flag_" + key for key in FLAGS) + tuple(
    key + "_mean_time_s" for key in SEGMENTS)
IDENTITY = ("candidate", "stage", "flow", "seed", "scenario", "mode", "run_dir")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def avg(values):
    return mean(values) if values else None


def equal(a, b):
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-7)
    return a == b


def audit_positions(run, trips):
    """Left-constant 0/1 integral and linear interpolation of actual x brackets."""
    previous_time = first_time = None
    previous_flags, active, episodes = {}, {}, []
    vehicle_seconds = participating_seconds = peak = 0
    previous_points, crossings = {}, {}
    frame_count = 0
    issues = []
    with gzip.open(run / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            frame = json.loads(line)
            time = float(frame["time_s"])
            if not math.isfinite(time) or (previous_time is not None and time < previous_time):
                raise ValueError("positions times must be finite and nondecreasing")
            states = frame["states"]
            flags = frame.get("formation_states")
            valid_flags = (isinstance(flags, dict) and set(flags) == set(states)
                           and all(type(v) is int and v in (0, 1) for v in flags.values()))
            if not valid_flags:
                issues.append("invalid_formation_flags")
                flags = {}
            if previous_time is None:
                first_time = time
            else:
                dt = time - previous_time
                vehicle_seconds += dt * len(previous_flags)
                participating_seconds += dt * sum(previous_flags.values())
                for key in active:
                    active[key] += dt
            for key in tuple(active):
                if not flags.get(key):
                    episodes.append(active.pop(key))
            for key, flag in flags.items():
                if flag:
                    active.setdefault(key, 0.0)
            peak = max(peak, sum(flags.values()))
            for key, state in states.items():
                x = float(state[0])
                if not math.isfinite(x):
                    raise ValueError("non-finite x position")
                observed = crossings.setdefault(key, {})
                for threshold in (100.0, 600.0, 640.0, 1100.0):
                    if threshold in observed:
                        continue
                    if x == threshold:
                        observed[threshold] = time
                    elif key in previous_points:
                        old_t, old_x = previous_points[key]
                        if old_x < threshold < x and time > old_t:
                            observed[threshold] = old_t + (time - old_t) * (threshold - old_x) / (x - old_x)
                previous_points[key] = (time, x)
            # Do not interpolate through a vehicle's missing observations.
            previous_points = {key: previous_points[key] for key in states}
            previous_time, previous_flags = time, flags
            frame_count += 1
    if not frame_count:
        issues.append("empty_positions")
    duration = previous_time - first_time if frame_count else 0.0
    episodes.extend(active.values())
    summary = dict(vehicle_seconds=vehicle_seconds, participating_vehicle_seconds=participating_seconds,
                   participation_rate=participating_seconds / vehicle_seconds if vehicle_seconds else None,
                   mean_participants=participating_seconds / duration if duration else None,
                   peak_participants=peak, episodes=len(episodes), mean_episode_s=avg(episodes),
                   max_episode_s=max(episodes) if episodes else None)
    rows = []
    for trip in trips:
        key = trip["vehicle_id"]
        for name, (start_x, end_x) in SEGMENTS.items():
            times = crossings.get(key, {})
            start, end = times.get(start_x), times.get(end_x)
            eligible = trip.get("entered_s") is not None and start is not None and end is not None and end >= start
            reason = ("observed_crossings" if eligible else "not_entered" if trip.get("entered_s") is None
                      else "missing_start_crossing" if start is None else "missing_end_crossing" if end is None
                      else "crossings_out_of_order")
            rows.append(dict(vehicle_id=key, segment=name, start_x_m=start_x, end_x_m=end_x,
                             start_crossing_s=start, end_crossing_s=end, eligible=eligible,
                             eligibility_reason=reason, time_s=end - start if eligible else None))
    return summary, rows, issues, frame_count, previous_time


def analyze_case(record, manifest_dir):
    row = {key: record.get(key) for key in IDENTITY}
    row.update(eligible=False, issues="", details=[], **{key: None for key in METRICS})
    issues, segment_rows, invariant = [], [], {}
    run = Path(str(record.get("run_dir", "")))
    if not run.is_absolute():
        run = manifest_dir / run
    row["run_dir"] = str(run.resolve())
    try:
        inp, result = load_json(run / "input.json"), load_json(run / "result.json")
        trips = load_json(run / "trips.json")
        for key in IDENTITY:
            if record.get(key) is None:
                issues.append("missing_manifest_field")
        case = inp["case"]
        if (not isinstance(inp.get("physical"), dict)
                or not PHYSICAL_KEYS.issubset(inp["physical"])
                or any(key not in inp for key in ("speed_mode", "lane_change_mode", "positions_step_s"))
                or any(key not in case for key in ("step_s", "lane_change_duration_s"))):
            issues.append("missing_physical_evidence")
        for manifest_key, saved_key in (("flow", "flow_veh_h_lane"), ("seed", "seed"),
                                        ("scenario", "scenario"), ("mode", "mode")):
            if record.get(manifest_key) != case.get(saved_key) or result.get(saved_key) != case.get(saved_key):
                issues.append("manifest_config_mismatch")
        if case.get("demand_duration_s") != 600 or case.get("max_time_s") != 900:
            issues.append("unexpected_trial_duration")
        for key, value in case.items():
            if result.get(key) != value:
                issues.append("input_result_config_mismatch")
        hashes = inp.get("source_sha256", {})
        if not REQUIRED_SOURCES.issubset(hashes) or hashes != result.get("source_sha256"):
            issues.append("source_manifest_mismatch")
        for name, expected in hashes.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                issues.append("invalid_snapshot_path")
                continue
            path = run / "source" / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                issues.append("snapshot_hash")
                row["details"].append("snapshot hash mismatch: " + name)
        for key in ("status", "safe", "all_completed", "performance_comparison_eligible", "requested",
                    "departed", "completed", "actual_end_s", "collisions", "teleports", "error",
                    "completion_fraction", "pending_final", "onroad_final", "fuel_source", "sumo_version",
                    "completed_subset_mean_travel_time_s", "completed_subset_mean_system_time_s",
                    "departed_subset_mean_entry_wait_s", "completed_subset_fuel_g_per_km", "lane_transitions") + DIRECT:
            row[key] = result.get(key)
        safe = (result.get("safe") is True and result.get("collisions") == 0
                and result.get("teleports") == 0 and result.get("error") is None
                and result.get("cleanup_error") is None and result.get("tripinfo_error") is None)
        complete = (result.get("all_completed") is True and bool(trips)
                    and all(t.get("entered_s") is not None and t.get("exited_s") is not None for t in trips)
                    and len(trips) == result.get("requested") == result.get("completed"))
        if not safe:
            issues.append("unsafe_or_error")
        if not complete or result.get("status") != "drained" or result.get("performance_comparison_eligible") is not True:
            issues.append("incomplete_or_ineligible")
        if {t["vehicle_id"] for t in trips} != {t["vehicle_id"] for t in inp["arrivals"]}:
            issues.append("trip_demand_ids_mismatch")
        saved_flags = result.get("formation_state")
        if not isinstance(saved_flags, dict) or not all(key in saved_flags for key in FLAGS):
            issues.append("missing_direct_flag_summary")
            saved_flags = {}
        row.update({"flag_" + key: saved_flags.get(key) for key in FLAGS})
        audited, segment_rows, frame_issues, frame_count, last_time = audit_positions(run, trips)
        issues.extend(frame_issues)
        row["positions_frames"] = frame_count
        row.update({"flag_recomputed_" + key: audited[key] for key in FLAGS})
        if any(not equal(saved_flags.get(key), audited[key]) for key in FLAGS):
            issues.append("flag_summary_mismatch")
        if not equal(last_time, result.get("actual_end_s")):
            issues.append("positions_end_mismatch")
        for name in SEGMENTS:
            eligible_segments = [s for s in segment_rows if s["segment"] == name and s["eligible"]]
            row[name + "_eligible_vehicles"] = len(eligible_segments)
            row[name + "_total_vehicles"] = len(trips)
            row[name + "_mean_time_s"] = avg([s["time_s"] for s in eligible_segments])
        version = result.get("sumo_version")
        if not version or version == "unavailable":
            issues.append("missing_sumo_version")
        # Normalize only run-local paths in command evidence; physical switches remain exact.
        command_path = run / "sumo_command.json"
        if command_path.is_file():
            command = load_json(command_path)
            if not isinstance(command, list) or not command:
                issues.append("invalid_sumo_command")
                command = None
            else:
                command = [str(arg).replace(str(run.resolve()), "<RUN>").replace(str(run), "<RUN>") for arg in command]
        else:
            command = None
            issues.append("missing_sumo_command")
        invariant = dict(demand=digest(inp["arrivals"]), physics=digest({
            key: inp.get(key) for key in ("physical", "speed_mode", "lane_change_mode", "positions_step_s",
                                         "insertion", "positions_schema", "formation_state_schema",
                                         "longitudinal_coordinate", "lateral_coordinate")}),
            config=digest({key: value for key, value in case.items() if key != "mode"}),
            sumo=digest(dict(version=version, command=command)),
            sources=digest({key: value for key, value in hashes.items() if key != RULE_SOURCE}))
        row["demand_sha256"] = invariant["demand"]
        row["rules_sha256"] = hashes.get(RULE_SOURCE)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        issues.append("missing_or_invalid_evidence")
        row["details"].append(type(exc).__name__ + ": " + str(exc))
    row["issues"] = "|".join(sorted(set(issues)))
    row["eligible"] = not issues
    row["_invariant"] = invariant
    row["_segments"] = {name: {s["vehicle_id"]: s["time_s"] for s in segment_rows
                               if s["segment"] == name and s["eligible"]} for name in SEGMENTS}
    for segment in segment_rows:
        segment.update({key: row[key] for key in IDENTITY})
        segment["case_eligible"] = row["eligible"]
    return row, segment_rows


def paired(left, right, comparison, candidate, stage, flow, seed, scenario, mode):
    row = dict(comparison=comparison, candidate=candidate, stage=stage, flow=flow, seed=seed,
               scenario=scenario, mode=mode, left_run=left["run_dir"] if left else None,
               right_run=right["run_dir"] if right else None)
    issues = []
    if left is None:
        issues.append("missing_reference")
    elif not left["eligible"]:
        issues.append("reference_ineligible:" + left["issues"])
    if right is None:
        issues.append("missing_target")
    elif not right["eligible"]:
        issues.append("target_ineligible:" + right["issues"])
    if left is not None and right is not None:
        for key in ("demand", "physics", "config", "sumo", "sources"):
            if left["_invariant"].get(key) != right["_invariant"].get(key):
                issues.append(key + "_mismatch")
        if left["candidate"] == right["candidate"] and left.get("rules_sha256") != right.get("rules_sha256"):
            issues.append("rules_mismatch")
    row["issues"], row["eligible"] = "|".join(issues), not issues
    for key in METRICS:
        a, b = (left.get(key) if left else None), (right.get(key) if right else None)
        row["left_" + key], row["right_" + key] = a, b
        row["delta_" + key] = b - a if not issues and a is not None and b is not None else None
    for name in SEGMENTS:
        row[name + "_left_eligible_vehicles"] = left.get(name + "_eligible_vehicles") if left else None
        row[name + "_right_eligible_vehicles"] = right.get(name + "_eligible_vehicles") if right else None
        left_values = left["_segments"][name] if left else {}
        right_values = right["_segments"][name] if right else {}
        common = sorted(left_values.keys() & right_values.keys())
        row[name + "_matched_vehicles"] = len(common)
        metric = name + "_mean_time_s"
        row["left_" + metric] = avg([left_values[key] for key in common])
        row["right_" + metric] = avg([right_values[key] for key in common])
        row["delta_" + metric] = avg([right_values[key] - left_values[key] for key in common]) if not issues else None
    return row


def build_pairs(cases):
    index = {}
    for case in cases:
        key = tuple(case[k] for k in ("candidate", "stage", "flow", "seed", "scenario", "mode"))
        if key in index:
            case["eligible"] = index[key]["eligible"] = False
            case["issues"] += "|duplicate_manifest_key"
            index[key]["issues"] += "|duplicate_manifest_key"
        index[key] = case
    pairs = []
    for key, case in index.items():
        candidate, stage, flow, seed, scenario, mode = key
        if candidate != "base":
            base = index.get(("base", stage, flow, seed, scenario, mode))
            pairs.append(paired(base, case, "candidate_vs_base", *key))
    contexts = sorted({tuple(c[k] for k in ("candidate", "stage", "flow", "seed", "scenario"))
                       for c in cases if c["mode"] in ("noa", "transform")}, key=str)
    for key in contexts:
        noa, transform = index.get(key + ("noa",)), index.get(key + ("transform",))
        pairs.append(paired(noa, transform, "transform_vs_noa", *key, "transform-minus-noa"))
    return pairs


def aggregate(pairs):
    groups = {}
    group_keys = ("comparison", "candidate", "stage", "flow", "scenario", "mode")
    for pair in pairs:
        groups.setdefault(tuple(pair[k] for k in group_keys), []).append(pair)
    rows = []
    for key, values in groups.items():
        suppressed = any(not p["eligible"] for p in values)
        row = dict(zip(group_keys, key), pairs=len(values), eligible_pairs=sum(p["eligible"] for p in values),
                   suppressed=suppressed, issues="|".join(sorted({p["issues"] for p in values if p["issues"]})))
        for metric in METRICS:
            available = [p["delta_" + metric] for p in values if p["delta_" + metric] is not None]
            row["n_" + metric] = len(available)
            row["mean_delta_" + metric] = avg(available) if not suppressed and len(available) == len(values) else None
        rows.append(row)
    return rows


def write_csv(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row if not key.startswith("_")))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items() if key in keys})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = load_json(args.manifest)
    if not isinstance(manifest, list):
        parser.error("manifest must be a JSON list of case records")
    args.output.mkdir(parents=True, exist_ok=True)
    cases, segments = [], []
    for record in manifest:
        row, observed = analyze_case(record, args.manifest.resolve().parent)
        cases.append(row)
        segments.extend(observed)
    pairs = build_pairs(cases)
    eligibility_by_run = {case["run_dir"]: case["eligible"] for case in cases}
    for segment in segments:
        segment["case_eligible"] = eligibility_by_run[segment["run_dir"]]
    aggregates = aggregate(pairs)
    warnings = ["Direct 0/1 participants are all reported participants, not the size of one platoon.",
                "mean_episode_s is the existing mean continuous-1 duration; no holding threshold or layer detector is used.",
                "Segment times use only each vehicle's observed front-position crossing brackets, without extrapolation.",
                "Per-case segment means cover independently eligible vehicles. Paired segment means/deltas use the common per-vehicle eligible set; counts and vehicle rows are retained.",
                "All case rows remain visible. Unsafe, incomplete, invalid or mismatched pairs have no deltas; their aggregate group is suppressed.",
                "Candidate-minus-base holds mode fixed. Transform-minus-NOA holds candidate fixed; base NOA remains the original reference.",
                "A rule changing regular longitudinal following also changes candidate NOA; its transform-minus-NOA comparison cannot isolate a formation-only effect.",
                "Only noa/native_rules.py source differences are permitted across paired runs; every saved snapshot is hash-verified.",
                "Per-case observed flag/segment/subset values on unsafe or incomplete runs are descriptive and excluded from paired aggregates."]
    clean_cases = [{k: v for k, v in row.items() if not k.startswith("_")} for row in cases]
    data = dict(manifest=str(args.manifest.resolve()), cases=clean_cases, pairs=pairs, aggregates=aggregates,
                segment_vehicles=segments, warnings=warnings,
                definitions={"delta": "target minus reference; negative travel/system/wait/fuel means improvement",
                             "flag_prefix": "saved result.json formation_state values",
                             "flag_recomputed_prefix": "independent left-constant integral of positions 0/1 reports",
                             "segments": SEGMENTS})
    (args.output / "analysis.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for filename, rows in (("per_case", clean_cases), ("paired", pairs), ("paired_aggregates", aggregates),
                           ("segment_vehicles", segments)):
        write_csv(args.output / (filename + ".csv"), rows)
    lines = ["# Literature-rule trial analysis", "", f"Cases: {len(cases)}; eligible: {sum(c['eligible'] for c in cases)}.", "",
             "All differences below are target minus reference. Blank means suppressed or unavailable.", "",
             "| Comparison | Candidate | Stage | Flow | Scenario | Mode | Pairs | Eligible | Suppressed | Δ TT (s) | Δ fuel (g/km) |",
             "|---|---|---|---:|---|---|---:|---:|---|---:|---:|"]
    for row in aggregates:
        values = [row[k] for k in ("comparison", "candidate", "stage", "flow", "scenario", "mode", "pairs", "eligible_pairs", "suppressed",
                                   "mean_delta_mean_travel_time_s", "mean_delta_fuel_g_per_km")]
        lines.append("| " + " | ".join("" if v is None else f"{v:.6g}" if isinstance(v, float) else str(v) for v in values) + " |")
    lines.extend(["", "## Interpretation", ""] + ["- " + warning for warning in warnings])
    lines.extend(["", "## Case issues", ""] + [f"- {c['candidate']} / {c['mode']} / flow {c['flow']} / seed {c['seed']}: {c['issues']}" for c in cases if c["issues"]])
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(dict(cases=len(cases), eligible_cases=sum(c["eligible"] for c in cases),
                          pairs=len(pairs), eligible_pairs=sum(p["eligible"] for p in pairs), output=str(args.output.resolve()))))


if __name__ == "__main__":
    main()
