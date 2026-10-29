"""Bounded, read-only collection of explicitly named diagnostic candidates."""
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[3]
TMP=PROJECT/"tmp"
PACKAGES=(
    "E1_full_gain","E2_full_gain_safe_gap","E2_cruise_cap_ablation",
    "E3_balanced_phase_safe_gap","E3_balanced_lane_phase","E3_own_execution_feedback",
    "E5_balanced_phase_execution","E6_neighbor_velocity","E7_symmetric_velocity",
    "E8_front_chain","E9_local_pair_phase","E10_bounded_group","E11_actual_head_phase",
    "J_spatial_phase","K_spatial_velocity","N_common_pair_head","P_common_pair",
    "common_pair_P_release",
)
CORE=("experiments/native_sumo.py","experiments/global_reference.py","experiments/complete_layers.py","noa/native_rules.py","run_native_flow.py","research/common.py")
EXTRAS=("E_candidate_quality_review/summary.json","H_method_independent_review.json","P_ending_lane_geometry_audit.json")
MAX_METADATA=2*1024*1024
members={}
origins={}
versions=[]
references=[]
skipped=[]


def sha(raw):return hashlib.sha256(raw).hexdigest()


def add_bytes(name,raw,category,original=None):
    assert not name.startswith("/") and ".." not in Path(name).parts
    if name in members:
        assert members[name]["raw"]==raw
    else:
        members[name]=dict(raw=raw,category=category,original_paths=[])
    if original is not None:
        path=str(Path(original).resolve())
        members[name]["original_paths"].append(path)
        if path in origins:assert origins[path]==sha(raw)
        origins[path]=sha(raw)
    return dict(member=name,sha256=sha(raw),bytes=len(raw))


def add_file(path,name,category,blob=False):
    raw=Path(path).read_bytes()
    return add_bytes("blobs/"+sha(raw) if blob else name,raw,category,path)


