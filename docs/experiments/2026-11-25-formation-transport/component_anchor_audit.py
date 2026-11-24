"""Pair the complete-component trial with the verified, identical moment baseline."""
import argparse
from bisect import bisect_left,bisect_right
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import hashlib
import json
from pathlib import Path
import endpoint_reciprocity_audit as audit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FLOW={"moment":"moment_3to2_600","component":"component_anchor_3to2_600"}


def fixed(output):
    ref=[r for r in csv.DictReader((HERE/"nearest_segment_fixed.csv").open(encoding="utf8")) if r["mode"]=="moment"]
    rows=[json.loads(p.read_bytes()) for p in sorted((ROOT/"tmp/nov25-complete-component").glob("*/row.json"))]
    assert len(rows)==len(ref)==28
    for r in rows:
        b=next(z for z in ref if all(str(r[k])==z[k] for k in ("road","profile","n","seed")))
        key="first_frame_sha" if r["profile"]=="long" else "entry_states_sha"
        assert r[key]==b[key] and r["tape_sha"]==b["tape_sha"]
    audit.write(output,ref+[{k:r.get(k) for k in ref[0]} for r in rows])


def read_cell(job):
    audit.FLOW=FLOW
    return audit.traffic_cell(job)


def traffic(output,rates,workers):
    with ProcessPoolExecutor(workers) as pool:
        panel=list(pool.map(read_cell,[(m,q) for m in FLOW for q in rates]))
    for r,first in panel:
        ref,base=next((s,v) for s,v in panel if s["flow"]==r["flow"] and s["model"]=="moment")
        assert base.keys()==first.keys() and r["arrivals_sha256"]==ref["arrivals_sha256"] and r["route_sha"]==ref["route_sha"]
        r["different_first_times"]=sum(s[0]!=base[k][0] for k,s in first.items())
        r["different_first_position_speed"]=sum(s[1:]!=base[k][1:] for k,s in first.items())
        r["first_state_sha"]=hashlib.sha256(json.dumps(first,sort_keys=True).encode()).hexdigest()
    audit.write(output,[r for r,_ in panel])


def gates(model):
    home=ROOT/"tmp/nov25study"/FLOW[model]/"3to2_s6_q1750"
    path=next(home.glob("*/positions.jsonl.gz"))
    stats=Counter()
    with gzip.open(path,"rt") as f:
        for line in f:
            frame=json.loads(line);t=frame["time_s"]
            if abs(t-round(t))>1e-7:continue
            xs=sorted(s[0] for s in frame["states"].values())
            starts=[0]+[i for i in range(1,len(xs)) if xs[i]-xs[i-1]>50]+[len(xs)]
            for i,x in enumerate(xs):
                if not 0<=x<800:continue
                idx=bisect_right(starts,i)-1
                full_lo,full_hi=starts[idx:idx+2]
                lo=bisect_left(xs,x-100);hi=bisect_right(xs,x+200)
                left,right=max(lo,full_lo),min(hi,full_hi)
                if right>=hi:continue
                stats["visible_forward_anchor"]+=1
                head_room=x+200-xs[right-1];tail_room=xs[left]-(x-100)
                assert head_room>=50
                complete=full_lo==left and full_hi==right
                if tail_room>=50:
                    assert complete
                    stats["certified"]+=1
                    stats["certified_singleton"]+=right-left==1
                elif complete:stats["rejected_complete"]+=1
                else:stats["rejected_incomplete"]+=1
    return dict(model=model,**{k:stats[k] for k in ("visible_forward_anchor","certified","certified_singleton",
                                                    "rejected_complete","rejected_incomplete")})


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--fixed",type=Path)
    p.add_argument("--flow",type=Path);p.add_argument("--gates",type=Path);p.add_argument("--models",nargs="+",default=list(FLOW))
    p.add_argument("--rates",nargs="+",type=int,default=(1500,1750,2000));p.add_argument("--workers",type=int,default=3)
    a=p.parse_args()
    if a.fixed:fixed(a.fixed)
    if a.flow:traffic(a.flow,a.rates,a.workers)
    if a.gates:audit.write(a.gates,[gates(m) for m in a.models])
