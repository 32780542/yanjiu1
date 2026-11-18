"""用 SUMO 实际入场和驶出时刻复算路内行程。保留 600 秒内入场的子样本。"""

import argparse
import csv
import gzip
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
    else:
        safe = result["status"] == "drained" and result["collisions"] == 0
        trip_file, route_file = "sumo_tripinfo.xml", "native.rou.xml"
    if not safe or result["teleports"]:
        raise ValueError(f"行程未正常结束 {folder}")

    # 发车清单只校对配对输入，统计表的车辆和时间来自实际 tripinfo。
    demand = [(v.get("id"), v.get("departLane"), float(v.get("depart")),
               float(v.get("departPos")), float(v.get("departSpeed")))
              for v in ET.parse(run / route_file).iter("vehicle")]
    stamps = {}
    for vehicle in ET.parse(run / trip_file).iter("tripinfo"):
        key = vehicle.attrib["id"]
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
    return demand, dict(method=method, flow=flow, seed=seed, vehicles=len(travel),
                        total_travel_s=sum(travel) / 10, mean_travel_s=actual_mean,
                        entered_before_600=len(early), early_total_travel_s=sum(early) / 10,
                        early_mean_travel_s=mean(early) / 10,
                        first_entry_s=first / 10, last_exit_s=last / 10,
                        first_entry_to_last_exit_s=(last - first) / 10)


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
                for method in methods:
                    folder = args.batch / f"{method}_f{flow}_s{seed}"
                    demand, row = measure(folder, method, flow, seed, writer)
                    if reference is not None and demand != reference:
                        raise ValueError(f"三道发车清单有差异 {folder}")
                    reference = demand
                    cases.append(row)
            for method in methods:
                group = [c for c in cases if c["method"] == method and c["flow"] == flow]
                count = sum(c["vehicles"] for c in group)
                early = sum(c["entered_before_600"] for c in group)
                summaries.append(dict(method=method, flow=flow, vehicles=count,
                                      mean_travel_s=sum(c["total_travel_s"] for c in group) / count,
                                      seed_equal_mean_s=mean(c["mean_travel_s"] for c in group),
                                      entered_before_600=early,
                                      early_mean_travel_s=sum(c["early_total_travel_s"] for c in group) / early,
                                      mean_first_entry_to_last_exit_s=mean(c["first_entry_to_last_exit_s"] for c in group)))
    write_csv(args.output / "cases.csv", cases)
    write_csv(args.output / "summary.csv", summaries)


if __name__ == "__main__":
    main()
