"""Pair physical first states, 0.1 s two-layer exposures and both fixed-cohort stages."""
import argparse
import csv
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path

from persistent_flow import links
from measure import road_layout

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FIXED={"endpoint":"nov25-endpoint-reciprocal","extended":"nov25-endpoint-reciprocal",
       "baseline":"nov25-endpoint-base","mutual":"nov25-reciprocal"}
FLOW={"endpoint":"reciprocal_endpoint_dev","extended":"reciprocal_extended_dev",
      "baseline":"reciprocal_endpoint_base_dev","mutual":"reciprocal_mutual_600"}


def write(path,rows):
    with path.open("x",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)


def fixed(output):
    panel=[]
    for model,group in FIXED.items():
        rows=[json.loads(p.read_bytes()) for p in sorted((ROOT/"tmp"/group).glob(model+"_*/row.json"))]
        assert len(rows)==28
        panel.extend(rows)
    for r in panel:
        same=next(b for b in panel if b["mode"]=="baseline" and
                  all(r[k]==b[k] for k in ("n","seed","profile","road")))
        key="first_frame_sha" if r["profile"]=="long" else "entry_states_sha"
        assert r["tape_sha"]==same["tape_sha"] and r[key]==same[key]
    cols=("mode","road","n","profile","seed","upstream_m","status","completed","collisions","teleports",
          "same_ids_peak","upstream_peak_size","upstream_first_whole_s","upstream_whole_hold_s",
          "downstream_peak_size","downstream_first_whole_s","downstream_whole_hold_s",
          "first_connected_s","last_max_gap_up_m","formation_min_total_crossings","formation_total",
          "formation_min_max_crossings","formation_max_per_car","transform_min_total_crossings",
          "transform_total","transform_min_max_crossings","transform_max_per_car","tape_sha",
          "first_frame_sha","entry_states_sha","source_sha")
    write(output,[{k:r.get(k) for k in cols} for r in panel])


def traffic_cell(job):
    model,flow=job
    home=ROOT/"tmp/nov25study"/FLOW[model]/f"3to2_s6_q{flow}"
    row=json.loads((home/"row.json").read_bytes())
    run=next(home.glob("*/positions.jsonl.gz")).parent
    assert road_layout(run)==[(3,1000.),(2,200.)]
    regions=((3,0,800),(2,1000,1200))
    active=[{},{}];counts=[0,0];exposure=[[0.,0.,0.] for _ in regions]
    first={};previous=None
    with gzip.open(run/"positions.jsonl.gz","rt") as f:
        for line in f:
            frame=json.loads(line);t=frame["time_s"];states=frame["states"]
            if previous is not None:
                dt=t-previous;assert abs(dt-.1)<1e-7
                for j in range(2):
                    oldest={}
                    for pair,onset in active[j].items():
                        for layer in pair:
                            for name in layer:
                                oldest[name]=min(onset,oldest.get(name,onset))
                    exposure[j][0]+=dt*counts[j]
                    exposure[j][1]+=dt*len(oldest)
                    exposure[j][2]+=sum(max(0.,t-max(previous,onset+3.)) for onset in oldest.values())
            for name,state in states.items():
                if name not in first:first[name]=(t,*state[:3])
            for j,(lanes,lo,hi) in enumerate(regions):
                here={name:s for name,s in states.items() if lo<=s[0]<hi}
                counts[j]=len(here)
                pairs=links(here,lanes) if len(here)>=2*lanes else ()
                active[j]={p:active[j].get(p,t) for p in pairs}
            previous=t
    assert len(first)==row["completed"]
    out={k:row[k] for k in ("requested","departed","completed","collisions","teleports","mean_travel_time_s",
                              "mean_entry_wait_s","arrivals_sha256","controller_sha256","safe_drained","lane_changes")}
    out.update(model=model,flow=flow,route_sha=hashlib.sha256((run/"native.rou.xml").read_bytes()).hexdigest())
    for prefix,(den,yes,held) in zip(("up","down"),exposure):
        out[prefix+"_vehicle_s"]=round(den,4)
        out[prefix+"_instant_pct"]=100*yes/den
        out[prefix+"_held3_pct"]=100*held/den
    return out,first


def traffic(output,workers):
    jobs=[(m,flow) for m in FLOW for flow in (1500,1750,2000)]
    with ProcessPoolExecutor(workers) as pool:
        panel=list(pool.map(traffic_cell,jobs))
    for row,first in panel:
        control,base=next((r,firsts) for r,firsts in panel if r["flow"]==row["flow"] and r["model"]=="baseline")
        assert base.keys()==first.keys() and row["arrivals_sha256"]==control["arrivals_sha256"] and row["route_sha"]==control["route_sha"]
        row["different_first_times"]=sum(s[0]!=base[k][0] for k,s in first.items())
        row["different_first_position_speed"]=sum(s[1:]!=base[k][1:] for k,s in first.items())
        row["first_state_sha"]=hashlib.sha256(json.dumps(first,sort_keys=True).encode()).hexdigest()
    write(output,[r for r,_ in panel])


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixed",type=Path);p.add_argument("--traffic",type=Path)
    p.add_argument("--workers",type=int,default=3);a=p.parse_args()
    if a.fixed:fixed(a.fixed)
    if a.traffic:traffic(a.traffic,a.workers)
