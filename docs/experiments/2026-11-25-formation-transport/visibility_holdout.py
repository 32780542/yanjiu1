"""Offline visibility, grouping and kinematics in the selected 48 random holdouts.

--extend OUT also repeats the first and last declared long-layout seeds on
4000 m upstream roads, keeping demand, controller and downstream length fixed.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT/"tmp/nov25-random-selected-holdout"
ROADS = {"3to2":"formation_demo","4to3":"four_to_three_demo"}


def load_frozen():
    src = BASE/"frozen/candidate"
    sys.path.insert(0,str(src))
    from experiments import native_sumo, complete_layers
    from noa import native_rules,staggered,transport
    for m in (native_sumo,complete_layers,native_rules,staggered,transport):
        assert Path(m.__file__).resolve().is_relative_to(src)
    spec = importlib.util.spec_from_file_location("holdout_measure",BASE/"frozen/measure.py")
    measure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(measure)
    return native_sumo,measure


def initial_frame(path):
    with gzip.open(path,"rt") as f:
        return json.loads(next(f))


def extend_one(out,road,n,seed):
    case = f"{road}_{n}_long_{seed}"
    src = BASE/"frozen/candidate"
    native,measure = load_frozen()
    original = next((BASE/("candidate_"+case)).glob("*/positions.jsonl.gz")).parent
    tape = json.loads((BASE/"tapes"/(case+".json")).read_bytes())
    scenario = ROADS[road]
    old,down,lanes = native.ROAD_LAYOUT[scenario]
    assert (old,down)==(1600,1000)
    native.ROAD_LAYOUT[scenario] = 4000,down,lanes
    home = out/case
    home.mkdir()
    run = native.run_case(mode="transform",scenario=scenario,seed=seed,flow=1750,duration=8.,
                          gui=False,output_base=home,initial=tape)
    (_,up),(_,down) = measure.road_layout(run)
    assert up==4000 and down==1000
    assert initial_frame(run/"positions.jsonl.gz")==initial_frame(original/"positions.jsonl.gz")
    result = json.loads((run/"result.json").read_bytes())
    for f in ("noa/native_rules.py","noa/staggered.py","noa/transport.py"):
        assert hashlib.sha256((src/f).read_bytes()).hexdigest()==hashlib.sha256(
            (ROOT/"tmp/nov25study/selected_demo/source"/f).read_bytes()).hexdigest()
    reference = json.loads((original.parent/"measure.json").read_bytes())
    report = measure.measure(run,cohort=True)
    assert reference["arrivals_sha256"]==report["arrivals_sha256"]
    (home/"measure.json").write_text(json.dumps(report))
    assert result["status"]=="drained" and result["completed"]==n


def parallel_extensions(out,workers):
    out.mkdir(parents=True,exist_ok=False)
    jobs = [(road,n,s) for road in ROADS for n in (12,24) for s in (6411,6416)]
    def one(job):
        with (out/("_".join(map(str,job))+".log")).open("wb") as f:
            subprocess.run([sys.executable,"-E","-B",str(Path(__file__).resolve()),"--extend",str(out),
                            "--case",*map(str,job)],check=True,stdout=f,stderr=subprocess.STDOUT,timeout=600)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one,jobs))


def envelope_sum(p, q, fall, rise, steps):
    """Sum max(0, p-fall*k, q+rise*k), k=1..steps, for each (bin,car)."""
    switch = np.clip(np.floor((p-q)/(fall+rise)), 0, steps)
    last = np.clip(np.minimum(switch,np.floor(p/fall)),0,steps)
    first = np.clip(np.maximum(switch+1,np.ceil(-q/rise)),1,steps+1)
    return (last*p-fall*last*(last+1)/2
            + (steps+1-first)*(q+rise*(steps+first)/2))


def earliest_relaxed(x, v, lanes, horizon):
    """Necessary time only. All terminal roles, lanes and slot origins are free."""
    V, h, accel, brake = 33.3, .1, 5., 30.
    n=len(x)
    assert n%lanes==0
    coeff=np.sort([row+(lane%2)/2 for row in range(n//lanes) for lane in range(lanes)])[::-1]
    lo=np.arange(0.,V,.5)[:,None]
    hi=np.minimum(V,lo+1.)
    for k in range(horizon+1):
        possible=(v.max()-k*h*brake<=hi[:,0]+1e-9) & (v.min()+k*h*accel>=lo[:,0]-1e-9)
        if not possible.any():
            continue
        u,w=lo[possible],hi[possible]
        L=x+h*envelope_sum(v,u-k*h*accel,brake*h,accel*h,k)
        U=x+h*(k*V-envelope_sum(V-v,V-w-k*h*brake,accel*h,brake*h,k))
        low=np.sort(L)+coeff*(5.5+.85*u)-1.
        high=np.sort(U)+coeff*(5.5+.85*w)+1.
        if np.any(low.max(axis=1)<=high.min(axis=1)+1e-8):
            return round(k*h,1)
    return None


def envelope_check():
    rng=np.random.default_rng(711)
    for steps in range(0,73,2):
        p=rng.uniform(0,34,8)
        q=rng.uniform(-200,34,(11,1))
        for fall,rise in ((.5,3.),(3.,.5)):
            exact=sum((np.maximum(np.maximum(0,p-fall*k),q+rise*k) for k in range(1,steps+1)),
                      start=np.zeros((11,8)))
            assert np.allclose(envelope_sum(p,q,fall,rise,steps),exact,atol=1e-9)


def analyse(home,original,road,n,layout,seed,measure):
    run=next(home.glob("*/positions.jsonl.gz"))
    report=json.loads((home/"measure.json").read_bytes())
    (lanes,up),(down_lanes,down_length)=measure.road_layout(run.parent)
    boundary=up-200.
    frames=[]
    first_out={}
    last_in={}
    down_formed=down_blind=0
    down_spans=[]
    first_down=None
    with gzip.open(run,"rt") as f:
        for line in f:
            frame=json.loads(line)
            states=frame["states"]; t=frame["time_s"]
            if not frames:
                ids=tuple(f"initial_{i}" for i in range(n))
                assert len(ids)==n
            for i in ids:
                if i in states:
                    if states[i][0]<boundary:
                        last_in[i]=t
                    else:
                        first_out.setdefault(i,t)
            if all(i in states and 0<=states[i][0]<boundary for i in ids):
                frames.append((t,states))
            if (len(states)==n and all(up<=s[0]<up+down_length for s in states.values())
                    and measure.whole_shape(states,down_lanes)):
                if first_down is None:
                    first_down=t
                down_formed+=1
                xs=[s[0] for s in states.values()]
                rear,front=min(xs),max(xs)
                down_spans.append(front-rear)
                down_blind+=not any(front-x<=200 and x-rear<=100 for x in xs)
    assert first_down==report["downstream"]["first_whole_s"]
    h=.1
    ts=np.array([t for t,s in frames])
    assert np.allclose(np.diff(ts),h) and len(last_in)==n and len(first_out)==n
    pos=np.array([[s[i][0] for i in ids] for t,s in frames])
    vel=np.array([[s[i][2] for i in ids] for t,s in frames])
    sorted_x=np.sort(pos)
    gaps=np.diff(sorted_x,axis=1)
    comps=1+np.sum(gaps>50.,axis=1)
    observers=((sorted_x[:,-1,None]-sorted_x<=200.) & (sorted_x-sorted_x[:,0,None]<=100.)).sum(axis=1)
    formed=np.array([measure.whole_shape(s,lanes) for t,s in frames])
    assert (float(ts[formed][0]) if formed.any() else None)==report["upstream"]["first_whole_s"]
    assert np.all(comps[formed]==1)
    acc=np.diff(vel,axis=0)/h
    dx_error=np.max(abs(np.diff(pos,axis=0)-h*vel[1:]))
    assert np.min(vel)>=-1e-9 and np.max(vel)<=33.3+1e-8 and np.min(acc)>=-30.00001 and np.max(acc)<=5.00001 and dx_error<1e-7
    low=earliest_relaxed(pos[0],vel[0],lanes,len(ts)-1)
    assert not formed.any() or (low is not None and low<=ts[formed][0]-ts[0]+1e-7)
    def first(mask):
        return round(ts[mask][0]-ts[0],1) if mask.any() else ""
    def packed(vals):
        return "/".join(f"{v:.3f}" for v in vals)
    same_prefix=first_difference=max_prefix_dx=max_prefix_dv=""
    if original:
        prefix=next(original.glob("*/positions.jsonl.gz"))
        same_prefix=0
        max_prefix_dx=max_prefix_dv=0.
        base_meta=json.loads((prefix.parent/"result.json").read_bytes())
        extension_meta=json.loads((run.parent/"result.json").read_bytes())
        assert base_meta["source_sha256"]==extension_meta["source_sha256"]
        with gzip.open(prefix,"rt") as f:
            for (t,states),line in zip(frames,f):
                ref=json.loads(line)
                if max(s[0] for s in ref["states"].values())>=1400:
                    break
                assert t==ref["time_s"] and states.keys()==ref["states"].keys()
                if first_difference=="" and ref["states"]!=states:
                    first_difference=t
                if first_difference=="":
                    same_prefix+=1
                max_prefix_dx=max(max_prefix_dx,max(abs(s[0]-ref["states"][i][0]) for i,s in states.items()))
                max_prefix_dv=max(max_prefix_dv,max(abs(s[2]-ref["states"][i][2]) for i,s in states.items()))
    return dict(road=road,n=n,layout=layout,seed=seed,upstream_m=up,
        initial_span_m=round(np.ptp(pos[0]),4),initial_max_gap_m=round(gaps[0].max(),3),
        initial_components=int(comps[0]),initial_full_observers=int(observers[0]),
        initial_front_to_preview_m=round(boundary-pos[0].max(),3),
        initial_tail_to_preview_m=round(boundary-pos[0].min(),3),
        common_available_s=round(ts[-1]-ts[0],1),longest_individual_available_s=round(max(last_in.values())-ts[0],1),
        individual_to_preview_m_by_entry_id=packed(boundary-pos[0]),
        individual_upstream_s_by_entry_id=packed([last_in[i]-ts[0] for i in ids]),
        individual_common_travel_m_by_entry_id=packed(pos[-1]-pos[0]),
        final_components=int(comps[-1]),peak_components=int(comps.max()),min_components=int(comps.min()),
        first_connected_s=first(comps==1),first_full_observer_s=first(observers>0),
        first_full_group_observer_s=first((comps==1)&(observers>0)),
        common_samples=len(frames),disconnected_samples=int((comps>1).sum()),
        breaks_both_directions_visible=int(((50<gaps)&(gaps<=100)).any(axis=1).sum()),
        breaks_one_direction_visible=int(((100<gaps)&(gaps<=200)).any(axis=1).sum()),
        breaks_neither_direction_visible=int((gaps>200).any(axis=1).sum()),
        no_full_observer_samples=int((observers==0).sum()),not_all_see_samples=int((observers<n).sum()),
        connected_no_full_observer_samples=int(((comps==1)&(observers==0)).sum()),
        disconnected_with_full_observer_samples=int(((comps>1)&(observers>0)).sum()),
        formed_samples=int(formed.sum()),formed_no_full_observer_samples=int((formed&(observers==0)).sum()),
        formed_not_all_see_samples=int((formed&(observers<n)).sum()),
        final_span_m=round(np.ptp(pos[-1]),3),final_max_gap_m=round(gaps[-1].max(),3),
        last_10s_ranked_gap_max_range_m=round(np.ptp(gaps[-101:],axis=0).max(),6),
        last_10s_max_fleet_speed_spread_m_s=round(np.ptp(vel[-101:],axis=1).max(),6),
        last_sample_full_observers=int(observers[-1]),relaxed_necessary_s=low,
        up_first_s=first(formed),up_hold_s=report["upstream"]["whole_hold_s"],up_peak=report["upstream"]["peak_size"],
        down_hold_s=report["downstream"]["whole_hold_s"],down_formed_samples=down_formed,
        down_formed_no_full_observer_samples=down_blind,
        down_formed_min_span_m=round(min(down_spans),3) if down_spans else "",
        down_formed_max_span_m=round(max(down_spans),3) if down_spans else "",prefix_exact_samples=same_prefix,
        prefix_first_difference_s=first_difference,prefix_max_dx_m=max_prefix_dx,prefix_max_dv_m_s=max_prefix_dv,
        min_accel=round(float(acc.min()),6),max_accel=round(float(acc.max()),6),
        collisions=report["collisions"],teleports=report["teleports"])


def process(extended,out):
    _,measure=load_frozen()
    envelope_check()
    rows=[]
    for home in sorted(p for p in BASE.glob("candidate_*") if p.is_dir()):
        _,road,n,layout,seed=home.name.split("_")
        rows.append(analyse(home,None,road,int(n),layout,int(seed),measure))
    if extended:
        for home in sorted(p for p in extended.iterdir() if p.is_dir()):
            road,n,layout,seed=home.name.split("_")
            rows.append(analyse(home,BASE/("candidate_"+home.name),road,int(n),layout,int(seed),measure))
    with out.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} runs to {out}")


if __name__=="__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--extend",type=Path)
    p.add_argument("--case",nargs=3)
    p.add_argument("--workers",default=4,type=int)
    p.add_argument("--extended",type=Path)
    p.add_argument("--output",type=Path,default=HERE/"visibility_holdout.csv")
    a=p.parse_args()
    if a.case:
        extend_one(a.extend.resolve(),a.case[0],int(a.case[1]),int(a.case[2]))
    elif a.extend:
        parallel_extensions(a.extend.resolve(),a.workers)
    else:
        process(a.extended,a.output)
