"""Audit the five frozen traffic batches, then summarize matched seeds. Use --watch while running."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import itertools
import json
from pathlib import Path
from statistics import mean
import time
import xml.etree.ElementTree as ET

from persistent_flow import measure_persistence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BATCH = ROOT / "tmp/nov25study"
DATA = {
    "selected_development_600": ("development", "selected", 600, ("3to2","4to3","2to3","3to4"), (6,20)),
    "baseline_1124_traffic": ("development", "11.24", 600, ("3to2","4to3"), (6,20)),
    "pure_noa_matched": ("development", "NOA", 600, ("3to2","4to3"), (6,20)),
    "selected_holdout_900": ("holdout", "selected", 900, ("3to2","4to3"), (2701,2702,2703,2704)),
    "holdout_base_900": ("holdout", "11.24", 900, ("3to2","4to3"), (2701,2702,2703,2704)),
}
FLOWS = (1500,1750,2000)
OUTCOMES = ("travel_s","up_pct","down_pct","held_1s_pct","held_3s_pct","held_5s_pct",
            "submitted","crossings","finished","exit_flow_veh_h","clearance_s")


def read(path):
    return json.loads(path.read_bytes())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return digest(json.dumps(obj, sort_keys=True).encode())


def plans():
    expected, hashes = {}, {}
    for label,(panel,method,duration,roads,seeds) in DATA.items():
        batch = BATCH/label
        manifest = read(batch/"manifest.json")
        opts, files = manifest["arguments"], manifest["files"]
        if (set(opts["roads"]) != set(roads) or set(opts["seeds"]) != set(seeds) or
                set(opts["flows"]) != set(FLOWS) or opts["duration"] != duration):
            raise ValueError(f"Unexpected frozen case design in {label}")
        for name,value in files.items():
            if digest((batch/"source"/name).read_bytes()) != value:
                raise ValueError(f"Frozen source mismatch in {label}/{name}")
        hashes[label] = files
        for road,flow,seed in itertools.product(roads,FLOWS,seeds):
            expected[(label,road,flow,seed)] = batch/f"{road}_s{seed}_q{flow}"/"row.json"
    if hashes["selected_development_600"] != hashes["selected_holdout_900"]:
        raise ValueError("Selected method changed between development and confirmation")
    if hashes["baseline_1124_traffic"] != hashes["holdout_base_900"]:
        raise ValueError("11.24 reference changed between panels")
    return expected, hashes


def run_audit(job):
    (label,road,flow,seed), row_path, manifest = job
    return audit_case(label, road, flow, seed, row_path, manifest, DATA[label][:3])


def audit_case(label, road, flow, seed, row_path, manifest, design, *, physical_counts=False):
    panel,method,duration = design
    index = read(row_path)
    folder = ROOT/index["run_dir"]
    result, config = read(folder/"result.json"), read(folder/"input.json")
    if (folder.parent != row_path.parent or config["source_sha256"] != result["source_sha256"] or
            any(manifest[k]!=v or digest((folder/"source"/k).read_bytes())!=v for k,v in result["source_sha256"].items())):
        raise ValueError(f"Run snapshot mismatch: {folder}")
    if any(digest((folder/name).read_bytes()) != index[field] for name,field in
           (("input.json","input_sha256"),("result.json","result_sha256"))):
        raise ValueError(f"Result/index mismatch: {folder}")
    if (index["road"], result["flow_veh_h_lane"], result["seed"], result["demand_duration_s"],
            result["mode"]) != (road, flow, seed, duration, "noa" if method=="NOA" else "transform"):
        raise ValueError(f"Case parameters mismatch: {folder}")
    first = {}
    persistence = measure_persistence(folder, first_seen=first)
    arrivals = config["arrivals"]
    if canonical(arrivals) != index["arrivals_sha256"] or canonical(arrivals) != persistence["arrivals_sha256"]:
        raise ValueError(f"Demand mismatch: {folder}")
    trips = read(folder/"trips.json")
    unique = {r["vehicle_id"] for r in trips}
    if len(unique) != len(trips) or unique != {r["vehicle_id"] for r in arrivals}:
        raise ValueError(f"Trip identities mismatch: {folder}")
    complete = sum(r["exited_s"] is not None for r in trips)
    events = [e for r in trips for e in r["lane_events"]]
    crossings = sum(abs(e["from_lane"]-e["to_lane"]) for e in events)
    finished = sum(len(r["lane_completion_events"]) for r in trips)
    if (len(trips), complete, len(events), finished) != (result["requested"],result["completed"],
            result["lane_changes"],result["lane_change_completions"]):
        raise ValueError(f"Native event ledger mismatch: {folder}")
    eligible = bool(result["performance_comparison_eligible"])
    if eligible and (result["status"]!="drained" or result["collisions"] or result["teleports"] or complete!=len(trips)):
        raise ValueError(f"Inconsistent eligibility: {folder}")
    if eligible and (set(first)!=unique or abs(mean(r["exited_s"]-r["entered_s"] for r in trips)-
            result["mean_travel_time_s"])>1e-7):
        raise ValueError(f"Incomplete trace or travel mismatch: {folder}")
    if eligible and any(first[a["vehicle_id"]] != (a["lane"],a["x"],a["speed"]) for a in arrivals):
        raise ValueError(f"Actual starting position/lane/speed differs from the demand tape: {folder}")
    secs = [persistence[f"held_{h}s_pct"] or 0 for h in (0,1,3,5)]
    if any(a+1e-8 < b for a,b in zip(secs,secs[1:])):
        raise ValueError(f"Non-monotone duration thresholds: {folder}")
    out = dict(panel=panel, method=method, road=road, flow=flow, seed=seed, duration_s=duration,
        requested=len(trips), completed=complete, status=result["status"], eligible=eligible,
        collisions=result["collisions"], teleports=result["teleports"], travel_s=result["mean_travel_time_s"],
        up_pct=index["upstream_formed_pct"], down_pct=index["downstream_formed_pct"],
        held_0s_pct=persistence["held_0s_pct"], held_1s_pct=persistence["held_1s_pct"],
        held_3s_pct=persistence["held_3s_pct"], held_5s_pct=persistence["held_5s_pct"],
        submitted=result["execution"].get("native_lane_requests",0), crossings=crossings, finished=finished,
        exit_flow_veh_h=result["exit_flow_veh_h"], clearance_s=result["clearance_after_demand_s"],
        arrivals_sha256=index["arrivals_sha256"], initial_state_sha256=canonical(first),
        network_sha256=digest(ET.tostring(ET.parse(folder/"native.net.xml").getroot())),
        routes_sha256=digest(ET.tostring(ET.parse(folder/"native.rou.xml").getroot())),
        physical_sha256=canonical([config[k] for k in ("physical","speed_mode","lane_change_mode","positions_step_s")]),
        run_dir=index["run_dir"])
    if physical_counts:
        out["source_manifest_sha256"] = canonical(manifest)
        out["native_rules_sha256"] = manifest["noa/native_rules.py"]
        out["staggered_sha256"] = manifest.get("noa/staggered.py","")
        for region, short in (("upstream","up"),("downstream","down")):
            for field in ("vehicle_samples","formed_vehicle_samples","peak_multilayer_size"):
                out[f"{short}_{field}"] = index[f"{region}_{field}"]
            n = out[f"{short}_vehicle_samples"]
            made = out[f"{short}_formed_vehicle_samples"]
            if n and abs(100*made/n-out[f"{short}_pct"])>1e-8:
                raise ValueError(f"Geometry numerator differs in {folder}")
        out["downstream_vehicle_s"] = persistence["downstream_vehicle_s"]
        for h in (0,1,3,5):
            out[f"held_{h}s_vehicle_s"] = persistence[f"held_{h}s_vehicle_s"]
        counts = [sum(abs(e["to_lane"]-e["from_lane"]) for e in tr["lane_events"]) for tr in trips]
        out["crossings_per_100"] = 100*crossings/complete if complete else None
        out["vehicles_crossed"] = sum(n>0 for n in counts)
        out["vehicles_crossed_twice_or_more"] = sum(n>=2 for n in counts)
        out["vehicle_crossing_max"] = max(counts,default=0)
        bins = [
            sum(abs(e["to_lane"]-e["from_lane"]) for e in events if low <= e["x"] < high)
            for low,high in ((0,800),(800,1000),(1000,float("inf")))
        ]
        if sum(bins)!=crossings:
            raise ValueError(f"Crossing location ledger mismatch: {folder}")
        out["upstream_crossings"],out["approach_crossings"],out["downstream_crossings"] = bins
    return out


def compare(rows, candidate="selected", outcomes=OUTCOMES):
    pairs = []
    by_key = {(r["panel"],r["road"],r["flow"],r["seed"],r["method"]): r for r in rows}
    for (panel,road,flow,seed,method),ref in by_key.items():
        if method == candidate:
            continue
        test = by_key[(panel,road,flow,seed,candidate)]
        for field in ("arrivals_sha256","physical_sha256","routes_sha256","network_sha256"):
            if ref[field] != test[field]:
                raise ValueError(f"Unmatched {field}: {test['run_dir']} / {ref['run_dir']}")
        eligible = test["eligible"] and ref["eligible"]
        if eligible and test["initial_state_sha256"]!=ref["initial_state_sha256"]:
            raise ValueError("Realized entering lane, position or speed differs between methods")
        entries = []
        for r in (test,ref):
            entries.append({v["vehicle_id"]:v["entered_s"] for v in read(ROOT/r["run_dir"]/"trips.json")})
        common = [abs(t-entries[1][k]) for k,t in entries[0].items() if t is not None and entries[1][k] is not None]
        delta = dict(panel=panel, road=road, flow=flow, seed=seed, reference=method, eligible=eligible,
            actual_entry_pairs=len(common), same_entry_time=sum(dt<1e-8 for dt in common),
            max_abs_entry_difference_s=max(common, default=None))
        for field in outcomes:
            delta["delta_"+field] = test[field]-ref[field] if eligible else None
        pairs.append(delta)
    return pairs


def write_csv(name, rows):
    path=HERE/name
    tmp=path.with_suffix(".writing")
    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer=csv.DictWriter(stream, rows[0])
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args=parser.parse_args()
    expected, hashes=plans()
    audited={}
    with ProcessPoolExecutor(args.workers) as pool:
        while len(audited)<len(expected):
            available=[(k,p,hashes[k[0]]) for k,p in expected.items() if k not in audited and p.is_file()]
            for (key,_,_), row in zip(available,pool.map(run_audit,available)):
                audited[key]=row
                if not row["eligible"]:
                    print("INELIGIBLE",key,row["status"],flush=True)
            print("Checked",len(audited),"/",len(expected),dict(Counter(k[0] for k in audited)),flush=True)
            if len(audited)<len(expected):
                if not args.watch:
                    raise SystemExit("Incomplete native batches; use --watch")
                time.sleep(20)
    rows=[audited[k] for k in expected]
    pairs=compare(rows)
    write_csv("continuous_runs.csv",rows)
    write_csv("continuous_seed_differences.csv",pairs)
    print("Verified",len(rows),"runs and",len(pairs),"seed pairs",flush=True)


if __name__=="__main__":
    main()
