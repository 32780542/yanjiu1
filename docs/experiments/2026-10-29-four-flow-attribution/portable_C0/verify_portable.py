"""Independent archive/hash/binding verification; no SUMO or metric evaluation."""
import argparse
import ast
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parameter_digest(value):
    return digest(json.dumps(value,sort_keys=True,separators=(",",":")).encode())


def common(source,result):
    p={k:source.get(k) for k in ("physical","speed_mode","lane_change_mode","insertion","positions_step_s")}
    p["case"]={k:source["case"][k] for k in ("flow_veh_h_lane","demand_duration_s","max_time_s","step_s","lane_change_duration_s")}
    p["case"].update({k:source["case"].get(k) for k in ("request_acceleration_limit_mps2","request_deceleration_limit_mps2")})
    p["sumo_version"]=result.get("sumo_version")
    return p


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output",default="independent_verification.json")
args=parser.parse_args()
output=(ROOT/args.output).resolve()
assert output.is_relative_to(ROOT) and output.name in ("verification.json","independent_verification.json")
manifest_raw=(ROOT/"bundle_hashes.json").read_bytes()
manifest=json.loads(manifest_raw)
manifest_sha=digest(manifest_raw)
assert (ROOT/"bundle_sha256.txt").read_text(encoding="ascii").split()[0]==manifest_sha
actual={str(p.relative_to(ROOT)).replace("\\","/") for p in ROOT.rglob("*") if p.is_file() and str(p.relative_to(ROOT)).replace("\\","/") not in manifest["excluded_outputs"]}
assert actual==set(manifest["files"]),actual^set(manifest["files"])
for name,entry in manifest["files"].items():
    path=(ROOT/name).resolve()
    assert path.is_relative_to(ROOT)
    raw=path.read_bytes()
    assert len(raw)==entry["bytes"] and digest(raw)==entry["sha256"],name
assert not any(Path(name).name.startswith("positions.") for name in actual)
origins=read(ROOT/"provenance/copy_origins.json")
for item in origins:
    raw=(ROOT/item["bundle_path"]).read_bytes()
    assert digest(raw)==item["bundle_sha256"]
    original=gzip.decompress(raw) if item["gzip_wrapped"] else raw
    assert len(original)==item["original_bytes"] and digest(original)==item["original_sha256"]
lossless=read(ROOT/"provenance/lossless_manifest.json")
archive_names={x["archive"] for x in lossless}
members={}
for archive_name in archive_names:
    expected={x["member"]:x for x in lossless if x["archive"]==archive_name}
    with tarfile.open(ROOT/archive_name,"r:gz") as tar:
        assert len(tar.getmembers())==len(expected)
        assert set(tar.getnames())==set(expected)
        for member in tar.getmembers():
            assert member.isfile() and not member.name.startswith("/") and ".." not in Path(member.name).parts
            raw=tar.extractfile(member).read()
            entry=expected[member.name]
            assert len(raw)==entry["original_bytes"] and digest(raw)==entry["original_sha256"]
            members[(archive_name,member.name)]=raw
primary=[x for x in lossless if x["archive"]=="data/raw_case_json.tar.gz"]
short=[x for x in lossless if x["archive"]=="data/short_straight_raw.tar.gz"]
assert len(primary)==60 and all(x["member"].endswith(".json") for x in primary)
assert len(short)==16
freeze=read(ROOT/"provenance/freeze.json")
core=read(ROOT/"provenance/core_source_index.json")
assert len(core)==6 and set(core)==set(freeze["source_sha256"])
assert len(list((ROOT/"source/core").rglob("*.py")))==6
for name,item in core.items():
    assert digest((ROOT/item["path"]).read_bytes())==item["sha256"]==freeze["source_sha256"][name]
base=read(ROOT/"provenance/base_manifest.json")
for name,sha in base["configs_sha256"].items():
    assert digest((ROOT/"source"/name.replace("\\","/")).read_bytes())==sha
cases=read(ROOT/"provenance/case_index.json")
params=read(ROOT/"provenance/common_parameter_audit.json")
assert len(cases)==len(params)==20
expected={(flow,seed) for flow in (500,750,1000,1500) for seed in range(1,6)}
assert {(c["flow_veh_h_lane"],c["seed"]) for c in cases}==expected
total=0
for case in cases:
    archive=case["archive"]
    raw={name:members[(archive,member)] for name,member in case["members"].items()}
    source,result,trips=(json.loads(raw[name]) for name in ("input.json","result.json","trips.json"))
    assert source["case"]["mode"]==result["mode"]==case["mode"]=="cooperative"
    assert source["case"]["scenario"]=="lane_drop" and source["case"]["demand_duration_s"]==600 and source["case"]["max_time_s"]==900
    assert source["source_sha256"]==result["source_sha256"]==freeze["source_sha256"]
    assert result["safe"] and result["all_completed"] and result["status"]=="drained"
    assert len(source["arrivals"])==len(trips)==result["requested"]==result["completed"]
    assert {r["vehicle_id"] for r in source["arrivals"]}=={t["vehicle_id"] for t in trips}
    assert all(t["entered_s"] is not None and t["exited_s"] is not None for t in trips)
    total+=len(trips)
    for name in ("input.json","result.json","trips.json"):
        assert digest(raw[name])==case[name[:-5]+"_sha256"]
    item=next(p for p in params if p["flow_veh_h_lane"]==case["flow_veh_h_lane"] and p["seed"]==case["seed"])
    actual_parameters=common(source,result)
    assert json.dumps(actual_parameters,sort_keys=True)==json.dumps(item["cooperative_parameters"],sort_keys=True)
    assert parameter_digest(item["cooperative_parameters"])==item["cooperative_parameters_sha256"]==case["cooperative_parameters_sha256"]
    assert parameter_digest(item["H_parameters"])==item["H_parameters_sha256"]==case["H_parameters_sha256"]
    assert item["cooperative_parameters"]==item["H_parameters"]
    assert isinstance(item["cooperative_parameters"]["case"]["flow_veh_h_lane"],float)
    assert type(item["H_parameters"]["case"]["flow_veh_h_lane"]) is int
    assert item["cooperative_parameters_sha256"]!=item["H_parameters_sha256"]
