"""Re-run one recorded initial state, logging the ego's local inputs before each crossing."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path);p.add_argument("batch",type=Path);p.add_argument("case")
    p.add_argument("out",type=Path);p.add_argument("--vehicle",required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.source.resolve()))
    from experiments import native_sumo as native
    from noa import staggered as st
    from noa import native_rules as rules
    ids=a.case.split("_")
    olddir=a.batch/("candidate_"+a.case)
    prior=json.loads((olddir/"row.json").read_bytes())
    original=a.batch/prior["run"]
    old=json.loads((original/"input.json").read_bytes())
    name=old["case"]["scenario"]
    native.ROAD_LAYOUT[name]=(2800,1000,int(ids[0][-1]))
    obs=native.LocalTracks.observe
    choose=st.choose_target
    solve=st.solve_transport
    log=[]
    state={}
    def capture(self,key,*args,**kwargs):
        ego,neighbors=obs(self,key,*args,**kwargs)
        state["tracked"]=key==a.vehicle
        if state["tracked"]:
            state.update(time=ego.time,x=ego.x,current=ego.lane,
                         local_view=len(neighbors)+1)
        return ego,neighbors
    def record(vehicles,slots,**kwargs):
        fit=solve(vehicles,slots,**kwargs)
        if state["tracked"]:
            i=kwargs["ego_index"]
            state.update(target=slots[fit.assignment[i]][0], action=fit.action_lane,
                         B=fit.max_crossings,C=fit.total_crossings,action_gap=fit.action_gap,
                         robust_bound=fit.action_lower_bound,group_n=len(vehicles),
                         source_counts="/".join(str(Counter(s for s,_ in vehicles)[k]) for k in range(4)),
                         target_counts="/".join(str(Counter(s for s,_ in slots)[k]) for k in range(4)))
        return fit
    def snapshot(*args,**kwargs):
        target=choose(*args,**kwargs)
        if state["tracked"]:
            log.append({k:v for k,v in state.items() if k!="tracked"})
        return target
    native.LocalTracks.observe=capture
    st.choose_target=snapshot
    st.solve_transport=record
    tape=json.loads((a.batch/"tapes"/(a.case+".json")).read_bytes())
    output=native.run_case(mode="transform",scenario=name,seed=int(ids[-1]),flow=1750,duration=8,gui=False,
                           output_base=a.out,initial=tape)
    def fingerprint(folder):
        with gzip.open(folder/"positions.jsonl.gz","rb") as stream:
            return hashlib.file_digest(stream,"sha256").hexdigest()
    output_hash=fingerprint(output)
    if a.source.resolve()==(a.batch/"frozen/candidate").resolve():
        assert output_hash==fingerprint(original)
    changes=next(r for r in json.loads((output/"trips.json").read_bytes()) if r["vehicle_id"]==a.vehicle)["lane_events"]
    near=[r for r in log if any(-2.0<= r["time"]-e["time_s"]<=.2 for e in changes)]
    with (a.out/"ego.csv").open("w",newline="",encoding="utf8") as dest:
        w=csv.DictWriter(dest,list(log[0]));w.writeheader();w.writerows(near)
    print(output_hash, changes)


if __name__=="__main__":
    main()
