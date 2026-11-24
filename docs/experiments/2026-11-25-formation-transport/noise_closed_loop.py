"""Matched native SUMO measurement-noise experiments using the selected frozen source.

Run from the repo root with --out tmp/nov25study/noise_run01 --workers 6.
The same seeded observer/object/time variate is used by both policies.
Only the local assignment planner receives perturbed x; it rebuilds ordering,
slot template and fitted origin. Range filtering, lane observations, velocity,
physical following, safety checks, actuation and SUMO use physical state.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT = ROOT/"tmp/nov25study/selected_demo"
ROADS = {"3to2":"formation_demo", "4to3":"four_to_three_demo",
         "2to3":"two_to_three_demo", "3to4":"three_to_four_demo"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def positions_hash(folder):
    sha = hashlib.sha256()
    with gzip.open(folder/"positions.jsonl.gz","rb") as f:
        while block := f.read(1<<20):
            sha.update(block)
    return sha.hexdigest()


def first_positions(folder):
    rows = {}
    n = json.loads((folder/"result.json").read_bytes())["requested"]
    with gzip.open(folder/"positions.jsonl.gz","rt",encoding="utf-8") as frames:
        for line in frames:
            frame = json.loads(line)
            for key,state in frame["states"].items():
                rows.setdefault(key,(frame["time_s"],*state[:3]))
            if len(rows)==n:
                break
    return rows


def audit(frozen,out,destination):
    """Compare realized entries and audit raw trajectories, including unformed endpoints."""
    rows, bases = [], {}
    for path in sorted(out.glob("*/row.json")):
        row = json.loads(path.read_bytes())
        key = (row["road"],row["cohort"])
        if key not in bases:
            home = frozen/(f"{key[0]}_s20_q1750"+("" if key[1]=="stream" else "_"+key[1]))
            base = next(home.glob("*/positions.jsonl.gz")).parent
            bases[key] = first_positions(base),positions_hash(base)
        before,sha = bases[key]
        up,down = map(int,key[0].split("to"))
        tape = json.loads((frozen/f"{key[0]}_{key[1]}.json").read_bytes())
        assert len(tape)%up==len(tape)%down==0
        source = sorted(car["lane"] for car in tape)
        upstream = sorted(list(range(up))*(len(tape)//up))
        downstream = sorted(list(range(down))*(len(tape)//down))
        for name,left,right in (("formation",source,upstream),("transform",upstream,downstream)):
            hops = [abs(a-b) for a,b in zip(left,right)]
            row[name+"_ideal_lb_total"] = sum(hops)
            row[name+"_ideal_lb_max"] = max(hops)
        folder = ROOT/row["run"]
        after = first_positions(folder)
        assert before.keys()==after.keys()
        row["entry_geometry_differences"] = sum(before[k][1:]!=after[k][1:] for k in before)
        row["entry_time_differences"] = sum(before[k][0]!=after[k][0] for k in before)
        row["max_entry_time_delta_s"] = round(max(abs(before[k][0]-after[k][0]) for k in before),3)
        row["frozen_baseline_frames_equal"] = sha==row["positions_sha256"]
        assert row["positions_sha256"]==positions_hash(folder)
        provenance = json.loads((path.parent/"provenance.json").read_bytes())
        assert all(Path(f).is_relative_to(frozen/"source") for f in provenance.values())
        assert row["rescued"]==row["strong_yes"]-row["coarse_yes"]
        assert row["fixed_slot_shadow_disagreement"]==0
        rows.append(row)
    assert len(rows)==90 and len({(r["road"],r["cohort"],r["noise_seed"],r["certificate_eps_m"],r["policy"])
                                  for r in rows})==90
    with destination.open("w",encoding="utf-8",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    print(destination,len(rows))


def worker(frozen, out, road, cohort, seed, eps, policy):
    source = frozen/"source"
    sys.path.insert(0,str(source))
    from experiments import native_sumo, complete_layers
    from noa import native_rules, staggered, transport
    modules = (native_sumo, complete_layers, native_rules, staggered, transport)
    files = json.loads((frozen/"manifest.json").read_bytes())["files"]
    for key,wanted in files.items():
        assert digest(source/key)==wanted, key
    for module in modules:
        assert Path(module.__file__).resolve().is_relative_to(source), module.__file__
    tape = frozen/f"{road}_{cohort}.json"
    spec = json.loads(tape.read_bytes())
    base_case = frozen/(f"{road}_s20_q1750"+("" if cohort=="stream" else "_"+cohort))
    baseline = next(base_case.glob("*/positions.jsonl.gz")).parent
    stats = Counter(dict.fromkeys(("match","different_lane","coarse_yes","strong_yes","rescued",
                                   "strong_rejected","selected_yes","fixed_slot_shadow_disagreement",
                                   "selected_shadow_disagreement","template_shadow_disagreement",
                                   "nominal_yes","selected_template_disagreement"),0))
    ctx = {}
    observe, choose, solve = native_sumo.LocalTracks.observe, staggered.choose_target, staggered.solve_transport

    def observed(self,ego_id,states,*args,**kwargs):
        result = observe(self,ego_id,states,*args,**kwargs)
        names = {track:key for key,track in self.tracks[ego_id].items()}
        names[0] = ego_id
        ctx.update(ego_id=ego_id,names=names,tick=round(result[0].time*10))
        return result

    def measured(rank,group,lanes,spacing,**kwargs):
        original = {c.track:c for c in group}
        true_ego = group[rank]
        if seed:
            observed_group = []
            for c in group:
                token = f"{seed}/{ctx['tick']}/{ctx['ego_id']}/{ctx['names'][c.track]}".encode()
                bits = int.from_bytes(hashlib.blake2b(token,digest_size=8).digest(),"big") >> 11
                error = eps*(2*(bits/2**53)-1)
                observed_group.append(replace(c,x=c.x+error))
            observed_group.sort(key=lambda c:(-c.x,-c.lane))
            rank_measured = next(i for i,c in enumerate(observed_group) if c.track==true_ego.track)
        else:
            observed_group, rank_measured = group,rank
        ctx["true_order"] = [(original[c.track].lane,original[c.track].x) for c in observed_group]
        ctx["shadow"] = False
        result = choose(rank_measured,observed_group,lanes,spacing,**kwargs)
        stats["match"] += 1
        coarse = result.step_certified and not result.refined
        chosen = {"strong":result.step_certified,"coarse":coarse,"nominal":result.step_gap>0}[policy]
        if result.lane != true_ego.lane:
            stats["different_lane"] += 1
            stats["nominal_yes"] += result.step_gap>0
            stats["coarse_yes"] += coarse
            stats["strong_yes"] += result.step_certified
            stats["rescued"] += result.refined
            stats["strong_rejected"] += not result.step_certified
            stats["selected_yes"] += chosen
            if result.step_gap>0 and seed:
                physical = solve(ctx["true_order"],ctx["slots"],ego_index=rank_measured,action="next_lane")
                step = true_ego.lane+(1 if result.lane>true_ego.lane else -1)
                disagreement = physical.action_lane!=step or physical.action_gap<=0
                stats["fixed_slot_shadow_disagreement"] += result.step_certified and disagreement
                stats["selected_shadow_disagreement"] += chosen and disagreement
                # Rebuild the clean template too. Membership and safety stay
                # on the same physical frame; alternative dynamics are not run.
                ctx["shadow"] = True
                clean = choose(rank,group,lanes,spacing,**kwargs)
                clean_step = true_ego.lane+(clean.lane>true_ego.lane)-(clean.lane<true_ego.lane)
                other = clean_step!=step or clean.step_gap<=0
                stats["template_shadow_disagreement"] += result.step_certified and other
                stats["selected_template_disagreement"] += chosen and other
        return replace(result,step_certified=chosen,refined=False) if policy!="strong" else result

    def matched(vehicles,slots,**kwargs):
        if not ctx["shadow"]:
            ctx["slots"] = slots
        return solve(vehicles,slots,**kwargs)

    native_sumo.LocalTracks.observe = observed
    staggered.POSITION_ERROR_M = eps
    staggered.solve_transport = matched
    staggered.choose_target = measured
    folder = native_sumo.run_case(mode="transform",seed=20,scenario=ROADS[road],flow=1750.,
                                  duration=8.,road_limit=33.3,initial=spec,output_base=out)
    from measure import measure
    from run_study import audit_row
    report = measure(folder,cohort=True)
    # Raw arrivals, real route/network and generation parameters are frozen.
    for name in ("native.rou.xml","native.net.xml"):
        assert ET.canonicalize(from_file=folder/name)==ET.canonicalize(from_file=baseline/name), name
    original = json.loads((base_case/"row.json").read_bytes())
    assert report["arrivals_sha256"]==original["arrivals_sha256"]
    row = dict(road=road,cohort=cohort,noise_seed=seed,measurement_eps_m=eps if seed else 0,
               certificate_eps_m=eps,policy=policy,tape_sha256=digest(tape),**stats)
    info = audit_row(folder,report,"demo")
    for key in ("requested","departed","completed","collisions","teleports","safe","status",
                "upstream_whole_hold_s","downstream_whole_hold_s","upstream_whole_total_s",
                "downstream_whole_total_s","upstream_peak_size","downstream_peak_size","lane_changes"):
        row[key] = info[key]
    for region in ("formation","transform"):
        for key in ("actual_total","min_total_crossings","actual_max_per_car","min_max_crossings"):
            row[region+"_"+key] = info[region+"_"+key]
    row["refined_requests"] = sum(a.get("refined_requests",0) for a in report["transport_certificates"].values())
    row["positions_sha256"] = positions_hash(folder)
    row["run"] = folder.relative_to(ROOT).as_posix() if folder.is_relative_to(ROOT) else str(folder)
    if seed==0 and eps==.05 and policy=="strong":
        assert row["positions_sha256"]==positions_hash(baseline)
    (out/"row.json").write_text(json.dumps(row,indent=2))
    (out/"provenance.json").write_text(json.dumps({m.__name__:str(m.__file__) for m in modules},indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frozen",type=Path,default=DEFAULT)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--audit-csv",type=Path,help="verify finished native trajectories and write the compact table")
    p.add_argument("--case",nargs=5,metavar=("ROAD","COHORT","SEED","EPS","POLICY"))
    args = p.parse_args()
    frozen,out = args.frozen.resolve(),args.out.resolve()
    if args.audit_csv:
        return audit(frozen,out,args.audit_csv)
    if args.case:
        road,cohort,seed,eps,policy = args.case
        return worker(frozen,out,road,cohort,int(seed),float(eps),policy)
    out.mkdir(parents=True,exist_ok=True)
    scenarios = [(road,"stream") for road in ROADS]+[("3to2","chain24")]
    jobs = [(road,cohort,seed,eps,policy) for road,cohort in scenarios for seed in (0,1125,2026)
            for eps in (.05,.25) for policy in ("coarse","strong","nominal")]
    def one(job):
        road,cohort,seed,eps,policy = job
        home = out/f"{road}_{cohort}_{seed}_{eps}_{policy}"
        home.mkdir(exist_ok=True)
        if not (home/"row.json").exists():
            cmd = [sys.executable,"-E","-B",str(Path(__file__).resolve()),"--frozen",str(frozen),
                   "--out",str(home),"--case",road,cohort,str(seed),str(eps),policy]
            with (home/"log.txt").open("wb") as log:
                subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        return json.loads((home/"row.json").read_bytes())
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(one,jobs))
    with (out/"summary.csv").open("w",encoding="utf-8",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    print(out/"summary.csv",len(rows))


if __name__=="__main__":
    main()