assert total==9158
summary=json.loads(gzip.decompress((ROOT/"data/analysis_summary.json.gz").read_bytes()))
pairaudit=read(ROOT/"provenance/pair_audit.json")
assert summary["pairs"]==pairaudit["pairs"]
assert summary["audit"]["cases"]==20 and summary["audit"]["attribution_eligible"]==20
assert len(summary["pairs"])==len(summary["attributions"])==20 and len(summary["flow_means"])==4
for name,count in (("runs",20),("pairs",20),("attributions",20),("flow_means",4)):
    with (ROOT/"tables"/(name+".csv")).open(encoding="utf-8-sig",newline="") as stream:
        assert len(list(csv.DictReader(stream)))==count
evidence=list((ROOT/"data/case_evidence").glob("*.json.gz"))
assert len(evidence)==20
for path in evidence:
    saved=json.loads(gzip.decompress(path.read_bytes()))
    assert saved["attribution"]["attribution_eligible"]
    assert saved["attribution"]["mode"]=="cooperative"
post=read(ROOT/"provenance/analysis_v2/postverification.json")
assert post["passed"] and post["cases_checked"]==20 and post["requested"]==9158
failed=read(ROOT/"provenance/operations/analysis_v1_failed/result.json")
assert failed["status"]=="failed" and failed["returncode"]==1
stderr=gzip.decompress((ROOT/"provenance/operations/analysis_v1_failed/stderr.log.gz").read_bytes()).decode("utf-8")
assert "AssertionError" in stderr and 'parameters_sha256' in stderr
attempts=read(ROOT/"provenance/attempts_index.json")
assert attempts["failed_v1_preserved"]
ef=read(ROOT/"provenance/evaluator_freeze.json")
for name,sha in ef["source_sha256"].items():
    assert digest((ROOT/"source/evaluators"/name).read_bytes())==sha
for name in ef["changed_source_files"]:
    before=(ROOT/"source/evaluator_parent"/name).read_text(encoding="utf-8")
    after=(ROOT/"source/evaluators"/name).read_text(encoding="utf-8")
    assert digest(before.encode())==ef["parent_source_sha256"][name]
    def funcs(code):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(code).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    assert funcs(before)==funcs(after),name
short_cases=read(ROOT/"provenance/short_case_index.json")
equivalence=read(ROOT/"provenance/straight_equivalence_report.json")
assert len(short_cases)==4 and equivalence["reuse_H_noa_straight"]
for row in equivalence["rows"]:
    cc=next(c for c in short_cases if c["flow"]==row["flow"] and c["mode"]=="cooperative")
    nn=next(c for c in short_cases if c["flow"]==row["flow"] and c["mode"]=="noa")
    for name in ("trips.json","native.rou.xml"):
        cr=members[(cc["archive"],cc["members"][name])]
        nr=members[(nn["archive"],nn["members"][name])]
        assert cr==nr
        assert digest(cr)==row["comparisons"][name]["cooperative_sha256"]==row["comparisons"][name]["H_noa_sha256"]
    for case in (cc,nn):
        ci=json.loads(members[(case["archive"],case["members"]["input.json"])])
        cr=json.loads(members[(case["archive"],case["members"]["result.json"])])
        assert ci["case"]["mode"]==cr["mode"]==case["mode"]
traces=read(ROOT/"provenance/trace_index.json")
assert len(traces)==24 and all(not t["copied_to_bundle"] for t in traces)
h_reference=read(ROOT/"provenance/H_portable_reference.json")
h_archive=(ROOT/h_reference["raw_case_json_archive"]).resolve()
h_checked=0
if h_archive.is_file():
    assert digest(h_archive.read_bytes())==h_reference["raw_archive_sha256"]
    with tarfile.open(h_archive,"r:gz") as tar:
        for item in params:
            raw=tar.extractfile(item["H_portable_input_member"]).read()
            assert digest(raw)==item["H_input_sha256"]
            source=json.loads(raw)
            for name in ("physical","speed_mode","lane_change_mode","insertion","positions_step_s"):
                assert source.get(name)==item["H_parameters"][name]
            assert type(source["case"]["flow_veh_h_lane"]) is int
            assert source["case"]["flow_veh_h_lane"]==item["H_parameters"]["case"]["flow_veh_h_lane"]
            h_checked+=1
review=read(ROOT/"provenance/H_method_independent_review.json")
assert review["verified_source"]["noa/native_rules.py"]==read(ROOT/"provenance/H_release_freeze.json")["source_sha256"]["noa/native_rules.py"]
result=dict(passed=True,bundle_manifest_sha256=manifest_sha,payload_files_verified=len(manifest["files"]),payload_bytes=sum(x["bytes"] for x in manifest["files"].values()),primary_cases=20,primary_raw_json_members=60,short_cases=4,short_raw_members=16,requests_preserved=total,core_source_files=6,case_evidence_files=20,trace_index_entries=24,positions_files_copied=0,failed_analysis_v1_preserved=True,original_parameter_hashes_preserved_and_distinct=True,original_flow_int_float_forms_preserved=True,common_parameter_numeric_values_equal=True,H_control_raw_inputs_crosschecked=h_checked,original_H_method_review_retained=True,metric_recalculation_performed=False,simulation_performed=False,source_tmp_read_only=True)
output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result))
