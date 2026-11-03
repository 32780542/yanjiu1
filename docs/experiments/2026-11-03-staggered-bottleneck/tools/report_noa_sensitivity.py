"""NOA60 versus recorded NOA50, shared planned cases only; never changes baseline."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import report_paired
import seal_case
import summarize

METRICS=report_paired.METRICS


def plan_key(row):
    if row["mode"]!="noa":
        raise ValueError("NOA-only sensitivity requires mode=noa")
    return row["flow"],row["seed"],row["scenario"]


def noa_index(rows):
    index={}
    for row in rows:
        key=plan_key(row)
        if key in index:
            raise ValueError("duplicate NOA planned identity: "+repr(key))
        index[key]=row
    return index


def common_plan(reference,target):
    left,right=noa_index(reference),noa_index(target)
    return sorted(left.keys()&right.keys()),sorted(left.keys()-right.keys()),sorted(right.keys()-left.keys())


def pair_noa(reference,target):
    if plan_key(reference)!=plan_key(target):
        raise ValueError("NOA pair must share flow/seed/scenario")
    traffic=seal_case.tools()[1]
    a,b=reference["_run"],target["_run"]
    pair=traffic.pair(a,b,"NOA60-minus-NOA50","NOA_default_front_range_sensitivity")
    for role,case in (("reference",reference),("target",target)):
        if not case["protocol_verified"] or not case["evidence_verified"]:
            pair["rejection_reasons"].append(role+"_protocol_or_evidence_ineligible")
    pair["pair_eligible"]=not pair["rejection_reasons"]
    pair.update(reference_candidate=reference["candidate"],candidate=target["candidate"],reference_mode="noa",mode="noa")
    for metric in METRICS:
        pair["reference_"+metric]=a.get(metric)
        pair["target_"+metric]=b.get(metric)
        pair["delta_"+metric]=traffic.existing._difference(a,b,metric,pair["pair_eligible"])
    pair["system_improvement_percent"]=-100*pair["delta_mean_system_time_s"]/a["mean_system_time_s"] if pair["pair_eligible"] else None
    return pair


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-batch",type=Path,nargs="+",required=True)
    parser.add_argument("--target-batch",type=Path,required=True)
    parser.add_argument("--label",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("new output required")
    reference_records=[row for batch in args.reference_batch for row in summarize.protocol_records(batch) if row["mode"]=="noa"]
    target_records=summarize.protocol_records(args.target_batch)
    references=[summarize.load_case(row) for row in reference_records]
    targets=[summarize.load_case(row) for row in target_records]
    common,reference_only,target_only=common_plan(references,targets)
    left,right=noa_index(references),noa_index(targets)
    for case in (*references,*targets):
        if case.get("flag_participating_vehicle_seconds")!=0:
            raise ValueError("NOA sensitivity unexpectedly has formation participants")
    pairs=[pair_noa(left[key],right[key]) for key in common]
    traffic=seal_case.tools()[1]
    all_metrics=[prefix+metric for metric in METRICS for prefix in ("reference_","target_","delta_")]
    groups=traffic.existing._means(pairs,("flow","scenario"),all_metrics)
    means=[]
    by_group=defaultdict(list)
    for row in pairs:
        by_group[row["flow"],row["scenario"]].append(row)
    for group in groups:
        row=dict(flow=group["flow"],scenario=group["scenario"],seeds=group["attempted_n"],eligible=group["group_eligible"])
        row.update({key:group[key+"_mean"] for key in all_metrics})
        members=by_group[row["flow"],row["scenario"]]
        row["improved_seeds"]=sum(member["system_improvement_percent"]>0 for member in members) if row["eligible"] else None
        row["system_improvement_percent"]=-100*row["delta_mean_system_time_s"]/row["reference_mean_system_time_s"] if row["eligible"] else None
        means.append(row)
    args.output.mkdir(parents=True,exist_ok=False)
    cases=[]
    for role,rows in (("reference",references),("target",targets)):
        cases.extend({**{key:value for key,value in row.items() if not key.startswith("_")},
                      "comparison_role":role,"common_plan_member":plan_key(row) in common} for row in rows)
    traffic.write_rows(args.output/"per_case.csv",cases)
    traffic.write_rows(args.output/"paired_seeds.csv",pairs)
    traffic.write_rows(args.output/"flow_means.csv",means)
    summary=dict(label=args.label,reference_case_pool=len(references),target_case_pool=len(targets),common_pairs=len(pairs),
        eligible_pairs=sum(row["pair_eligible"] for row in pairs),
        protocol_verified=sum(row["protocol_verified"] for row in (*references,*targets)),
        evidence_verified=sum(row["evidence_verified"] for row in (*references,*targets)),
        safe=sum(row.get("safe") is True for row in (*references,*targets)),
        drained=sum(row.get("all_completed") is True for row in (*references,*targets)),
        reference_only_plan_keys=reference_only,target_only_plan_keys=target_only,means=means,
        reference_batches=[str(batch.resolve()) for batch in args.reference_batch],target_batch=str(args.target_batch.resolve()),
        protocol_sha256={str(batch.resolve()):seal_case.sha(batch/"protocol.json") for batch in (*args.reference_batch,args.target_batch)},
        modes="noa versus noa",invariant_policy="Demand, parameters including duration/max_time/SUMO, and all non-rule sources must match; rule SHA may differ by sensitivity.",
        pair_policy="Intersection of the two original NOA plans only; unmatched extra baseline/target cases recorded without fabricated pairs.",
        metric_policy="Existing complete-request/region/gate/flag measures and equal-seed means; missing fixed-window metrics remain null.",
        baseline_modified=False,formation_effect_claimed=False,final61_performance_read=False,
        tool_sha256=seal_case.sha(__file__),frozen_report_paired_sha256=seal_case.sha(Path(report_paired.__file__)))
    seal_case.write(args.output/"summary.json",summary)
    show=lambda value:"—" if value is None else f"{value:.4f}"
    lines=["# NOA60 / NOA50 距离敏感性（不是编队对照）","",f"共同计划{len(pairs)}对；不补造不匹配工况。差为NOA60减NOA50，改善百分比为负差/参考均值。","",
        "| 流量 | 道路 | 系统时间参考/NOA60(s) | 改善(%) | 改善种子 | 燃油差(g/km) | 瓶颈段差(s) | 固定窗低速差(车辆秒) |",
        "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in means:
        lines.append("| "+" | ".join((str(row["flow"]),row["scenario"],show(row["reference_mean_system_time_s"])+"/"+show(row["target_mean_system_time_s"]),
            show(row["system_improvement_percent"]),str(row["improved_seeds"])+"/"+str(row["seeds"]),show(row["delta_fuel_g_per_km"]),
            show(row["delta_mean_segment_640_1100_s"]),show(row["delta_region_low_speed_vehicle_s"])))+" |")
    (args.output/"tables.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({key:value for key,value in summary.items() if key not in ("means","protocol_sha256","reference_batches","target_batch")}),flush=True)
    return 0 if len(cases)==summary["protocol_verified"]==summary["evidence_verified"] and len(pairs)==summary["eligible_pairs"] else 1


if __name__=="__main__":
    raise SystemExit(main())
