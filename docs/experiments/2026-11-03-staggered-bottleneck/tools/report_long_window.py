"""Derive an extended traffic window solely from sealed full ledgers.

Never changes report_paired.py, old metrics or evidence; never opens positions.
"""
import argparse
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
from statistics import mean

import report_paired
import seal_case
import summarize

REGION_NAMES=("mean_n","density_veh_km_lane","mean_speed_mps","low_speed_vehicle_s","low_speed_fraction","max_simultaneous_low_speed")

def case_outcome(record):
    op=record.get('operation',{})
    if op.get('status')=='timeout' and op.get('returncode')==124:return 'worker_wallclock_timeout_physical_completion_unknown'
    if record.get('returncode') not in (None,0):return 'execution_failure_physical_completion_unknown'
    if record.get('status')=='drained' and record.get('safe') and record.get('seal_status')=='verified':return 'safe_drained_sealed'
    return 'unavailable_or_incomplete_not_imputed'

def read_steps(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        fields=json.loads(next(f));return [dict(zip(fields,json.loads(line))) for line in f]

def read_gates(path):
    result={}
    with gzip.open(path,'rt',encoding='utf-8') as f:
        fields=json.loads(next(f))
        assert fields==['vehicle_index','gate_m','t0','x0','t1','x1']
        for line in f:
            i,gate,t0,x0,t1,x1=json.loads(line);key=(i,gate)
            if key in result:raise ValueError('duplicate observed gate in immutable ledger')
            result[key]=t0 if t0==t1 else t0+(gate-x0)/(x1-x0)*(t1-t0)
    return result

def count_crossings(gates,start,end):
    # This is the frozen existing evaluator's closed endpoint convention.
    return sum(gate==1000 and start<=t<=end for (_,gate),t in gates.items())

def derive(steps,gates,start,end,trace_complete,existing):
    if not (math.isfinite(start) and math.isfinite(end) and end>start):raise ValueError('invalid window')
    region=existing._region(steps,start,end,trace_complete)
    n=count_crossings(gates,start,end)
    result={"region_"+name:region[name] if region['window_complete'] else None for name in REGION_NAMES}
    result.update(window_start_s=start,window_end_s=end,window_complete=region['window_complete'],
        extended_region_window=region,flow_1000m_crossings=n,flow_1000m_veh_h=n*3600/(end-start) if region['window_complete'] else None)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',nargs='+',type=Path,required=True)
    parser.add_argument('--target',nargs='+',required=True)
    parser.add_argument('--baseline',default='TM')
    parser.add_argument('--start',type=float,default=100.)
    parser.add_argument('--end',type=float,default=1800.)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('output already exists; use a new immutable attempt directory')
    records=[r for b in args.batch for r in summarize.protocol_records(b)]
    summarize.unique(records)
    cases=[summarize.load_case(r) for r in records]
    for case,record in zip(cases,records):
        case['case_analysis_status']=case_outcome(record)
        case['native_status_as_recorded']=record.get('status')
        case['worker_operation_status']=record.get('operation',{}).get('status')
        case['worker_operation_path']=record.get('operation',{}).get('path')
    _,traffic=seal_case.tools();existing=traffic.existing
    evidence=[]
    for case in cases:
        old=case['_run'];case['original_100_600_metrics']={name:old.get(name) for name in [*("region_"+n for n in REGION_NAMES),'flow_1000m_veh_h','flow_1000m_crossings']}
        extended=dict(old);case['extended_window_verified']=False
        if case['evidence_verified'] and case['protocol_verified']:
            folder=Path(case['evidence_dir']);seal=seal_case.read(folder/'seal.json');meta_path=folder/seal['traffic_metadata'];meta=seal_case.read(meta_path);ledger=meta_path.parent
            steps=read_steps(ledger/'region_steps.jsonl.gz');gates=read_gates(ledger/'gate_brackets.jsonl.gz')
            complete=(old['region_full']['window_complete'] and old['first_position_sample_s']<=args.start and old['last_position_sample_s']>=args.end)
            values=derive(steps,gates,args.start,args.end,complete,existing)
            # Retain a reproducibility check against the untouched original window.
            original=derive(steps,gates,100.,600.,old['region_window']['window_complete'],existing)
            for name,value in case['original_100_600_metrics'].items():
                actual=original.get(name)
                if isinstance(value,(int,float)) and not isinstance(value,bool):assert actual is not None and math.isclose(actual,value,rel_tol=1e-9,abs_tol=existing.TOLERANCE),name
                else:assert actual==value,name
            extended.update(values);case.update(values);case['extended_window_verified']=True
            evidence.append(dict(candidate=case['candidate'],mode=case['mode'],flow=case['flow'],seed=case['seed'],scenario=case['scenario'],
                evidence_dir=str(folder),ledger_dir=str(ledger),case_json_sha256=seal_case.sha(meta_path),
                ledger_sha256=meta['ledger_sha256'],source_method_sha256=seal['method_sha256'],
                ledger_rows=len(steps),first_interval_start_s=steps[0]['time_s'] if steps else None,last_interval_end_s=steps[-1]['end_s'] if steps else None,
                gate_observed_count=len(gates),trace_complete_input=complete,extended_window_complete=values['window_complete'],original_100_600_exactly_reconstructed=True))
        else:
            extended.update({name:None for name in [*("region_"+n for n in REGION_NAMES),'flow_1000m_veh_h']})
            case.update(window_start_s=args.start,window_end_s=args.end,window_complete=False)
        extended['attribution_eligible']=bool(extended.get('attribution_eligible') and case['extended_window_verified'] and extended.get('window_complete'))
        case['_run']=extended
    index=summarize.unique(cases);pairs=[]
    for target in args.target:
        for case in cases:
            if case['candidate']!=target or case['mode']!='transform':continue
            ref=index.get((args.baseline,case['flow'],case['seed'],case['scenario'],'noa'))
            a=ref['_run'] if ref else None;b=case['_run']
            pair=traffic.pair(a,b,target+'-NOA_extended_window','complete_strategy_same_following')
            pair.update(candidate=target,reference=args.baseline+'/noa',flow=case['flow'],seed=case['seed'],scenario=case['scenario'],window_start_s=args.start,window_end_s=args.end)
            for metric in report_paired.METRICS:
                pair['reference_'+metric]=a.get(metric) if a else None;pair['target_'+metric]=b.get(metric)
                pair['delta_'+metric]=existing._difference(a,b,metric,pair['pair_eligible'])
            pair['system_improvement_percent']=(-100*pair['delta_mean_system_time_s']/a['mean_system_time_s']) if pair['pair_eligible'] else None
            pairs.append(pair)
    groups=defaultdict(list)
    for p in pairs:groups[p['candidate'],p['flow'],p['scenario']].append(p)
    means=[]
    for (candidate,flow,scenario),rr in sorted(groups.items()):
        valid=all(r['pair_eligible'] for r in rr);m=dict(candidate=candidate,flow=flow,scenario=scenario,seeds=len(rr),eligible=valid)
        for metric in report_paired.METRICS:
            for prefix in ['reference_','target_','delta_']:m[prefix+metric]=report_paired.average([r[prefix+metric] for r in rr]) if valid else None
        m['system_improvement_percent']=-100*m['delta_mean_system_time_s']/m['reference_mean_system_time_s'] if valid else None
        means.append(m)
    args.output.mkdir(parents=True,exist_ok=False)
    traffic.write_rows(args.output/'per_case.csv',[{k:v for k,v in r.items() if not k.startswith('_')} for r in cases])
    traffic.write_rows(args.output/'paired_seeds.csv',pairs);traffic.write_rows(args.output/'flow_means.csv',means)
    seal_case.write(args.output/'ledger_index.json',evidence)
    summary=dict(cases=len(cases),planned_cases=len(records),protocol_verified=sum(r['protocol_verified'] for r in cases),evidence_verified=sum(r['evidence_verified'] for r in cases),
        extended_window_verified=sum(r['extended_window_verified'] for r in cases),window_complete=sum(r.get('window_complete') is True for r in cases),
        safe=sum(r.get('safe') is True for r in cases),drained=sum(r.get('all_completed') is True for r in cases),pairs=len(pairs),eligible_pairs=sum(p['pair_eligible'] for p in pairs),
        window_start_s=args.start,window_end_s=args.end,means=means,batches=[str(b.resolve()) for b in args.batch],
        method='existing._region(full sealed region_steps,start,end,complete); first observed gate times reconstructed from all sealed brackets',
        boundary='Region intervals clipped [start,end). Gate first crossings use original closed start<=t<=end.',
        nonwindow_metrics='TT/system/entry/fuel/segments/flags/lane changes remain original full-demand or full-trace values; not restricted to this time window.',
        no_positions_rescan=True,no_imputation_or_partial_completion=True,no_existing_evidence_changed=True)
    summary['worker_wallclock_timeouts']=sum(r['case_analysis_status']=='worker_wallclock_timeout_physical_completion_unknown' for r in cases)
    seal_case.write(args.output/'summary.json',summary)
    fmt=lambda x:'—' if x is None else f'{x:.5f}'
    lines=['# 延长窗口：复用封存账本','',f'区域积分窗口[{args.start:g},{args.end:g})；1000m首次越线沿原定义含两端。区域仍800≤x<1000、三道长度0.6车道公里，低速v<5m/s。TT/系统时间/燃油/分段时间/旗标沿用原全需求或全轨迹值，仅region和越线流量延长。缺样/不完整不补值；全部计划样本均列出，种子等权，target−NOA。','',
        '| 方法/流量 | eligible seeds | 系统时间NOA/候选(s) | 全窗区均速NOA/候选(m/s) | 全窗低速车辆秒NOA/候选 | 全窗越线流量NOA/候选(veh/h) |',
        '|---|---:|---|---|---|---|']
    for r in means:lines.append('| '+' | '.join([r['candidate']+'/'+str(r['flow']),str(r['seeds']) if r['eligible'] else '不完整',*(fmt(r['reference_'+k])+'/'+fmt(r['target_'+k]) for k in ['mean_system_time_s','region_mean_speed_mps','region_low_speed_vehicle_s','flow_1000m_veh_h'])])+' |')
    lines+=['','执行状态逐例保留case_analysis_status、原native status与worker operation路径。worker墙钟timeout/124与仿真max_time结束分开，native残留starting不表示仍在运行，也不推断物理已完成或算法未排空；未封存者不产生窗口指标。','',
        '全部案例、逐种子配对、均值与逐文件来源hash见同目录CSV/ledger_index.json/summary.json。原[100,600)数值另存original_100_600_metrics并逐项重建核对，不覆盖原工具或封包。','']
    (args.output/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['means','batches','method','nonwindow_metrics']}))
    return 0 if summary['extended_window_verified']==len(records) else 2

if __name__=='__main__':raise SystemExit(main())
