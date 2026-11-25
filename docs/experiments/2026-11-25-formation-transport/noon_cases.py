"""Compare the same real initial vehicles and stages across the noon control experiments."""
import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(paths):
    table = {}
    for batch in paths:
        for path in sorted(batch.glob("candidate_*/row.json")):
            row = json.loads(path.read_bytes())
            k = tuple(row[col] for col in ("road","n","spacing","seed"))
            if k in table:
                assert table[k]["first_frame_sha256"] == row["first_frame_sha256"]
            table[k] = row
    return table


def summarize(cases):
    formed = [r for r in cases if r["whole_both"]]
    dual = lambda r,s: all(r[s+"_excess_"+k] == 0 for k in ("total","max"))
    return dict(cases=len(cases), completed=sum(r["completed"] for r in cases),
                both=len(formed), hold10=sum(min(r[k+"_whole_hold_s"] for k in ("upstream","downstream"))>=10 for r in formed),
                up_dual=sum(dual(r,"formation") for r in formed), down_dual=sum(dual(r,"transform") for r in formed),
                up_excess=sum(r["formation_excess_total"] for r in formed),
                down_excess=sum(r["transform_excess_total"] for r in formed),
                down_multiple=sum(r["transform_actual_max"]>1 for r in formed),
                collisions=sum(r["collisions"] for r in cases), teleports=sum(r["teleports"] for r in cases))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",nargs="+",type=Path,required=True)
    p.add_argument("--variant",nargs="+",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    ref=read(args.base)
    rows=[]
    for path in args.variant:
        table=read([path])
        expected=sum(1 for (path0) in (path/"tapes").glob("*.json"))
        assert len(table)==expected>0
        base=[ref[k] for k in table]
        for k,row in table.items():
            old=ref[k]
            assert row["first_frame_sha256"]==old["first_frame_sha256"] and row["tape_sha256"]==old["tape_sha256"]
            assert row["completed"]==old["completed"]==row["n"] and row["status"]==old["status"]=="drained"
        for road in ["all",*sorted({r["road"] for r in base})]:
            for label,group in [("base",base),(path.name,table.values())]:
                subset=[r for r in group if road=="all" or r["road"]==road]
                record=dict(batch=path.name,method=label,road=road,**summarize(subset))
                rows.append(record)
                if road=="all":print(record)
        for k,r in table.items():
            if r["whole_both"]!=ref[k]["whole_both"]:
                print(k, "formed:",ref[k]["whole_both"],"->",r["whole_both"])
    with args.out.open("w",newline="",encoding="utf8") as dest:
        w=csv.DictWriter(dest,list(rows[0]));w.writeheader();w.writerows(rows)


if __name__=="__main__":
    main()
