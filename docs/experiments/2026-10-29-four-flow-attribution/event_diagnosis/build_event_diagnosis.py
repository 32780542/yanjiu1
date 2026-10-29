"""Read-only completed-event diagnosis; no traffic evaluator/controller imports."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[3]
P_STUDY=PROJECT/"variants/phase5g_pure_formation/results/flow_attribution_P_heldout/20261029T033726974665Z"
C1_STUDY=PROJECT/"tmp/common_pair_P_strict_ablation/results/20261029T034544698651Z"
P_ANALYSIS=PROJECT/"docs/experiments/2026-10-29-four-flow-attribution/P_analysis"
PARTS=("x_lt_640","x_ge640_lt1000","x_ge1000")
original_hashes={}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    old=original_hashes.setdefault(str(path.resolve()),digest)
    assert old==digest
    return json.loads(raw.decode("utf-8"))


def write(name,value):
    path=OUT/name
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")


def csv_write(name,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,keys);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def digest_object(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def parameters(source,result):
    p={k:source.get(k) for k in ("physical","speed_mode","lane_change_mode","insertion","positions_step_s")}
    p["case"]={k:source["case"][k] for k in ("flow_veh_h_lane","demand_duration_s","max_time_s","step_s","lane_change_duration_s")}
    p["case"].update({k:source["case"].get(k) for k in ("request_acceleration_limit_mps2","request_deceleration_limit_mps2")})
    p["sumo_version"]=result.get("sumo_version")
    return p


assert not (OUT/"summary.json").exists()
assert read(P_ANALYSIS/"analysis_status.json")["status"]=="completed"
assert read(P_ANALYSIS/"postverification.json")["passed"]
overview=read(P_ANALYSIS/"analysis_overview.json")
existing_context=[]
for row in overview["run_means"]:
    flow,scenario,mode=row["flow_veh_h_lane"],row["scenario"],row["mode"]
    native=next(x for x in overview["native_run_means"][f"{flow:g}"] if x["scenario"]==scenario and x["mode"]==mode)
    context=dict(cohort="P100",flow_veh_h_lane=flow,scenario=scenario,mode=mode,
        mean_segment_100_600_s_mean=row["mean_segment_100_600_s_mean"],
        mean_segment_640_1100_s_mean=row["mean_segment_640_1100_s_mean"],
        mean_segment_800_1100_s_mean=row["mean_segment_800_1100_s_mean"],
        mean_travel_time_s_mean=row["mean_travel_time_s_mean"],
        upstream_full_multilayer_participation=native.get("upstream_formation_participation_rate_mean"),
        downstream_full_multilayer_participation=native.get("downstream_formation_participation_rate_mean"),
        straight_whole_full_multilayer_participation=native.get("whole_formation_participation_rate_mean"),
        original_context_file=str(P_ANALYSIS/"analysis_overview.json"),
        original_context_sha256=original_hashes[str((P_ANALYSIS/"analysis_overview.json").resolve())],
        copied_existing_values_only=True)
    existing_context.append(context)

runs=[];index=[];reasons=[];cohorts=[];p_parameters={}
for label,study,expected_count in (("P100",P_STUDY,100),("C1_P_strict",C1_STUDY,20)):
    protocol=read(study/"protocol.json")
    manifest=read(study/"manifest.json")
    status=read(study/"run_status.json")
    paths=[(study/p).resolve() for p in manifest["cases"]]
    assert len(paths)==len(set(paths))==len(status)==expected_count
    assert set(protocol["flows"])=={500,750,1000,1500} and set(protocol["seeds"])=={6,7,8,9,10}
    assert {str(p) for p in paths}=={str(Path(r["run_dir"]).resolve()) for r in status}
    seen=set()
    for path in paths:
        assert path.is_relative_to(study.resolve())
        source,result=read(path/"input.json"),read(path/"result.json")
        config=source["case"]
        flow,seed,scenario,mode=config["flow_veh_h_lane"],config["seed"],config["scenario"],config["mode"]
        key=(flow,seed,scenario,mode);assert key not in seen;seen.add(key)
        assert result["source_sha256"]==source["source_sha256"]==protocol["source_sha256"]
        for name,digest in protocol["source_sha256"].items():
            file=path/"source"/name
            actual=sha(file);assert actual==digest
            original_hashes[str(file.resolve())]=actual
        assert result["safe"] and result["all_completed"] and result["status"]=="drained"
        assert result["mode"]==mode and result["seed"]==seed and result["scenario"]==scenario
        requested=result["requested"];assert requested==len(source["arrivals"])==result["completed"]
        ids={x["vehicle_id"] for x in source["arrivals"]}
        events=result["lane_completion_events"]
        assert len(events)==result["lane_change_completions"]
        count=Counter();directions=Counter()
        for event in events:
            x,y,vy,time=(event[k] for k in ("x","y","vy","time_s"))
            assert all(isinstance(v,(int,float)) and math.isfinite(v) for v in (x,y,vy,time))
            assert event["vehicle_id"] in ids and event["to_lane"] in (0,1,2) and abs(event["to_lane"]-event["from_lane"])==1
            assert abs(y-(1.65+3.3*event["to_lane"]))<.05 and abs(vy)<.05
            assert time>=event["requested_s"]
            assert "reason" not in event
            part=PARTS[0] if x<640 else PARTS[1] if x<1000 else PARTS[2]
            count[part]+=1;directions[f"{event['from_lane']}->{event['to_lane']}"]+=1
        assert sum(count.values())==len(events)
        source_version=digest_object(protocol["source_sha256"])
        row=dict(cohort=label,source_version_sha256=source_version,flow_veh_h_lane=flow,seed=seed,scenario=scenario,mode=mode,case_dir=str(path),requested=requested,completed=result["completed"],lane_change_completions=len(events),LC_per_requested_vehicle=len(events)/requested,
            **{part:count[part] for part in PARTS},
            **{part+"_LC_per_requested_vehicle":count[part]/requested for part in PARTS},
            completion_array_equals_recorded_count=True,partition_sum_equals_total=True,strict_event_geometry_valid=True,action_reasons_are_not_completion_counts=True)
        runs.append(row)
        for reason,ticks in result["action_reasons"].items():
            assert type(ticks) is int and ticks>=0
            reasons.append(dict(cohort=label,source_version_sha256=source_version,flow_veh_h_lane=flow,seed=seed,scenario=scenario,mode=mode,reason=reason,decision_tick_count=ticks,not_successful_LC_count=True))
        param=parameters(source,result);param_sha=digest_object(param)
        parent_sha=None
        if label=="P100" and scenario=="lane_drop" and mode=="transform":p_parameters[(flow,seed)]=param_sha
        if label=="C1_P_strict":
            assert scenario=="lane_drop" and mode=="cooperative"
            parent_sha=p_parameters[(flow,seed)]
            assert param_sha==parent_sha
        index.append(dict(cohort=label,case_dir=str(path),flow_veh_h_lane=flow,seed=seed,scenario=scenario,mode=mode,input_sha256=original_hashes[str((path/"input.json").resolve())],result_sha256=original_hashes[str((path/"result.json").resolve())],source_sha256=protocol["source_sha256"],source_version_sha256=source_version,parameters_sha256=param_sha,paired_P_transform_parameters_sha256=parent_sha,original_action_reasons=result["action_reasons"],recorded_lane_change_completions=result["lane_change_completions"]))
    if label=="P100":
        expected={(f,s,road,m) for f in protocol["flows"] for s in protocol["seeds"] for road,modes in (("straight3",("noa","transform")),("lane_drop",("noa","formation","transform"))) for m in modes}
    else:expected={(f,s,"lane_drop","cooperative") for f in protocol["flows"] for s in protocol["seeds"]}
    assert seen==expected
    cohorts.append(dict(label=label,study_dir=str(study),cases=expected_count,seeds=protocol["seeds"],flows=protocol["flows"],source_sha256=protocol["source_sha256"],protocol_sha256=original_hashes[str((study/"protocol.json").resolve())],manifest_sha256=original_hashes[str((study/"manifest.json").resolve())]))

grouped=defaultdict(list)
for row in runs:grouped[(row["cohort"],row["source_version_sha256"],row["flow_veh_h_lane"],row["scenario"],row["mode"])].append(row)
groups=[]
for (cohort,version,flow,scenario,mode),rows in sorted(grouped.items()):
    assert len(rows)==5 and {r["seed"] for r in rows}=={6,7,8,9,10}
    requested=sum(r["requested"] for r in rows);events=sum(r["lane_change_completions"] for r in rows)
    groups.append(dict(cohort=cohort,source_version_sha256=version,flow_veh_h_lane=flow,scenario=scenario,mode=mode,runs=5,seeds=[6,7,8,9,10],requested_total=requested,completed_LC_total=events,mean_completed_LC_per_run=events/5,mean_run_LC_per_requested_vehicle=mean(r["LC_per_requested_vehicle"] for r in rows),pooled_LC_per_requested_vehicle=events/requested,**{part+"_total":sum(r[part] for r in rows) for part in PARTS},**{part+"_mean_run_LC_per_requested_vehicle":mean(r[part+"_LC_per_requested_vehicle"] for r in rows) for part in PARTS}))
reason_groups=defaultdict(int)
for row in reasons:reason_groups[tuple(row[k] for k in ("cohort","source_version_sha256","flow_veh_h_lane","scenario","mode","reason"))]+=row["decision_tick_count"]
reason_summary=[dict(zip(("cohort","source_version_sha256","flow_veh_h_lane","scenario","mode","reason"),key),decision_tick_count=value,not_successful_LC_count=True) for key,value in sorted(reason_groups.items())]
comparisons=[]
for flow in (500,750,1000,1500):
    for scenario in ("straight3","lane_drop"):
        tf=next(g for g in groups if g["cohort"]=="P100" and g["flow_veh_h_lane"]==flow and g["scenario"]==scenario and g["mode"]=="transform")
        noa=next(g for g in groups if g["cohort"]=="P100" and g["flow_veh_h_lane"]==flow and g["scenario"]==scenario and g["mode"]=="noa")
        tc=next(c for c in existing_context if c["flow_veh_h_lane"]==flow and c["scenario"]==scenario and c["mode"]=="transform")
        nc=next(c for c in existing_context if c["flow_veh_h_lane"]==flow and c["scenario"]==scenario and c["mode"]=="noa")
        comparisons.append(dict(cohort="P100",flow_veh_h_lane=flow,scenario=scenario,source_version_sha256=tf["source_version_sha256"],TF_mean_run_LC_per_requested_vehicle=tf["mean_run_LC_per_requested_vehicle"],NOA_mean_run_LC_per_requested_vehicle=noa["mean_run_LC_per_requested_vehicle"],extra_mean_run_LC_per_requested_vehicle=tf["mean_run_LC_per_requested_vehicle"]-noa["mean_run_LC_per_requested_vehicle"],extra_pre640_mean_run_LC_per_requested_vehicle=tf[PARTS[0]+"_mean_run_LC_per_requested_vehicle"]-noa[PARTS[0]+"_mean_run_LC_per_requested_vehicle"],TF_mean_segment_100_600_s_existing=tc["mean_segment_100_600_s_mean"],NOA_mean_segment_100_600_s_existing=nc["mean_segment_100_600_s_mean"],TF_minus_NOA_segment_100_600_s_existing=tc["mean_segment_100_600_s_mean"]-nc["mean_segment_100_600_s_mean"],TF_upstream_full_multilayer_participation_existing=tc["upstream_full_multilayer_participation"],TF_straight_whole_full_multilayer_participation_existing=tc["straight_whole_full_multilayer_participation"],descriptive_only_not_rule_causality=True))

summary=dict(scope="Existing strict completion events and action reason counters only; no new traffic evaluation standard or simulation",cohorts=cohorts,partition_definition={"x_lt_640":"completion x<640","x_ge640_lt1000":"640<=completion x<1000","x_ge1000":"completion x>=1000"},all_arrays_match_recorded_counts=True,all_partition_sums_match=True,all_events_pass_recorded_strict_completion_geometry=True,P100_requested=sum(r["requested"] for r in runs if r["cohort"]=="P100"),C1_P_requested=sum(r["requested"] for r in runs if r["cohort"]=="C1_P_strict"),event_reason_link_available=False,action_reason_warning="Counters are repeated decision ticks, not lane changes, successes or a one-to-one event/rule attribution; no per-region action reason count can be recovered from aggregate result counters",groups=groups,existing_P_context=existing_context,descriptive_comparisons=comparisons,mechanism_boundary="Extra measured lateral completions and upstream delay can coexist. Counts alone do not identify _fill/helper/other rules as the whole cause; the formation/speed/transient effects and interactions remain inseparable in this event-only diagnosis.")
write("summary.json",summary);write("source_input_result_index.json",dict(cases=index,original_file_sha256=original_hashes))
for name,rows in (("runs.csv",runs),("groups.csv",groups),("action_reason_runs.csv",reasons),("action_reason_groups.csv",reason_summary),("P_existing_context.csv",existing_context),("P_transform_vs_NOA_descriptive.csv",comparisons)):
    csv_write(name,rows)
for path,expected in original_hashes.items():assert sha(path)==expected,"Original changed during diagnosis: "+path
files={str(p.relative_to(OUT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in OUT.iterdir() if p.is_file() and p.name not in ("artifact_hashes.json","verification.json")}
write("artifact_hashes.json",dict(files=files,originals_unchanged=True,original_file_sha256=original_hashes,verification_output_excluded=True))
print(json.dumps(dict(output=str(OUT),runs=len(runs),groups=len(groups),P100_requested=summary["P100_requested"],C1_P_requested=summary["C1_P_requested"],completed_LC_total=sum(r["lane_change_completions"] for r in runs),all_arrays_and_partitions_match=True,descriptive_comparisons=comparisons)),flush=True)
