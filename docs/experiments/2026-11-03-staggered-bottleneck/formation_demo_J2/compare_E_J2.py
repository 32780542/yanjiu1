"""Measured same-input E/J2 comparison; raw signed dx, no formation success metric."""
import csv
import gzip
import json
from pathlib import Path
import statistics as st

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
E=OUT.parent/'formation_demo'
colors={'E':'#E64B35','J2':'#3C5488'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none'})


def write(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


summary=[];fixed_head=[];current_head=[];frame_deltas=[];events=[]
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
for row_index,demo in enumerate(['unformed24','formed45']):
    records={};firstexit={};first640={}
    rank=7 if demo=='unformed24' else 14
    initial_head0=f'{"unformed" if demo=="unformed24" else "formed"}_l0_r{rank:02d}'
    initial_head1=f'{"unformed" if demo=="unformed24" else "formed"}_l1_r{rank:02d}'
    for version,folder in [('E',E),('J2',OUT)]:
        assert (folder/(demo+'_initial.json')).read_bytes()==(E/(demo+'_initial.json')).read_bytes()
        case=next((ROOT/f'tmp/staggered_bottleneck/20261103_{version}_formation_demo'/demo).glob('20*'))
        records[version]=[json.loads(line) for line in gzip.open(case/'diagnostic.jsonl.gz','rt')]
        result=json.loads((case/'result.json').read_text());trips=json.loads((case/'trips.json').read_text())
        firstexit[version]=min(t['exited_s'] for t in trips)
        first640[version]=next(f['time_s'] for f in records[version] if any(s['x']>=640 for s in f['states'].values()))
        summary.append(dict(demo=demo,version=version,mean_tt_s=result['mean_travel_time_s'],
            end_s=result['actual_end_s'],first_vehicle_640_s=first640[version],first_exit_s=firstexit[version],
            lane_change_completions=result['lane_change_completions'],
            flag_participation_rate=result['formation_state']['participation_rate']))
        xx=[];yy=[];hx=[];hy=[];last_pair=None
        for f in records[version]:
            t=f['time_s'];states=f['states']
            if initial_head0 in states and initial_head1 in states:
                dx=states[initial_head1]['x']-states[initial_head0]['x']
                fixed_head.append(dict(demo=demo,version=version,time_s=t,left_id=initial_head0,right_id=initial_head1,signed_x1_minus_x0_m=dx))
                xx.append(t);yy.append(dx)
            heads=[max((k for k,s in states.items() if s['lane']==lane),key=lambda k:(states[k]['x'],states[k]['y'],states[k]['speed']),default=None) for lane in [0,1]]
            if all(heads):
                pair=tuple(heads);dx=states[heads[1]]['x']-states[heads[0]]['x']
                current_head.append(dict(demo=demo,version=version,time_s=t,lane0_head_id=heads[0],lane1_head_id=heads[1],signed_x1_minus_x0_m=dx))
                hx.append(t);hy.append(dx if pair==last_pair else np.nan);last_pair=pair
        axes[row_index,0].plot(xx,yy,c=colors[version],label=version,lw=1.15)
        axes[row_index,1].plot(hx,hy,c=colors[version],label=version,lw=1.15)
        for ax in axes[row_index]:
            ax.axvline(first640[version],c=colors[version],ls=':',lw=.6,alpha=.7)
            ax.axvline(firstexit[version],c=colors[version],ls='--',lw=.6,alpha=.7)
    indexed={v:{f['time_s']:f for f in records[v]} for v in records}
    for t in sorted(set(indexed['E'])&set(indexed['J2'])):
        a,b=indexed['E'][t]['states'],indexed['J2'][t]['states'];common=set(a)&set(b)
        frame_deltas.append(dict(demo=demo,time_s=t,E_n=len(a),J2_n=len(b),common_n=len(common),
            max_abs_x_delta_m=max((abs(a[k]['x']-b[k]['x']) for k in common),default=0),
            max_abs_y_delta_m=max((abs(a[k]['y']-b[k]['y']) for k in common),default=0),
            max_abs_speed_delta_mps=max((abs(a[k]['speed']-b[k]['speed']) for k in common),default=0)))
    for version,folder in [('E',E),('J2',OUT)]:
        observations=list(csv.DictReader((folder/'per_vehicle_downstream.csv').open(encoding='utf-8-sig')))
        r=max((r for r in observations if r['demo']==demo and r['first_observed_cutoff_x_m']=='1100' and r['front_id']),key=lambda r:float(r['front_gap_minus_cth_D_m']))
        f=indexed[version][float(r['time_s'])];a=f['actions'][r['vehicle_id']]
        events.append(dict(version=version,**r,command_speed_mps=a['speed'],action_reference_private_track=a['reference']))
    axes[row_index,0].set_title(demo+': same initial lane0/lane1 head identities')
    axes[row_index,1].set_title(demo+': actual current lane0/lane1 heads (identity breaks)')
for ax in axes.flat:
    ax.axhline(15,c='#888888',ls=':',lw=.7);ax.axhline(-15,c='#888888',ls=':',lw=.7)
    ax.set_xlabel('Time (s)');ax.set_ylabel('Raw signed x(lane1) - x(lane0) (m)')
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2,ls='--');ax.legend(frameon=False)
fig.suptitle('E versus J2 / actual head positions; vertical dotted = first x640, dashed = first vehicle exit',fontsize=11)
fig.savefig(OUT/'E_J2_head_signed_dx.png',dpi=300,bbox_inches='tight')
fig.savefig(OUT/'E_J2_head_signed_dx.svg',bbox_inches='tight');plt.close(fig)
write('E_J2_demo_summary.csv',summary)
write('E_J2_fixed_head_signed_dx.csv',fixed_head)
write('E_J2_current_head_signed_dx.csv',current_head)
write('E_J2_frame_differences.csv',frame_deltas)
write('E_J2_large_gap_events.csv',events)
print({'runs_compared':4,'frame_comparisons':len(frame_deltas),'actual_head_records':len(current_head)})
