"""Read-only, flow-stratified bottleneck attribution from native 0.1 s samples.

Gate times use first measured crossings and linear interpolation ONLY between
adjacent 0.1 s observations of the same vehicle. No entry/exit extrapolation is
used. Every requested vehicle remains in the report, including left/right and
gap censoring. Means require every requested vehicle and every attempted seed.

The 800 <= x < 1000 m region has three physical lanes in both road scenarios.
Exposure is left-held over normal adjacent sample intervals, with no terminal
extrapolation. The fixed region window is [100,600) s; 1000 m first crossings
use the inclusive [100,600] s counting window (500 s denominator).
"""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

from experiments.native_comparison import load_case


GATES = (100, 600, 640, 800, 1000, 1100)
SEGMENTS = ((100, 600), (640, 1100), (800, 1100))
STEP_S = 0.1
TOLERANCE = 1e-6
WINDOW = (100.0, 600.0)
MODES = ("noa", "formation", "transform", "cooperative")
TIME_METRICS = (
    "mean_travel_time_s", "mean_system_time_s", "mean_entry_wait_s",
    *(f"mean_segment_{a}_{b}_s" for a, b in SEGMENTS),
)
REGION_METRICS = (
    "mean_n", "density_veh_km_lane", "mean_speed_mps",
    "low_speed_vehicle_s", "low_speed_fraction", "max_simultaneous_low_speed",
)
METRICS = (*TIME_METRICS, *("region_" + k for k in REGION_METRICS), "flow_1000m_veh_h")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _trips(path):
    if (path / "trips.json").is_file():
        return _read(path / "trips.json")
    if (path / "trips.jsonl.gz").is_file():
        with gzip.open(path / "trips.jsonl.gz", "rt", encoding="utf-8") as stream:
            return [json.loads(line) for line in stream]
    return []


def _region(steps, start, end, complete):
    duration = max(0.0, end - start)
    vehicle_s = low_s = speed_vehicle_m = observed_s = 0.0
    peak = 0
    for row in steps:
        dt = max(0.0, min(row["end_s"], end) - max(row["time_s"], start))
        if dt:
            observed_s += dt
            vehicle_s += row["n"] * dt
            low_s += row["low_speed_n"] * dt
            speed_vehicle_m += row["speed_sum_mps"] * dt
            peak = max(peak, row["low_speed_n"])
    usable = complete and abs(observed_s - duration) <= TOLERANCE and duration > 0
    return dict(
        start_s=start, end_s=end, duration_s=duration, observed_duration_s=observed_s,
        window_complete=usable, vehicle_s=vehicle_s,
        mean_n=vehicle_s / duration if usable else None,
        density_veh_km_lane=vehicle_s / duration / 0.6 if usable else None,
        mean_speed_mps=speed_vehicle_m / vehicle_s if usable and vehicle_s else None,
        low_speed_vehicle_s=low_s,
        low_speed_fraction=low_s / vehicle_s if usable and vehicle_s else None,
        max_simultaneous_low_speed=peak,
    )


