"""Audit either the 1,800 s history comparison or the independent one-hour reference."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from itertools import product
from statistics import mean
import time

from validate_traffic import BATCH, HERE, ROOT, audit_case, compare, digest, read, write_csv
from check_crossing_trace import check as coordinate_ledger


ROADS = ("3to2", "4to3")
PANELS = {
    "history": (1800, (3801, 3802), (1500, 1750, 2000), {
        "history": "fair_history_1800", "base": "fair_base_1800"}),
    "hour": (3600, (4801,), (2000,), {
        "selected": "long_selected_3600", "11.24": "long_1124_3600", "NOA": "long_noa_3600"}),
}
NAMES = {"history": "历史信息方案", "base": "选定方案", "selected": "选定方案",
         "11.24": "11.24", "NOA": "纯 NOA"}
REFERENCE = {"base": "selected_development_600", "selected": "selected_development_600",
             "11.24": "baseline_1124_traffic", "NOA": "selected_development_600"}


def design(panel):
    duration, seeds, flows, methods = PANELS[panel]
    jobs = {}
    for method, label in methods.items():
        batch = BATCH / label
        manifest = read(batch / "manifest.json")
        source, args = manifest["files"], manifest["arguments"]
        mode = "noa" if method == "NOA" else "transform"
        if (set(args["roads"]) != set(ROADS) or set(args["seeds"]) != set(seeds)
                or set(args["flows"]) != set(flows) or args["duration"] != duration or args["mode"] != mode):
            raise ValueError(f"Case matrix differs in {label}")
        for name, wanted in source.items():
            if digest((batch / "source" / name).read_bytes()) != wanted:
                raise ValueError(f"Frozen content differs in {label}/{name}")
        if method in REFERENCE and source != read(BATCH / REFERENCE[method] / "manifest.json")["files"]:
            raise ValueError(f"Frozen source differs from the earlier comparison in {label}")
        for road, flow, seed in product(ROADS, flows, seeds):
            p = batch / f"{road}_s{seed}_q{flow}" / "row.json"
            jobs[(method, road, flow, seed)] = (label, road, flow, seed, p, source, (panel, method, duration))
    return jobs


def audit(job):
    return audit_case(*job)


def metric(rows, key, *, diff=False):
    if not rows:
        return "—"
    nums = [r[key] for r in rows]
    if diff:
        return (f"{mean(nums):+.2f} [{min(nums):+.2f}, {max(nums):+.2f}]"
                if len(nums)>1 else f"{nums[0]:+.2f}")
    return f"{mean(nums):.2f}"


def actual_crossing_load(row):
    trips = read(ROOT / row["run_dir"] / "trips.json")
    repeats = {}
    for label, lower in (("whole", 0), ("approach_down", 800)):
        counts = [sum(abs(e["from_lane"]-e["to_lane"]) for e in trip["lane_events"] if e["x"] >= lower)
                  for trip in trips]
        repeats[label+"_crossings"] = sum(counts)
        repeats[label+"_two_or_more_pct"] = 100*sum(n>=2 for n in counts)/len(counts)
        repeats[label+"_max_per_vehicle"] = max(counts)
    if repeats["whole_crossings"] != row["crossings"]:
        raise ValueError("Individual crossing counts differ from the native event ledger")
    return repeats


def add_crossing_table(lines, runs):
    rows = []
    for run in runs:
        row = {k:run[k] for k in ("road","flow","seed","method","requested","run_dir")}
        native=actual_crossing_load(run)
        label=PANELS["history"][3][run["method"]]
        case=f"{run['road']}_s{run['seed']}_q{run['flow']}"
        coords=coordinate_ledger(label,case,individual=True)
        physical={
            "center_whole_crossings":coords["coordinate_crossings"],
            "center_whole_two_or_more_pct":100*coords["coordinate_vehicles_crossed_twice_or_more"]/coords["vehicles"],
            "center_whole_max_per_vehicle":coords["coordinate_vehicle_crossing_max"],
            "center_approach_down_crossings":coords["coordinate_approach_crossings"]+coords["coordinate_downstream_crossings"],
            "center_approach_down_two_or_more_pct":100*coords["coordinate_approach_down_two_or_more"]/coords["vehicles"],
            "center_approach_down_max_per_vehicle":coords["coordinate_approach_down_vehicle_max"]}
        rows.append(dict(row, **native, **physical))
    write_csv("history_individual_crossings.csv", rows)
    lines += ["", "## 每车实际跨界负担", ""]
    by_key = {(r["road"],r["flow"],r["seed"],r["method"]):r for r in rows}
    for road in ROADS:
        effects = []
        for flow, seed in product(PANELS["history"][2], PANELS["history"][1]):
            key = "center_approach_down_two_or_more_pct"
            effects.append(by_key[(road,flow,seed,"history")][key] - by_key[(road,flow,seed,"base")][key])
        lines.append(f"- {road.replace('to','→')} 的 {len(effects)} 个配对中，{sum(x<0 for x in effects)} 个配对的历史方案降低了接近段及下游累计跨越至少两道边界的车辆占比，逐种子差值为 {min(effects):+.2f} 至 {max(effects):+.2f} 个百分点。")
    lines += ["",
              "对每辆实际入场车，从车心的横向轨迹累计已越过的标线。末帧恰好压线时保留此前一侧。下表以两个种子等权计算至少两次越线的车辆占比，再取两次运行中最高的单车次数。接近段和下游取物理位置 x ≥ 800 m，包含缩道前的最后 200 m。CSV 的 center 字段为车心越线，其余字段记录 SUMO 原生车道索引事件。", "",
              "| 道路 | 流量 | 方法 | 全程至少两次 % | 全程最多 | 接近段及下游至少两次 % | 该段最多 |",
              "|---|---:|---|---:|---:|---:|---:|"]
    for road, flow, method in product(ROADS, PANELS["history"][2], PANELS["history"][3]):
        sample = [r for r in rows if (r["road"],r["flow"],r["method"]) == (road,flow,method)]
        cells = []
        for region in ("whole","approach_down"):
            cells.extend((metric(sample,"center_"+region+"_two_or_more_pct"), str(max(r["center_"+region+"_max_per_vehicle"] for r in sample))))
        lines.append(f"| {road.replace('to','→')} | {flow} | {NAMES[method]} | " + " | ".join(cells) + " |")
    lines += ["", "[逐种子实际跨界分布及记录目录](history_individual_crossings.csv)"]


def read_rows(path):
    def native(key, value):
        if key in ("method","reference","panel","road","run_dir","status") or key.endswith("_sha256"):
            return value
        if value == "True": return True
        if value == "False": return False
        if value == "": return None
        try:
            return int(value)
        except ValueError:
            try: return float(value)
            except ValueError: return value
    with path.open(encoding="utf-8", newline="") as stream:
        return [{k:native(k,v) for k,v in row.items()} for row in csv.DictReader(stream)]


def report(panel, runs, pairs):
    duration, seeds, flows, methods = PANELS[panel]
    candidate = next(iter(methods))
    title = "1800 秒历史信息对照" if panel == "history" else "3600 秒高流量对照"
    lines = ["# " + title, "",
             f"每次连续来车 {duration} 秒，种子为 " + "、".join(map(str, seeds)) + "。"
             "逐对核对来车请求、SUMO 路网、路线与车辆物理设置。对照双方按车辆标识核对第一帧实际入口车道、位置和速度。", ""]
    for method in methods:
        sample = [r for r in runs if r["method"] == method]
        if len(sample)!=len(ROADS)*len(seeds)*len(flows):
            raise ValueError(f"Incomplete report rows for {method}")
        complete = sum(r["completed"] for r in sample)
        requested = sum(r["requested"] for r in sample)
        collisions = sum(r["collisions"] for r in sample)
        teleports = sum(r["teleports"] for r in sample)
        lines.append(f"- {NAMES[method]}完成 {complete:,}/{requested:,} 辆次，碰撞 {collisions}、瞬移 {teleports}。")
    lines+=["", "## 配对结果", ""]
    for road, ref in product(ROADS, list(methods)[1:]):
        subset = [r for r in pairs if r["eligible"] and (r["road"],r["reference"])==(road,ref)]
        if not subset:
            continue
        time_d = [r["delta_travel_s"] for r in subset]
        durable_d = [r["delta_held_3s_pct"] for r in subset]
        if len(subset) == 1:
            finding = f"路内行程差 {time_d[0]:+.2f} 秒，持续 3 秒后的下游交错占比差 {durable_d[0]:+.2f} 个百分点。"
        else:
            finding = (f"{len(subset)} 个同种子、同流量配对中有 {sum(x<0 for x in time_d)} 个路内行程较短，"
                       f"{sum(x>0 for x in durable_d)} 个持续 3 秒后的下游交错占比较高。")
        lines.append(f"- {road.replace('to','→')}，{NAMES[candidate]}相对{NAMES[ref]}，{finding}")
    lines += ["", "每行对种子等权平均。路内时间从实际入场累计到离场。上、下游几何占比按整秒统计完整相邻两层的车辆占比。持续占比使用 0.1 秒轨迹，识别同一组车辆、同一排列连续满足条件 1/3/5 秒后的下游车辆时间。", "",
              "| 道路 | 辆/h/道 | 方法 | 路内秒 | 上游 % | 下游 % | 持续 1 / 3 / 5 秒后 % |",
              "|---|---:|---|---:|---:|---:|---:|"]
    for road, flow, method in product(ROADS, flows, methods):
        sample = [r for r in runs if r["eligible"] and (r["road"],r["flow"],r["method"]) == (road,flow,method)]
        scores = [metric(sample,k) for k in ("travel_s","up_pct","down_pct")]
        scores.append(" / ".join(metric(sample, f"held_{s}s_pct") for s in (1,3,5)))
        lines.append(f"| {road.replace('to','→')} | {flow} | {NAMES[method]} | " + " | ".join(scores) + " |")
    lines += ["", f"## {NAMES[candidate]}减各参照的同种子差值", "",
              "路内时间差为秒，几何占比差为百分点。" +
              ("每格给出两个种子的均值和各自差值范围。" if len(seeds)>1 else "每格均为种子 4801 的实测差值。"), "",
              "| 道路 | 流量 | 参照 | 配对数 | 路内秒差 | 上游差 | 下游差 | 持续 1 秒差 | 持续 3 秒差 | 持续 5 秒差 |",
              "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for road, flow, ref in product(ROADS, flows, list(methods)[1:]):
        sample = [r for r in pairs if r["eligible"] and (r["road"],r["flow"],r["reference"]) == (road,flow,ref)]
        present = [r for r in pairs if (r["road"],r["flow"],r["reference"]) == (road,flow,ref)]
        if len(present)!=len(seeds):
            raise ValueError(f"Incomplete comparison rows for {road}, {flow}, {ref}")
        cells = [metric(sample,"delta_"+key,diff=True) for key in ("travel_s","up_pct","down_pct",
                                                                   "held_1s_pct","held_3s_pct","held_5s_pct")]
        lines.append(f"| {road.replace('to','→')} | {flow} | {NAMES[ref]} | {len(sample)} | " + " | ".join(cells) + " |")
    lines += ["", f"实际入场时刻相同的逐车方法配对为 {sum(r['same_entry_time'] for r in pairs):,}/"
              f"{sum(r['actual_entry_pairs'] for r in pairs):,}，最大绝对差 {max(r['max_abs_entry_difference_s'] for r in pairs):.2f} 秒。"
              "原生安全插入会改变实际入场时间。固定 30 m 同道间距可漏计压缩队列，200 m 下游会截断长时观察。", "",
              (f"[逐次运行与原轨迹目录]({panel}_continuous_runs.csv) · "
               f"[逐种子配对差、提交与实际跨界]({panel}_continuous_pairs.csv) · "
               "[复算脚本](validate_extended_traffic.py)")]
    if panel == "history":
        add_crossing_table(lines, runs)
    (HERE/f"{panel}_continuous_results.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", choices=PANELS)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--report-only", action="store_true", help="Re-render from the completed audited CSVs")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.report_only:
        report(args.panel, read_rows(HERE/f"{args.panel}_continuous_runs.csv"),
               read_rows(HERE/f"{args.panel}_continuous_pairs.csv"))
        return
    jobs = design(args.panel)
    complete = {}
    with ProcessPoolExecutor(args.workers) as pool:
        while len(complete) < len(jobs):
            ready = [(key,job) for key,job in jobs.items() if key not in complete and job[4].is_file()]
            for (key,_), row in zip(ready, pool.map(audit, (job for _,job in ready))):
                complete[key] = row
                if not row["eligible"]:
                    print("INELIGIBLE", key, row["status"], flush=True)
            print(args.panel, "verified", len(complete), "/", len(jobs), flush=True)
            if len(complete) < len(jobs):
                if not args.watch:
                    raise SystemExit("Incomplete native batches; run with --watch")
                time.sleep(20)
    rows = [complete[key] for key in jobs]
    pairs = compare(rows, candidate=next(iter(PANELS[args.panel][3])))
    write_csv(f"{args.panel}_continuous_runs.csv", rows)
    write_csv(f"{args.panel}_continuous_pairs.csv", pairs)
    report(args.panel, rows, pairs)
    print(args.panel, "published", len(rows), "runs,", len(pairs), "paired cases", flush=True)


if __name__ == "__main__":
    main()