def generated(name,value):
    return add_bytes(name,(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode(),"generated index")


def walk(value,document,path="$"):
    if isinstance(value,dict):
        for key,item in value.items():walk(item,document,path+"."+str(key))
    elif isinstance(value,list):
        for index,item in enumerate(value):walk(item,document,path+f"[{index}]")
    elif isinstance(value,str):
        low=path.lower()
        if any(k in low for k in ("red","green","tdd","operation","log","case_dir","run_dir","manifest","protocol","sha256")) or "results/" in value.replace("\\","/"):
            references.append(dict(document_member=document,json_path=path,value=value,dereferenced=False))


assert not (OUT/"method_diagnostics.tar.gz").exists(),"Do not overwrite an existing archive"
for name in PACKAGES:
    base=TMP/name
    row=dict(version=name,original_directory=str(base),source_files={},metadata_files=[],tests=[],configs={},missing=[],declared_freeze_present=False,declared_hash_mismatches=[],no_recursive_results_scan=True)
    if not base.is_dir():
        row["missing"].append("candidate directory")
        versions.append(row)
        continue
    declared={}
    for candidate in ("freeze.json","candidate_manifest.json"):
        if (base/candidate).is_file():
            payload=json.loads((base/candidate).read_text(encoding="utf-8"))
            if isinstance(payload.get("source_sha256"),dict):
                declared=payload["source_sha256"]
                row["declared_freeze_present"]=True
                row["declared_freeze_file"]=candidate
                break
    for relative in CORE:
        path=base/relative
        if not path.is_file():
            row["missing"].append(relative)
            continue
        item=add_file(path,"",name+" core source",blob=True)
        item["original_path"]=str(path)
        item["declared_sha256"]=declared.get(relative)
        row["source_files"][relative]=item
        if relative in declared and declared[relative]!=item["sha256"]:
            row["declared_hash_mismatches"].append(relative)
    for path in sorted(base.iterdir()):
        if not path.is_file() or path.name=="run_native_flow.py" or path.suffix.lower() not in (".json",".py",".log",".diff",".patch",".md",".txt"):
            continue
        if path.stat().st_size>MAX_METADATA:
            raw=path.read_bytes();origins[str(path.resolve())]=sha(raw)
            skipped.append(dict(path=str(path),bytes=len(raw),sha256=sha(raw),reason="Metadata size exceeds fixed2MiB cap; no raw trace/large table collection"))
            continue
        item=add_file(path,f"versions/{name}/{path.name}",name+" metadata or source script")
        row["metadata_files"].append(item)
        if path.suffix==".json":
            walk(json.loads(path.read_text(encoding="utf-8")),item["member"])
    configs=base/"configs"
    if configs.is_dir():
        for path in sorted(configs.iterdir()):
            if path.is_file() and path.suffix==".json":
                row["configs"][path.name]=add_file(path,"",name+" config",blob=True)
    tests=base/"tests"
    if tests.is_dir():
        for path in sorted(tests.iterdir()):
            if path.is_file() and path.suffix in (".py",".json",".log") and path.stat().st_size<=MAX_METADATA:
                row["tests"].append(add_file(path,f"versions/{name}/tests/{path.name}",name+" core tests"))
        fixtures=tests/"fixtures"
        if fixtures.is_dir():
            for path in sorted(fixtures.iterdir()):
                if path.is_file() and path.suffix in (".json",".py",".log") and path.stat().st_size<=MAX_METADATA:
                    row["tests"].append(add_file(path,f"versions/{name}/tests/fixtures/{path.name}",name+" small test fixture"))
    summary_names={Path(item["member"]).name for item in row["metadata_files"]}
    row["package_summary_present"]=bool(summary_names & {"report.json","brief_summary.json","probe_summary.json","six_summary.json","six_verification.json"})
    if not row["package_summary_present"]:
        row["evidence_gap"]="No dedicated summary in the allowed candidate directory; preserve source bytes and explicitly provided aggregate review only, do not invent run outcomes or source-to-run binding."
    versions.append(row)
for relative in EXTRAS:
    path=TMP/relative
    assert path.is_file(),path
    member="aggregate_evidence/"+relative.replace("/","__")
    item=add_file(path,member,"explicitly allowed aggregate evidence")
    walk(json.loads(path.read_text(encoding="utf-8")),item["member"])
for name in ("README.md","review.json","build_archive.py","verify_archive.py"):
    assert (OUT/name).is_file()
    add_file(OUT/name,"package_provenance/"+name,"archive sidecar snapshot")
generated("indices/versions.json",versions)
generated("indices/reported_R_G_case_protocol_hash_references.json",dict(references=references,policy="Exact values from saved allowed JSON; never dereference outside the fixed directory allowlist. R/G entries are reference-only unless a log is already inside a collected candidate."))
generated("indices/collection_scope.json",dict(allowed_candidate_directories=list(PACKAGES),allowed_aggregate_files=list(EXTRAS),source_files_per_version=list(CORE),metadata_cap_bytes=MAX_METADATA,results_scanned_recursively=False,positions_or_large_region_csv_copied=False,skipped=skipped))
p=next(v for v in versions if v["version"]=="common_pair_P_release")
assert p["source_files"]["noa/native_rules.py"]["sha256"]=="8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864"
assert p["source_files"]["experiments/native_sumo.py"]["sha256"]=="6a530098146e85a637b4f29d580d61877c7a54b3a7e15858724651d80e8956b0"
archive=OUT/"method_diagnostics.tar.gz"
with archive.open("wb") as file:
    with gzip.GzipFile(filename="",mode="wb",fileobj=file,mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode="w") as tar:
            for name,item in sorted(members.items()):
                info=tarfile.TarInfo(name)
                info.size,info.mtime,info.mode,info.uid,info.gid=len(item["raw"]),0,0o644,0,0
                tar.addfile(info,io.BytesIO(item["raw"]))
for path,before in origins.items():
    assert sha(Path(path).read_bytes())==before,"Original changed during archive: "+path
sidecars={name:dict(sha256=sha((OUT/name).read_bytes()),bytes=(OUT/name).stat().st_size) for name in ("README.md","review.json","build_archive.py","verify_archive.py")}
manifest=dict(format_version=1,archive=archive.name,archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,member_count=len(members),members={name:dict(sha256=sha(item["raw"]),bytes=len(item["raw"]),category=item["category"],original_paths=sorted(set(item["original_paths"]))) for name,item in sorted(members.items())},versions=versions,source_reference_count=sum(len(v["source_files"]) for v in versions),deduplicated_blob_count=sum(n.startswith("blobs/") for n in members),sidecars=sidecars,all_collected_original_files_byte_unchanged=True,original_files_verified=len(origins),no_simulation_or_metric_recalculation=True,no_recursive_results_scan=True,no_positions_or_large_region_csv=True,missing_summaries_not_fabricated=True,verification_outputs_excluded=["verification.json"],skipped_files=skipped)
(OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"manifest.sha256").write_text(sha((OUT/"manifest.json").read_bytes())+"  manifest.json\n",encoding="ascii")
total=sum(x.stat().st_size for x in OUT.iterdir() if x.is_file())
assert total<5*1024*1024,total
print(json.dumps(dict(output=str(OUT),versions=len(versions),source_references=manifest["source_reference_count"],deduplicated_blobs=manifest["deduplicated_blob_count"],members=len(members),archive_bytes=archive.stat().st_size,total_bytes=total,original_files_unchanged=len(origins),archive_sha256=manifest["archive_sha256"])))