def evaluate_case(case_dir):
    """Return audit, all requested gate/censor records and measured region steps."""
    path = Path(case_dir).resolve()
    source, result = _read(path / "input.json"), _read(path / "result.json")
    config = source["case"]
    issues = []
    try:
        native = load_case(path)
        issues.extend(native["audit_issues"])
    except (OSError, ValueError, KeyError, TypeError, IndexError, EOFError) as error:
        native = dict(performance_eligible=False)
        issues.append("native_audit_error:" + str(error))
    if source.get("positions_step_s") != STEP_S or config.get("step_s") != STEP_S:
        issues.append("requires_measured_0.1s_trace")
    trips = {t["vehicle_id"]: t for t in _trips(path)}
    vehicles = {}
    for request in source["arrivals"]:
        name = request["vehicle_id"]
        trip = trips.get(name, {})
        vehicles[name] = dict(
            vehicle_id=name, requested_s=request["requested_s"],
            entered_s=trip.get("entered_s"), exited_s=trip.get("exited_s"),
            first_observed_s=None, last_observed_s=None, last_observed_x_m=None,
            gates={str(g): dict(time_s=None, status="not_observed") for g in GATES},
            segments_s={}, segment_status={},
        )
    previous = None
    last_vehicle = {}
    steps = []
    frame_count = 0
    first_time = last_time = None
    trace_read_ok = True
    positions = path / "positions.jsonl.gz"
    try:
        with gzip.open(positions, "rt", encoding="utf-8") as stream:
            for line in stream:
                frame = json.loads(line)
                now, states = frame["time_s"], frame["states"]
                if not isinstance(now, (int, float)) or not math.isfinite(now) or not isinstance(states, dict):
                    raise ValueError("invalid frame time/states")
                frame_count += 1
                if first_time is None:
                    first_time = now
                    if min(abs(now), abs(now - STEP_S)) > TOLERANCE:
                        issues.append("position_trace_start_mismatch")
                normal_interval = False
                if previous is not None:
                    before, before_states = previous
                    normal_interval = abs(now - before - STEP_S) <= TOLERANCE
                    if not normal_interval:
                        issues.append("position_frame_gap_or_nonmonotonic_time")
                    if now <= before:
                        continue
                    if normal_interval:
                        region_states = [s for s in before_states.values() if 800 <= s[0] < 1000]
                        speed_sum = sum(s[2] for s in region_states)
                        n = len(region_states)
                        steps.append(dict(
                            time_s=before, end_s=now, n=n,
                            density_veh_km_lane=n / 0.6,
                            mean_speed_mps=speed_sum / n if n else None,
                            speed_sum_mps=speed_sum,
                            low_speed_n=sum(s[2] < 5.0 for s in region_states),
                        ))
                clean_states = {}
                for name, state in states.items():
                    if (not isinstance(state, (list, tuple)) or len(state) < 3
                            or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in state[:3])):
                        issues.append("invalid_position_state:" + name)
                        continue
                    clean_states[name] = state
                    if name not in vehicles:
                        issues.append("unrequested_position_vehicle:" + name)
                        continue
                    row = vehicles[name]
                    x = state[0]
                    last = last_vehicle.get(name)
                    if row["first_observed_s"] is None:
                        row["first_observed_s"] = now
                        for g in GATES:
                            if x > g:
                                row["gates"][str(g)]["status"] = "left_censored"
                            elif abs(x - g) <= TOLERANCE:
                                row["gates"][str(g)] = dict(time_s=now, status="observed")
                    elif last is not None:
                        old_time, old_x = last
                        adjacent = abs(now - old_time - STEP_S) <= TOLERANCE and normal_interval
                        if not adjacent:
                            issues.append("vehicle_observation_gap:" + name)
                        for g in GATES:
                            gate = row["gates"][str(g)]
                            if gate["status"] == "not_observed" and old_x < g <= x:
                                if adjacent:
                                    row["gates"][str(g)] = dict(
                                        time_s=old_time + (g - old_x) / (x - old_x) * (now - old_time),
                                        status="observed")
                                else:
                                    gate["status"] = "gap_censored"
                    row["last_observed_s"], row["last_observed_x_m"] = now, x
                    last_vehicle[name] = now, x
                previous = now, clean_states
                last_time = now
    except (OSError, ValueError, KeyError, TypeError, IndexError, EOFError) as error:
        trace_read_ok = False
        issues.append("position_read_error:" + str(error))
    if not frame_count:
        issues.append("empty_position_trace")
    if last_time is None or abs(last_time - result["actual_end_s"]) > TOLERANCE:
        issues.append("position_trace_end_mismatch")
    censored = {f"{a}_{b}": 0 for a, b in SEGMENTS}
    for row in vehicles.values():
        for gate in row["gates"].values():
            if gate["status"] == "not_observed" and row["first_observed_s"] is not None:
                gate["status"] = "right_censored"
        if row["entered_s"] is not None and row["first_observed_s"] is None:
            issues.append("entered_vehicle_not_observed:" + row["vehicle_id"])
        if (row["entered_s"] is not None and row["first_observed_s"] is not None
                and not -TOLERANCE <= row["first_observed_s"] - row["entered_s"] <= STEP_S + TOLERANCE):
            # SUMO subscriptions first expose a newly inserted vehicle one step
            # after entered_s. Earlier/later observations cannot certify coverage.
            issues.append("vehicle_observation_gap_at_entry:" + row["vehicle_id"])
        if (row["exited_s"] is not None and row["last_observed_s"] is not None
                and abs(row["exited_s"] - row["last_observed_s"]) > STEP_S + TOLERANCE):
            issues.append("vehicle_observation_gap_at_exit:" + row["vehicle_id"])
        if (row["exited_s"] is None and row["last_observed_s"] is not None
                and last_time is not None and row["last_observed_s"] < last_time - TOLERANCE):
            issues.append("vehicle_observation_gap_at_end:" + row["vehicle_id"])
        for a, b in SEGMENTS:
            key = f"{a}_{b}"
            t0, t1 = (row["gates"][str(g)]["time_s"] for g in (a, b))
            observed = t0 is not None and t1 is not None and t1 >= t0
            row["segments_s"][key] = t1 - t0 if observed else None
            row["segment_status"][key] = "observed" if observed else "censored"
            censored[key] += not observed
    if any(censored.values()):
        issues.append("censored_segment_times")
    issues = list(dict.fromkeys(issues))
    eligible = bool(native.get("performance_eligible")) and not issues and bool(vehicles)
    full_complete = trace_read_ok and not any("gap" in issue or "read_error" in issue for issue in issues)
    full = _region(steps, first_time or 0.0, last_time or 0.0, full_complete)
    window_complete = (full_complete and first_time is not None and first_time <= WINDOW[0]
                       and last_time is not None and last_time >= WINDOW[1])
    window = _region(steps, *WINDOW, window_complete)
    crossings = sum(row["gates"]["1000"]["time_s"] is not None
                    and WINDOW[0] <= row["gates"]["1000"]["time_s"] <= WINDOW[1]
                    for row in vehicles.values())
    run = dict(
        case_dir=str(path), flow_veh_h_lane=config["flow_veh_h_lane"], seed=config["seed"],
        scenario=config["scenario"], mode=config["mode"], safe=native.get("safe", False),
        all_completed=native.get("all_completed", False), requested=len(source["arrivals"]),
        departed=native.get("departed"), completed=native.get("completed"),
        actual_end_s=result["actual_end_s"], native_performance_eligible=native.get("performance_eligible", False),
        attribution_eligible=eligible, audit_issues=issues, segment_censored_n=censored,
        vehicles=list(vehicles.values()), region_steps=steps, region_full=full, region_window=window,
        position_sample_count=frame_count, first_position_sample_s=first_time,
        last_position_sample_s=last_time, flow_1000m_crossings=crossings,
        flow_1000m_veh_h=crossings * 3600 / (WINDOW[1] - WINDOW[0]) if window_complete else None,
        source_sha256=source.get("source_sha256", {}),
        input_sha256=_sha(path / "input.json"), result_sha256=_sha(path / "result.json"),
        positions_sha256=_sha(positions) if positions.is_file() else None,
    )
    for key in ("trips_sha256", "demand_sha256", "parameters_sha256", "source_version_sha256"):
        run[key] = native.get(key)
    for key in TIME_METRICS[:3]:
        run[key] = native.get(key)
    for a, b in SEGMENTS:
        key = f"{a}_{b}"
        run[f"mean_segment_{key}_s"] = (sum(v["segments_s"][key] for v in vehicles.values()) / len(vehicles)
                                            if eligible and not censored[key] else None)
    for metric in REGION_METRICS:
        run["region_" + metric] = window[metric] if window["window_complete"] else None
    return run


