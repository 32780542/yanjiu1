"""Measure finite two-layer links separately from whole upstream cohort formation."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
from pathlib import Path
from persistent_flow import links

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def one(home):
    row=json.loads((home/"row.json").read_bytes())
    n=row["n"];lanes=int(row["road"][0]);cut=row["upstream_m"]-200
    patch=next(home.glob("*/positions.jsonl.gz"));active={};last=None;qualified=False
    vehicle_s=formed_s=mature_s=longest=0.
    with gzip.open(patch,"rt") as f:
        for line in f:
            frame=json.loads(line);t=frame["time_s"];states=frame["states"]
            if last is not None and qualified:
                dt=t-last
                vehicle_s+=n*dt
                oldest={}
                for pair,onset in active.items():
                    longest=max(longest,last-onset)
                    for layer in pair:
                        for k in layer:oldest[k]=min(onset,oldest.get(k,onset))
                formed_s+=len(oldest)*dt
                mature_s+=sum(max(0.,t-max(last,b+3)) for b in oldest.values())
            qualified=len(states)==n and all(0<=s[0]<cut for s in states.values())
            pairs=links(states,lanes) if qualified else ()
            active={pair:active.get(pair,t) for pair in pairs}
            last=t
            if states and min(s[0] for s in states.values())>=cut:break
    return dict(model=row["mode"],road=row["road"],n=n,seed=row["seed"],up_whole_s=row["upstream_whole_hold_s"],
        up_peak=row["upstream_peak_size"],longest_same_link_s=round(longest,3),vehicle_s=round(vehicle_s,3),
        any_link_pct=100*formed_s/vehicle_s,held3_link_pct=100*mature_s/vehicle_s)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",nargs="+",required=True);p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--workers",type=int,default=3);a=p.parse_args()
    jobs=[]
    for model in a.models:
        name={"shared_view":"nov25-shared-view-anchor","formed_pair":"nov25-formed-pair-anchor",
              "unanchored":"nov25-unanchored-control"}.get(model,"nov25-pose-anchor")
        jobs.extend(sorted(p.parent for p in (ROOT/"tmp"/name).glob(f"{model}_*_long_*/row.json")))
    assert len(jobs)==24*len(a.models)
    with ProcessPoolExecutor(a.workers) as pool:rows=list(pool.map(one,jobs))
    with a.csv.open("x",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
