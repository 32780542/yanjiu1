"""Run a frozen scenario and record the actual gap, proposed target and command for every car."""
import argparse
import csv
import json
from pathlib import Path
import sys


def run(batch,case,out):
    p=batch/"frozen/candidate";sys.path.insert(0,str(p.resolve()))
    from experiments import native_sumo as sim
    from noa import native_rules as rules
    import noa.staggered as st
    road,n,spacing,seed=case.split("_")
    old=json.loads((batch/("candidate_"+case)/"row.json").read_bytes())
    input_data=json.loads((batch/old["run"]/"input.json").read_bytes())
    name=input_data["case"]["scenario"];sim.ROAD_LAYOUT[name]=(2800,1000,int(road[-1]))
    observe=sim.LocalTracks.observe;decide=rules.decide;choose=st.choose_target
    ctx={};rows=[]
    def capture(adapter,key,*args,**kw):
        ego,others=observe(adapter,key,*args,**kw)
        ctx["key"]=key;ctx["names"]={v:k for k,v in adapter.tracks[key].items()}
        return ego,others
    def selecting(*args,**kw):
        target=choose(*args,**kw)
        ctx["released"]=target.released
        return target
    def decision(ego,others,memory,*args,**kw):
        cmd,remember=decide(ego,others,memory,*args,**kw)
        if (ego.time in (85,90,95,98,100,105,110) and 2600<=ego.x<=3700):
            action=cmd.proposal_lane
            remaining=cmd.target_x-ego.x if cmd.target_x is not None else None
            blockers=[]
            if action is not None and action!=ego.lane:
                step=ego.lane+(action>ego.lane)-(action<ego.lane)
                for peer in others:
                    if rules._occupies(peer,step) and not rules._clear(ego,(peer,),step):
                        blockers.append(str(ctx["names"][peer.track])+":"+str(round(peer.x-ego.x,2)))
            rows.append(dict(time=ego.time,vehicle=ctx["key"],x=round(ego.x,3),lane=ego.lane,v=round(ego.speed,3),
                target=action,request=cmd.lane,step_certified=cmd.step_certified,step_gap=cmd.step_gap,
                released=ctx.get("released"),dx=round(remaining,3) if remaining is not None else None,
                blockers=" ".join(blockers)))
        return cmd,remember
    sim.LocalTracks.observe=capture;rules.decide=decision;st.choose_target=selecting
    tape=json.loads((batch/"tapes"/(case+".json")).read_bytes())
    folder=sim.run_case(mode="transform",scenario=name,seed=int(seed),flow=1750,duration=8.,gui=False,output_base=out,initial=tape)
    import gzip,hashlib
    def digest(f):
        with gzip.open(f/"positions.jsonl.gz","rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
    assert digest(folder)==digest(batch/old["run"])
    with (out/"decisions.csv").open("w",newline="",encoding="utf8") as stream:
        writer=csv.DictWriter(stream,list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(len(rows),"native decisions; unchanged physical trace")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("batch",type=Path);p.add_argument("case");p.add_argument("out",type=Path)
    a=p.parse_args();run(a.batch,a.case,a.out)
