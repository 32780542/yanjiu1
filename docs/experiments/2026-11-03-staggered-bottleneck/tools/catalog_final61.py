"""Bind the eight verified fixed-profile archives to the locked final report."""
import json
from pathlib import Path

import review_E_heldout as independent
import review_final61_S160 as locked
import seal_case
import summarize

ROOT=Path(__file__).resolve().parents[1]


def file_record(path):
    return dict(sha256=seal_case.sha(path),bytes=path.stat().st_size)


def main():
    folder=ROOT/"evidence_final61"
    if (folder/"PUBLIC_MANIFEST.json").exists():
        raise ValueError("catalog already exists")
    manifests=[seal_case.read(path) for path in sorted(folder.glob("*.tar.manifest.json"))]
    assert len(manifests)==8
    cases=[]
    for manifest in manifests:
        archive=folder/manifest["archive"]
        assert file_record(archive)=={key:manifest[key] for key in ("sha256","bytes")}
        assert archive.stat().st_size<20_000_000
        verified=seal_case.read(archive.with_suffix(".verification.json"))
        assert verified["archive_original_bytes_compared"] and not verified["original_repository_reads"]
        assert not verified["original_paths_required"] and not verified["simulations_run"]
        assert verified["cases_verified"]==verified["protocol_verified"]==verified["physical_safe_count"]==verified["all_completed_count"]==manifest["case_count"]
        descriptor=manifest["partition"]
        batch=Path(descriptor["original_batch"])
        assert descriptor["original_protocol_sha256"]==seal_case.sha(batch/"protocol.json")
        assert descriptor["original_manifest_sha256"]==seal_case.sha(batch/"manifest.json")
        cases.extend(verified["cases"])
    lock=locked.audit_locked_cases(cases)
    index=summarize.unique(cases)
    columns=(*summarize.IDENTITY,*independent.METRICS,"safe","all_completed","protocol_verified","evidence_verified",
        "input_sha256","result_sha256","trips_sha256","source_version_sha256","rules_sha256",
        "demand_sha256","parameters_sha256","nonrule_source_sha256")
    actual=[{key:row[key] for key in columns} for row in independent.read_csv(ROOT/"final61_S160/per_case.csv")]
    independent.check_csv(actual,cases,summarize.IDENTITY,"archived_case_vs_report")
    pairs=independent.read_csv(ROOT/"final61_S160/paired_seeds.csv")
    assert len(pairs)==80
    for pair in pairs:
        key=float(pair["flow"]),int(pair["seed"]),pair["scenario"]
        reference=index[("TM",*key,"noa")]
        target=index[("S",*key,"transform")]
        for name in ("demand_sha256","parameters_sha256","nonrule_source_sha256"):
            assert reference[name]==target[name]
        for metric in independent.METRICS:
            a,b=reference.get(metric),target.get(metric)
            for prefix,expected in (("reference_",a),("target_",b),("delta_",b-a if a is not None and b is not None else None)):
                independent.compare(pair[prefix+metric],expected,repr(key)+prefix+metric,"archived_pair_vs_report")
    crosscheck=dict(cases=160,pairs=80,groups=16,complete_disjoint_matrix=lock,
        archived_case_fields=list(columns),primary_pair_metrics=list(independent.METRICS),
        comparisons=dict(independent.COUNTS),max_absolute_numeric_errors=dict(independent.MAXERR),
        original_archive_byte_checks=True,all_archives_offline_verified=True,
        original_repository_reads=[],original_paths_required=False,full_positions_included=False,
        generic_single_method_package_pairs_are_not_formal_method_comparisons=True,
        tool_sha256=seal_case.sha(__file__))
    seal_case.write(folder/"archive_report_crosscheck.json",crosscheck)
    lines=["# 锁定 S 的61–65独立确认：紧凑证据","",
        "8 个独立可核验包完整覆盖原 NOA80 + S80，160例，无重复、无遗漏。每方法按两种原道路，再按全部低流量<=1500（每道路25例）/全部高流量>=2000（每道路15例）分区；不依表现或完成结果选择。每包保留全批80例原 protocol/manifest 字节及明确分区映射。","",
        "| 包 | 例数 | 字节 |","|---|---:|---:|"]
    for item in manifests:
        lines.append(f"| {item['archive']} | {item['case_count']} | {item['bytes']} |")
    lines.extend(["",f"归档总字节 {sum(item['bytes'] for item in manifests):,}；每包严格小于20,000,000字节。", "",
        "每个case保留原input/result/trips、六源和选定flags/gate brackets/region ledgers，以及case_record、worker和必要operation日志。大runner snapshot按批去重。index.json逐成员记录SHA/字节及原路径映射；工具先核对原件字节，再临时解包于独立Python -I中核验全部病例，禁止读取原仓库。", "",
        "按仓库命令可复核任一包：`python -B tools/package_stage.py verify ARCHIVE --check-originals --report NEW.json`（从本实验目录运行）。离线使用时先安全解包，调用包内repo/docs/experiments/2026-11-03-staggered-bottleneck/tools/package_stage.py verify；完整依赖已内置，无须原tmpcase。原件路径是可选的额外字节比对条件；异机离线验证请省略--check-originals。", "",
        "单包只有一个方法，原generic配对可能缺参考而不eligible；这不等同于正式配对失败。正式80配对、16组来自../final61_S160，并经../review_final61_S160.{json,md}逐原件复算。archive_report_crosscheck.json另将8包160个离线核验case的15指标和input/result/trips/源码/需求/参数SHA逐例绑定正式表，并重新核对80对的15指标差。", "",
        "正式160例全部safe/drained、80对有效。2250/2500缩道系统时间改善15.8138%/14.3397%，均5/5种子；同种子道路额外节省8.929788/11.583358秒，均5/5。500缩道仅2/5改善，三例未改善完整保留。80/80配对燃油增加，16组均值也全部增加，不能省略代价。", "",
        "完整positions/events已按原政策清理，原全文件仅留SHA/字节索引；这些包不能重建完整轨迹或追加未保留指标。现有选定字段可独立复核，交通成功不能单独证明完整形成几何。全矩阵、source lock、输入和失败资格均不由返回码替代。", "",
        "S31/G0匹配归因及S-phase子系统关闭证明另见../matched_nonformation31_and_S170；不把原NOA总差当成单纯交错或P参数作用。", "",
        "冻结package_stage/report_paired/旧road工具均未修改，旧证据包未移动或重写；此工具不仿真、不改生产或候选、不删除原件。"])
    (folder/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    report_paths=[*sorted((ROOT/"final61_S160").glob("*")),ROOT/"review_final61_S160.json",ROOT/"review_final61_S160.md",
        *sorted((ROOT/"matched_nonformation31_and_S170").glob("*")),ROOT/"implementation/LP0_S_phase_zero_equivalence.json"]
    catalog=dict(format="locked-final61-complete-matrix-v1",archives=manifests,case_count=160,formal_pairs=80,formal_groups=16,
        total_archive_bytes=sum(row["bytes"] for row in manifests),partition_coverage=lock,
        full_positions_included=False,source_locked_before_unblinding=True,
        files={p.name:file_record(p) for p in sorted(folder.iterdir()) if p.is_file()},
        related_reports={str(p.relative_to(ROOT)):file_record(p) for p in report_paths if p.is_file()},
        tools={name:file_record(ROOT/"tools"/name) for name in ("package_stage.py","package_partition.py","package_final_partition.py","report_paired.py","review_final61_S160.py","review_E_heldout.py","catalog_final61.py")})
    seal_case.write(folder/"PUBLIC_MANIFEST.json",catalog)
    print(json.dumps(dict(archives=8,cases=160,pairs=80,groups=16,archive_bytes=catalog["total_archive_bytes"],crosscheck_comparisons=dict(independent.COUNTS))),flush=True)


if __name__=="__main__":
    main()
