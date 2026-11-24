"""Paired fixed cohorts on four roads. Each worker imports just its frozen controller."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import random_cohorts as cohorts
from run_study import ROADS, hash_file

HERE = Path(__file__).resolve().parent
SIZES = (7, 11, 13, 17)
cohorts.SPANS.update({n: {"compact":10.*n+25, "long":20.*n+160} for n in SIZES})
for n in (12,24):
    # Keep 20 m of same-lane separation possible even on a two-lane entry.
    cohorts.SPANS[n]["compact"] = 10.*n + 5
cohorts.ROADS.update({road: demo for road,(_,demo) in ROADS.items()})


def case(out, cell):
    model, road, *rest = cell
    source = out / "frozen" / model
    sys.path.insert(0, str(source))
    from experiments import native_sumo
    scenario = cohorts.ROADS[road]
    incoming, downstream, lanes = native_sumo.ROAD_LAYOUT[scenario]
    assert incoming == 1600 and downstream == 1000
    native_sumo.ROAD_LAYOUT[scenario] = (2800, downstream, lanes)
    cohorts.run_one(out, cell)
    folder = out / "_".join(cell)
    row = json.loads((folder/"row.json").read_bytes())
    report = json.loads((folder/"measure.json").read_bytes())
    initial = json.loads((out/"tapes"/("_".join(cell[1:])+".json")).read_bytes())
    assert row["first_frame_n"] == len(initial) and row["initial_matches_request"]
    for stage in ("formation","transform"):
        moves=report[stage+"_moves"]
        row[stage+"_end_counts"] = "/".join(map(str,moves["end_counts"])) if moves else None
        row[stage+"_best_legal_total"] = moves["three_lane_outer_first"]["min_total_given_min_max"] if moves else None
        row[stage+"_best_legal_max"] = moves["three_lane_outer_first"]["min_max_crossings"] if moves else None
    cohorts.write(folder/"row.json",row)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--baseline", type=Path, help="Optional paired reference, on roads it supports")
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--roads", nargs="+", choices=tuple(ROADS), default=tuple(ROADS))
    ap.add_argument("--seeds",nargs="+",default=list(map(str,range(9901,9905))))
    ap.add_argument("--sizes",type=int,nargs="+",choices=sorted(cohorts.SPANS),default=SIZES)
    ap.add_argument("--workers",type=int,default=4)
    ap.add_argument("--case",nargs=5)
    args=ap.parse_args()
    out=args.out.resolve()
    if args.case:
        return case(out,args.case)
    out.mkdir(parents=True,exist_ok=False)
    (out/"tapes").mkdir()
    models={"baseline":args.baseline} if args.baseline is not None else {}
    models["candidate"]=args.candidate
    for name,src in models.items():
        cohorts.freeze(src.resolve(),out/"frozen"/name)
    # Use the same original geometric test for both methods, with a strict
    # two-lane tail: between any two consecutive cars the lane must alternate.
    measure=(HERE/"measure.py").read_text(encoding="utf8")
    marker="    columns = [[] for _ in range(lanes)]"
    start=measure.index(marker,measure.index("def whole_shape("))
    strict="""    if lanes == 2:
        order = sorted(states.values(),key=lambda state:-state[0])
        if any(lane_of(a[1]) == lane_of(b[1]) for a,b in zip(order,order[1:])):
            return False
"""
    (out/"frozen/measure.py").write_text(measure[:start]+strict+measure[start:],encoding="utf8")
    cells=list(product(args.roads, map(str,args.sizes), ("compact","long"), args.seeds))
    for road,n,profile,seed in cells:
        cohorts.write(out/"tapes"/("_".join((road,n,profile,seed))+".json"),
                      cohorts.make_tape(int(seed),road,int(n),profile))
    fingerprint={name:{path.relative_to(out/"frozen"/name).as_posix():hash_file(path)
                       for path in (out/"frozen"/name).rglob("*.py")} for name in models}
    cohorts.write(out/"manifest.json",dict(sources=fingerprint,evaluator=hash_file(out/"frozen/measure.py")))
    def run(params):
        with (out/("_".join(params)+".log")).open("x") as log:
            subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),str(out),"--case",*params],
                           check=True,stdout=log,stderr=subprocess.STDOUT)
        return json.loads((out/"_".join(params)/"row.json").read_bytes())
    all_cases=[(method,*cell) for cell in cells for method in models]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows=list(pool.map(run,all_cases))
    if args.baseline is not None:
        for a,b in zip(rows[::2],rows[1::2]):
            assert a["first_frame_sha256"]==b["first_frame_sha256"] and a["tape_sha256"]==b["tape_sha256"]
    with (out/"summary.csv").open("x",newline="",encoding="utf8") as dest:
        writer=csv.DictWriter(dest,list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(cells)} initial states, {len(rows)} SUMO runs")


if __name__=="__main__":
    main()
