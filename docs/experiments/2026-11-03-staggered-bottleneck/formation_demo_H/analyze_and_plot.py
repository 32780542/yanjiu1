"""Render measured geometry only; no formation classifier or simulator imports."""
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import statistics as st
import tarfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
RUNS=ROOT/'tmp/staggered_bottleneck/20261103_H_formation_demo'
protocol=json.loads((OUT/'protocol.json').read_text())
SKILL=Path('C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py')
spec=importlib.util.spec_from_file_location('academic_figure_style',SKILL)
style=importlib.util.module_from_spec(spec);spec.loader.exec_module(style)
theme=style.THEMES['nature'];colors=theme['colors'][:3]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none',
                     'axes.titlesize':10,'axes.labelsize':9,'legend.fontsize':8})
HEADWAY=(30-5.5)/28.8


def csv_write(name, rows):
    if name.endswith('.gz'):
        stream=gzip.open(OUT/name,'wt',encoding='utf-8',newline='')
    else:stream=(OUT/name).open('w',encoding='utf-8-sig',newline='')
    with stream as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def save(fig, name):
    fig.savefig(OUT/(name+'.png'),dpi=300,bbox_inches='tight',facecolor='white')
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',facecolor='white')
    plt.close(fig)


def road(ax):
    style.apply_base_style(ax,theme)
    ax.axvline(640,c='#777777',ls=':',lw=.9)
    ax.axvline(1000,c='#333333',ls='--',lw=.9)
    for y in [0,3.3,6.6,9.9]:
        ax.plot([0,1000 if y>6.6 else 1200],[y,y],c='#aaaaaa',lw=.6)
    ax.add_patch(Rectangle((1000,6.6),200,3.3,facecolor='#eeeeee',hatch='///',edgecolor='#cccccc',lw=.4))
    ax.set_xlim(-10,1210);ax.set_ylim(0,9.9);ax.set_yticks([1.65,4.95,8.25]);ax.set_ylabel('y (m)')


def summary_stats(values):
    return (None,None,None) if not values else (min(values),st.median(values),max(values))


def geometry(t,states,actions):
    result=[]
    for k,s in states.items():
        # Current physical corridor, including measured straddling vehicles.
        front=min((j for j,v in states.items() if j!=k and v['x']>s['x']
                   and abs(v['y']-(s['lane']+.5)*3.3)<(1.8+3.3)/2),
                  key=lambda j:(states[j]['x'],states[j]['y'],states[j]['speed']),default=None)
        gap=None if front is None else states[front]['x']-s['x']
        desired=5.5+HEADWAY*s['speed']
        row=dict(time_s=t,vehicle_id=k,x_m=s['x'],y_m=s['y'],speed_mps=s['speed'],lane=s['lane'],
            reason=actions[k]['reason'],front_id=front,front_gap_m=gap,cth_D_m=desired,
            front_gap_minus_cth_D_m=None if gap is None else gap-desired,
            front_inside_existing_50m_following_range=gap is not None and gap<=50)
        for lane in range(3):
            other=min((j for j,v in states.items() if j!=k and v['lane']==lane),
                      key=lambda j:(abs(states[j]['x']-s['x']),states[j]['x'],states[j]['y'],states[j]['speed']),default=None) if abs(lane-s['lane'])==1 else None
            row[f'adj_lane{lane}_id']=other
            row[f'adj_lane{lane}_signed_dx_m']=None if other is None else states[other]['x']-s['x']
        result.append(row)
    return result


