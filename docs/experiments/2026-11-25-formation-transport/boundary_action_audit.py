"""Offline mask of either observed terminal band, recomputing each local vehicle's own template."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

from sample_gaps import ROOT, sample_run


def audit(batch, dest):
    source = (batch/"source").resolve()
    sys.path.insert(0,str(source))
    from noa import native_rules as rules, staggered
    hashes = json.loads((batch/"manifest.json").read_bytes())["files"]
    for module in (rules,staggered):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(source) and hashlib.sha256(path.read_bytes()).hexdigest() == hashes[path.relative_to(source).as_posix()]
    bins = defaultdict(Counter)
    original = staggered.choose_target

    def compare(rank, group, lanes, spacing, **options):
        ego = group[rank]
        target = original(rank,group,lanes,spacing,**options)
        step = lambda lane: ego.lane + (lane>ego.lane) - (lane<ego.lane)
        action = step(target.lane)
        key = (row["road"],row.get("cohort") or "flow",region(ego.x),
               "proposed move" if action != ego.lane else "stay",
               "structural" if math.isinf(target.step_gap) else "finite")
        counts = bins[key]
        counts["base_windows"] += 1
        branches = []
        for edge_name,x in (("front",group[0].x),("rear",group[-1].x)):
            if ego.x == x:
                continue
            view = [v for v in group if v.x != x]
            if len(view)<2:
                continue
            move = original(view.index(ego),view,lanes,rules.desired_spacing(sum(v.speed for v in view)/len(view)),
                head_clipped=view[0].x-ego.x > rules.FRONT_VIEW-rules.GROUP_GAP,
                tail_clipped=ego.x-view[-1].x > rules.REAR_VIEW-rules.GROUP_GAP,
                sensor_bounds=(ego.x-rules.REAR_VIEW,ego.x+rules.FRONT_VIEW))
            agrees = step(move.lane) == action
            branches.append((agrees,move.step_gap>0,move.step_certified))
            counts[edge_name+"_tested"] += 1
            counts[edge_name+"_changes"] += not agrees
        if branches:
            counts["eligible"] += 1
            counts["changes_somewhere"] += any(not a for a,_,_ in branches)
            counts["unique_all"] += target.step_gap>0 and all(a and unique for a,unique,_ in branches)
            counts["positive_box_all"] += target.step_certified and all(a and box for a,_,box in branches)
        return target

    staggered.choose_target = compare
    with (batch/"summary.csv").open(encoding="utf8") as f:
        records = [r for r in csv.DictReader(f) if r.get("cohort") in ("stream","chain24")]
    for row in records:
        folder=ROOT/row["run_dir"]
        from measure import road_layout
        boundary=road_layout(folder)[0][1]
        def region(x):
            return "formation" if x<boundary-rules.ROAD_PREVIEW else "preview" if x<boundary else "downstream"
        list(sample_run(folder,row,10,3,rules,staggered))
    fields = ("base_windows","eligible","front_tested","front_changes","rear_tested","rear_changes",
              "changes_somewhere","unique_all","positive_box_all")
    with dest.open("x",newline="",encoding="utf8") as f:
        w=csv.writer(f)
        w.writerow(("road","cohort","stage","action","nominal_gap",*fields))
        for key,c in sorted(bins.items()):
            w.writerow((*key,*(c[field] for field in fields)))
    total=sum(bins.values(),Counter())
    print({name:total[name] for name in fields})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    audit(args.batch.resolve(),args.output)
