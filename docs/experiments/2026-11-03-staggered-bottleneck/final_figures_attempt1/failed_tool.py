"""Reproducible final-61 plots and one declared long-run speed raster; no simulations."""
import csv,gzip,hashlib,importlib.util,json,math,shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parent.parent
ROOT=BASE.parents[2]
OUT=BASE/'final_figures'
SKILL=Path('C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py')
spec=importlib.util.spec_from_file_location('academic_style',SKILL)
style=importlib.util.module_from_spec(spec);spec.loader.exec_module(style)
theme=style.THEMES['nature'];colors=theme['colors']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none','legend.fontsize':8})

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=300,bbox_inches='tight',facecolor='white')
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',facecolor='white');plt.close(fig)

def main():
    OUT.mkdir(exist_ok=False);(OUT/'source_tables').mkdir()
    sources={}
    for name in ['flow_means.csv','paired_seeds.csv','per_case.csv','summary.json']:
        p=BASE/'final61_S160'/name;sources[str(p)]=sha(p);shutil.copyfile(p,OUT/'source_tables'/name)
    summary=json.loads((OUT/'source_tables/summary.json').read_text())
    assert all(summary[k]==160 for k in ['case_count','protocol_verified','evidence_verified','drained','safe'])
    assert summary['pair_count']==summary['eligible_pairs']==80
    pairs=read(OUT/'source_tables/paired_seeds.csv');means=read(OUT/'source_tables/flow_means.csv')
    assert len(pairs)==80 and len(means)==16 and all(r['pair_eligible']=='True' for r in pairs)
    assert {int(r['seed']) for r in pairs}==set(range(61,66))
    assert {r['candidate_rules_sha256'] for r in pairs}=={'8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'}
    flows=sorted({float(r['flow']) for r in pairs});scenarios=['lane_drop','straight3']
    for r in pairs:
        for name in ['demand','nonrule_source','parameters']:
            assert r['reference_'+name+'_sha256']==r['candidate_'+name+'_sha256']
        assert math.isclose(float(r['system_improvement_percent']),100*(float(r['reference_mean_system_time_s'])-float(r['target_mean_system_time_s']))/float(r['reference_mean_system_time_s']),abs_tol=1e-10)
    for m in means:
        pp=[p for p in pairs if p['flow']==m['flow'] and p['scenario']==m['scenario']];assert len(pp)==5
        for metric in ['mean_system_time_s','fuel_g_per_km']:
            for prefix in ['reference_','target_','delta_']:
                assert math.isclose(float(m[prefix+metric]),np.mean([float(p[prefix+metric]) for p in pp]),abs_tol=1e-10)
    fig,axes=plt.subplots(2,2,figsize=(11.2,7.0),layout='constrained')
    for col,scenario in enumerate(scenarios):
        rr=sorted([r for r in means if r['scenario']==scenario],key=lambda r:float(r['flow']))
        ax=axes[0,col];style.apply_base_style(ax,theme)
        for label,prefix,color,marker in [('NoA','reference_',colors[0],'o'),('S','target_',colors[1],'s')]:
            ax.plot(flows,[float(r[prefix+'mean_system_time_s']) for r in rr],color=color,marker=marker,lw=1.4,ms=4,label=label+' (5-seed mean)')
            ax.scatter([float(p['flow']) for p in pairs if p['scenario']==scenario],[float(p[prefix+'mean_system_time_s']) for p in pairs if p['scenario']==scenario],s=12,color=color,alpha=.4,lw=0,zorder=2)
        ax.set_title(('a  3 to 2 lane drop' if col==0 else 'b  Three-lane straight road'),loc='left',fontweight='bold')
        ax.set_ylabel('Mean system time (s)');ax.legend(frameon=False);ax.set_xticks(flows);ax.tick_params(axis='x',rotation=35)
        ax=axes[1,col];style.apply_base_style(ax,theme)
        for seed in range(61,66):
            pp=sorted([p for p in pairs if p['scenario']==scenario and int(p['seed'])==seed],key=lambda r:float(r['flow']))
            ax.scatter([float(p['flow'])+(seed-63)*12 for p in pp],[float(p['system_improvement_percent']) for p in pp],s=16,color=colors[2],alpha=.6,lw=0,label='Paired seed values' if seed==61 else None)
        ax.plot(flows,[float(r['system_improvement_percent']) for r in rr],color=colors[1],marker='D',lw=1.3,ms=4,label='Ratio of seed means')
        ax.axhline(0,c='#666666',lw=.7);ax.set_xticks(flows);ax.tick_params(axis='x',rotation=35)
        ax.set_xlabel('Requested flow per lane (veh/h/lane)');ax.set_ylabel('System-time improvement (%)');ax.legend(frameon=False)
    fig.suptitle('Locked S vs NoA: independent seeds 61–65, 600 s demand',fontsize=12)
    save(fig,'system_time_and_paired_improvement')
    fig,axes=plt.subplots(1,2,figsize=(10.2,3.6),layout='constrained')
    for ax,scenario,title in zip(axes,scenarios,['a  3 to 2 lane drop','b  Three-lane straight road']):
        style.apply_base_style(ax,theme)
        rr=sorted([r for r in means if r['scenario']==scenario],key=lambda r:float(r['flow']))
        pp=[p for p in pairs if p['scenario']==scenario]
        ax.scatter([float(p['flow'])+(int(p['seed'])-63)*12 for p in pp],[float(p['delta_fuel_g_per_km']) for p in pp],s=15,color=colors[3],alpha=.55,lw=0,label='Paired seed values')
        ax.plot(flows,[float(r['delta_fuel_g_per_km']) for r in rr],c=colors[3],marker='D',ms=4,lw=1.3,label='5-seed mean')
        ax.axhline(0,c='#555555',lw=.8);ax.set_ylim(bottom=-.5);ax.set_xticks(flows);ax.tick_params(axis='x',rotation=35)
        ax.set_xlabel('Requested flow per lane (veh/h/lane)');ax.set_ylabel('Fuel difference: S minus NoA (g/km)');ax.set_title(title,loc='left',fontweight='bold');ax.legend(frameon=False)
    save(fig,'fuel_cost_paired')
    raster_meta=[];raster_rows=[];spot_rows=[]
    for label,batch in [('NoA','20261103_long1800_NOA4'),('S','20261103_long1800_S4')]:
        folder=ROOT/'tmp/staggered_bottleneck'/batch
        manifest=json.loads((folder/'manifest.json').read_text());record=next(r for r in manifest if r['flow']==2250 and r['seed']==42)
        assert record['safe'] and record['all_completed'] and record['seal_status']=='verified'
        run=Path(record['run_dir']);evidence=Path(record['evidence_dir']);seal=json.loads((evidence/'seal.json').read_text())
        positions=run/'positions.jsonl.gz';digest=sha(positions);assert digest==seal['originals']['positions.jsonl.gz']['sha256']
        assert sha(run/'input.json')==sha(Path(next(r['run_dir'] for r in json.loads((ROOT/'tmp/staggered_bottleneck/20261103_long1800_NOA4/manifest.json').read_text()) if r['flow']==2250 and r['seed']==42))/'input.json')
        meta_path=evidence/seal['traffic_metadata'];meta=json.loads(meta_path.read_text())
        ledger={}
        with gzip.open(meta_path.parent/'region_steps.jsonl.gz','rt') as f:
            fields=json.loads(next(f))
            for line in f:
                d=dict(zip(fields,json.loads(line)));ledger[round(d['time_s'],4)]=d
        sums=np.zeros((25,340));counts=np.zeros((25,340),dtype=np.int64);frames=0;sample_n=0;last_t=None;checks=[]
        with gzip.open(positions,'rt',encoding='utf-8') as f:
            for line in f:
                d=json.loads(line);t=d['time_s'];states=d['states'];last_t=t
                if round(t,4) in (100.,600.,1000.,1799.9):
                    selected=[s for s in states.values() if 800<=s[0]<1000]
                    n=len(selected);low=sum(s[2]<5 for s in selected);speed=sum(s[2] for s in selected);step=ledger[round(t,4)]
                    assert n==step['n'] and low==step['low_speed_n'] and math.isclose(speed,step['speed_sum_mps'],abs_tol=1e-8)
                    row=dict(profile=label,time_s=t,raw_region_n=n,raw_low_speed_n=low,raw_speed_sum_mps=speed,ledger_n=step['n'],ledger_low_speed_n=step['low_speed_n'],ledger_speed_sum_mps=step['speed_sum_mps']);checks.append(row);spot_rows.append(row)
                if not 100<=t<1800:continue
                frames+=1;j=int((t-100)//5)
                for s in states.values():
                    if 500<=s[0]<1000:
                        i=int((s[0]-500)//20);sums[i,j]+=s[2];counts[i,j]+=1;sample_n+=1
        assert frames==17000 and len(checks)==4
        means_grid=np.full((25,340),np.nan);np.divide(sums,counts,out=means_grid,where=counts>0)
        np.savez_compressed(OUT/(label+'_2250_seed42_speed_raster.npz'),speed_sum_mps=sums,sample_count=counts,mean_speed_mps=means_grid)
        for i in range(25):
            for j in range(340):raster_rows.append(dict(profile=label,x_left_m=500+20*i,x_right_m=520+20*i,t_left_s=100+5*j,t_right_s=105+5*j,vehicle_samples=int(counts[i,j]),sum_sample_speed_mps=float(sums[i,j]),mean_speed_mps=float(means_grid[i,j]) if counts[i,j] else ''))
        raster_meta.append(dict(profile=label,run_dir=str(run),positions=str(positions),positions_sha256=digest,positions_bytes=positions.stat().st_size,input_sha256=sha(run/'input.json'),seal_sha256=sha(evidence/'seal.json'),rule_sha256=json.loads((folder/'protocol.json').read_text())['sources'][record['candidate']]['noa/native_rules.py'],raw_frames_in_window=frames,vehicle_samples_in_raster=sample_n,first_window_s=100,last_window_exclusive_s=1800,spatial_window_m=[500,1000],bins_m_s=[20,5],empty_cells=int(np.sum(counts==0)),last_raw_sample_s=last_t))
    write(OUT/'speed_raster_cells.csv',raster_rows);write(OUT/'raw_ledger_spotchecks.csv',spot_rows)
    fig,axes=plt.subplots(1,2,figsize=(12.1,4.3),sharex=True,sharey=True,layout='constrained')
    cmap=plt.colormaps['viridis'].copy();cmap.set_bad('#eeeeee')
    for ax,record in zip(axes,raster_meta):
        grid=np.load(OUT/(record['profile']+'_2250_seed42_speed_raster.npz'))['mean_speed_mps']
        im=ax.pcolormesh(np.arange(100,1800.1,5),np.arange(500,1000.1,20),np.ma.masked_invalid(grid),cmap=cmap,vmin=0,vmax=32,shading='flat',rasterized=True)
        ax.axhline(640,c='white',ls=':',lw=.8);ax.axhline(1000,c='#333333',ls='--',lw=.8)
        ax.set_xlim(100,1800);ax.set_ylim(500,1000);ax.set_xlabel('Time (s)');ax.set_title(record['profile'],fontweight='bold');ax.set_ylabel('Longitudinal position x (m)')
    fig.colorbar(im,ax=axes,label='Observed vehicle-sample mean speed (m/s)',shrink=.85)
    fig.suptitle('Same demand: 2250 veh/h/lane, seed 42, 3 to 2 lane drop\n20 m × 5 s cells; grey = no observed vehicle samples; dotted line = 640 m preparation',fontsize=11)
    save(fig,'long1800_2250_seed42_speed_raster')
    assert all(sha(Path(p))==h for p,h in sources.items())
    report=dict(final160_verified=True,cases=160,pairs=80,seeds=list(range(61,66)),source_tables_sha256=sources,raster_sources=raster_meta,raw_ledger_spotchecks=8,rule_source_locked_before_seeds61=True,source_csv_unchanged=True,all_points_from_actual_rows=True,seed_horizontal_plot_offset_veh_h=[-24,-12,0,12,24],raster_method='All 0.1 s observed samples; 100 <= t < 1800, 500 <= x < 1000. Arithmetic mean speed of vehicle samples across all physical lanes, not flow/density. 20 m x 5 s; empty NaN, no interpolation, no smoothing, no occupancy imputation.',style_skill=str(SKILL),style_skill_sha256=sha(SKILL),outputs={p.name:sha(p) for p in OUT.iterdir() if p.is_file()})
    (OUT/'provenance.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'out':str(OUT),'case_count':160,'eligible_pairs':80,'raster_sources':raster_meta},indent=2))
if __name__=='__main__':main()
