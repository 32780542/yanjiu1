"""Test fixed groups whose initial span already exceeds a complete sensor window."""
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import json
from pathlib import Path
import subprocess
import sys

from noon_gui import strict_shape
import measure
from random_cohorts import SPANS, make_tape

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SPANS[48]={"compact":485.}
measure.whole_shape=strict_shape


def case(args):
    out,road=args
    tape=make_tape(11811,road,48,"compact")
    folder=out/road
    folder.mkdir()
    initial=folder/"initial.json"
    initial.write_text(json.dumps(tape,indent=2),encoding="utf8")
    subprocess.run([sys.executable,"-B",str(ROOT/"runrun.py"),"--headless","--layout",road,"--initial-demo",
                    str(initial),"--output-base",str(folder/"live")],cwd=ROOT,check=True)
    [run]=(folder/"live").iterdir()
    stat=measure.measure(run,True)
    with gzip.open(run/"positions.jsonl.gz","rt") as stream:
        first=next(f["states"] for f in map(json.loads,stream) if f["states"])
    assert len(first)==len(tape)==48
    for i,car in enumerate(tape):
        x,y,v,*_=first[f"initial_{i}"]
        assert abs(x-car["x"])<1e-6 and abs(v-car["speed"])<1e-6 and measure.lane_of(y)==car["lane"]
    assert stat["completed"]==48 and stat["safe"] and stat["status"]=="drained"
    return dict(road=road,seed=11811,completed=48,collisions=stat["collisions"],teleports=stat["teleports"],
                initial_span_m=max(s[0] for s in first.values())-min(s[0] for s in first.values()),
                upstream_hold_s=stat["upstream"]["whole_hold_s"],downstream_hold_s=stat["downstream"]["whole_hold_s"],
                upstream_peak=stat["upstream"]["peak_size"],downstream_peak=stat["downstream"]["peak_size"],
                same_members_peak=stat["paired_peak"]["size"],run_dir=str(run.relative_to(ROOT)))


if __name__=="__main__":
    out=Path(sys.argv[1]).resolve()
    out.mkdir(parents=True,exist_ok=False)
    with ThreadPoolExecutor(4) as pool:
        rows=list(pool.map(case,[(out,road) for road in ("3to2","4to3","2to3","3to4")]))
    with (HERE/"noon_long48.csv").open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
    print(rows)
