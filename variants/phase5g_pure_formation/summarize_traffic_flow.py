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
from experiments.platoon_metrics import evaluate_platoons, PLATOON_METRICS


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


def independent_metrics(trips, duration, recording_end_s):
    entered = [r for r in trips if r["entered_s"] is not None]
    completed = [r for r in entered if r["exited_s"] is not None]
    complete = len(completed) == len(trips) and bool(trips)
    released = sum(r["requested_s"]<recording_end_s-1e-9 for r in trips)
    window_complete = recording_end_s>=duration-1e-9
    distance = math.fsum(r["distance_m"] for r in trips)
    fuel = math.fsum(r["fuel_mg"] for r in trips)
    seconds = math.fsum(r["onroad_s"] for r in trips)
    result = dict(requested=len(trips),entered=len(entered),completed=len(completed),
        all_completed=complete,requested_until_end=released,
        not_yet_requested_final=len(trips)-released,window_complete=window_complete,
        pending_final=released-len(entered),
        onroad_final=len(entered)-len(completed),
        entered_by_600s=sum(r["entered_s"]<=duration for r in entered) if window_complete else None,
        exited_by_600s=sum(r["exited_s"]<=duration for r in completed) if window_complete else None,
        pending_at_600s=len(trips)-sum(r["entered_s"]<=duration for r in entered) if window_complete else None,
        onroad_at_600s=(sum(r["entered_s"]<=duration for r in entered)-sum(r["exited_s"]<=duration for r in completed)) if window_complete else None,
        mean_entry_wait_s=mean(r["entered_s"]-r["requested_s"] for r in entered) if complete else None,
        mean_travel_time_s=mean(r["exited_s"]-r["entered_s"] for r in completed) if complete else None,
        mean_system_time_s=mean(r["exited_s"]-r["requested_s"] for r in completed) if complete else None,
        total_distance_km=distance/1000,total_fuel_kg=fuel/1e6,
        fuel_g_per_km=fuel/distance if distance else None,
        mean_fuel_rate_mg_s=fuel/seconds if seconds else None,
        network_mean_speed_mps=distance/seconds if seconds else None,
        exit_flow_veh_h=3600*sum(r["exited_s"]<=duration for r in completed)/duration if window_complete else None,
        clearance_after_600s_s=max(0.,max(r["exited_s"] for r in completed)-duration) if complete else None)
    if trips and 'inserted_s' in trips[0]:
        inserted = [r for r in trips if r['inserted_s'] is not None]
        source_count = sum(r['inserted_s']<=duration for r in inserted)
        entry_count = sum(r['entered_s']<=duration for r in entered)
        result.update(inserted=len(inserted),source_queue_final=released-len(inserted),
            upstream_final=len(inserted)-len(entered),
            source_queue_at_600s=len(trips)-source_count if window_complete else None,
            upstream_at_600s=source_count-entry_count if window_complete else None,
            mean_entry_wait_s=mean(r['inserted_s']-r['requested_s'] for r in trips) if complete else None,
            mean_upstream_travel_s=mean(r['entered_s']-r['inserted_s'] for r in trips) if complete else None,
            mean_entry_delay_s=mean(r['entered_s']-r['requested_s'] for r in trips) if complete else None)
    return result


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
               "exit_flow_veh_h","fuel_g_per_km","mean_fuel_rate_mg_s","total_fuel_kg","network_mean_speed_mps",
               "mean_upstream_travel_s","mean_entry_delay_s",*PLATOON_METRICS)
    output = []
    for key, values in sorted(groups.items()):
        result = dict(zip(fields,key))
        result["runs"] = len(values)
        valid_values = [v for v in values if (v["comparison_valid"] if paired else
            v["all_completed"] and v["collision_pairs"] == 0 and v["road_departure_vehicles"] == 0)]
        result["valid_runs"] = len(valid_values)
        for metric in metrics:
            population = values if metric in ("requested","completed") else valid_values
            data = [v[metric] for v in population if v.get(metric) is not None]
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


def summarize(root, output, additional_roots=()):
    root, output = Path(root).resolve(), Path(output).resolve()
    protocol = json.loads((root/"protocol.json").read_text(encoding="utf-8"))
    expected = {c["name"]:c for c in protocol["cases"]}
    batches = [root,*(Path(path).resolve() for path in additional_roots)]
    evidence, snapshots = {}, {}
    for batch in batches:
        batch_protocol = json.loads((batch/"protocol.json").read_text(encoding="utf-8"))
        snapshots[str(batch)] = hashlib.sha256((batch/"source_snapshot.zip").read_bytes()).hexdigest()
        for case in batch_protocol["cases"]:
            directory = batch/case["name"]
            if not (directory/"hashes.json").is_file():
                continue
            if case != expected.get(case["name"]):
                raise ValueError("接续批次改变了工况参数")
            if case["name"] in evidence:
                raise ValueError("同一条件重复进入汇总")
            evidence[case["name"]] = directory
    if set(evidence) != set(expected):
        raise ValueError("运行结果与固定工况集合不符")
    rows, tapes, checked, requests, network_checked = [], {}, 0, 0, 0
    for name,directory in sorted(evidence.items()):
        row = json.loads((directory/"result.json").read_text(encoding="utf-8"))
        if row["status"] != "completed":
            raise ValueError(f"执行未完成：{row['name']}")
        for filename, expected_hash in json.loads((directory/"hashes.json").read_text(encoding="utf-8")).items():
            if hashlib.sha256((directory/filename).read_bytes()).hexdigest() != expected_hash:
                raise ValueError(f"文件摘要不符：{row['name']}/{filename}")
            checked += 1
        inputs = json.loads((directory/"input.json").read_text(encoding="utf-8"))
        if inputs["case"] != expected[name]:
            raise ValueError("实际输入与固定协议不符")
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
        recomputed = independent_metrics(trips,row["demand_duration_s"],row["recording_end_s"])
        for key,value in recomputed.items():
            if key not in row and key in ("requested_until_end","not_yet_requested_final","window_complete"):
                row[key] = value
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
        incidents = json.loads((directory/"incidents.json").read_text(encoding="utf-8"))
        if (directory/'platoon_metrics.json').is_file():
            measured = evaluate_platoons(directory/'positions.jsonl.gz',row['lane_count'],row['same_lane_gap_m'])
            for key in PLATOON_METRICS:
                a,b = measured[key],row[key]
                if not (a == b if a is None or b is None else math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-8)):
                    raise ValueError(f"编队指标复算不符：{row['name']}/{key}")
        times = [event["time_s"] for events in incidents.values() for event in events]
        row["first_safety_event_s"] = min(times) if times else None
        if "termination_reason" not in row:
            row["termination_reason"] = ("completed_with_incident" if times else
                "drained" if row["all_completed"] else "time_limit")
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
        source_directory=str(root),source_snapshot_sha256=snapshots,
        case_sources={name:str(path) for name,path in evidence.items()}))
    print(json.dumps(dict(output=str(output),cases=len(rows),trips=requests,files=checked)),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--additional-root",type=Path,action="append",default=[])
    args = parser.parse_args()
    summarize(args.root,args.output,args.additional_root)
