"""Measure ego action radii on a reproducible stratified sample of centered SUMO frames."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from math import isfinite
from pathlib import Path
import random
import sys
import xml.etree.ElementTree as ET

from sample_gaps import ROOT, sample_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--per-cell",type=int,default=4)
    parser.add_argument("--seconds",type=float,default=3.)
    args = parser.parse_args()
    source = (args.batch / "source").resolve()
    sys.path.insert(0,str(source))
    from noa import native_rules, staggered, transport
    from action_radius import action_graph, action_radius, witness_competitor
    hashes = json.loads((args.batch / "manifest.json").read_bytes())["files"]
    for module in (native_rules,staggered,transport):
        path=Path(module.__file__).resolve()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[path.relative_to(source).as_posix()]
    rng = random.Random(25110323)
    counts = Counter()
    retained = defaultdict(list)
    original_choose, original_solve = staggered.choose_target, staggered.solve_transport
    def choose(rank, group, *others, **kwargs):
        nonlocal moment, stage
        ego = group[rank]
        moment = ego.time
        stage = ("formation" if ego.x < boundary-native_rules.ROAD_PREVIEW else
                 "preview" if ego.x < boundary else "downstream")
        return original_choose(rank, group, *others, **kwargs)
    def solve(vehicles,slots,**kwargs):
        fit=original_solve(vehicles,slots,**kwargs)
        ego=kwargs["ego_index"]
        decision = "stay" if fit.action_lane==vehicles[ego][0] else "move"
        kind="finite" if isfinite(fit.action_gap) else "structural"
        cell = (case["road"],case["cohort"],stage,decision,kind)
        counts[cell]+=1
        if kind == "finite":
            sample=(case["result_sha256"], moment, ego, vehicles, slots)
            kept=retained[cell]
            if len(kept)<args.per_cell:
                kept.append(sample)
            else:
                j=rng.randrange(counts[cell])
                if j<args.per_cell:
                    kept[j]=sample
        return fit
    staggered.choose_target,staggered.solve_transport=choose,solve
    with (args.batch/"summary.csv").open(encoding="utf8") as file:
        rows = [r for r in csv.DictReader(file) if r["cohort"] in ("stream","chain24")]
    for case in sorted(rows,key=lambda r:(r["road"],r["cohort"])):
        folder = ROOT / case["run_dir"]
        net=ET.parse(folder/"native.net.xml")
        boundary=float(net.find("./edge[@id='upstream']/lane").get("length"))
        moment=stage=None
        list(sample_run(folder,case,10,3,native_rules,staggered))
    staggered.choose_target,staggered.solve_transport=original_choose,original_solve
    fields=("road","cohort","stage","decision","alternatives","population","result_sha256",
            "t_s","ego_rank","n_visible","nominal_gap_m2","general_radius_m","witness_radius_m",
            "exact_radius_lower_m","exact_radius_upper_m","converged")
    with args.output.open("x",encoding="utf8",newline="") as output:
        writer=csv.writer(output)
        writer.writerow(fields)
        for cell, count in sorted(counts.items()):
            if cell[-1]=="structural":
                writer.writerow([*cell,count]+[""]*(len(fields)-6))
            else:
                for sha,t,ego,vehicles,slots in retained[cell]:
                    graph=action_graph(vehicles,slots,ego)
                    x,y,p,same,other,gap=graph
                    w,_=witness_competitor(x,y,p,other)
                    exact=action_radius(*graph,seconds=args.seconds)
                    general=gap/(2*len(x)*(max(y)-min(y))) if max(y)>min(y) else 0.
                    writer.writerow([*cell,count,sha,t,ego,len(x),gap,general,w,
                                     exact.lower_m,exact.upper_m,exact.converged])
                    output.flush()
    print(f"{sum(counts.values())} sampled observer windows, {sum(map(len,retained.values()))} finite competitors analysed")


if __name__=="__main__":
    main()
