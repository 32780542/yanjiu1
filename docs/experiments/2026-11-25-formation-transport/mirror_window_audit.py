"""Replay both two-lane template choices on archived physical windows."""
from bisect import bisect_left, bisect_right
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TRIAL = ROOT / "tmp/nov25study/mirror_hold_source"
sys.path.insert(0, str(TRIAL))
from noa import native_rules as rules, staggered as st
assert Path(st.__file__).resolve().is_relative_to(TRIAL)


def lane_history(run):
    trips=json.loads((run/"trips.json").read_bytes())
    return {r["vehicle_id"]:([e["time_s"] for e in r["lane_events"]],
                             [r["lane"]] + [e["to_lane"] for e in r["lane_events"]]) for r in trips}


def replay(frame,history,region,transition,previous,count,check_action=False):
    t=frame["time_s"]
    cars=[]
    for key,s in frame["states"].items():
        event,values=history[key]
        lane=values[bisect_right(event,t)]
        cars.append(rules.Vehicle(key,s[0],s[1],s[2],lane))
    cars.sort(key=lambda c:(c.x,c.y,c.speed))
    xs=[c.x for c in cars]
    for ego in cars:
        if not region[0]<=ego.x<region[1]:
            continue
        count["windows"]+=1
        visible=cars[bisect_left(xs,ego.x-100.):bisect_right(xs,ego.x+200.)]
        peers=[c for c in visible if c is not ego]
        group=list(reversed(rules._local_group(ego,peers)))
        if len(group)==1 and transition:
            front=min((c for c in peers if 0<c.x-ego.x<=100),key=lambda c:(c.x,c.lane),default=None)
            if front is not None:
                group=[front,ego]
        if len(group)<2:
            continue
        count["groups"]+=1
        ordered=tuple(c.track for c in group)
        spacing=rules.desired_spacing(sum(c.speed for c in group)/len(group))
        h=group[0].x-ego.x>150.
        tail=ego.x-group[-1].x>50.
        bounds=(ego.x-100.,ego.x+200.)
        result=None
        if h or tail:
            for p in (0,1):
                result=st._observed_offsets(group,2,spacing,p,bounds)
                if result is not None:
                    break
        lead=min(group[0].lane,1)%2
        if ego.track in previous:
            last_t,old_lead,old_ids=previous[ego.track]
            if abs(t-last_t-.1)<1e-6:
                count["adjacent_samples"]+=1
                if lead!=old_lead:
                    count["visible_head_lane_flip"]+=1
                    if set(ordered)==set(old_ids):
                        count["flip_same_members"]+=1
        previous[ego.track]=(t,lead,ordered)
        if result is not None:
            count["observed_unchanged"]+=1
            primary=result
        else:
            primary=st._balanced_offsets(group,2,spacing,h,tail)
            alternate=st._balanced_offsets(group,2,spacing,h,tail,mirror=True)
            population=sorted(c.lane for c in group)
            eligible=(population==sorted(j for j,_ in primary)==sorted(j for j,_ in alternate))
            count["two_zero_crossing_profiles"]+=eligible
            if st._holding_offsets(group,spacing,h,tail,primary) is not primary:
                count["trial_would_change"]+=1
        if check_action:
            origin=sum(c.x+d for c,(_,d) in zip(group,primary))/len(group)
            fit=st.solve_transport([(c.lane,c.x) for c in group],[(j,origin-d) for j,d in primary],
                                   ego_index=group.index(ego),action="next_lane",position_error=.05)
            lane=primary[fit.assignment[group.index(ego)]][0]
            count["ego_change_nominal"]+=lane!=ego.lane
            count["ego_change_strong"]+=lane!=ego.lane and fit.action_lower_bound>0
            count["local_population_needs_change"]+=bool(fit.max_crossings)


def main():
    rows=[]
    run=next((ROOT/"tmp/nov25study/selected_holdout_900/3to2_s2701_q1750").glob("*/positions.jsonl.gz")).parent
    hist=lane_history(run)
    previous=[{},{}]
    tally=[Counter(),Counter()]
    with gzip.open(run/"positions.jsonl.gz","rt") as f:
        for line in f:
            frame=json.loads(line)
            for i,region in enumerate(((800,1000),(1000,1200))):
                replay(frame,hist,region,True,previous[i],tally[i])
    for name,count in zip(("approach","downstream"),tally):
        rows.append(dict(case="3to2_1750_2701",region=name,**count))
    for n in (12,24):
        for seed in (8722,8723):
            home=ROOT/f"tmp/splice-hold-long-v1/group_2to3_{n}_long_{seed}_4000"
            run=next(home.glob("*/positions.jsonl.gz")).parent
            with gzip.open(run/"positions.jsonl.gz","rt") as f:
                for line in f:
                    frame=json.loads(line)
                    if max(s[0] for s in frame["states"].values())>=3800.:
                        break
                    last=frame
            assert len(last["states"])==n
            count=Counter()
            replay(last,lane_history(run),(0,3800),False,{},count,True)
            pop=sum(s[1]<3.3 for s in last["states"].values())
            rows.append(dict(case=f"2to3_{n}_{seed}",region="last_common_up",time=last["time_s"],
                             lane0_n=pop,lane1_n=n-pop,**count))
    dest=HERE/"mirror_window_counts.csv"
    with dest.open("x",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader(); writer.writerows(rows)
    print(rows)


if __name__=="__main__":
    main()