def _reasons(runs, names):
    reasons = []
    for name, run in zip(names, runs):
        if run is None:
            reasons.append("missing_" + name)
        elif not run["attribution_eligible"]:
            reasons.append(name + "_ineligible")
    present = [r for r in runs if r is not None]
    for key, reason in (("demand_sha256", "demand_mismatch"),
                        ("parameters_sha256", "parameters_mismatch"),
                        ("source_version_sha256", "source_version_mismatch")):
        if any(r.get(key) != present[0].get(key) for r in present[1:]):
            reasons.append(reason)
    return reasons


def _difference(a, b, metric, eligible):
    return b[metric] - a[metric] if eligible and a.get(metric) is not None and b.get(metric) is not None else None


def _means(rows, keys, metrics, eligible_key="pair_eligible"):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    summaries = []
    for values, members in sorted(groups.items()):
        eligible_n = sum(r[eligible_key] for r in members)
        row = dict(zip(keys, values), attempted_n=len(members), eligible_n=eligible_n,
                   group_eligible=eligible_n == len(members))
        for metric in metrics:
            numbers = [m[metric] for m in members if m.get(metric) is not None]
            row[metric + "_n"] = len(numbers)
            row[metric + "_mean"] = (sum(numbers) / len(numbers)
                                      if numbers and row["group_eligible"] and len(numbers) == len(members) else None)
        summaries.append(row)
    return summaries


