"""Catalog complete iteration3 plans, preserving unfinalized cases without metrics."""
import json
from pathlib import Path
import tarfile

from catalog_final61 import file_record
import seal_case
import summarize

ROOT=Path(__file__).resolve().parents[1]


def identity(row):
    return tuple(row[key] for key in summarize.IDENTITY)


def main():
    folder=ROOT/"evidence_iteration3"
    if (folder/"PUBLIC_MANIFEST.json").exists():
        raise ValueError("catalog exists")
    manifests=[seal_case.read(path) for path in sorted(folder.glob("*.tar.manifest.json"))]
    assert len(manifests)==18
    batches,seen,archives,raw_records,failures={},set(),[],[],[]
    sealed_total=0
    for manifest in manifests:
        archive=folder/manifest["archive"]
        assert file_record(archive)=={key:manifest[key] for key in ("sha256","bytes")}
        assert archive.stat().st_size<20_000_000
        with tarfile.open(archive,"r:gz") as stream:
            index=json.load(stream.extractfile("index.json"))
        report=seal_case.read(archive.with_suffix(".verification.json"))
        assert report["archive_original_bytes_compared"]
        assert not report["original_repository_reads"] and not report["original_paths_required"] and not report["simulations_run"]
        batch=Path(index["original_batch"])
        if "partition" in manifest:
            assert manifest["partition"]["original_protocol_sha256"]==seal_case.sha(batch/"protocol.json")
            assert manifest["partition"]["original_manifest_sha256"]==seal_case.sha(batch/"manifest.json")
        else:
            for name in ("protocol.json","manifest.json"):
                assert index["members"]["stage/"+name]["sha256"]==seal_case.sha(batch/name)
        batches[str(batch)]=dict(protocol_sha256=seal_case.sha(batch/"protocol.json"),manifest_sha256=seal_case.sha(batch/"manifest.json"))
        if "unfinalized_cases" in report:
            assert report["planned_cases"]==4 and report["sealed_cases_verified"]==2 and len(report["unfinalized_cases"])==2
            rows=[case["identity"] for case in index["cases"]]
            sealed,unfinalized=2,2
            failures.extend(report["unfinalized_cases"])
            raw_records.extend(index["raw_index"])
        else:
            rows=report["cases"]
            sealed=report["cases_verified"]
            unfinalized=0
            assert sealed==report["protocol_verified"]==report["physical_safe_count"]==report["all_completed_count"]==len(rows)
        keys=[identity(row) for row in rows]
        assert len(set(keys))==len(keys) and not (seen&set(keys))
        seen.update(keys)
        sealed_total+=sealed
        archives.append({**manifest,"planned_cases":len(rows),"sealed_verified":sealed,"unfinalized":unfinalized})
    expected=[identity(task) for batch in batches for task in seal_case.read(Path(batch)/"protocol.json")["tasks"]]
    assert len(expected)==len(set(expected))==len(seen)==186 and set(expected)==seen
    assert sealed_total==178 and len(failures)==8 and len(batches)==16
    for failed in failures:
        assert failed["classification"]=="unverified_compute_timeout" and failed["operation_returncode"]==124
        assert failed["case_returncode"]==124 and failed["physical_completion"]=="undetermined" and failed["eligible"] is False
    for raw in raw_records:
        path=Path(raw["local_path"])
        assert path.is_file() and path.stat().st_size==raw["bytes"] and seal_case.sha(path)==raw["sha256"]
    failed_keys={identity(row["identity"]) for row in failures}
    failed_raw=[row for row in raw_records if identity(row["identity"]) in failed_keys]
    local_raw=dict(files=len(raw_records),bytes=sum(row["bytes"] for row in raw_records),all_original_files_still_present_and_hash_matched=True,
        unfinalized_case_raw_files=len(failed_raw),unfinalized_case_raw_bytes=sum(row["bytes"] for row in failed_raw),
        payload_included=False,raw_reconstructed_or_parsed=False,records=raw_records)
    seal_case.write(folder/"unfinalized_and_raw_index.json",dict(planned_cases=186,sealed_verified=178,unfinalized=failures,
        original_batches=batches,complete_disjoint_plan_union=True,local_raw=local_raw,
        execution_context="Operator reports active M/Q processes temporarily lowered to BelowNormal around15:20; L remained normal priority. This is context, not a wall-time performance comparison. Physical inputs unchanged; N priority not inferred."))
    lines=["# 后续正常批与1800秒未封口试验：完整矩阵封存","",
        "18包覆盖16个完整原始批计划、186例：178例已封口并通过协议/紧凑证据核验，8例为真实计算超时，物理完成情况未知。没有按完成或表现筛选；旧M8/N8等已发布批不复制。M40/Q40按预定完整道路20例分包，其他本轮批保留完整原计划。","",
        "| 包 | 计划 | 已核验封口 | 未封口 | 字节 |","|---|---:|---:|---:|---:|"]
    for item in archives:
        lines.append(f"| {item['archive']} | {item['planned_cases']} | {item['sealed_verified']} | {item['unfinalized']} | {item['bytes']} |")
    lines.extend(["",f"全部包共{sum(item['bytes'] for item in archives):,}字节；最大{max(item['bytes'] for item in archives):,}字节，均严格小于20,000,000。", "",
        "正常案例保留原input/result/trips、六源、全部选定flags/gate brackets/region ledgers、case_record/worker与必要run_logged日志；批冻结runner/seal及旧方法依赖一并内置。每包逐成员SHA/字节索引，先对原件字节，再临时解包由独立Python -I核验全部病例，禁止读取原仓库。单方法包generic配对缺reference不代表物理/协议失败；正式对照表另行引用。", "",
        "L/M/N/Q的每个1800秒4例包保留原protocol/manifest全字节，以及两例成功的完整evidence、两例未封口的全部原有小文件和操作日志；没有把成功子集当完整物理对照。8个未封口案例均为2500、种子41/42缩道，原result仍starting，实际outer/case returncode均124；child_returncode和实际耗时3000.06–3000.11秒见索引及原操作日志。trips不存在时保持不存在，不补造字段或性能。", "",
        "8例physical completion=undetermined，eligible=false；计算超时不能证明物理上限达到或道路不能排空。root报告约15:20对当时活动的M/Q进程临时设置BelowNormal，L保持正常priority；N优先级不推断。物理输入不变，**不得比较wall-clock耗时作为方法性能**。", "",
        f"原位置仍有{local_raw['files']}个大raw文件、{local_raw['bytes']:,}字节，全部重新核对存在/字节/SHA；其中未封口8例对应{len(failed_raw)}个、{local_raw['unfinalized_case_raw_bytes']:,}字节。这里只保存索引，不上传大raw，不删除原件，不声称能从云端包重建/解析partial raw。其余正常案例已清理的完整轨迹也不能由哈希重建。", "",
        "现有选定字段可离线复核既定指标，不能替代完整轨迹、独立形成几何或新增未保留指标。包内工具复核入口为repo/docs/experiments/2026-11-03-staggered-bottleneck/tools/package_stage.py verify ARCHIVE --report NEW.json，异机离线省略--check-originals；在原机可加该参数额外核对原件。", "",
        "S对NOA60的同输入敏感性见../S_NOA60_sensitivity，原件独立复算10对全部有效，采用实际NOA60分母，不机械减去另一表改善率。M/Q未采用结果及所有L/M/N/Q超时均保留。正式final61数值和旧封包不改。"])
    (folder/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    related=[*sorted((ROOT/"S_NOA60_sensitivity").glob("*")),ROOT/"matched_nonformation31_and_S170/LP0_addendum.md"]
    tools=("package_stage.py","package_partition.py","package_unfinished.py","package_failed_followup.py","package_long1800.py","report_matched_attribution.py","review_S_NOA60.py","catalog_iteration3.py")
    catalog=dict(format="iteration3-complete-plan-and-unfinalized-v1",archives=archives,original_batch_count=16,planned_cases=186,
        sealed_verified=178,unfinalized_cases=8,total_archive_bytes=sum(row["bytes"] for row in archives),
        complete_disjoint_plan_union=True,original_batches=batches,raw_payload_included=False,
        local_raw_files_still_present=len(raw_records),local_raw_bytes=sum(row["bytes"] for row in raw_records),
        files={p.name:file_record(p) for p in sorted(folder.iterdir()) if p.is_file()},
        related_reports={str(p.relative_to(ROOT)):file_record(p) for p in related if p.is_file()},
        tools={name:file_record(ROOT/"tools"/name) for name in tools})
    seal_case.write(folder/"PUBLIC_MANIFEST.json",catalog)
    print(json.dumps(dict(archives=18,plans=186,sealed=178,unfinalized=8,bytes=catalog["total_archive_bytes"],local_raw_files=len(raw_records),local_raw_bytes=catalog["local_raw_bytes"])),flush=True)


if __name__=="__main__":
    main()
