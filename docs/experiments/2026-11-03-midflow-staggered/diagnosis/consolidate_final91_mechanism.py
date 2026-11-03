"""Close all45 final lane-drop post5/actual-LC outputs without control feedback."""
import argparse
import json
from pathlib import Path
from statistics import mean,median
import summarize_D1_mechanism as common


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    root=common.ROOT
    directories=[root/"raw_final91_D1_NOA_drop30_allLC_post5_v1",root/"raw_final91_S_drop15_allLC_post5_v1"]
    audited={(r["label"],float(r["flow"]),int(r["seed"]),r["scenario"]):r for r in common.rows(root/"final91_independent_v1/per_case.csv")}
    provenance,early_rows,censored=[],[],[]
    postchecks,mandatory_n=0,0
    for directory in directories:
        for path in sorted(directory.glob("*_provenance.json")):
            p=common.read(path)
            assert p["window_complete"] and p["safe"] and p["all_complete"]
            label="S" if p["candidate"]=="S" else "NOA" if p["mode"]=="noa" else "D1"
            key=label,float(p["flow"]),int(p["seed"]),p["scenario"]
            assert p["positions_sha256"]==audited[key]["positions_sha256"]
            assert Path(p["case_dir"]).resolve()==Path(audited[key]["case_dir"]).resolve()
            data=common.rows(path.with_name(path.name.replace("_provenance.json","_merges.csv")))
            mandatory=[r for r in data if r["from_lane"]=="2" and r["to_lane"]=="1" and float(r["request_x"])>=640]
            mandatory_n+=len(mandatory)
            for event in mandatory:
                for role in ("entrant","receiver"):
                    if not event.get(role+"_merge_observed_s"):
                        continue
                    for window,target in (("post0_2",2),("post2_5",3)):
                        observed=float(event.get(role+"_"+window+"_observed_s",0))
                        postchecks+=1
                        if abs(observed-target)>1e-7:
                            censored.append(dict(**{k:p[k] for k in ("candidate","mode","flow","seed")},vehicle=event["vehicle_id"],role=role,window=window,observed_s=observed))
            early=[r for r in data if r["from_lane"]=="1" and r["to_lane"]=="0" and float(r["request_x"])<640]
            row=dict(label=label,flow=p["flow"],seed=p["seed"],all_LC_n=len(data),mandatory_2to1_n=len(mandatory),
                     early1to0_submissions_n=len(early),early1to0_actual_starts_before640_n=sum(float(r["lateral_start_x"])<640 for r in early),
                     early1to0_strict_completions_before640_n=sum(float(r["complete_x"])<640 for r in early))
            if early:
                row.update(early1to0_request_x_p50_m=median(float(x["request_x"]) for x in early),
                           early1to0_start_x_p50_m=median(float(x["lateral_start_x"]) for x in early))
                for role in ("entrant","receiver"):
                    field=role+"_through_post5_hard_brake_s"
                    values=[float(x[field]) for x in early if x.get(field)]
                    if values:row["early1to0_"+field+"_mean"]=mean(values)
            early_rows.append(row)
            provenance.append(p)
    assert len(provenance)==45
    fields=[k for k in early_rows[0] if k.endswith("_n") or k.endswith("_m") or k.endswith("_mean")]
    report=dict(verification=dict(cases_n=45,matched_to_original90_audit=True,mandatory_2to1_events_n=mandatory_n,
          all_LC_events_n=sum(p["events"] for p in provenance),event_integral_invariant_checks=sum(p["event_integral_invariant_checks"] for p in provenance),
          event_integral_max_error=max(p["event_integral_max_absolute_error"] for p in provenance),
          independent_region_ledger_max_error=max(max(p["independent_region_ledger_absolute_errors"].values()) for p in provenance),
          mandatory_post5_window_checks=postchecks,censored_mandatory_windows=censored),
          early1to0_per_case=early_rows,early1to0_seed_equal_means=common.grouped_mean(early_rows,("label","flow"),fields),
          region_and_merge_seed_equal_means=common.rows(root/"final91_drop45_mechanism_summary_v1/seed_equal_means.csv"))
    for reference,folder in (("NOA","final91_D1_NOA_post5_matched_v1"),("S","final91_D1_S_post5_matched_v1")):
        matched=common.read(root/folder/"matched_post5.json")
        means=[]
        for flow in (1500,1750,2000):
            for cohort in ("same_entrant","same_entrant_and_receiver"):
                selected=sorted((x for x in matched["summaries"] if x["flow"]==flow and x["cohort"]==cohort),key=lambda x:x["seed"])
                assert len(selected)==5
                row=dict(flow=flow,reference=reference,cohort=cohort,seeds=[x["seed"] for x in selected],event_n_each_seed=[x["n"] for x in selected])
                for role in ("entrant","receiver"):
                    for window in ("merge","post0_2","post2_5","through_post5"):
                        for metric in ("hard_brake_s","negative_acceleration_integral_mps","acceleration_square_integral_m2ps3"):
                            field=role+"_"+window+"_"+metric
                            row[field]={side:mean(x[field][side] for x in selected) for side in ("reference","candidate","delta")}
                means.append(row)
        report["post5_vs_"+reference]=dict(five_seed_equal_means=means,per_seed=matched["summaries"])
    report["limitations"]=["Final91–95, all45 lane-drop cases only; full90 formal traffic and roadDID remain unchanged.",
          "Regional window100–600s; event integrals use the full original requests to completion+5s, not selected favorable phases.",
          "Early1to0 counts use full recorded strict events; request, first measured start and strict completion before640 are separate.",
          "Receiver event windows overlap; event means cannot be summed as unique whole-road exposure. Positive speed deficit excludes overspeed credits and is not net system time.",
          "Same identities do not fix timing/position/other vehicles and are not a randomized single-event causal contrast.",
          "No final data were fed to control or used to change the locked source. Formation flags do not replace true geometry."]
    (output/"mechanism.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    common.USED.update([Path(__file__),Path(common.__file__)])
    (output/"source_sha256.json").write_text(json.dumps({str(p.resolve()):common.hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(common.USED)},indent=2)+"\n",encoding="utf-8")
    (output/"consolidate_final91_mechanism_source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(output=str(output.resolve()),verification=report["verification"])))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    run(parser.parse_args().output)
