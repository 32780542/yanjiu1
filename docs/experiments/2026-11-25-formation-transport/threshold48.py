"""Test downstream lengths straddling the first whole-shape position in the 2400 m trial."""
import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
from noon_gui import strict_shape
from noon_summary import HERE, write
import measure

measure.whole_shape=strict_shape


def trial(args):
    road,length,predicted,out=args
    folder=out/f"{road}_{length}"
    subprocess.run([sys.executable,"-B",str(HERE/"long48_extension.py"),"--worker",road,str(folder),str(length)],
                   check=True)
    [run]=folder.iterdir()
    stat=measure.measure(run,True)
    assert stat["safe"] and stat["completed"]==48
    held=stat["downstream"]["whole_hold_s"]
    return dict(road=road,downstream_m=length,head_position_from_boundary_m=predicted,
                predicted_whole=length>predicted,observed_whole=held>0,downstream_hold_s=held,
                first_whole_s=stat["downstream"]["first_whole_s"],peak=stat["downstream"]["peak_size"],
                completed=stat["completed"],collisions=stat["collisions"],teleports=stat["teleports"])


if __name__=="__main__":
    out=Path(sys.argv[1]).resolve()
    out.mkdir(parents=True,exist_ok=False)
    with (HERE/"noon_long48_extension.csv").open() as f:
        head={r["road"]:float(r["first_whole_head_m"])-2800 for r in csv.DictReader(f)}
    jobs=[(road,length,head[road],out) for road,length in (("3to2",1400),("3to2",1500),("2to3",1500),("2to3",1600))]
    with ThreadPoolExecutor(4) as pool:
        rows=list(pool.map(trial,jobs))
    write("noon_long48_threshold.csv",rows)
    print(rows)
