"""Can the ego certify its entire connected component from a finite longitudinal view?"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("batch",type=Path)
    ap.add_argument("output",type=Path)
    ap.add_argument("--period",type=float,default=2.)
    ap.add_argument("--ranks",type=int,default=2)
    args=ap.parse_args()
    batch=args.batch.resolve()
    source=batch/"source"
    sys.path.insert(0,str(source))
    from noa import native_rules as rules, staggered
    manifest=json.loads((batch/"manifest.json").read_bytes())["files"]
    for mod in (rules,staggered):
        p=Path(mod.__file__).resolve()
        assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest[p.relative_to(source).as_posix()]
    with (batch/"summary.csv").open(encoding="utf8") as f:
        cases=[row for row in csv.DictReader(f) if row.get("cohort") in (None,"","stream","chain24")]
    stats=defaultdict(Counter)
    for row in cases:
        folder=ROOT/row["run_dir"]
        net=ET.parse(folder/"native.net.xml")
        cut=float(net.find("./edge[@id='upstream']/lane").get("length"))
        upstream,downstream=map(int,row["road"].split("to"))
        dt=json.loads((folder/"input.json").read_bytes())["positions_step_s"]
        stride=round(args.period/dt)
        with gzip.open(folder/"positions.jsonl.gz","rt",encoding="utf8") as f:
            for tick,line in enumerate(f):
                if tick%stride:
                    continue
                frame=json.loads(line)
                cars=sorted((rules.Vehicle(j,x,y,v,round(y/rules.LANE_WIDTH-.5))
                             for j,(x,y,v,_) in enumerate(frame["states"].values())),
                            key=lambda v:(-v.x,-v.lane))
                if not cars:
                    continue
                # A ground-truth oracle forms connected components on this frame only.
                parts=[]
                for c in cars:
                    if not parts or parts[-1][-1].x-c.x > rules.GROUP_GAP:
                        parts.append([])
                    parts[-1].append(c)
                pick={(tick//stride + i*len(cars)//args.ranks)%len(cars) for i in range(args.ranks)}
                selected={cars[j].track for j in pick}
                for group in parts:
                    if len(group)<2 or not any(c.track in selected for c in group):
                        continue
                    if group[0].x < cut-rules.ROAD_PREVIEW:
                        stage,lanes="formation",upstream
                    elif group[-1].x >= cut:
                        stage,lanes="downstream",downstream
                    else:
                        continue
                    if any(c.lane>=lanes or abs(c.y-(c.lane+.5)*rules.LANE_WIDTH)>.3 for c in group):
                        continue
                    for ego in group:
                        if ego.track not in selected:
                            continue
                        back,front=ego.x-rules.REAR_VIEW,ego.x+rules.FRONT_VIEW
                        local=[c for c in group if back<=c.x<=front]
                        if len(local)<2:
                            continue
                        head=front-local[0].x < rules.GROUP_GAP
                        tail=local[-1].x-back < rules.GROUP_GAP
                        cert=not (head or tail)
                        full=len(local)==len(group)
                        assert not cert or full
                        def choose(cars, h=False, t=False, bounds=None):
                            spacing=rules.desired_spacing(sum(c.speed for c in cars)/len(cars))
                            return staggered.choose_target(cars.index(ego),cars,lanes,spacing,
                                head_clipped=h,tail_clipped=t,sensor_bounds=bounds)
                        target=choose(local,head,tail,(back,front))
                        oracle=choose(group)
                        action=lambda lane: ego.lane+(lane>ego.lane)-(lane<ego.lane)
                        same=action(target.lane)==action(oracle.lane)
                        if cert:
                            assert same and target.lane==oracle.lane and abs(target.x-oracle.x)<1e-7
                        cell=(row["road"],row.get("cohort") or "flow",row["seed"],row["flow"],stage)
                        c=stats[cell]
                        c["views"]+=1
                        c["actually_complete"]+=full
                        c["certified_complete"]+=cert
                        c["same_action"]+=same
                        c["different_action"]+=not same
                        c["different_target_lane"]+=target.lane!=oracle.lane
                        c["different_action_full_but_edge_flag"]+=full and not same
                        c["locally_positive_gap_but_different"]+=(not same and target.step_gap>0)
                        c["uncertified_agree"]+=not cert and same
                        c["certified_different"]+=cert and not same
    columns=("views","actually_complete","certified_complete","same_action","different_action",
             "different_target_lane","different_action_full_but_edge_flag","locally_positive_gap_but_different",
             "uncertified_agree","certified_different")
    with args.output.open("x",encoding="utf8",newline="") as f:
        w=csv.writer(f)
        w.writerow(("road","cohort","seed","flow","stage",*columns))
        for cell,c in sorted(stats.items()):
            w.writerow((*cell,*(c[k] for k in columns)))
    total=sum(stats.values(),Counter())
    print({k:total[k] for k in columns})


if __name__=="__main__":
    main()
