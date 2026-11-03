"""Independent read-only physical-neighbor graph and shadow-state review."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import review_candidates as shared


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--states",type=int,default=2000)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("new output required")
    root=shared.REPO/"tmp/staggered_bottleneck/candidates"
    names=("direct_gap","local_phase_coupling","time_scaled_phase_coupling",
           "local_phase_coupling_physical","time_scaled_phase_coupling_physical")
    paths={name:root/name/"native_rules.py" for name in names}
    paths["production"]=shared.REPO/shared.RULE
    raw={name:path.read_bytes() for name,path in paths.items()}
    modules={name:shared.module("J2_review_"+name,data,paths[name]) for name,data in raw.items() if name!="production"}
    e=modules["direct_gap"]
    report=dict(states=args.states,random_seed=shared.SEED,candidates={},source_sha256={k:shared.digest(v) for k,v in raw.items()})
    for name,parent in (("local_phase_coupling_physical","local_phase_coupling"),
                        ("time_scaled_phase_coupling_physical","time_scaled_phase_coupling")):
        r,old=modules[name],modules[parent]
        metadata=json.loads((shared.REPO/"docs/experiments/2026-11-03-staggered-bottleneck/candidates"/name/"source.json").read_bytes())
        assert metadata["source_sha256"]==shared.digest(raw[name])
        assert metadata["parent_sha256"]==shared.digest(raw[parent])
        structure=shared.structure(raw[name],raw[parent])
        assert structure["changed_definitions"]==["_following"]
        versus_e=shared.structure(raw[name],raw["direct_gap"])
        assert versus_e["changed_definitions"]==["_fill","_following","_pair_error","_phase"]
        assert raw[name].decode().replace("        if 0 <= lane < 3:\n","        if 0 <= lane < lanes:\n")==raw[parent].decode()
        counts=dict(noa_e_exact=0,retained_only_parent_exact=0,track_order_exact=0,remote_exact=0,pair_error_antisymmetric=0)
        for values,memory,labels,drop in shared.scenes(args.states):
            assert shared.decision(r,values,memory,"noa",drop)==shared.decision(e,values,memory,"noa",drop)
            counts["noa_e_exact"]+=1
            retained=[]
            for car in values:
                lane=car["lane"]%2
                retained.append({**car,"lane":lane,"y":car["y"]+(lane-car["lane"])*r.LANE_WIDTH})
            for mode in ("noa","formation","transform"):
                original=shared.decision(r,values,memory,mode,drop)
                assert shared.decision(r,values,memory,mode,drop,labels,reverse=True)==original
                counts["track_order_exact"]+=1
                assert shared.decision(r,values,memory,mode,drop,remote=True)==original
                counts["remote_exact"]+=1
                assert shared.decision(r,retained,memory,mode,drop)==shared.decision(old,retained,memory,mode,drop)
                counts["retained_only_parent_exact"]+=1
            cars,_=shared.state(r,values,memory)
            a,b=cars[:2]
            forward=r._pair_error(a,b,2,640)[0]
            reverse=r._pair_error(b,a,3,640)[0]
            assert abs(forward+reverse)<1e-10
            counts["pair_error_antisymmetric"]+=1
        car=lambda track,x,lane:r.Vehicle(track,x,(lane+.5)*r.LANE_WIDTH,28.8,lane)
        middle,ending=car(1,700,1),car(2,700,2)
        cars=(middle,ending,car(11,730,1),car(12,730,2))
        increments=[]
        for ego,lanes in ((middle,2),(ending,3)):
            rows=tuple(c for c in cars if c is not ego)
            output=r._following(ego,rows,lanes,640)
            increments.append(output[0]-r._front_following(ego,rows)[0])
        assert abs(increments[0]+.4)<1e-10 and abs(increments[1]-.4)<1e-10
        report["candidates"][name]=dict(relative_to_parent=structure,relative_to_E=versus_e,
            **counts,preparation_middle_ending_body_increments=increments)
        print(json.dumps(dict(candidate=name,**counts)),flush=True)
    assert shared.structure(raw["time_scaled_phase_coupling_physical"],raw["local_phase_coupling_physical"])["changed_definitions"]==["_pair_error"]
    assert all(path.read_bytes()==raw[name] for name,path in paths.items())
    report.update(protected_sources_unchanged=True,driver_sha256=shared.digest(Path(__file__).read_bytes()),
        shared_driver_sha256=shared.digest(Path(shared.__file__).read_bytes()),simulations_run=False,
        limits="Finite source/shadow checks do not establish congestion benefit, zero-sum node dynamics, or complete formation recovery. Head cruise recovery and existing task/safety overrides remain active.")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
