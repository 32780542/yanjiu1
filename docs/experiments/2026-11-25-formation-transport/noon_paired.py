"""Pair two closed-loop controllers by initial states; preserve denominators and stage-specific availability."""
import argparse
import csv
from pathlib import Path
from statistics import median
from noon_cases import read

META = ("road","n","spacing","seed")
FIELDS = ("whole_both","upstream_whole_hold_s","downstream_whole_hold_s","formation_excess_total","formation_excess_max",
          "transform_excess_total","transform_excess_max","formation_actual_total","transform_actual_total",
          "formation_actual_max","transform_actual_max","completed","collisions","teleports")


def dual(row,stage):
    return row[stage+"_excess_total"]==row[stage+"_excess_max"]==0


def evaluate(base,new):
    rows = []
    for key,b in sorted(new.items()):
        a=base[key]
        assert all(a[k]==b[k] for k in ("first_frame_sha256","tape_sha256","n","completed","first_frame_s"))
        assert a["completed"]==a["n"] and b["status"]==a["status"]=="drained"
        row={k:b[k] for k in META}
        row["first_frame_sha256"]=b["first_frame_sha256"]
        for label,r in (("base",a),("new",b)):
            row.update({label+"_"+k:r[k] for k in FIELDS})
            row.update({label+"_"+stage+"_dual":dual(r,stage) for stage in ("formation","transform")})
        rows.append(row)
    for road in ("all",*sorted({r["road"] for r in rows})):
        group=[r for r in rows if road=="all" or r["road"]==road]
        print(road,len(group))
        for name in ("whole_both","formation_dual","transform_dual"):
            aa=[r["base_"+name] for r in group];bb=[r["new_"+name] for r in group]
            print(name, sum(aa),sum(bb),"gained",sum(y and not x for x,y in zip(aa,bb)),
                  "lost",sum(x and not y for x,y in zip(aa,bb)))
        joint=[r for r in group if r["base_whole_both"] and r["new_whole_both"]]
        if joint:
            for key in ("formation_actual_total","transform_actual_total","upstream_whole_hold_s","downstream_whole_hold_s"):
                print("same-success",key,len(joint),round(sum(r["new_"+key]-r["base_"+key] for r in joint),2),
                      "median delta",median(r["new_"+key]-r["base_"+key] for r in joint))
    return rows


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--base",nargs="+",type=Path,required=True)
    p.add_argument("--new",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();b=read(a.base);n=read([a.new]);assert len(n)==len(list((a.new/"tapes").glob("*.json")))>0
    rows=evaluate(b,n)
    with a.out.open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
