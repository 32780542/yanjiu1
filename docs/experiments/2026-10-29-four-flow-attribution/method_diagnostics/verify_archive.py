"""Self-contained member/source verification, without tmp or metric execution."""
import ast
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parent


def sha(raw):return hashlib.sha256(raw).hexdigest()


def definitions(raw):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw.decode("utf-8")).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}


manifest_raw=(ROOT/"manifest.json").read_bytes()
manifest=json.loads(manifest_raw)
assert (ROOT/"manifest.sha256").read_text(encoding="ascii").split()[0]==sha(manifest_raw)
for name,item in manifest["sidecars"].items():
    raw=(ROOT/name).read_bytes()
    assert sha(raw)==item["sha256"] and len(raw)==item["bytes"],name
archive=(ROOT/manifest["archive"]).resolve()
assert archive.is_relative_to(ROOT)
assert sha(archive.read_bytes())==manifest["archive_sha256"]
assert archive.stat().st_size==manifest["archive_bytes"]
raw_members={}
with tarfile.open(archive,"r:gz") as tar:
    assert len(tar.getmembers())==len(manifest["members"])==manifest["member_count"]
    assert set(tar.getnames())==set(manifest["members"])
    for member in tar.getmembers():
        assert member.isfile() and not member.name.startswith("/") and ".." not in Path(member.name).parts
        assert "positions.json" not in member.name.lower() and not member.name.endswith(".csv")
        raw=tar.extractfile(member).read()
        expected=manifest["members"][member.name]
        assert len(raw)==member.size==expected["bytes"] and sha(raw)==expected["sha256"],member.name
        raw_members[member.name]=raw
versions=manifest["versions"]
assert versions==json.loads(raw_members["indices/versions.json"])
assert len(versions)==18
assert manifest["source_reference_count"]==108
core=("experiments/native_sumo.py","experiments/global_reference.py","experiments/complete_layers.py","noa/native_rules.py","run_native_flow.py","research/common.py")
for version in versions:
    assert set(version["source_files"])==set(core)
    for relative,item in version["source_files"].items():
        assert item["member"].startswith("blobs/")
        assert sha(raw_members[item["member"]])==item["sha256"]
        if item["declared_sha256"] is not None:
            assert (item["declared_sha256"]==item["sha256"]) == (relative not in version["declared_hash_mismatches"])
    for item in [*version["metadata_files"],*version["tests"],*version["configs"].values()]:
        assert sha(raw_members[item["member"]])==item["sha256"]
    if not version["package_summary_present"]:
        assert "evidence_gap" in version
by_name={v["version"]:v for v in versions}


def source(version,relative="noa/native_rules.py"):
    return raw_members[by_name[version]["source_files"][relative]["member"]]


p=source("common_pair_P_release")
calibration=source("P_common_pair")
h_equivalent=source("E11_actual_head_phase")
assert sha(p)=="8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864"
assert sha(calibration)=="d72154c245bddb572bc33aceb9e406b04484012a4e4cbbbe94705471fe15a69e"
assert sha(source("common_pair_P_release","experiments/native_sumo.py"))=="6a530098146e85a637b4f29d580d61877c7a54b3a7e15858724651d80e8956b0"
pd,cd,hd=definitions(p),definitions(calibration),definitions(h_equivalent)
assert sorted(k for k in pd.keys()|cd.keys() if pd.get(k)!=cd.get(k))==["_pair_error"]
assert sorted(k for k in pd.keys()|hd.keys() if pd.get(k)!=hd.get(k))==["_decide","_following","_pair_error"]
for name in ("Memory","Vehicle","_physical_phase","_phase","_request","_merge_target","_join_speed","_make_room","_fill","_receiving_distance","safe_speed","decide"):
    assert pd[name]==hd[name],name
tree=ast.parse(p.decode("utf-8"))
following=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_following")
assert not any(isinstance(n,ast.Name) and n.id in ("rear","slope","dpdx") for n in ast.walk(following))
for n in ast.walk(tree):
    if isinstance(n,ast.Attribute) and n.attr=="pending_lane":
        assert isinstance(n.value,ast.Name) and n.value.id=="ego"
code=p.decode("utf-8")
assert "max(car.lane, peer.lane) < 2" in code and "min(car.x, peer.x) >= phase_boundary" in code
assert "abs(c.x - car.x) <= 50.0" in code
review=json.loads((ROOT/"review.json").read_text(encoding="utf-8"))
assert review["source"]["rule_sha256"]==sha(p)
assert raw_members["package_provenance/review.json"]==(ROOT/"review.json").read_bytes()
assert review["pair_geometry"]["claim_limit"]
audit=json.loads(raw_members["aggregate_evidence/P_ending_lane_geometry_audit.json"])
assert audit["candidate_rule_sha256"]==sha(calibration) and audit["P_pair_lanes"]==2
assert audit["expected_three_lane_raw"]==15.0
release_freeze=json.loads(raw_members["versions/common_pair_P_release/freeze.json"])
assert release_freeze["source_sha256"]["noa/native_rules.py"]==sha(p)
assert release_freeze["scope_regression"]==dict(red_failures=2,green_passed=2)
assert "2 failed" in raw_members["versions/common_pair_P_release/scope_red.log"].decode("utf-8")
assert "2 passed" in raw_members["versions/common_pair_P_release/scope_green.log"].decode("utf-8")
six=json.loads(raw_members["versions/common_pair_P_release/six_verification.json"])
assert len(six)==2 and all(x["safe"] and x["completed"]==6 and x["source_ok"] and x["layers"]["peak_multilayer_size"]==6 for x in six)
references=json.loads(raw_members["indices/reported_R_G_case_protocol_hash_references.json"])["references"]
assert references and all(x["document_member"] in raw_members and isinstance(x["value"],str) and not x["dereferenced"] for x in references)
scope=json.loads(raw_members["indices/collection_scope.json"])
assert scope["allowed_candidate_directories"]==[v["version"] for v in versions]
assert not scope["results_scanned_recursively"] and not scope["positions_or_large_region_csv_copied"]
assert set(scope["allowed_aggregate_files"])=={"E_candidate_quality_review/summary.json","H_method_independent_review.json","P_ending_lane_geometry_audit.json"}
assert manifest["all_collected_original_files_byte_unchanged"] and manifest["no_simulation_or_metric_recalculation"]
assert manifest["no_recursive_results_scan"] and manifest["no_positions_or_large_region_csv"]
total=sum(path.stat().st_size for path in ROOT.iterdir() if path.is_file())
assert total<5*1024*1024
result=dict(passed=True,archive_sha256=manifest["archive_sha256"],archive_bytes=manifest["archive_bytes"],member_sha256_verified=manifest["member_count"],version_identities=len(versions),logical_core_sources=108,deduplicated_blob_count=manifest["deduplicated_blob_count"],reported_evidence_references=len(references),original_files_byte_unchanged_at_build=manifest["original_files_verified"],calibration_and_release_P_distinct=True,P_release_AST_scope_verified=True,P_scope_red_green_original_logs_retained=True,summaries_absent_not_fabricated=True,works_without_tmp=True,no_controller_execution=True,no_simulation=True,no_metric_recalculation=True,no_positions_or_large_region_csv=True,total_bundle_bytes=total)
(ROOT/"verification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result))
