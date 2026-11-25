"""Track each naturally formed group from upstream to downstream, reusing the strict physical cohort test."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import json
from pathlib import Path
import time

from boundary_cohorts import evaluate, strata_rows, write_csv

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LABELS=("noon_ref_1200","noon_onehop_1200","noon_combined_1200","noon_receive_1200")
CELLS=tuple(product(LABELS,("3to2","4to3"),(1500,1750,2000),(11261,11262)))


def extract(rowpath):
    row=json.loads(rowpath.read_bytes())
    assert row["status"]=="drained" and row["completed"]==row["requested"] and row["collisions"]==row["teleports"]==0
    return evaluate((rowpath.parent.parent.name, ROOT/row["run_dir"]))


def main():
    p=argparse.ArgumentParser();p.add_argument("--workers",type=int,default=3);p.add_argument("--watch",action="store_true")
    a=p.parse_args();remaining=set(CELLS);runs=[];groups=[]
    with ProcessPoolExecutor(a.workers) as pool:
        while remaining:
            ready={}
            for label,road,flow,seed in sorted(remaining):
                row=ROOT/"tmp/nov25study"/label/f"{road}_s{seed}_q{flow}"/"row.json"
                if row.is_file():ready[pool.submit(extract,row)]=(label,road,flow,seed)
            for fut in as_completed(ready):
                counts,members=fut.result();runs.extend(counts);groups.extend(members);remaining.remove(ready[fut])
            print("finished",len(CELLS)-len(remaining),"of",len(CELLS),"upstream groups",len(groups),flush=True)
            if remaining:
                if not a.watch:raise SystemExit("Incomplete inputs")
                time.sleep(30)
    runs.sort(key=lambda x:(x["model"],x["road"],x["flow"],x["seed"],x["period"]))
    groups.sort(key=lambda x:(x["model"],x["road"],x["flow"],x["seed"],x["up_t"]))
    write_csv(HERE/"noon_stream_runs.csv",runs)
    write_csv(HERE/"noon_stream_groups.csv",groups)
    write_csv(HERE/"noon_stream_strata.csv",strata_rows(runs))


if __name__=="__main__":
    main()
