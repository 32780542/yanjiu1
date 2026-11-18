"""从实际 SUMO 轨迹量出三车道完整队形。可用 --depart-at 分开检查分批出发的车群。"""
import argparse
import gzip
import json
from pathlib import Path
import sys

VARIANT = Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"
sys.path.insert(0, str(VARIANT))
from experiments.complete_layers import groups_at


def measure(run, depart_at=None):
    inputs = json.loads((run / "input.json").read_bytes())
    result = json.loads((run / "result.json").read_bytes())
    ids = {r["vehicle_id"] for r in inputs["arrivals"] if depart_at is None or r["requested_s"] == depart_at}
    if len(ids) < 3:
        raise ValueError("所选车群不足三辆")
    end = 800 if result["scenario"] == "lane_drop" else 1200
    moves = sum(e["x"] < end for car in json.loads((run / "trips.json").read_bytes())
                if car["vehicle_id"] in ids for e in car["lane_events"])
    first = start = None
    longest = 0.
    with gzip.open(run / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            now, states = frame["time_s"], frame["states"]
            if start is not None:
                longest = max(longest, now - start)
            counts = [0, 0, 0]
            eligible = ids <= states.keys()
            if eligible:
                for key in ids:
                    x, y = states[key][:2]
                    lane = round(y / 3.3 - .5)
                    if x >= end or not 0 <= lane < 3 or abs(y - (lane + .5) * 3.3) > .3:
                        eligible = False
                        break
                    counts[lane] += 1
            formed = eligible and max(counts) - min(counts) <= 1 and any(
                g["size"] == len(ids) // 3 * 3 and ids.issuperset(g["vehicle_ids"])
                for g in groups_at(states, 3))
            if formed and start is None:
                start = now
                if first is None:
                    first = now
            elif not formed:
                start = None
    return dict(vehicles=len(ids), status=result["status"], collisions=result["collisions"],
                teleports=result["teleports"], lane_crossings=moves, first_shape_s=first,
                longest_shape_s=round(longest, 1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="包含 positions.jsonl.gz 的 SUMO 运行目录")
    parser.add_argument("--depart-at", type=float, help="只核对该时刻请求入场的车群")
    args = parser.parse_args()
    print(json.dumps(measure(args.run, args.depart_at), ensure_ascii=False, indent=2))
