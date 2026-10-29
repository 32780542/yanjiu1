"""C1_P strict formation ablation versus heldout P; frozen metrics, seeds6–10 only."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from statistics import mean
import sys

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
STUDY = PACKAGE / "results/20261029T034544698651Z"
OPERATION = ROOT / "results/operations/20261029T034544274513Z_C1_P-heldout-twenty-drop_3fd04f54"
P_ANALYSIS = ROOT / "docs/experiments/2026-10-29-four-flow-attribution/P_analysis"
OUTPUT = PACKAGE / "analysis"
sys.path.insert(0, str(PACKAGE / "analysis_source"))
from experiments import bottleneck_attribution as b
from experiments import native_comparison as n


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def csv_write(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v for k,v in row.items()})


def key(row):
    return float(row["flow_veh_h_lane"]), int(row["seed"]), row["scenario"], row["mode"]


def recorded_common_parameters(path):
    source, result = read(Path(path) / "input.json"), read(Path(path) / "result.json")
    case = source["case"]
    parameters = {name: source.get(name) for name in ("physical", "speed_mode", "lane_change_mode", "insertion", "positions_step_s")}
    parameters["case"] = {name: case[name] for name in ("flow_veh_h_lane", "demand_duration_s", "max_time_s", "step_s", "lane_change_duration_s")}
    parameters["case"].update({name:case.get(name) for name in ("request_acceleration_limit_mps2", "request_deceleration_limit_mps2")})
    parameters["sumo_version"] = result.get("sumo_version")
    return parameters


if OUTPUT.exists():
    raise FileExistsError(OUTPUT)
outer = read(OPERATION / "result.json")
assert outer["status"] == "completed" and outer["returncode"] == 0
freeze, base = read(PACKAGE / "freeze.json"), read(PACKAGE / "base_manifest.json")
protocol = read(STUDY / "protocol.json")
assert protocol["source_sha256"] == freeze["source_sha256"]
assert protocol["wrapper_sha256"] == freeze["wrapper_sha256"] == sha(STUDY / "run_flow_study.py")
assert protocol["case_count"] == 20 and protocol["jobs"] == 2 and protocol["reuse_H_noa_straight"]
assert set(protocol["seeds"]) == {6,7,8,9,10} and len(protocol["seeds"]) == 5
assert all(type(flow) is float for flow in protocol["flows"])
assert protocol["duration_s"] == 600 and protocol["max_time_s"] == 900
assert protocol["label"] == freeze["label"] == "C1_P strict formation ablation"
assert protocol["policy"] == "C1_P_strict_formation_ablation" and not protocol["normal_overtake"]
inheritance = read(PACKAGE / "straight_equivalence_inheritance.json")
assert inheritance["fixed_state_actions_and_Memory_identical"] and inheritance["new_pair_following_fill_unexecuted"]
assert inheritance["C0_report_sha256"] == sha(PACKAGE / "straight_equivalence_report.json")
assert read(PACKAGE / "straight_equivalence_report.json")["reuse_H_noa_straight"]
h_post, h_audit = read(P_ANALYSIS / "postverification.json"), read(P_ANALYSIS / "data_audit.json")
assert h_post["passed"] and h_audit["passed"] and h_audit["case_count"] == 100
assert h_audit["protocol"]["source_sha256"] == base["source_sha256"]
paths = [Path(p).resolve() for p in read(STUDY / "manifest.json")["cases"]]
records = read(STUDY / "run_status.json")
assert len(paths) == len(set(paths)) == len(records) == 20
assert {str(p) for p in paths} == {str(Path(r["run_dir"]).resolve()) for r in records}
expected = {(float(flow),seed,"lane_drop","cooperative") for flow in (500,750,1000,1500) for seed in range(6,11)}
actual = set()
for path in paths:
    assert path.is_relative_to(STUDY.resolve())
    source, result = read(path / "input.json"), read(path / "result.json")
    config = source["case"]
    actual.add((float(config["flow_veh_h_lane"]),int(config["seed"]),config["scenario"],config["mode"]))
    assert config["mode"] == result["mode"] == "cooperative"
    assert config["demand_duration_s"] == 600 and config["max_time_s"] == 900
    assert source["source_sha256"] == result["source_sha256"] == freeze["source_sha256"]
    for relative, digest in freeze["source_sha256"].items():
        assert sha(path / "source" / relative) == digest
assert actual == expected
assert {str(p.parent.resolve()) for p in STUDY.glob("flow_*/*/input.json")} == {str(p) for p in paths}
for relative,digest in freeze["source_sha256"].items():
    assert sha(PACKAGE / relative) == digest
for relative,digest in freeze["old_C1_H_source_sha256"].items():
    assert sha(Path(freeze["old_C1_H_root"]) / relative) == digest
for relative,digest in base["source_sha256"].items():
    assert sha(Path(base["source_root"]) / relative) == digest
for relative,digest in base["configs_sha256"].items():
    assert sha(PACKAGE / relative) == digest
analysis_freeze = read(PACKAGE / "analysis_source/freeze.json")
for relative,digest in analysis_freeze["source_sha256"].items():
    assert sha(PACKAGE / "analysis_source" / relative) == digest

h_attr = {key(row):row for row in read(P_ANALYSIS / "attribution/summary.json")["runs"]}
h_native = {}
for flow in (500,750,1000,1500):
    for row in read(P_ANALYSIS / f"flow_{flow}/native_comparison/summary.json")["runs"]:
        h_native[(float(row.get("flow_veh_h_lane",flow)),int(row["seed"]),row["scenario"],row["mode"])] = row
OUTPUT.mkdir()
(OUTPUT / "case_evidence").mkdir()
shutil.copyfile(__file__, OUTPUT / "analyze_cooperative.source.py")
write(OUTPUT / "analysis_status.json", dict(status="running", audited_manifest_cases=20))
run_rows, pairs, attribution_rows = [], [], []
P_FIELDS = ("upstream_formation_participation_rate", "downstream_formation_participation_rate", "upstream_stable_participation_rate", "downstream_stable_participation_rate")
METRICS = (*b.METRICS, "fuel_g_per_km", *P_FIELDS)
for path in sorted(paths, key=lambda p:(read(p/"input.json")["case"]["flow_veh_h_lane"],read(p/"input.json")["case"]["seed"])):
    native = n.load_case(path)
    evaluated = b.evaluate_case(path)
    flow,seed,_,_ = key(evaluated)
    h_tf = h_attr[(flow,seed,"lane_drop","transform")]
    h_st = h_attr[(flow,seed,"straight3","transform")]
    h_nd = h_attr[(flow,seed,"lane_drop","noa")]
    h_ns = h_attr[(flow,seed,"straight3","noa")]
    hn = h_native[(flow,seed,"lane_drop","transform")]
    cooperative_parameters = recorded_common_parameters(path)
    P_parameters = recorded_common_parameters(h_tf["case_dir"])
    assert n._digest(cooperative_parameters) == native["parameters_sha256"]
    assert n._digest(P_parameters) == hn["parameters_sha256"]
    assert native["parameters_sha256"] == hn["parameters_sha256"], "Raw P/C1_P parameter SHA differs; normalization is forbidden"
    assert cooperative_parameters == P_parameters, "Actual common control parameters differ"
    assert evaluated["demand_sha256"] == h_tf["demand_sha256"] == h_nd["demand_sha256"]
    assert evaluated["requested"] == h_tf["requested"] == h_nd["requested"]
    for ref in (h_tf,h_st,h_nd,h_ns):
        case = Path(ref["case_dir"])
        for field,name in (("input_sha256","input.json"),("result_sha256","result.json"),("positions_sha256","positions.jsonl.gz")):
            assert sha(case/name) == ref[field]
        assert ref["source_sha256"] == base["source_sha256"]
        for relative,digest in base["source_sha256"].items():
            assert sha(case/"source"/relative) == digest
    compact = {k:v for k,v in evaluated.items() if k not in ("vehicles","region_steps")}
    compact.update({name:native.get(name) for name in ("fuel_g_per_km",*P_FIELDS,"upstream_peak_multilayer_size","downstream_peak_multilayer_size")})
    assert read(path / "result.json").get("action_reasons", {}).get("normal_overtake", 0) == 0
    run_rows.append(compact)
    evidence = dict(attribution=evaluated,native=native)
    with gzip.open(OUTPUT/"case_evidence"/f"flow{flow:g}_s{seed}.json.gz","wt",encoding="utf-8",compresslevel=5) as stream:
        json.dump(evidence,stream,ensure_ascii=False,allow_nan=False)
    reasons = []
    if not evaluated["attribution_eligible"]: reasons.append("cooperative_ineligible:"+";".join(evaluated["audit_issues"]))
    if not h_tf["attribution_eligible"]: reasons.append("P_transform_ineligible")
    pair = dict(flow_veh_h_lane=flow,seed=seed,pair_eligible=not reasons,rejection_reasons=reasons,cooperative_case_dir=str(path),P_transform_case_dir=h_tf["case_dir"],source_contrast="C1_P deliberate forming/fill ablation; source hashes retained separately",cooperative_source_version_sha256=evaluated["source_version_sha256"],P_source_version_sha256=h_tf["source_version_sha256"],cooperative_parameters_sha256=native["parameters_sha256"],P_parameters_sha256=hn["parameters_sha256"],recorded_common_parameters_equal=True,raw_parameter_sha256_equal=True,parameter_representation_note="Both P and C1_P use explicit float flows; raw parameter hashes and field types equal; no normalization exception",demand_sha256=evaluated["demand_sha256"])
    for metric in METRICS:
        cv=compact.get(metric)
        hv=hn.get(metric) if metric in ("fuel_g_per_km",*P_FIELDS) else h_tf.get(metric)
        pair["cooperative_"+metric],pair["P_transform_"+metric]=cv,hv
        pair["cooperative_minus_P_"+metric]=cv-hv if not reasons and cv is not None and hv is not None else None
    pairs.append(pair)
    ar=dict(flow_veh_h_lane=flow,seed=seed,pair_eligible=not reasons and all(x["attribution_eligible"] for x in (h_st,h_nd,h_ns)),cooperative_straight_control="same H NOA straight by complete NOA delegation; static and actual strict-equivalence evidence",cooperative_drop_case=str(path),P_noa_straight_case=h_ns["case_dir"],P_transform_straight_case=h_st["case_dir"],P_noa_drop_case=h_nd["case_dir"],P_transform_drop_case=h_tf["case_dir"])
    for metric in b.METRICS:
        values=(h_nd.get(metric),h_ns.get(metric),h_tf.get(metric),h_st.get(metric),compact.get(metric))
        if ar["pair_eligible"] and all(v is not None for v in values):
            nd,ns,td,ts,cd=values
            noa_added=nd-ns;P_added=td-ts;C0_added=cd-ns
            ar["P_reduction_"+metric]=noa_added-P_added
            ar["cooperative_reduction_"+metric]=noa_added-C0_added
            ar["P_incremental_reduction_over_cooperative_"+metric]=C0_added-P_added
        else:
            for prefix in ("P_reduction_","cooperative_reduction_","P_incremental_reduction_over_cooperative_"):
                ar[prefix+metric]=None
    attribution_rows.append(ar)
    write(OUTPUT/"analysis_status.json",dict(status="running",cases_finished=len(run_rows),total_cases=20))
    print(json.dumps(dict(label="C1_P strict formation ablation",flow=flow,seed=seed,eligible=pair["pair_eligible"],cooperative_tt=compact["mean_travel_time_s"],P_tt=h_tf["mean_travel_time_s"],C1_minus_P_tt=pair["cooperative_minus_P_mean_travel_time_s"])),flush=True)

means=[]
for flow in (500.,750.,1000.,1500.):
    rows=[p for p in pairs if p["flow_veh_h_lane"]==flow]
    attrs=[p for p in attribution_rows if p["flow_veh_h_lane"]==flow]
    eligible=len(rows)==5 and all(p["pair_eligible"] for p in rows)
    item=dict(flow_veh_h_lane=flow,attempted_n=len(rows),eligible_n=sum(p["pair_eligible"] for p in rows),group_eligible=eligible)
    for k in rows[0]:
        if k.startswith(("cooperative_","P_transform_")) and isinstance(rows[0][k],(int,float)):
            item[k+"_mean"]=mean(p[k] for p in rows) if eligible and all(p[k] is not None for p in rows) else None
    for k in attrs[0]:
        if k.startswith(("P_reduction_","cooperative_reduction_","P_incremental_reduction_over_cooperative_")):
            item[k+"_mean"]=mean(p[k] for p in attrs) if eligible and all(p["pair_eligible"] and p[k] is not None for p in attrs) else None
    means.append(item)
audit=dict(passed=True,cases=20,requested=sum(r["requested"] for r in run_rows),completed=sum(r["completed"] for r in run_rows),all_safe=all(r["safe"] for r in run_rows),all_completed=all(r["all_completed"] for r in run_rows),attribution_eligible=sum(r["attribution_eligible"] for r in run_rows),source_snapshots_checked=120,cooperative_source_sha256=freeze["source_sha256"],P_source_sha256=base["source_sha256"],source_change_AST=freeze["changed_AST_nodes"],frozen_analysis_source=analysis_freeze,study_manifest_sha256=sha(STUDY/"manifest.json"),study_protocol_sha256=sha(STUDY/"protocol.json"),P_postverification_sha256=sha(P_ANALYSIS/"postverification.json"),P_attribution_summary_sha256=sha(P_ANALYSIS/"attribution/summary.json"),straight_equivalence_sha256=sha(PACKAGE/"straight_equivalence_report.json"),outer_operation=outer)
report=dict(metadata=dict(label="C1_P strict formation ablation",policy="cooperative",normal_overtake=False,seeds=[6,7,8,9,10],comparison="C1_P cooperative minus P transform: negative time/fuel means C1_P is lower",raw_parameter_hashes_must_equal=True,no_new_metrics=True,no_runtime_monkeypatch=True,source_mismatch_is_explicit_ablation=True,source_versions_never_pooled_as_same_policy=True,low_flow_no_congestion_remains_valid=True,interpretation="C1_P and P suppress ordinary overtaking in lane-drop organized modes; P-minus-C1_P contrasts formation following and layer fill under unchanged cooperation. A numerical contrast alone does not prove that physically formed groups caused it.",straight_proof="Bound old C1_H/C0 proof inherited after fixed-state action/Memory equality; new pair/follow/fill never execute in cooperative; no old seeds rerun"),audit=audit,runs=run_rows,pairs=pairs,attributions=attribution_rows,flow_means=means)
write(OUTPUT/"summary.json",report)
for name,rows in (("runs",run_rows),("pairs",pairs),("attributions",attribution_rows),("flow_means",means)):
    csv_write(OUTPUT/(name+".csv"),rows)
from experiments.native_recovery import summarize_manifest
summarize_manifest(STUDY / "manifest.json", OUTPUT / "recovery")
write(OUTPUT/"analysis_status.json",dict(status="completed",cases_finished=20,total_cases=20))
hashes={str(path.relative_to(OUTPUT)):sha(path) for path in OUTPUT.rglob("*") if path.is_file()}
write(OUTPUT/"artifact_hashes.json",hashes)
print(json.dumps(dict(output=str(OUTPUT),audit=audit,flow_means=means)),flush=True)
