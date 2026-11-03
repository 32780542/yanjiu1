"""Archive the two exact authorized successful long batches; retain selected raw."""
import csv,hashlib,io,json,tarfile
from pathlib import Path
import seal_case

BASE=Path(__file__).resolve().parent.parent;ROOT=BASE.parents[2]
OUT=BASE/'long_window_NOA_S1800';DEST=OUT/'evidence_profiles'
def sha(p):return seal_case.sha(p)
def main():
    assert not DEST.exists();DEST.mkdir()
    proof=json.loads((OUT/'independent_audit/verification.json').read_text())
    assert proof['independent_cases']==8 and proof['raw_frame_checks']==32 and proof['all_ledger_integrals_and_gate_counts_match'] and proof['all_raw_region_counts_low_counts_speed_sums_match']
    allcases=[];archives=[]
    for label,bname in [('NoA','20261103_long1800_NOA4'),('S','20261103_long1800_S4')]:
        batch=ROOT/'tmp/staggered_bottleneck'/bname;records=json.loads((batch/'manifest.json').read_text());assert len(records)==4
        selected=[]
        for r in records:
            assert r['safe'] and r['all_completed'] and r['status']=='drained' and r['seal_status']=='verified' and r['returncode']==0
            assert r['flow'] in (2250.,2500.) and r['seed'] in (41,42)
            folder=Path(r['evidence_dir']);seal=seal_case.read(folder/'seal.json')
            seal_case.verify(folder,check_originals=True)
            run=Path(r['run_dir']);keep=r['flow']==2250 and r['seed']==42
            case=dict(label=label,flow=r['flow'],seed=r['seed'],run_dir=str(run),batch=str(batch),evidence_dir=str(folder),keep_full_raw=keep,raw_expected=seal['originals'],evidence_verified_with_originals=True)
            allcases.append(case)
            prefix=f'{label}_{int(r["flow"])}_{r["seed"]}'
            for p in sorted(folder.rglob('*')):
                if p.is_file():selected.append((prefix+'/evidence/'+p.relative_to(folder).as_posix(),p))
            for name in ['input.json','result.json','trips.json','sumo_command.json','netconvert.json','native.net.xml','sumo_tripinfo.xml','sumo_warnings.log']:
                p=run/name
                if p.is_file():selected.append((prefix+'/original_context/'+name,p))
        for p in sorted((batch/'sources').rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:selected.append(('frozen_runtime/'+p.relative_to(batch/'sources').as_posix(),p))
        for name in ['protocol.json','manifest.json','runner.py','seal_case.py']:
            selected.append(('batch/'+name,batch/name))
        for p in sorted(OUT.iterdir()):
            if p.is_file():selected.append(('window_report/'+p.name,p))
        for p in sorted((OUT/'independent_audit').iterdir()):
            if p.is_file():selected.append(('window_report/independent_audit/'+p.name,p))
        methodfiles=[Path(__file__),BASE/'tools/report_long_window.py',BASE/'tools/test_report_long_window.py',BASE/'long_window_analysis/verify_window_ledgers.py',BASE/'tools/seal_case.py',BASE/'tools/summarize.py',BASE/'tools/report_paired.py']
        old=ROOT/'docs/experiments/2026-10-30-rule-trials'
        methodfiles += [old/'evidence/compact_evidence.py',old/'analysis/bottleneck_trials.py']
        _,traffic=seal_case.tools()
        methodfiles += [Path(traffic.existing.__file__).with_name(n+'.py') for n in ['bottleneck_attribution','native_comparison','complete_layers','native_sumo']]
        for p in methodfiles:selected.append(('method_sources/'+p.relative_to(ROOT).as_posix(),p))
        names=[n for n,_ in selected];assert len(names)==len(set(names))
        members={n:dict(sha256=sha(p),bytes=p.stat().st_size) for n,p in selected}
        manifest=dict(profile=label,format='complete_sealed_evidence_full_raw_indexed_v1',members=members,full_positions_events_included=False,raw_index=[r for r in allcases if r['label']==label],description='Complete compact original JSON/six source bundle, all region/gate/vehicle ledgers and 0/1 frames. Full positions/events are indexed, not silently claimed included; selected2250seed42 kept locally because each positions file alone exceeds20MB.')
        archive=DEST/(label+'_four_cases_evidence.tar.gz')
        with tarfile.open(archive,'w:gz',compresslevel=6) as tf:
            for n,p in selected:tf.add(p,arcname=n,recursive=False)
            blob=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('MEMBER_MANIFEST.json');info.size=len(blob);tf.addfile(info,io.BytesIO(blob))
        assert archive.stat().st_size<20_000_000,'Do not prune when the requested small evidence archive is too large'
        with tarfile.open(archive,'r:gz') as tf:
            assert set(tf.getnames())==set(members)|{'MEMBER_MANIFEST.json'}
            for n,entry in members.items():
                b=tf.extractfile(n).read();assert len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256']
        archives.append(dict(profile=label,archive=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),members_including_manifest=len(members)+1,all_members_byte_hash_verified=True))
    # Both complete archives and every source original passed before any removal.
    seal_case.write(DEST/'archive_verification.json',archives)
    seal_case.write(DEST/'raw_index_before_pruning.json',allcases)
    deleted=[];released=0
    for case in allcases:
        run=Path(case['run_dir'])
        if case['keep_full_raw']:
            assert all((run/n).is_file() and sha(run/n)==v['sha256'] for n,v in case['raw_expected'].items())
            deleted.append(dict(label=case['label'],flow=case['flow'],seed=case['seed'],retained_full_raw=True,deleted=[],bytes_released=0));continue
        result=seal_case.prune_raw(run,Path(case['batch']),case['raw_expected'],verified=True)
        assert set(result['deleted'])=={'positions.jsonl.gz','events.jsonl.gz'}
        assert all(not (run/n).exists() for n in result['deleted'])
        released+=result['bytes_released'];deleted.append(dict(label=case['label'],flow=case['flow'],seed=case['seed'],retained_full_raw=False,**result))
        seal_case.verify(Path(case['evidence_dir']),check_originals=False)
    result=dict(archives=archives,raw_cases=deleted,pruned_successful_cases=6,retained_selected_full_raw_cases=2,bytes_released=released,only_exact_authorized_NOA4_S4_successes=True,old_other_batch_raw_untouched=True,existing_prune_raw_used=True,no_recursive_delete=True)
    seal_case.write(DEST/'pruning_verification.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
