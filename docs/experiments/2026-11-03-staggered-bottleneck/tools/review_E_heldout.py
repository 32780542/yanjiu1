"""Independent trip/ledger reconstruction and full-cell review of E_heldout90.

Does not import report_paired.py or run SUMO. Uses sealed field/hash verifiers.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import tarfile

import seal_case
import summarize

ROOT = Path(__file__).resolve().parents[1]
METRICS = ("mean_travel_time_s", "mean_system_time_s", "mean_entry_wait_s", "fuel_g_per_km",
    "mean_segment_100_600_s", "mean_segment_640_1100_s", "region_density_veh_km_lane",
    "region_mean_speed_mps", "region_low_speed_vehicle_s", "flow_1000m_veh_h",
    "lane_change_completions", "flag_participation_rate", "flag_mean_participants",
    "flag_peak_participants", "flag_mean_episode_s")
COUNTS, MAXERR = Counter(), defaultdict(float)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def mean(values):
    return math.fsum(values) / len(values) if values and all(v is not None for v in values) else None


def compare(actual, expected, context, section):
    if isinstance(actual, str) and not isinstance(expected, str):
        actual = None if actual == "" else actual == "True" if actual in ("True", "False") else json.loads(actual)
    if isinstance(expected, dict):
        assert set(actual) == set(expected), (context, "dict keys")
        for key in expected:
            compare(actual[key], expected[key], context + "." + key, section)
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), (context, "list length")
        for i, value in enumerate(expected):
            compare(actual[i], value, context + f"[{i}]", section)
    else:
        COUNTS[section] += 1
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            assert isinstance(actual, (int, float)) and math.isfinite(actual), (context, actual)
            error = abs(actual - expected)
            MAXERR[section] = max(MAXERR[section], error)
            assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-7), (context, actual, expected)
        else:
            assert actual == expected, (context, actual, expected)


def region(steps, start, end):
    dt = [(row, max(0., min(row["end_s"], end) - max(row["time_s"], start))) for row in steps]
    duration = end - start
    observed = math.fsum(t for _, t in dt)
    assert abs(observed - duration) <= 1e-6
    vehicle_s = math.fsum(row["n"] * t for row, t in dt)
    low = math.fsum(row["low_speed_n"] * t for row, t in dt)
    speed_m = math.fsum(row["speed_sum_mps"] * t for row, t in dt)
    return dict(start_s=start, end_s=end, duration_s=duration, observed_duration_s=observed,
        window_complete=True, vehicle_s=vehicle_s, mean_n=vehicle_s/duration,
        density_veh_km_lane=vehicle_s/duration/.6, mean_speed_mps=speed_m/vehicle_s if vehicle_s else None,
        low_speed_vehicle_s=low, low_speed_fraction=low/vehicle_s if vehicle_s else None,
        max_simultaneous_low_speed=max((row["low_speed_n"] for row,t in dt if t), default=0))


def reconstruct(record):
    folder = Path(record["evidence_dir"])
    verified = seal_case.verify(folder)
    compact = verified["compact"]["cases"][0]
    originals, hashes = summarize.archived_originals(folder)
    for name in originals:
        path = Path(record["run_dir"]) / name
        assert seal_case.sha(path) == hashes[name], (name, "local original/archive differs")
        originals[name] = seal_case.read(path)
    inp, result, trips = (originals[name] for name in ("input.json", "result.json", "trips.json"))
    saved = seal_case.read(folder / "seal.json")
    ledger = (folder / saved["traffic_metadata"]).parent
    cached = seal_case.read(ledger / "case.json")["run"]
    assert not summarize.audit_protocol(record, record["_task"], record["_protocol"], originals, hashes, cached)
    with gzip.open(ledger / "region_steps.jsonl.gz", "rt", encoding="utf-8") as stream:
        fields = json.loads(next(stream))
        steps = [dict(zip(fields,json.loads(line))) for line in stream]
    window = region(steps, 100., 600.)
    full = region(steps, cached["region_full"]["start_s"], cached["region_full"]["end_s"])
    compare(window, cached["region_window"], "region_window", "raw_vs_cached")
    compare(full, cached["region_full"], "region_full", "raw_vs_cached")
    with gzip.open(ledger / "vehicles.json.gz", "rt", encoding="utf-8") as stream:
        vehicles = json.load(stream)
    gates = {}
    with gzip.open(ledger / "gate_brackets.jsonl.gz", "rt", encoding="utf-8") as stream:
        next(stream)
        for line in stream:
            i, gate, t0, x0, t1, x1 = json.loads(line)
            value = t0 if t0 == t1 else t0 + (gate-x0)/(x1-x0)*(t1-t0)
            assert (i,str(gate)) not in gates
            gates[i,str(gate)] = value
            compare(value, vehicles[i]["gates"][str(gate)]["time_s"], "gate bracket", "raw_vs_cached")
    assert len(gates) == sum(g["status"] == "observed" for v in vehicles for g in v["gates"].values())
    arrivals = {row["vehicle_id"]: row for row in inp["arrivals"]}
    assert len(arrivals) == len(trips) == len(vehicles)
    for trip in trips:
        assert trip["entered_s"] is not None and trip["exited_s"] is not None
        assert all(trip[key] == arrivals[trip["vehicle_id"]][key] for key in ("requested_s","lane","x","speed"))
    safe = result["safe"] is True and not result.get("collisions") and not result.get("teleports") and result.get("error") is None
    assert safe and result["status"] == "drained" and cached["attribution_eligible"]
    travel = mean([t["exited_s"]-t["entered_s"] for t in trips])
    system = mean([t["exited_s"]-t["requested_s"] for t in trips])
    waiting = mean([t["entered_s"]-t["requested_s"] for t in trips])
    fuel, distance = math.fsum(t["fuel_mg"] for t in trips), math.fsum(t["distance_m"] for t in trips)
    duration = inp["case"]["demand_duration_s"]
    raw = dict(requested=len(trips), departed=len(trips), completed=len(trips), all_completed=True,
        performance_comparison_eligible=True, mean_entry_wait_s=waiting, mean_travel_time_s=travel,
        mean_system_time_s=system, fuel_g_per_km=fuel/distance,
        completed_subset_mean_travel_time_s=travel, completed_subset_mean_system_time_s=system,
        departed_subset_mean_entry_wait_s=waiting, completed_subset_fuel_g_per_km=fuel/distance,
        completed_fuel_mg=fuel, all_fuel_mg=fuel,
        exit_flow_veh_h=sum(t["exited_s"] <= duration for t in trips)*3600/duration,
        clearance_after_demand_s=max(0,max(t["exited_s"] for t in trips)-duration),
        lane_changes=sum(t.get("lane_changes",0) for t in trips),
        lane_change_completions=sum(len(t.get("lane_completion_events",[])) for t in trips))
    for a,b in ((100,600),(640,1100),(800,1100)):
        values = [gates[i,str(b)]-gates[i,str(a)] for i in range(len(vehicles))]
        for i,value in enumerate(values):
            compare(value, vehicles[i]["segments_s"][f"{a}_{b}"], "vehicle segment", "raw_vs_cached")
        raw[f"mean_segment_{a}_{b}_s"] = mean(values)
    raw.update({"region_"+key:window[key] for key in ("mean_n","density_veh_km_lane","mean_speed_mps",
        "low_speed_vehicle_s","low_speed_fraction","max_simultaneous_low_speed")})
    count = sum(100 <= value <= 600 for (i,gate),value in gates.items() if gate == "1000")
    raw.update(flow_1000m_crossings=count, flow_1000m_veh_h=count*3600/500,
               region_window=window, region_full=full)
    raw.update({"flag_"+key:value for key,value in compact["formation_state"].items()})
    common_keys = ("flow_veh_h_lane","demand_duration_s","max_time_s","step_s","lane_change_duration_s")
    params = {key:inp["case"][key] for key in common_keys}
    params.update({key:inp["case"].get(key) for key in ("request_acceleration_limit_mps2","request_deceleration_limit_mps2")})
    parameters = {key:inp.get(key) for key in ("physical","speed_mode","lane_change_mode","insertion","positions_step_s")}
    parameters.update(case=params,sumo_version=result.get("sumo_version"))
    raw.update(demand_sha256=digest(sorted(inp["arrivals"],key=lambda r:r["vehicle_id"])),
        parameters_sha256=digest(parameters), source_version_sha256=digest(inp["source_sha256"]),
        nonrule_source_sha256=digest({k:v for k,v in inp["source_sha256"].items() if k != "noa/native_rules.py"}),
        rules_sha256=inp["source_sha256"]["noa/native_rules.py"])
    assert cached["positions_sha256"] == compact["positions_sha256"]
    for key,value in raw.items():
        if key in cached:
            compare(value,cached[key],key,"raw_vs_cached")
        if key in result:
            compare(value,result[key],key,"raw_vs_original_result")
    expected = {key:value for key,value in record.items() if not key.startswith("_") and key not in ("operation","raw_pruning")}
    expected.update({k:v for k,v in cached.items() if k not in ("case_dir","ledger_dir")})
    expected.update(raw,evidence_verified=True,protocol_verified=True,protocol_issues=[])
    return expected


def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def check_csv(actual, expected, key_fields, section):
    key = lambda row:tuple(str(float(row[k])) if k in ("flow",) else str(int(row[k])) if k == "seed" else str(row[k]) for k in key_fields)
    a,b = {key(row):row for row in actual},{key(row):row for row in expected}
    assert len(a)==len(actual) and len(b)==len(expected) and set(a)==set(b), (section,"identities")
    for identity,row in a.items():
        for name,value in row.items():
            assert name in b[identity], (section,"unhandled column",name)
            compare(value,b[identity][name],str(identity)+"."+name,section)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir",type=Path,default=ROOT/"E_heldout90")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("new output required")
    summary=seal_case.read(args.report_dir/"summary.json")
    before={name:seal_case.sha(args.report_dir/name) for name in ("per_case.csv","paired_seeds.csv","flow_means.csv","summary.json","tables.md")}
    records=[row for batch in summary["batches"] for row in summarize.protocol_records(Path(batch))]
    summarize.unique(records)
    cases=[]
    for i,record in enumerate(records,1):
        cases.append(reconstruct(record))
        if i%10==0:
            print(json.dumps(dict(reconstructed=i,total=len(records))),flush=True)
    index=summarize.unique(cases)
    pairs=[]
    for target in cases:
        if target["candidate"]=="TM":
            continue
        main=target["candidate"]=="E"
        reference=index[("TM" if main else "E",target["flow"],target["seed"],target["scenario"],"noa" if main else "transform")]
        assert all(reference[key]==target[key] for key in ("demand_sha256","parameters_sha256","nonrule_source_sha256"))
        pair=dict(comparison=target["candidate"]+("-NOA" if main else "-E"),
            interpretation="same_following_complete_strategy" if main else "formation_mechanism_ablation",
            candidate=target["candidate"],reference="TM/noa" if main else "E",flow=target["flow"],seed=target["seed"],
            scenario=target["scenario"],pair_eligible=True,rejection_reasons=[])
        for prefix,case in (("reference",reference),("candidate",target)):
            pair[prefix+"_case_dir"]=case["run_dir"]
            for key in ("rules_sha256","nonrule_source_sha256","demand_sha256","parameters_sha256"):
                pair[prefix+"_"+key]=case[key]
        metrics=set(METRICS)|{key[6:] for key in read_csv(args.report_dir/"paired_seeds.csv")[0] if key.startswith("delta_")}
        for metric in metrics:
            a,b=reference.get(metric),target.get(metric)
            pair["reference_"+metric]=a
            pair["target_"+metric]=b
            pair["delta_"+metric]=b-a if a is not None and b is not None else None
        pair["system_improvement_percent"]=-100*pair["delta_mean_system_time_s"]/reference["mean_system_time_s"]
        pairs.append(pair)
    groups=defaultdict(list)
    for pair in pairs:
        groups[pair["candidate"],pair["reference"],pair["flow"],pair["scenario"]].append(pair)
    means=[]
    for (candidate,reference,flow,scenario),rows in sorted(groups.items()):
        assert len(rows)==5 and len({row["seed"] for row in rows})==5
        item=dict(candidate=candidate,reference=reference,flow=flow,scenario=scenario,seeds=5,eligible=True,
                  improved_seeds=sum(row["system_improvement_percent"]>0 for row in rows))
        for metric in METRICS:
            for prefix in ("reference_","target_","delta_"):
                item[prefix+metric]=mean([row[prefix+metric] for row in rows])
        item["system_improvement_percent"]=-100*item["delta_mean_system_time_s"]/item["reference_mean_system_time_s"]
        means.append(item)
    check_csv(read_csv(args.report_dir/"per_case.csv"),cases,summarize.IDENTITY,"per_case")
    check_csv(read_csv(args.report_dir/"paired_seeds.csv"),pairs,("candidate","flow","seed","scenario"),"paired_seeds")
    check_csv(read_csv(args.report_dir/"flow_means.csv"),means,("candidate","reference","flow","scenario"),"flow_means")
    for name,value in dict(case_count=90,protocol_verified=90,evidence_verified=90,drained=90,safe=90,pair_count=50,eligible_pairs=50,means=means).items():
        compare(summary[name],value,"summary."+name,"summary")
    show=lambda value:"—" if value is None else f"{value:.4f}"
    lines=["| "+" | ".join((row["candidate"]+"−"+row["reference"],str(row["flow"]),row["scenario"],
        show(row["reference_mean_system_time_s"])+"/"+show(row["target_mean_system_time_s"]),show(row["system_improvement_percent"]),
        str(row["improved_seeds"])+"/5",show(row["delta_fuel_g_per_km"]),show(row["delta_mean_segment_640_1100_s"]),
        show(row["delta_region_low_speed_vehicle_s"])))+" |" for row in means]
    actual=[line for line in (args.report_dir/"tables.md").read_text(encoding="utf-8").splitlines() if line.startswith("| E")]
    compare(actual,lines,"tables data rows","tables")
    assert before=={name:seal_case.sha(args.report_dir/name) for name in before}
    result=dict(case_count=len(cases),pair_count=len(pairs),flow_groups=len(means),primary_metrics=len(METRICS),
        all_parent_table_cells_checked=True,scalar_comparisons=dict(COUNTS),max_absolute_numeric_errors=dict(MAXERR),
        source_report_sha256=before,report_paired_tool_sha256=seal_case.sha(ROOT/"tools/report_paired.py"),
        reviewer_tool_sha256=seal_case.sha(__file__),means=means,
        ENP_seed_improvements=[dict(seed=row["seed"],percent=row["system_improvement_percent"]) for row in pairs if row["candidate"]=="ENP"],
        source_batch_protocol_sha256={str(batch):seal_case.sha(Path(batch)/"protocol.json") for batch in summary["batches"]},
        no_parent_report_functions_imported=True,simulations_run=False,
        geometry_recovery_verified=False,limits="Traffic/trip/flag/gate/region reconstruction does not establish complete staggered geometry or full-trajectory collision safety. The separate 24-car and 45-car demos did not show complete 30/15m recovery over the available 200m downstream; these are two vehicle-count settings, not 24 failed cases out of45.")
    seal_case.write(args.output,result)
    print(json.dumps(dict(cases=len(cases),pairs=len(pairs),flow_groups=len(means),scalar_comparisons=dict(COUNTS))),flush=True)


if __name__=="__main__":
    main()
