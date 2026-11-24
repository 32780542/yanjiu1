"""Independent native-trajectory participation and anchor diagnostics for the two trials."""
import argparse
from bisect import bisect_left,bisect_right
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STUDY=ROOT/"tmp/nov25study"
TRIAL=ROOT/"tmp/nov25-pose-anchor"
sys.path.insert(0,str(TRIAL/"frozen/common"))
from noa import native_rules as rule,staggered
from persistent_flow import links
from measure import road_layout

def formed_predicate():
    spec=importlib.util.spec_from_file_location("pose_frozen_formed",ROOT/"tmp/nov25-formed-pair-anchor/frozen/formed_pair/noa/staggered.py")
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    return mod._inside_formed_pair


def mechanism(states,t,history,stats,predicate=None):
    cars=[]
    for k,s in states.items():
        times,lanes=history[k]
        cars.append(rule.Vehicle(k,s[0],s[1],s[2],lanes[bisect_right(times,t)]))
    cars.sort(key=lambda c:(c.x,c.y,c.speed));xs=[c.x for c in cars]
    for ego in cars:
        if not 0<=ego.x<800:
            continue
        rows=[c for c in cars[bisect_left(xs,ego.x-100):bisect_right(xs,ego.x+200)] if c is not ego]
        group=list(reversed(rule._local_group(ego,rows)))
        stats["sampled_egos"]+=1
        if len(group)<2:
            continue
        anchor=min((c.x for c in rows if c.x>group[0].x),default=None)
        if anchor is None:
            continue
        rank=group.index(ego)
        spacing=rule.desired_spacing(sum(c.speed for c in group)/len(group))
        target=staggered.choose_target(rank,group,3,spacing,head_clipped=group[0].x-ego.x>150.,
            tail_clipped=ego.x-group[-1].x>50.,sensor_bounds=(ego.x-100.,ego.x+200.),forward_anchor=anchor)
        if not target.base_positions:
            continue
        base=target.base_positions;s=target.requested_shift
        _,applied=rule._shared_anchor_speed(rank,group,base,s)
        m=sum(-100<=anchor-c.x<=200 for c in group)
        stats["positive_multi_anchor"]+=1
        stats["common_zero"]+=applied<1e-8
        stats["common_fraction_sum"]+=applied/s
        stats["visible_all"]+=m==len(group)
        stats["visible_fraction_sum"]+=2*m/(m+len(group))
        changes=[(rule._shape_speed(c,z+s)-rule._shape_speed(c,z))/rule.CONTROL_STEP for c,z in zip(group,base)]
        stats["old_differential_change"]+=max(changes)-min(changes)>.01
        if predicate is not None:
            old_speed=rule._shape_speed(ego,base[rank]+s)
            base_speed=rule._shape_speed(ego,base[rank])
            ratio=2*m/(m+len(group))
            formed=predicate(rank,group,3,spacing)
            stats["already_formed_ego"]+=formed
            stats["already_formed_speed_changed"]+=formed and abs(old_speed-base_speed)>1e-7
            stats["visible_speed_changed"]+=abs(old_speed-rule._shape_speed(ego,base[rank]+s*ratio))>1e-7
            stats["shared_gate_speed_changed"]+=m<len(group) and abs(old_speed-base_speed)>1e-7


def sampled_gates(job):
    mode,batch=job
    case=next((STUDY/batch/"3to2_s6_q1750").glob("*/positions.jsonl.gz")).parent
    trips=json.loads((case/"trips.json").read_bytes())
    history={r["vehicle_id"]:([e["time_s"] for e in r["lane_events"]],[r["lane"],*[e["to_lane"] for e in r["lane_events"]]]) for r in trips}
    stats=Counter();predicate=formed_predicate()
    with gzip.open(case/"positions.jsonl.gz","rt") as f:
        for line in f:
            frame=json.loads(line);t=frame["time_s"]
            if abs(t/2-round(t/2))<1e-7:
                mechanism(frame["states"],t,history,stats,predicate)
    keys=("sampled_egos","positive_multi_anchor","common_zero","visible_all","already_formed_ego",
          "already_formed_speed_changed","visible_speed_changed","shared_gate_speed_changed")
    return dict(model=mode,**{k:stats[k] for k in keys})


