"""Independent raw-trip/ledger review and matched-road difference for locked independent seeds61-65."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import review_E_heldout as independent
import seal_case
import summarize

ROOT=Path(__file__).resolve().parents[1]
METRICS=independent.METRICS


def audit_locked_cases(cases):
    expected={(candidate,mode,flow,seed,road)
        for candidate,mode in (("TM","noa"),("S","transform"))
        for flow in (500.,750.,1000.,1250.,1500.,2000.,2250.,2500.)
        for seed in range(61,66) for road in ("straight3","lane_drop")}
    actual=[(r["candidate"],r["mode"],r["flow"],r["seed"],r["scenario"]) for r in cases]
    assert len(actual)==len(set(actual))==160 and set(actual)==expected
    hashes={"TM":"65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317",
        "S":"8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"}
    assert all(row["rules_sha256"]==hashes[row["candidate"]] for row in cases)
    return dict(cases=160,plan="2 methods x 8 flows x 5 original seeds x 2 roads",rule_sha256=hashes)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir",type=Path,default=ROOT/"final61_S160")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("new output required")
    parent=seal_case.read(args.report_dir/"summary.json")
    names=("per_case.csv","paired_seeds.csv","flow_means.csv","summary.json","tables.md")
    source_hashes={name:seal_case.sha(args.report_dir/name) for name in names}
    records=[row for batch in parent["batches"] for row in summarize.protocol_records(Path(batch))]
    summarize.unique(records)
    assert len(records)==160 and {row["seed"] for row in records}==set(range(61,66))
    cases=[]
    for i,record in enumerate(records,1):
        cases.append(independent.reconstruct(record))
        if i%10==0:
            print(json.dumps(dict(reconstructed=i,total=160)),flush=True)
    index=summarize.unique(cases)
    lock=audit_locked_cases(cases)
    paired_columns=independent.read_csv(args.report_dir/"paired_seeds.csv")[0]
    metrics=set(METRICS)|{key[6:] for key in paired_columns if key.startswith("delta_")}
    pairs=[]
    for target in cases:
        if target["candidate"]!="S":
            continue
        reference=index[("TM",target["flow"],target["seed"],target["scenario"],"noa")]
        assert all(reference[key]==target[key] for key in ("demand_sha256","parameters_sha256","nonrule_source_sha256"))
        pair=dict(comparison="S-NOA",interpretation="same_following_complete_strategy",
            candidate="S",reference="TM/noa",flow=target["flow"],seed=target["seed"],scenario=target["scenario"],
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
        assert len(rows)==5 and {row["seed"] for row in rows}==set(range(61,66))
        row=dict(candidate="S",reference="TM/noa",flow=flow,scenario=scenario,seeds=5,eligible=True,
                 improved_seeds=sum(item["system_improvement_percent"]>0 for item in rows))
        for metric in METRICS:
            for prefix in ("reference_","target_","delta_"):
                row[prefix+metric]=independent.mean([item[prefix+metric] for item in rows])
        row["system_improvement_percent"]=-100*row["delta_mean_system_time_s"]/row["reference_mean_system_time_s"]
        means.append(row)
    independent.check_csv(independent.read_csv(args.report_dir/"per_case.csv"),cases,summarize.IDENTITY,"per_case")
    independent.check_csv(independent.read_csv(args.report_dir/"paired_seeds.csv"),pairs,("candidate","flow","seed","scenario"),"paired_seeds")
    independent.check_csv(independent.read_csv(args.report_dir/"flow_means.csv"),means,("candidate","reference","flow","scenario"),"flow_means")
    for name,value in dict(case_count=160,protocol_verified=160,evidence_verified=160,drained=160,safe=160,pair_count=80,eligible_pairs=80,means=means).items():
        independent.compare(parent[name],value,"summary."+name,"summary")
    show=lambda value:"—" if value is None else f"{value:.4f}"
    table=["| "+" | ".join((row["candidate"]+"−"+row["reference"],str(row["flow"]),row["scenario"],
        show(row["reference_mean_system_time_s"])+"/"+show(row["target_mean_system_time_s"]),show(row["system_improvement_percent"]),
        str(row["improved_seeds"])+"/5",show(row["delta_fuel_g_per_km"]),show(row["delta_mean_segment_640_1100_s"]),
        show(row["delta_region_low_speed_vehicle_s"])))+" |" for row in means]
    actual=[line for line in (args.report_dir/"tables.md").read_text(encoding="utf-8").splitlines() if line.startswith("| S")]
    independent.compare(actual,table,"tables data rows","tables")
    by_seed={(row["flow"],row["seed"],row["scenario"]):row for row in pairs}
    road_difference=[]
    for flow in sorted({row["flow"] for row in means}):
        changes=[]
        for seed in range(61,66):
            straight=by_seed[flow,seed,"straight3"]["delta_mean_system_time_s"]
            drop=by_seed[flow,seed,"lane_drop"]["delta_mean_system_time_s"]
            changes.append(dict(seed=seed,straight_delta_s=straight,drop_delta_s=drop,additional_drop_saving_s=straight-drop))
        road_difference.append(dict(flow=flow,straight_saving_s=-independent.mean([row["straight_delta_s"] for row in changes]),
            drop_saving_s=-independent.mean([row["drop_delta_s"] for row in changes]),
            additional_drop_saving_s=independent.mean([row["additional_drop_saving_s"] for row in changes]),seeds=changes))
    assert source_hashes=={name:seal_case.sha(args.report_dir/name) for name in names}
    result=dict(case_count=160,pair_count=80,flow_groups=16,primary_metrics=len(METRICS),locked_source_matrix=lock,
        all_parent_table_cells_checked=True,scalar_comparisons=dict(independent.COUNTS),
        max_absolute_numeric_errors=dict(independent.MAXERR),source_report_sha256=source_hashes,
        source_batch_protocol_sha256={str(batch):seal_case.sha(Path(batch)/"protocol.json") for batch in parent["batches"]},
        report_paired_tool_sha256=seal_case.sha(ROOT/"tools/report_paired.py"),
        reviewer_tool_sha256=seal_case.sha(__file__),independent_reconstruction_sha256=seal_case.sha(Path(independent.__file__)),
        means=means,matched_road_effect_difference=road_difference,no_parent_report_functions_imported=True,simulations_run=False,
        fuel_increase_pair_count=sum(row["delta_fuel_g_per_km"]>0 for row in pairs),
        nonimproving_system_pairs=[{key:row[key] for key in ("flow","seed","scenario","delta_mean_system_time_s","delta_fuel_g_per_km")} for row in pairs if row["delta_mean_system_time_s"]>=0],
        limits="Same-seed road difference is descriptive additional bottleneck saving, not isolated formation causality. Straight-road gains remain explicit. Locked-source independent confirmation; no rule changes after unblinding. Traffic success does not verify complete staggered geometry.")
    seal_case.write(args.output,result)
    lines=["# 独立确认 S61：原件与表格复核","",
        "原预定矩阵为 NOA80 + 锁定 S80，共 160 例、80 对、16 个道路/流量均值组；每组完整 5 个输入种子（61–65）。",
        "全部原协议与封存核验通过；160 例 safe/drained。完整矩阵及规则 SHA 单独断言，没有按表现筛选。",
        "",
        "从原 input/result/trips 重新计算时间、入口等待、燃油和参数/需求/六源哈希；由完整保留的选定旗标记录、越线 brackets 和 region steps 核对参与指标、段时间、越线流量及固定窗区域量。未调用 report_paired 的统计函数。",
        f"15 项主指标及父表所有实际 CSV/JSON/Markdown 单元均已逐格核对；数值最大绝对误差 {max(independent.MAXERR.values(),default=0):.12g}。详见同名 JSON 的 scalar_comparisons、max_absolute_numeric_errors 和五个源报告哈希。",
        "",
        f"80 对中燃油增加 {result['fuel_increase_pair_count']} 对；系统时间未改善 {len(result['nonimproving_system_pairs'])} 对。所有逐种子反例与油耗差仍保留在原 paired_seeds.csv；未改善案例另列 JSON。",
        "",
        "## 同种子道路额外节省","",
        "额外节省 = 三道直路的 S−NOA 时间差 − 缩道的 S−NOA 时间差；先逐种子计算，再等权平均。单位为秒，正数表示缩道额外节省。不是两个改善百分比相减，也不是单独形成几何的因果效果。","",
        "| 每道流量 | 直路节省(s) | 缩道节省(s) | 缩道额外节省(s) | 额外节省为正的种子 |",
        "|---:|---:|---:|---:|---:|"]
    for row in road_difference:
        lines.append(f"| {row['flow']:g} | {row['straight_saving_s']:.6f} | {row['drop_saving_s']:.6f} | {row['additional_drop_saving_s']:.6f} | {sum(item['additional_drop_saving_s']>0 for item in row['seeds'])}/5 |")
    lines.extend(["","正式 S 源 SHA：`"+lock["rule_sha256"]["S"]+"`；原 NOA 源 SHA：`"+lock["rule_sha256"]["TM"]+"`。", "",
        "交通与几何证据须分开：此表不能单独证明完整 15 m 交错恢复。正常案例已按原政策删除大 positions/events；保留的选定 flags/gates/region ledgers 可复核现有指标，完整轨迹只有原文件哈希，不能重建或用来追加全轨迹结论。",
        "原生产源、候选、报告方法及旧封包均未由此复核工具修改；没有重仿真。"])
    args.output.with_suffix(".md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(dict(cases=160,pairs=80,groups=16,scalar_comparisons=dict(independent.COUNTS),road_difference=road_difference)),flush=True)


if __name__=="__main__":
    main()
