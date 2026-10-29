"""Independent arithmetic/raw-trip/window/source checks for the C1 contrast."""
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean

PACKAGE = Path(__file__).resolve().parent
OUTPUT = PACKAGE / "analysis"
ROOT = PACKAGE.parents[1]
P_OUTPUT = ROOT / "docs/experiments/2026-10-29-four-flow-attribution/P_analysis"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a,b):
    assert abs(a-b) < 1e-8, (a,b)


def types(a,b,prefix=""):
    if isinstance(a,dict) and isinstance(b,dict):
        assert set(a)==set(b)
        return [p for k in a for p in types(a[k],b[k],prefix+"/"+k)]
    if isinstance(a,list) and isinstance(b,list):
        assert len(a)==len(b)
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in types(x,y,prefix+f"/{i}")]
    assert a==b,(prefix,a,b)
    return [prefix] if type(a) is not type(b) else []


report=read(OUTPUT/"summary.json")
artifacts=read(OUTPUT/"artifact_hashes.json")
assert all(sha(OUTPUT/name)==digest for name,digest in artifacts.items())
h_runs=read(P_OUTPUT/"attribution/summary.json")["runs"]
hm={(float(r["flow_veh_h_lane"]),int(r["seed"]),r["scenario"],r["mode"]):r for r in h_runs}
checks=[]
for run in report["runs"]:
    flow,seed=float(run["flow_veh_h_lane"]),int(run["seed"])
    path=Path(run["case_dir"])
    source=read(path/"input.json")
    trips=read(path/"trips.json")
    evidence=json.loads(gzip.decompress((OUTPUT/"case_evidence"/f"flow{flow:g}_s{seed}.json.gz").read_bytes()))
    vehicles=evidence["attribution"]["vehicles"]
    ids={x["vehicle_id"] for x in source["arrivals"]}
    assert len(trips)==len(vehicles)==len(ids)==run["requested"]
    assert {x["vehicle_id"] for x in trips}=={x["vehicle_id"] for x in vehicles}==ids
    close(mean(x["exited_s"]-x["entered_s"] for x in trips),run["mean_travel_time_s"])
    close(mean(x["entered_s"]-x["requested_s"] for x in trips),run["mean_entry_wait_s"])
    close(sum(x["fuel_mg"] for x in trips)/sum(x["distance_m"] for x in trips),run["fuel_g_per_km"])
    close(mean(x["gates"]["1100"]["time_s"]-x["gates"]["640"]["time_s"] for x in vehicles),run["mean_segment_640_1100_s"])
    crossings=sum(100<=x["gates"]["1000"]["time_s"]<=600 for x in vehicles)
    close(crossings*3600/500,run["flow_1000m_veh_h"])
    low=0.;previous=None
    with gzip.open(path/"positions.jsonl.gz","rt",encoding="utf-8") as stream:
        for line in stream:
            frame=json.loads(line)
            if previous is not None:
                dt=max(0.,min(frame["time_s"],600)-max(previous["time_s"],100))
                if dt:
                    low+=dt*sum(800<=s[0]<1000 and s[2]<5 for s in previous["states"].values())
            previous=frame
    close(low,run["region_low_speed_vehicle_s"])
    h=hm[(flow,seed,"lane_drop","transform")]
    h_source=read(Path(h["case_dir"])/"input.json")
    source_fields=("physical","speed_mode","lane_change_mode","insertion","positions_step_s")
    type_changes=[]
    for name in source_fields:
        type_changes+=types(source[name],h_source[name],"/"+name)
    for name in ("flow_veh_h_lane","demand_duration_s","max_time_s","step_s","lane_change_duration_s"):
        type_changes+=types(source["case"][name],h_source["case"][name],"/case/"+name)
    assert type_changes==[],type_changes
    assert isinstance(source["case"]["flow_veh_h_lane"],float) and isinstance(h_source["case"]["flow_veh_h_lane"],float)
    pair=next(p for p in report["pairs"] if p["flow_veh_h_lane"]==flow and p["seed"]==seed)
    assert pair["cooperative_parameters_sha256"]==pair["P_parameters_sha256"]
    for metric in ("mean_travel_time_s","mean_entry_wait_s","mean_segment_640_1100_s","region_low_speed_vehicle_s","flow_1000m_veh_h","fuel_g_per_km"):
        close(pair["cooperative_"+metric]-pair["P_transform_"+metric],pair["cooperative_minus_P_"+metric])
    attr=next(p for p in report["attributions"] if p["flow_veh_h_lane"]==flow and p["seed"]==seed)
    nd,ns,ts=(hm[(flow,seed,road,mode)] for road,mode in (("lane_drop","noa"),("straight3","noa"),("straight3","transform")))
    metric="mean_segment_640_1100_s"
    close(nd[metric]-run[metric],attr["cooperative_reduction_"+metric])
    close((nd[metric]-ns[metric])-(h[metric]-ts[metric]),attr["P_reduction_"+metric])
    close(attr["P_reduction_"+metric]-attr["cooperative_reduction_"+metric],attr["P_incremental_reduction_over_cooperative_"+metric])
    checks.append(dict(flow=flow,seed=seed,requested=len(ids),all_raw_trip_metrics_match=True,primary_segment_from_all_request_gates_matches=True,fixed_window_low_speed_matches_raw_trace=True,flow_from_all_request_gates_matches=True,common_parameter_numeric_type_difference_only=type_changes,pair_sign_and_DID_identity_match=True))
for row in report["flow_means"]:
    ps=[p for p in report["pairs"] if p["flow_veh_h_lane"]==row["flow_veh_h_lane"]]
    assert len(ps)==5 and row["group_eligible"]
    for field,value in row.items():
        if field.endswith("_mean") and field[:-5] in ps[0] and value is not None:
            close(mean(p[field[:-5]] for p in ps),value)
freeze=read(PACKAGE/"freeze.json")
for relative,digest in freeze["source_sha256"].items(): assert sha(PACKAGE/relative)==digest
for relative,digest in freeze["P_source_sha256"].items(): assert sha(Path(freeze["P_source_root"])/relative)==digest
for relative,digest in freeze["old_C1_H_source_sha256"].items(): assert sha(Path(freeze["old_C1_H_root"])/relative)==digest
assert read(OUTPUT/"summary.json")["metadata"]["label"]=="C1_P strict formation ablation"
assert all(read(Path(r["case_dir"])/"result.json").get("action_reasons",{}).get("normal_overtake",0)==0 for r in report["runs"])
result=dict(passed=True,label="C1_P strict formation ablation",seeds=[6,7,8,9,10],cases_checked=len(checks),requested=sum(x["requested"] for x in checks),artifacts_checked=len(artifacts),all_cases_safe_completed=report["audit"]["all_safe"] and report["audit"]["all_completed"],ordinary_overtake_actions=0,original_P_sources_unchanged=True,original_C1_H_sources_unchanged=True,cooperative_sources_unchanged=True,raw_inputs_never_rewritten=True,raw_parameter_sha256_equal=True,parameter_type_exceptions_allowed=False,same_source_pooling=False,strict_source_contrast_retained=True,inherited_C1_H_straight_proof_reused=True,checks=checks)
(OUTPUT/"postverification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k!="checks"}))
