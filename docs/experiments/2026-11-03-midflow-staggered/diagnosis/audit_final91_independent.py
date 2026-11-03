"""Independent original/trip/raw/ledger reconstruction for all locked final91 cases.

This imports no traffic evaluator and never runs a simulator or controller.
Full matrix sealing is required before any table is emitted.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean
import tarfile
from audit_raw_midflow import read, sha, write_csv

D1 = "2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a"
S = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
NONRULE = {
    "experiments/native_sumo.py": "bc22273fa224206e03dd896fb7b386a5d28ce3526fddebfa6bf7d7c93caaa1d1",
    "experiments/global_reference.py": "b10a3b450c4c9b13968aefeff4fcb3c248e84cd7dabd2f8be3be8de74bf14279",
    "experiments/complete_layers.py": "4dc155c13ac78eb2f351529f9de92b82f8470250df9157561fc23a7932cfdb60",
    "run_native_flow.py": "986431e85af09e2e4610d5be5570ea0860606717e94ca64a1167f07f3f9c3e24",
    "research/common.py": "de1cfb560b4b842c6d5c813bdbec7fcb0cce6b4027994911b91e5ef6b7cc2c5c",
}


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def close(a, b, tolerance=1e-7):
    assert a is not None and b is not None and abs(a-b) < tolerance, (a, b)


def verify_case(folder, label, raw_check=True):
    record = read(folder / "case_record.json")
    assert record.get("seal_status") == "verified", folder
    assert record["base_commit"] == "177f7a32088fb69efcc94d9acb72863e7e00e787"
    run, evidence = Path(record["run_dir"]), folder / "evidence"
    seal = read(evidence / "seal.json")
    for relative, digest in seal["files"].items():
        assert sha(evidence / relative) == digest, relative
    for relative, info in seal["originals"].items():
        file = run / relative
        assert file.stat().st_size == info["bytes"] and sha(file) == info["sha256"], file
    with tarfile.open(evidence / "compact/bundle.tar.gz", "r:gz") as archive:
        index_bytes = archive.extractfile("index.json").read()
        assert hashlib.sha256(index_bytes).hexdigest() == read(evidence / "compact/bundle.json")["index_sha256"]
        indexed = json.loads(index_bytes)["cases"]
        assert len(indexed) == 1
        for relative, digest in indexed[0]["files"].items():
            file = run / relative
            if file.is_file():
                assert sha(file) == digest, file
    original, result, trips = read(run / "input.json"), read(run / "result.json"), read(run / "trips.json")
    assert original["source_sha256"] == result["source_sha256"]
    assert {k:v for k,v in result["source_sha256"].items() if k != "noa/native_rules.py"} == NONRULE
    for relative, digest in result["source_sha256"].items():
        assert sha(run / "source" / relative) == digest
    assert result["source_sha256"]["noa/native_rules.py"] == (S if label == "S" else D1)
    assert result["demand_duration_s"] == 600 and result["max_time_s"] == 1200 and result["step_s"] == .1
    assert result["lane_change_duration_s"] == 1 and original["positions_step_s"] == .1
    assert original["physical"]["maxSpeed"] == 33.3 and original["physical"]["speedFactor"] == 1
    assert original["speed_mode"] == 31 and original["lane_change_mode"] == 512
    arrivals = original["arrivals"]
    assert len(trips) == len(arrivals) == result["requested"]
    planned = {x["vehicle_id"]: x for x in arrivals}
    assert len(planned) == len(trips)
    for trip in trips:
        for key in ("requested_s", "lane", "x", "speed"):
            assert trip[key] == planned[trip["vehicle_id"]][key]
    eligible = result["safe"] and result["all_completed"] and result["performance_comparison_eligible"]
    assert result["safe"] == (not result["collisions"] and not result["teleports"] and result["error"] is None)
    ident = dict(label=label, flow=record["flow"], seed=record["seed"], scenario=record["scenario"], mode=record["mode"])
    row = dict(**ident, case_dir=str(run), eligible=eligible, requested=len(trips), completed=result["completed"],
               safe=result["safe"], all_completed=result["all_completed"], collisions=result["collisions"], teleports=result["teleports"],
               input_sha256=sha(run / "input.json"), result_sha256=sha(run / "result.json"), trips_sha256=sha(run / "trips.json"),
               seal_sha256=sha(evidence / "seal.json"), positions_sha256=seal["originals"]["positions.jsonl.gz"]["sha256"],
               arrival_sha256=canonical(arrivals), physical_sha256=canonical({k: original[k] for k in
                  ("physical", "speed_mode", "lane_change_mode", "positions_step_s", "insertion")}),
               nonrule_sources_sha256=canonical({k: v for k,v in result["source_sha256"].items() if k != "noa/native_rules.py"}),
               source_files_n=len(result["source_sha256"]), rules_sha256=result["source_sha256"]["noa/native_rules.py"])
    if eligible:
        assert all(x["entered_s"] is not None and x["exited_s"] is not None for x in trips)
        assert result["completed"] == len(trips) and result["pending_final"] == result["onroad_final"] == result["not_yet_requested_final"] == 0
        metrics = dict(mean_system_time_s=mean(x["exited_s"]-x["requested_s"] for x in trips),
                       mean_travel_time_s=mean(x["exited_s"]-x["entered_s"] for x in trips),
                       mean_entry_wait_s=mean(x["entered_s"]-x["requested_s"] for x in trips),
                       fuel_g_per_km=sum(x["fuel_mg"] for x in trips)/sum(x["distance_m"] for x in trips))
        for key,value in metrics.items():
            close(value, result[key])
        close(metrics["mean_system_time_s"], metrics["mean_travel_time_s"]+metrics["mean_entry_wait_s"])
        row.update(metrics)
    row["midpoint_transitions_n"] = sum(len(x["lane_events"]) for x in trips)
    row["strict_completions_n"] = sum(len(x["lane_completion_events"]) for x in trips)
    assert row["midpoint_transitions_n"] == result["lane_changes"]
    assert row["strict_completions_n"] == result["lane_change_completions"]
    ledger = evidence / seal["traffic_metadata"]
    meta = read(ledger)
    with gzip.open(ledger.with_name("vehicles.json.gz"), "rt", encoding="utf-8") as stream:
        vehicles = json.load(stream)
    by_id = {x["vehicle_id"]: x for x in trips}
    assert len(vehicles) == len(trips)
    for vehicle in vehicles:
        trip = by_id[vehicle["vehicle_id"]]
        for key in ("requested_s", "entered_s", "exited_s"):
            assert trip[key] == vehicle[key]
    expected_queries, gate_times = defaultdict(list), defaultdict(dict)
    with gzip.open(ledger.with_name("gate_brackets.jsonl.gz"), "rt", encoding="utf-8") as stream:
        next(stream)
        for line in stream:
            i, gate, t0, x0, t1, x1 = json.loads(line)
            assert x0 < gate <= x1 and t0 < t1
            crossing = t0+(gate-x0)*(t1-t0)/(x1-x0)
            close(crossing, vehicles[i]["gates"][str(gate)]["time_s"])
            vehicle = vehicles[i]["vehicle_id"]
            gate_times[gate][vehicle] = crossing
            for t,x in ((t0,x0),(t1,x1)):
                expected_queries[round(t*10)].append((vehicle,x))
    ledger_integrals = dict(vehicle_s=0., low_speed_vehicle_s=0., speed_integral_m=0., observed_s=0.)
    with gzip.open(ledger.with_name("region_steps.jsonl.gz"), "rt", encoding="utf-8") as stream:
        next(stream)
        for line in stream:
            t0,t1,n,low,speed = json.loads(line)
            dt = max(0,min(600,t1)-max(100,t0))
            ledger_integrals["vehicle_s"] += n*dt
            ledger_integrals["low_speed_vehicle_s"] += low*dt
            ledger_integrals["speed_integral_m"] += speed*dt
            ledger_integrals["observed_s"] += dt
    close(ledger_integrals["observed_s"],500)
    raw_integrals = dict(vehicle_s=0., low_speed_vehicle_s=0., speed_integral_m=0.)
    checks, flags_n, frames, previous, old_time = 0, 0, 0, None, None
    if raw_check:
        with gzip.open(run / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                frame = json.loads(line)
                now, states = frame["time_s"], frame["states"]
                if old_time is not None:
                    assert 0 < now-old_time < .100001
                    dt = max(0,min(now,600)-max(old_time,100))
                    if dt:
                        selected = [s for s in previous.values() if 800 <= s[0] < 1000]
                        raw_integrals["vehicle_s"] += len(selected)*dt
                        raw_integrals["low_speed_vehicle_s"] += sum(s[2]<5 for s in selected)*dt
                        raw_integrals["speed_integral_m"] += sum(s[2] for s in selected)*dt
                for vehicle,x in expected_queries.pop(round(now*10),[]):
                    close(states[vehicle][0],x)
                    checks += 1
                for value in frame.get("formation_states",{}).values():
                    assert value in (0,1) and (label != "NOA" or value == 0)
                    flags_n += 1
                previous,old_time,frames = states,now,frames+1
        assert not expected_queries
        for key,value in raw_integrals.items():
            close(value,ledger_integrals[key],1e-6)
    for key in ("vehicle_s","low_speed_vehicle_s"):
        close(ledger_integrals[key],meta["run"]["region_window"][key],1e-6)
    row.update(region_window_vehicle_s=ledger_integrals["vehicle_s"], region_window_low_speed_vehicle_s=ledger_integrals["low_speed_vehicle_s"],
               region_window_mean_speed_mps=ledger_integrals["speed_integral_m"]/ledger_integrals["vehicle_s"],
               crossing800_window_n=sum(100 <= t < 600 for t in gate_times[800].values()),
               crossing1000_window_n=sum(100 <= t < 600 for t in gate_times[1000].values()),
               raw_frames=frames, raw_gate_bracket_endpoint_checks=checks, binary_formation_state_checks=flags_n,
               raw_region_ledger_max_absolute_error=max((abs(raw_integrals[k]-ledger_integrals[k]) for k in raw_integrals),default=0) if raw_check else None)
    return row


def run(primary, secondary, output, raw_check):
    manifests = [read(primary / "manifest.json"), read(secondary / "manifest.json")]
    assert [len(x) for x in manifests] == [60,30], "full matrix has not completed"
    expected = {(f,s,r,m) for f in (1500,1750,2000) for s in range(91,96) for r in ("straight3","lane_drop") for m in ("noa","transform")}
    assert {(x["flow"],x["seed"],x["scenario"],x["mode"]) for x in manifests[0]} == expected
    assert {(x["flow"],x["seed"],x["scenario"],x["mode"]) for x in manifests[1]} == {x for x in expected if x[3] == "transform"}
    records = [x for group in manifests for x in group]
    for record in records:
        assert read(Path(record["case_output"]) / "case_record.json").get("seal_status") == "verified", "full matrix not sealed"
    output.mkdir(parents=True,exist_ok=False)
    (output / "audit_final91_independent_source.py").write_bytes(Path(__file__).read_bytes())
    (output / "audit_raw_midflow.py").write_bytes(Path(__file__).with_name("audit_raw_midflow.py").read_bytes())
    preflight=[]
    for record in records:
        state=read(Path(record["case_output"])/"case_record.json")
        preflight.append({k:state.get(k) for k in ("candidate","flow","seed","scenario","mode","status","safe","all_completed","collisions","teleports","error","seal_status","case_output")})
    (output/"preflight_case_states.json").write_text(json.dumps(preflight,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    cases = []
    for record in records:
        label = "S" if record["candidate"] == "S" else "NOA" if record["mode"] == "noa" else "D1"
        try:
            cases.append(verify_case(Path(record["case_output"]),label,raw_check))
        except Exception as exc:
            failure=dict(case_output=record["case_output"],completed_audits=len(cases),planned_cases_n=90,
                         error_type=type(exc).__name__,error=str(exc),interpretation="Audit could not verify this original; no case or seed was replaced.")
            (output/"audit_failure.json").write_text(json.dumps(failure,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            raise
        print(json.dumps(dict(completed=len(cases),expected=90,label=label,flow=record["flow"],seed=record["seed"],scenario=record["scenario"])),flush=True)
    assert len({x["physical_sha256"] for x in cases}) == len({x["nonrule_sources_sha256"] for x in cases}) == 1
    indexed = {(x["label"],x["flow"],x["seed"],x["scenario"]): x for x in cases}
    assert len(indexed) == 90
    for flow in (1500,1750,2000):
        for seed in range(91,96):
            assert len({x["arrival_sha256"] for x in cases if x["flow"]==flow and x["seed"]==seed}) == 1
    pairs, did = [], []
    metrics = ("mean_system_time_s","mean_travel_time_s","mean_entry_wait_s","fuel_g_per_km")
    for reference in ("NOA","S"):
        for flow in (1500,1750,2000):
            for seed in range(91,96):
                roadpairs = {}
                for road in ("straight3","lane_drop"):
                    a,b = indexed[(reference,flow,seed,road)],indexed[("D1",flow,seed,road)]
                    row = dict(reference=reference,flow=flow,seed=seed,scenario=road,eligible=a["eligible"] and b["eligible"])
                    if row["eligible"]:
                        for key in metrics:
                            row.update({key+"_reference":a[key],key+"_candidate":b[key],key+"_delta":b[key]-a[key]})
                        row["system_improvement_percent"] = 100*(a[metrics[0]]-b[metrics[0]])/a[metrics[0]]
                    pairs.append(row)
                    roadpairs[road] = row
                d = dict(reference=reference,flow=flow,seed=seed,eligible=all(x["eligible"] for x in roadpairs.values()))
                if d["eligible"]:
                    d.update({key+"_did":roadpairs["lane_drop"][key+"_delta"]-roadpairs["straight3"][key+"_delta"] for key in metrics})
                did.append(d)
    assert len(pairs)==60 and len(did)==30
    write_csv(output / "per_case.csv",cases)
    write_csv(output / "paired_seeds.csv",pairs)
    write_csv(output / "road_did_seeds.csv",did)
    means = []
    for reference in ("NOA","S"):
        for flow in (1500,1750,2000):
            for road in ("straight3","lane_drop"):
                selected = [x for x in pairs if x["reference"]==reference and x["flow"]==flow and x["scenario"]==road]
                valid = [x for x in selected if x["eligible"]]
                out = dict(reference=reference,flow=flow,scenario=road,pairs_n=len(selected),eligible_n=len(valid))
                if valid:
                    for key in metrics:
                        out[key+"_delta_mean"] = mean(x[key+"_delta"] for x in valid)
                    out["system_improvement_percent_mean"] = mean(x["system_improvement_percent"] for x in valid)
                    out["system_faster_n"] = sum(x["mean_system_time_s_delta"] < 0 for x in valid)
                means.append(out)
    write_csv(output / "flow_means.csv",means)
    didmeans=[]
    for reference in ("NOA","S"):
        for flow in (1500,1750,2000):
            selected=[x for x in did if x["reference"]==reference and x["flow"]==flow]
            valid=[x for x in selected if x["eligible"]]
            out=dict(reference=reference,flow=flow,road_DID_n=len(selected),eligible_n=len(valid))
            if valid:
                out.update({key+"_did_mean":mean(x[key+"_did"] for x in valid) for key in metrics})
                out["extra_lane_drop_saving_n"]=sum(x["mean_system_time_s_did"]<0 for x in valid)
            didmeans.append(out)
    write_csv(output / "road_did_flow_means.csv",didmeans)
    summary = dict(cases_n=90,common_road_inputs_n=30,primary_pairs_n=30,secondary_pairs_n=30,primary_road_DID_n=15,secondary_road_DID_n=15,
                   primary_manifest_sha256=sha(primary/"manifest.json"),secondary_manifest_sha256=sha(secondary/"manifest.json"),
                   rules_sha256=dict(D1=D1,S=S),nonrule_sources_sha256=NONRULE,
                   eligible_cases_n=sum(x["eligible"] for x in cases),source_files_n=sorted({x["source_files_n"] for x in cases}),
                   raw_reconstructed=raw_check,raw_gate_endpoint_checks=sum(x["raw_gate_bracket_endpoint_checks"] for x in cases),
                   raw_region_ledger_max_error=max(x["raw_region_ledger_max_absolute_error"] for x in cases) if raw_check else None,
                   limitations=["Full-request system/travel/wait/fuel are reconstructed directly from original trips, not copied from official tables.",
                   "All case originals, snapshots, sealed compact index and ledger SHA are checked. Raw gate endpoints and fixed-window regional exposure are independently reconstructed when requested.",
                   "DID subtracts absolute time deltas across roads, never percentages. Five seeds are reported individually; no post-final tuning or global feedback.",
                   "Region [100,600) and crossing counts are mechanism evidence, not saturated capacity. Failures remain counted and ineligible, never replaced."])
    (output / "verification.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-batch",type=Path,required=True)
    parser.add_argument("--secondary-batch",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--skip-raw-reconstruction",action="store_true")
    args=parser.parse_args()
    run(args.primary_batch,args.secondary_batch,args.output,not args.skip_raw_reconstruction)
