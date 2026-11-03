"""Reconstruct the 20 common original cases in the S/NOA60 sensitivity table."""
from collections import defaultdict
from pathlib import Path

import review_E_heldout as independent
import seal_case
import summarize

ROOT=Path(__file__).resolve().parents[1]


def main():
    report=ROOT/"S_NOA60_sensitivity"
    if (report/"verification.json").exists():
        raise ValueError("verification already exists")
    summary=seal_case.read(report/"summary.json")
    records=[row for batch in summary["batches"] for row in summarize.protocol_records(Path(batch))]
    assert len(records)==30
    records=[row for row in records if row["scenario"]=="lane_drop"]
    assert len(records)==20
    cases=[independent.reconstruct(row) for row in records]
    index=summarize.unique(cases)
    actual=independent.read_csv(report/"paired_seeds.csv")
    assert len(actual)==10
    metrics=set(independent.METRICS)|{key[6:] for key in actual[0] if key.startswith("delta_")}
    assert all(prefix+metric in actual[0] for metric in independent.METRICS for prefix in ("reference_","target_","delta_"))
    pairs=[]
    for row in actual:
        key=float(row["flow"]),int(row["seed"]),row["scenario"]
        assert key[0] in (2250.,2500.) and key[1] in range(31,36) and key[2]=="lane_drop"
        a,b=index[("NOA60",*key,"noa")],index[("S",*key,"transform")]
        assert a["flag_participating_vehicle_seconds"]==0
        for name in ("demand_sha256","parameters_sha256","nonrule_source_sha256"):
            assert a[name]==b[name]
        expected=dict(flow=key[0],seed=key[1],scenario=key[2])
        for metric in metrics:
            av,bv=a.get(metric),b.get(metric)
            for prefix,value in (("reference_",av),("target_",bv),("delta_",bv-av if av is not None and bv is not None else None)):
                if prefix+metric in row:
                    independent.compare(row[prefix+metric],value,repr(key)+prefix+metric,"original_pair_vs_table")
                expected[prefix+metric]=value
        for prefix,case in (("reference",a),("candidate",b)):
            for name in ("rules_sha256","demand_sha256","parameters_sha256","nonrule_source_sha256"):
                independent.compare(row[prefix+"_"+name],case[name],repr(key)+prefix+name,"original_hash_vs_table")
        expected["system_improvement_percent"]=-100*expected["delta_mean_system_time_s"]/a["mean_system_time_s"]
        independent.compare(row["system_improvement_percent"],expected["system_improvement_percent"],repr(key)+"percent","original_pair_vs_table")
        pairs.append(expected)
    means=[]
    for flow in (2250.,2500.):
        members=[p for p in pairs if p["flow"]==flow]
        assert len(members)==5 and {p["seed"] for p in members}==set(range(31,36))
        item=dict(comparison="S/transform=NOA60/noa",candidate="S",reference="NOA60/noa",flow=flow,scenario="lane_drop",
            seeds=5,eligible=True,improved_seeds=sum(p["system_improvement_percent"]>0 for p in members))
        for metric in independent.METRICS:
            for prefix in ("reference_","target_","delta_"):
                item[prefix+metric]=independent.mean([p[prefix+metric] for p in members])
        item["system_improvement_percent"]=-100*item["delta_mean_system_time_s"]/item["reference_mean_system_time_s"]
        means.append(item)
    independent.check_csv(independent.read_csv(report/"flow_means.csv"),means,("flow","scenario"),"original_flow_mean_vs_table")
    result=dict(original_common_cases_reconstructed=20,original_protocol_case_pool=30,matched_pairs=10,groups=2,
        comparisons=dict(independent.COUNTS),max_absolute_numeric_errors=dict(independent.MAXERR),means=means,
        matched_invariants=("demand_sha256","parameters_sha256","nonrule_source_sha256"),
        source_hashes={candidate:sorted({r["rules_sha256"] for r in cases if r["candidate"]==candidate}) for candidate in ("NOA60","S")},
        report_sha256={name:seal_case.sha(report/name) for name in ("per_case.csv","paired_seeds.csv","flow_means.csv","summary.json","tables.md")},
        tool_sha256=seal_case.sha(__file__),reconstruction_tool_sha256=seal_case.sha(Path(independent.__file__)),
        formal_baseline_changed=False,percentages_subtracted=False,simulations_run=False)
    seal_case.write(report/"verification.json",result)
    (report/"README.md").write_text("# S 对 NOA60 的同输入敏感性\n\n原NOA60长20与S31高10的30例协议均核验；只比较两档缩道、31–35种子的10对共同计划，不补造直路S样本。另从20个共同case的原input/result/trips、compact旗标及gate/region ledgers独立重构，核验全部15项主指标均值、原始差和来源/需求/参数SHA。\n\n2250系统时间52.9391→48.5624s，改善8.2674%；2500为76.2814→67.4847s，改善11.5320%，均5/5种子。燃油差仍为+6.2546、+5.5279g/km。改善率由NOA60实际分母逐输入重算，不能把另表的约1.8%从原S改善率机械相减。正式NOA50基线和数值表不改。\n\nNOA60为无形成模式的默认前车距离敏感性，对照不是单独形成几何的因果识别；规则源不同，需求、物理参数（含SUMO版本、duration/max_time）及非rule源码SHA逐对相同。通用wrapper表头内G0/LP0说明不参与本比较，LP0后续等价证明见其他附注。完整源、逐seed、反例和油耗均保留；本复核不重仿真。\n",encoding="utf-8")
    print(result["comparisons"],flush=True)


if __name__=="__main__":
    main()
