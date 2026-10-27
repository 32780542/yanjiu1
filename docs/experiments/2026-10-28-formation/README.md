# 2026-10-28 编队随机车流实验

本目录为65例实验的便携结果。正文见[多工况验证报告](../../编队多工况验证报告.md)，指标定义见[评价标准](../../编队效果评价标准.md)。

| 文件 | 内容 |
| --- | --- |
| `protocol.json` | 运行前固定的65例参数、生成机制、判据与源码摘要。 |
| `results.json`、`cases.csv` | 逐例独立复算结果。 |
| `aggregates.json`、`groups.csv` | 13个工况的汇总。 |
| `unformed_cases.json` | 8个未形成案例的终态物理状态、车群规模及车道分布。 |
| `verification.json` | 65例物理指标与260个文件摘要的核验记录。 |
| `formation_rate.*` | 车道数与需求率的形成率图，PNG/SVG。 |
| `parameter_delay.*` | 5个种子的参数配对结果图，PNG/SVG。 |
| `formation_examples.*` | 完整队形与分离车群的真实终态图，PNG/SVG。 |
| `formation_rate_figure.json` | 形成率图的数值来源。 |
| `tables.md` | 程序导出的完整汇总表。 |

形成时间为空表示该例在完整观察期内尚未形成；几何误差为空表示该终态的目标占位不完整或缺少必要比较对象。CSV使用UTF-8 BOM，便于直接用Excel阅读。JSON保留完整数值精度。

原始物理轨迹在本机 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\formation_study\20261027T170127795643Z`。原始数据采用逐例gzip物理轨迹及批次共享源码存档，约54.2MiB；本目录的小体积表格、图表和代码随Git版本保存。
