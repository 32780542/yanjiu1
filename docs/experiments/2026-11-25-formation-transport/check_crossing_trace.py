"""Compare the native lane-index ledger with lane boundaries read from Cartesian y."""
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import argparse
import gzip
import json
from math import floor
import os
import time

from validate_traffic import BATCH, ROOT, read, write_csv


CASES = (
    ("anchor_group_1200","3to2_s9301_q2000"),
    ("anchor_group_1200","4to3_s9301_q1500"),
    ("subflow_expand_1200","2to3_s9301_q2000"),
    ("retained_34_1200","3to4_s9301_q1500"),
)


def check(label, case, *, individual=False):
    index=read(BATCH/label/case/"row.json")
    folder=ROOT/index["run_dir"]
    cache=ROOT/"tmp/nov25_crossing_trace_audit/strict_center"/label/(case+".json")
    fingerprint = ["strict_center_v1",index["result_sha256"]]
    for name in ("positions.jsonl.gz","trips.json"):
        st=(folder/name).stat()
        fingerprint.extend([st.st_size,st.st_mtime_ns])
    if cache.is_file():
        item=read(cache)
        if (item.get("fingerprint")==fingerprint and "coordinate_downstream_crossings" in item["row"]
                and (not individual or "coordinate_approach_down_two_or_more" in item["row"])):
            return item["row"]
    trips=read(folder/"trips.json")
    original={r["vehicle_id"]:[(e["from_lane"],e["to_lane"],e["time_s"],e["x"]) for e in r["lane_events"]]
              for r in trips}
    exits={r["vehicle_id"]:r["exited_s"] for r in trips}
    prev={}
    last={}
    observed=defaultdict(list)
    with gzip.open(folder/"positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame=json.loads(line)
            for key,state in frame["states"].items():
                nearest=round(state[1]/3.3)*3.3
                lane=prev.get(key,floor(state[1]/3.3)) if abs(state[1]-nearest)<=1e-6 else floor(state[1]/3.3)
                if key in prev and prev[key]!=lane:
                    observed[key].append((prev[key],lane,frame["time_s"],state[0]))
                prev[key]=lane
                last[key]=(frame["time_s"],state[1])
    def count(ledger):
        return sum(abs(e[1]-e[0]) for events in ledger.values() for e in events)
    if set(prev)!=set(original):
        raise ValueError("Vehicle IDs differ")
    unmatched=nonzero=zero=boundary_bin_changes=ending_on_line=0
    max_shift=0.
    for key,stored in original.items():
        coords=observed[key]
        if [e[:2] for e in coords] != [e[:2] for e in stored]:
            unmatched+=1
            if (stored and [e[:2] for e in coords]==[e[:2] for e in stored[:-1]]
                    and abs(last[key][1]-3.3*max(stored[-1][:2]))<=1e-6 and exits[key] is not None
                    and abs(last[key][0]-exits[key])<=.100001
                    and abs(last[key][0]-stored[-1][2])<=.100001):
                ending_on_line+=1
            continue
        for a,b in zip(coords,stored):
            dt=abs(a[2]-b[2])
            max_shift=max(dt,max_shift)
            if dt<1e-6: zero+=1
            else: nonzero+=1
            boundary_bin_changes+=((a[3]>=800)+(a[3]>=1000))!=((b[3]>=800)+(b[3]>=1000))
    out = dict(batch=label,case=case,vehicles=len(prev),native_crossings=count(original),
                coordinate_crossings=count(observed),different_per_vehicle_lane_sequences=unmatched,
                matched_events_same_time=zero,matched_events_time_differs=nonzero,
                matched_max_abs_time_difference_s=round(max_shift,4),
                matched_events_different_spatial_bin=boundary_bin_changes,run_dir=index["run_dir"])
    counts=[sum(abs(e[1]-e[0]) for e in events) for events in observed.values()]
    out["coordinate_vehicles_crossed_twice_or_more"]=sum(n>=2 for n in counts)
    out["coordinate_vehicle_crossing_max"]=max(counts,default=0)
    out["terminal_center_on_line_vehicles"]=ending_on_line
    near=[sum(abs(e[1]-e[0]) for e in events if e[3]>=800) for events in observed.values()]
    out["coordinate_approach_down_two_or_more"]=sum(n>=2 for n in near)
    out["coordinate_approach_down_vehicle_max"]=max(near,default=0)
    for name,low,high in (("upstream",0,800),("approach",800,1000),("downstream",1000,float("inf"))):
        out["coordinate_"+name+"_crossings"] = sum(abs(e[1]-e[0]) for events in observed.values()
                                                   for e in events if low<=e[3]<high)
    cache.parent.mkdir(parents=True,exist_ok=True)
    tmp=cache.with_suffix(f".{os.getpid()}.writing")
    tmp.write_text(json.dumps(dict(fingerprint=fingerprint,row=out)),encoding="utf-8")
    tmp.replace(cache)
    return out


def job(pair):
    return check(*pair)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch-public",action="store_true")
    parser.add_argument("--workers",type=int,default=2)
    args=parser.parse_args()
    if not args.watch_public:
        rows=[check(*case) for case in CASES]
        write_csv("crossing_trace_check.csv",rows)
        for row in rows:
            print(row["case"],row["native_crossings"],row["coordinate_crossings"],
                  row["different_per_vehicle_lane_sequences"],row["matched_max_abs_time_difference_s"])
    else:
        from public_traffic import PANELS, get_design
        labels={label for _,batches,_ in PANELS.values() for label in batches}
        while missing:=sorted(label for label in labels if not (BATCH/label/"manifest.json").is_file()):
            print("Waiting for frozen manifest:",*missing,flush=True)
            time.sleep(20)
        expected=get_design(PANELS)
        done=set()
        with ProcessPoolExecutor(args.workers) as pool:
            while len(done)<len(expected):
                keys=[k for k,v in expected.items() if k not in done and v[4].is_file()]
                jobs=[(expected[k][4].parent.parent.name,f"{k[1]}_s{k[3]}_q{k[2]}") for k in keys]
                for k,row in zip(keys,pool.map(job,jobs)):
                    done.add(k)
                print("Coordinate ledgers",len(done),"/",len(expected),flush=True)
                if len(done)<len(expected): time.sleep(20)
