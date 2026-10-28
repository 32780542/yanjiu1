# 阶段4初始化故障定位与修复

2026-09-11；范围仅为实验物理时间零点之前的SUMO初态安装。

首次实跑 `20260910T175330533300Z_84f34950/merge_no_gap/base` 在初始化读回时失败，没有完成任何物理驾驶区间。其结果保留，不能称作控制器在无空隙时停车失败。

预定队列车长4 m、车心间隔6 m，真实车身净距2 m。[SUMO官方碰撞说明](https://sumo.dlr.de/docs/Simulation/Safety.html)表明默认碰撞登记还包含低于原生minGap的情况，默认值为2.5 m；这与独立车身相交审计含义不同。本机1.27.1随附 `docs/userdoc/Simulation/Safety.html` 的说明一致。

## 独立探针

在 `results/phase4/continuation/bootstrap/` 为每个尝试保存实际执行的bootstrap源码、命令、原始SUMO日志、读回和异常。生产文件未在这些定位实验中修改。

| 试验 | 结果 |
|---|---|
| 原初始化：分散暂存后大幅搬移 | 初始化碰撞报告，失败 |
| 仅将外部载体minGap设为0 | 仍有车道次序相关的远距离负gap报告，失败 |
| 仅按终态x顺序选择暂存位置 | 失败 |
| minGap为0且按x选择暂存位置 | 失败 |
| 先moveTo安装原生位置，再moveToXY | 默认间隙与零间隙均失败，仍有次序相关负gap |
| 直接在预定车道位置插入，默认minGap | 部分车辆因间距不足未插入，失败 |
| 直接在预定车道位置插入，外部载体minGap为0 | 全部29车插入，初态读回及随后3个物理步通过 |

前四项见 `probe_results.json`，中间两项见 `native_place_results.json`，最后两项见 `direct_place_results.json`。次序问题是根据负gap对应的车辆位置与原生安装路径作出的平台层定位；未声称修复或完整解释SUMO内部实现。

## 最终平台改动

新增 `experiments/phase4_bootstrap.py`，保留阶段3旧初始化代码和冻结证据。平台使用冻结初态的前保险杠坐标映射原生edge、lane、position，在该位置以零速插入，再于第二个排除的初始化区间安装规定的速度、横向偏移和航向。所有初态经既有FleetBridge读回验证，通过后才定义物理t=0。

这是实验初始条件安装，不向NOA提供完整路网、他车ID/类型或计划，也不在物理驾驶中排序让行、安排时隙或重新设置状态。正常物理推进仍为各自局部决策、积分后批量同步、一次SUMO推进及独立审计。

配置新增 `sumo_external_min_gap_m=0 m`，记录在phase4_experiments层；它只定义完全外部控制的SUMO载体。NOA的跟驰间距、候选车身裕量、加速度/jerk/跟踪阈值和独立车身扫掠判据均保持不变。SUMO碰撞仍使用warn并由读回失败终止，未关闭碰撞检测。

## 回归证据

`tests/test_phase4_bootstrap.py` 的3项真实SUMO测试覆盖29车密集队列及物理推进、跨edge/横向偏移读回、真实追尾仍终止FleetBridge。`regression_red.log`保存缺少新模块时的3项失败；`regression_green.log`保存3项通过，其中真实追尾产生 `gap=-2.00`、`SynchronizationError`。这证明修复没有把实际碰撞整体屏蔽，不能推导NOA对任意碰撞风险安全。

完整无空隙驾驶结果以本轮最终冻结运行与阶段4验收报告为准，3步平台回归不作为驾驶成功证据。
