"""Every original post-1000 raw frame before first exit; fixed +20/+25 only."""
import ast
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics as st
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT=Path(__file__).resolve().parent;BASE=OUT.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tree=ast.parse((BASE/'formation_demo/analyze_and_plot.py').read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='geometry')
env={'HEADWAY':(30-5.5)/28.8};exec(compile(ast.Module(body=[node],type_ignores=[]),'original_geometry','exec'),env);geometry=env['geometry']
spec=importlib.util.spec_from_file_location('figure_style',Path('C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py'))
style=importlib.util.module_from_spec(spec);spec.loader.exec_module(style);theme=style.THEMES['nature'];colors=theme['colors']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'svg.fonttype':'none'})
cases=[]
for tag,folder in [('E2400','formation_demo_long'),('J22400','formation_demo_long'),('L2400','formation_demo_L_long'),('M2400','formation_demo_M_long')]:
    cases.extend({**r,'folder':folder} for r in json.loads((BASE/folder/'demo_results.json').read_text()) if r['version']==tag)
summary=[];extras=[];extra_states=[];pairs=[];index={};metadata=[]
for run in cases:
    tag=run['version'];demo=run['demo'];case=Path(run['case_dir']);initial=json.loads((BASE/run['folder']/(demo+'_initial.json')).read_text());ids={r['id'] for r in initial}
    trips=json.loads((case/'trips.json').read_text());first_exit=min(r['exited_s'] for r in trips)
    with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=list(map(json.loads,f))
    seen=set()
    for f in ff:
        seen.update(k for k,s in f['states'].items() if s['x']>=1000)
        if seen==ids:anchor=f['time_s'];break
    assert anchor==run['anchor_last_first1000_s']
    frame_map={f['time_s']:f for f in ff};index[tag,demo]=frame_map
    dynamic=[f for f in ff if anchor<=f['time_s']<first_exit]
    for f in dynamic:
        assert set(f['states'])==ids
        gg=geometry(f['time_s'],f['states'],f['actions']);err=[r['front_gap_minus_cth_D_m'] for r in gg if r['front_id'] is not None]
        cross=[]
        for r in gg:
            for lane in range(3):
                if r[f'adj_lane{lane}_id'] is not None:
                    dx=r[f'adj_lane{lane}_signed_dx_m'];cross.append(dx)
                    pairs.append(dict(version=tag,demo=demo,time_s=f['time_s'],anchor_offset_s=round(f['time_s']-anchor,1),vehicle_id=r['vehicle_id'],peer_id=r[f'adj_lane{lane}_id'],raw_signed_dx_m=dx))
        speeds=[s['speed'] for s in f['states'].values()]
        summary.append(dict(version=tag,demo=demo,time_s=f['time_s'],anchor_offset_s=round(f['time_s']-anchor,1),initial_n=len(ids),onroad_n=len(gg),
            cth_front_n=len(err),cth_error_min=min(err),cth_error_median=st.median(err),cth_error_max=max(err),
            raw_signed_adj_dx_min=min(cross),raw_signed_adj_dx_median=st.median(cross),raw_signed_adj_dx_max=max(cross),
            v_min=min(speeds),v_median=st.median(speeds),v_max=max(speeds)))
    for offset in [20,25]:
        t=round(anchor+offset,1);f=frame_map.get(t)
        states=f['states'] if f else {};gg=geometry(t,states,f['actions']) if f else []
        err=[r['front_gap_minus_cth_D_m'] for r in gg if r['front_id'] is not None]
        cross=[r[f'adj_lane{i}_signed_dx_m'] for r in gg for i in range(3) if r[f'adj_lane{i}_id'] is not None]
        extras.append(dict(version=tag,demo=demo,anchor_offset_s=offset,time_s=t,initial_n=len(ids),onroad_n=len(states),absent_initial_ids=sorted(ids-set(states)),
            any_initial_exit_at_or_before_t=first_exit<=t,all_initial_present=set(states)==ids,cth_front_n=len(err),
            cth_error_min=min(err) if err else None,cth_error_median=st.median(err) if err else None,cth_error_max=max(err) if err else None,
            raw_signed_adj_dx_min=min(cross) if cross else None,raw_signed_adj_dx_median=st.median(cross) if cross else None,raw_signed_adj_dx_max=max(cross) if cross else None))
        extra_states.extend(dict(version=tag,demo=demo,anchor_offset_s=offset,**r) for r in gg)
    metadata.append(dict(version=tag,demo=demo,case_dir=str(case),anchor_s=anchor,first_actual_exit_s=first_exit,continuous_first_s=dynamic[0]['time_s'],continuous_last_s=dynamic[-1]['time_s'],continuous_frames=len(dynamic),all_initial_present_through_all_dynamic_frames=True,
        diagnostic_sha256=sha(case/'diagnostic.jsonl.gz'),positions_sha256=sha(case/'positions.jsonl.gz'),initial_sha256=sha(BASE/run['folder']/(demo+'_initial.json'))))

