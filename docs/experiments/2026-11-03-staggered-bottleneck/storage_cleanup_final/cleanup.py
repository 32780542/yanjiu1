"""Exact authorized cleanup; immutable iteration3 history and failed raw are guards."""
import datetime,hashlib,importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent;BASE=OUT.parent;ROOT=BASE.parents[2]
ITER=BASE/'evidence_iteration3'
spec=importlib.util.spec_from_file_location('existing_seal_case',BASE/'tools/seal_case.py')
seal=importlib.util.module_from_spec(spec);spec.loader.exec_module(seal)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def info(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def matches(p,expected):return p.is_file() and p.stat().st_size==expected['bytes'] and sha(p)==expected['sha256']

def main():
    assert not (OUT/'preflight.json').exists(),'Do not repeat a cleanup attempt; inspect the saved result first'
    public=read(ITER/'PUBLIC_MANIFEST.json');public_sha=sha(ITER/'PUBLIC_MANIFEST.json')
    bound=[]
    for section,prefix in [('files',ITER),('related_reports',BASE),('tools',BASE/'tools')]:
        for relative,expected in public[section].items():
            p=(prefix/relative).resolve();assert matches(p,expected),str(p)
            bound.append(dict(section=section,**info(p)))
    assert len(bound)==72
    index=read(ITER/'unfinalized_and_raw_index.json');raw=index['local_raw']['records']
    assert len(raw)==32 and sum(r['bytes'] for r in raw)==1291519466
    failed=[r for r in raw if r['identity']['flow']==2500]
    success=[r for r in raw if r['identity']['flow']==2250]
    assert len(failed)==len(success)==16
    assert sum(r['bytes'] for r in failed)==813903124
    assert sum(r['bytes'] for r in success)==477616342
    assert {r['identity']['candidate'] for r in raw}=={'L','M','N','Q'}
    for r in raw:assert matches(Path(r['local_path']),r),r['local_path']
    failures_before=[info(Path(r['local_path'])) for r in failed]
    protected=[]
    for label,batchname in [('NoA','20261103_long1800_NOA4'),('S','20261103_long1800_S4')]:
        records=read(ROOT/'tmp/staggered_bottleneck'/batchname/'manifest.json')
        record=next(r for r in records if r['flow']==2250 and r['seed']==42)
        original=read(Path(record['evidence_dir'])/'seal.json')['originals']
        for name,expected in original.items():
            p=Path(record['run_dir'])/name;assert matches(p,expected)
            protected.append(dict(label=label,**info(p)))
    assert len(protected)==4
    packages=[];eligible=[];skipped=[];batch_snapshots=[]
    for label in ['L','M','N','Q']:
        batch=(ROOT/'tmp/staggered_bottleneck'/('20261103_long1800_'+label+'4')).resolve()
        marker=batch/'.staggered-runner-owned';assert marker.read_text(encoding='utf-8')==str(batch)
        for n in ['protocol.json','manifest.json']:batch_snapshots.append(info(batch/n))
        records=read(batch/'manifest.json');assert len(records)==4
        archive_name='20261103_long1800_'+label+'4_unfinished.tar.gz'
        archive=ITER/archive_name;v=read(ITER/(archive_name[:-3]+'.verification.json'))
        assert v['planned_cases']==4 and v['sealed_cases_verified']==2 and len(v['unfinalized_cases'])==2
        assert v['archive_original_bytes_compared'] is True and v['original_repository_reads']==[]
        assert v['original_paths_required'] is False and v['simulations_run'] is False
        assert v['archive_members_verified']>0
        entry=next(a for a in v['archives'] if Path(a['path']).name==archive.name)
        assert matches(archive,entry)
        packages.append(dict(label=label,archive=str(archive),archive_bytes=entry['bytes'],archive_sha256=entry['sha256'],original_byte_comparison_verified=True,isolated_verification_no_repository_reads=True,verification_sha256=sha(ITER/(archive_name[:-3]+'.verification.json'))))
        good=[r for r in records if r['flow']==2250];bad=[r for r in records if r['flow']==2500]
        assert {r['seed'] for r in good}=={41,42} and len(bad)==2
        for r in bad:
            assert r['candidate']==label and r['returncode']==124 and r['operation']['status']=='timeout' and r['operation']['returncode']==124
        for r in good:
            identity={k:r[k] for k in ['candidate','flow','seed','scenario','mode']}
            try:
                assert r['candidate']==label and r['scenario']=='lane_drop' and r['mode']=='transform'
                assert r['status']=='drained' and r['safe'] and r['all_completed'] and r['seal_status']=='verified' and r['returncode']==0
                assert r['collisions']==r['teleports']==0 and r['completed']==r['requested']
                run=Path(r['run_dir']).resolve();assert run.is_relative_to(batch/'cases') and run!=batch/'cases'
                evidence=Path(r['evidence_dir']).resolve();saved=read(evidence/'seal.json')
                assert saved['record']['run_dir']==r['run_dir']
                for name in seal.RAW_FILES:
                    p=run/name
                    old=next(x for x in success if x['identity']==identity and x['name']==name)
                    assert str(p)==old['local_path'] and saved['originals'][name]['sha256']==old['sha256'] and saved['originals'][name]['bytes']==old['bytes']
                    assert matches(p,old)
                verification=seal.verify(evidence,check_originals=True)
                assert verification['cases_verified']==1 and verification['local_originals_checked'] is True
                eligible.append(dict(identity=identity,batch=str(batch),run_dir=str(run),evidence_dir=str(evidence),raw_before=saved['originals'],existing_original_verification=verification))
            except Exception as exc:skipped.append(dict(identity=identity,reason=repr(exc),action='No raw touched for this case'))
    preflight=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),authorization='Parent explicitly authorized only8 successful2250 cases in long1800_L4/M4/N4/Q4, after confirmed iteration3 original-byte and isolated verification; no git/source/old snapshot edits.',publisher_reported_research_tree_commit='06081e2',iteration3_public_manifest_sha256=public_sha,manifest_bound_files=bound,manifest_bound_file_count=72,complete_packages=packages,batch_snapshots=batch_snapshots,eligible_cases=eligible,skipped_cases=skipped,failed_raw_before=failures_before,failed_raw_files=16,failed_raw_bytes=813903124,protected_selected_NOA_S_seed42_raw_before=protected,iteration3_raw_before_files=32,iteration3_raw_before_bytes=1291519466)
    save('preflight.json',preflight)
    result=dict(started_at_utc=preflight['at_utc'],deleted_cases=[],skipped_cases=skipped)
    save('cleanup_result.json',result)
    for case in eligible:
        run=Path(case['run_dir']);evidence=Path(case['evidence_dir'])
        deletion=seal.prune_raw(run,Path(case['batch']),case['raw_before'],verified=True)
        assert set(deletion['deleted'])=={'positions.jsonl.gz','events.jsonl.gz'}
        assert all(not (run/name).exists() for name in deletion['deleted'])
        offline=seal.verify(evidence,check_originals=False);assert offline['cases_verified']==1
        result['deleted_cases'].append(dict(identity=case['identity'],run_dir=str(run),raw_before=case['raw_before'],raw_after={n:dict(exists=(run/n).exists()) for n in seal.RAW_FILES},offline_evidence_verified=True,**deletion))
        save('cleanup_result.json',result)
    failed_after=[info(Path(r['local_path'])) for r in failed]
    assert failed_after==failures_before
    for r in protected:assert info(Path(r['path']))=={k:v for k,v in r.items() if k!='label'}
    for r in bound:assert info(Path(r['path']))=={k:v for k,v in r.items() if k!='section'}
    assert sha(ITER/'PUBLIC_MANIFEST.json')==public_sha
    for r in batch_snapshots:assert info(Path(r['path']))==r
    removed=sum(r['bytes_released'] for r in result['deleted_cases'])
    result.update(completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),deleted_successful_cases=len(result['deleted_cases']),deleted_raw_files=sum(len(r['deleted']) for r in result['deleted_cases']),bytes_released=removed,failed_raw_after=failed_after,failed_raw_files_still_present=16,failed_raw_bytes_still_present=sum(r['bytes'] for r in failed_after),all_failed_raw_sha_bytes_unchanged=True,protected_selected_NOA_S_seed42_raw_after=protected,all_selected_NOA_S_seed42_raw_sha_bytes_unchanged=True,manifest_bound_files_rechecked=72,all_manifest_bound_files_unchanged=True,public_manifest_unchanged=True,batch_protocol_manifests_unchanged=True,only_existing_prune_raw_used=True,no_recursive_delete=True,no_new_simulations=True,no_git_operations=True,no_source_changes=True,old_iteration3_snapshot_intentionally_not_rewritten=True)
    save('cleanup_result.json',result)
    lines=['# 最终本地存储清理：仅本轮八个成功2250案例','',f'本单元在研究结束后按父明确授权执行，只清理`20261103_long1800_L4/M4/N4/Q4`中drained、safe、sealed的2250每道流量、seed41/42案例。没有新仿真、Git或source修改。实际清理{result["deleted_successful_cases"]}例、{result["deleted_raw_files"]}个positions/events文件，释放{removed:,}字节（{removed/1024**2:.3f}MiB）。未满足严格条件者原样保留，跳过{len(skipped)}例。','',
      '| 方法 | 流量 | seed | 清理文件 | 释放字节 |','|---|---:|---:|---:|---:|']
    for r in result['deleted_cases']:
        i=r['identity'];lines.append(f'| {i["candidate"]} | {i["flow"]:g} | {i["seed"]} | {len(r["deleted"])} | {r["bytes_released"]:,} |')
    lines+=['','前提逐项核验：iteration3对应四个完整原计划包仍在本地，包SHA与PUBLIC_MANIFEST及原verification一致；已有原字节比较=true、隔离验证无原仓库读取、无original paths依赖，两成功/两timeout的原四例矩阵均保留。父确认包已发布于研究树`06081e2`，本单元没有运行Git去改变或重复发布。','',
      '每个清理案例先用既有`seal_case.verify(check_originals=True)`验证紧凑原件及全部ledger；两个raw同时匹配原seal及iteration3索引的字节/SHA。随后直接调用原`prune_raw`，核验batch ownership marker、解析绝对路径位于指定batch/cases/run、原SHA且非symlink；只unlink已列出的positions.jsonl.gz和events.jsonl.gz，不递归删除。清理后离线封存验证仍通过。','',
      f'八个2500 timeout案例的16个raw共813,903,124字节，操作前后逐文件存在/字节/SHA完全一致；没有解析、改写或补造partial raw。选定2250 seed42 NoA/S双源的4个完整positions/events也逐文件前后哈希一致。较早阶段原件未列为删除目标。','',
      'iteration3的72项manifest绑定文件（56包/索引/说明文件、8相关报告、8工具）以及PUBLIC_MANIFEST自身，操作前后SHA全部一致；四批原protocol/manifest也一致。旧README及unfinalized_and_raw_index仍描述当时32 raw/1,291,519,466字节的封存快照，刻意不回写历史。当前状态以本补记及JSON为准。','',
      '[完整前置条件、包与原始文件索引](preflight.json)、[逐例精确前后/释放量/失败raw复核](cleanup_result.json)、[执行工具](cleanup.py)。原证据：[iteration3完整矩阵](../evidence_iteration3/README.md)、[旧只读索引](../evidence_iteration3/unfinalized_and_raw_index.json)。主报告引用由root另行补入，本单元不改旧报告。','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['deleted_successful_cases','deleted_raw_files','bytes_released','failed_raw_files_still_present','failed_raw_bytes_still_present','all_failed_raw_sha_bytes_unchanged','manifest_bound_files_rechecked','all_manifest_bound_files_unchanged']},ensure_ascii=False))

if __name__=='__main__':main()
