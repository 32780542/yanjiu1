"""Plot frozen stage4 physical trajectories, including failures, at 300dpi."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run  # Isolated runtime setup and declared matplotlib dependency path.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research.common import output_path

source=output_path(sys.argv[1])
out=output_path('results/phase4/figures')
out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
colors=['#0072B2','#D55E00','#009E73','#CC79A7']
fig,axes=plt.subplots(4,2,figsize=(12,13),layout='constrained')
stats={}
for ax,(name,title) in zip(axes.flat,[('normal_lane_change','A  Ordinary lane change'),('two_lane_changes','B  Sequential lane changes'),
                                    ('merge_clear','C  Merge into clear lane'),('merge_no_gap','D  Blocked merge: stop / wait'),
                                    ('stop_restart','E  Stop and restart'),('observed_cut_in','F  Observed cut-in'),
                                    ('merge_gap_after_queue','G  Merge after sparse queue'),('urgent_braking_stress','H  Severe braking stress')]):
    folder=source/name/'base'
    rows=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    rows=[r for r in rows if r.get('steps') and 'ego' in r['steps']]
    result=json.loads((folder/'validation.json').read_text())
    if not rows:
        ax.text(.5,.5,'No physical trajectory\nInitialization / recording failure',ha='center',va='center',transform=ax.transAxes)
        ax.set_title(title+' — FAIL retained',loc='left',fontweight='bold',fontsize=11)
        stats[name]={'result':False,'samples':0}
        continue
    states=[rows[0]['initial']['ego']]+[s for r in rows for s in r['steps']['ego']['samples']]
    if name in ('stop_restart','urgent_braking_stress'):
        ax.plot([s['time_s'] for s in states],[s['vx_mps'] for s in states],color=colors[0],label='NOA speed')
        for key in rows[0]['steps']:
            if key=='ego': continue
            other=[rows[0]['initial'][key]]+[s for r in rows for s in r['steps'][key]['samples']]
            ax.plot([s['time_s'] for s in other],[s['vx_mps'] for s in other],lw=1,alpha=.7,label=key)
        ax.set(xlabel='Physical time (s)',ylabel='Speed (m/s)')
        for time,*keys in result.get('geometry',{}).get('collision_events',[]):
            ax.axvline(time,color=colors[1],alpha=.06,lw=1)
    else:
        for y in (0,3.3,6.6,9.9):
            if name.startswith('merge') and y>6.6:
                ax.plot([min(s['x_m'] for s in states)-3,1000],[y,y],color='.7',ls='--',lw=.7)
            else: ax.axhline(y,color='.7',ls='--',lw=.7)
        if name.startswith('merge'):
            ax.plot([1000,1000],[6.6,9.9],color='.4',lw=1)
        ax.plot([s['x_m'] for s in states],[s['y_m'] for s in states],color=colors[0],lw=1.8,label='NOA actual')
        if name=='normal_lane_change':
            half=source/name/'sampling_half/trace.jsonl'
            other=[s for line in half.read_text().splitlines() for s in json.loads(line)['steps']['ego']['samples']]
            ax.plot([s['x_m'] for s in other],[s['y_m'] for s in other],color=colors[1],lw=1,ls=':',label='Sampling half')
        ax.set(xlabel='Longitudinal position (m)',ylabel='Lateral position (m)',ylim=(-.4,10.3))
    case_result=json.loads((source/name/'validation.json').read_text())
    status='PASS' if case_result['passed'] else 'FAIL retained'
    if name=='normal_lane_change' and result['passed'] and not case_result['passed']:
        status='base PASS; sampling FAIL'
    ax.set_title(title+' — '+status,loc='left',fontweight='bold',fontsize=11)
    ax.grid(alpha=.15)
    ax.legend(fontsize=8,loc='best')
    stats[name]={'base_passed':result['passed'],'case_total_passed':case_result['passed'],
                 'recorded_end_time_s':states[-1]['time_s'],'samples':len(states)}
fig.suptitle('Stage 4 independent NOA: recorded motion and failure cases\nFinite ideal observations; kinematic model; no formation or traffic-benefit claim',fontsize=13)
fig.savefig(out/'phase4_motion.png',dpi=300)
fig.savefig(out/'phase4_motion.svg')
plt.close(fig)
(out/'figure_sources.json').write_text(json.dumps({'run_id':source.name,'panels':stats},indent=2)+'\n',encoding='utf-8')
print(str(out/'phase4_motion.png'))
