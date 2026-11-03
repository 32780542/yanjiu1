"""Evaluation-only matching of identical entrant vehicles; never controller input."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean


def load(folder, candidate_label=None):
    result = {}
    for path in folder.glob("*_merges.csv"):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if candidate_label is not None and row["candidate"] != candidate_label:
                    continue
                if row["scenario"] != "lane_drop" or float(row["request_x"]) < 640:
                    continue
                key = float(row["flow"]), int(row["seed"]), row["vehicle_id"]
                assert key not in result, "multiple mandatory completions for entrant"
                result[key] = row
    return result


def run(reference, candidate, output, reference_label=None, candidate_label=None):
    left, right = load(reference, reference_label), load(candidate, candidate_label)
    common = sorted(left.keys() & right.keys())
    summaries = []
    for flow, seed in sorted({key[:2] for key in common}):
        keys = [key for key in common if key[:2] == (flow, seed)]
        for cohort in ("same_entrant", "same_entrant_and_receiver"):
            selected = [k for k in keys if cohort == "same_entrant" or
                        left[k]["target_rear_vehicle"] == right[k]["target_rear_vehicle"] != ""]
            row = dict(flow=flow, seed=seed, cohort=cohort, n=len(selected),
                       vehicles=[key[2] for key in selected])
            for role in ("entrant", "receiver"):
                for window in ("merge", "post0_2", "post2_5", "through_post5"):
                    for metric in ("negative_acceleration_integral_mps", "acceleration_square_integral_m2ps3", "hard_brake_s"):
                        field = role + "_" + window + "_" + metric
                        pairs = [(float(left[k][field]), float(right[k][field])) for k in selected
                                 if left[k].get(field) and right[k].get(field)]
                        if pairs:
                            row[field] = dict(n=len(pairs), reference=mean(a for a, b in pairs),
                                              candidate=mean(b for a, b in pairs), delta=mean(b - a for a, b in pairs))
            summaries.append(row)
    output.mkdir(parents=True, exist_ok=False)
    (output / "matched_post5.json").write_text(json.dumps(dict(reference=str(reference.resolve()),
          candidate=str(candidate.resolve()), limitations="Identity matching is evaluation-only. Timing/position and receiving relationship may differ; same_entrant_and_receiver fixes both observed identities.",
          reference_label=reference_label, candidate_label=candidate_label,
          summaries=summaries), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "compare_post5_matched_source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(matched_events=len(common), output=str(output.resolve()))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-label")
    parser.add_argument("--candidate-label")
    args = parser.parse_args()
    run(args.reference, args.candidate, args.output, args.reference_label, args.candidate_label)
