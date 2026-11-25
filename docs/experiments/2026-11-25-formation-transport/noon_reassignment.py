"""Read alternate local assignments on unchanged native trajectories at three bottleneck instants."""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def audit(base, variant, out):
    key="4to3_24_long_10153"
    stored=base/("candidate_"+key)
    oldrun=base/json.loads((stored/"row.json").read_bytes())["run"]
    tape=json.loads((base/"tapes"/(key+".json")).read_bytes())
    sys.path.insert(0,str((base/"frozen/candidate").resolve()))
    from experiments import native_sumo as sim
    from noa import staggered as st
    spec=importlib.util.spec_from_file_location("noon_alternate_transport", variant/"noa/transport.py")
    other=importlib.util.module_from_spec(spec);sys.modules[spec.name]=other;spec.loader.exec_module(other)
    sim.ROAD_LAYOUT["four_to_three_demo"]=(2800,1000,3)
    observe,choose,solve=sim.LocalTracks.observe,st.choose_target,st.solve_transport
    ctx={};past={};records=[]
    times={81.5,81.7,82.1}
    def watched(self,k,*args,**kwargs):
        result=observe(self,k,*args,**kwargs)
        ctx["key"]=k;ctx["names"]={t:key for key,t in self.tracks[k].items()};ctx["names"][0]=k
        return result
    def capture(rank,group,lanes,spacing,**kwargs):
        ego=group[rank];k=ctx["key"]
        memo=past.get(k,{})
        seen={}
        for c in group:
            lane,cross=memo.get(c.track,(c.lane,float("-inf")))
            seen[c.track]=(c.lane,c.x if c.lane!=lane else cross)
        past[k]=seen
        ctx.update(group=group,ego=ego,used=[seen[c.track][1]>=2600 for c in group],rank=rank,lanes=lanes)
        return choose(rank,group,lanes,spacing,**kwargs)
    def compare(vehicles,slots,**kwargs):
        original=solve(vehicles,slots,**kwargs)
        ego=ctx["ego"]
        if round(ego.time,1) in times and ego.x>=2600 and ctx["lanes"]==3:
            alt=other.solve_transport(vehicles,slots,history=ctx["used"],**kwargs)
            def senders(assignment):
                return " ".join(sorted(ctx["names"][car.track] for car,j in zip(ctx["group"],assignment)
                                       if car.lane==1 and slots[j][0]==0))
            row=dict(time=ego.time,observer=ctx["key"],x=round(ego.x,3),current=ego.lane,seen=len(vehicles),
                     used=" ".join(sorted(ctx["names"][car.track] for car,h in zip(ctx["group"],ctx["used"]) if h)),
                     baseline_action=original.action_lane,conditioned_action=alt.action_lane,
                     baseline_senders=senders(original.assignment),conditioned_senders=senders(alt.assignment),
                     baseline_margin=original.action_gap,conditioned_margin=alt.action_gap,
                     C=original.total_crossings,B=original.max_crossings)
            assert (row["B"],row["C"])==(alt.max_crossings,alt.total_crossings)
            records.append(row)
        return original
    sim.LocalTracks.observe=watched;st.choose_target=capture;st.solve_transport=compare
    result=sim.run_case(mode="transform",scenario="four_to_three_demo",seed=10153,flow=1750,duration=8,
                        gui=False,output_base=out,initial=tape)
    def digest(folder):
        with gzip.open(folder/"positions.jsonl.gz","rb") as s:return hashlib.file_digest(s,"sha256").hexdigest()
    assert digest(result)==digest(oldrun)
    with (out/"counterfactual.csv").open("w",newline="",encoding="utf8") as s:
        w=csv.DictWriter(s,list(records[0]));w.writeheader();w.writerows(records)
    print(len(records),"local witnesses;",digest(result))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("base",type=Path);p.add_argument("variant",type=Path)
    p.add_argument("out",type=Path);a=p.parse_args();audit(a.base,a.variant,a.out)