all_summaries=[];all_downstream=[];all_snapshot_states=[];tail_states=[];case_summaries=[];archive_files={}
for name in ['unformed24','formed45']:
    case=next((RUNS/name).glob('20*'))
    initial=json.loads((OUT/(name+'_initial.json')).read_text());initial_by={r['id']:r for r in initial}
    result=json.loads((case/'result.json').read_text())
    assert result['safe'] and result['all_completed'] and result['collisions']==result['teleports']==0
    assert result['source_sha256']['noa/native_rules.py']==protocol['rules_sha256']
    trips=json.loads((case/'trips.json').read_text())
    assert all(r['entered_s']==0 for r in trips)
    frames=[json.loads(line) for line in gzip.open(case/'diagnostic.jsonl.gz','rt')]
    positions=[json.loads(line) for line in gzip.open(case/'positions.jsonl.gz','rt')]
    assert len(frames)==len(positions)
    for f,p in zip(frames,positions):
        assert f['time_s']==p['time_s']
        assert {k:[v['x'],v['y'],v['speed'],v['acceleration']] for k,v in f['states'].items()}==p['states']
        assert {k:v['formation_state'] for k,v in f['actions'].items()}==p['formation_states']
    first=frames[0]
    assert set(first['states'])==set(initial_by)
    assert all(first['states'][k]['x']==r['x'] and first['states'][k]['speed']==r['speed'] for k,r in initial_by.items())
    seen1100=set();tail_index=None
    for i,f in enumerate(frames):
        seen1100.update(k for k,s in f['states'].items() if s['x']>=1100)
        if len(seen1100)==len(initial_by):tail_index=i;break
    assert tail_index is not None
    tail_time=frames[tail_index]['time_s']
    frame_index={round(f['time_s'],6):i for i,f in enumerate(frames)}
    snapshot_times=[first['time_s'],5.,10.,15.,20.,tail_time]
    tail_times=[round(tail_time-1,1),tail_time,round(tail_time+1,1)]
    selected_times=set(snapshot_times+tail_times)
    rows=[];bytime={}
    for f in frames:
        gg=geometry(f['time_s'],f['states'],f['actions']);rows.extend(gg);bytime[f['time_s']]=gg
    csv_write(name+'_geometry.csv.gz',rows)
    for t in sorted(selected_times):
        f=frames[frame_index[t]];gg=bytime[t]
        gaps=[r['front_gap_m'] for r in gg if r['front_gap_m'] is not None]
        errors=[r['front_gap_minus_cth_D_m'] for r in gg if r['front_gap_minus_cth_D_m'] is not None]
        gmin,gmed,gmax=summary_stats(gaps);emin,emed,emax=summary_stats(errors)
        all_summaries.append(dict(demo=name,time_s=t,frame_index=frame_index[t],n=len(gg),
            actual_front_n=len(gaps),isolated_or_front_exited_n=len(gg)-len(gaps),
            front_gap_min_m=gmin,front_gap_median_m=gmed,front_gap_max_m=gmax,
            cth_error_min_m=emin,cth_error_median_m=emed,cth_error_max_m=emax))
        for r in gg:
            if t in snapshot_times:all_snapshot_states.append(dict(demo=name,**r))
            if t in tail_times:tail_states.append(dict(demo=name,**r))
        for cutoff in [1000,1100]:
            downstream=[r for r in gg if r['x_m']>=cutoff and r['lane']<2]
            errors=[r['front_gap_minus_cth_D_m'] for r in downstream if r['front_id'] is not None]
            emin,emed,emax=summary_stats(errors)
            vmin,vmed,vmax=summary_stats([r['speed_mps'] for r in downstream])
            all_downstream.append(dict(demo=name,time_s=t,cutoff_x_m=cutoff,
                n_lane0_1=len(downstream),n_lane2_at_or_beyond=sum(r['x_m']>=cutoff and r['lane']==2 for r in gg),
                n_with_actual_front=len(errors),n_without_actual_front=len(downstream)-len(errors),
                n_front_within_50=sum(r['front_inside_existing_50m_following_range'] for r in downstream),
                speed_min_mps=vmin,speed_median_mps=vmed,speed_max_mps=vmax,
                cth_error_min_m=emin,cth_error_median_m=emed,cth_error_max_m=emax))
    # Full-road snapshots, measured front position minus actual 4 m body length.
    fig,axes=plt.subplots(6,1,figsize=(14,10.5),sharex=True,layout='constrained')
    for ax,t in zip(axes,snapshot_times):
        f=frames[frame_index[t]];road(ax)
        for k,s in f['states'].items():
            ax.add_patch(Rectangle((s['x']-4,s['y']-.9),4,1.8,facecolor=colors[initial_by[k]['lane']],edgecolor='#333333',lw=.35))
        label='first recorded initial geometry' if t==first['time_s'] else 'all vehicles have passed 1100 m' if t==tail_time else 'fixed snapshot'
        ax.set_title(f't = {t:g} s | n on road = {len(f["states"])} | {label}',loc='left')
    axes[-1].set_xlabel('Measured front position x (m)')
    fig.suptitle(f'H / {name}: measured x-y snapshots (body dimensions 4.0 x 1.8 m; axes scaled separately)',fontsize=12)
    axes[0].legend(handles=[Patch(color=colors[l],label=f'Initial lane {l}') for l in range(3)],loc='upper right',ncol=3,frameon=False)
    save(fig,name+'_snapshots')
    # Continuous geometry: no modulo, no snapping, gaps when partner identity changes.
    fig,axes=plt.subplots(3,3,figsize=(15,10),layout='constrained')
    times=np.array([f['time_s'] for f in frames])
    perid={k:[] for k in initial_by}
    for r in rows:perid[r['vehicle_id']].append(r)
    for k,rr in perid.items():
        c=colors[initial_by[k]['lane']];tt=[r['time_s'] for r in rr]
        axes[0,0].plot(tt,[r['x_m'] for r in rr],c=c,alpha=.55,lw=.65)
        axes[1,0].plot(tt,[r['y_m'] for r in rr],c=c,alpha=.55,lw=.65)
        axes[2,0].plot(tt,[r['speed_mps'] for r in rr],c=c,alpha=.55,lw=.65)
    for ax,title,ylabel in zip(axes[:,0],['All measured trajectories','Measured lateral motion','Measured speed'],['x (m)','y (m)','v (m/s)']):
        ax.set_title(title);ax.set_ylabel(ylabel)
    axes[0,0].axhline(640,c='#777777',ls=':',lw=.7);axes[0,0].axhline(1000,c='#555555',ls='--',lw=.7)
    for i,k in enumerate(protocol['selected_geometry_ids'][name]):
        rr=perid[k];tt=[r['time_s'] for r in rr]
        yy=[];last=None
        for r in rr:
            partner=r['front_id'];value=r['front_gap_minus_cth_D_m']
            yy.append(np.nan if value is None or partner!=last else value);last=partner
        axes[i,1].plot(tt,yy,c='#3C5488',lw=1)
        axes[i,1].axhline(0,c='#555555',ls=':',lw=.7)
        axes[i,1].set_title(k+' / actual front')
        axes[i,1].set_ylabel('Actual front gap - D(v) (m)')
        for lane in range(3):
            yy=[];last=None
            for r in rr:
                partner=r[f'adj_lane{lane}_id'];value=r[f'adj_lane{lane}_signed_dx_m']
                yy.append(np.nan if value is None or partner!=last else value);last=partner
            axes[i,2].plot(tt,yy,c=colors[lane],lw=.9,label=f'neighbor lane {lane}')
        axes[i,2].axhline(15,c='#777777',ls=':',lw=.6);axes[i,2].axhline(-15,c='#777777',ls=':',lw=.6)
        axes[i,2].set_title(k+' / nearest adjacent vehicle')
        axes[i,2].set_ylabel('Raw signed dx (m)')
        axes[i,2].legend(loc='best',frameon=False,fontsize=7)
    for ax in axes.flat:
        style.apply_base_style(ax,theme);ax.set_xlabel('Time (s)')
    fig.suptitle(f'H / {name}: raw time series; D(v)=5.5+0.8506944444v; lines break on partner change',fontsize=12)
    save(fig,name+'_time_series')
    # Tail views deliberately retain only actually remaining vehicles.
    fig,axes=plt.subplots(3,1,figsize=(14,6),sharex=True,layout='constrained')
    for ax,t in zip(axes,tail_times):
        f=frames[frame_index[t]];road(ax)
        ax.set_xlim(900,1210)
        for k,s in f['states'].items():
            ax.add_patch(Rectangle((s['x']-4,s['y']-.9),4,1.8,facecolor=colors[initial_by[k]['lane']],edgecolor='#333333',lw=.45))
            ax.text(s['x'],s['y']+.95,k.replace('unformed_','').replace('formed_',''),fontsize=7,rotation=15)
        ax.axvline(1100,c='#555555',ls=':',lw=.8)
        ax.set_title(f't = {t:g} s | actual remaining vehicles = {len(f["states"])}',loc='left')
    axes[-1].set_xlabel('Measured front position x (m)')
    fig.suptitle(name+': before / at / after last vehicle passes 1100 m; exited vehicles are absent',fontsize=11)
    save(fig,name+'_tail')
    case_summaries.append(dict(demo=name,case_dir=str(case),n=len(initial),first_recorded_s=first['time_s'],
        all_entered_s_zero=True,first_frame_matches_requested_positions_exactly=True,last_vehicle_1100_s=tail_time,
        onroad_n_at_last1100=len(frames[tail_index]['states']),
        **{k:result[k] for k in ['safe','all_completed','actual_end_s','mean_travel_time_s','collisions','teleports','lane_change_completions','formation_state','ending_lane_observed_vehicles','ending_lane_completed_before_drop','ending_lane_completion_before_drop_rate']}))
    for path in case.rglob('*'):
        if path.is_file():archive_files[name+'/'+str(path.relative_to(case)).replace('\\','/')]=path

