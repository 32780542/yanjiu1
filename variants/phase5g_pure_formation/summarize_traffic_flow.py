"""从持续交通台账独立复算效率、油耗并导出配对结果。"""

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, stdev

from experiments.formation_study import write_json


def paired_rows(rows):
    key = lambda r:(r["lane_count"],r["flow_veh_h_lane"],r["seed"],r["target_speed_mps"])
    baselines = {key(r):r for r in rows if not r["formation"]}
    pairs = []
    for row in rows:
        if not row["formation"]:
            continue
        baseline = baselines[key(row)]
        valid = (row["all_completed"] and baseline["all_completed"]
                 and row["collision_pairs"] == baseline["collision_pairs"] == 0
                 and row["road_departure_vehicles"] == baseline["road_departure_vehicles"] == 0)
        item = {k:row[k] for k in ("kind","lane_count","flow_veh_h_lane","seed",
                                   "target_speed_mps","same_lane_gap_m")}
        item.update(name=row["name"],baseline_name=baseline["name"],comparison_valid=valid)
        for metric, label, sign in (("mean_system_time_s","system_time_reduction_pct",1),
            ("mean_travel_time_s","travel_time_reduction_pct",1),
            ("fuel_g_per_km","fuel_reduction_pct",1),("exit_flow_veh_h","exit_flow_change_pct",-1)):
            a, b = baseline[metric], row[metric]
            item[label] = sign*100*(a-b)/a if valid and a else None
        pairs.append(item)
    return pairs


def independent_metrics(trips, duration):
    entered = [r for r in trips if r["entered_s"] is not None]
    completed = [r for r in entered if r["exited_s"] is not None]
    complete = len(completed) == len(trips) and bool(trips)
    distance = math.fsum(r["distance_m"] for r in trips)
    fuel = math.fsum(r["fuel_mg"] for r in trips)
    seconds = math.fsum(r["onroad_s"] for r in trips)
    return dict(requested=len(trips),entered=len(entered),completed=len(completed),
        all_completed=complete,pending_final=len(trips)-len(entered),
        onroad_final=len(entered)-len(completed),
        entered_by_600s=sum(r["entered_s"]<=duration for r in entered),
        exited_by_600s=sum(r["exited_s"]<=duration for r in completed),
        pending_at_600s=len(trips)-sum(r["entered_s"]<=duration for r in entered),
        onroad_at_600s=sum(r["entered_s"]<=duration for r in entered)-sum(r["exited_s"]<=duration for r in completed),
        mean_entry_wait_s=mean(r["entered_s"]-r["requested_s"] for r in entered) if complete else None,
        mean_travel_time_s=mean(r["exited_s"]-r["entered_s"] for r in completed) if complete else None,
        mean_system_time_s=mean(r["exited_s"]-r["requested_s"] for r in completed) if complete else None,
        total_distance_km=distance/1000,total_fuel_kg=fuel/1e6,
        fuel_g_per_km=fuel/distance if distance else None,
        mean_fuel_rate_mg_s=fuel/seconds if seconds else None,
        network_mean_speed_mps=distance/seconds if seconds else None,
        exit_flow_veh_h=3600*sum(r["exited_s"]<=duration for r in completed)/duration,
        clearance_after_600s_s=max(0.,max(r["exited_s"] for r in completed)-duration) if complete else None)


def group_rows(rows, paired=False):
    groups = {}
    fields = ["kind","lane_count","flow_veh_h_lane","target_speed_mps","same_lane_gap_m"]
    if not paired:
        fields.append("formation")
    for row in rows:
        groups.setdefault(tuple(row[k] for k in fields),[]).append(row)
    metrics = ("system_time_reduction_pct","travel_time_reduction_pct","fuel_reduction_pct",
               "exit_flow_change_pct") if paired else (
               "requested","completed","mean_entry_wait_s","mean_travel_time_s","mean_system_time_s",
               "exit_flow_veh_h","fuel_g_per_km","mean_fuel_rate_mg_s","total_fuel_kg","network_mean_speed_mps")
    output = []
    for key, values in sorted(groups.items()):
        result = dict(zip(fields,key))
        result["runs"] = len(values)
        result["valid_runs"] = sum(v["comparison_valid"] for v in values) if paired else sum(
            v["all_completed"] and v["collision_pairs"] == 0 and v["road_departure_vehicles"] == 0 for v in values)
        for metric in metrics:
            data = [v[metric] for v in values if v.get(metric) is not None]
            result[metric+"_mean"] = mean(data) if data else None
            result[metric+"_sd"] = stdev(data) if len(data)>1 else None
        output.append(result)
    return output


