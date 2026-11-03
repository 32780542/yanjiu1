"""Archive each whole L/M/N/Q long1800 four-plan, including compute timeouts.

Reuses frozen byte extraction, sealed-case verification, raw indexing and tar writer.
"""
import argparse
import builtins
import io
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import package_stage as normal
import package_unfinished as prior
import seal_case
import summarize

REPO,REL=normal.REPO,normal.REL
SCOPE="Full original four-case long1800 plan; two sealed cases verified, two unfinalized compute timeouts retained without physical metrics. All extant partial raw remains local, SHA/bytes indexed only. Physical completion of timed-out cases is undetermined. Wall-clock runtimes are not performance comparisons; the operator reports active M/Q workers were temporarily lowered to BelowNormal around15:20, without changing physical inputs."


def validate_plan(name,records):
    if name not in {"20261103_long1800_"+candidate+"4" for candidate in ("L","M","N","Q")}:
        raise ValueError("unsupported original long1800 batch")
    if len(records)!=4 or sum(row.get("seal_status")=="verified" for row in records)!=2:
        raise ValueError("whole four-case plan with two sealed and two unfinalized attempts required")
    for row in records:
        if row.get("seal_status")!="verified" and (row.get("status")!="starting" or row.get("returncode")!=124):
            raise ValueError("unfinalized long case is not a recorded compute timeout")


def failure_kind(record,execution):
    if record.get("status")!="starting":
        raise ValueError("unfinalized classification requires original result=starting")
    if execution.get("status")=="timeout" and execution.get("returncode")==124 and record.get("returncode")==124:
        return "unverified_compute_timeout"
    if execution.get("status")=="failed" and execution.get("returncode") not in (None,0) and record.get("returncode") not in (None,0):
        return "unverified_execution_failure"
    raise ValueError("unsupported or inconsistent execution evidence")


def check_extracted(roots):
    if len(roots)!=1:
        raise ValueError("one full failed-followup plan required")
    root=Path(roots[0]).resolve()
    index=seal_case.read(root/"index.json")
    forbidden=os.path.normcase(index["original_repo"])
    original_open,original_io_open,attempts=builtins.open,io.open,[]
    def guard(function):
        def guarded(file,*args,**kwargs):
            if isinstance(file,(str,bytes,os.PathLike)):
                path=os.path.normcase(os.path.abspath(os.fsdecode(file)))
                if path==forbidden or path.startswith(forbidden+os.sep):
                    attempts.append(path)
                    raise OSError("original repository reads forbidden")
            return function(file,*args,**kwargs)
        return guarded
    builtins.open,io.open=guard(original_open),guard(original_io_open)
    try:
        records=summarize.protocol_records(root/"stage")
        mapping={tuple(row["identity"][key] for key in summarize.IDENTITY):row for row in index["cases"]}
        validate_plan(index["stage"],records)
        if len(mapping)!=4:
            raise ValueError("whole four-case matrix missing")
        sealed,failed=0,[]
        for record in records:
            case=mapping[tuple(record[key] for key in summarize.IDENTITY)]
            if record.get("seal_status")=="verified":
                record["evidence_dir"]=str(root/case["evidence"])
                checked=summarize.load_case(record)
                if not checked["evidence_verified"] or not checked["protocol_verified"]:
                    raise ValueError("sealed archive/protocol verification failed")
                sealed+=1
                continue
            execution=seal_case.read(root/case["operation"]/"result.json")
            kind=failure_kind(record,execution)
            run=root/case["run"]
            inp,result=(seal_case.read(run/name) for name in ("input.json","result.json"))
            if result.get("status")!="starting":
                raise ValueError("original result no longer starting")
            task,protocol=record["_task"],record["_protocol"]
            for field,key in dict(mode="mode",seed="seed",scenario="scenario",flow_veh_h_lane="flow",demand_duration_s="duration",max_time_s="max_time").items():
                if inp["case"][field]!=task[key]:
                    raise ValueError("failed case input/protocol mismatch")
            if result.get("source_sha256")!=inp["source_sha256"]:
                raise ValueError("starting source hash mismatch")
            for name,digest in inp["source_sha256"].items():
                if protocol["sources"][record["candidate"]].get(name)!=digest or seal_case.sha(run/"source"/name)!=digest:
                    raise ValueError("failed source/protocol mismatch")
            failed.append(dict(identity=case["identity"],classification=kind,
                case_returncode=record["returncode"],operation_returncode=execution["returncode"],
                child_returncode=execution.get("child_returncode"),
                operation_status=execution["status"],elapsed_s=execution["elapsed_s"],worker_timeout_s=execution["timeout_s"],
                original_result_status="starting",trips_present=(run/"trips.json").is_file(),
                physical_completion="undetermined",eligible=False))
        if sealed!=2 or len(failed)!=2:
            raise ValueError("expected two sealed and two unfinalized attempts")
        return dict(planned_cases=4,sealed_cases_verified=sealed,unfinalized_cases=failed,
                    original_repository_reads=attempts,original_paths_required=False,raw_index=index["raw_index"],
                    raw_payload_included=False,raw_contents_verified=False,simulations_run=False,scope=SCOPE)
    finally:
        builtins.open,io.open=original_open,original_io_open