def write(path,rr):
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'wt',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
write(OUT/'all_pre_exit_frame_statistics.csv',summary);write(OUT/'all_actual_raw_cross_pairs.csv.gz',pairs)
write(OUT/'fixed_extra_20_25_summary.csv',extras);write(OUT/'fixed_extra_20_25_states.csv',extra_states)
(OUT/'source_index.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
tags=['E2400','J22400','L2400','M2400']
def save(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=300,bbox_inches='tight',facecolor='white');fig.savefig(path.with_suffix('.svg'),bbox_inches='tight',facecolor='white');plt.close(fig)
for demo in ['unformed24','formed45']:
    fig,axes=plt.subplots(3,4,figsize=(17,10),layout='constrained')
    for col,tag in enumerate(tags):
        rr=[r for r in summary if r['version']==tag and r['demo']==demo];tt=[r['anchor_offset_s'] for r in rr]
        for ax in axes[:,col]:style.apply_base_style(ax,theme)
        for key,color in [('max',colors[0]),('median',colors[2]),('min',colors[1])]:
            axes[0,col].plot(tt,[r['cth_error_'+key] for r in rr],label=key,color=color,lw=1)
            axes[1,col].plot(tt,[r['raw_signed_adj_dx_'+key] for r in rr],label=key,color=color,lw=1)
            axes[2,col].plot(tt,[r['v_'+key] for r in rr],label=key,color=color,lw=1)
        for ax in axes[:2,col]:ax.axhline(0,color='#777777',lw=.6,ls=':')
        axes[1,col].axhline(15,color='#777777',lw=.6,ls=':');axes[1,col].axhline(-15,color='#777777',lw=.6,ls=':')
        axes[2,col].axhline(28.8,color='#777777',lw=.6,ls=':')
        axes[0,col].set_title(tag+' / all initial vehicles present')
        axes[0,col].set_ylabel('Actual front gap - D(v) (m)');axes[1,col].set_ylabel('Raw signed nearest adjacent dx (m)');axes[2,col].set_ylabel('Every-vehicle speed (m/s)');axes[2,col].set_xlabel('Time since last initial vehicle crossed 1000 m (s)')
        axes[0,col].legend(frameon=False,ncol=3,fontsize=7)
    fig.suptitle(demo+': every original frame after tail1000 and strictly before first actual exit; no convergence deadline',fontsize=11)
    save(fig,OUT/(demo+'_continuous_dynamics'))
    fig,axes=plt.subplots(8,1,figsize=(15,14),sharex=True,layout='constrained')
    for ax,r in zip(axes,[r for r in extras if r['demo']==demo]):
        style.apply_base_style(ax,theme)
        f=index[r['version'],demo].get(r['time_s']);ss=f['states'] if f else {}
        for y in [0,3.3,6.6,9.9]:ax.plot([0,1000 if y>6.6 else 2400],[y,y],color='#bbbbbb',lw=.4)
        ax.axvline(640,c='#777777',ls=':',lw=.6);ax.axvline(1000,c='#555555',ls='--',lw=.6)
        for k,s in ss.items():
            ax.add_patch(Rectangle((s['x']-4,s['y']-.9),4,1.8,facecolor=colors[s['lane']],edgecolor='#333333',lw=.2))
        ax.set_xlim(0,2400);ax.set_ylim(0,9.9);ax.set_yticks([1.65,4.95,8.25]);ax.set_ylabel('y (m)')
        ax.set_title(f'{r["version"]} +{r["anchor_offset_s"]} s / t={r["time_s"]:.1f} / actual {r["onroad_n"]}/{r["initial_n"]} / any prior exit={r["any_initial_exit_at_or_before_t"]}',loc='left',fontsize=8)
    axes[-1].set_xlabel('Measured actual front x (m)');fig.suptitle(demo+': fixed additional +20/+25 frames; actual survivors, no completion imputation',fontsize=11)
    save(fig,OUT/(demo+'_fixed_extra_20_25_xy'))
print(json.dumps(dict(raw_cases=len(cases),all_dynamic_frames=len(summary),all_pair_rows=len(pairs),extra_rows=extras)))