def export_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w",newline="",encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    protocol = json.loads((root/"protocol.json").read_text(encoding="utf-8"))
    summary = json.loads((root/"summary.json").read_text(encoding="utf-8"))
    expected = {c["name"] for c in protocol["cases"]}
    if {r["name"] for r in summary["results"]} != expected:
        raise ValueError("运行结果与固定工况集合不符")
    rows, tapes, checked, requests, network_checked = [], {}, 0, 0, 0
    for row in summary["results"]:
        if row["status"] != "completed":
            raise ValueError(f"执行未完成：{row['name']}")
        directory = root/row["name"]
        for name, expected_hash in json.loads((directory/"hashes.json").read_text(encoding="utf-8")).items():
            if hashlib.sha256((directory/name).read_bytes()).hexdigest() != expected_hash:
                raise ValueError(f"文件摘要不符：{row['name']}/{name}")
            checked += 1
        inputs = json.loads((directory/"input.json").read_text(encoding="utf-8"))
        trips = json.loads((directory/"trips.json").read_text(encoding="utf-8"))
        tape = {r["vehicle_id"]:r for r in inputs["arrivals"]}
        if set(tape) != {r["vehicle_id"] for r in trips}:
            raise ValueError("请求车辆台账不完整")
        for trip in trips:
            original = tape[trip["vehicle_id"]]
            if trip["requested_s"] != original["requested_s"] or trip["lane"] != original["lane"]:
                raise ValueError("台账改变了请求")
            entry, exit_time = trip["entered_s"], trip["exited_s"]
            if entry is not None and entry < trip["requested_s"]-1e-9:
                raise ValueError("车辆提前入场")
            if exit_time is not None and (entry is None or exit_time < entry):
                raise ValueError("车辆出入口顺序错误")
            if exit_time is not None and not math.isclose(exit_time-entry,trip["onroad_s"],abs_tol=1e-6):
                raise ValueError("在网时间积分与出入口时刻不符")
        recomputed = independent_metrics(trips,row["demand_duration_s"])
        for key,value in recomputed.items():
            previous = row[key]
            equal = (value == previous if value is None or isinstance(value,bool) else
                     math.isclose(value,previous,rel_tol=1e-9,abs_tol=1e-6))
            if not equal:
                raise ValueError(f"指标复算不符：{row['name']}/{key}")
        totals = dict(distance_m=0.,fuel_mg=0.,vehicle_seconds=0.)
        with gzip.open(directory/"network.jsonl.gz","rt",encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                if event["entered"] != event["exited"]+event["active"]:
                    raise ValueError("逐拍车辆守恒不符")
                for key in totals:
                    totals[key] += event[key]
        if not math.isclose(event["time_s"],row["recording_end_s"],abs_tol=1e-9):
            raise ValueError("记录终点与逐拍数据不符")
        for key, trip_key in (("distance_m","distance_m"),("fuel_mg","fuel_mg"),("vehicle_seconds","onroad_s")):
            if not math.isclose(totals[key],math.fsum(t[trip_key] for t in trips),rel_tol=1e-9,abs_tol=1e-5):
                raise ValueError(f"逐拍与逐车累计不符：{row['name']}/{key}")
        network_checked += 1
        tapes[row["name"]] = inputs["arrivals"]
        rows.append(row)
        requests += row["requested"]
        print(f"verified {len(rows)}/{len(expected)} {row['name']}",flush=True)
    pairs = paired_rows(rows)
    for pair in pairs:
        if tapes[pair["name"]] != tapes[pair["baseline_name"]]:
            raise ValueError("配对实验的来车表不同")
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/"protocol.json",protocol)
    write_json(output/"results.json",rows)
    write_json(output/"groups.json",group_rows(rows))
    write_json(output/"pairs.json",pairs)
    write_json(output/"pair_groups.json",group_rows(pairs,paired=True))
    export_csv(output/"cases.csv",rows)
    export_csv(output/"groups.csv",group_rows(rows))
    export_csv(output/"pairs.csv",pairs)
    export_csv(output/"pair_groups.csv",group_rows(pairs,paired=True))
    write_json(output/"verification.json",dict(cases=len(rows),file_hashes_checked=checked,
        trips_checked=requests,network_ledger_checks=network_checked,paired_tapes_checked=len(pairs),
        source_directory=str(root),source_snapshot_sha256=hashlib.sha256((root/"source_snapshot.zip").read_bytes()).hexdigest()))
    print(json.dumps(dict(output=str(output),cases=len(rows),trips=requests,files=checked)),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    summarize(args.root,args.output)