def build(batch,output):
    batch,output=Path(batch).resolve(),Path(output).resolve()
    records=summarize.protocol_records(batch)
    validate_plan(batch.name,records)
    payload,cases,raw_index={},[],[]
    for name in ("protocol.json","manifest.json","runner.py","seal_case.py",".staggered-runner-owned"):
        if (batch/name).is_file():
            payload["stage/"+name]=batch/name
    operations=normal.stage_operations(batch,records)
    operation_map={str(path):f"stage/operations/{i:04d}" for i,path in enumerate(operations)}
    for number,row in enumerate(records):
        folder,base=Path(row["case_output"]),f"stage/cases/{number:04d}"
        stored,raw=prior.case_files(folder)
        for path in stored:
            payload[base+"/"+path.relative_to(folder).as_posix()]=path
        identity={key:row[key] for key in summarize.IDENTITY}
        raw_index.extend({**item,"identity":identity} for item in raw)
        cases.append(dict(identity=identity,evidence=base+"/evidence",run=base+"/"+Path(row["run_dir"]).name,
            operation=operation_map[str(Path(row["operation"]["path"]).resolve())]))
    for path in sorted((batch/"sources").rglob("*")):
        if path.is_file() and "tmp" not in path.relative_to(batch/"sources").parts:
            payload["stage/sources/"+path.relative_to(batch/"sources").as_posix()]=path
    for operation in operations:
        for name in ("started.json","result.json","stdout.log","stderr.log"):
            if (operation/name).is_file():
                payload[operation_map[str(operation)]+"/"+name]=operation/name
        snapshot=operation/"runner_snapshot.py"
        if snapshot.is_file():
            payload["stage/run_logged_sources/"+seal_case.sha(snapshot)+".py"]=snapshot
    for relative in [*normal.dependencies(),REL+"/package_unfinished.py",REL+"/package_long1800.py"]:
        payload["repo/"+relative]=REPO/relative
    payload["README.md"]=(SCOPE+"\n\nCase and operation exit codes are preserved separately. A failed operation is not relabelled as timeout.\nMissing trips remain missing; no completion, safety or travel-time values are inferred for unfinalized attempts.\n").encode()
    index=dict(kind="long1800_four_plan_unfinalized",stage=batch.name,case_count=4,cases=cases,raw_index=raw_index,
        original_repo=str(REPO),original_batch=str(batch),scope=SCOPE,package_tool="repo/"+REL+"/package_long1800.py")
    prior.write_archive(output,index,payload)
    report=normal.verify([output],check_originals=True)
    seal_case.write(output.with_suffix(".verification.json"),report)
    seal_case.write(output.with_suffix(".manifest.json"),dict(archive=output.name,sha256=seal_case.sha(output),bytes=output.stat().st_size,
        planned_cases=4,sealed_cases=2,unfinalized_cases=2,raw_payload_included=False,raw_index_bytes=sum(row["bytes"] for row in raw_index),scope=SCOPE))
    print(json.dumps(dict(archive=str(output),bytes=output.stat().st_size,sealed=2,unfinalized=2)),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    make=commands.add_parser("build")
    make.add_argument("--batch",type=Path,required=True)
    make.add_argument("--output",type=Path,required=True)
    check=commands.add_parser("check-extracted")
    check.add_argument("roots",type=Path,nargs="+")
    check.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="build":
        build(args.batch,args.output)
    else:
        seal_case.write(args.report,check_extracted(args.roots))


if __name__=="__main__":
    main()
