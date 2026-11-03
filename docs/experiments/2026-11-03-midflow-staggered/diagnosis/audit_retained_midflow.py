"""Read-only reconstruction of retained final61 midflow evidence; never runs SUMO.

Original trips contain lane-index midpoint and strict completion events, but no
request position. Request position is reported only when a retained gate sample
has the exact request timestamp; otherwise it remains null.
"""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[4]
PAIRS = ROOT / "docs/experiments/2026-11-03-staggered-bottleneck/final61_S160/paired_seeds.csv"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stats(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0}
    def quantile(q):
        x = (len(values) - 1) * q
        i = int(x)
        return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (x - i)
    return dict(n=len(values), mean=mean(values), min=values[0], p05=quantile(.05),
                p50=quantile(.5), p95=quantile(.95), max=values[-1])


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    with PAIRS.open(encoding="utf-8-sig", newline="") as stream:
        pairs = [r for r in csv.DictReader(stream) if float(r["flow"]) in (1500, 2000)]
    events, cases, cohorts, sources = [], [], [], []
    for pair in pairs:
        for key, label in (("reference_case_dir", "NOA"), ("candidate_case_dir", "S")):
            folder = Path(pair[key])
            evidence = folder.parent / "evidence"
            seal = read(evidence / "seal.json")
            ledger = evidence / seal["traffic_metadata"]
            meta = read(ledger)
            # Verify selected source bytes against immutable sealing metadata.
            for file in (ledger, ledger.with_name("vehicles.json.gz"), ledger.with_name("gate_brackets.jsonl.gz"),
                         ledger.with_name("region_steps.jsonl.gz")):
                assert sha(file) == seal["files"][file.relative_to(evidence).as_posix()]
            result = read(folder / "result.json")
            trips = read(folder / "trips.json")
            with gzip.open(ledger.with_name("vehicles.json.gz"), "rt", encoding="utf-8") as stream:
                vehicles = json.load(stream)
            by_id = {v["vehicle_id"]: v for v in vehicles}
            gate_points = defaultdict(dict)
            with gzip.open(ledger.with_name("gate_brackets.jsonl.gz"), "rt", encoding="utf-8") as stream:
                next(stream)
                for line in stream:
                    i, gate, t0, x0, t1, x1 = json.loads(line)
                    gate_points[vehicles[i]["vehicle_id"]][round(t0, 7)] = x0
                    gate_points[vehicles[i]["vehicle_id"]][round(t1, 7)] = x1
            ident = dict(method=label, flow=int(float(pair["flow"])), seed=int(pair["seed"]),
                         scenario=pair["scenario"])
            sources.append(dict(**ident, case_dir=str(folder), rules_sha256=result["source_sha256"]["noa/native_rules.py"],
                                trips_sha256=sha(folder / "trips.json"), seal_sha256=sha(evidence / "seal.json"),
                                positions_present=(folder / "positions.jsonl.gz").is_file()))
            row = dict(**ident, requested=result["requested"], safe=result["safe"], all_completed=result["all_completed"],
                       mean_system_s=result["mean_system_time_s"], mean_travel_s=result["mean_travel_time_s"],
                       mean_entry_wait_s=result["mean_entry_wait_s"], lane_changes=result["lane_changes"],
                       ending_seen=result["ending_lane_observed_vehicles"],
                       ending_completed_before_drop=result["ending_lane_completed_before_drop"],
                       mean_fuel_g_km=result["fuel_g_per_km"])
            row.update({k: v for k, v in meta["run"].items() if k.startswith("mean_segment_") or
                        k in ("region_mean_speed_mps", "region_low_speed_vehicle_s", "region_density_veh_km_lane")})
            cases.append(row)
            for lane in range(3):
                selected = [t for t in trips if t["lane"] == lane]
                cohort = dict(**ident, initial_lane=lane, n=len(selected),
                              system_s=mean(t["exited_s"] - t["requested_s"] for t in selected),
                              waiting_s=mean(t.get("waiting_s", 0) for t in selected))
                for a, b in ((100, 600), (600, 640), (640, 800), (800, 1000), (1000, 1100)):
                    seconds = [by_id[t["vehicle_id"]]["gates"][str(b)]["time_s"] -
                               by_id[t["vehicle_id"]]["gates"][str(a)]["time_s"] for t in selected]
                    cohort[f"mean_{a}_{b}_s"] = mean(seconds)
                    cohort[f"excess_{a}_{b}_over_28p8_s"] = mean(seconds) - (b - a) / 28.8
                cohorts.append(cohort)
            for trip in trips:
                for completion in trip["lane_completion_events"]:
                    if (completion["from_lane"], completion["to_lane"]) != (2, 1):
                        continue
                    request = completion["requested_s"]
                    midpoint = next((e for e in trip["lane_events"] if e["from_lane"] == 2 and e["to_lane"] == 1
                                     and request - 1e-7 <= e["time_s"] <= completion["time_s"] + 1e-7), None)
                    gate640 = by_id[trip["vehicle_id"]]["gates"]["640"]["time_s"]
                    events.append(dict(**ident, vehicle_id=trip["vehicle_id"], initial_lane=trip["lane"],
                                       request_s=request, request_x_exact=gate_points[trip["vehicle_id"]].get(round(request, 7)),
                                       request_minus_gate640_s=request - gate640,
                                       mandatory_window_request=request >= gate640 - .000001,
                                       midpoint_s=midpoint["time_s"] if midpoint else None,
                                       midpoint_x=midpoint["x"] if midpoint else None,
                                       complete_s=completion["time_s"], complete_x=completion["x"],
                                       request_to_complete_s=completion["time_s"] - request))
    summaries = []
    for flow in (1500, 2000):
        for method in ("NOA", "S"):
            group = [e for e in events if e["flow"] == flow and e["method"] == method and e["scenario"] == "lane_drop"]
            mandatory = [e for e in group if e["mandatory_window_request"]]
            entry = dict(flow=flow, method=method, all_2_to_1_events=len(group), mandatory_window_events=len(mandatory),
                         pre640_requests=len(group) - len(mandatory))
            entry["all_events"] = {key: stats(e[key] for e in group) for key in
                                   ("midpoint_x", "complete_x", "request_minus_gate640_s", "request_to_complete_s")}
            entry["mandatory_window"] = {key: stats(e[key] for e in mandatory) for key in
                                         ("midpoint_x", "complete_x", "request_minus_gate640_s", "request_to_complete_s", "request_x_exact")}
            for name, selected in (("all_events", group), ("mandatory", mandatory)):
                entry[name + "_completion_bins"] = {f"{lo}_{hi}": sum(lo <= e["complete_x"] < hi for e in selected)
                                                     for lo, hi in ((0, 640), (640, 700), (700, 800), (800, 900),
                                                                    (900, 980), (980, 1000), (1000, 1201))}
            summaries.append(entry)
    report = dict(scope="Retained final61 seeds61-65, 1500/2000, both roads and modes; no simulations",
                  limitations=["No complete trajectories remain in selected old cases: acceleration, actual lateral start and local headway cannot be reconstructed.",
                               "Midpoint is lane index flip; strict completion is at lane center with measured lateral rest.",
                               "requested_s is most recent native changeLane submission, not necessarily first successful lateral motion.",
                               "request_x_exact is populated only when a saved gate-bracket sample has the identical timestamp.",
                               "mandatory_window_request means request after own first640 crossing; earlier voluntary 2-to-1 events are kept separately."],
                  paired_table_sha256=sha(PAIRS), events=summaries, sources=sources)
    (output / "retained_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(output / "retained_cases.csv", cases)
    write_csv(output / "retained_merge_events.csv", events)
    write_csv(output / "retained_initial_lane_cohorts.csv", cohorts)
    print(json.dumps(dict(output=str(output), cases=len(cases), events=len(events), summaries=summaries), ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
