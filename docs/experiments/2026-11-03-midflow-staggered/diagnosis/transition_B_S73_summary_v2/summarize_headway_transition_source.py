"""Summarize all crossings and fixed persistent-front cohorts without imputation."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median


def run(inputs, output):
    cases = []
    for folder in inputs:
        for meta_path in folder.glob("*_provenance.json"):
            name = meta_path.name.removesuffix("_provenance.json")
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            profiles = list(csv.DictReader((folder / (name + "_profile20m.csv")).open(encoding="utf-8-sig")))
            events = list(csv.DictReader((folder / (name + "_gate640_followers.csv")).open(encoding="utf-8-sig")))
            case = dict(metadata=metadata, profile_all_lanes=[r for r in profiles if r["lane"] == "-1"], cohorts=[])
            for lane in ("all", "0", "1", "2"):
                selected = [e for e in events if lane == "all" or e["anchor_lane"] == lane]
                by_car = {}
                for e in selected:
                    by_car.setdefault(e["vehicle_id"], []).append(e)
                persistent = {key for key, rows in by_car.items() if len(rows) == 5 and all(e["same_front"] == "True" and e.get("continuous_same_front", "True") == "True" for e in rows)}
                group = dict(anchor_lane=lane, crossing_n=len(by_car), persistent_front_n=len(persistent), samples=[])
                for relative in (0, .5, 1, 2, 5):
                    rows = [e for e in selected if float(e["relative_s"]) == relative]
                    fixed = [e for e in rows if e["vehicle_id"] in persistent]
                    gaps = [float(e["current_gap_m"]) for e in rows if e["current_gap_m"]]
                    fixed_gaps = [float(e["current_gap_m"]) for e in fixed]
                    group["samples"].append(dict(relative_s=relative, observed_front_n=len(gaps),
                         same_front_at_sample_n=sum(e["same_front"] == "True" for e in rows),
                         all_current_gap_p50_m=median(gaps) if gaps else None,
                         persistent_gap_p50_m=median(fixed_gaps) if fixed_gaps else None,
                         persistent_gap_mean_m=mean(fixed_gaps) if fixed_gaps else None,
                         all_speed_mean_mps=mean(float(e["speed"]) for e in rows) if rows else None))
                case["cohorts"].append(group)
            case["continuous_front_monitor_available"] = bool(events and "continuous_same_front" in events[0])
            cases.append(case)
    output.mkdir(parents=True, exist_ok=False)
    (output / "transition_summary.json").write_text(json.dumps(dict(inputs=[str(p.resolve()) for p in inputs],
          limitations="All-current-front profiles keep front changes. Persistent cohort uses every 0.1s front monitor when available, otherwise only the five saved samples; report availability and cohort size, never substitute it for all traffic.", cases=cases), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "summarize_headway_transition_source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(cases=len(cases), output=str(output.resolve()))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
