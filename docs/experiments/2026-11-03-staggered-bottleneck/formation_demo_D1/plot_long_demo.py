"""One plotting implementation for E2400/J22400, all actual states unchanged."""
import csv
import gzip
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Patch
import numpy as np

OUT=Path(__file__).resolve().parent
SKILL=Path('C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py')
spec=importlib.util.spec_from_file_location('academic_figure_style',SKILL)
style=importlib.util.module_from_spec(spec);spec.loader.exec_module(style)
theme=style.THEMES['nature'];colors=theme['colors'][:3]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none','legend.fontsize':7})
p=json.loads((OUT/'protocol.json').read_text())

def read(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def save(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=300,bbox_inches='tight',facecolor='white')
    fig.savefig(path.with_suffix('.svg'),bbox_inches='tight',facecolor='white');plt.close(fig)

def road(ax):
    style.apply_base_style(ax,theme)
    for y in [0,3.3,6.6,9.9]:ax.plot([0,1000 if y>6.6 else 2400],[y,y],c='#aaaaaa',lw=.55)
    ax.axvline(640,c='#777777',ls=':',lw=.7);ax.axvline(1000,c='#333333',ls='--',lw=.7)
    ax.add_patch(Rectangle((1000,6.6),1400,3.3,facecolor='#eeeeee',hatch='///',edgecolor='#cccccc',lw=.3))
    ax.set_xlim(0,2400);ax.set_ylim(0,9.9);ax.set_yticks([1.65,4.95,8.25]);ax.set_ylabel('y (m)')

for result in json.loads((OUT/'demo_results.json').read_text()):
    tag=result['version'];demo=result['demo'];folder=OUT/tag
    case=Path(result['case_dir'])
    initial={r['id']:r for r in json.loads((OUT/(demo+'_initial.json')).read_text())}
    with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:frames=[json.loads(s) for s in f]
    indexed={f['time_s']:f for f in frames}
    geometry=read(folder/(demo+'_geometry.csv.gz'))
    byid={k:[r for r in geometry if r['vehicle_id']==k] for k in initial}
    for kind,times in [('fixed',[frames[0]['time_s'],5.,10.,15.,20.]),('downstream',result['registered_downstream_times_s'])]:
        fig,axes=plt.subplots(len(times),1,figsize=(14,9 if kind=='fixed' else 12),sharex=True,layout='constrained')
        for ax,t in zip(axes,times):
            road(ax);states=indexed[t]['states'];absent=sorted(set(initial)-set(states))
            for k,s in states.items():
                ax.add_patch(Rectangle((s['x']-4,s['y']-.9),4,1.8,facecolor=colors[initial[k]['lane']],edgecolor='#333333',lw=.3))
                if kind=='downstream':ax.text(s['x'],s['y']+.9,k.replace('unformed_','').replace('formed_',''),fontsize=4.5,rotation=55,ha='left')
            prefix=f'anchor + {round(t-result["anchor_last_first1000_s"],1):g} s | ' if kind=='downstream' else ''
            ax.set_title(f'{prefix}t = {t:g} s | actually present = {len(states)}/{len(initial)} | exited initial IDs = {len(absent)}',loc='left',fontsize=9)
        axes[0].legend(handles=[Patch(facecolor=colors[i],label=f'Initial lane {i}') for i in range(3)],loc='upper right',ncol=3,frameon=False)
        axes[-1].set_xlabel('Measured front position x (m)')
        fig.suptitle(f'{tag} / {demo}: {kind} measured x-y snapshots (4.0 x 1.8 m bodies; axes scaled separately)',fontsize=11)
        save(fig,folder/(demo+'_'+kind+'_snapshots'))
    fig,axes=plt.subplots(3,3,figsize=(15,10),layout='constrained')
    for k,rr in byid.items():
        tt=[float(r['time_s']) for r in rr];c=colors[initial[k]['lane']]
        for ax,field in zip(axes[:,0],['x_m','y_m','speed_mps']):ax.plot(tt,[float(r[field]) for r in rr],c=c,lw=.55,alpha=.5)
    for ax,title,label in zip(axes[:,0],['All measured trajectories','Measured lateral motion','Measured speed'],['x (m)','y (m)','v (m/s)']):ax.set_title(title);ax.set_ylabel(label)
    axes[0,0].axhline(640,c='#777777',ls=':',lw=.6);axes[0,0].axhline(1000,c='#333333',ls='--',lw=.6)
    for i,k in enumerate(p['selected_geometry_ids'][demo]):
        rr=byid[k];tt=[float(r['time_s']) for r in rr];yy=[];last=None
        for r in rr:
            partner=r['front_id'];value=r['front_gap_minus_cth_D_m']
            yy.append(np.nan if not value or partner!=last else float(value));last=partner
        axes[i,1].plot(tt,yy,c='#3C5488',lw=1);axes[i,1].axhline(0,c='#555555',ls=':',lw=.7)
        axes[i,1].set_title(k+' / actual front',fontsize=9);axes[i,1].set_ylabel('Actual front gap - D(v) (m)')
        for lane in range(3):
            yy=[];last=None
            for r in rr:
                partner=r[f'adj_lane{lane}_id'];value=r[f'adj_lane{lane}_signed_dx_m']
                yy.append(np.nan if not value or partner!=last else float(value));last=partner
            axes[i,2].plot(tt,yy,c=colors[lane],lw=.8,label=f'neighbor lane {lane}')
        for d in [-15,15]:axes[i,2].axhline(d,c='#777777',ls=':',lw=.6)
        axes[i,2].set_title(k+' / nearest actual adjacent vehicle',fontsize=9);axes[i,2].set_ylabel('Raw signed dx (m)')
        axes[i,2].legend(frameon=False,loc='best')
    for ax in axes.flat:style.apply_base_style(ax,theme);ax.set_xlabel('Time (s)')
    fig.suptitle(f'{tag} / {demo}: unchanged raw trajectories; D(v)=5.5+0.8506944444v; lines break on partner change',fontsize=11)
    save(fig,folder/(demo+'_time_series'))
    fig,axes=plt.subplots(len(result['registered_downstream_times_s']),3,figsize=(15,16),layout='constrained')
    for i,t in enumerate(result['registered_downstream_times_s']):
        rr=[r for r in geometry if float(r['time_s'])==t]
        for r in rr:
            x=float(r['x_m']);c=colors[initial[r['vehicle_id']]['lane']];marker='o' if r['lane']=='0' else '^'
            axes[i,0].scatter(x,float(r['speed_mps']),c=c,marker=marker,s=10)
            if r['front_id']:axes[i,1].scatter(x,float(r['front_gap_minus_cth_D_m']),c=c,marker=marker,s=10)
            for lane in range(3):
                if r[f'adj_lane{lane}_id']:axes[i,2].scatter(x,float(r[f'adj_lane{lane}_signed_dx_m']),c=c,marker=marker,s=10)
        for j,title in enumerate(['Every present vehicle speed','Actual front gap - D(v), missing fronts omitted','Raw signed nearest adjacent dx']):
            axes[i,j].set_title(f't={t:g}s, n={len(rr)} / '+title,fontsize=8)
            style.apply_base_style(axes[i,j],theme);axes[i,j].set_xlim(0,2400);axes[i,j].set_xlabel('Measured x (m)')
        axes[i,0].axhline(28.8,c='#555555',ls=':',lw=.6);axes[i,0].set_ylabel('v (m/s)')
        axes[i,1].axhline(0,c='#555555',ls=':',lw=.6);axes[i,1].set_ylabel('Front gap - D(v) (m)')
        for d in [-15,15]:axes[i,2].axhline(d,c='#777777',ls=':',lw=.6)
        axes[i,2].set_ylabel('Raw signed dx (m)')
    fig.suptitle(f'{tag} / {demo}: all present states at registered anchor + 0/5/10/15/20/25 s; color = initial lane, marker = actual lane',fontsize=11)
    save(fig,folder/(demo+'_downstream_all_states'))
print(json.dumps(dict(figure_pairs=16,same_plot_functions_for_E2400_J22400=True,png_dpi=300,svg_text=True)))
