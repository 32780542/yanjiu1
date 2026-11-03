"""Plot measured cohort snapshots; retain the exact plotted rows as CSV."""
import argparse
import csv
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    fonts = {font.name for font in fm.fontManager.ttflist}
    selected = next((name for name in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC')
                     if name in fonts), None)
    if selected is None:
        raise RuntimeError('Install Microsoft YaHei, SimHei, or Noto Sans CJK SC.')
    plt.rcParams.update({'font.family': selected, 'font.size': 9, 'axes.unicode_minus': False,
                         'svg.fonttype': 'path', 'axes.spines.top': False,
                         'axes.spines.right': False})
    ticks = {1: '初始三道编队', 150: '变换过程中', 350: '局部接续',
             700: '全队车道交替', 1000: '间距恢复'}
    frames = []
    with gzip.open(args.run / 'positions.jsonl.gz', 'rt', encoding='utf8') as stream:
        for line in stream:
            frame = json.loads(line)
            if round(frame['time_s'] * 10) in ticks:
                if len(frame['states']) != 45:
                    raise ValueError('Each plotted snapshot must retain all 45 vehicles.')
                frames.append(frame)
    if len(frames) != len(ticks):
        raise ValueError('Missing requested physical snapshot.')
    colors = ('#00A087', '#4DBBD5', '#E64B35')  # Nature palette
    fig, axes = plt.subplots(5, 1, figsize=(9, 7.8), sharex=True, layout='constrained')
    rows = []
    minimum = min(x - max(v[0] for v in frame['states'].values())
                  for frame in frames for x, *_ in frame['states'].values())
    left = min(-700, (minimum // 50) * 50 - 10)
    for index, (ax, frame) in enumerate(zip(axes, frames)):
        time = frame['time_s']
        lead = max(v[0] for v in frame['states'].values())
        for edge in (-.5, .5, 1.5, 2.5):
            ax.axhline(edge, color='#b8b8b8', linewidth=.6, zorder=0)
        end = 1000 - lead
        if end < 10:
            ax.add_patch(Rectangle((max(left, end), 1.5), 10 - max(left, end), 1,
                                   facecolor='#eeeeee', edgecolor='none', zorder=0))
        if left <= end <= 10:
            ax.axvline(end, color='#777777', linewidth=.7, linestyle='--')
        for key, (x, y, speed, acceleration) in frame['states'].items():
            origin = int(key.split('_')[1][1:])
            lateral = y / 3.3 - .5
            ax.add_patch(Rectangle((x - lead - 4, lateral - 1.8 / 6.6), 4, 1.8 / 3.3,
                                   facecolor=colors[origin], edgecolor='#333333', linewidth=.25))
            rows.append(dict(time_s=time, vehicle_id=key, initial_lane=origin, x_m=x,
                             y_m=y, speed_mps=speed, acceleration_mps2=acceleration,
                             relative_front_x_m=x - lead))
        ax.set(ylim=(-.6, 2.65), yticks=(0, 1, 2),
               yticklabels=('存续道0', '存续道1', '终止道2'))
        title = ticks[round(time * 10)]
        ax.set_title(f'({chr(97 + index)}) {time:g} s · {title}    队首位置 {lead:.1f} m',
                     loc='left', fontsize=9, pad=4)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y', length=0)
    axes[-1].set(xlim=(left, 10), xlabel='相对队首的车头位置 / m')
    fig.legend(handles=[Patch(facecolor=colors[i], label=f'初始车道{i}') for i in range(3)],
               loc='outside lower center', ncol=3, frameon=False)
    fig.suptitle('45辆车的真实交错编队收缩与恢复', fontsize=12)
    for suffix in ('png', 'svg'):
        fig.savefig(args.output / f'cohort45.{suffix}', dpi=300, bbox_inches='tight')
    plt.close(fig)
    with (args.output / 'snapshot_points.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / 'caption.md').write_text(
        '全部截面均45车在场、0离场，车辆位置来自原生SUMO。颜色表示初始车道；'
        '灰区表示1000米之后已经结束的车道2。观察出口为3600米，效率道路另为1200米。'
        '70秒车道交替闭合，之后间距继续收敛；全程22次横移，无往返。\n\n'
        f'轨迹来源：`{args.run}`。225条实际绘图记录见snapshot_points.csv。\n', encoding='utf8')
    print(json.dumps(dict(output=str(args.output), rows=len(rows), font=selected)))


if __name__ == '__main__':
    main()
