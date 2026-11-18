"""从两种限速的配对仿真计算行程、出口流率、油耗与编队指标。"""
import argparse
import csv
import json
import os
import xml.etree.ElementTree as ET
from itertools import product
from math import ceil
from pathlib import Path

from summarize_onroad import measure, write_csv

METHODS = ("hdv", "noa", "transform")


def first_merges(run, method, ending_ids):
    if method == "hdv":
        positions = {}
        for e in ET.parse(run / "lanechanges.xml").iter("change"):
            if e.get("from") == "upstream_2" and e.get("to") == "upstream_1":
                positions.setdefault(e.get("id"), float(e.get("pos")))
    else:
        positions = {}
        for t in json.loads((run / "trips.json").read_bytes()):
            for e in t["lane_events"]:
                if e["from_lane"] == 2 and e["to_lane"] == 1:
                    positions[t["vehicle_id"]] = e["x"]
                    break
    if not ending_ids <= positions.keys():
        raise ValueError(f"缺少从终止道出发车辆的并入记录 {run}")
    return sum(positions[k] < 800 for k in ending_ids)


def observations(run, method):
    trips = list(ET.parse(run / ("trips.xml" if method == "hdv" else "sumo_tripinfo.xml")).iter("tripinfo"))
    ending_ids = {t.get("id") for t in trips if t.get("departLane") == "upstream_2"}
    stats = ({"participating_vehicle_seconds": 0, "vehicle_seconds": 0, "episodes": 0, "peak_participants": 0}
             if method == "hdv" else json.loads((run / "result.json").read_bytes())["formation_state"])
    durations = [round(float(t.get("arrival")) * 10) - round(float(t.get("depart")) * 10) for t in trips]
    if any(float(t.get("routeLength")) != 1200 for t in trips):
        raise ValueError(f"行驶距离有误 {run}")
    return dict(durations=durations, waiting_s=sum(float(t.get("waitingTime")) for t in trips),
                fuel_mg=sum(float(t.find("emissions").attrib["fuel_abs"]) for t in trips),
                exits=sum(float(t.get("arrival")) < 600 for t in trips),
                entered=sum(float(t.get("depart")) < 600 for t in trips),
                ending=len(ending_ids), early=first_merges(run, method, ending_ids),
                participant_s=stats["participating_vehicle_seconds"], observed_s=stats["vehicle_seconds"],
                episodes=stats["episodes"], peak_participants=stats["peak_participants"])


def aggregate(records):
    durations = sorted(v for r in records for v in r["durations"])
    count = len(durations)
    def total(key):
        return sum(r[key] for r in records)
    episodes, observed = total("episodes"), total("observed_s")
    return dict(vehicles=count, entered_before_600=total("entered"),
                mean_s=sum(durations) / (10 * count), p95_s=durations[ceil(.95 * count) - 1] / 10,
                exit_veh_h=6 * total("exits") / len(records), wait_s=total("waiting_s") / count,
                fuel_g_km=total("fuel_mg") / (1200 * count),
                ending_vehicles=total("ending"), early_merges=total("early"),
                early_pct=100 * total("early") / total("ending"),
                participation_pct=100 * total("participant_s") / observed if observed else 0.,
                episode_s=total("participant_s") / episodes if episodes else None,
                peak_participants=max(r["peak_participants"] for r in records))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("batch333", "batch288", "output"):
        parser.add_argument(key, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases, summary = [], []
    with open(os.devnull, "w", newline="") as sink:
        for limit, batch in ((33.3, args.batch333), (28.8, args.batch288)):
            for flow in (1500, 1750, 2000):
                groups = {method: [] for method in METHODS}
                inputs = {}
                for seed, method in product(range(311, 316), METHODS):
                    folder = batch / f"{method}_f{flow}_s{seed}"
                    demand, signature, row = measure(folder, method, flow, seed, csv.writer(sink))
                    if (not signature or inputs.setdefault(seed, (signature, demand)) != (signature, demand)
                            or row["road_limit_mps"] != limit
                            or row["idm_tau_s"] != (.85 if method == "hdv" else .2)):
                        raise ValueError(f"配对输入有误 {folder}")
                    result, = folder.glob("*/result.json")
                    obs = observations(result.parent, method)
                    metrics = aggregate([obs])
                    if abs(row["mean_travel_s"] - metrics["mean_s"]) > 1e-8:
                        raise ValueError(f"行程与原始记录不一致 {folder}")
                    cases.append(dict(road_limit=limit, flow=flow, method=method, seed=seed, **metrics))
                    groups[method].append(obs)
                for method, group in groups.items():
                    summary.append(dict(road_limit=limit, flow=flow, method=method, **aggregate(group)))
    write_csv(args.output / "cases.csv", cases)
    write_csv(args.output / "summary.csv", summary)


if __name__ == "__main__":
    main()
