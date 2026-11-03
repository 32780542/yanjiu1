"""Consolidate sealed DR/DP600 mechanism outputs without rerunning extraction."""
import argparse
import json
from pathlib import Path
import summarize_D1_mechanism as common


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    root=common.ROOT
    report=dict(DR_vs_D1=common.comparison("D1_DRDP_development36_summary_v1","D","DR"),
                DP_vs_D1=common.comparison("D1_DRDP_development36_summary_v1","D","DP"),
                fill=common.scores("DRDPdevelopment24_fill_scores_v1",24))
    raw=[common.read(p) for p in (root/"raw_DRDPdevelopment24_allLC_post5_v1").glob("*_provenance.json")]
    assert len(raw)==24 and all(p["window_complete"] and p["safe"] and p["all_complete"] for p in raw)
    report["verification"]=dict(raw_cases_n=len(raw),event_integral_checks=sum(p["event_integral_invariant_checks"] for p in raw),
       event_integral_max_error=max(p["event_integral_max_absolute_error"] for p in raw),
       independent_region_ledger_max_error=max(max(p["independent_region_ledger_absolute_errors"].values()) for p in raw))
    events=[r for p in (root/"raw_DRDPdevelopment24_allLC_post5_v1").glob("*_merges.csv") for r in common.rows(p)]
    counts=[]
    for p in raw:
        group=[r for r in events if all(str(r[k])==str(p[k]) for k in ("candidate","flow","seed","scenario","mode"))]
        early=[r for r in group if r["from_lane"]=="1" and r["to_lane"]=="0" and float(r["request_x"])<640]
        counts.append(dict(**{k:p[k] for k in ("candidate","flow","seed","scenario")},
                      all_transitions_n=len(group),early1to0_submissions_n=len(early),
                      early1to0_starts_before640_n=sum(float(r["lateral_start_x"])<640 for r in early),
                      early1to0_completions_before640_n=sum(float(r["complete_x"])<640 for r in early)))
    report["early1to0"]=dict(per_case=counts,seed_equal_means=common.grouped_mean(counts,
         ("candidate","flow","scenario"),("all_transitions_n","early1to0_submissions_n","early1to0_starts_before640_n","early1to0_completions_before640_n")))
    geo=[r for p in (root/"D1_DRDPdevelopment36_phase_geometry_v1").glob("*_phase_pairs.csv") for r in common.rows(p)]
    report["geometry_seed_equal_case_summaries"]=common.grouped_mean(geo,("candidate","flow","scenario","region","lanes"),
         ("sampled_mutual_pairs_n","abs_phase_error_p50_m","fraction_error_le2m"))
    for k in ("DR_D1_development_post5_matched_v1","DP_D1_development_post5_matched_v1"):
        report[k]=common.read(root/k/"matched_post5.json")
    report["limitations"]=["Development71/72 and600s only; final91 data are excluded.",
         "All post5 reference D1 raw remains available on both roads and both seeds; matching statistics here select mandatory lane_drop2to1 and expose each matched identity cohort.",
         "DP retains active lateral organization and own relationship flags, and is not pure NoA. DR receives the same argument but removes the future resource mapping.",
         "Local physical pair geometry is not whole-platoon formation or24/45 perturbation recovery. Positive speed deficit is not net system time.",
         "All traffic/system/fuel signs and absolute road DID belong to the complete original formal tables, independently of regional diagnostics."]
    (output/"mechanism.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    provenance={str(p.resolve()):common.hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(common.USED)}
    (output/"source_sha256.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    (output/"consolidate_DRDPdevelopment_source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(output=str(output.resolve()),input_files=len(provenance),verification=report["verification"])))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    run(parser.parse_args().output)
