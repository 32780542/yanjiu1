"""Track physical endpoints across closing, observable breaks in the 1750/h/lane stream."""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BATCHES={"selected":"selected_development_600","group":"splice_group_600",
         **{k:f"pose_anchor_{k}_dev" for k in ("subflow","common","visible","shared_view","formed_pair","unanchored")}}


def evaluate(model):
    home=ROOT/"tmp/nov25study"/BATCHES[model]/"3to2_s6_q1750"
    run=next(home.glob("*/positions.jsonl.gz"))
    counts=Counter();previous={}
    def end(episode,reached):
        n,all_half,had_half,had_zero=episode
        if n>=11:
            counts["episodes_at_least_1s"]+=1
            counts["all_half_episodes"]+=all_half
            counts["both_bands_episodes"]+=had_half and had_zero
            counts["episodes_closing_to_50m"]+=reached
    with gzip.open(run,"rt") as f:
        for line in f:
            frame=json.loads(line);states=frame["states"];current={}
            order=sorted(states,key=lambda k:(states[k][0],states[k][1]))
            for j in range(len(order)-1):
                head,anchor=order[j],order[j+1];b,a=states[head],states[anchor]
                if not 0<=b[0]<800 or not 50<a[0]-b[0]<=200 or b[2]<=a[2]+1e-7:continue
                if (j and states[order[j-1]][0]==b[0]) or (j+2<len(order) and states[order[j+2]][0]==a[0]):
                    continue
                la,lb=round(a[1]/3.3-.5),round(b[1]/3.3-.5)
                if max(abs(a[1]-(la+.5)*3.3),abs(b[1]-(lb+.5)*3.3))>.3:continue
                i=j
                while i>0 and b[0]-states[order[i-1]][0]<=100 and states[order[i]][0]-states[order[i-1]][0]<=50:
                    i-=1
                count=j-i+1
                if count<2:continue
                d=5.5+.85*sum(states[k][2] for k in order[i:j+1])/count
                projected=a[0]-b[0]+.5*d*((la%2)-(lb%2))
                residual=abs(projected-round(projected/d)*d)
                zero=residual<=2+1e-9;half=d/2-residual<=2+1e-9
                counts["closing_pair_frames"]+=1;counts["near_zero"]+=zero;counts["near_half"]+=half
                counts["opposite_parity"]+=la%2!=lb%2
                for tag,lo,hi in (("50_100",50,100),("100_150",100,150),("150_200",150,200)):
                    if lo<a[0]-b[0]<=hi:
                        counts[tag]+=1;counts[tag+"_half"]+=half
                n,all_half,had_half,had_zero=previous.get((head,anchor),(0,True,False,False))
                current[head,anchor]=(n+1,all_half and half,had_half or half,had_zero or zero)
            for pair in previous.keys()-current.keys():
                head,anchor=pair
                reached=head in states and anchor in states and 0<states[anchor][0]-states[head][0]<=50
                end(previous[pair],reached)
            previous=current
    for entry in previous.values():end(entry,False)
    keys=("closing_pair_frames","near_zero","near_half","opposite_parity","50_100","50_100_half",
          "100_150","100_150_half","150_200","150_200_half","episodes_at_least_1s","all_half_episodes",
          "both_bands_episodes","episodes_closing_to_50m")
    return dict(model=model,**{k:counts[k] for k in keys})


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--models",nargs="+",required=True)
    p.add_argument("--csv",type=Path,required=True);a=p.parse_args()
    rows=[evaluate(m) for m in a.models]
    with a.csv.open("x",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
