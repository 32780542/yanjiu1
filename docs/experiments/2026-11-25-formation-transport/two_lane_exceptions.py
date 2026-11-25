"""Explain the upstream geometry of two paired eleven-car exceptions."""
import csv
import gzip
import json
from pathlib import Path
from collections import Counter

from measure import centered, lane_of

HERE=Path(__file__).resolve().parent


def run(label, folder, seed):
    case = folder / f"candidate_2to3_11_long_{seed}"
    meta = json.loads((case/"row.json").read_bytes())
    trace = folder/meta["run"]/"positions.jsonl.gz"
    rows=[]
    with gzip.open(trace, "rt", encoding="utf8") as stream:
        for frame in map(json.loads,stream):
            states=frame["states"]
            if len(states)!=11 or any(s[0]>=2600 for s in states.values()) or not centered(states,2):
                continue
            order=sorted(states.values(),key=lambda s:-s[0])
            lanes=[lane_of(s[1]) for s in order]
            repeats=sum(a==b for a,b in zip(lanes,lanes[1:]))
            speeds=[s[2] for s in order]
            spacing=5.5+.85*sum(speeds)/len(speeds)
            counts=Counter(lanes)
            errors=[]
            for phase in (0,1):
                rank=Counter()
                origins=[]
                for s,lane in zip(order,lanes):
                    origins.append(s[0]+(rank[lane]+.5*(lane!=phase))*spacing)
                    rank[lane]+=1
                errors.append(max(origins)-min(origins))
            rows.append(dict(label=label,seed=seed,time_s=frame["time_s"],counts=f"{counts[0]}/{counts[1]}",
                             order="".join(map(str,lanes)),adjacent_same_lane_pairs=repeats,
                             speed_spread_mps=max(speeds)-min(speeds),best_origin_spread_m=min(errors),
                             head_to_tail_m=order[0][0]-order[-1][0]))
    # The last centered frame before the leader sees the road change; plus the
    # best common-grid fit seen at uniform speed and balanced occupancy.
    eligible=[r for r in rows if r["counts"] in ("5/6","6/5") and r["speed_spread_mps"]<=.5]
    best=min(eligible,key=lambda r:r["best_origin_spread_m"]) if eligible else None
    return [dict(snapshot=kind,**r) for kind,r in (("last_upstream",rows[-1]),("best_fit",best)) if r]


if __name__=="__main__":
    tmp=HERE.parents[2]/"tmp"
    rows=[]
    for seed,base,new in ((11254,"reference-fresh","hold-first"),(11321,"final-reference","hold-last")):
        for label,d in (("morning",base),("noon",new)):
            rows.extend(run(label,tmp/("nov25-noon-"+d),seed))
    with (HERE/"noon_two_lane_exceptions.csv").open("w",encoding="utf8",newline="") as out:
        writer=csv.DictWriter(out,list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
