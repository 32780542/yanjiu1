"""用 SUMO 实际入场和驶出时刻复算路内行程。保留 600 秒内入场的子样本。"""

import argparse
import csv
import gzip
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
from statistics import mean
import xml.etree.ElementTree as ET


def write_csv(path, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        table = csv.DictWriter(stream, fieldnames=rows[0])
        table.writeheader()
        table.writerows(rows)


def measure(folder, method, flow, seed, writer):
    run, = (p.parent for p in folder.glob("*/result.json"))
    result = json.loads((run / "result.json").read_bytes())
    hdv = method.startswith("hdv")
    if hdv:
        safe = result["all_arrived"] and result["collision_log_lines"] == 0
        trip_file, route_file = "trips.xml", "hdv.rou.xml"
        if result.get("profile") in ("shared_noa", "hdv_headway"):
            route_file = "native.rou.xml"
    else:
        safe = result["status"] == "drained" and result["collisions"] == 0
        trip_file, route_file = "sumo_tripinfo.xml", "native.rou.xml"
    if not safe or result["teleports"]:
        raise ValueError(f"行程未正常结束 {folder}")
    shared_type = route_file == "native.rou.xml"
    # netconvert 的注释含运行时间和绝对路径；只比较仿真实际读取的网络内容。
    route_bytes = (run / route_file).read_bytes()
    routes = ET.fromstring(route_bytes)
    vehicle_type = routes.find("vType")
    tau = float(vehicle_type.attrib["tau"])
    shared_inputs = None
    network_hash = routes_hash = ""
    road_limit = None
    if shared_type:
        network = ET.parse(run / "native.net.xml").getroot()
        road_limit, = {float(lane.attrib["speed"]) for lane in network.findall("edge/lane")}
        network_hash = sha256(ET.tostring(network)).hexdigest()
        routes_hash = sha256(route_bytes).hexdigest()
        # 配对时只允许普通车采用约定的 IDM 时距，原始文件哈希单独保留。
        expected_tau = result.get("idm_tau_s", 0.65) if result.get("profile") == "hdv_headway" else 0.2
        if tau != expected_tau:
            raise ValueError(f"车型 IDM 时距与方案不符 {folder}: {tau}")
        vehicle_type.set("tau", "0.2")
        shared_inputs = network_hash, sha256(ET.tostring(routes)).digest()

    # 发车清单只校对配对输入，统计表的车辆和时间来自实际 tripinfo。
    demand = [(v.get("id"), v.get("departLane"), float(v.get("depart")),
               float(v.get("departPos")), float(v.get("departSpeed")))
              for v in routes.iter("vehicle")]
    stamps = {}
    for vehicle in ET.parse(run / trip_file).iter("tripinfo"):
        key = vehicle.attrib["id"]
        if shared_type and (vehicle.get("vType") != "CAV_ICV" or float(vehicle.get("speedFactor")) != 1):
            raise ValueError(f"实际行程采用了其他车型或速度倍率 {folder} {key}")
        # 原始记录以 0.1 秒为步长，换成整数步再相减。
        entry, exit_ = (round(float(vehicle.attrib[k]) * 10) for k in ("depart", "arrival"))
        duration = exit_ - entry
        if (key in stamps or entry < 0 or duration <= 0 or vehicle.get("vaporized")
                or not isclose(duration / 10, float(vehicle.attrib["duration"]), abs_tol=1e-8)):
            raise ValueError(f"入场或离场记录异常 {folder} {key}")
        stamps[key] = (entry, exit_)
        writer.writerow((method, flow, seed, key, entry / 10, exit_ / 10, duration / 10))
    if (len(stamps) != result["completed"] or set(stamps) != {r[0] for r in demand}
            or not hdv and len(stamps) != result["departed"]):
        raise ValueError(f"实际完成车辆核对失败 {folder}")

    travel = [end - start for start, end in stamps.values()]
    early = [end - start for start, end in stamps.values() if start < 6000]
    actual_mean = mean(travel) / 10
    if not isclose(actual_mean, result["mean_travel_time_s"], abs_tol=1e-8):
        raise ValueError(f"逐车行程与 SUMO 汇总不一致 {folder}")
    first = min(entry for entry, _ in stamps.values())
    last = max(exit_ for _, exit_ in stamps.values())
    return demand, shared_inputs, dict(method=method, flow=flow, seed=seed, vehicles=len(travel),
                        total_travel_s=sum(travel) / 10, mean_travel_s=actual_mean,
                        entered_before_600=len(early), early_total_travel_s=sum(early) / 10,
                        early_mean_travel_s=mean(early) / 10,
                        first_entry_s=first / 10, last_exit_s=last / 10,
                        first_entry_to_last_exit_s=(last - first) / 10,
                        exits_before_600=sum(end < 6000 for _, end in stamps.values()),
                        profile=result.get("profile", "shared_noa"), network_sha256=network_hash,
                        routes_sha256=routes_hash, road_limit_mps=road_limit, idm_tau_s=tau)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("output", type=Path, help="新建报告目录")
    parser.add_argument("--with-matlab", action="store_true")
    args = parser.parse_args()
    methods = ["transform", "noa", "hdv"]
    if args.with_matlab:
        methods.append("hdv_matlab")
    args.output.mkdir(parents=True, exist_ok=False)
    cases, summaries = [], []
    with gzip.open(args.output / "trips.csv.gz", "wt", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("method", "flow", "seed", "vehicle", "entry_s", "exit_s", "travel_s"))
        for flow in (1500, 1750, 2000):
            for seed in range(311, 316):
                reference = None
                shared_inputs = None
                for method in methods:
                    folder = args.batch / f"{method}_f{flow}_s{seed}"
                    demand, inputs, row = measure(folder, method, flow, seed, writer)
                    if reference is not None and demand != reference:
                        raise ValueError(f"三道发车清单有差异 {folder}")
                    reference = demand
                    if inputs is not None:
                        if shared_inputs is not None and inputs != shared_inputs:
                            raise ValueError(f"共同车型、路由或道路不一致 {folder}")
                        shared_inputs = inputs
                    cases.append(row)
            for method in methods:
                group = [c for c in cases if c["method"] == method and c["flow"] == flow]
                count = sum(c["vehicles"] for c in group)
                early = sum(c["entered_before_600"] for c in group)
                summaries.append(dict(method=method, flow=flow, vehicles=count,
                                      road_limit_mps=group[0]["road_limit_mps"],
                                      mean_travel_s=sum(c["total_travel_s"] for c in group) / count,
                                      seed_equal_mean_s=mean(c["mean_travel_s"] for c in group),
                                      entered_before_600=early,
                                      early_mean_travel_s=sum(c["early_total_travel_s"] for c in group) / early,
                                      outlet_flow_first_600_veh_h=6 * mean(c["exits_before_600"] for c in group),
                                      mean_first_entry_to_last_exit_s=mean(c["first_entry_to_last_exit_s"] for c in group)))
    write_csv(args.output / "cases.csv", cases)
    write_csv(args.output / "summary.csv", summaries)


if __name__ == "__main__":
    main()
