# F2：只修订未来资源占位判定

F2保留[F的资源映射与策略层/执行层含义](../future_resources/method.md)，没有叠加V。构建读取冻结F（`e4b18ac1...aba7e7`），同时核对冻结S（`8bdaa210...d12f`）。原F源与原patch没有覆盖；S→F2及F→F2分别保存差异。

## 为什么需要新revision

matches±2m是形成几何的匹配容差；它不能独自代表未来资源可用净空。有效物理反例全部速度28.8m/s：本车lane0@702；其余lane0@760/730/690/680，其中后三车已有vy=.2m/s；lane1@745/655；ending lane2@(715+δ)，δ=3/4/5/6/7m。

资源中心q730提供lane1目标x715，参考来自实际lane0@730。本车与ending车相隔16–20m，真实目标道前后车也有足够当前走廊净空，因此原`_clear`和`_mandatory_priority`均允许；但ending车即将使用的lane1资源距目标715只有3–7m。F仍返回目的lane1，说明未来vacancy判定确实漏掉了已近距占用的机会。

F2将该守卫改为：当同一未来资源道上的任何局部车与目标真实纵坐标之差小于既有CLEARANCE=8m时，排除该选道机会。这个判断只属于未来资源层；没有把ending车变成当前lane1物理占道对象。formation的matches/full容差仍为原2m，实际`_clear`、response_cost、safe_speed和gap执行均未修改。

## 红灯、绿灯及没有掩盖的设计修正

先写`tests/test_future_resource_occupancy.py`。最初手构的ego@730场景缺少除本车外的q730 reference，未触发所要检验的补位；因此那次失败来自错误的场景假设，不是有效需求红灯。日志原样保留：`results/operations/20261103T105510335224Z_midflow-F-future-occupancy-red_76d8a7ed`。

把本车移到702并加入已有横移的负荷车后，F对五个δ均出现预期失败，另一项“未来资源投影不改变实际占道”的合同通过。有效红灯：`results/operations/20261103T105623125773Z_midflow-F-future-occupancy-red-corrected_d3b81a34`。

随后才构建F2；合并原F的6项与新2项，8项全通过：`results/operations/20261103T105802157914Z_midflow-F2-green-contract_519dca16`。包括700快照范围回归、24排列及ID双射、真实阻挡、mandatory保持、指定slot不被执行承诺以及3–7m未来净空反例。

## 解释与验收边界

本修订避免选道层把已有未来近距占用误当机会；它不证明更早让位更高效，也不赋予全路唯一slot分配。`_fill`仍只返回lane，`_join_speed`仍追踪本车旁实际gap；该执行闭环与future几何机会特征是不同层次。未来目标x715不必成为最终Command.target_x，已经通过正向场景明确展示并保留。

因此F2可以作为独立、待筛查的选道策略候选交给runner，不能称为已验证的编队变换控制器。后续需要：同需求/种子与S/NOA的1500/1750/2000交通对照；实际换道起终点及真实间隙；24/45辆几何成形/恢复；失败、燃油增加和未完成原样保留。此次没有运行这些仿真或修改生产源。
