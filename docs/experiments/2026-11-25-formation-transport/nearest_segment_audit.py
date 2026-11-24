"""Pair the moment and nearest sources using the same physical exposure evaluator."""
import argparse
from bisect import bisect_left,bisect_right
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import endpoint_reciprocity_audit as audit
from endpoint_reciprocity_check import load

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TRIAL=ROOT/"tmp/nov25-nearest-segment"
FLOW={"moment":"moment_3to2_600","nearest":"nearest_segment_3to2_600"}


def read_cell(job):
    audit.FLOW=FLOW
    return audit.traffic_cell(job)


def flow_panel(output,workers,rates):
    jobs=[(m,q) for m in FLOW for q in rates]
    with ProcessPoolExecutor(workers) as pool:panel=list(pool.map(read_cell,jobs))
    for r,first in panel:
        ref,base=next((s,f) for s,f in panel if s["flow"]==r["flow"] and s["model"]=="moment")
        assert r["arrivals_sha256"]==ref["arrivals_sha256"] and r["route_sha"]==ref["route_sha"] and base.keys()==first.keys()
        r["different_first_times"]=sum(s[0]!=base[k][0] for k,s in first.items())
        r["different_first_position_speed"]=sum(s[1:]!=base[k][1:] for k,s in first.items())
        r["first_state_sha"]=hashlib.sha256(json.dumps(first,sort_keys=True).encode()).hexdigest()
    audit.write(output,[r for r,_ in panel])


def fixed_panel(output):
    rows=[json.loads(p.read_bytes()) for p in sorted(TRIAL.glob("*/row.json"))];assert len(rows)==56
    for r in rows:
        b=next(z for z in rows if z["mode"]=="moment" and all(z[k]==r[k] for k in ("road","profile","n","seed")))
        field="first_frame_sha" if r["profile"]=="long" else "entry_states_sha"
        assert b[field]==r[field] and b["tape_sha"]==r["tape_sha"]
    keys=("mode","road","n","seed","profile","status","completed","collisions","teleports",
          "same_ids_peak","upstream_peak_size","downstream_peak_size","upstream_whole_hold_s","downstream_whole_hold_s",
          "upstream_first_whole_s","downstream_first_whole_s","first_connected_s","last_max_gap_up_m",
          "formation_total","formation_min_total_crossings","formation_max_per_car","formation_min_max_crossings",
          "transform_total","transform_min_total_crossings","transform_max_per_car","transform_min_max_crossings",
          "tape_sha","first_frame_sha","entry_states_sha","source_sha")
    audit.write(output,[{k:r.get(k) for k in keys} for r in rows])


def sample(model):
    native=load(TRIAL/"frozen/nearest")
    file=next((ROOT/"tmp/nov25study"/FLOW[model]/"3to2_s6_q1750").glob("*/positions.jsonl.gz"))
    counts=Counter()
    with gzip.open(file,"rt") as f:
        for line in f:
            frame=json.loads(line);t=frame["time_s"]
            if abs(t-round(t))>1e-7:continue
            cars=sorted((native.Vehicle(k,s[0],s[1],s[2],round(s[1]/3.3-.5)) for k,s in frame["states"].items()),
                        key=lambda c:(c.x,c.lane))
            xs=[c.x for c in cars];starts=[0]+[j for j in range(1,len(cars)) if xs[j]-xs[j-1]>50]+[len(cars)]
            gaps=[xs[j]-xs[j-1] for j in starts[1:-1]]
            allowed=set()
            for edge,gap in enumerate(gaps):
                prev=gaps[edge-1] if edge else float("inf")
                nex=gaps[edge+1] if edge+1<len(gaps) else float("inf")
                if gap<=prev and gap<nex:allowed.add(edge)
            seen=set()
            for i,ego in enumerate(cars):
                if not 0<=ego.x<800:continue
                edge=bisect_right(starts,i)-1
                lo=bisect_left(xs,ego.x-100);hi=bisect_right(xs,ego.x+200)
                rows=cars[lo:i]+cars[i+1:hi]
                grp=list(reversed(native._local_group(ego,rows)))
                if not any(c.x>grp[0].x for c in rows):continue
                counts["original_opportunities"]+=1
                if native._nearest_segment_anchor(grp,rows) is None:continue
                counts["locally_accepted"]+=1
                counts["accepted_outside_global_matching"]+=edge not in allowed
                seen.add(edge)
            counts["sample_frames"]+=1
            counts["frames_with_adjacent_accepted_edges"]+=any(edge+1 in seen for edge in seen)
    return dict(model=model,**counts)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--fixed",type=Path)
    p.add_argument("--flow",type=Path);p.add_argument("--gates",type=Path)
    p.add_argument("--rates",nargs="+",type=int,default=(1500,1750,2000))
    p.add_argument("--models",nargs="+",default=list(FLOW));p.add_argument("--workers",type=int,default=3)
    a=p.parse_args()
    if a.fixed:fixed_panel(a.fixed)
    if a.flow:flow_panel(a.flow,a.workers,a.rates)
    if a.gates:audit.write(a.gates,[sample(m) for m in a.models])
