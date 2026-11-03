"""Explicit same-input candidate/mode contrasts using existing verified metrics."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import report_paired
import seal_case
import summarize


def select_pairs(rows,specification):
    index=summarize.unique(rows)
    target,reference=(tuple(part.split("/")) for part in specification.split("="))
    if len(target)!=2 or len(reference)!=2 or target==reference:
        raise ValueError("comparison must be distinct TARGET/MODE=REFERENCE/MODE")
    def subset(identity):
        return {(row["flow"],row["seed"],row["scenario"]):row for row in index.values()
                if (row["candidate"],row["mode"])==identity}
    left,right=subset(reference),subset(target)
    common=sorted(left.keys()&right.keys())
    if not common:
        raise ValueError("comparison has no common original planned inputs: "+specification)
    return [(left[key],right[key]) for key in common],dict(comparison=specification,common=len(common),
        reference_only=sorted(left.keys()-right.keys()),target_only=sorted(right.keys()-left.keys()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch",type=Path,nargs="+",required=True)
    parser.add_argument("--compare",nargs="+",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("new output required")
    if len(set(args.compare))!=len(args.compare):
        parser.error("duplicate explicit comparison")
    records=[row for batch in args.batch for row in summarize.protocol_records(batch)]
    summarize.unique(records)
    cases=[summarize.load_case(row) for row in records]
    traffic=seal_case.tools()[1]
    pairs,coverage=[],[]
    for specification in args.compare:
        selected,membership=select_pairs(cases,specification)
        coverage.append(membership)
        for reference,target in selected:
            a,b=reference["_run"],target["_run"]
            pair=traffic.pair(a,b,specification,"explicit_same_input_strategy_or_matched_nonformation_control")
            for role,case in (("reference",reference),("target",target)):
                if not case["protocol_verified"] or not case["evidence_verified"]:
                    pair["rejection_reasons"].append(role+"_protocol_or_evidence_ineligible")
            pair["pair_eligible"]=not pair["rejection_reasons"]
            pair.update(candidate=target["candidate"],reference=reference["candidate"]+"/"+reference["mode"],
                mode=target["mode"],flow=target["flow"],seed=target["seed"],scenario=target["scenario"])
            for metric in report_paired.METRICS:
                pair["reference_"+metric],pair["target_"+metric]=a.get(metric),b.get(metric)
                pair["delta_"+metric]=traffic.existing._difference(a,b,metric,pair["pair_eligible"])
            pair["system_improvement_percent"]=-100*pair["delta_mean_system_time_s"]/a["mean_system_time_s"] if pair["pair_eligible"] else None
            pairs.append(pair)
    grouped=defaultdict(list)
    for pair in pairs:
        grouped[pair["comparison"],pair["flow"],pair["scenario"]].append(pair)
    means=[]
    for (comparison,flow,scenario),members in sorted(grouped.items()):
        valid=all(row["pair_eligible"] for row in members)
        row=dict(comparison=comparison,candidate=members[0]["candidate"],reference=members[0]["reference"],
            flow=flow,scenario=scenario,seeds=len(members),eligible=valid,
            improved_seeds=sum(row["system_improvement_percent"]>0 for row in members) if valid else None)
        for metric in report_paired.METRICS:
            for prefix in ("reference_","target_","delta_"):
                row[prefix+metric]=report_paired.average([member[prefix+metric] for member in members]) if valid else None
        row["system_improvement_percent"]=-100*row["delta_mean_system_time_s"]/row["reference_mean_system_time_s"] if valid else None
        means.append(row)
    args.output.mkdir(parents=True,exist_ok=False)
    traffic.write_rows(args.output/"per_case.csv",[{k:v for k,v in case.items() if not k.startswith("_")} for case in cases])
    traffic.write_rows(args.output/"paired_seeds.csv",pairs)
    traffic.write_rows(args.output/"flow_means.csv",means)
    summary=dict(case_count=len(cases),protocol_verified=sum(row["protocol_verified"] for row in cases),
        evidence_verified=sum(row["evidence_verified"] for row in cases),safe=sum(row.get("safe") is True for row in cases),
        drained=sum(row.get("all_completed") is True for row in cases),pair_count=len(pairs),
        eligible_pairs=sum(row["pair_eligible"] for row in pairs),means=means,coverage=coverage,
        batches=[str(batch.resolve()) for batch in args.batch],
        protocol_sha256={str(batch.resolve()):seal_case.sha(batch/"protocol.json") for batch in args.batch},
        conventions="Only the common original planned input keys; equal seed weights; target minus reference; missing metrics remain null.",
        causal_limits="G0/G0N are explicitly transform-mode nonformation controls, not original NOA. S versus LP0 changes the extra gate as well as longitudinal phase; not strict S-phase0 equivalence. Traffic success does not prove formation geometry.",
        tool_sha256=seal_case.sha(__file__),frozen_report_paired_sha256=seal_case.sha(Path(report_paired.__file__)))
    seal_case.write(args.output/"summary.json",summary)
    show=lambda value:"—" if value is None else f"{value:.4f}"
    lines=["# 显式同输入配对归因","",summary["causal_limits"],"",
        "| 比较(target=reference) | 流量 | 道路 | 系统参考/候选(s) | 改善(%) | 改善种子 | 燃油差(g/km) | 瓶颈差(s) | 低速差(车辆秒) |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for row in means:
        lines.append("| "+" | ".join((row["comparison"],str(row["flow"]),row["scenario"],
            show(row["reference_mean_system_time_s"])+"/"+show(row["target_mean_system_time_s"]),
            show(row["system_improvement_percent"]),str(row["improved_seeds"])+"/"+str(row["seeds"]),
            show(row["delta_fuel_g_per_km"]),show(row["delta_mean_segment_640_1100_s"]),show(row["delta_region_low_speed_vehicle_s"])))+" |")
    (args.output/"tables.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("means","batches","protocol_sha256","coverage")}),flush=True)
    return 0 if len(cases)==summary["protocol_verified"]==summary["evidence_verified"] and len(pairs)==summary["eligible_pairs"] else 1


if __name__=="__main__":
    raise SystemExit(main())
