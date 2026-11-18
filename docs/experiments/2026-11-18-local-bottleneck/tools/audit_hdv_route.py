"""在同一道路上分别改变下游路线的可用时刻和 IDM 时距，观察原生换道。"""

import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path

VARIANT = Path(__file__).resolve().parents[4] / "variants/phase5g_pure_formation"
sys.path.insert(0, str(VARIANT))
from experiments.native_sumo import STEP, arrival_tape, build_network, write_routes
from research.common import binary, lock_traci
from run_cai_hdv import set_cai_lane_model


def run_case(case):
    base, flow, seed, visibility, tau, duration, limit, advice_weight = case
    local = visibility == "200m"
    folder = base / f"f{flow}_s{seed}_{visibility}_tau{tau}"
    folder.mkdir()
    net = build_network(folder, road_limit=limit)
    demand = arrival_tape(seed, flow, duration)
    routes = write_routes(folder, demand)
    route_tree = ET.parse(routes)
    route_tree.find("vType").set("tau", str(tau))
    if local:
        route_tree.find("route").set("edges", "upstream")
    route_tree.write(routes, encoding="utf-8", xml_declaration=True)
    trips, changes, log = (folder / name for name in ("trips.xml", "changes.xml", "sumo.log"))
    traci = lock_traci()
    tc = traci.constants
    traci.start([binary("sumo"), "-n", str(net), "-r", str(routes), "--step-length", str(STEP),
                 "--lanechange.duration", "1", "--time-to-teleport", "-1", "--seed", str(seed),
                 "--route-steps", "0", "--collision.action", "warn", "--collision.mingap-factor", "0",
                 "--collision.check-junctions", "true", "--no-step-log", "true",
                 "--duration-log.disable", "true", "--device.emissions.probability", "1",
                 "--tripinfo-output", str(trips), "--lanechange-output", str(changes),
                 "--error-log", str(log)])
    teleports = releases = 0
    probe = {}
    try:
        traci.simulation.subscribe((tc.VAR_DEPARTED_VEHICLES_IDS, tc.VAR_MIN_EXPECTED_VEHICLES,
                                    tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER))
        for _ in range(round(1800 / STEP)):
            traci.simulationStep()
            state = traci.simulation.getSubscriptionResults()
            for car in state[tc.VAR_DEPARTED_VEHICLES_IDS]:
                traci.vehicle.setSpeedMode(car, 31)
                traci.vehicle.setLaneChangeMode(car, 1621)
                set_cai_lane_model(traci.vehicle, car)
                if advice_weight != .5:
                    traci.vehicle.setParameter(car, "laneChangeModel.lcCooperativeSpeed", str(advice_weight))
                if local:
                    traci.vehicle.subscribe(car, (tc.VAR_LANEPOSITION,))
                if not probe and traci.vehicle.getLaneIndex(car) == 2:
                    probe.update(car=car, x=traci.vehicle.getLanePosition(car),
                                 entry=traci.vehicle.getBestLanes(car))
            if local:
                for car, record in traci.vehicle.getAllSubscriptionResults().items():
                    x = record[tc.VAR_LANEPOSITION]
                    if x >= 800:
                        traci.vehicle.setRoute(car, ("upstream", "downstream"))
                        traci.vehicle.unsubscribe(car)
                        releases += 1
                        if car == probe.get("car"):
                            probe.update(release_x=x, after=traci.vehicle.getBestLanes(car))
            teleports += state[tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER]
            if state[tc.VAR_MIN_EXPECTED_VEHICLES] == 0:
                break
    finally:
        traci.close()

    vehicles = {t.get("id"): t for t in ET.parse(trips).iter("tripinfo")}
    collisions = sum("collision" in s.lower() or "collid" in s.lower()
                     for s in log.read_text(encoding="utf-8").splitlines())
    correct_path = all(t.get("arrivalLane").startswith("downstream_")
                       and float(t.get("routeLength")) == 1200 and not t.get("vaporized")
                       for t in vehicles.values())
    if (set(vehicles) != {v["vehicle_id"] for v in demand} or not correct_path
            or teleports or collisions or local and releases != len(vehicles)):
        raise ValueError(f"核对行程失败 {folder}: {len(vehicles)=} {releases=} {collisions=} {teleports=}")

    ending = {v for v, t in vehicles.items() if t.get("departLane") == "upstream_2"}
    first = {}
    for e in ET.parse(changes).iter("change"):
        if e.get("id") in ending and e.get("from") == "upstream_2" and e.get("to") == "upstream_1":
            first.setdefault(e.get("id"), (float(e.get("pos")), e.get("reason").split("|")[0]))
    if set(first) != ending:
        raise ValueError(f"终止道首次并入记录不齐 {folder}")
    early = Counter(reason for x, reason in first.values() if x < 800)
    total_ticks = sum(round(float(t.get("arrival")) * 10) - round(float(t.get("depart")) * 10)
                      for t in vehicles.values())
    (folder / "route_probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    return dict(flow=flow, seed=seed, visibility=visibility, tau_s=tau, road_limit=limit,
                advice_weight=advice_weight,
                vehicles=len(vehicles), total_travel_s=total_ticks / 10,
                mean_travel_s=total_ticks / (10 * len(vehicles)), ending=len(ending),
                before_800=sum(early.values()), strategic_before_800=early["strategic"],
                early_reasons=json.dumps(dict(early), sort_keys=True),
                collisions=collisions, teleports=teleports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--flows", type=int, nargs="+", default=[1500, 1750, 2000])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(311, 316)))
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--limit", type=float, default=28.8)
    parser.add_argument("--advice-weight", type=float, choices=(0., .5, 1.), default=.5,
                        help="LC2013 对邻车调速建议的权重，普通车为 0.5")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cases = product([out], args.flows, args.seeds, ["full", "200m"], [.2, .65],
                    [args.duration], [args.limit], [args.advice_weight])
    with ProcessPoolExecutor(args.jobs) as pool, (out / "cases.csv").open("x", newline="") as f:
        writer = None
        for row in pool.map(run_case, cases):
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=row)
                writer.writeheader()
            writer.writerow(row)
            f.flush()


if __name__ == "__main__":
    main()
