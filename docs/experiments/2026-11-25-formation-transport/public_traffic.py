"""Audit frozen flow experiments without launching SUMO. Publish each panel once it is complete."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import hashlib
from itertools import product
import json
import os
from pathlib import Path
from statistics import mean
import time

from validate_traffic import (
    BATCH, HERE, ROOT, OUTCOMES, audit_case, canonical, compare, digest, read, write_csv,
)
from check_crossing_trace import check as coordinate_ledger


SHRINK = ("3to2","4to3")
EXPAND = ("2to3","3to4")
ALL_FLOWS = (1500,1750,2000)
FOUR = (9301,9302,9303,9304)
HOUR = (4801,)
REVIEW = (10121,10122)
# Batch labels are unique even when two batches share all frozen source files.
BATCHES = {
    "noon_prospective_exact_600": (SHRINK, ALL_FLOWS, (11803,), 600, "new_exact"),
    "noon_prospective_noa_600": (SHRINK, ALL_FLOWS, (11803,), 600, "new_noa"),
    "noon_minimum_1200": (SHRINK, ALL_FLOWS, (11261,11262), 1200, "noon_minimum"),
    "noon_noa_1200": (SHRINK, ALL_FLOWS, (11261,11262), 1200, "noon_noa"),
    "noon_receive_1200": (SHRINK, ALL_FLOWS, (11261,11262), 1200, "noon_receive"),
    "noon_combined_1200": (SHRINK, ALL_FLOWS, (11261,11262), 1200, "noon_combined"),
    "noon_ref_1200": (SHRINK, ALL_FLOWS, (11261,11262), 1200, "noon_ref1200"),
    "noon_onehop_1200": (SHRINK, ALL_FLOWS, (11261,11262), 1200, "noon_hop1200"),
    "noon_onehop_900": (SHRINK, ALL_FLOWS, REVIEW, 900, "noon_onehop"),
    "anchor_base_1200": (SHRINK, ALL_FLOWS, FOUR, 1200, "e186"),
    "anchor_group_1200": (SHRINK, ALL_FLOWS, FOUR, 1200, "anchor"),
    "retained_product_1200": (SHRINK, ALL_FLOWS, FOUR, 1200, "retained"),
    "retained_expand_1200": (("2to3",), ALL_FLOWS, FOUR, 1200, "retained"),
    "path_1200": (("3to2","2to3"), ALL_FLOWS, FOUR, 1200, "path1200"),
    "long_selected_3600": (SHRINK, (2000,), HOUR, 3600, "e186"),
    "long_1124_3600": (SHRINK, (2000,), HOUR, 3600, "11.24"),
    "long_noa_3600": (SHRINK, (2000,), HOUR, 3600, "NOA"),
    "path_hour_shrink_4801": (SHRINK, (2000,), HOUR, 3600, "path3600"),
    "path_hour_expand_4801": (EXPAND, (2000,), HOUR, 3600, "path3600"),
    "subflow_shrink_1200": (SHRINK, ALL_FLOWS, FOUR, 1200, "subflow"),
    "subflow_expand_1200": (EXPAND, ALL_FLOWS, FOUR, 1200, "subflow"),
    "retained_34_1200": (("3to4",), ALL_FLOWS, FOUR, 1200, "retained"),
    "subflow_hour_shrink_4801": (SHRINK, (2000,), HOUR, 3600, "subflow3600"),
    "subflow_hour_expand_4801": (EXPAND, (2000,), HOUR, 3600, "subflow3600"),
    "review_base_900": (SHRINK, ALL_FLOWS, REVIEW, 900, "review_base"),
    "review_noa_900": (SHRINK, ALL_FLOWS, REVIEW, 900, "review_noa"),
    "review_tag_900": (SHRINK, ALL_FLOWS, REVIEW, 900, "11.24"),
    "review_final_900": (SHRINK, ALL_FLOWS, REVIEW, 900, "review_final"),
    "review_moment_shrink_3600": (SHRINK, (2000,), HOUR, 3600, "moment3600"),
    "review_moment_expand_3600": (EXPAND, (2000,), HOUR, 3600, "moment3600"),
}
PANELS = {
    "noon_prospective": ("冻结后新种子连续车流复核",
        {"noon_prospective_exact_600":SHRINK,"noon_prospective_noa_600":SHRINK},
        (("new_exact","new_noa",SHRINK),)),
    "noon_exact": ("逐车道最少重复换道的正式对照",
        {"noon_minimum_1200":SHRINK,"noon_hold_1200":SHRINK,"noon_ref_1200":SHRINK,"noon_noa_1200":SHRINK},
        (("noon_minimum","noon_hold",SHRINK),("noon_minimum","noon_noa",SHRINK),
         ("noon_minimum","noon_ref1200",SHRINK))),
    "noon_product": ("中午版与同来车纯 NOA 的路内效率",
        {"noon_hold_1200":SHRINK,"noon_ref_1200":SHRINK,"noon_noa_1200":SHRINK},
        (("noon_hold","noon_noa",SHRINK),("noon_hold","noon_ref1200",SHRINK))),
    "noon_receive_1200": ("按目标槽前驱形成合流间隙的持续流对照",
        {"noon_receive_1200":SHRINK,"noon_combined_1200":SHRINK,"noon_ref_1200":SHRINK},
        (("noon_receive","noon_combined",SHRINK),("noon_receive","noon_ref1200",SHRINK))),
    "noon_combined_1200": ("合群补位与一步变换的连续流对照",
        {"noon_combined_1200":SHRINK,"noon_onehop_1200":SHRINK,"noon_ref_1200":SHRINK},
        (("noon_combined","noon_ref1200",SHRINK),("noon_combined","noon_hop1200",SHRINK))),
    "noon_fresh_1200": ("新来车序列的一步分配对照",
        {"noon_onehop_1200":SHRINK,"noon_ref_1200":SHRINK},
        (("noon_hop1200","noon_ref1200",SHRINK),)),
    "noon_onehop_900": ("一次换道名额的连续流验证",
        {"noon_onehop_900":SHRINK,"review_final_900":SHRINK,"review_noa_900":SHRINK},
        (("noon_onehop","review_final",SHRINK),("noon_onehop","review_noa",SHRINK))),
    "anchor_1200": (
        "前群锚与保留方案的 1200 秒缩道对照",
        {"anchor_base_1200":SHRINK,"anchor_group_1200":SHRINK,"retained_product_1200":SHRINK},
        (("anchor","e186",SHRINK),("retained","e186",SHRINK),("anchor","retained",SHRINK))),
    "path_1200": (
        "路径方案的 1200 秒配对验证",
        {"path_1200":("3to2","2to3"),"retained_product_1200":("3to2",),"retained_expand_1200":("2to3",)},
        (("path1200","retained",("3to2","2to3")),)),
    "path_3600": (
        "路径方案的一小时缩道对照与扩道观察",
        {"path_hour_shrink_4801":SHRINK,"path_hour_expand_4801":EXPAND,
         "long_selected_3600":SHRINK,"long_1124_3600":SHRINK,"long_noa_3600":SHRINK},
        (("path3600","e186",SHRINK),("path3600","11.24",SHRINK),("path3600","NOA",SHRINK))),
    "subflow_1200": (
        "阶段通量方案在四种拓扑的 1200 秒验证",
        {"subflow_shrink_1200":SHRINK,"subflow_expand_1200":EXPAND,
         "retained_product_1200":SHRINK,"retained_expand_1200":("2to3",),"retained_34_1200":("3to4",),
         "path_1200":("3to2","2to3"),"anchor_base_1200":SHRINK},
        (("subflow","retained",SHRINK+EXPAND), ("subflow","path1200",("3to2","2to3")),
         ("subflow","e186",SHRINK))),
    "subflow_3600": (
        "阶段通量整理版在四种道路的一小时验证",
        {"subflow_hour_shrink_4801":SHRINK,"subflow_hour_expand_4801":EXPAND,
         "path_hour_shrink_4801":SHRINK,"path_hour_expand_4801":EXPAND,
         "long_selected_3600":SHRINK,"long_1124_3600":SHRINK,"long_noa_3600":SHRINK},
        (("subflow3600","path3600",SHRINK+EXPAND),("subflow3600","e186",SHRINK),
         ("subflow3600","11.24",SHRINK),("subflow3600","NOA",SHRINK))),
    "review_900": (
        "新种子 900 秒的晨间选版对照",
        {"review_final_900":SHRINK,"review_base_900":SHRINK,"review_tag_900":SHRINK,"review_noa_900":SHRINK},
        (("review_final","review_base",SHRINK),("review_final","11.24",SHRINK),
         ("review_final","review_noa",SHRINK),("review_base","11.24",SHRINK),
         ("review_base","review_noa",SHRINK),("11.24","review_noa",SHRINK))),
    "moment_3600": (
        "镜像矩正式产品的四路一小时对照",
        {"review_moment_shrink_3600":SHRINK,"review_moment_expand_3600":EXPAND,
         "subflow_hour_shrink_4801":SHRINK,"subflow_hour_expand_4801":EXPAND,
         "path_hour_shrink_4801":SHRINK,"path_hour_expand_4801":EXPAND,
         "long_selected_3600":SHRINK,"long_1124_3600":SHRINK,"long_noa_3600":SHRINK},
        (("moment3600","subflow3600",SHRINK+EXPAND),("moment3600","path3600",SHRINK+EXPAND),
         ("moment3600","e186",SHRINK),("moment3600","11.24",SHRINK),("moment3600","NOA",SHRINK))),
}
NAMES = {"e186":"e186","anchor":"前群锚","retained":"保留方案","path1200":"路径原型","subflow":"阶段通量",
         "noon_onehop":"已观察跨道的一步分配",
         "noon_hop1200":"一步分配","noon_ref1200":"上午原版",
         "noon_combined":"合群补位与一步变换",
         "noon_receive":"目标槽前驱跟驰",
         "noon_noa":"纯 NOA",
         "noon_minimum":"最少重复换道的交错编队",
         "new_exact":"中午正式编队","new_noa":"纯 NOA",
         "subflow3600":"阶段通量整理版",
         "review_base":"晨间基准","review_final":"晨间候选","review_noa":"晨间纯 NOA","moment3600":"镜像矩正式版",
         "path3600":"路径闭式","11.24":"11.24","NOA":"纯 NOA"}
for suffix, name in (("conflict","仅在净空不足时跟驰前槽"), ("hold","接收间隙持续到前槽车辆就位"), ("target","按目标位置识别接收冲突")):
    label = "noon_" + suffix
    batch = label + "_1200"
    BATCHES[batch] = (SHRINK, ALL_FLOWS, (11261,11262), 1200, label)
    NAMES[label] = name
    PANELS[batch] = (name + "的连续流对照",
                     {batch:SHRINK, "noon_receive_1200":SHRINK, "noon_ref_1200":SHRINK},
                     ((label,"noon_receive",SHRINK),(label,"noon_ref1200",SHRINK)))

EXTRA = ("crossings_per_100","upstream_crossings","approach_crossings","downstream_crossings",
         "vehicles_crossed","vehicles_crossed_twice_or_more","vehicle_crossing_max",
         "coordinate_crossings","coordinate_crossings_per_100","coordinate_upstream_crossings",
         "coordinate_approach_crossings","coordinate_downstream_crossings",
         "coordinate_vehicles_crossed_twice_or_more","coordinate_vehicle_crossing_max")
CACHE = ROOT / "tmp/nov25_public_flow_audit"
RECOVERIES = {
    ("review_moment_shrink_3600","4to3",2000,4801): "noon_moment_hour4",
    ("anchor_base_1200","4to3",2000,9303): "anchor_e186_recovery9303",
    ("anchor_base_1200","4to3",1750,9304): "anchor_e186_recovery9304",
    ("anchor_base_1200","4to3",2000,9304): "anchor_e186_recovery9304",
}
COORD_FIELDS = (
    "coordinate_crossings","coordinate_upstream_crossings","coordinate_approach_crossings",
    "coordinate_downstream_crossings","coordinate_vehicles_crossed_twice_or_more",
    "coordinate_vehicle_crossing_max","different_per_vehicle_lane_sequences","terminal_center_on_line_vehicles",
    "matched_events_same_time","matched_events_time_differs","matched_max_abs_time_difference_s",
    "matched_events_different_spatial_bin",
)
TRACE_CHECKS = {
    "subflow_1200":("subflow","retained",("4to3",)),
    "review_900":("review_final","review_base",("4to3",)),
    "moment_3600":("moment3600","subflow3600",("4to3","3to4")),
}


def get_design(panels):
    needed = {}
    for panel in panels:
        for label, roads in PANELS[panel][1].items():
            needed.setdefault(label,set()).update(roads)
    jobs, manifests = {}, {}
    for label, needed_roads in needed.items():
        roads, flows, seeds, duration, method = BATCHES[label]
        directory = BATCH/label
        m = read(directory/"manifest.json")
        args, files = m["arguments"], m["files"]
        if (set(args["roads"])!=set(roads) or set(args["flows"])!=set(flows) or set(args["seeds"])!=set(seeds)
                or args["duration"]!=duration or args["mode"]!=("noa" if method in ("NOA","review_noa","noon_noa","new_noa") else "transform")):
            raise ValueError(f"Unexpected matrix or mode in {label}")
        for name, expected in files.items():
            if digest((directory/"source"/name).read_bytes()) != expected:
                raise ValueError(f"Frozen source differs in {label}/{name}")
        if method in manifests and files!=manifests[method]:
            raise ValueError(f"Different frozen source labelled as {method}")
        if method=="moment3600" and files!=read(BATCH/"review_final_900"/"manifest.json")["files"]:
            raise ValueError(f"Product differs from the new-seed 900 s candidate: {label}")
        manifests[method]=files
        for road,flow,seed in product(roads,flows,seeds):
            if road in needed_roads:
                key=(label,road,flow,seed)
                actual=BATCH/RECOVERIES.get(key,label)
                if actual!=directory:
                    retry=read(actual/"manifest.json")
                    a=retry["arguments"]
                    if (retry["files"]!=files or a["mode"]!=args["mode"] or a["duration"]!=duration or
                            road not in a["roads"] or flow not in a["flows"] or seed not in a["seeds"]):
                        raise ValueError(f"Interrupted case recovery differs: {actual}")
                    for name,value in files.items():
                        if digest((actual/"source"/name).read_bytes())!=value:
                            raise ValueError(f"Recovered source differs: {actual}/{name}")
                row=actual/f"{road}_s{seed}_q{flow}"/"row.json"
                jobs[key]=(label,road,flow,seed,row,files,("flow",method,duration))
    return jobs


def audit(job):
    label, road, flow, seed, path, files, spec = job
    index=read(path)
    folder=ROOT/index["run_dir"]
    if path.parent.parent.name!=label:
        originals=list((BATCH/label/path.parent.name).glob("*/input.json"))
        if len(originals)!=1:
            raise ValueError(f"Missing original interrupted demand: {path}")
        first,second=read(originals[0]),read(folder/"input.json")
        for k in ("arrivals","physical","source_sha256","positions_step_s","speed_mode","lane_change_mode"):
            if first[k]!=second[k]:
                raise ValueError(f"Recovered input differs in {k}: {path}")
    metrics_source = [digest((HERE/name).read_bytes()) for name in
                      ("measure.py","persistent_flow.py","validate_traffic.py")]
    metrics_source += [digest((ROOT/"variants/phase5g_pure_formation/experiments/complete_layers.py").read_bytes())]
    fingerprint = [digest(path.read_bytes()),canonical(files), metrics_source]
    for name in ("input.json","result.json","trips.json","positions.jsonl.gz","native.net.xml","native.rou.xml"):
        st=(folder/name).stat()
        fingerprint.extend([name,st.st_size,st.st_mtime_ns])
    cache = CACHE/label/f"{road}_s{seed}_q{flow}.json"
    if cache.is_file():
        item=read(cache)
        if fingerprint==item["verified"]:
            return item["row"]
    native_spec=(spec[0],"NOA",spec[2]) if spec[1] in ("review_noa", "noon_noa", "new_noa") else spec
    out = audit_case(label,road,flow,seed,path,files,native_spec,physical_counts=True)
    out["method"]=spec[1]
    out["batch"] = label
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp=cache.with_suffix(f".{os.getpid()}.writing")
    tmp.write_text(json.dumps(dict(verified=fingerprint,row=out)), encoding="utf-8")
    tmp.replace(cache)
    return out


def summarize(subset, key, diff=False):
    vals=[r[key] for r in subset if r[key] is not None]
    if not vals: return "—"
    if not diff: return f"{mean(vals):.2f}"
    if len(vals)==1: return f"{vals[0]:+.2f}"
    return f"{mean(vals):+.2f} [{min(vals):+.2f}, {max(vals):+.2f}]"


def publish(panel, rows):
    title, labels, comparisons = PANELS[panel]
    rows=[r for r in rows if r["batch"] in labels and r["road"] in labels[r["batch"]]]
    reconciled=[]
    for r in rows:
        case=f"{r['road']}_s{r['seed']}_q{r['flow']}"
        actual_batch=Path(r["run_dir"]).parents[1].name
        index=read(BATCH/actual_batch/case/"row.json")
        check=coordinate_ledger(actual_batch,case)
        if check["native_crossings"]!=r["crossings"] or check["vehicles"]!=r["requested"]:
            raise ValueError(f"Coordinate/ledger source mismatch for {case}")
        fields={k:check[k] for k in COORD_FIELDS}
        fields["input_sha256"]=index["input_sha256"]
        fields["result_sha256"]=index["result_sha256"]
        fields["actual_batch"]=actual_batch
        fields["coordinate_crossings_per_100"]=100*check["coordinate_crossings"]/r["completed"] if r["completed"] else None
        reconciled.append(dict(r,**fields))
    rows=reconciled
    rows.sort(key=lambda r:(r["road"],r["flow"],r["seed"],r["method"]))
    pairs=[]
    for candidate,reference,roads in comparisons:
        sample=[r for r in rows if r["method"] in (candidate,reference) and r["road"] in roads]
        for p in compare(sample, candidate, OUTCOMES+EXTRA):
            p["candidate"]=candidate
            pairs.append(p)
    if panel in TRACE_CHECKS:
        left,right,check_roads=TRACE_CHECKS[panel]
        by_key={(r["method"],r["road"],r["flow"],r["seed"]):r for r in rows}
        for pair in pairs:
            pair["candidate_uncompressed_positions_sha256"]=None
            pair["reference_uncompressed_positions_sha256"]=None
            if pair["candidate"]==left and pair["reference"]==right and pair["road"] in check_roads:
                for role in ("candidate","reference"):
                    r=by_key[(pair[role],pair["road"],pair["flow"],pair["seed"])]
                    with gzip.open(ROOT/r["run_dir"]/"positions.jsonl.gz","rb") as stream:
                        pair[role+"_uncompressed_positions_sha256"]=hashlib.file_digest(stream,"sha256").hexdigest()
    prefix="public_"+panel
    write_csv(prefix+"_runs.csv",rows)
    write_csv(prefix+"_pairs.csv",pairs)
    legit=[r for r in rows if r["eligible"]]
    seeds="、".join(str(v) for v in sorted({r["seed"] for r in rows}))
    lines=["# "+title, "", f"每次连续来车 {rows[0]['duration_s']} 秒，种子为 {seeds}。从实际进入道路到实际驶出计算行程。以同道路、同流量、同种子的一次运行为单位，对种子等权平均。所有配对逐车核查入场请求以及首次物理观测的车道、位置和速度，并核对 SUMO 路网、路线及车辆物理参数。", "",
           "| 方法 | 冻结批次 | 源码清单 SHA-256 前 12 位 | 运行数 | 完成/请求车次 | 碰撞/瞬移 |", "|---|---|---|---:|---:|---:|"]
    for label in labels:
        s=[r for r in rows if r["batch"]==label]
        lines.append(f"| {NAMES[s[0]['method']]} | {label} | {s[0]['source_manifest_sha256'][:12]} | {len(s)} | {sum(r['completed'] for r in s):,}/{sum(r['requested'] for r in s):,} | {sum(r['collisions'] for r in s)}/{sum(r['teleports'] for r in s)} |")
    if panel in ("review_900","moment_3600"):
        before,after=(("review_base_900","review_final_900") if panel=="review_900" else
                      ("subflow_hour_shrink_4801","review_moment_shrink_3600"))
        a,b=[read(BATCH/name/"manifest.json")["files"] for name in (before,after)]
        if {k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}!={"noa/staggered.py"}:
            raise ValueError("The mirror comparison now includes additional source changes")
        lines+=["", "镜像矩方案与其阶段通量基准的冻结文件逐一核查后，只有 noa/staggered.py 不同。对局部两道车辆数相等的排列，两列纵向一阶矩差的绝对值超过车数乘以定位误差时，按其符号选择交错朝向。误差范围内沿用最前车所在道。两者使用同一实际来车请求，表内成对差值反映这项规则在该次闭环运行中的总体影响。"]
    resumed=[r for r in rows if r["actual_batch"]!=r["batch"]]
    if resumed:
        lines+=["",f"e186 原批次达到运行时限。{len(resumed)} 例在恢复批次完成，逐文件核对冻结源码并与原始输入逐车核对入口需求和物理设置。逐运行表的 actual_batch 和 run_dir 指向实际完成目录。"]
    if panel in TRACE_CHECKS:
        left,right,check_roads=TRACE_CHECKS[panel]
        checked=[p for p in pairs if p["candidate_uncompressed_positions_sha256"]]
        identical=sum(p["candidate_uncompressed_positions_sha256"]==p["reference_uncompressed_positions_sha256"] for p in checked)
        road_names="、".join(r.replace("to","→") for r in check_roads)
        lines+=["",f"{road_names} 的{NAMES[left]}与{NAMES[right]}另逐对核对了完整的原生轨迹。{identical}/{len(checked)} 对的解压 positions.jsonl 字节完全相同，逐种子表保留双方轨迹 SHA-256。"]
    lines+=["", "## 车心越线与三秒持续队形", ""]
    for c,ref,roads in comparisons:
        for road in roads:
            s=[p for p in pairs if p["eligible"] and (p["road"],p["candidate"],p["reference"])==(road,c,ref)]
            more=sum(p["delta_coordinate_crossings"]>0 for p in s)
            held=sum(p["delta_held_3s_pct"]>0 for p in s)
            if len(s)>1:
                lines.append(f"- {road.replace('to','→')}，{NAMES[c]}相对{NAMES[ref]}，{len(s)} 个同种子同流量配对中，{more} 个车心越线次数增加，{held} 个下游同车组满三秒后占比提高。")
            elif s:
                lines.append(f"- {road.replace('to','→')}，{NAMES[c]}相对{NAMES[ref]}，车心越线差 {s[0]['delta_coordinate_crossings']:+d} 次，下游同车组满三秒后占比差 {s[0]['delta_held_3s_pct']:+.2f} 个百分点。")
    lines+=["", "## 逐道路和流量", "",
            "上游为 0–800 m，下游为 1000–1200 m。整秒时，只有形成闭合的至少两个完整相邻交错层，才计入分子，分母为对应路段的全部车辆采样数。持续时间用 0.1 秒原始轨迹，同一组车保持条件满 1/3/5 秒后的车辆秒记入分子，分母为下游全部车辆秒。原始计数和分母逐运行保存在 CSV。", "",
            "| 道路 | 辆/h/道 | 方法 | 种子数 | 路内秒 | 上游/下游交错 % | 下游持续 1/3/5 秒后 % | 车心越线/百辆 |",
            "|---|---:|---|---:|---:|---:|---:|---:|"]
    for road,q,m in sorted({(r["road"],r["flow"],r["method"]) for r in rows}):
        s=[r for r in legit if (r["road"],r["flow"],r["method"])==(road,q,m)]
        g=" / ".join(summarize(s,k) for k in ("up_pct","down_pct"))
        held=" / ".join(summarize(s,f"held_{h}s_pct") for h in (1,3,5))
        lines.append(f"| {road.replace('to','→')} | {q} | {NAMES[m]} | {len(s)} | {summarize(s,'travel_s')} | {g} | {held} | {summarize(s,'coordinate_crossings_per_100')} |")
    lines+=["", "### 物理分母与事件原数", "",
            "下表合计同一道路、同一版本的各流量和种子。前两组分数分别是物理交错车辆采样数 / 区域全部车辆采样数。车辆秒保留一位小数。逐档、逐种子的相同分母见 CSV。", "",
            "| 道路 | 方法 | 上游采样数 | 下游采样数 | 下游满 1/3/5 秒后的车辆秒 | 全部下游车辆秒 | 提交/原生索引跨道/车心越线/到中完成 |",
            "|---|---|---:|---:|---:|---:|---:|"]
    for road,m in sorted({(r["road"],r["method"]) for r in rows}):
        s=[r for r in legit if (r["road"],r["method"])==(road,m)]
        def total(key): return sum(r[key] for r in s)
        g=[f"{total(k+'_formed_vehicle_samples'):,} / {total(k+'_vehicle_samples'):,}" for k in ("up","down")]
        held=" / ".join(f"{total(f'held_{h}s_vehicle_s'):,.1f}" for h in (1,3,5))
        events=" / ".join(f"{total(k):,}" for k in ("submitted","crossings","coordinate_crossings","finished"))
        lines.append(f"| {road.replace('to','→')} | {NAMES[m]} | "+" | ".join(g)+
                     f" | {held} | {total('downstream_vehicle_s'):,.1f} | {events} |")
    lines+=["","## 同种子差值","",
            "各格为表中前一种方法减后一种。多种子给出均值和逐种子最小、最大差值，单种子给出该次实测差。交错和持续占比差为百分点，车心越线按每百辆驶出车折算。",
            "", "| 道路 | 流量 | 差值 | 配对数 | 行程秒差 | 上游差 | 下游差 | 持续 3 秒差 | 车心越线/百辆差 |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for c,ref,roads in comparisons:
        for road,q in sorted({(r["road"],r["flow"]) for r in rows if r["road"] in roads}):
            s=[p for p in pairs if p["eligible"] and (p["candidate"],p["reference"],p["road"],p["flow"])==(c,ref,road,q)]
            cells=[summarize(s,"delta_"+k,True) for k in ("travel_s","up_pct","down_pct","held_3s_pct","coordinate_crossings_per_100")]
            lines.append(f"| {road.replace('to','→')} | {q} | {NAMES[c]} − {NAMES[ref]} | {len(s)} | "+" | ".join(cells)+" |")
    shared=sum(p["actual_entry_pairs"] for p in pairs)
    same=sum(p["same_entry_time"] for p in pairs)
    maxdt=max(p["max_abs_entry_difference_s"] for p in pairs)
    lines+=["",f"逐车方法配对共 {shared:,} 次。其中 {same:,} 次实际入场时刻相同，最大差 {maxdt:.2f} 秒。安全插入所需等待依运行而异。每比较一种参照，同一来车清单会再次计入配对数。", "",
            "几何判据为同道 30 m、邻道错位 15 m，位置容差 2 m，组内速差至多 0.5 m/s。短下游会截断持续时间。车心由原始横向坐标独立计算，距标线 0.000001 m 以内保持此前一侧，后续采样到达另一侧才计一次越线。离场末帧恰好在线上时，原生车道索引可能已经变化。CSV 分别保留两个账本、逐车序列一致性、接口提交和到中完成数。比例均值以种子等权，直接汇总分子分母会按交通暴露量加权。", "",
            f"[逐次物理计数、分母和轨迹目录]({prefix}_runs.csv) · [逐种子全部指标差]({prefix}_pairs.csv) · [复算脚本](public_traffic.py)"]
    (HERE/(prefix+"_results.md")).write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("Published",panel,len(rows),"runs and",len(pairs),"pairs",flush=True)


def comparison_index():
    """Combine study links and matched-seed effects without pooling candidate versions."""
    results={}
    for panel in PANELS:
        sets=[]
        for suffix in ("runs","pairs"):
            with (HERE/f"public_{panel}_{suffix}.csv").open(encoding="utf-8",newline="") as stream:
                sets.append(list(csv.DictReader(stream)))
        results[panel]=sets
    unique={r["run_dir"]:r for rows,_ in results.values() for r in rows}
    cells={(r["road"],r["flow"],r["duration_s"],r["seed"]) for r in unique.values()}
    lines=["# 连续流公开对照索引","",
           f"下列面板共使用 {len(unique)} 个完整原生运行目录，覆盖 {len(cells)} 个道路、流量、来车时长及种子组合。多份面板共用参考轨迹。以同一种子同一来车条件的运行均值比较，程序版本分别列示。", "",
           "| 对照明细 | 运行数 | 同种子方法配对数 | 已驶出/请求车次 | 原生碰撞/瞬移 |",
           "|---|---:|---:|---:|---:|"]
    for panel,(rows,pairs) in results.items():
        title=PANELS[panel][0]
        complete,requested,collisions,teleports=[sum(int(r[k]) for r in rows) for k in
                                                 ("completed","requested","collisions","teleports")]
        lines.append(f"| [{title}](public_{panel}_results.md) | {len(rows)} | {len(pairs)} | "
                     f"{complete:,}/{requested:,} | {collisions}/{teleports} |")
    lines+=["","## 2000 辆/小时/道的主要配对", "",
            "各行以一种候选减同来车的指定参照，多个种子等权。路内行程差单位为秒，交错占比差单位为百分点，车心越线差单位为次/百辆驶出车。持续三秒占比使用下游同一组车保持完整交错至三秒后的车辆时间。各档全部结果、逐种子范围、分子和实际车辆秒分母见上表链接。", "",
            "| 时长 | 候选减参照 | 道路 | 种子数 | 行程差 | 上游即时差 | 下游即时差 | 下游持续三秒差 | 车心越线差 |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|"]
    contrasts=(("anchor_1200","anchor","e186"),("path_1200","path1200","retained"),
               ("subflow_1200","subflow","retained"),("review_900","review_final","review_base"),
               ("review_900","review_final","11.24"),("moment_3600","moment3600","subflow3600"),
               ("moment_3600","moment3600","11.24"))
    for panel,candidate,ref in contrasts:
        rows,pairs=results[panel]
        sample=[r for r in pairs if (r["candidate"],r["reference"],r["flow"],r["eligible"])==
                (candidate,ref,"2000","True")]
        for road in sorted({r["road"] for r in sample}):
            s=[r for r in sample if r["road"]==road]
            vals=[f"{mean(float(r['delta_'+k]) for r in s):+.2f}" for k in
                  ("travel_s","up_pct","down_pct","held_3s_pct","coordinate_crossings_per_100")]
            lines.append(f"| {rows[0]['duration_s']} | {NAMES[candidate]} − {NAMES[ref]} | {road.replace('to','→')} | "
                         f"{len(s)} | "+" | ".join(vals)+" |")
    lines+=["", "1200 秒比较使用种子 9301–9304。900 秒和一小时的镜像矩产品使用同一冻结源码，前者来自种子 10121、10122，后者来自种子 4801。单种子小时结果能检验时长和这一条来车序列，跨种子变异由分开的 900 秒配对展示。固定 30 m 同道间距可能漏计压缩车列，200 m 下游只允许观察在区域内完整出现的同组车。", "",
            "[坐标越线与原生车道索引的核对](physical_evaluation.md) · [面板及索引复算程序](public_traffic.py)"]
    (HERE/"public_traffic_index.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("panels",nargs="*", help="One or more of: "+", ".join(PANELS))
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--watch",action="store_true")
    p.add_argument("--index",action="store_true",help="Summarize all finished public panels")
    args=p.parse_args()
    if args.index:
        comparison_index()
        return
    if not args.panels or any(panel not in PANELS for panel in args.panels):
        p.error("Specify a known panel or --index")
    args.panels=list(dict.fromkeys(args.panels))
    if args.watch:
        labels={label for panel in args.panels for label in PANELS[panel][1]}
        while missing:=sorted(label for label in labels if not (BATCH/label/"manifest.json").is_file()):
            print("Waiting for frozen manifest:",*missing,flush=True)
            time.sleep(20)
    jobs=get_design(args.panels)
    finished, published={},set()
    with ProcessPoolExecutor(args.workers) as pool:
        while len(published)<len(args.panels):
            ready=[(k,j) for k,j in jobs.items() if k not in finished and j[4].is_file()]
            for (key,_),row in zip(ready,pool.map(audit,(job for _,job in ready))):
                finished[key]=row
                if not row["eligible"]: print("INELIGIBLE",key,row["status"],flush=True)
            print("Verified",len(finished),"/",len(jobs),dict(Counter(k[0] for k in finished)),flush=True)
            for panel in args.panels:
                labels=PANELS[panel][1]
                if panel not in published and all(k in finished for k in jobs if k[0] in labels and k[1] in labels[k[0]]):
                    publish(panel,list(finished.values()))
                    published.add(panel)
            if len(published)<len(args.panels):
                if not args.watch: raise SystemExit("Incomplete native batches; run with --watch")
                time.sleep(20)


if __name__=="__main__":
    main()
