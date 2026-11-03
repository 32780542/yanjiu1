"""Summarize extracted raw diagnostics, keeping seed/window identities explicit."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean


def write(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def percentile(values, q):
    values.sort()
    if not values:
        return None
    x = (len(values) - 1) * q
    i = int(x)
    return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (x - i)


def run(inputs, output):
    regions, merges, provenances = [], [], []
    for source in inputs:
        for path in source.glob("*_provenance.json"):
            provenances.append(json.loads(path.read_text(encoding="utf-8")))
        for path in source.glob("*_regions.csv"):
            with path.open(encoding="utf-8-sig", newline="") as stream:
                regions.extend(r for r in csv.DictReader(stream) if r["group_type"] == "all")
        for path in source.glob("*_merges.csv"):
            with path.open(encoding="utf-8-sig", newline="") as stream:
                merges.extend(csv.DictReader(stream))
    windows = {tuple(p.get("window_s", (100, 600))) for p in provenances}
    assert len(windows) == 1, "cannot mix diagnostic time windows"
    identities = [(p["candidate"], p["mode"], p["flow"], p["seed"], p["scenario"]) for p in provenances]
    assert len(set(identities)) == len(identities), "duplicate case inputs"
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for p in provenances:
        identity = {k: p[k] for k in ("candidate", "mode", "flow", "seed", "scenario")}
        def matches(r):
            return all(str(r[k]) == str(v) for k, v in identity.items())
        selected = [r for r in regions if matches(r)]
        events = [r for r in merges if matches(r) and r["scenario"] == "lane_drop" and float(r["request_x"]) >= 640]
        row = dict(identity, mandatory_event_n=len(events))
        for field in ("request_x", "lateral_start_x", "complete_x", "target_rear_gap_at_request_m",
                      "target_rear_cth_residual_at_request_m", "target_rear_min_acceleration_through_complete_plus2"):
            values = [float(e[field]) for e in events if e[field]]
            row[field + "_p50"] = percentile(values, .5)
            row[field + "_p95"] = percentile(values, .95)
        rear = [float(e["target_rear_min_acceleration_through_complete_plus2"]) for e in events
                if e["target_rear_min_acceleration_through_complete_plus2"]]
        row["observed_target_rear_n"] = len(rear)
        row["rear_hard_brake_events_n"] = sum(a <= -6 for a in rear)
        row["rear_hard_brake_event_fraction"] = sum(a <= -6 for a in rear) / len(rear) if rear else None
        for lo, hi in ((640, 700), (700, 800), (640, 800), (800, 1000), (1000, 1100)):
            included = [r for r in selected if lo <= float(r["region"].split("_")[0]) < hi]
            for field in ("vehicle_s", "speed_integral_m", "positive_speed_deficit_s",
                          "strong_brake_vehicle_s_a_le_minus3", "hard_brake_vehicle_s_a_le_minus6"):
                row[f"region_{lo}_{hi}_{field}"] = sum(float(r[field]) for r in included)
            exposure = row[f"region_{lo}_{hi}_vehicle_s"]
            row[f"region_{lo}_{hi}_mean_speed_mps"] = row[f"region_{lo}_{hi}_speed_integral_m"] / exposure if exposure else None
        cases.append(row)
    write(output / "per_case.csv", cases)
    groups = sorted({(r["candidate"], r["mode"], r["flow"], r["scenario"]) for r in cases})
    averages = []
    for candidate, mode, flow, scenario in groups:
        group = [r for r in cases if (r["candidate"], r["mode"], r["flow"], r["scenario"]) == (candidate, mode, flow, scenario)]
        row = dict(candidate=candidate, mode=mode, flow=flow, scenario=scenario, seed_n=len(group))
        row.update({k: mean(r[k] for r in group) for k in group[0] if k not in
                    ("candidate", "mode", "flow", "scenario", "seed") and all(r[k] is not None for r in group)})
        averages.append(row)
    write(output / "seed_equal_means.csv", averages)
    (output / "source_windows.json").write_text(json.dumps(dict(inputs=[str(p.resolve()) for p in inputs],
          window_s=list(next(iter(windows))), summary_policy="Case-specific event quantiles; seed-equal means of case summaries, never pooled event quantiles.",
          cases=provenances), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "summarize_raw_midflow_source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(cases=len(cases), output=str(output.resolve()))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
