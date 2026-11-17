"""Compare shared IDM type transfers with source-identical native controls."""

import argparse
import csv
import hashlib
import json
from math import isclose
from pathlib import Path
from statistics import mean
import sys


ROOT = next(path for path in Path(__file__).resolve().parents if (path / "scripts/run_logged.py").is_file())
HISTORICAL = ROOT / "docs/experiments/2026-11-04-timegap-staggered"
sys.path.insert(0, str(ROOT / "variants/phase5g_pure_formation"))
sys.path.insert(0, str(HISTORICAL / "tools"))
from experiments.bottleneck_attribution import evaluate_case
from report_trial import read_report_rows, stop_and_merge


METRICS = (
    "mean_system_time_s", "mean_entry_wait_s", "mean_travel_time_s",
    "mean_segment_100_600_s", "mean_segment_800_1100_s", "flow_1000m_veh_h",
    "region_mean_speed_mps", "region_low_speed_vehicle_s", "stop_sample_vehicle_s",
    "fuel_g_per_km", "lane_change_completions", "merge_2to1_mean_x_m",
    "merge_2to1_completions", "merge_2to1_before_900", "merge_1to0_completions",
    "merge_0to1_completions", "merge_1to2_completions", "ending_lane_completion_before_drop_rate",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_case(run, old_record=None):
    result = read_json(run / "result.json")
    case = read_json(run / "input.json")
    metrics = {key: result.get(key) for key in METRICS}
    events = result["lane_completion_events"]
    metrics["merge_2to1_before_900"] = sum((e["from_lane"], e["to_lane"]) == (2, 1) and e["x"] < 900
                                         for e in events)
    for a, b in ((1, 0), (0, 1), (1, 2)):
        metrics[f"merge_{a}to{b}_completions"] = sum((e["from_lane"], e["to_lane"]) == (a, b) for e in events)
    if old_record:
        assert all(isclose(metrics[key], old_record[key], rel_tol=0, abs_tol=1e-12) for key in (
            "mean_system_time_s", "mean_entry_wait_s", "mean_travel_time_s", "fuel_g_per_km"))
        assert metrics["lane_change_completions"] == old_record["lane_change_completions"]
        assert old_record["attribution_eligible"] is True and old_record["evidence_verified"] is True
        assert (digest(run / "input.json"), digest(run / "result.json")) == (
            old_record["input_sha256"], old_record["result_sha256"])
        metrics.update({key: old_record[key] for key in METRICS if key in old_record})
    elif result["safe"] and result["all_completed"]:
        audit = evaluate_case(run)
        assert audit["attribution_eligible"], audit["audit_issues"]
        measured = {**audit, **stop_and_merge(run)}
        metrics.update({key: measured[key] for key in METRICS if key in measured})
    return case, result, metrics


def diff(a, b):
    return {key: (a[key] - b[key] if a[key] is not None and b[key] is not None else None) for key in METRICS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    history = {(row["flow"], row["seed"], row["mode"]): row
               for row in read_report_rows(HISTORICAL / "data/formal600_main/per_case.csv")
               if row["candidate"] == "C12_200" and row["scenario"] == "lane_drop"}
    controls = {}
    per_case = []
    for batch in args.batch:
        protocol = read_json(batch / "protocol.json")
        control_hashes = protocol["hashes"]["control"]
        baseline_folder = ROOT / "tmp/staggered_bottleneck/20261104_formal600_main_drop_211_215_r01/sources/C12_200"
        assert all(digest(baseline_folder / name) == sha for name, sha in control_hashes.items())
        for row in read_json(batch / "manifest.json"):
            assert row["verified"], row
            key = row["flow"], row["seed"], row["mode"]
            if key not in controls:
                old = history[key]
                old_run = Path(old["run_dir"])
                case, result, metrics = extract_case(old_run, old)
                controls[key] = case, result
                per_case.append(dict(profile="control", flow=key[0], seed=key[1], mode=key[2],
                                     run=str(old_run), **summary(result), **metrics))
            case, result, metrics = extract_case(Path(row["run"]))
            old_case, old_result = controls[key]
            assert result["sumo_version"] == old_result["sumo_version"]
            assert {k: case[k] for k in case if k not in ("case", "physical", "source_sha256")} == {
                k: old_case[k] for k in old_case if k not in ("case", "physical", "source_sha256")}
            assert case["case"] == old_case["case"]
            different = {k for k in case["physical"] if case["physical"][k] != old_case["physical"][k]}
            assert different == {"transfer": {"minGap", "tau", "accel"}, "tau_only": {"tau"}}[row["profile"]]
            assert {k for k, v in case["source_sha256"].items() if v != old_case["source_sha256"][k]} == {
                "experiments/native_sumo.py"}
            per_case.append(dict(profile=row["profile"], flow=key[0], seed=key[1], mode=key[2],
                                 run=row["run"], **summary(result), **metrics))
            print(row["profile"], *key, result["status"], flush=True)
    cases = {(r["profile"], r["flow"], r["seed"], r["mode"]): r for r in per_case}
    pairs = []
    for profile, flow, seed in sorted({key[:3] for key in cases}):
        noa, transform = (cases.get((profile, flow, seed, mode)) for mode in ("noa", "transform"))
        if noa and transform:
            pairs.append(dict(profile=profile, flow=flow, seed=seed, noa=summary(noa),
                              transform=summary(transform), transform_minus_noa=diff(transform, noa)))
    pair_map = {(p["profile"], p["flow"], p["seed"]): p["transform_minus_noa"] for p in pairs}
    changes = []
    for p in pairs:
        profile, flow, seed = (p[k] for k in ("profile", "flow", "seed"))
        if profile != "control":
            changes.append(dict(profile=profile, flow=flow, seed=seed,
                                change_in_transform_minus_noa=diff(p["transform_minus_noa"],
                                                                  pair_map["control", flow, seed])))
    means = []
    for profile, flow in sorted({(p["profile"], p["flow"]) for p in pairs}):
        group = [p["transform_minus_noa"] for p in pairs if (p["profile"], p["flow"]) == (profile, flow)]
        means.append(dict(profile=profile, flow=flow, pairs=len(group),
                          transform_minus_noa={key: mean(p[key] for p in group)
                                               if all(p[key] is not None for p in group) else None for key in METRICS}))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(cases=sorted(per_case, key=lambda p: (p["profile"], p["flow"],
                                                                           p["seed"], p["mode"])),
                                       pairs=pairs, means=means, effect_modification=changes),
                                   indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with args.out.with_name(args.out.stem + "_cases.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(per_case[0]))
        writer.writeheader()
        writer.writerows(per_case)


def summary(result):
    return {key: result[key] for key in ("status", "safe", "all_completed", "requested", "completed", "collisions", "teleports")}


if __name__ == "__main__":
    main()
