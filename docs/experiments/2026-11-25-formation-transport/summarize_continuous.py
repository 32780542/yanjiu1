"""Generate the Chinese continuous-flow report and paired means/ranges from validated CSVs."""
import csv
from statistics import mean

from validate_traffic import FLOWS, HERE, OUTCOMES, write_csv


def load(name):
    with (HERE/name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def group(rows, **conditions):
    return [r for r in rows if all(str(v)==r[k] for k,v in conditions.items())]


def values(rows, field):
    return [float(r[field]) for r in rows if r.get(field) not in (None,"")]


def means(rows, fields):
    if not rows:
        return "—"
    return " / ".join(f"{mean(values(rows,k)):.2f}" for k in fields)


def variation(series):
    return f"{mean(series):+.2f} [{min(series):+.2f}, {max(series):+.2f}]" if series else "—"


def confirmation_findings(pairs):
    confirmed = group(pairs, panel="holdout", reference="11.24")
    if len(confirmed) != 24:
        return []
    upstream = values(confirmed, "delta_up_pct")
    findings = [
        "## 独立确认的主要观察", "",
        f"在两种缩道、三档流量的 24 个同种子配对中，{sum(x>0 for x in upstream)} 个配对的上游物理交错占比高于 11.24，各配对差值从 {min(upstream):+.2f} 到 {max(upstream):+.2f} 个百分点。", "",
    ]
    for road in ("3to2", "4to3"):
        samples = [group(confirmed, road=road, flow=q) for q in FLOWS]
        deltas = []
        for field in ("travel_s", "down_pct", "held_3s_pct"):
            deltas.append(" / ".join(f"{mean(values(s, 'delta_'+field)):+.2f}" for s in samples))
        findings.append(
            f"- {road.replace('to','→')} 在 1500 / 1750 / 2000 辆/小时/道下，"
            f"平均路内行程差分别为 {deltas[0]} 秒，下游整秒物理交错差为 {deltas[1]} 个百分点，"
            f"同组车持续满三秒后的下游占比差为 {deltas[2]} 个百分点。"
        )
    return findings + [""]


def report():
    runs=load("continuous_runs.csv")
    pairs=load("continuous_seed_differences.csv")
    eligible=group(runs,eligible=True)
    accepted=group(pairs,eligible=True)
    lines=["# 连续随机流的配对验证", "",
           "每次运行独立生成实际来车文件。配对时逐车核查请求时间、车道和速度，核对 SUMO 路网、路线、车辆物理参数以及首次观测的车道、位置和速度。原生安全插入决定实际入场时刻。路内行程从实际入场至驶出。以一个种子在一道路、一流量下的一次运行为一个观测单位，各种子等权。", "",
           "开发组为种子 6、20，各持续来车 600 秒。单独确认组为 2701–2704，各持续来车 900 秒。同一方法中的不同道路和流量共用各自组的种子。开发组选定方案覆盖四条道路，两个参照方法只覆盖两条缩道。下文方括号是已观察到的逐种子差值范围。", ""]
    lines+=confirmation_findings(accepted)
    for panel,title,methods in (("development","600 秒开发组",("selected","11.24","NOA")),
                                ("holdout","900 秒独立确认组",("selected","11.24"))):
        lines+=["## "+title, ""]
        totals=[]
        for method in methods:
            sample=group(runs,panel=panel,method=method)
            totals.append(f"{method} 完成 {sum(int(r['completed']) for r in sample):,}/{sum(int(r['requested']) for r in sample):,} 辆次，碰撞 {sum(int(r['collisions']) for r in sample)}、瞬移 {sum(int(r['teleports']) for r in sample)}")
        lines+=["。".join(totals)+"。", "",
                "每格依次为平均路内行程（秒）、上游物理交错占比和下游物理交错占比（%）。物理占比在每整秒统计至少两个完整相邻交错层中的车辆数，再除以区域的车辆采样总数。上游取 0–800 m，下游取 1000–1200 m。", "",
                "| 道路 | 每道流量 | 选定方案 | 11.24 |"+(" 纯 NOA |" if panel=="development" else ""),
                "|---|---:|---:|---:|"+("---:|" if panel=="development" else "")]
        roads=("3to2","4to3","2to3","3to4") if panel=="development" else ("3to2","4to3")
        for road in roads:
            for q in FLOWS:
                subset=group(eligible,panel=panel,road=road,flow=q)
                cells=[means(group(subset,method=m),("travel_s","up_pct","down_pct")) for m in methods]
                lines.append(f"| {road.replace('to','→')} | {q} | "+" | ".join(cells)+" |")
        lines+=["", "### 同种子差值", "",
                "下表均取选定方案减参照方法。行程单位为秒，几何占比单位为百分点。各行依次给出配对均值、最小值和最大值。", "",
                "| 道路 | 流量 | 参照 | 种子数 | 行程差 | 上游几何差 | 下游几何差 |",
                "|---|---:|---|---:|---:|---:|---:|"]
        for road in ("3to2","4to3"):
            for q in FLOWS:
                for m in methods[1:]:
                    sample=group(accepted,panel=panel,road=road,flow=q,reference=m)
                    cells=[variation(values(sample,"delta_"+field)) for field in ("travel_s","up_pct","down_pct")]
                    lines.append(f"| {road.replace('to','→')} | {q} | {m} | {len(sample)} | "+" | ".join(cells)+" |")
        lines+=["", "### 下游同一组车的持续交错", "",
                "每 0.1 秒识别完整相邻层对，在相邻采样之间沿用前一帧。同一组实车的标识和层内次序保持、几何与速度条件逐帧持续满足，才继续累计。每格依次为满 **1 / 3 / 5 秒之后**的下游车辆时间占比（%），重叠的层对按车去重。", "",
                "| 道路 | 每道流量 | 选定方案 | 11.24 |"+(" 纯 NOA |" if panel=="development" else ""),
                "|---|---:|---:|---:|"+("---:|" if panel=="development" else "")]
        for road in ("3to2","4to3"):
            for q in FLOWS:
                subset=group(eligible,panel=panel,road=road,flow=q)
                cells=[means(group(subset,method=m),("held_1s_pct","held_3s_pct","held_5s_pct")) for m in methods]
                lines.append(f"| {road.replace('to','→')} | {q} | "+" | ".join(cells)+" |")
        lines+=[""]
        if panel=="holdout":
            lines+=["四个独立种子上，选定方案相对 11.24 的持续交错差值如下，单位为百分点。", "",
                    "| 道路 | 每道流量 | 满 1 秒后 | 满 3 秒后 | 满 5 秒后 |",
                    "|---|---:|---:|---:|---:|"]
            for road in ("3to2","4to3"):
                for q in FLOWS:
                    sample=group(accepted,panel=panel,road=road,flow=q,reference="11.24")
                    cells=[variation(values(sample,f"delta_held_{h}s_pct")) for h in (1,3,5)]
                    lines.append(f"| {road.replace('to','→')} | {q} | "+" | ".join(cells)+" |")
            lines+=[""]
    summary=[]
    for panel,road,flow,reference in sorted({(r["panel"],r["road"],r["flow"],r["reference"]) for r in pairs}):
        subset=group(accepted,panel=panel,road=road,flow=flow,reference=reference)
        row=dict(panel=panel,road=road,flow=flow,reference=reference,paired_seeds=len(subset))
        for key in OUTCOMES:
            vals=values(subset,"delta_"+key)
            for name,fun in (("mean",mean),("min",min),("max",max)):
                row[f"{key}_{name}"]=fun(vals) if vals else None
        summary.append(row)
    write_csv("continuous_group_differences.csv",summary)
    lines+=["## 横移事件与解释范围", "",
            "本车请求通过执行检查、由运行器调用 SUMO 横移接口后记为一次提交。车道索引改变时累计实际跨越的边界数，抵达目标道中心且横移结束后另记完成事件。三项均覆盖入场至离场的全程。下表按每 100 辆实际驶出的车辆折算每次运行的事件数，再对种子等权平均。每格依次为提交 / 跨界 / 完成。", "",
            "| 独立确认道路 | 每道流量 | 选定方案 | 11.24 |", "|---|---:|---:|---:|"]
    for road in ("3to2","4to3"):
        for q in FLOWS:
            cells=[]
            for m in ("selected","11.24"):
                subset=group(eligible,panel="holdout",road=road,flow=q,method=m)
                cells.append(" / ".join(f"{mean(100*float(r[k])/float(r['completed']) for r in subset):.1f}" for k in ("submitted","crossings","finished")) if subset else "—")
            lines.append(f"| {road.replace('to','→')} | {q} | "+" | ".join(cells)+" |")
    count=sum(int(p["actual_entry_pairs"]) for p in pairs)
    same=sum(int(p["same_entry_time"]) for p in pairs)
    maximum=max(values(pairs,"max_abs_entry_difference_s"))
    lines+=["",f"逐方法配对共核对 {count:,} 个实际入场比较，其中 {same:,} 个入场时刻相同，最大差 {maximum:.2f} 秒。同一开发候选分别与 11.24 和纯 NOA 比较，因此这里的分母包含两次不同参照比较。", "",
            "CSV 同时给出实验开始至来车截止期间的出口流率（辆/小时）和截止至末车驶出的清空时间（秒）。每次实验都从空路开始。所有车辆最终驶出时，规定时间窗内的出口流率仍可能不同。", "",
            "扩道只在开发组运行了选定方案。900 秒组支持两种缩道相对 11.24 的复核。几何指标使用 30 m 同道参考间距、15 m 邻道错位、2 m 纵向容差、0.3 m 居中容差和 0.5 m/s 组内速度极差。低速压缩队列可能超出该固定间距窗口。200 m 短下游限制了整组可观察时长。两个或四个种子的范围是实测差异，不代表总体置信区间。几何匹配也可能偶合，各控制分支的独立贡献仍需另外的消融。", "",
            "[逐运行指标及原始运行目录](continuous_runs.csv) · [逐种子配对差](continuous_seed_differences.csv) · [各指标配对均值及范围](continuous_group_differences.csv) · [轨迹与配对复核程序](validate_traffic.py) · [表格生成程序](summarize_continuous.py) · [纯 NOA 与原始存档交叉核对](physical_evaluation.md)"]
    (HERE/"continuous_results.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(len(runs),"runs,",len(pairs),"pairs,",len(summary),"paired groups")


if __name__=="__main__":
    report()
