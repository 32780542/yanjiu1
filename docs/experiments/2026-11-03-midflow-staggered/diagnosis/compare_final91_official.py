"""Check original formal directions against independent direct D1-reference results."""
import argparse
import csv
import json
from pathlib import Path
from audit_raw_midflow import sha

METRICS=("mean_system_time_s","mean_travel_time_s","mean_entry_wait_s","fuel_g_per_km")


def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def compare(audit,pairs_path,did_path,reference):
    independent={(float(r["flow"]),int(r["seed"]),r["scenario"]):r for r in rows(audit/"paired_seeds.csv") if r["reference"]==reference}
    ind_did={(float(r["flow"]),int(r["seed"])):r for r in rows(audit/"road_did_seeds.csv") if r["reference"]==reference}
    cases={(r["label"],float(r["flow"]),int(r["seed"]),r["scenario"]):r for r in rows(audit/"per_case.csv")}
    official=rows(pairs_path)
    official_did=rows(did_path)
    assert len(independent)==len(official)==30 and len(ind_did)==len(official_did)==15
    checks,max_error=0,0.
    def equal(a,b):
        nonlocal checks,max_error
        error=abs(float(a)-float(b));max_error=max(max_error,error);checks+=1
        assert error<1e-7,(a,b,error)
    for original in official:
        key=float(original["flow"]),int(original["seed"]),original["scenario"]
        r=independent[key]
        assert original["pair_eligible"]==r["eligible"]=="True"
        a,b=cases[(reference,*key)],cases[("D1",*key)]
        for field in METRICS:
            for prefix,suffix in (("reference_","_reference"),("candidate_","_candidate"),("delta_","_delta")):
                equal(original[prefix+field],r[field+suffix])
        for prefix,case in (("reference_",a),("candidate_",b)):
            if prefix+"case_dir" in original:
                assert Path(original[prefix+"case_dir"]).resolve()==Path(case["case_dir"]).resolve()
            if prefix+"rules_sha256" in original:
                assert original[prefix+"rules_sha256"]==case["rules_sha256"]
        supplemental={"region_mean_n":lambda c:float(c["region_window_vehicle_s"])/500,
          "region_density_veh_km_lane":lambda c:float(c["region_window_vehicle_s"])/500/.2/3,
          "region_mean_speed_mps":lambda c:float(c["region_window_mean_speed_mps"]),
          "region_low_speed_vehicle_s":lambda c:float(c["region_window_low_speed_vehicle_s"]),
          "flow_1000m_veh_h":lambda c:float(c["crossing1000_window_n"])*3600/500,
          "lane_changes":lambda c:float(c["midpoint_transitions_n"]),
          "lane_change_completions":lambda c:float(c["strict_completions_n"])}
        for field,formula in supplemental.items():
            if original.get("delta_"+field) not in (None,""):
                equal(original["delta_"+field],formula(b)-formula(a))
        if original.get("system_improvement_percent") not in (None,""):
            equal(original["system_improvement_percent"],r["system_improvement_percent"])
    for original in official_did:
        key=float(original["flow"]),int(original["seed"])
        r=ind_did[key]
        assert original["pair_eligible"]==r["eligible"]=="True"
        for field in METRICS:
            equal(original["did_"+field],r[field+"_did"])
    return dict(reference=reference,paired_n=30,road_DID_n=15,numeric_checks=checks,max_absolute_error=max_error,
                official_pair_csv=str(pairs_path.resolve()),official_pair_sha256=sha(pairs_path),
                official_DID_csv=str(did_path.resolve()),official_DID_sha256=sha(did_path))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit",type=Path,required=True)
    parser.add_argument("--pairs",type=Path,required=True)
    parser.add_argument("--did",type=Path,required=True)
    parser.add_argument("--reference",choices=("NOA","S"),required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    assert not args.output.exists()
    result=compare(args.audit,args.pairs,args.did,args.reference)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