csv_write('snapshot_summary.csv',all_summaries)
csv_write('downstream_cth_summary.csv',all_downstream)
csv_write('snapshot_states.csv',all_snapshot_states)
csv_write('tail_window_states.csv',tail_states)
(OUT/'demo_results.json').write_text(json.dumps(case_summaries,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
for name in ['protocol.json','unformed24_initial.json','formed45_initial.json','prepare_demo.py','analyze_and_plot.py','initial_equilibrium_check.json']:
    archive_files['analysis/'+name]=OUT/name
manifest={name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in archive_files.items()}
archive=OUT/'evidence_reviewed.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz') as t:
    for name,path in sorted(archive_files.items()):t.add(path,arcname=name,recursive=False)
    raw=json.dumps(manifest,indent=2,ensure_ascii=False).encode();info=tarfile.TarInfo('manifest.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
with tarfile.open(archive) as t:
    for name,expected in manifest.items():
        raw=t.extractfile(name).read();assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
audit=dict(cases=2,position_diagnostic_all_frames_exact=True,initial_requests_physically_observed=True,
    raw_frames={s['demo']:len([1 for _ in gzip.open(Path(s['case_dir'])/'positions.jsonl.gz','rt')]) for s in case_summaries},
    archive_members_verified=len(manifest),archive_bytes=archive.stat().st_size,
    archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    academic_skill_style_sha256=hashlib.sha256(SKILL.read_bytes()).hexdigest(),
    analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    no_geometry_success_threshold=True,no_modulo_or_position_reordering=True)
(OUT/'verification.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False))