def audit(job):
    label,folder=job
    run=next(folder.glob("*/result.json")).parent
    row=json.loads((folder/"row.json").read_bytes())
    assert road_layout(run)==[(3,1000.),(2,200.)]
    trips=json.loads((run/"trips.json").read_bytes())
    history={r["vehicle_id"]:([e["time_s"] for e in r["lane_events"]],[r["lane"],*[e["to_lane"] for e in r["lane_events"]]]) for r in trips}
    audit_mechanism=row["flow"]==1750
    first={};prior=None;born=[{},{}];stats=Counter()
    with gzip.open(run/"positions.jsonl.gz","rt") as f:
        for line in f:
            frame=json.loads(line);t=frame["time_s"];states=frame["states"]
            for k,s in states.items():
                if k not in first:first[k]=(t,*s[:3])
            if prior is not None:
                old_t,counts=prior
                dt=t-old_t;assert abs(dt-.1)<1e-7
                for i,num in enumerate(counts):
                    stats[f"vehicle_s{i}"]+=dt*num
                    oldest={}
                    for pair,onset in born[i].items():
                        for layer in pair:
                            for k in layer:oldest[k]=min(onset,oldest.get(k,onset))
                    stats[f"formed_s{i}"]+=len(oldest)*dt
                    stats[f"held3_s{i}"]+=sum(max(0.,t-max(old_t,a+3)) for a in oldest.values())
            counts=[]
            for i,(lanes,lo,hi) in enumerate(((3,0,800),(2,1000,1200))):
                region={k:s for k,s in states.items() if lo<=s[0]<hi}
                active=links(region,lanes) if len(region)>=2*lanes else ()
                born[i]={pair:born[i].get(pair,t) for pair in active}
                counts.append(len(region))
            prior=t,counts
            if audit_mechanism and abs(t/2-round(t/2))<1e-7:
                mechanism(states,t,history,stats)
    assert len(first)==row["completed"]
    result=dict(model=label,seed=row["seed"],flow=row["flow"],status=row["status"],
                requested=row["requested"],completed=row["completed"],collision=row["collisions"],teleport=row["teleports"],
                tape_sha=row["arrivals_sha256"],route_sha=hashlib.sha256((run/"native.rou.xml").read_bytes()).hexdigest(),
                first_states_sha=hashlib.sha256(json.dumps(first,sort_keys=True).encode()).hexdigest(),
                up_1hz_pct=row["upstream_formed_pct"],down_1hz_pct=row["downstream_formed_pct"],travel_s=row["mean_travel_time_s"],
                crossing=row["lane_changes"])
    for i,prefix in enumerate(("up","down")):
        result[prefix+"_vehicle_s"]=round(stats[f"vehicle_s{i}"],4)
        result[prefix+"_all_pct"]=100*stats[f"formed_s{i}"]/stats[f"vehicle_s{i}"]
        result[prefix+"_held3_pct"]=100*stats[f"held3_s{i}"]/stats[f"vehicle_s{i}"]
    for k in ("sampled_egos","positive_multi_anchor","common_zero","common_fraction_sum","visible_all",
              "visible_fraction_sum","old_differential_change"):result[k]=stats[k] if audit_mechanism else None
    return result


def write(file,rows):
    with file.open("x",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",nargs="+",default=["selected","group","subflow","common","visible"])
    p.add_argument("--traffic",type=Path)
    p.add_argument("--fixed",type=Path)
    p.add_argument("--gates",type=Path)
    p.add_argument("--workers",type=int,default=3)
    p.add_argument("--include-shared-view",action="store_true")
    p.add_argument("--include-formed-pair",action="store_true")
    p.add_argument("--include-unanchored",action="store_true")
    args=p.parse_args()
    batches=dict(selected="selected_development_600",group="splice_group_600",
                 **{k:f"pose_anchor_{k}_dev" for k in ("subflow","common","visible","shared_view","formed_pair","unanchored")})
    if args.gates:
        with ProcessPoolExecutor(args.workers) as pool:
            write(args.gates,list(pool.map(sampled_gates,[(m,batches[m]) for m in args.models])))
    if args.traffic:
        jobs=[(m,STUDY/batches[m]/f"3to2_s6_q{flow}") for m in args.models for flow in (1500,1750,2000)]
        with ProcessPoolExecutor(args.workers) as pool: rows=list(pool.map(audit,jobs))
        write(args.traffic,rows)
    if args.fixed:
        rows=[json.loads(p.read_bytes()) for p in sorted(TRIAL.glob("*/row.json"))]
        assert len(rows)==84
        if args.include_shared_view:
            extra=[json.loads(p.read_bytes()) for p in sorted((ROOT/"tmp/nov25-shared-view-anchor").glob("*/row.json"))]
            assert len(extra)==28
            rows+=extra
        if args.include_formed_pair:
            extra=[json.loads(p.read_bytes()) for p in sorted((ROOT/"tmp/nov25-formed-pair-anchor").glob("*/row.json"))]
            assert len(extra)==28
            rows+=extra
        if args.include_unanchored:
            extra=[json.loads(p.read_bytes()) for p in sorted((ROOT/"tmp/nov25-unanchored-control").glob("*/row.json"))]
            assert len(extra)==28
            rows+=extra
        for r in rows:
            k="entry_states_sha" if r["profile"]=="demo12" else "first_frame_sha"
            base=next(a for a in rows if a["mode"]=="subflow" and all(a[j]==r[j] for j in ("road","n","profile","seed")))
            assert r[k]==base[k] and r["tape_sha"]==base["tape_sha"]
        keys=("mode","road","n","profile","seed","upstream_m","tape_sha","first_frame_sha","entry_states_sha",
              "status","completed","collisions","teleports","same_ids_peak","upstream_whole_hold_s","downstream_whole_hold_s",
              "upstream_peak_size","downstream_peak_size","upstream_first_whole_s","first_connected_s","last_max_gap_up_m","net_lane_crossings",
              "formation_min_total_crossings","formation_total","formation_min_max_crossings","formation_max_per_car",
              "transform_min_total_crossings","transform_total","transform_min_max_crossings","transform_max_per_car")
        write(args.fixed,[{k:r.get(k) for k in keys} for r in rows])
