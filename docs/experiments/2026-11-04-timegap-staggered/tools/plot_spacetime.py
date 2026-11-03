"""Plot the four preselected formal seed211/flow2000 physical speed traces."""
import argparse
import csv
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
from matplotlib import patheffects
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[4]
ROUND = Path(__file__).resolve().parents[1]
SEED, FLOW = 211, 2000
TIME_LOW, TIME_HIGH, TIME_BIN = 100., 600., 10.
X_LOW, X_HIGH, X_BIN = 0., 1200., 25.
TIME_EDGES = np.arange(TIME_LOW, TIME_HIGH + TIME_BIN, TIME_BIN)
X_EDGES = np.arange(X_LOW, X_HIGH + X_BIN, X_BIN)
SHAPE = (len(TIME_EDGES) - 1, len(X_EDGES) - 1)


def select_cases(per_case):
    with per_case.open(encoding='utf-8-sig', newline='') as stream:
        cases = [r for r in csv.DictReader(stream)
                 if r['candidate'] in ('C12_200', 'C12_300')
                 and int(float(r['seed'])) == SEED and int(float(r['flow'])) == FLOW
                 and r['scenario'] == 'lane_drop' and r['mode'] in ('noa', 'transform')]
    expected = {(f'C12_{info}', mode) for info in (200, 300) for mode in ('noa', 'transform')}
    if len(cases) != 4 or {(r['candidate'], r['mode']) for r in cases} != expected:
        raise ValueError('Expected the four fixed cases, without outcome-based selection.')
    return sorted(cases, key=lambda r: (int(r['candidate'].split('_')[1]), r['mode'] != 'noa'))


def aggregate(case):
    count = np.zeros(SHAPE, dtype=np.int64)
    speed_sum = np.zeros(SHAPE, dtype=float)
    frames, time_samples = 0, 0
    with gzip.open(Path(case['run_dir']) / 'positions.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            frame = json.loads(line)
            time = frame['time_s']
            if time >= TIME_HIGH:
                break
            if time < TIME_LOW:
                continue
            frames += 1
            time_samples += len(frame['states'])
            ti = int((time - TIME_LOW) // TIME_BIN)
            for state in frame['states'].values():
                x, speed = state[0], state[2]
                # All lanes; positions[3] is acceleration and is not used here.
                if X_LOW <= x < X_HIGH:
                    xi = int((x - X_LOW) // X_BIN)
                    count[ti, xi] += 1
                    speed_sum[ti, xi] += speed
    mean = np.full(SHAPE, np.nan)
    np.divide(speed_sum, count, out=mean, where=count > 0)
    return dict(case=case, count=count, speed_sum=speed_sum, mean=mean,
                frames=frames, time_samples=time_samples, binned_samples=int(count.sum()),
                empty_bins=int(np.count_nonzero(count == 0)))


def write_bins(panels, path):
    fields = ['candidate', 'information_m', 'mode', 'scenario', 'seed', 'flow_veh_h_lane',
              'time_left_s', 'time_right_exclusive_s', 'x_left_m', 'x_right_exclusive_m',
              'vehicle_observations', 'speed_sum_mps', 'mean_speed_mps', 'run_dir']
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for panel in panels:
            case = panel['case']
            for ti in range(SHAPE[0]):
                for xi in range(SHAPE[1]):
                    n = int(panel['count'][ti, xi])
                    writer.writerow(dict(candidate=case['candidate'],
                        information_m=int(case['candidate'].split('_')[1]), mode=case['mode'],
                        scenario='lane_drop', seed=SEED, flow_veh_h_lane=FLOW,
                        time_left_s=TIME_EDGES[ti], time_right_exclusive_s=TIME_EDGES[ti + 1],
                        x_left_m=X_EDGES[xi], x_right_exclusive_m=X_EDGES[xi + 1],
                        vehicle_observations=n, speed_sum_mps=panel['speed_sum'][ti, xi],
                        mean_speed_mps=float(panel['mean'][ti, xi]) if n else '', run_dir=case['run_dir']))


def plot(panels, prefix):
    preferred = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
    available = {font.name for font in fm.fontManager.ttflist}
    font = next(name for name in preferred if name in available)
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': [font],
                         'axes.unicode_minus': False, 'font.size': 10,
                         'axes.titlesize': 11, 'axes.labelsize': 11,
                         'xtick.labelsize': 9, 'ytick.labelsize': 9,
                         'savefig.dpi': 300})
    fig, axes = plt.subplots(2, 2, figsize=(11.6, 8.5), sharex=True, sharey=True)
    fig.subplots_adjust(left=.085, right=.875, bottom=.14, top=.875, hspace=.19, wspace=.10)
    cmap = plt.get_cmap('viridis').copy()
    cmap.set_bad('#e2e2e2')
    for index, (ax, panel) in enumerate(zip(axes.flat, panels)):
        info = int(panel['case']['candidate'].split('_')[1])
        method = 'NoA' if panel['case']['mode'] == 'noa' else 'C12'
        image = ax.pcolormesh(X_EDGES, TIME_EDGES, np.ma.masked_invalid(panel['mean']),
                              cmap=cmap, vmin=0., vmax=33.3, shading='flat', rasterized=False)
        visible_x = 1000 - info
        white_edge = [patheffects.Stroke(linewidth=2.8, foreground='white'), patheffects.Normal()]
        ax.axvline(1000, color='#151515', linewidth=1.25, path_effects=white_edge)
        ax.axvline(visible_x, color='#151515', linewidth=1.2, linestyle=(0, (4, 3)), path_effects=white_edge)
        for x in (visible_x, 1000):
            ax.text(x - 9, 591, f'{x} m', ha='right', va='top', fontsize=8,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.85, pad=1.5))
        ax.set_title(f"({chr(97 + index)}) {method}  |  道路可见 {info} m", loc='left', pad=7)
        ax.set_xlim(X_LOW, X_HIGH)
        ax.set_ylim(TIME_LOW, TIME_HIGH)
        ax.set_xticks(np.arange(0, 1201, 200))
        ax.set_yticks(np.arange(100, 601, 100))
        ax.tick_params(direction='out', length=3)
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('固定种子 211：瓶颈区实际速度时空分布', fontsize=16, y=.974)
    fig.text(.48, .932, '2000 veh/h/lane  |  t [100,600) s  |  25 m × 10 s bins', ha='center', fontsize=10)
    fig.supxlabel('纵向位置 (m)', y=.075, fontsize=12)
    fig.supylabel('时间 (s)', x=.021, fontsize=12)
    color_ax = fig.add_axes((.902, .20, .019, .61))
    bar = fig.colorbar(image, cax=color_ax, ticks=[0, 5, 10, 15, 20, 25, 30, 33.3])
    bar.set_label('观测均速 (m/s)', labelpad=10)
    legend = [Line2D([0], [0], color='#151515', linewidth=1.3, label='缩道位置 1000 m'),
              Line2D([0], [0], color='#151515', linewidth=1.2, linestyle=(0, (4, 3)), label='道路信息开始可见 800 / 700 m'),
              Patch(facecolor='#e2e2e2', edgecolor='#b0b0b0', label='无车辆观测（缺测）')]
    fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(.49, .018), ncol=3,
               frameon=False, fontsize=9, handlelength=2.8, columnspacing=2.)
    fig.savefig(prefix.with_suffix('.png'), dpi=300, facecolor='white')
    fig.savefig(prefix.with_suffix('.svg'), facecolor='white')
    svg = prefix.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)
    return font


