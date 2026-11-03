"""Draw the observed request wave from the measured 45-vehicle event table."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager, pyplot as plt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    with a.csv.open(encoding='utf-8-sig', newline='') as stream:
        rows = [row for row in csv.DictReader(stream) if row['from_lane'] == '2' and row['to_lane'] == '1']
    rows.sort(key=lambda row: float(row['request_s']))
    assert len(rows) == 15 and sum(int(row['request_road_visible']) for row in rows) == 1
    fonts = {f.name for f in font_manager.fontManager.ttflist}
    family = next(name for name in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC') if name in fonts)
    plt.rcParams.update({'font.family': family, 'font.size': 9, 'axes.unicode_minus': False,
                         'svg.fonttype': 'path', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.6), layout='constrained')
    times = [float(row['request_s']) for row in rows]
    positions = [float(row['request_x_m']) for row in rows]
    axes[0].plot(times, positions, '-', color='#4DBBD5', linewidth=1)
    axes[0].scatter(times[1:], positions[1:], color='#4DBBD5', label='本车尚未看见缩道', s=25)
    axes[0].scatter(times[:1], positions[:1], color='#E64B35', label='已看见缩道的头车', s=35, zorder=3)
    axes[0].axhline(800, linestyle='--', color='#888888', linewidth=.8)
    axes[0].set(xlabel='独立请求时刻 / s', ylabel='请求时本车位置 / m', ylim=(390, 850),
                title='(a) 实际运动引导向后传播')
    axes[0].legend(frameon=False, fontsize=8, loc='lower left')
    for index, row in enumerate(rows):
        start, end = float(row['request_s']), float(row['completion_s'])
        color = '#E64B35' if int(row['request_road_visible']) else '#4DBBD5'
        axes[1].plot([start, end], [index, index], color=color, linewidth=2)
        axes[1].scatter([end], [index], color=color, s=10)
    axes[1].invert_yaxis()
    axes[1].set(xlabel='实际时间 / s', yticks=(0, 7, 14), yticklabels=('头车', '后7', '后14'),
                ylabel='沿原终止车道的车辆顺序', title='(b) 请求至严格完成，15辆均完成')
    fig.suptitle('局部运动引导：14辆后车在自己看到缩道前接续', fontsize=11)
    for suffix in ('png', 'svg'):
        path = a.output / ('motion_guidance.' + suffix)
        fig.savefig(path, dpi=300, bbox_inches='tight')
        if suffix == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines()) + '\n',
                            encoding='utf-8', newline='\n')
    plt.close(fig)
    (a.output / 'caption.md').write_text(
        '45车固定交错初态，C12、道路直接可见200米。15个独立2→1请求中，'
        '1辆头车已经看见道路，其余14辆的请求位置均小于800米。横向线段从独立接受请求时刻到严格完成时刻；'
        '全体完成于14.6秒。本图按实际事件绘制，车辆序号只用于记录顺序。\n\n'
        f'源表：{a.csv.as_posix()}。\n', encoding='utf-8')
    print(f'Plotted 15 actual requests: {a.output}')


if __name__ == '__main__':
    main()
