"""Plot the derived fixed-predecessor linear model, without SUMO or traffic data."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / 'figures/ctg_response'


def response(frequency, headway):
    step, relaxation, gain = .1, .2, .3
    a = 1 - relaxation - relaxation * gain * headway
    c = relaxation * gain
    z = np.exp(2j * np.pi * frequency * step)
    return np.abs(((relaxation + step * c) * z - relaxation)
                  / (z * z - (1 + a - step * c) * z + a))


def main():
    OUT.mkdir(exist_ok=False)
    frequency = np.r_[0., np.geomspace(.001, 5., 4000)]
    fixed, ctg = response(frequency, 0.), response(frequency, .85)
    with (OUT / 'frequency_response.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('frequency_hz', 'fixed_distance_gain', 'ctg_h085_gain'))
        writer.writerows(zip(frequency, fixed, ctg))
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False,
                         'svg.fonttype': 'path', 'font.size': 10})
    fig, ax = plt.subplots(figsize=(7.4, 4.6), layout='constrained')
    ax.semilogx(frequency[1:], fixed[1:], color='#B24745', linewidth=2,
                label='固定距离 29.98 m')
    ax.semilogx(frequency[1:], ctg[1:], color='#326B9A', linewidth=2,
                label='固定时距 h = 0.85 s')
    ax.axhline(1., color='#555555', linestyle='--', linewidth=.9)
    peak = np.argmax(fixed)
    ax.scatter(frequency[peak], fixed[peak], color='#B24745', s=28, zorder=3)
    ax.annotate(f'峰值 {fixed[peak]:.4f}', (frequency[peak], fixed[peak]),
                xytext=(.15, 1.16), arrowprops={'arrowstyle': '-', 'color': '#B24745'},
                color='#8E3331')
    ax.set(xlabel='前车速度扰动频率 (Hz)', ylabel='后车 / 前车的速度扰动幅值比',
           xlim=(.001, 5), ylim=(0, 1.24),
           title='固定前驱理想离散模型：时距项抑制速度扰动传播')
    ax.text(.0012, 1.025, '幅值比 1：不放大', color='#555555', fontsize=9)
    ax.grid(axis='both', alpha=.18)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(frameon=False, loc='lower left')
    fig.savefig(OUT / 'frequency_response.png', dpi=300, facecolor='white')
    fig.savefig(OUT / 'frequency_response.svg', facecolor='white')
    plt.close(fig)
    svg = OUT / 'frequency_response.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    (OUT / 'caption.md').write_text(
        '# 理想固定前驱模型的速度扰动传播\n\n'
        '图直接计算[理论文](../../理论性质与稳定性边界.md)推导的H(z)，采样周期0.1 s、'
        '位置增益0.3、每步松弛0.2，零初始扰动。固定距离在与h=.85相同的巡航平衡29.98 m处展开，'
        '目标对速度的导数为0；固定时距使用D(v)=5.5+.85v。两者均为固定前驱、同质、无切换、'
        '无约束激活且命令准确执行的模型。\n\n'
        '固定距离最大幅值约1.1047，出现在约0.085 Hz；时距曲线在非零频率小于1，'
        '两者直流增益均为1。这解释的是该理想链的扰动传播，不是SUMO完整混合控制器的稳定性测试。'
        '实际形成、接收和切换另由轨迹与交通试验报告。\n\n'
        '数值见[frequency_response.csv](frequency_response.csv)；PNG为300 dpi，另有矢量SVG。'
        '用[plot_ctg_response.py](../../tools/plot_ctg_response.py)可复算，工具不读取实验结果或修改控制器。\n',
        encoding='utf-8')
    print(f'Wrote {len(frequency)} frequencies; fixed peak={fixed[peak]:.8f}; CTG max={ctg.max():.8f}')


if __name__ == '__main__':
    main()
