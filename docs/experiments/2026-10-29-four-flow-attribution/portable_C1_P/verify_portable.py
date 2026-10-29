"""Independent portable C1 integrity, raw-evidence and paired-arithmetic checks."""
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean
import tarfile

BUNDLE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def close(a, b):
    if a is None or b is None:
        assert a is b, (a, b)
    else:
        assert abs(a - b) < 1e-8, (a, b)


def common(source, result):
    values = {k: source.get(k) for k in ("physical", "speed_mode", "lane_change_mode", "insertion", "positions_step_s")}
    values["case"] = {k: source["case"][k] for k in ("flow_veh_h_lane", "demand_duration_s", "max_time_s", "step_s", "lane_change_duration_s")}
    values["case"].update({k: source["case"].get(k) for k in ("request_acceleration_limit_mps2", "request_deceleration_limit_mps2")})
    values["sumo_version"] = result.get("sumo_version")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    manifest = read(BUNDLE / "bundle_hashes.json")
    for name, expected in manifest["files"].items():
        raw = (BUNDLE / name).read_bytes()
        assert digest(raw) == expected["sha256"] and len(raw) == expected["bytes"], name
    assert digest((BUNDLE / "bundle_hashes.json").read_bytes()) == (BUNDLE / "bundle_sha256.txt").read_text().split()[0]
    for row in read(BUNDLE / "provenance/copy_origins.json"):
        raw = (BUNDLE / row["bundle_path"]).read_bytes()
        assert digest(raw) == row["bundle_sha256"]
        decoded = gzip.decompress(raw) if row["gzip_wrapped"] else raw
        assert digest(decoded) == row["original_sha256"] and len(decoded) == row["original_bytes"]
    lossless = read(BUNDLE / "provenance/lossless_manifest.json")
    expected = {}
    for row in lossless:
        expected.setdefault(row["archive"], {})[row["member"]] = row
    archives = {}
    members_checked = 0
    for archive, names in expected.items():
        stored = {}
        with tarfile.open(BUNDLE / archive, "r|gz") as stream:
            for member in stream:
                raw = stream.extractfile(member).read()
                entry = names[member.name]
                assert digest(raw) == entry["original_sha256"] and len(raw) == entry["original_bytes"]
                stored[member.name] = raw
                members_checked += 1
        assert set(stored) == set(names)
        archives[archive] = stored
    freeze = read(BUNDLE / "provenance/freeze.json")
    parent = read(BUNDLE / "provenance/old_C1_H_freeze.json")
    for name, expected_sha in freeze["source_sha256"].items():
        assert digest((BUNDLE / "source/core" / name).read_bytes()) == expected_sha
    rules = (BUNDLE / "source/core/noa/native_rules.py").read_bytes()
    c0rules = (BUNDLE / "source/old_C1_H_reference/noa/native_rules.py").read_bytes()
    assert digest(c0rules) == parent["source_sha256"]["noa/native_rules.py"]
    p_bundle = (BUNDLE / "../portable_P").resolve()
    def definitions(code):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(code).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    cn,pn,on=definitions(rules.decode()),definitions((p_bundle/"source/noa/native_rules.py").read_text(encoding="utf-8")),definitions(c0rules.decode())
    assert sorted(n for n in cn.keys()|pn.keys() if cn.get(n)!=pn.get(n))==["_decide"]
    for name in ("_following","_pair_error","_fill"):assert cn[name]==pn[name]
    for name in ("_make_room","_receiving","_receiving_distance","_merge_target","_join_speed","_mandatory_priority","_clear","safe_speed","_occupies","Memory","Vehicle"):
        assert cn[name]==pn[name]==on[name]
    assert freeze["source_sha256"]["experiments/native_sumo.py"]==parent["source_sha256"]["experiments/native_sumo.py"]
    assert freeze["normal_overtake"] is False and freeze["group_following"] is False and freeze["layer_fill"] is False
    report = json.loads(gzip.decompress((BUNDLE / "data/analysis_summary.json.gz").read_bytes()))
    assert report["metadata"]["label"] == freeze["label"] == "C1_P strict formation ablation"
    assert report["audit"]["cases"] == report["audit"]["attribution_eligible"] == 20
    h_ref = read(BUNDLE / "provenance/P_portable_reference.json")
    h_bundle = (BUNDLE / h_ref["sibling_bundle"]).resolve()
    h_archive = h_bundle / "data/raw_case_json.tar.gz"
    assert digest(h_archive.read_bytes()) == h_ref["raw_archive_sha256"]
    h_inputs = {}
    h_trips = {}
    h_results = {}
    with tarfile.open(h_archive, "r|gz") as stream:
        for member in stream:
            if member.name.startswith("cases/") and "_lane_drop_transform/" in member.name:
                _, case_id, filename = member.name.split("/")
                value = json.loads(stream.extractfile(member).read())
                if filename == "input.json": h_inputs[case_id] = value
                elif filename == "trips.json": h_trips[case_id] = value
                elif filename == "result.json": h_results[case_id] = value
    h_attr_bytes = gzip.decompress((h_bundle / "data/attribution_summary.json.gz").read_bytes())
    assert digest(h_attr_bytes) == report["audit"]["P_attribution_summary_sha256"]
    hm = {(float(r["flow_veh_h_lane"]), int(r["seed"]), r["scenario"], r["mode"]): r for r in json.loads(h_attr_bytes)["runs"]}
    index = read(BUNDLE / "provenance/case_index.json")
    raw_cases = archives["data/raw_case_json.tar.gz"]
    requests = 0
    ordinary = 0
    checked = []
    for run in report["runs"]:
        flow, seed = float(run["flow_veh_h_lane"]), int(run["seed"])
        case = next(row for row in index if row["flow_veh_h_lane"] == flow and row["seed"] == seed)
        source = json.loads(raw_cases[case["members"]["input.json"]])
        result = json.loads(raw_cases[case["members"]["result.json"]])
        trips = json.loads(raw_cases[case["members"]["trips.json"]])
        evidence = json.loads(gzip.decompress((BUNDLE / f"data/case_evidence/flow{flow:g}_s{seed}.json.gz").read_bytes()))
        vehicles = evidence["attribution"]["vehicles"]
        ids = {a["vehicle_id"] for a in source["arrivals"]}
        assert len(ids) == len(vehicles) == len(trips) == run["requested"]
        assert ids == {a["vehicle_id"] for a in vehicles} == {a["vehicle_id"] for a in trips}
        assert source["case"]["mode"] == result["mode"] == "cooperative"
        assert source["source_sha256"] == result["source_sha256"] == freeze["source_sha256"]
        ordinary += result.get("action_reasons", {}).get("normal_overtake", 0)
        requests += len(ids)
        close(mean(t["exited_s"] - t["entered_s"] for t in trips), run["mean_travel_time_s"])
        close(sum(t["fuel_mg"] for t in trips) / sum(t["distance_m"] for t in trips), run["fuel_g_per_km"])
        close(mean(v["gates"]["1100"]["time_s"] - v["gates"]["640"]["time_s"] for v in vehicles), run["mean_segment_640_1100_s"])
        close(sum(100 <= v["gates"]["1000"]["time_s"] <= 600 for v in vehicles) * 7.2, run["flow_1000m_veh_h"])
        low = sum(max(0.0, min(s["end_s"], 600) - max(s["time_s"], 100)) * s["low_speed_n"] for s in evidence["attribution"]["region_steps"])
        close(low, run["region_low_speed_vehicle_s"])
        pair = next(p for p in report["pairs"] if p["flow_veh_h_lane"] == flow and p["seed"] == seed)
        h_id = f"f{flow:g}_s{seed}_lane_drop_transform"
        assert source["arrivals"] == h_inputs[h_id]["arrivals"]
        cp, hp = common(source, result), common(h_inputs[h_id], h_results[h_id])
        assert cp == hp
        assert digest(json.dumps(cp, sort_keys=True, separators=(",", ":")).encode()) == pair["cooperative_parameters_sha256"]
        assert digest(json.dumps(hp, sort_keys=True, separators=(",", ":")).encode()) == pair["P_parameters_sha256"]
        assert pair["cooperative_parameters_sha256"] == pair["P_parameters_sha256"]
        assert type(source["case"]["flow_veh_h_lane"]) is type(h_inputs[h_id]["case"]["flow_veh_h_lane"]) is float
        close(mean(t["exited_s"] - t["entered_s"] for t in h_trips[h_id]), pair["P_transform_mean_travel_time_s"])
        for name, value in pair.items():
            if name.startswith("cooperative_minus_P_"):
                metric = name[len("cooperative_minus_P_"):]
                cv, hv = pair["cooperative_" + metric], pair["P_transform_" + metric]
                close(value, cv - hv if cv is not None and hv is not None else None)
        ar = next(p for p in report["attributions"] if p["flow_veh_h_lane"] == flow and p["seed"] == seed)
        nd, ns, td, ts = (hm[(flow, seed, road, mode)] for road, mode in (("lane_drop", "noa"), ("straight3", "noa"), ("lane_drop", "transform"), ("straight3", "transform")))
        metric = "mean_segment_640_1100_s"
        close(ar["cooperative_reduction_" + metric], nd[metric] - run[metric])
        close(ar["P_reduction_" + metric], (nd[metric] - ns[metric]) - (td[metric] - ts[metric]))
        close(ar["P_incremental_reduction_over_cooperative_" + metric], ar["P_reduction_" + metric] - ar["cooperative_reduction_" + metric])
        checked.append(dict(flow=flow, seed=seed, requested=len(ids), raw_trip_gate_window_pair_checks=True))
    assert len(checked) == 20 and requests == 9612 and ordinary == 0
    assert {int(r["seed"]) for r in checked}=={6,7,8,9,10}
    for row in report["flow_means"]:
        selected = [p for p in report["pairs"] if p["flow_veh_h_lane"] == row["flow_veh_h_lane"]]
        assert len(selected) == 5 and row["group_eligible"]
        for name, value in row.items():
            if name.endswith("_mean") and name[:-5] in selected[0] and value is not None:
                close(value, mean(p[name[:-5]] for p in selected))
    recovery = json.loads(gzip.decompress((BUNDLE / "data/recovery_summary.json.gz").read_bytes()))
    assert len(recovery["runs"]) == 20
    outcome = dict(passed=True, label="C1_P strict formation ablation", primary_cases=20, requests=requests,
                   ordinary_overtake_actions=ordinary, source_core_changes_only_MODE_enum_and_decide=True,
                   raw_original_archive_members_checked=members_checked, payload_files_checked=len(manifest["files"]),
                   compressed_copy_origins_checked=len(read(BUNDLE / "provenance/copy_origins.json")),
                   exact_gzip_and_archive_bytes=True, original_parameter_forms_preserved=True,raw_parameter_hashes_equal=True,
                   P_pair_source_contrast_explicit=True, no_success_only_means=True,
                   inherited_C1_H_C0_straight_evidence=True, old_seed_cases_reused=False, checks=checked)
    if args.write:
        (BUNDLE / "independent_verification.json").write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in outcome.items() if k != "checks"}, indent=2))


if __name__ == "__main__":
    main()
