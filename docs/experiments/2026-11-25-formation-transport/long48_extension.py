"""Change only the downstream length to distinguish censored formation from a persistent defect."""
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import json
from pathlib import Path
import subprocess
import sys
from noon_gui import strict_shape
import measure

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
measure.whole_shape=strict_shape


def run_child(road, out, length=2400):
    sys.path.insert(0,str(ROOT))
    sys.path.insert(0,str(ROOT/"variants/phase5g_pure_formation"))
    import runrun
    scenario=runrun.LAYOUTS[road][0]+"_long"
    upstream,downstream,lanes=runrun.native.ROAD_LAYOUT[scenario]
    assert (upstream,downstream)==(2800,1000)
    runrun.native.ROAD_LAYOUT[scenario]=(upstream,length,lanes)
    tape=ROOT/"tmp/nov25-noon-long48"/road/"initial.json"
    return runrun.main(["--headless","--layout",road,"--initial-demo",str(tape),"--output-base",str(out)])


def case(args):
    road,out=args
    subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"--worker",road,str(out/road)],check=True)
    return summarize((road,out))


def summarize(args):
    road,out=args
    [old]=(ROOT/"tmp/nov25-noon-long48"/road/"live").iterdir()
    [new]=(out/road).iterdir()
    data=measure.measure(new,True)
    assert data["safe"] and data["completed"]==48
    trips=json.loads((old/"trips.json").read_bytes())
    first_exit=min(t["exited_s"] for t in trips)
    identical=total=0
    first_difference=None
    max_delta=[0.,0.,0.]
    membership_changes=lane_disagreements=0
    with gzip.open(old/"positions.jsonl.gz","rt") as a, gzip.open(new/"positions.jsonl.gz","rt") as b:
        for left,right in zip(map(json.loads,a),map(json.loads,b)):
            if left["time_s"]>=first_exit:
                break
            assert left["time_s"]==right["time_s"]
            equal=left["states"]==right["states"]
            identical+=equal
            total+=1
            old_states,new_states=left["states"],right["states"]
            membership_changes+=old_states.keys()!=new_states.keys()
            for key in old_states.keys() & new_states.keys():
                astate,bstate=old_states[key],new_states[key]
                for i in range(3):
                    max_delta[i]=max(max_delta[i],abs(astate[i]-bstate[i]))
                lane_disagreements+=measure.lane_of(astate[1])!=measure.lane_of(bstate[1])
            if not equal and first_difference is None:
                first_difference=left["time_s"]
    first_whole=data["downstream"]["first_whole_s"]
    with gzip.open(new/"positions.jsonl.gz","rt") as stream:
        shape=next(f for f in map(json.loads,stream) if f["time_s"]==first_whole)
    return dict(road=road,downstream_m=2400,completed=data["completed"],collisions=data["collisions"],
                teleports=data["teleports"],upstream_s=data["upstream"]["whole_hold_s"],
                downstream_s=data["downstream"]["whole_hold_s"],downstream_peak=data["downstream"]["peak_size"],
                same_members_peak=data["paired_peak"]["size"],frames_before_original_first_exit=total,
                identical_frames=identical,first_difference_s=first_difference,first_exit_short_s=first_exit,
                first_whole_long_s=first_whole,first_whole_head_m=max(s[0] for s in shape["states"].values()),
                membership_disagreement_frames=membership_changes,lane_disagreement_samples=lane_disagreements,
                max_dx_m=max_delta[0],max_dy_m=max_delta[1],max_dv_mps=max_delta[2],run_dir=str(new.relative_to(ROOT)))


if __name__=="__main__":
    if sys.argv[1]=="--worker":
        sys.exit(run_child(sys.argv[2],Path(sys.argv[3]),int(sys.argv[4]) if len(sys.argv)>4 else 2400))
    reading=sys.argv[1]=="--read"
    output=Path(sys.argv[-1]).resolve()
    if not reading:
        output.mkdir(parents=True,exist_ok=False)
    with ThreadPoolExecutor(4) as pool:
        rows=list(pool.map(summarize if reading else case,[(road,output) for road in ("3to2","4to3","2to3","3to4")]))
    with (HERE/"noon_long48_extension.csv").open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
    print(rows)