def summarize_cases(manifest_path, output_dir=None):
    """Audit each case, pair by flow/seed, and optionally save a fresh report."""
    manifest_path = Path(manifest_path).resolve()
    manifest = _read(manifest_path)
    paths = manifest["cases"] if isinstance(manifest, dict) else manifest
    if output_dir is not None and Path(output_dir).exists():
        raise FileExistsError(output_dir)
    runs, excluded = [], []
    grouped = {}
    for item in paths:
        path = (manifest_path.parent / item).resolve()
        config = _read(path / "input.json")["case"]
        if config["mode"] not in MODES:
            excluded.append(dict(case_dir=str(path), mode=config["mode"], reason="outside_NOA_formation_attribution"))
            continue
        key = config["flow_veh_h_lane"], config["seed"], config["scenario"], config["mode"]
        if key in grouped:
            raise ValueError("Duplicate flow/seed/scenario/mode; separate versions/probes")
        run = evaluate_case(path)
        grouped[key] = run
        runs.append(run)
    flow_seeds = sorted({(r["flow_veh_h_lane"], r["seed"]) for r in runs})
    effects, attributions, ablations, scenario_pairs = [], [], [], []
    for flow, seed in flow_seeds:
        for mode in ("noa", "transform"):
            a, b = (grouped.get((flow, seed, scenario, mode)) for scenario in ("straight3", "lane_drop"))
            reasons = _reasons((a, b), ("straight", "drop"))
            row = dict(flow_veh_h_lane=flow, seed=seed, mode=mode, pair_eligible=not reasons,
                       rejection_reasons=reasons, straight_case_dir=a["case_dir"] if a else None,
                       drop_case_dir=b["case_dir"] if b else None)
            row.update({"additional_" + k: _difference(a, b, k, not reasons) for k in METRICS})
            effects.append(row)
        four = [grouped.get((flow, seed, scenario, mode))
                for mode in ("noa", "transform") for scenario in ("straight3", "lane_drop")]
        reasons = _reasons(four, ("noa_straight", "noa_drop", "transform_straight", "transform_drop"))
        row = dict(flow_veh_h_lane=flow, seed=seed, baseline_mode="noa", candidate_mode="transform",
                   pair_eligible=not reasons, rejection_reasons=reasons)
        for k in METRICS:
            values = [r.get(k) if r else None for r in four]
            row["reduction_" + k] = ((values[1] - values[0]) - (values[3] - values[2])
                                     if not reasons and all(v is not None for v in values) else None)
        reduction = row["reduction_mean_segment_640_1100_s"]
        row["supports_bottleneck_time_reduction"] = reduction > 0 if reduction is not None else None
        attributions.append(row)
        for scenario in ("straight3", "lane_drop"):
            comparisons = [("noa", "transform")]
            if scenario == "lane_drop" and any(r["mode"] == "formation" and r["flow_veh_h_lane"] == flow for r in runs):
                comparisons += [("noa", "formation"), ("formation", "transform")]
            for baseline, candidate in comparisons:
                a, b = (grouped.get((flow, seed, scenario, mode)) for mode in (baseline, candidate))
                reasons = _reasons((a, b), ("baseline", "candidate"))
                pair = dict(flow_veh_h_lane=flow, seed=seed, scenario=scenario,
                            baseline_mode=baseline, candidate_mode=candidate,
                            pair_eligible=not reasons, rejection_reasons=reasons)
                pair.update({"delta_" + k: _difference(a, b, k, not reasons) for k in METRICS})
                (scenario_pairs if (baseline, candidate) == ("noa", "transform") else ablations).append(pair)
    report = dict(
        metadata=dict(
            manifest=str(manifest_path), manifest_sha256=_sha(manifest_path),
            evaluator_source_sha256=_sha(__file__),
            native_audit_source_sha256=_sha(Path(__file__).with_name("native_comparison.py")),
            sample_step_s=STEP_S, gates_m=list(GATES), region_m=[800, 1000], region_lanes=3,
            low_speed_threshold_mps=5.0, region_window_s=list(WINDOW),
            region_exposure="Left-held measured samples on adjacent 0.1s intervals; [100,600); no terminal extrapolation",
            speed_mean="Vehicle-time weighted mean of measured speeds in region",
            flow_window="Inclusive [100,600]s first 1000m crossings / 500s * 3600; not a saturation capacity estimate",
            effect_definition="lane_drop minus straight3 for the same flow, seed and mode",
            reduction_definition="NOA (drop-straight) minus transform (drop-straight); positive time/accumulation is reduction; speed/flow have the opposite benefit direction",
            pair_delta_definition="candidate minus baseline",
            mean_policy="Every requested vehicle and every attempted seed must qualify; no successful-only means",
            interpretation="Positive primary segment reduction supports time attribution; safety, accumulation, and physical formation still require separate evidence",
        ),
        excluded_cases=excluded, runs=runs, scenario_effects=effects, attributions=attributions,
        scenario_pairs=scenario_pairs, ablations=ablations,
        run_means=_means(runs, ("flow_veh_h_lane", "scenario", "mode"), METRICS, "attribution_eligible"),
        attribution_means=_means(attributions, ("flow_veh_h_lane",), ["reduction_" + k for k in METRICS]),
        scenario_effect_means=_means(effects, ("flow_veh_h_lane", "mode"), ["additional_" + k for k in METRICS]),
        scenario_pair_means=_means(scenario_pairs, ("flow_veh_h_lane", "scenario", "baseline_mode", "candidate_mode"), ["delta_" + k for k in METRICS]),
        ablation_means=_means(ablations, ("flow_veh_h_lane", "scenario", "baseline_mode", "candidate_mode"), ["delta_" + k for k in METRICS]),
    )
    if output_dir is not None:
        _save(report, Path(output_dir))
    return report


