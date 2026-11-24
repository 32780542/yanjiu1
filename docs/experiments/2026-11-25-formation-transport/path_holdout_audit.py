"""Independent physical shape, lane movement and sampled clearance audit for the 9800 holdout."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


def lane(car):
    return round(car[1]/3.3-.5)


def physical_shape(states,lanes):
    n=len(states);ordered=sorted(states.values(),key=lambda c:-c[0])
    if not all(0<=lane(c)<lanes and abs(c[1]-(lane(c)+.5)*3.3)<=.3 for c in ordered):
        return False
    if max(c[2] for c in ordered)-min(c[2] for c in ordered)>.5:
        return False
    step=5.5+.85*sum(c[2] for c in states.values())/n
    if lanes==2:
        if any(lane(c)!=(lane(ordered[0])^(k%2)) for k,c in enumerate(ordered)):
            return False
        origin=[c[0]+k*step/2 for k,c in enumerate(ordered)]
    else:
        count=Counter()
        origin=[]
        for c in ordered:
            j=lane(c)
            origin.append(c[0]+(count[j]+.5*(j%2))*step)
            count[j]+=1
        if any(count[k]!=n//lanes for k in range(lanes)):
            return False
    return max(origin)-min(origin)<=2.


def snapshot(t,states):
    return {k:(t,lane(c)) for k,c in states.items()}


def ledger(start,end,trips,event_field):
    if start is None or end is None:
        return None
    first=sorted(j for _,j in start.values())
    last=sorted(j for _,j in end.values())
    # Total is obtained independently from the integer boundary flows.
    lower_total=sum(abs(sum(j<=k for j in first)-sum(j<=k for j in last))
                    for k in range(min(first+last),max(first+last)))
    lower_worst=max(abs(a-b) for a,b in zip(first,last))
    hops=[];bad=0
    for k,(t,l) in start.items():
        until,wanted=end[k]
        cost=0
        for e in trips[k][event_field]:
            if t<e["time_s"]<=until:
                bad+=int(l!=e["from_lane"] or abs(e["to_lane"]-l)!=1)
                l=e["to_lane"];cost+=abs(e["to_lane"]-e["from_lane"])
        bad+=int(l!=wanted)
        hops.append(cost)
    return lower_total,lower_worst,sum(hops),max(hops),bad


def audit(cell):
    index=json.loads((cell/"index.json").read_bytes())
    report=json.loads((cell/"measure.json").read_bytes())
    road=index["road"];n=index["n"]
    case=cell/index["run"]
    trips={r["vehicle_id"]:r for r in json.loads((case/"trips.json").read_bytes())}
    pending={k:[(e["requested_s"],e["time_s"]) for e in r["lane_completion_events"]] for k,r in trips.items()}
    first=last=None
    points=dict.fromkeys(("up_first","up_last","down_first","down_last","up_first_set","up_last_set","down_first_set","down_last_set"))
    onsets={"up":None,"down":None};duration={"up":0.,"down":0.}
    clearance=float("inf");vmin=float("inf");amin=float("inf");vmax=0.
    last={}
    with gzip.open(case/"positions.jsonl.gz","rt") as f:
        for line in f:
            row=json.loads(line);t=row["time_s"];states=row["states"]
            if first is None:
                assert set(states)==set(trips);first=snapshot(t,states)
            last.update(snapshot(t,states))
            cars=sorted(states.values(),key=lambda c:c[0])
            for i,c in enumerate(cars):
                vmin=min(vmin,c[2]);vmax=max(vmax,c[2]);amin=min(amin,c[3])
                for j in range(i+1,len(cars)):
                    other=cars[j];distance=other[0]-c[0]-4.
                    if distance>=clearance:
                        break
                    if abs(c[1]-other[1])<1.8:
                        clearance=distance
            for side,lanes,lo,hi in (("up",int(road[0]),0,2600),("down",int(road[-1]),2800,3800)):
                qualifies=len(cars)==n and lo<=cars[0][0] and cars[-1][0]<hi and physical_shape(states,lanes)
                if not qualifies:
                    onsets[side]=None
                    continue
                if onsets[side] is None:
                    onsets[side]=t
                duration[side]=max(duration[side],t-onsets[side])
                snap=snapshot(t,states)
                if points[side+"_first"] is None:
                    points[side+"_first"]=snap
                points[side+"_last"]=snap
                if all(abs(c[1]-(lane(c)+.5)*3.3)<=.05 and not any(a<=t<b for a,b in pending[k])
                       for k,c in states.items()):
                    if points[side+"_first_set"] is None:
                        points[side+"_first_set"]=snap
                    points[side+"_last_set"]=snap
    r={k:index[k] for k in ("model","road","n","profile","seed","tape_sha","frame_sha","route_sha")}
    r.update(completed=report["completed"],collision=report["collisions"],teleport=report["teleports"],
             status=report["status"],same_ids_peak=report["paired_peak"]["size"],
             total_crossings=report["lane_changes"],total_completions=report["lane_change_completions"],
             mean_travel_s=round(report["mean_travel_time_s"],4),mean_fuel_g_km=round(report["fuel_g_per_km"],4),
             min_clearance_m=round(clearance,4),min_speed_m_s=round(vmin,3),max_speed_m_s=round(vmax,3),
             min_accel_m_s2=round(amin,3))
    assert not report["missing_from_trajectory"] and not report["missing_at_downstream"]
    for side,region in (("up","upstream"),("down","downstream")):
        expected=report[region]
        p=points[side+"_first"]
        onset=next(iter(p.values()))[0] if p else None
        assert onset==expected["first_whole_s"] and abs(duration[side]-expected["whole_hold_s"])<1e-7
        r.update({side+"_hold_s":round(duration[side],3),side+"_first_s":onset,
                  side+"_peak":expected["peak_size"],side+"_episodes":len(expected["whole_episodes"])})
    r["both_formed"]=int(r["same_ids_peak"]==n and min(duration.values())>0)
    for tag,a,b,ref in (("form", first,points["up_first"],"formation_moves"),
        ("transform",points["up_last"],points["down_first"],"transform_moves"),
        ("settled_form",first,points["up_first_set"],"settled_formation_moves"),
        ("settled_transform",points["up_last_set"],points["down_first_set"],"settled_transform_moves"),
        ("late",points["down_last_set"],last,"after_last_downstream_shape_moves")):
        mid=ledger(a,b,trips,"lane_events");end=ledger(a,b,trips,"lane_completion_events")
        ref_result=report[ref]
        if ref_result:
            assert mid[:2]==(ref_result["min_total_crossings"],ref_result["min_max_crossings"])
            for key,v in (("midpoint",mid),("completed",end)):
                assert v[2:4]==(ref_result[key]["total"],ref_result[key]["max_per_car"])
                assert bool(v[4])==bool(ref_result[key]["mismatch_ids"])
        else:
            assert mid is None or tag=="late" and report["last_off_center_ids"]
        for k,idx in (("lb_total",0),("lb_max",1),("mid_total",2),("mid_max",3),("mid_chain_errors",4)):
            r[tag+"_"+k]=mid[idx] if mid else None
        r[tag+"_end_total"]=end[2] if end else None
        r[tag+"_end_max"]=end[3] if end else None
        r[tag+"_end_chain_errors"]=end[4] if end else None
        r[tag+"_both_bounds"]=int(mid[:2]==mid[2:4] and mid[4]==0) if mid else None
    return r


def crossing_witnesses(cells,output):
    rows=[]
    for cell in cells:
        i=json.loads((cell/"index.json").read_bytes())
        m=json.loads((cell/"measure.json").read_bytes())["settled_transform_moves"]
        if not m or m["midpoint"]["max_per_car"]<=m["min_max_crossings"]:
            continue
        t0,t1=m["start_time_range_s"][0],m["end_time_range_s"][0]
        for car in json.loads((cell/i["run"]/"trips.json").read_bytes()):
            ev=[e for e in car["lane_events"] if t0<e["time_s"]<=t1]
            if len(ev)<=m["min_max_crossings"]:
                continue
            rows.append(dict(model=i["model"],road=i["road"],n=i["n"],profile=i["profile"],seed=i["seed"],
                vehicle=car["vehicle_id"],start_s=t0,end_s=t1,lower_total=m["min_total_crossings"],
                actual_total=m["midpoint"]["total"],lower_max=m["min_max_crossings"],
                lane_sequence="/".join(map(str,[ev[0]["from_lane"]]+[e["to_lane"] for e in ev])),
                times_s="/".join(str(e["time_s"]) for e in ev),
                positions_m="/".join(f"{e['x']:.4f}" for e in ev)))
    with output.open("x",newline="",encoding="utf-8") as f:
        fields=("model","road","n","profile","seed","vehicle","start_s","end_s","lower_total","actual_total",
                "lower_max","lane_sequence","times_s","positions_m")
        writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(rows)
    return len(rows)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--csv",type=Path,default=HERE/"path_holdout_9800_runs.csv")
    p.add_argument("--workers",type=int,default=4)
    p.add_argument("--witness-only",action="store_true")
    p.add_argument("--witness",type=Path,default=HERE/"path_holdout_9800_witnesses.csv")
    a=p.parse_args();cells=sorted(idx.parent for idx in a.out.glob("*/index.json"))
    assert len(cells)==96
    if a.witness_only:
        print("Double-crossing witnesses:",crossing_witnesses(cells,a.witness))
        sys.exit(0)
    with ProcessPoolExecutor(a.workers) as pool:
        rows=list(pool.map(audit,cells))
    for r in rows:
        if r["model"]=="path":
            ref=next(v for v in rows if v["model"]=="retained" and all(v[k]==r[k] for k in ("road","n","profile","seed")))
            assert all(ref[k]==r[k] for k in ("tape_sha","frame_sha","route_sha"))
    with a.csv.open("x",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,rows[0]);writer.writeheader();writer.writerows(rows)
    print(len(rows),"runs; 48 independent first-frame/geometry/event-chain comparisons;",
          crossing_witnesses(cells,a.witness),"double-crossing witnesses")
