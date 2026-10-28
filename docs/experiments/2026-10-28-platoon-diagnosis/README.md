# 局部几何匹配与完整队形的结构复查

正文见[仅NOA误计与大流量小车组诊断](../../仅NOA误计与大流量小车组诊断.md)。本目录核查修正NOA后的三车道主实验24例，没有重新生成车辆或改变控制。

| 文件 | 内容 |
| --- | --- |
| `structure_audit.json` | 24例的匹配分量大小、一层分量数、上下双车数、同道/跨道边、实际换道、完整车群检查及原始文件摘要。 |
| `rule_examples.json` | 两个直接调用真实规则函数的数值例子，复现位置误差30.48m而加速度请求为0、层窗不稳定拒绝补位。 |
| `summary.json` | 按模式、流量汇总的观测数量、换道次数和源码摘要。 |
| `reproduce_audit.py` | 本次离线复查与数值例子的完整脚本。 |

`counts`中的数量按采样帧累计，同一车辆、关系或车组在不同帧会重复出现。`matched_size_N`表示N车几何匹配分量的观测次数；`single_layer_samples`表示车组内每条车道最多一车；`outer_pair_samples`表示只有上下两车并排、中间缺位的双车组。

`same_lane_edges`、`cross_lane_edges`分别是原局部匹配评价器接纳的同道边和跨道边。原局部匹配速度容差为0.5m/s。`complete_component_size_N`使用既有完整队形函数，在50m相邻纵向连通的整个物理车群上检查N车的车道分布、30m层距、15m相位与1m/s速度差。两种检查沿用各自既有参数，分别回答局部相似关系和整个车群队形是否合格。

完整检查的观测次数是单帧事实，没有进行连续保持确认，不能写成形成次数。24例的合格完整车群样本均为三车一层，多层合格样本为0。

`same_lane_gap_min_m`和`same_lane_gap_median_m`来自所有帧中、距车道中心不超过0.3m的同车道物理相邻车辆，单位m。`completed_lane_changes`来自逐车台账求和。

`first_match`、`first_full`保存首个匹配/合格车群的原始帧位置或成员，便于直接定位。`source_sha256`逐例记录`input.json`、`positions.jsonl.gz`、`trips.json`的SHA256。

复算入口：

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B scripts/run_logged.py --label geometry-audit --timeout 300 -- python -B docs/experiments/2026-10-28-platoon-diagnosis/reproduce_audit.py
```

脚本读取本机`variants/phase5g_pure_formation/results/continuous_traffic_v3/20261028T100105100032Z/demand_*`，输出两个JSON到`tmp`，应与本目录`structure_audit.json`及`rule_examples.json`逐字节一致。原始轨迹仍留本机结果目录，诊断数据与脚本随GitHub保存。
