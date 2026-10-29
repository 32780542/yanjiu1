"""Independently recount existing completion records; never evaluate trajectories."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

OUT=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def close(a,b):assert abs(a-b)<1e-10,(a,b)


artifact=read(OUT/"artifact_hashes.json")
for name,entry in artifact["files"].items():
    assert sha(OUT/name)==entry["sha256"] and (OUT/name).stat().st_size==entry["bytes"],name
for name,digest in artifact["original_file_sha256"].items():assert sha(name)==digest,name
summary=read(OUT/"summary.json")
index=read(OUT/"source_input_result_index.json")["cases"]
assert len(index)==120
with (OUT/"runs.csv").open(encoding="utf-8-sig",newline="") as stream:
    rows=list(csv.DictReader(stream))
assert len(rows)==120
by_path={r["case_dir"]:r for r in rows};assert len(by_path)==120
computed=[];reason_counts=Counter();array_checks=0;total_events=0
for item in index:
    case=Path(item["case_dir"])
    assert sha(case/"input.json")==item["input_sha256"] and sha(case/"result.json")==item["result_sha256"]
    source,result=read(case/"input.json"),read(case/"result.json")
    assert source["source_sha256"]==result["source_sha256"]==item["source_sha256"]
    assert source["case"]["mode"]==result["mode"]==item["mode"]
    assert source["case"]["seed"]==result["seed"]==item["seed"]
    assert source["case"]["scenario"]==result["scenario"]==item["scenario"]
    events=result["lane_completion_events"]
    assert len(events)==result["lane_change_completions"]==item["recorded_lane_change_completions"]
    parts=dict(x_lt_640=sum(e["x"]<640 for e in events),x_ge640_lt1000=sum(640<=e["x"]<1000 for e in events),x_ge1000=sum(e["x"]>=1000 for e in events))
    assert sum(parts.values())==len(events)
    assert all(abs(e["y"]-(1.65+3.3*e["to_lane"]))<.05 and abs(e["vy"])<.05 for e in events)
    assert all("reason" not in e for e in events)
    row=by_path[str(case)];requested=result["requested"]
    assert int(row["requested"])==requested==len(source["arrivals"])
    assert int(row["lane_change_completions"])==len(events)
    close(float(row["LC_per_requested_vehicle"]),len(events)/requested)
    for name,value in parts.items():
        assert int(row[name])==value
        close(float(row[name+"_LC_per_requested_vehicle"]),value/requested)
    assert result["action_reasons"]==item["original_action_reasons"]
    for reason,count in result["action_reasons"].items():
        reason_counts[(item["cohort"],item["source_version_sha256"],item["flow_veh_h_lane"],item["seed"],item["scenario"],item["mode"],reason)]+=count
    if item["cohort"]=="C1_P_strict":
        assert item["parameters_sha256"]==item["paired_P_transform_parameters_sha256"]
    computed.append(dict(**{name:item[name] for name in ("cohort","source_version_sha256","flow_veh_h_lane","seed","scenario","mode")},requested=requested,total=len(events),parts=parts))
    array_checks+=1;total_events+=len(events)
assert sum(x["requested"] for x in computed if x["cohort"]=="P100")==summary["P100_requested"]==48060
assert sum(x["requested"] for x in computed if x["cohort"]=="C1_P_strict")==summary["C1_P_requested"]==9612
grouped=defaultdict(list)
for row in computed:grouped[tuple(row[k] for k in ("cohort","source_version_sha256","flow_veh_h_lane","scenario","mode"))].append(row)
assert len(grouped)==len(summary["groups"])==24
for group in summary["groups"]:
    key=tuple(group[k] for k in ("cohort","source_version_sha256","flow_veh_h_lane","scenario","mode"))
    rs=grouped[key];assert len(rs)==5 and {r["seed"] for r in rs}=={6,7,8,9,10}
    assert sum(r["requested"] for r in rs)==group["requested_total"]
    assert sum(r["total"] for r in rs)==group["completed_LC_total"]
    close(mean(r["total"]/r["requested"] for r in rs),group["mean_run_LC_per_requested_vehicle"])
    close(sum(r["total"] for r in rs)/sum(r["requested"] for r in rs),group["pooled_LC_per_requested_vehicle"])
    for part in ("x_lt_640","x_ge640_lt1000","x_ge1000"):
        assert sum(r["parts"][part] for r in rs)==group[part+"_total"]
        close(mean(r["parts"][part]/r["requested"] for r in rs),group[part+"_mean_run_LC_per_requested_vehicle"])
with (OUT/"action_reason_runs.csv").open(encoding="utf-8-sig",newline="") as stream:
    actual=Counter({(r["cohort"],r["source_version_sha256"],float(r["flow_veh_h_lane"]),int(r["seed"]),r["scenario"],r["mode"],r["reason"]):int(r["decision_tick_count"]) for r in csv.DictReader(stream)})
assert actual==reason_counts
group_reason=Counter()
for key,count in reason_counts.items():group_reason[(key[0],key[1],key[2],key[4],key[5],key[6])]+=count
with (OUT/"action_reason_groups.csv").open(encoding="utf-8-sig",newline="") as stream:
    actual=Counter({(r["cohort"],r["source_version_sha256"],float(r["flow_veh_h_lane"]),r["scenario"],r["mode"],r["reason"]):int(r["decision_tick_count"]) for r in csv.DictReader(stream)})
assert actual==group_reason
for context in summary["existing_P_context"]:
    assert sha(context["original_context_file"])==context["original_context_sha256"]
    original=read(context["original_context_file"])
    row=next(r for r in original["run_means"] if r["flow_veh_h_lane"]==context["flow_veh_h_lane"] and r["scenario"]==context["scenario"] and r["mode"]==context["mode"])
    for name in ("mean_segment_100_600_s_mean","mean_segment_640_1100_s_mean","mean_segment_800_1100_s_mean","mean_travel_time_s_mean"):
        assert context[name]==row[name]
    native=next(r for r in original["native_run_means"][f"{context['flow_veh_h_lane']:g}"] if r["scenario"]==context["scenario"] and r["mode"]==context["mode"])
    assert context["upstream_full_multilayer_participation"]==native.get("upstream_formation_participation_rate_mean")
    assert context["straight_whole_full_multilayer_participation"]==native.get("whole_formation_participation_rate_mean")
assert not summary["event_reason_link_available"]
result=dict(passed=True,cases_checked=array_checks,P_cases=100,C1_P_cases=20,P_requests=48060,C1_P_requests=9612,strict_completion_events_recounted=total_events,all_event_array_lengths_equal_recorded_counts=True,all_spatial_partition_sums_equal=True,all_requested_vehicle_denominators_match=True,all_source_input_result_hashes_match=True,action_reason_tick_tables_match_originals=True,source_label_seed_cohorts_separate=True,C1_P_parent_parameter_hashes_equal=True,existing_time_and_participation_values_copied_exactly=True,no_rule_specific_causality_inferred=True,no_traffic_metric_recalculation=True,no_simulation=True,originals_unchanged=True)
(OUT/"verification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result))