def _csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()} for row in rows)


def _save(report, output):
    output.mkdir(parents=True, exist_ok=False)
    # Detailed samples live in compressed CSV, leaving summary.json readable.
    compact = {k: v for k, v in report.items() if k != "runs"}
    compact["runs"] = [{k: v for k, v in r.items() if k not in ("vehicles", "region_steps")} for r in report["runs"]]
    (output / "summary.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for name, rows in compact.items():
        if isinstance(rows, list):
            _csv(output / (name + ".csv"), rows)
    vehicles = []
    for run in report["runs"]:
        identity = {k: run[k] for k in ("flow_veh_h_lane", "seed", "scenario", "mode", "case_dir")}
        for vehicle in run["vehicles"]:
            row = dict(identity, **{k: v for k, v in vehicle.items() if k not in ("gates", "segments_s", "segment_status")})
            for gate, values in vehicle["gates"].items():
                row["gate_" + gate + "_s"] = values["time_s"]
                row["gate_" + gate + "_status"] = values["status"]
            row.update({"segment_" + k + "_s": v for k, v in vehicle["segments_s"].items()})
            row.update({"segment_" + k + "_status": v for k, v in vehicle["segment_status"].items()})
            vehicles.append(row)
    _csv(output / "vehicles.csv", vehicles)
    with gzip.open(output / "region_steps.csv.gz", "wt", encoding="utf-8", newline="") as stream:
        fields = ["flow_veh_h_lane", "seed", "scenario", "mode", "case_dir", "time_s", "end_s", "n", "density_veh_km_lane", "mean_speed_mps", "speed_sum_mps", "low_speed_n"]
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for run in report["runs"]:
            identity = {k: run[k] for k in fields[:5]}
            writer.writerows(dict(identity, **step) for step in run["region_steps"])
    (output / "input_hashes.json").write_text(json.dumps([
        {k: r[k] for k in ("case_dir", "input_sha256", "result_sha256", "trips_sha256", "positions_sha256", "source_sha256")}
        for r in report["runs"]], indent=2) + "\n", encoding="utf-8")
    (output / "bottleneck_attribution.source.py").write_bytes(Path(__file__).read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = summarize_cases(args.manifest, args.output)
    print(json.dumps(dict(output=str(args.output.resolve()), runs=len(report["runs"]),
                          eligible_runs=sum(r["attribution_eligible"] for r in report["runs"]),
                          attribution_means=report["attribution_means"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
