"""Pair two traffic CSVs by road, seed, flow and demand period; check physical inputs.

Report per-run results, actual entry differences and the mean on-road time spent
in each road segment. Segment boundaries are the first front-position sample
at/after the boundary, so the mean components sum to the measured trip time.
The final 200 m of the approach is the lane-change preview zone in these runs.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
import math
from pathlib import Path
from statistics import mean
import xml.etree.ElementTree as ET

from measure import lane_of, road_layout

ROOT = Path(__file__).resolve().parents[3]


def index(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    mapping = {(r["road"], int(r["seed"]), float(r["flow"]), float(r["duration_s"])): r for r in rows}
    if len(mapping) != len(rows):
        raise ValueError(f"Duplicate road/seed/flow/duration in {path}")
    return mapping


def observations(folder, stop):
    trips = {r["vehicle_id"]:r for r in json.loads((folder/"trips.json").read_bytes())}
    (_, cut), _ = road_layout(folder)
    first, approach, downstream = {}, {}, {}
    end_state = None
    with gzip.open(folder/"positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            t, states = frame["time_s"], frame["states"]
            for k, (x,y,v,*_) in states.items():
                if k not in first:
                    first[k] = (lane_of(y), x, v)
                if x >= cut-200.:
                    approach.setdefault(k,t)
                if x >= cut:
                    downstream.setdefault(k,t)
            if abs(t-stop) < 1e-6:
                near = [v for x,y,v,*_ in states.values() if cut-200. <= x < cut]
                end_state = dict(approach_vehicles_at_stop=len(near), approach_lt5mps_at_stop=sum(v<5. for v in near),
                                 approach_stopped_at_stop=sum(v<.1 for v in near))
    r = json.loads((folder/"result.json").read_bytes())
    exited = sum(tr["exited_s"] is not None and tr["exited_s"] <= stop for tr in trips.values())
    entered = sum(tr["entered_s"] is not None and tr["entered_s"] <= stop for tr in trips.values())
    due = sum(tr["requested_s"] <= stop for tr in trips.values())
    summary = {k:r[k] for k in ("mode","status","completed","requested","collisions","teleports","mean_travel_time_s",
                                "mean_system_time_s","mean_entry_wait_s","exit_flow_veh_h","clearance_after_demand_s")}
    summary.update(exited_at_stop=exited, onroad_at_stop=entered-exited, entry_queue_at_stop=due-entered)
    if end_state is not None:
        summary.update(end_state)
    cohort = [k for k,tr in trips.items() if k in approach and k in downstream and tr["exited_s"] is not None]
    summary["spatial_trips"] = len(cohort)
    if cohort:
        summary["upstream_s"] = mean(approach[k]-trips[k]["entered_s"] for k in cohort)
        summary["last_200m_approach_s"] = mean(downstream[k]-approach[k] for k in cohort)
        summary["downstream_s"] = mean(trips[k]["exited_s"]-downstream[k] for k in cohort)
        if len(cohort)==r["requested"] and r["performance_comparison_eligible"]:
            assert math.isclose(summary["upstream_s"]+summary["last_200m_approach_s"]+summary["downstream_s"],
                                r["mean_travel_time_s"], abs_tol=1e-6)
    return summary, first, trips


def pair(job):
    (road,seed,flow,duration), left, right = job
    folders = [ROOT/entry["run_dir"] for entry in (left,right)]
    inputs = [json.loads((p/"input.json").read_bytes()) for p in folders]
    for k in ("arrivals", "physical", "speed_mode", "lane_change_mode", "positions_step_s"):
        if inputs[0][k] != inputs[1][k]:
            raise ValueError(f"Mismatched {k} for {road}/{flow}/{seed}")
    for fname in ("native.net.xml","native.rou.xml"):
        a,b = (ET.tostring(ET.parse(p/fname).getroot()) for p in folders)
        if a != b:
            raise ValueError(f"Mismatched {fname} for {road}/{flow}/{seed}")
    ls, lf, lt = observations(folders[0],duration)
    rs, rf, rt = observations(folders[1],duration)
    ids = lf.keys() & rf.keys()
    same_lane = sum(lf[k][0]==rf[k][0] for k in ids)
    same_speed = sum(abs(lf[k][2]-rf[k][2])<=1e-6 for k in ids)
    same_x = sum(abs(lf[k][1]-rf[k][1])<=1e-6 for k in ids)
    times = [abs(lt[k]["entered_s"]-rt[k]["entered_s"]) for k in ids]
    r = dict(road=road,seed=seed,flow=flow,duration_s=duration,arrivals_sha256=left["arrivals_sha256"],
             common_observed_entries=len(ids),equal_entry_times=sum(dt<=1e-6 for dt in times),
             equal_first_lanes=same_lane,equal_first_speeds=same_speed,equal_first_positions=same_x,
             max_entry_time_difference_s=max(times, default=None),mean_abs_entry_time_difference_s=mean(times) if times else None)
    for label, stats, entry in (("reference",ls,left),("comparison",rs,right)):
        r.update({label+"_"+k:v for k,v in stats.items()})
        r[label+"_run_dir"]=entry["run_dir"]
    return r


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference",type=Path)
    parser.add_argument("comparison",type=Path)
    parser.add_argument("--csv",type=Path,required=True)
    parser.add_argument("--workers",type=int,default=1)
    args=parser.parse_args()
    a,b=index(args.reference),index(args.comparison)
    if a.keys()!=b.keys():
        parser.error("The two indices must cover the same road/seed/flow/duration cases")
    jobs=[(k,a[k],b[k]) for k in sorted(a)]
    if args.workers>1:
        with ProcessPoolExecutor(args.workers) as pool:
            out=list(pool.map(pair,jobs))
    else:
        out=[pair(j) for j in jobs]
    with args.csv.open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,list(dict.fromkeys(k for r in out for k in r)))
        writer.writeheader()
        writer.writerows(out)
    print(args.csv,len(out))
