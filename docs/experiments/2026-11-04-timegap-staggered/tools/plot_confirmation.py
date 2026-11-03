"""Plot the locked five-seed traffic comparison and its existing paired effects."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager, pyplot as plt

MODES = {'noa': ('纯NOA', '#777777'), 'formation': ('仅形成', '#4DBBD5'),
         'transform': ('形成并变换', '#00A087')}
FLOWS = (1500, 1750, 2000)


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def save(fig, output, name):
    fig.savefig(output / (name + '.png'), dpi=300, bbox_inches='tight')
    svg = output / (name + '.svg')
    fig.savefig(svg, bbox_inches='tight')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n',
                   encoding='utf-8', newline='\n')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    family = next(name for name in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC') if name in fonts)
    plt.rcParams.update({'font.family': family, 'font.size': 9, 'axes.unicode_minus': False,
                         'svg.fonttype': 'path', 'axes.spines.top': False, 'axes.spines.right': False})
    cases = [row for row in read(args.report / 'per_case.csv') if row['scenario'] == 'lane_drop']
    assert all(row['safe'] == row['all_completed'] == row['evidence_verified'] == 'True' for row in cases)
    groups = defaultdict(list)
    for row in cases:
        groups[row['candidate'], row['mode'], int(float(row['flow']))].append(row)
    assert len(groups) == 18 and all(len(group) == 5 for group in groups.values())
    summary = []
    metrics = ('mean_system_time_s', 'fuel_g_per_km', 'flag_mean_participants',
               'flag_participation_rate', 'flag_mean_episode_s', 'region_mean_speed_mps',
               'region_low_speed_vehicle_s', 'stop_sample_vehicle_s', 'merge_2to1_mean_x_m')
    for (candidate, mode, flow), group in sorted(groups.items()):
        summary.append(dict(candidate=candidate, mode=mode, flow=flow, seeds=5,
                            **{key: mean(float(row[key]) for row in group) if all(row[key] for row in group)
                               else None for key in metrics}))
    with (args.output / 'plotted_means.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    def curves(ax, preview, metric, scale=1., modes=MODES):
        for mode in modes:
            label, color = MODES[mode]
            values = []
            for flow in FLOWS:
                group = groups[f'C12_{preview}', mode, flow]
                samples = [float(row[metric]) * scale for row in group]
                ax.scatter([flow] * len(samples), samples, color=color, alpha=.35, s=12)
                values.append(mean(samples))
            ax.plot(FLOWS, values, 'o-', color=color, label=label, markersize=4, linewidth=1.5)
        ax.set(xticks=FLOWS, xlabel='流量 / 辆·h⁻¹·车道⁻¹')
        ax.grid(axis='y', linewidth=.5, alpha=.3)

    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.6), sharey=True, layout='constrained')
    for ax, preview in zip(axes, (200, 300)):
        curves(ax, preview, 'mean_system_time_s')
        ax.set_title(f'{preview} m道路信息')
    axes[0].set_ylabel('平均系统时间 / s·车⁻¹')
    axes[1].legend(frameon=False)
    fig.suptitle('缩道交通效率：独立五种子确认')
    save(fig, args.output, 'system_time')

    pairs = read(args.report / 'flow_means.csv')
    did = read(args.report / 'road_did_means.csv')
    fig, axes = plt.subplots(2, 2, figsize=(8.5, 6.2), layout='constrained')
    for index, preview in enumerate((200, 300)):
        selected = [row for row in pairs if row['candidate'] == f'C12_{preview}'
                    and row['mode'] == 'transform' and row['reference_mode'] == 'noa'
                    and row['scenario'] == 'lane_drop']
        roads = [row for row in did if row['candidate'] == f'C12_{preview}'
                 and row['mode'] == 'transform' and row['reference_mode'] == 'noa']
        selected.sort(key=lambda row: float(row['flow']))
        roads.sort(key=lambda row: float(row['flow']))
        assert len(selected) == len(roads) == 3
        axes[index, 0].plot(FLOWS, [float(row['delta_mean_system_time_s']) for row in selected],
                            'o-', color='#00A087', label='缩道总差值')
        axes[index, 0].plot(FLOWS, [float(row['did_mean_system_time_s']) for row in roads],
                            's--', color='#3C5488', label='扣除直路差值')
        axes[index, 1].plot(FLOWS, [float(row['delta_fuel_g_per_km']) for row in selected],
                            'o-', color='#E64B35')
        axes[index, 0].set_ylabel(f'{preview} m · 时间差 / s·车⁻¹')
        axes[index, 1].set_ylabel(f'{preview} m · 油耗差 / g·km⁻¹')
        for ax in axes[index]:
            ax.axhline(0, color='#aaaaaa', linewidth=.7)
            ax.set(xticks=FLOWS, xlabel='流量 / 辆·h⁻¹·车道⁻¹')
            ax.grid(axis='y', linewidth=.5, alpha=.3)
    axes[0, 0].legend(frameon=False)
    fig.suptitle('形成并变换−NOA：时间改善与燃油代价')
    save(fig, args.output, 'paired_effects')

    fig, axes = plt.subplots(2, 2, figsize=(8.5, 6.2), layout='constrained')
    for index, preview in enumerate((200, 300)):
        curves(axes[index, 0], preview, 'flag_mean_participants', modes=('formation', 'transform'))
        curves(axes[index, 1], preview, 'flag_participation_rate', scale=100,
               modes=('formation', 'transform'))
        axes[index, 0].set_ylabel(f'{preview} m · 平均同时参与车辆数')
        axes[index, 1].set_ylabel(f'{preview} m · 车辆时间参与率 / %')
    axes[0, 1].legend(frameon=False)
    fig.suptitle('直接0/1关系统计：全路参与规模与参与率')
    save(fig, args.output, 'participation')
    (args.output / 'caption.md').write_text(
        '独立种子211–215，600秒来车、1200秒排空上限，三档流量；'
        '线为五种子等权均值，浅色点为各个种子。两种道路信息分别比较，所有模式共同获得。\n\n'
        'paired_effects的负时间差表示改善，正油耗差表示消耗增加；'
        '扣除直路差值为相同种子下的道路差中差。参与规模是全路状态1人数，可包含多支队伍；'
        '纯NOA的状态始终0。plotted_means.csv保留绘图均值，逐种子源数据位于研究报告。\n\n'
        f'数据来源：{args.report.as_posix()}。\n', encoding='utf-8')
    print(f'Wrote three PNG300dpi/SVG figures and plotted means to {args.output}')


if __name__ == '__main__':
    main()
