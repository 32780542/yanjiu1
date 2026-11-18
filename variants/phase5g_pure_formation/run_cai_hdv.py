"""用 Cai 的普通 HDV 车型跑完全程。每辆车由 SUMO 自己跟驰和换道。"""

import argparse
import json
import os
from pathlib import Path
from statistics import mean
import sys
import xml.etree.ElementTree as ET

from experiments.native_sumo import STEP, arrival_tape, build_network, write_json
from research.common import sumo_home


# 来自 MATLAB 工程 cross.rou.xml 的 CAV_HDV。
HDV = dict(id="CAV_HDV", carFollowModel="IDM", length="4", minGap="2", tau="0.65",
           accel="3", decel="10", emergencyDecel="30", delta="4", stepping="0.1",
           lcSpeedGain="0.3", lcImpatience="0", lcCooperative="0.5",
           guiShape="passenger", color="255,0,0")


def scenario(directory, requests, matlab_data):
    if matlab_data:
        source = ET.parse(matlab_data / "cross.rou.xml")
        vehicle_type = source.find("./vType[@id='CAV_HDV']")
        route = source.find("./route[@id='P1P3']")
        network = matlab_data / "cross.net.xml"
    else:
        vehicle_type = ET.Element("vType", **HDV, maxSpeed="33.3", speedFactor="1", speedDev="0")
        route = ET.Element("route", id="through", edges="upstream downstream")
        network = build_network(directory)
    routes = ET.Element("routes")
    routes.extend((vehicle_type, route))
    for row in requests:
        ET.SubElement(routes, "vehicle", id=row["vehicle_id"], type=vehicle_type.attrib["id"],
                      route=route.attrib["id"], depart=str(row["requested_s"]),
                      departLane=str(row["lane"]), departPos=str(row["x"]),
                      departSpeed=str(row["speed"]), arrivalPos="max")
    file = directory / "hdv.rou.xml"
    ET.ElementTree(routes).write(file, encoding="utf-8", xml_declaration=True)
    return network, file


def run(traci, binary, directory, flow, seed, duration, max_time, matlab_data, gui):
    directory.mkdir(parents=True, exist_ok=False)
    requests = arrival_tape(seed, flow, duration)
    network, routes = scenario(directory, requests, matlab_data)
    trips, log = directory / "trips.xml", directory / "sumo.log"
    command = [str(binary), "-n", str(network), "-r", str(routes), "--step-length", str(STEP),
               "--lanechange.duration", "1", "--seed", str(seed), "--route-steps", "0",
               "--time-to-teleport", "-1", "--collision.action", "warn", "--no-step-log", "true",
               "--error-log", str(log), "--tripinfo-output", str(trips)]
    if not matlab_data:
        command.extend(["--collision.mingap-factor", "0", "--collision.check-junctions", "true"])
    if gui:
        command.extend(["--start", "--quit-on-end"])
    version = traci.start(command)
    tc = traci.constants
    teleports = 0
    try:
        traci.simulation.subscribe((tc.VAR_DEPARTED_VEHICLES_IDS, tc.VAR_MIN_EXPECTED_VEHICLES,
                                    tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER))
        for _ in range(round(max_time / STEP)):
            traci.simulationStep()
            state = traci.simulation.getSubscriptionResults()
            for vehicle in state[tc.VAR_DEPARTED_VEHICLES_IDS]:
                traci.vehicle.setSpeedMode(vehicle, 31)
                traci.vehicle.setLaneChangeMode(vehicle, 1621)
            teleports += state[tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER]
            if state[tc.VAR_MIN_EXPECTED_VEHICLES] == 0:
                break
    finally:
        traci.close()

    completed = {t.attrib["id"]: t for t in ET.parse(trips).iter("tripinfo")}
    expected = {r["vehicle_id"]: r["requested_s"] for r in requests}
    all_arrived = completed.keys() == expected.keys()
    warnings = log.read_text(encoding="utf-8", errors="replace").lower().splitlines()
    collisions = sum("collision" in line or "collid" in line for line in warnings)
    result = dict(profile="matlab" if matlab_data else "project", sumo=version, flow=flow,
                  seed=seed, duration_s=duration, requested=len(expected), completed=len(completed),
                  all_arrived=all_arrived, teleports=teleports, collision_log_lines=collisions)
    if all_arrived and completed:
        result.update(mean_travel_time_s=mean(float(t.attrib["duration"]) for t in completed.values()),
                      mean_entry_wait_s=mean(float(t.attrib["depart"]) - expected[k] for k, t in completed.items()),
                      mean_system_time_s=mean(float(t.attrib["arrival"]) - expected[k] for k, t in completed.items()),
                      last_exit_s=max(float(t.attrib["arrival"]) for t in completed.values()))
    write_json(directory / "result.json", result)
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return all_arrived and not teleports and not collisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flows", type=int, nargs="+", default=[1500])
    parser.add_argument("--seeds", type=int, nargs="+", default=[311])
    parser.add_argument("--duration", type=float, default=600)
    parser.add_argument("--max-time", type=float, default=1800)
    parser.add_argument("--output", type=Path, required=True, help="每次运行使用新的输出目录")
    parser.add_argument("--matlab-data", type=Path, help="使用原始路网和车型的 traci_tls/data 目录")
    parser.add_argument("--sumo-home", type=Path, help="对应版本的 SUMO 安装目录，默认使用项目版本")
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if args.max_time < args.duration:
        parser.error("--max-time must cover --duration")
    home = (args.sumo_home or sumo_home()).resolve()
    os.environ["SUMO_HOME"] = str(home)
    sys.path.insert(0, str(home / "tools"))
    import traci

    name = "sumo-gui" if args.gui else "sumo"
    binary = home / "bin" / name
    if binary.with_suffix(".exe").is_file():
        binary = binary.with_suffix(".exe")
    successful = True
    for flow in args.flows:
        for seed in args.seeds:
            directory = args.output.resolve() / f"f{flow}_s{seed}"
            if not run(traci, binary, directory, flow, seed, args.duration, args.max_time,
                       args.matlab_data, args.gui):
                successful = False
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
