"""Archive-only C1 strict ablation bundle; C0/H/D/main sources remain read-only."""
import gzip
import ast
import difflib
import hashlib
import io
import json
from pathlib import Path
import tarfile

BUNDLE = Path(__file__).resolve().parent
ROOT = BUNDLE.parents[3]
C0 = ROOT / "tmp/common_pair_P_strict_ablation"
C0_PARENT = ROOT / "tmp/H_strict_formation_ablation"
ANALYSIS = C0 / "analysis"
STUDY = C0 / "results/20261029T034544698651Z"
H = ROOT / "tmp/common_pair_P_release"
P_PORTABLE = BUNDLE.parent / "portable_P"
ORIGINS = []
LOSSLESS = []


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def destination(relative):
    path = (BUNDLE / relative).resolve()
    assert path.is_relative_to(BUNDLE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json(relative, value):
    path = destination(relative)
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def copy(source, relative, compress=False):
    source = Path(source)
    raw = source.read_bytes()
    path = destination(relative)
    assert not path.exists(), path
    packed = gzip.compress(raw, mtime=0) if compress else raw
    path.write_bytes(packed)
    ORIGINS.append(dict(source_path=str(source), bundle_path=relative, gzip_wrapped=compress, original_sha256=digest(raw), original_bytes=len(raw), bundle_sha256=digest(packed)))
    return relative


def archive(relative, members):
    path = destination(relative)
    assert not path.exists(), path
    with path.open("wb") as outer:
        with gzip.GzipFile(filename="", mode="wb", fileobj=outer, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as tar:
                for member, source in members:
                    raw = Path(source).read_bytes()
                    info = tarfile.TarInfo(member)
                    info.size, info.mtime, info.mode, info.uid, info.gid = len(raw), 0, 0o644, 0, 0
                    tar.addfile(info, io.BytesIO(raw))
                    LOSSLESS.append(dict(archive=relative, member=member, original_path=str(source), original_sha256=digest(raw), original_bytes=len(raw)))


def common(source, result):
    result_dict = {k:source.get(k) for k in ("physical","speed_mode","lane_change_mode","insertion","positions_step_s")}
    case=source["case"]
    result_dict["case"]={k:case[k] for k in ("flow_veh_h_lane","demand_duration_s","max_time_s","step_s","lane_change_duration_s")}
    result_dict["case"].update({k:case.get(k) for k in ("request_acceleration_limit_mps2","request_deceleration_limit_mps2")})
    result_dict["sumo_version"]=result.get("sumo_version")
    return result_dict


def parameter_sha(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


assert not (BUNDLE/"data").exists(), "Never overwrite a portable attempt"
report, post, freeze = read(ANALYSIS/"summary.json"), read(ANALYSIS/"postverification.json"), read(C0/"freeze.json")
assert post["passed"] and post["cases_checked"]==20 and post["requested"]==report["audit"]["requested"]==9612
assert report["metadata"]["label"] == freeze["label"] == "C1_P strict formation ablation"
assert post["ordinary_overtake_actions"] == 0
assert set(report["metadata"]["seeds"])=={6,7,8,9,10} and post["raw_parameter_sha256_equal"]
assert report["audit"]["cases"]==20 and report["audit"]["attribution_eligible"]==20
for name, expected in freeze["source_sha256"].items():
    assert sha(C0/name)==expected
for name, expected in freeze["P_source_sha256"].items():
    assert sha(H/name)==expected
for name, expected in read(ANALYSIS/"artifact_hashes.json").items():
    assert sha(ANALYSIS/name)==expected
core = {}
for name, expected in freeze["source_sha256"].items():
    core[name]=dict(path=copy(C0/name,"source/core/"+name),sha256=expected)
base = read(C0/"base_manifest.json")
for name, expected in base["configs_sha256"].items():
    assert sha(C0/name)==expected
    copy(C0/name,"source/"+name.replace("\\","/"))
eval_freeze = read(C0/"analysis_source/freeze.json")
for name, expected in eval_freeze["source_sha256"].items():
    assert sha(C0/"analysis_source"/name)==expected
    copy(C0/"analysis_source"/name,"source/evaluators/"+name)
for name in eval_freeze["changed_source_files"]:
    original=Path(eval_freeze["parent"])/name
    assert sha(original)==eval_freeze["parent_source_sha256"][name]
    copy(original,"source/evaluator_parent/"+name)
copy(C0/"analysis_source/freeze.json","provenance/evaluator_freeze.json")
copy(C0/"analysis_source/enum_label_only.patch","source/evaluator_enum_label_only.patch")
for name in ("run_flow_study.py","test_C1_P_rules.py","freeze_C1_P.py"):
    copy(C0/name,"source/experiment_scripts/"+name)
for name in ("verify_straight_equivalence.py", "prepare_analysis_source.py"):
    copy(ROOT/"tmp/H_cooperative_ablation"/name,"source/inherited_C0_scripts/"+name)
copy(ANALYSIS/"analyze_cooperative.source.py","source/analysis_scripts/analyze_C1_P.py")
copy(C0/"postverify_analysis.py","source/analysis_scripts/postverify_analysis.py")
for name in ("freeze.json","base_manifest.json","straight_equivalence_report.json", "straight_equivalence_inheritance.json", "analysis_freeze.json"):
    copy(C0/name,"provenance/"+name)
patch=[]
for name in freeze["P_source_sha256"]:
    old,new=(H/name).read_text(encoding="utf-8"),(C0/name).read_text(encoding="utf-8")
    if old!=new:patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile="P/"+name,tofile="C1_P/"+name))
destination("source/C1_P_vs_P.patch").write_text("".join(patch),encoding="utf-8")
copy(C0_PARENT/"noa/native_rules.py","source/old_C1_H_reference/noa/native_rules.py")
copy(C0_PARENT/"freeze.json","provenance/old_C1_H_freeze.json")
copy(H/"freeze.json","provenance/P_release_freeze.json")
copy(ROOT/"tmp/prepare_C1_P_source.py","source/experiment_scripts/prepare_C1_P_source.py")
for name in ("protocol.json","manifest.json","run_status.json","run_flow_study.py",*(f"flow_{flow}_manifest.json" for flow in (500,750,1000,1500))):
    copy(STUDY/name,"provenance/study/"+name)
for name in ("analysis_status.json","artifact_hashes.json","postverification.json"):
    copy(ANALYSIS/name,"provenance/analysis_v2/"+name)
for name in ("runs.csv","pairs.csv","attributions.csv","flow_means.csv"):
    copy(ANALYSIS/name,"tables/"+name)
copy(ANALYSIS/"summary.json","data/analysis_summary.json.gz",compress=True)
for name in ("summary.json", "runs.csv", "per_vehicle.csv"):
    copy(ANALYSIS/"recovery"/name,"data/recovery_"+name+".gz",compress=True)
for path in sorted((ANALYSIS/"case_evidence").glob("*.json.gz")):
    copy(path,"data/case_evidence/"+path.name)

case_index, parameter_audit, trace_index, members = [], [], [], []
for run in sorted(report["runs"],key=lambda x:(x["flow_veh_h_lane"],x["seed"])):
    case=Path(run["case_dir"])
    flow,seed=run["flow_veh_h_lane"],run["seed"]
    label=f"f{flow:g}_s{seed}_lane_drop_cooperative"
    source,result=read(case/"input.json"),read(case/"result.json")
    assert source["case"]["mode"]==result["mode"]=="cooperative"
    assert source["source_sha256"]==freeze["source_sha256"]==result["source_sha256"]
    for name, expected in freeze["source_sha256"].items():
        assert sha(case/"source"/name)==expected
    files={name:f"cases/{label}/{name}" for name in ("input.json","result.json","trips.json")}
    for name,member in files.items():
        members.append((member,case/name))
    pair=next(x for x in report["pairs"] if x["flow_veh_h_lane"]==flow and x["seed"]==seed)
    h_case=Path(pair["P_transform_case_dir"])
    hs,hr=read(h_case/"input.json"),read(h_case/"result.json")
    cp,hp=common(source,result),common(hs,hr)
    assert cp==hp
    assert parameter_sha(cp)==pair["cooperative_parameters_sha256"]
    assert parameter_sha(hp)==pair["P_parameters_sha256"]
    assert pair["cooperative_parameters_sha256"]==pair["P_parameters_sha256"]
    parameter_audit.append(dict(flow_veh_h_lane=flow,seed=seed,cooperative_parameters=cp,P_parameters=hp,cooperative_parameters_sha256=pair["cooperative_parameters_sha256"],P_parameters_sha256=pair["P_parameters_sha256"],numeric_values_equal=True,original_hashes_equal=True,numeric_representation_difference_only=None,cooperative_input_sha256=sha(case/"input.json"),P_input_sha256=sha(h_case/"input.json"),P_portable_input_member=f"cases/f{flow:g}_s{seed}_lane_drop_transform/input.json"))
    case_index.append(dict(label=label,original_case_dir=str(case),flow_veh_h_lane=flow,seed=seed,mode="cooperative",scenario="lane_drop",source_sha256=source["source_sha256"],archive="data/raw_case_json.tar.gz",members=files,requested=result["requested"],completed=result["completed"],status=result["status"],safe=result["safe"],all_completed=result["all_completed"],cooperative_source_version_sha256=pair["cooperative_source_version_sha256"],P_source_version_sha256=pair["P_source_version_sha256"],cooperative_parameters_sha256=pair["cooperative_parameters_sha256"],P_parameters_sha256=pair["P_parameters_sha256"],input_sha256=sha(case/"input.json"),result_sha256=sha(case/"result.json"),trips_sha256=sha(case/"trips.json")))
    trace=case/"positions.jsonl.gz"
    assert sha(trace)==run["positions_sha256"]
    trace_index.append(dict(label=label,original_path=str(trace),compressed_sha256=run["positions_sha256"],bytes=trace.stat().st_size,copied_to_bundle=False,reason="Original large .1s positions remain local; existing metric evidence retained separately"))
archive("data/raw_case_json.tar.gz",members)
assert len(members)==60

short_members, short_cases = [], []
equivalence=read(C0/"straight_equivalence_report.json")
assert equivalence["reuse_H_noa_straight"] and len(equivalence["rows"])==2
for row in equivalence["rows"]:
    for policy,field in (("cooperative","cooperative_case"),("H_noa","H_noa_case")):
        case=Path(row[field]);label=f"q{row['flow']:g}_{policy}_straight10s"
        data=read(case/"input.json");result=read(case/"result.json")
        actual_mode="cooperative" if policy=="cooperative" else "noa"
        assert data["case"]["mode"]==result["mode"]==actual_mode
        files={name:f"short/{label}/{name}" for name in ("input.json","result.json","trips.json","native.rou.xml")}
        short_members.extend((member,case/name) for name,member in files.items())
        short_cases.append(dict(label=label,flow=row["flow"],seed=1,mode=actual_mode,original_case_dir=str(case),archive="data/short_straight_raw.tar.gz",members=files))
        trace=case/"positions.jsonl.gz"
        uncompressed=hashlib.sha256()
        with gzip.open(trace,"rb") as stream:
            for chunk in iter(lambda:stream.read(1<<20),b""):
                uncompressed.update(chunk)
        expected=row["comparisons"]["positions.jsonl.gz"]["cooperative_sha256" if policy=="cooperative" else "H_noa_sha256"]
        assert uncompressed.hexdigest()==expected
        trace_index.append(dict(label=label,original_path=str(trace),compressed_sha256=sha(trace),decompressed_sha256=expected,bytes=trace.stat().st_size,copied_to_bundle=False,reason="Strict equality digests and original short-run JSON/routes retained, no duplicate positions"))
archive("data/short_straight_raw.tar.gz",short_members)
assert len(short_members)==16

operations={
    "static_red_expected":"20261029T034234279474Z_C1_P-static-red_8fdf1985",
    "static_green":"20261029T034309864908Z_C1_P-static-green_fe0820d5",
    "C1_P_source_freeze":"20261029T034543115460Z_C1_P-source-freeze_b9a38a0c",
    "twenty_drop_batch":"20261029T034544274513Z_C1_P-heldout-twenty-drop_3fd04f54",
    "guarded_analysis_and_postverify":"20261029T035246835677Z_C1_P-guarded-P-paired-analysis_c062564a",
    "portable_build_v1_failed":"20261029T041905151466Z_portable-C1_P-lossless-build_0b5cae1a",
}
attempts=[]
for label,folder in operations.items():
    operation=ROOT/"results/operations"/folder
    result=read(operation/"result.json")
    for name in ("result.json","started.json","runner_snapshot.py","stdout.log","stderr.log"):
        if (operation/name).is_file():
            copy(operation/name,"provenance/operations/"+label+"/"+name+(".gz" if name.endswith(".log") else ""),compress=name.endswith(".log"))
    attempts.append(dict(label=label,original_operation=str(operation),status=result["status"],returncode=result["returncode"],result_path="provenance/operations/"+label+"/result.json"))
write_json("provenance/attempts_index.json",dict(attempts=attempts,seeds=[6,7,8,9,10],
    old_seed_cases_reused=False,formal_attempts=1,
    common_parameters="P and C1_P explicit float flows: original parameter SHA exactly equal; no numeric-type exception or normalization."))
write_json("provenance/core_source_index.json",core)
write_json("provenance/case_index.json",case_index)
write_json("provenance/short_case_index.json",short_cases)
write_json("provenance/lossless_manifest.json",LOSSLESS)
write_json("provenance/common_parameter_audit.json",parameter_audit)
write_json("provenance/trace_index.json",trace_index)
write_json("provenance/pair_audit.json",dict(metadata=report["metadata"],audit=report["audit"],pairs=report["pairs"],raw_policy_source_versions_kept_distinct=True,metric_recalculation_performed_during_packaging=False))
h_archive=P_PORTABLE/"data/raw_case_json.tar.gz"
write_json("provenance/P_portable_reference.json",dict(sibling_bundle="../portable_P",raw_case_json_archive="../portable_P/data/raw_case_json.tar.gz",raw_archive_sha256=sha(h_archive),P_input_members=[x["P_portable_input_member"] for x in parameter_audit],P_source_sha256=freeze["P_source_sha256"],note="Only heldout P seed6–10 comparator data are referenced; no old H/C1_H outcomes are pooled."))
write_json("provenance/copy_origins.json",ORIGINS)
excluded=["bundle_hashes.json","bundle_sha256.txt","verification.json","independent_verification.json"]
files={str(path.relative_to(BUNDLE)).replace("\\","/"):dict(sha256=sha(path),bytes=path.stat().st_size) for path in sorted(BUNDLE.rglob("*")) if path.is_file() and str(path.relative_to(BUNDLE)).replace("\\","/") not in excluded}
write_json("bundle_hashes.json",dict(algorithm="SHA256",excluded_outputs=excluded,files=files))
manifest_sha=sha(BUNDLE/"bundle_hashes.json")
destination("bundle_sha256.txt").write_text(manifest_sha+"  bundle_hashes.json\n",encoding="ascii")
write_json("verification.json",dict(build_copy_checks_passed=True,primary_cases=len(case_index),primary_original_json_members=60,short_cases=len(short_cases),short_original_members=16,requests=9612,core_source_files=len(core),retained_case_evidence_files=20,copied_positions_files=0,bundle_manifest_sha256=manifest_sha,payload_files=len(files),payload_bytes=sum(x["bytes"] for x in files.values()),raw_numeric_forms_preserved=True,raw_parameter_hashes_equal=True,metrics_recomputed=False,source_tmp_read_only=True,P_main_Git_untouched=True,seeds=[6,7,8,9,10]))
print(json.dumps(dict(bundle=str(BUNDLE),primary_cases=20,primary_raw_json=60,short_cases=4,payload_files=len(files),payload_bytes=sum(x["bytes"] for x in files.values()),bundle_manifest_sha256=manifest_sha)))
