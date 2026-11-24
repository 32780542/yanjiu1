"""Trace-only diagnostic of speed, spacing and middle-lane phase in the three-lane upstream."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STUDY=ROOT/"tmp/nov25study"
BATCHES={"selected":"selected_development_600","group":"splice_group_600",
         **{k:f"pose_anchor_{k}_dev" for k in ("subflow","common","visible","shared_view","formed_pair","unanchored")}}


def one(job):
    model,flow=job
    run=next((STUDY/BATCHES[model]/f"3to2_s6_q{flow}").glob("*/positions.jsonl.gz"))
    counts=Counter()
    with gzip.open(run,"rt") as f:
        for line in f:
            frame=json.loads(line);t=frame["time_s"]
            if abs(t-round(t))>1e-7:continue
            order=sorted((s for s in frame["states"].values() if 0<=s[0]<800),key=lambda s:-s[0])
            counts["cars"]+=len(order)
            counts["speed_sum"]+=sum(s[2] for s in order)
            counts["near_cap"]+=sum(s[2]>=33.2 for s in order)
            for k in range(len(order)-5):
                six=order[k:k+6]
                if k and order[k-1][0]==six[0][0] or k+6<len(order) and six[-1][0]==order[k+6][0]:
                    continue
                counts["windows"]+=1
                cols=[[] for _ in range(3)]
                for s in six:
                    j=round(s[1]/3.3-.5)
                    if 0<=j<3 and abs(s[1]-(j+.5)*3.3)<=.3:cols[j].append(s[0])
                if any(len(c)!=2 for c in cols):continue
                counts["balanced_centered"]+=1
                v=[s[2] for s in six];dynamic=5.5+.85*sum(v)/6
                same_speed=max(v)-min(v)<=.5+1e-9
                counts["speed"]+=same_speed
                for tag,d in (("fixed",30.),("adaptive",dynamic)):
                    same=all(abs(col[0]-col[1]-d)<=2+1e-9 for col in cols)
                    origins=[[cols[j][i]+(j%2)*d/2 for j in range(3)] for i in range(2)]
                    phase=all(max(o)-min(o)<=2+1e-9 for o in origins)
                    counts[tag+"_same"]+=same;counts[tag+"_phase"]+=phase
                    counts[tag+"_geometry"]+=same and phase
                    counts[tag+"_all"]+=same and phase and same_speed
                aligned=all(abs(cols[0][i]-cols[2][i])<=2+1e-9 for i in range(2))
                if aligned and same:
                    counts["phase_eligible"]+=1
                    residual=[(cols[0][i]+cols[2][i])/2-cols[1][i]-dynamic/2 for i in range(2)]
                    if max(map(abs,residual))<=2+1e-9: kind="correct"
                    elif residual[0]*residual[1]>0 and all(abs(abs(z)-dynamic/2)<=2 for z in residual):kind="half_gap_error"
                    elif residual[0]*residual[1]>0 and all(abs(abs(z)-dynamic)<=2 for z in residual):kind="full_gap_error"
                    else:kind="other"
                    counts[kind]+=1
    keys=("cars","speed_sum","near_cap","windows","balanced_centered","speed",
          "fixed_same","fixed_phase","fixed_geometry","fixed_all",
          "adaptive_same","adaptive_phase","adaptive_geometry","adaptive_all",
          "phase_eligible","correct","half_gap_error","full_gap_error","other")
    return dict(model=model,flow=flow,**{k:counts[k] for k in keys})


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",nargs="+",required=True);p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--workers",type=int,default=2)
    a=p.parse_args()
    jobs=[(model,q) for model in a.models for q in (1500,1750,2000)]
    with ProcessPoolExecutor(a.workers) as pool:rows=list(pool.map(one,jobs))
    with a.csv.open("x",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,rows[0]);writer.writeheader();writer.writerows(rows)
