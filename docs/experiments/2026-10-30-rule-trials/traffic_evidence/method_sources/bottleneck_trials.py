"""Cache the existing measured bottleneck evaluator for sealed trial profiles.

The five profiles are base_noa, base_transform, T_transform, TM_noa,
TM_transform. No simulator or historical formation evaluator is invoked.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "variants/phase5g_pure_formation"))
from experiments import bottleneck_attribution as existing

PROFILES = {"base_noa": ("base", "noa"), "base_transform": ("base", "transform"),
            "T_transform": ("T", "transform"), "TM_noa": ("TM", "noa"),
            "TM_transform": ("TM", "transform")}
COMPARISONS = (("base_transform", "base_noa", "complete_strategy_same_following"),
               ("T_transform", "base_transform", "CTH_candidate_change"),
               ("TM_noa", "base_noa", "CTH_NOA_change"),
               ("TM_transform", "base_transform", "CTH_and_M_candidate_change"),
               ("TM_transform", "TM_noa", "complete_strategy_same_following"),
               ("TM_transform", "T_transform", "M_increment_on_CTH"))
METRICS = (*existing.METRICS, "fuel_g_per_km", "lane_changes", "lane_change_completions")
RULE = "noa/native_rules.py"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return existing._sha(Path(path))


def obj_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_rows(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def write_ledger(path, columns, rows):
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as stream:
        stream.write(json.dumps(columns, separators=(",", ":")) + "\n")
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")


def brackets(path, vehicles):
    """Retain original adjacent measurement endpoints for evaluator-observed gates."""
    index = {v["vehicle_id"]: i for i, v in enumerate(vehicles)}
    pending = {v["vehicle_id"]: {int(g): data["time_s"] for g, data in v["gates"].items()
                                if data["status"] == "observed"} for v in vehicles}
    previous, seen = {}, set()
    for_frame_time = None
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            now, states = frame["time_s"], frame["states"]
            normal = for_frame_time is not None and abs(now - for_frame_time - existing.STEP_S) <= existing.TOLERANCE
            for key, state in states.items():
                if key not in pending:
                    continue
                x = state[0]
                old = previous.get(key)
                for gate, expected in tuple(pending[key].items()):
                    if key not in seen and abs(x - gate) <= existing.TOLERANCE:
                        t0, x0, t1, x1 = now, x, now, x
                        actual = now
                    elif old is not None and normal and abs(now - old[0] - existing.STEP_S) <= existing.TOLERANCE and old[1] < gate <= x:
                        t0, x0, t1, x1 = old[0], old[1], now, x
                        actual = t0 + (gate - x0) / (x1 - x0) * (t1 - t0)
                    else:
                        continue
                    if abs(actual - expected) > existing.TOLERANCE:
                        raise ValueError("gate bracket disagrees with existing evaluator")
                    rows.append([index[key], gate, t0, x0, t1, x1])
                    del pending[key][gate]
                previous[key] = (now, x)
                seen.add(key)
            for_frame_time = now
    if any(pending.values()):
        raise ValueError("an observed evaluator gate has no retained measurement bracket")
    return rows


def verify_ledgers(folder, run, vehicles):
    with gzip.open(folder / "region_steps.jsonl.gz", "rt", encoding="utf-8") as stream:
        fields = json.loads(next(stream))
        steps = [dict(zip(fields, json.loads(line))) for line in stream]
    rebuilt = existing._region(steps, *existing.WINDOW, run["region_window"]["window_complete"])
    for key, value in run["region_window"].items():
        actual = rebuilt[key]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if actual is None or not math.isclose(actual, value, rel_tol=1e-9, abs_tol=existing.TOLERANCE):
                raise ValueError("region ledger reconstruction mismatch: " + key)
        elif actual != value:
            raise ValueError("region ledger reconstruction mismatch: " + key)
    reconstructed = {}
    with gzip.open(folder / "gate_brackets.jsonl.gz", "rt", encoding="utf-8") as stream:
        next(stream)
        for line in stream:
            i, gate, t0, x0, t1, x1 = json.loads(line)
            value = t0 if t1 == t0 else t0 + (gate - x0) / (x1 - x0) * (t1 - t0)
            expected = vehicles[i]["gates"][str(gate)]["time_s"]
            if not math.isclose(value, expected, rel_tol=1e-9, abs_tol=existing.TOLERANCE):
                raise ValueError("gate ledger reconstruction mismatch")
            reconstructed[i, str(gate)] = value
    expected_count = sum(g["status"] == "observed" for v in vehicles for g in v["gates"].values())
    if len(reconstructed) != expected_count:
        raise ValueError("gate ledger count mismatch")
    count = sum(existing.WINDOW[0] <= t <= existing.WINDOW[1]
                for (i, gate), t in reconstructed.items() if gate == "1000")
    if count != run["flow_1000m_crossings"]:
        raise ValueError("first-crossing flow reconstruction mismatch")
    for a, b in existing.SEGMENTS:
        for i, vehicle in enumerate(vehicles):
            original = vehicle["segments_s"][f"{a}_{b}"]
            left, right = reconstructed.get((i, str(a))), reconstructed.get((i, str(b)))
            value = right - left if left is not None and right is not None else None
            if original is None:
                if value is not None:
                    raise ValueError("censored segment reconstructed as observed")
            elif value is None or not math.isclose(value, original, rel_tol=1e-9, abs_tol=existing.TOLERANCE):
                raise ValueError("segment ledger reconstruction mismatch")
    return dict(region_window_reconstructed=True, gate_brackets_reconstructed=expected_count,
                first_crossings_reconstructed=count, all_vehicle_segments_reconstructed=True)


def case_cache(record, root, evaluator_hashes):
    path = Path(record["run_dir"]).resolve()
    folder = root / "cases" / hashlib.sha256(str(path).encode()).hexdigest()[:16]
    metadata_path = folder / "case.json"
    input_path, result_path = path / "input.json", path / "result.json"
    inp, result = read(input_path), read(result_path)
    if not inp.get("formation_state_schema"):
        raise ValueError("direct local flag schema required; historical layer path is forbidden: " + str(path))
    if result.get("status") in (None, "starting"):
        raise ValueError("case is not sealed: " + str(path))
    inputs = {name: dict(size=(path / name).stat().st_size, mtime_ns=(path / name).stat().st_mtime_ns)
              for name in ("input.json", "result.json", "trips.json", "positions.jsonl.gz")}
    if metadata_path.is_file():
        saved = read(metadata_path)
        if saved["input_stats"] != inputs or saved["evaluator_hashes"] != evaluator_hashes:
            raise ValueError("immutable cached case inputs/evaluator changed: " + str(path))
        for name, expected in saved["ledger_sha256"].items():
            if sha(folder / name) != expected:
                raise ValueError("cached ledger hash mismatch: " + name)
        return saved["run"]
    folder.mkdir(parents=True, exist_ok=False)
    run = existing.evaluate_case(path)
    if record["flow"] != run["flow_veh_h_lane"] or record["seed"] != run["seed"] or record["scenario"] != run["scenario"] or record["mode"] != run["mode"]:
        raise ValueError("manifest/result identity mismatch: " + str(path))
    run.update(profile=next(k for k, value in PROFILES.items() if value == (record["candidate"], record["mode"])),
               candidate=record["candidate"], stage=record["stage"],
               rules_sha256=run["source_sha256"].get(RULE),
               nonrule_source_sha256=obj_sha({k: v for k, v in run["source_sha256"].items() if k != RULE}))
    for key in ("fuel_g_per_km", "lane_changes", "lane_change_completions"):
        run[key] = result.get(key)
    steps, vehicles = run.pop("region_steps"), run.pop("vehicles")
    columns = ("time_s", "end_s", "n", "low_speed_n", "speed_sum_mps")
    write_ledger(folder / "region_steps.jsonl.gz", columns, ([step[k] for k in columns] for step in steps))
    write_ledger(folder / "gate_brackets.jsonl.gz", ("vehicle_index", "gate_m", "t0", "x0", "t1", "x1"),
                 brackets(path / "positions.jsonl.gz", vehicles))
    with gzip.open(folder / "vehicles.json.gz", "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(vehicles, stream, separators=(",", ":"), allow_nan=False)
    checks = verify_ledgers(folder, run, vehicles)
    run["ledger_dir"] = str(folder.resolve())
    names = ("region_steps.jsonl.gz", "gate_brackets.jsonl.gz", "vehicles.json.gz")
    write_json(metadata_path, dict(input_stats=inputs, evaluator_hashes=evaluator_hashes, run=run,
                                   ledger_verification=checks, ledger_sha256={name: sha(folder / name) for name in names}))
    return run


def pair(reference, candidate, comparison, interpretation):
    issues = []
    if not reference or not candidate:
        issues.append("missing_pair_member")
    for label, run in (("reference", reference), ("candidate", candidate)):
        if run and not run["attribution_eligible"]:
            issues.append(label + "_ineligible")
    if reference and candidate:
        for key in ("demand_sha256", "parameters_sha256", "nonrule_source_sha256"):
            if reference[key] != candidate[key]:
                issues.append(key + "_mismatch")
        if reference["candidate"] == candidate["candidate"] and reference["source_sha256"] != candidate["source_sha256"]:
            issues.append("same_candidate_source_mismatch")
    identity = candidate or reference
    row = dict(comparison=comparison, interpretation=interpretation, flow=identity["flow_veh_h_lane"],
               seed=identity["seed"], scenario=identity["scenario"], pair_eligible=not issues, rejection_reasons=issues)
    for label, run in (("reference", reference), ("candidate", candidate)):
        for key in ("case_dir", "rules_sha256", "nonrule_source_sha256", "demand_sha256", "parameters_sha256"):
            row[label + "_" + key] = run.get(key) if run else None
    row.update({"delta_" + metric: existing._difference(reference, candidate, metric, not issues) for metric in METRICS})
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profiles", nargs="+", choices=tuple(PROFILES), default=list(PROFILES))
    parser.add_argument("--expected-per-profile", type=int, default=50)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if Path(args.tag).name != args.tag or args.tag in (".", ".."):
        parser.error("tag must be a single directory name")
    manifest = read(args.manifest)
    selected = [r for r in manifest if (r["candidate"], r["mode"]) in [PROFILES[p] for p in args.profiles]]
    counts = {profile: sum((r["candidate"], r["mode"]) == PROFILES[profile] for r in selected) for profile in args.profiles}
    if any(n != args.expected_per_profile for n in counts.values()):
        parser.error("selected profiles are not fully sealed: " + json.dumps(counts))
    output = args.output.resolve() / "reports" / args.tag
    if output.exists():
        parser.error("report is immutable and already exists: " + str(output))
    evaluator_hashes = {name: sha(Path(existing.__file__).with_name(name + ".py"))
                        for name in ("bottleneck_attribution", "native_comparison", "complete_layers")}
    evaluator_hashes["wrapper"] = sha(__file__)
    runs, index = [], {}
    for i, record in enumerate(selected, 1):
        run = case_cache(record, args.output.resolve(), evaluator_hashes)
        key = run["profile"], run["flow_veh_h_lane"], run["seed"], run["scenario"]
        if key in index:
            raise ValueError("duplicate profile/flow/seed/scenario")
        runs.append(run)
        index[key] = run
        if i % 5 == 0:
            print(json.dumps(dict(progress=i, total=len(selected), profile=run["profile"])), flush=True)
    contexts = sorted({(r["flow_veh_h_lane"], r["seed"], r["scenario"]) for r in runs})
    pairs = [pair(index.get((reference, *key)), index.get((candidate, *key)), candidate + "-minus-" + reference, label)
             for candidate, reference, label in COMPARISONS if candidate in args.profiles and reference in args.profiles
             for key in contexts]
    scenarios = [pair(index.get((profile, flow, seed, "straight3")), index.get((profile, flow, seed, "lane_drop")),
                      profile + "_drop-minus-straight", "existing_road_scenario_effect")
                 for profile in args.profiles for flow, seed in sorted({(r["flow_veh_h_lane"], r["seed"]) for r in runs})]
    deltas = ["delta_" + metric for metric in METRICS]
    means = existing._means(pairs, ("comparison", "flow", "scenario"), deltas)
    overall = existing._means(pairs, ("comparison", "scenario"), deltas)
    scenario_means = existing._means(scenarios, ("comparison", "flow"), deltas)
    output.mkdir(parents=True)
    metadata = dict(manifest=str(args.manifest.resolve()), manifest_sha256=sha(args.manifest), profiles=counts,
                    evaluator_hashes=evaluator_hashes, region_m=[800, 1000], physical_lanes=3,
                    region_window_s=list(existing.WINDOW), low_speed_threshold_mps=5.0,
                    flow_definition="first 1000m crossings in inclusive [100,600]s / 500s * 3600; not capacity",
                    delta_definition="candidate minus reference", direct_flag_path_required=True,
                    mean_policy="existing evaluator eligibility; all paired seeds required; five flows equally represented",
                    source_policy="each source snapshot verified by existing load_case; only rule source may differ across candidates")
    write_json(output / "report.json", dict(metadata=metadata, runs=runs, pairs=pairs, paired_means=means,
                                             overall_paired_means=overall, scenario_effects=scenarios,
                                             scenario_effect_means=scenario_means))
    for name, rows in (("per_case", runs), ("paired", pairs), ("paired_means", means),
                       ("overall_paired_means", overall), ("scenario_effects", scenarios), ("scenario_effect_means", scenario_means)):
        write_rows(output / (name + ".csv"), rows)
    write_json(output / "manifest.json", selected)
    print(json.dumps(dict(cases=len(runs), eligible=sum(r["attribution_eligible"] for r in runs),
                          pairs=len(pairs), output=str(output))), flush=True)


if __name__ == "__main__":
    main()
