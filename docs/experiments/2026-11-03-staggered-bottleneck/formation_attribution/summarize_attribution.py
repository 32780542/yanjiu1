"""Project the verified merged report; no simulation or controller execution."""
import csv
import hashlib
import gzip
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "tmp/staggered_bottleneck/20261103_E_formation_ablation180_18_analysis"


def write(name, rows):
    with (OUT/name).open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


raw=list(csv.DictReader((ANALYSIS/'per_case.csv').open(encoding='utf-8-sig')))
selected=[]
for r in raw:
    if float(r['flow']) not in [2000,2250,2500] or r['scenario']!='lane_drop':continue
    candidate=r['candidate']
    if candidate=='TM':profile='NOA' if r['mode']=='noa' else 'TM'
    elif candidate in ['NC','ENF','ENP','ENB'] and r['mode']=='transform':profile='E' if candidate=='NC' else candidate
    else:continue
    full=json.loads(r['region_full'])
    trips=json.loads((Path(r['run_dir'])/'trips.json').read_text())
    ledger=next((Path(r['evidence_dir'])/'traffic/cases').iterdir())
    vehicles=json.load(gzip.open(ledger/'vehicles.json.gz','rt'))
    gates={v['vehicle_id']:v['gates']['1100']['time_s'] for v in vehicles}
    lane_counts=[0,0,0]
    for trip in trips:
        lane=trip['lane']
        for event in trip['lane_events']:
            if event['time_s'] <= gates[trip['vehicle_id']]:lane=event['to_lane']
        lane_counts[lane]+=1
    assert sum(lane_counts)==len(trips) and lane_counts[2]==0
    selected.append(dict(profile=profile,actual_candidate=candidate,flow=float(r['flow']),seed=int(r['seed']),
        safe=r['safe'],all_completed=r['all_completed'],requested=int(r['requested']),
        mean_travel_time_s=float(r['mean_travel_time_s']),mean_system_time_s=float(r['mean_system_time_s']),
        fuel_g_per_km=float(r['fuel_g_per_km']),mean_entry_wait_s=float(r['mean_entry_wait_s']),
        mean_segment_640_1100_s=float(r['mean_segment_640_1100_s']),
        lane_changes=int(r['lane_changes']),lane_change_completions=int(r['lane_change_completions']),
        full_region_low_speed_vehicle_s=full['low_speed_vehicle_s'],
        full_region_mean_speed_mps=full['mean_speed_mps'],
        full_region_vehicle_s=full['vehicle_s'],full_region_exposure_end_s=full['end_s'],
        actual_end_s=float(r['actual_end_s']),
        gate1100_lane0_n=lane_counts[0],gate1100_lane1_n=lane_counts[1],
        gate1100_lane0_share_pct=lane_counts[0]/len(trips)*100,
        flag_participation_rate=float(r['flag_participation_rate']),
        flag_mean_episode_s=float(r['flag_mean_episode_s']) if r['flag_mean_episode_s'] not in ('','None','null') else None,
        fixed_region_window_complete=json.loads(r['region_window'])['window_complete'],
        trips_sha256=r['trips_sha256'],run_dir=r['run_dir']))
assert len(selected)==36
assert all(r['safe']=='True' and r['all_completed']=='True' for r in selected)
index={(r['profile'],r['flow'],r['seed']):r for r in selected}
assert len(index)==36
write('per_case.csv',selected)
metrics=['mean_travel_time_s','mean_system_time_s','fuel_g_per_km','mean_entry_wait_s',
         'mean_segment_640_1100_s','lane_change_completions','full_region_low_speed_vehicle_s',
         'full_region_mean_speed_mps','actual_end_s','gate1100_lane0_share_pct']
means=[]
for flow in [2000,2250,2500]:
    for profile in ['NOA','TM','E','ENF','ENP','ENB']:
        rows=[index[profile,flow,seed] for seed in [1,4]]
        means.append(dict(profile=profile,flow=flow,seeds=2,**{k:statistics.mean(r[k] for r in rows) for k in metrics}))
write('flow_means.csv',means)
differences=[]
comparisons=[('fill_with_phase','E','ENF'),('fill_without_phase_speed','ENP','ENB'),
             ('phase_with_fill','E','ENP'),('phase_without_fill','ENF','ENB'),
             ('E_minus_NOA','E','NOA'),('ENB_minus_NOA','ENB','NOA')]
for label,on,off in comparisons:
    for flow in [2000,2250,2500]:
        for seed in [1,4]:
            a,b=index[on,flow,seed],index[off,flow,seed]
            assert a['requested']==b['requested']
            differences.append(dict(comparison=label,retained=on,disabled_or_reference=off,flow=flow,seed=seed,
                **{k:a[k]-b[k] for k in metrics}))
write('seed_effects.csv',differences)
effects=[]
for label,on,off in comparisons:
    for flow in [2000,2250,2500]:
        rows=[r for r in differences if r['comparison']==label and r['flow']==flow]
        effects.append(dict(comparison=label,flow=flow,**{k:statistics.mean(r[k] for r in rows) for k in metrics}))
write('flow_effects.csv',effects)
interactions=[]
for flow in [2000,2250,2500]:
    for seed in [1,4]:
        a,b,c,d=[index[profile,flow,seed] for profile in ['E','ENF','ENP','ENB']]
        interactions.append(dict(flow=flow,seed=seed,**{k:a[k]-b[k]-c[k]+d[k] for k in metrics}))
write('interactions.csv',interactions)
summary=json.loads((ANALYSIS/'summary.json').read_text())
assert summary['evidence_verified_count']==summary['case_count']==74
audit=dict(selected_cases=36,merged_cases=74,all_selected_safe_drained=True,
    merged_analysis=str(ANALYSIS),reference='NC (behavior-equivalent E)',
    retained_merged_failed_cases=summary['failed_cases'],
    fixed_window_complete_selected=sum(r['fixed_region_window_complete'] for r in selected),
    metric_note='full-region low-speed exposure integrates until each run drains; not a common fixed time window or capacity',
    source_sha256={name:hashlib.sha256((ANALYSIS/name).read_bytes()).hexdigest() for name in ['per_case.csv','paired.csv','summary.json']},
    analysis_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(OUT/'verification.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False))
