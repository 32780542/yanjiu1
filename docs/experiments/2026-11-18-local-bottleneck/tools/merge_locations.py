"""每辆从终止道出发的车只记第一次实际完成并入的位置。"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean


def first_merges(case):
    path = Path(case["run_dir"]) / "trips.json"
    if case["evidence_verified"] != "True" or case["safe"] != "True" or case["all_completed"] != "True":
        raise ValueError(f"案例未通过完整性或安全验收 {path}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != case["trips_sha256"]:
        raise ValueError(f"行程文件与验收记录不一致 {path}")
    trips = [trip for trip in json.loads(raw) if trip["lane"] == 2]
    positions = []
    for trip in trips:
        for event in trip["lane_completion_events"]:
            if event["from_lane"] == 2 and event["to_lane"] == 1:
                positions.append(event["x"])
                break
    return dict(flow_veh_h_lane=int(float(case["flow"])), seed=int(case["seed"]),
                candidate=case["candidate"], mode=case["mode"],
                started_lane2=len(trips), recorded=len(positions), missing=len(trips) - len(positions),
                before_800_m=sum(x < 800 for x in positions),
                from_800_to_900_m=sum(800 <= x < 900 for x in positions),
                at_or_after_900_m=sum(x >= 900 for x in positions),
                mean_completion_x_m=mean(positions) if positions else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("per_case", type=Path, help="已验收的 per_case.csv")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.per_case.open(encoding="utf-8-sig", newline="") as stream:
        rows = [first_merges(case) for case in csv.DictReader(stream) if case["scenario"] == "lane_drop"]
    rows.sort(key=lambda row: (row["flow_veh_h_lane"], row["seed"], row["candidate"], row["mode"]))
    with args.output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
