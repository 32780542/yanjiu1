"""Extract compact episode or raw certificate rows from existing immutable native runs."""
import argparse
import csv
import json
from pathlib import Path

from measure import measure


def rows(folder, kind):
    folder = folder.resolve()
    res = json.loads((folder/"result.json").read_bytes())
    if "completed" not in res:
        raise ValueError(f"Run has no final trip counts yet: {folder}")
    meta_path = folder.parent/"row.json"
    meta = json.loads(meta_path.read_bytes()) if meta_path.is_file() else {}
    root = Path(__file__).resolve().parents[3]
    base = dict(batch=folder.parent.parent.name, scenario=res["scenario"], cohort=meta.get("cohort"),
                seed=res["seed"], flow=res["flow_veh_h_lane"], duration_s=res["demand_duration_s"],
                requested=res["requested"], completed=res["completed"], status=res["status"],
                collisions=res["collisions"], teleports=res["teleports"], run_dir=folder.relative_to(root).as_posix())
    if kind == "certificates":
        counts = res.get("transport_certificates")
        if not counts:
            yield dict(**base, reason=None, certificate_log_available=False)
        else:
            for reason, values in counts.items():
                assert sum(values[k] for k in ("zero_gap_ticks", "positive_gap_ticks", "no_alternative_ticks",
                                               "unevaluated_gap_ticks")) == values["matched_ticks"]
                yield dict(**base, reason=reason, certificate_log_available=True, **values)
        return
    data = measure(folder, True)
    for region in ("upstream", "downstream"):
        report = data[region]
        episodes = report["whole_episodes"]
        head = dict(**base, region=region, peak_size=report["peak_size"], same_ids_peak=data["paired_peak"]["size"],
                    episode_count=len(episodes), total_hold_s=report["whole_total_s"],
                    all_present_s=report["all_present_total_s"], formed_pct_while_all_present=report["formed_pct_while_all_present"])
        if not episodes:
            yield head
        for i, ep in enumerate(episodes, 1):
            movement = ep["moves_to_first_settled_s"]
            within = ep["moves_while_settled_endpoints"]
            row = dict(**head, episode=i, start_s=ep["start_s"], end_s=ep["end_s"], hold_s=ep["hold_s"],
                       counts="/".join(map(str, ep["lane_counts"])), first_settled_s=ep["first_settled_s"],
                       last_settled_s=ep["last_settled_s"])
            if movement:
                row.update(from_counts="/".join(map(str, movement["start_counts"])),
                           start_latest_s=movement["start_time_range_s"][1],
                           fixed_target_min=movement["min_total_crossings"],
                           fixed_target_min_max=movement["min_max_crossings"],
                           free_tail_min=movement["free_balanced_tail"]["min_total_crossings"],
                           free_tail_min_max=movement["free_balanced_tail"]["min_max_crossings"],
                           outer_first_min=movement["three_lane_outer_first"]["min_total_crossings"],
                           outer_first_min_max=movement["three_lane_outer_first"]["min_max_crossings"],
                           actual=movement["midpoint"]["total"], actual_max=movement["midpoint"]["max_per_car"],
                           finished=movement["completed"]["total"], finished_chain_ok=not movement["completed"]["mismatch_ids"])
            if within:
                row["crossings_within_settled_span"] = within["midpoint"]["total"]
            yield row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("episodes", "certificates"))
    parser.add_argument("folders", type=Path, nargs="+")
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    data = [row for folder in args.folders for row in rows(folder, args.kind)]
    with args.csv.open("x", encoding="utf-8", newline="") as stream:
        out = csv.DictWriter(stream, list(dict.fromkeys(key for row in data for key in row)))
        out.writeheader()
        out.writerows(data)
    print(args.csv, len(data))
