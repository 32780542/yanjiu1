"""从真实入场、驶出与车头过线时刻分解路内时间。"""
import argparse
from bisect import bisect_right
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

GATES = (640, 800, 1000)
ZONES = ("0_640", "640_800", "800_1000", "1000_1200")


def measure(run):
    result = json.loads((run / "result.json").read_bytes())
    trips = list(ET.parse(run / "sumo_tripinfo.xml").iter("tripinfo"))
    times = {v.get("id"): [float(v.get("depart"))] for v in trips}
    if not (result["status"] == "drained" and result["requested"] == result["completed"] == len(times)
            and result["collisions"] == result["teleports"] == 0):
        raise ValueError(f"未完整安全驶出 {run}")
    slow = Counter()
    slow_by_lane = Counter()
    previous = {}
    before = None
    with gzip.open(run / "positions.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            frame = json.loads(line)
            now, states = frame["time_s"], frame["states"]
            if before is not None:
                dt = now - before
                if abs(dt - .1) > 1e-6:
                    raise ValueError(f"轨迹步长不符 {run}")
                for key, (x, y, speed, _) in previous.items():
                    zone = bisect_right(GATES, x)
                    if speed < 5:
                        slow[zone] += dt
                        if zone == 2:
                            lane = round(y / 3.3 - .5)
                            slow_by_lane[lane] += dt
                    if zone < len(GATES) and key in states and states[key][0] >= GATES[zone]:
                        fraction = (GATES[zone] - x) / (states[key][0] - x)
                        times[key].append(before + fraction * dt)
            previous, before = states, now
    sums = [0.] * len(ZONES)
    for trip in trips:
        stamps = times[trip.get("id")]
        stamps.append(float(trip.get("arrival")))
        if len(stamps) != 5 or stamps != sorted(stamps):
            raise ValueError(f"缺少过线记录 {trip.get('id')}")
        for i in range(4):
            sums[i] += stamps[i+1] - stamps[i]
    n = len(trips)
    if abs(sum(sums)/n - result["mean_travel_time_s"]) > 1e-6:
        raise ValueError(f"分段总和不符 {run}")
    changes = Counter()
    for trip in json.loads((run / "trips.json").read_bytes()):
        for event in trip["lane_events"]:
            changes[bisect_right(GATES, event["x"])] += 1
    row = dict(flow=result["flow_veh_h_lane"], seed=result["seed"], vehicles=n,
               exits_600=sum(float(v.get("arrival")) < 600 for v in trips),
               travel_s=sum(sums))
    for i, zone in enumerate(ZONES):
        row.update({f"time_{zone}": sums[i], f"slow_{zone}": slow[i], f"changes_{zone}": changes[i]})
    for lane in range(3):
        row[f"slow_800_1000_lane{lane}"] = slow_by_lane[lane]
    if abs(sum(slow_by_lane.values()) - slow[2]) > 1e-6 or slow_by_lane.keys() - {0, 1, 2}:
        raise ValueError(f"低速车道划分不符 {run}")
    return row


def check_pair(reference, run):
    """来车、道路、车型与实际完成的车辆逐项对应。"""
    def arrivals(path):
        return json.loads((path / "input.json").read_bytes())["arrivals"]

    def vehicles(path):
        return {v.get("id") for v in ET.parse(path / "sumo_tripinfo.xml").iter("tripinfo")}

    if arrivals(reference) != arrivals(run) or vehicles(reference) != vehicles(run):
        raise ValueError("两次运行的来车或实际驶出车辆不同")
    for name in ("native.net.xml", "native.rou.xml"):
        if ET.tostring(ET.parse(reference / name).getroot()) != ET.tostring(ET.parse(run / name).getroot()):
            raise ValueError(f"两次运行的 {name} 不同")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--reference", type=Path, help="对照运行目录")
    parser.add_argument("--geometry", action="store_true", help="同时复核上游完整交错队形")
    args = parser.parse_args()
    if args.reference:
        check_pair(args.reference, args.run)
    result = measure(args.run)
    if args.geometry:
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"))
        from experiments.complete_layers import evaluate_layers
        result["geometry"] = evaluate_layers(args.run / "positions.jsonl.gz", 3, (0, 640))
    print(json.dumps(result, indent=2))
