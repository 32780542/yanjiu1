"""Real SUMO no-lane-change strings under the same prescribed leader input."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "variants/phase5g_pure_formation"))
from experiments import native_sumo as native
from research.common import binary, tool_env


def leader_speed(time_s, signal):
    if signal == "sine":
        return 28.8 + (.8 * math.sin(.5 * (time_s - 20)) if time_s >= 20 else 0)
    if time_s < 30:
        return 28.8
    if time_s < 32.2:
        return 28.8 - 4 * (time_s - 30)
    if time_s < 37.2:
        return 20.
    return min(28.8, 20 + 4 * (time_s - 37.2))


def run(source, directory, signal):
    directory.mkdir(parents=True, exist_ok=False)
    raw = source.read_bytes()
    (directory / "native_rules.py").write_bytes(raw)
    spec = importlib.util.spec_from_file_location("string_rules_" + directory.name, source)
    rules = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = rules
    spec.loader.exec_module(rules)
    nodes, edges = ET.Element("nodes"), ET.Element("edges")
    for index, x in enumerate((0, 6000, 12000)):
        ET.SubElement(nodes, "node", id=f"n{index}", x=str(x), y="0", type="priority")
    for index, name in enumerate(("upstream", "downstream")):
        ET.SubElement(edges, "edge", id=name, **{"from": f"n{index}", "to": f"n{index+1}"},
                      numLanes="1", speed="33.3", width="3.3")
    native._write_xml(directory / "nodes.xml", nodes)
    native._write_xml(directory / "edges.xml", edges)
    net_command = [binary("netconvert"), "-n", str(directory / "nodes.xml"), "-e",
                   str(directory / "edges.xml"), "-o", str(directory / "network.net.xml"),
                   "--no-turnarounds", "true"]
    with (directory / "netconvert.log").open("w", encoding="utf-8") as stream:
        subprocess.run(net_command, env=tool_env(), stdout=stream, stderr=subprocess.STDOUT,
                       check=True, timeout=30)
    keys = [f"v{i:02d}" for i in range(12)]
    initial = [dict(id=key, depart=0, lane=0, x=400 - 30 * i, speed=28.8)
               for i, key in enumerate(keys)]
    routes = native.write_routes(directory, native.initial_tape(initial))
    command = [binary("sumo"), "-n", str(directory / "network.net.xml"), "-r", str(routes),
               "--step-length", ".1", "--time-to-teleport", "-1", "--no-step-log", "true",
               "--collision.action", "warn", "--collision.mingap-factor", "0",
               "--duration-log.disable", "true"]
    traci = native.lock_traci()
    label = "string_" + directory.name
    horizon = 180. if signal == "sine" else 100.
    traces = [[] for _ in keys]
    local = native.LocalTracks(rules.Vehicle)
    collisions = teleports = 0
    minimum_net_gap = float("inf")
    with (directory / "sumo.log").open("w", encoding="utf-8") as stream:
        traci.start(command, label=label, stdout=stream, doSwitch=False)
        connection = traci.getConnection(label)
        version = connection.getVersion()[1]
        try:
            with gzip.open(directory / "trajectory.jsonl.gz", "wt", encoding="utf-8") as trace:
                for tick in range(1, round(horizon / .1) + 1):
                    connection.simulationStep()
                    now = connection.simulation.getTime()
                    for key in connection.simulation.getDepartedIDList():
                        connection.vehicle.setSpeedMode(key, 31)
                        connection.vehicle.setLaneChangeMode(key, 512)
                    present = connection.vehicle.getIDList()
                    if set(present) != set(keys):
                        raise RuntimeError("String insertion or road coverage changed")
                    states = {key: native.PhysicalState(connection.vehicle.getPosition(key)[0], 1.65,
                              connection.vehicle.getSpeed(key), 0, 0.,
                              connection.vehicle.getAcceleration(key), now) for key in keys}
                    collisions += connection.simulation.getCollidingVehiclesNumber()
                    teleports += connection.simulation.getStartingTeleportNumber()
                    minimum_net_gap = min(minimum_net_gap,
                        min(states[keys[i-1]].x - states[keys[i]].x - 4 for i in range(1, 12)))
                    for i, key in enumerate(keys):
                        ego, neighbors = local.observe(key, states)
                        if i == 0:
                            requested = leader_speed(now, signal)
                        else:
                            # Isolate the longitudinal law on the one-lane bench.
                            # The complete 3-lane decision is tested in run_trials.
                            requested = min(rules._following(ego, neighbors, 1)[0],
                                            rules.safe_speed(ego, neighbors))
                        connection.vehicle.setSpeed(key, requested)
                        traces[i].append((now, states[key].speed, states[key].acceleration))
                    trace.write(json.dumps(dict(time_s=now, states={key: [s.x, s.speed, s.acceleration]
                                for key, s in states.items()}), separators=(",", ":")) + "\n")
        finally:
            connection.close()
    window = (60., 180.) if signal == "sine" else (20., 100.)
    measures = []
    for key, rows in zip(keys, traces):
        sample = [r for r in rows if window[0] <= r[0] <= window[1]]
        speeds = [r[1] for r in sample]
        accelerations = [r[2] for r in sample]
        measures.append(dict(vehicle=key, half_speed_range_mps=(max(speeds)-min(speeds))/2,
                             speed_rms_from_cruise_mps=math.sqrt(sum((v-28.8)**2 for v in speeds)/len(speeds)),
                             min_acceleration_mps2=min(accelerations), max_acceleration_mps2=max(accelerations)))
    result = dict(signal=signal, source_sha256=hashlib.sha256(raw).hexdigest(), physical=native.PHYSICAL,
                  leader_input="leader_speed() in saved driver", vehicles=12, initial_head_gap_m=30.,
                  follower_control="_following plus unchanged safe_speed; no lane-change decision",
                  horizon_s=horizon, measurement_window_s=window, sumo_version=version,
                  collisions=collisions, teleports=teleports, minimum_net_gap_m=minimum_net_gap,
                  safe=collisions == teleports == 0 and minimum_net_gap >= 1.5-1e-6, measures=measures)
    native.write_json(directory / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--base-label", default="base")
    parser.add_argument("--candidate-label", default="T")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = REPO / "tmp/literature_trials/strings" / stamp
    output.mkdir(parents=True, exist_ok=False)
    (output / "driver.py").write_bytes(Path(__file__).read_bytes())
    results = []
    for name, source in ((args.base_label, args.base), (args.candidate_label, args.candidate)):
        for signal in ("sine", "brake"):
            result = run(source.resolve(), output / (name + "_" + signal), signal)
            results.append(dict(candidate=name, run_dir=str(output / (name + "_" + signal)), **result))
            print(json.dumps(dict(candidate=name, signal=signal, safe=result["safe"],
                             leader_amplitude=result["measures"][0]["half_speed_range_mps"],
                             tail_amplitude=result["measures"][-1]["half_speed_range_mps"])), flush=True)
    native.write_json(output / "summary.json", results)
    print(json.dumps(dict(output=str(output))), flush=True)
    return 0 if all(r["safe"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
