"""直路NOA对照与编队规模、参与率、稳定度的研究图表。"""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def plot(directory):
    directory = Path(directory)
    rows = json.loads((directory/'groups.json').read_text(encoding='utf-8'))
    lookup = {(r['flow_veh_h_lane'],r['formation']):r for r in rows if r['kind']=='demand'}
    flows = (1250,1500,1750,2000)
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
        'font.size':10,'axes.unicode_minus':False,'svg.fonttype':'none'})
    colors = ('#3C5488','#E64B35')
    labels = ('仅NOA','NOA＋编队')

    def curve(ax,metric,ylabel,scale=1.):
        for on in (False,True):
            values = np.array([lookup[q,on][metric+'_mean'] for q in flows],dtype=float)*scale
            errors = np.array([lookup[q,on][metric+'_sd'] for q in flows],dtype=float)*scale
            ax.plot(flows,values,marker='o',markersize=4,color=colors[on],label=labels[on])
            valid = np.isfinite(values)&np.isfinite(errors)
            ax.errorbar(np.array(flows)[valid],values[valid],yerr=errors[valid],
                        color=colors[on],fmt='none',capsize=3)
        ax.set_xlabel('每车道需求率（辆/h）')
        ax.set_ylabel(ylabel)
        ax.set_xticks(flows)
        ax.grid(axis='y',alpha=.18)
        ax.spines[['top','right']].set_visible(False)

    def save(fig,name):
        for suffix in ('png','svg'):
            path = directory/f'{name}.{suffix}'
            fig.savefig(path,dpi=300,bbox_inches='tight',facecolor='white')
            if suffix=='svg':
                path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
        plt.close(fig)

    fig,axes = plt.subplots(1,2,figsize=(9,3.7),layout='constrained')
    curve(axes[0],'mean_travel_time_s','1200 m平均在网行程时间（s）')
    curve(axes[1],'mean_entry_wait_s','平均源端未放行等待（s）')
    axes[0].legend(frameon=False)
    fig.suptitle('恒定三车道直路对照：共同应急保护与巡航设定',fontsize=12)
    save(fig,'noa_straight_comparison')

    fig,axes = plt.subplots(2,2,figsize=(9,7),layout='constrained')
    for ax,(metric,label,scale) in zip(axes.flat,(
        ('mean_platoon_size','平均局部编队规模（辆）',1.),
        ('max_platoon_size','逐例最大规模的跨种子均值（辆）',1.),
        ('participation_rate','编队参与率（%）',100.),
        ('stable_participation_rate','连续关系确认5 s后的稳定参与率（%）',100.))):
        curve(ax,metric,label,scale)
    axes[0,0].legend(frameon=False)
    fig.suptitle('编队规模与稳定参与：3种子均值±样本标准差',fontsize=12)
    save(fig,'platoon_size_stability')

    fig,axes = plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
    for ax,(metric,label) in zip(axes,(
        ('geometry_rms_m','已成队关系的几何RMS（m）'),
        ('speed_rms_mps','队内速度RMS（m/s）'),
        ('internal_breaks_per_100_platoon_vehicle_s','内部断裂（次/100编队车辆秒）'))):
        curve(ax,metric,label)
    axes[0].legend(frameon=False)
    fig.suptitle('局部编队质量：边界退出删失，内部关系丢失计断裂',fontsize=12)
    save(fig,'platoon_quality')

    (directory/'figure_sources.json').write_text(json.dumps(dict(
        source='groups.json',filter=dict(kind='demand'),flows_veh_h_lane=flows,
        error_bars='sample standard deviation across valid paired seeds',
        participation_units='percent in figures; fraction in JSON/CSV'),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    plot(parser.parse_args().directory)
