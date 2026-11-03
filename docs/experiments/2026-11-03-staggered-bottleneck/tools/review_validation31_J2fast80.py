"""Independent raw-trip/ledger review and matched-road difference for seeds31-35."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import review_E_heldout as independent
import seal_case
import summarize

ROOT=Path(__file__).resolve().parents[1]
METRICS=independent.METRICS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir",type=Path,default=ROOT/"validation31_J2fast80")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("new output required")
    parent=seal_case.read(args.report_dir/"summary.json")
    names=("per_case.csv","paired_seeds.csv","flow_means.csv","summary.json","tables.md")
    source_hashes={name:seal_case.sha(args.report_dir/name) for name in names}
    records=[row for batch in parent["batches"] for row in summarize.protocol_records(Path(batch))]
    summarize.unique(records)
    assert len(records)==80 and {row["seed"] for row in records}==set(range(31,36))
    cases=[]
    for i,record in enumerate(records,1):
        cases.append(independent.reconstruct(record))
        if i%10==0:
            print(json.dumps(dict(reconstructed=i,total=80)),flush=True)
    index=summarize.unique(cases)
    paired_columns=independent.read_csv(args.report_dir/"paired_seeds.csv")[0]
    metrics=set(METRICS)|{key[6:] for key in paired_columns if key.startswith("delta_")}
    pairs=[]
    for target in cases:
        if target["candidate"]!="J2fast":
            continue
        reference=index[("TM",target["flow"],target["seed"],target["scenario"],"noa")]
        assert all(reference[key]==target[key] for key in ("demand_sha256","parameters_sha256","nonrule_source_sha256"))
        pair=dict(comparison="J2fast-NOA",interpretation="same_following_complete_strategy",
            candidate="J2fast",reference="TM/noa",flow=target["flow"],seed=target["seed"],scenario=target["scenario"],
            pair_eligible=True,rejection_reasons=[])
        for prefix,case in (("reference",reference),("candidate",target)):
            pair[prefix+"_case_dir"]=case["run_dir"]
            for key in ("rules_sha256","nonrule_source_sha256","demand_sha256","parameters_sha256"):
                pair[prefix+"_"+key]=case[key]
        for metric in metrics:
            a,b=reference.get(metric),target.get(metric)
            pair["reference_"+metric],pair["target_"+metric]=a,b
            pair["delta_"+metric]=b-a if a is not None and b is not None else None
        pair["system_improvement_percent"]=-100*pair["delta_mean_system_time_s"]/reference["mean_system_time_s"]
        pairs.append(pair)
    groups=defaultdict(list)
    for pair in pairs:
        groups[pair["flow"],pair["scenario"]].append(pair)
    means=[]
    for (flow,scenario),rows in sorted(groups.items()):
        assert len(rows)==5 and {row["seed"] for row in rows}==set(range(31,36))
        row=dict(candidate="J2fast",reference="TM/noa",flow=flow,scenario=scenario,seeds=5,eligible=True,
                 improved_seeds=sum(item["system_improvement_percent"]>0 for item in rows))
        for metric in METRICS:
            for prefix in ("reference_","target_","delta_"):
                row[prefix+metric]=independent.mean([item[prefix+metric] for item in rows])
        row["system_improvement_percent"]=-100*row["delta_mean_system_time_s"]/row["reference_mean_system_time_s"]
        means.append(row)
    independent.check_csv(independent.read_csv(args.report_dir/"per_case.csv"),cases,summarize.IDENTITY,"per_case")
    independent.check_csv(independent.read_csv(args.report_dir/"paired_seeds.csv"),pairs,("candidate","flow","seed","scenario"),"paired_seeds")
    independent.check_csv(independent.read_csv(args.report_dir/"flow_means.csv"),means,("candidate","reference","flow","scenario"),"flow_means")
    for name,value in dict(case_count=80,protocol_verified=80,evidence_verified=80,drained=80,safe=80,pair_count=40,eligible_pairs=40,means=means).items():
        independent.compare(parent[name],value,"summary."+name,"summary")
    show=lambda value:"—" if value is None else f"{value:.4f}"
    table=["| "+" | ".join((row["candidate"]+"−"+row["reference"],str(row["flow"]),row["scenario"],
        show(row["reference_mean_system_time_s"])+"/"+show(row["target_mean_system_time_s"]),show(row["system_improvement_percent"]),
        str(row["improved_seeds"])+"/5",show(row["delta_fuel_g_per_km"]),show(row["delta_mean_segment_640_1100_s"]),
        show(row["delta_region_low_speed_vehicle_s"])))+" |" for row in means]
    actual=[line for line in (args.report_dir/"tables.md").read_text(encoding="utf-8").splitlines() if line.startswith("| J2fast")]
    independent.compare(actual,table,"tables data rows","tables")
    by_seed={(row["flow"],row["seed"],row["scenario"]):row for row in pairs}
    road_difference=[]
    for flow in sorted({row["flow"] for row in means}):
        changes=[]
        for seed in range(31,36):
            straight=by_seed[flow,seed,"straight3"]["delta_mean_system_time_s"]
            drop=by_seed[flow,seed,"lane_drop"]["delta_mean_system_time_s"]
            changes.append(dict(seed=seed,straight_delta_s=straight,drop_delta_s=drop,additional_drop_saving_s=straight-drop))
        road_difference.append(dict(flow=flow,straight_saving_s=-independent.mean([row["straight_delta_s"] for row in changes]),
            drop_saving_s=-independent.mean([row["drop_delta_s"] for row in changes]),
            additional_drop_saving_s=independent.mean([row["additional_drop_saving_s"] for row in changes]),seeds=changes))
    assert source_hashes=={name:seal_case.sha(args.report_dir/name) for name in names}
    result=dict(case_count=80,pair_count=40,flow_groups=8,primary_metrics=len(METRICS),
        all_parent_table_cells_checked=True,scalar_comparisons=dict(independent.COUNTS),
        max_absolute_numeric_errors=dict(independent.MAXERR),source_report_sha256=source_hashes,
        source_batch_protocol_sha256={str(batch):seal_case.sha(Path(batch)/"protocol.json") for batch in parent["batches"]},
        report_paired_tool_sha256=seal_case.sha(ROOT/"tools/report_paired.py"),
        reviewer_tool_sha256=seal_case.sha(__file__),independent_reconstruction_sha256=seal_case.sha(Path(independent.__file__)),
        means=means,matched_road_effect_difference=road_difference,no_parent_report_functions_imported=True,simulations_run=False,
        limits="Same-seed road difference is descriptive additional bottleneck saving, not isolated formation causality. Straight-road gains remain explicit. No matched E31 cohort exists in this report; no direct E-versus-J2fast ranking across different seeds. Traffic success does not verify complete staggered geometry.")
    seal_case.write(args.output,result)
    print(json.dumps(dict(cases=80,pairs=40,groups=8,scalar_comparisons=dict(independent.COUNTS),road_difference=road_difference)),flush=True)


if __name__=="__main__":
    main()
