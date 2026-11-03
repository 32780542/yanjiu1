"""Summarize frozen D1 diagnostics; no simulation or controller feedback."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
USED = set()


def rows(path):
    USED.add(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read(path):
    USED.add(path)
    return json.loads(path.read_text(encoding="utf-8"))


def grouped_mean(items, keys, fields):
    groups = defaultdict(list)
    for item in items:
        groups[tuple(item[k] for k in keys)].append(item)
    answer = []
    for key, group in sorted(groups.items()):
        out = dict(zip(keys, key), cases_n=len(group))
        out.update({f: mean(float(x[f]) for x in group) for f in fields if all(x.get(f) not in (None, "") for x in group)})
        answer.append(out)
    return answer


def comparison(directory, reference, candidate):
    data = rows(ROOT / directory / "per_case.csv")
    key = lambda r: (r["flow"], r["seed"], r["scenario"])
    ref = {key(r): r for r in data if r["candidate"] == reference and r["mode"] == "transform"}
    cand = {key(r): r for r in data if r["candidate"] == candidate and r["mode"] == "transform"}
    fields = ["request_x_p50", "lateral_start_x_p50", "complete_x_p50", "target_rear_gap_at_request_m_p50",
              "region_100_600_positive_speed_deficit_s", "region_640_800_positive_speed_deficit_s",
              "region_800_1000_positive_speed_deficit_s", "region_100_1100_positive_speed_deficit_s",
              "region_600_800_hard_brake_vehicle_s_a_le_minus6", "region_100_1100_hard_brake_vehicle_s_a_le_minus6"]
    paired = []
    for k in sorted(ref.keys() & cand.keys()):
        item = dict(flow=k[0], seed=k[1], scenario=k[2])
        for f in fields:
            if ref[k].get(f) and cand[k].get(f):
                a, b = float(ref[k][f]), float(cand[k][f])
                item.update({f + "_reference": a, f + "_candidate": b, f + "_delta": b-a})
        paired.append(item)
    result = grouped_mean(paired, ("flow", "scenario"), [f+suffix for f in fields for suffix in ("_reference", "_candidate", "_delta")])
    return dict(reference=reference, candidate=candidate, pairs_n=len(paired), seed_equal_flow_means=result, per_pair=paired)


def scores(directory, expected):
    cases, samples = [], []
    for path in sorted((ROOT / directory).glob("*_provenance.json")):
        info = read(path)
        prefix = path.name.removesuffix("_provenance.json")
        events = rows(path.parent / (prefix + "_completed_submission_scores.csv"))
        winners = rows(path.parent / (prefix + "_sampled_fresh_winners.csv"))
        assert all(float(x["winner_phi_delta"]) < 0 for x in winners)
        early = [r for r in events if r["from_lane"] == "1" and r["to_lane"] == "0" and float(r["x"]) < 640]
        scopes = rows(path.parent / (prefix + "_sampled_scope_counts.csv"))
        item = {k: info[k] for k in ("candidate", "flow", "seed", "scenario")}
        item.update(pure_winner_equivalence_checks=info["pure_winner_equivalence_checks"],
                    same_frame_fresh_binding_checks=info["same_frame_fresh_binding_checks"],
                    all_completed_submissions_n=len(events), early_1_to_0_submissions_n=len(early),
                    early_1_to_0_receiving_argument_n=sum(x["future_argument"] == "True" for x in early),
                    early_1_to_0_fresh_winner_matches_n=sum(x["latest_submission_matches_fresh_winner"] == "True" for x in early),
                    sampled_own_winners_n=len(winners),
                    sampled_winner_phi_delta_min=min((float(x["winner_phi_delta"]) for x in winners), default=None),
                    sampled_winner_phi_delta_max=max((float(x["winner_phi_delta"]) for x in winners), default=None))
        cases.append(item)
        samples.extend(scopes)
    assert len(cases) == expected
    fields = [k for k in cases[0] if k.endswith("_n") or k.endswith("_checks")]
    return dict(cases_n=len(cases), total_equivalence_checks=sum(x["pure_winner_equivalence_checks"] for x in cases),
                total_binding_checks=sum(x["same_frame_fresh_binding_checks"] for x in cases),
                per_case=cases, seed_equal_flow_means=grouped_mean(cases, ("candidate", "flow", "scenario"), fields),
                fixed_1s_scope_samples=samples,
                limitations=["receiving_argument is the actual _fill argument; DR deliberately ignores future mapping even when this argument is true.",
                "Fresh queries use empty own Memory for interface verification, not reconstructed private first intentions.",
                "Latest completed submissions include held-intent retries; local single-car potential descent does not prove monotone global simultaneous descent."])


def all_lc(directory, original, expected):
    answer, max_difference, check_n = [], 0.0, 0
    for path in sorted((ROOT / directory).glob("*_merges.csv")):
        data = rows(path)
        old = rows(ROOT / original / path.name)
        indexed = {(r["vehicle_id"], r["request_s"]): r for r in data if r["from_lane"] == "2" and r["to_lane"] == "1"}
        assert len(indexed) == len(old)
        for r in old:
            current = indexed[(r["vehicle_id"], r["request_s"])]
            for field, value in r.items():
                if value == "" or field in ("candidate", "mode", "scenario", "vehicle_id", "target_rear_vehicle"):
                    assert current[field] == value
                    continue
                difference = abs(float(value) - float(current[field]))
                max_difference = max(max_difference, difference)
                check_n += 1
                assert difference < 1e-8, (path.name, field, difference)
        early = [r for r in data if r["from_lane"] == "1" and r["to_lane"] == "0" and float(r["request_x"]) < 640]
        item = {k: data[0][k] for k in ("candidate", "flow", "seed", "scenario", "mode")}
        item.update(all_completed_transitions_n=len(data), early_1_to_0_submissions_n=len(early),
                    early_1_to_0_actual_start_before640_n=sum(float(r["lateral_start_x"]) < 640 for r in early),
                    early_1_to_0_strict_completion_before640_n=sum(float(r["complete_x"]) < 640 for r in early))
        for role in ("entrant", "receiver"):
            for window in ("merge", "post0_2", "post2_5", "through_post5"):
                for metric in ("hard_brake_s", "acceleration_square_integral_m2ps3", "negative_acceleration_integral_mps"):
                    field = role + "_" + window + "_" + metric
                    valid = [float(r[field]) for r in early if r.get(field)]
                    if valid:
                        item[field + "_mean"] = mean(valid)
        answer.append(item)
    assert len(answer) == expected
    fields = [k for k in answer[0] if k.endswith("_n") or k.endswith("_mean")]
    return dict(cases_n=len(answer), exact_2to1_regression_scalar_checks=check_n,
                exact_2to1_regression_max_absolute_error=max_difference, per_case=answer,
                seed_equal_flow_means=grouped_mean(answer, ("candidate", "flow", "scenario"), fields))


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        metric_notes=["Positive speed deficit integrates max(0,1-v/28.8) and excludes overspeed credits; it is not net system time.",
        "Regional exposure counts each vehicle-frame once. Receiver event windows can overlap and are never summed as network exposure.",
        "Event post5 covers full requests, independently of the regional [30,180) or [100,600) windows.",
        "Short S matching uses seed73 only; development new S post5 matching uses seed71/drop only because older raw was pruned.",
        "Flow means average per-case values equally; event quantiles are per case then averaged, not pooled."])
    report["short_D1_vs_S73"] = comparison("D1_S73_short_summary_v1", "S", "D")
    report["development_D1_vs_S"] = comparison("D1_development_baseline36_summary_v1", "S", "D")
    report["short_DR_vs_D1"] = comparison("D1_DRDP_short18_summary_v1", "D", "DR")
    report["short_DP_vs_D1"] = comparison("D1_DRDP_short18_summary_v1", "D", "DP")
    report["short_D1_fill"] = scores("D1_fill_scores_v1", 6)
    report["short_DRDP_fill"] = scores("DRDP_fill_scores_v1", 12)
    report["development_D1_fill"] = scores("D1_development12_fill_scores_v1", 12)
    report["short_D1_all_LC"] = all_lc("raw_D1screen6_allLC_post5_v1", "raw_D1screen6_post5_v1", 6)
    report["development_D1_all_LC"] = all_lc("raw_D1development12_allLC_post5_v1", "raw_D1development12_post5_v1", 12)
    for label in ("D1_post5_matched73_v1", "D1_development_post5_matched71_v1", "DR_D1_post5_matched_v1", "DP_D1_post5_matched_v1"):
        report[label] = read(ROOT / label / "matched_post5.json")
    geometry = [r for path in (ROOT / "D1_DRDP_S73_phase_geometry_v1").glob("*_phase_pairs.csv") for r in rows(path)]
    report["short_local_geometry_seed_equal_case_summaries"] = grouped_mean(geometry,
         ("candidate", "flow", "scenario", "region", "lanes"),
         ("sampled_mutual_pairs_n", "abs_phase_error_p50_m", "abs_phase_error_p95_m", "fraction_error_le2m"))
    (output / "mechanism.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "summarize_D1_mechanism_source.py").write_bytes(Path(__file__).read_bytes())
    provenance = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(USED)}
    (output / "source_sha256.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output.resolve()), input_files=len(provenance),
         total_fill_queries=sum(report[k]["total_equivalence_checks"] for k in ("short_D1_fill", "short_DRDP_fill", "development_D1_fill")))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