def caption(panels, prefix, per_case, font):
    lines = ['# 固定正式seed211的瓶颈速度时空图', '',
        f'来源表：`{per_case.relative_to(ROOT)}`。预先固定seed211、2000 veh/h/lane，仅取C12_200/300的NoA与transform四例，未按结果选例。', '',
        '图按两行200/300 m道路可见范围、两列NoA/C12排列，时间为`[100,600)` s、位置为`[0,1200)` m。'
        '每个25m×10s bin合并全车道的真实速度观测，以速度总和除以车辆观测样本数；每次车辆采样各计一次。'
        '这是车辆观测加权的均速，不能直接当作道路容量、吞吐量或独立车辆统计。', '',
        '**所有面板共用0–33.3 m/s色标。灰色是样本数为0的缺测bin，均速留空，既不按0计也不解释为畅通。**'
        '实线为1000m缩道位置；虚线分别为800/700m开始可见道路的位置，仅标道路信息边界，不是强制准备区。'
        'positions第四列是纵向加速度，本图只读取x与speed。', '',
        f'PNG为300 dpi，另存矢量SVG；实际使用字体为`{font}`。图的9600个bin完整保存在同名`_bins.csv`，含速度和、样本数、均速、边界和源run。', '',
        '| 面板 | case | 时间帧 | 时间窗内车辆观测 | 纳入时空窗的车辆观测 | 空bin / 2400 |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for index, panel in enumerate(panels):
        case = panel['case']
        lines.append(f"| {chr(97 + index)} | {case['candidate']} / {case['mode']} | {panel['frames']} | {panel['time_samples']} | {panel['binned_samples']} | {panel['empty_bins']} |")
    lines += ['', f"四例共{sum(p['binned_samples'] for p in panels):,}个车辆观测、9600个bin，其中空bin合计{sum(p['empty_bins'] for p in panels)}个。"
              '图例保留灰色缺测编码；时空均值会平滑单车短时速度，不能据某个bin均速不为0推断其中没有车辆短暂停车。']
    lines += ['', '## 四条原始case身份', '']
    for panel in panels:
        case = panel['case']
        lines.append(f"- `{case['candidate']} / {case['mode']} / lane_drop / flow2000 / seed211`：`{case['run_dir']}`。")
    lines += ['', '## 复现', '',
        '工具[../tools/plot_spacetime.py](../tools/plot_spacetime.py)自包含，仅依赖Python、NumPy、Matplotlib和上述四条本机原始轨迹。'
        '图与bin表可随仓库保存；完整全路raw不全量入Git。没有读取旧数据、启动SUMO、修改控制器或新增评价门。', '',
        '```powershell',
        'python -X utf8 -B scripts/run_logged.py --label formal211_spacetime --timeout 300 -- python -X utf8 -B docs/experiments/2026-11-04-timegap-staggered/tools/plot_spacetime.py',
        '```', '']
    prefix.with_name(prefix.name + '_caption.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--per-case', type=Path, default=ROUND / 'data/formal600_main/per_case.csv')
    parser.add_argument('--output-prefix', type=Path, default=ROUND / 'figures/formal211_spacetime')
    args = parser.parse_args()
    per_case = args.per_case if args.per_case.is_absolute() else ROOT / args.per_case
    prefix = args.output_prefix if args.output_prefix.is_absolute() else ROOT / args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    panels = [aggregate(case) for case in select_cases(per_case)]
    write_bins(panels, prefix.with_name(prefix.name + '_bins.csv'))
    font = plot(panels, prefix)
    caption(panels, prefix, per_case, font)
    print(json.dumps(dict(output=str(prefix), font=font, panels=[dict(
        candidate=p['case']['candidate'], mode=p['case']['mode'], frames=p['frames'],
        samples=p['binned_samples'], empty_bins=p['empty_bins']) for p in panels]), ensure_ascii=False))


if __name__ == '__main__':
    main()
