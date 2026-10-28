# 研究规格第六版修订记录

2026-09-11，接续“执行研究规格阶段3”最后中断的文档修订。阶段3实现与验收已存在，本次完成用户要求的规格一致性修改。

修改文件为[研究规格](D:/yanjiu1/keyan1/docs/noa_staggered_formation_research_plan_2026-09-10.md)和[README](D:/yanjiu1/keyan1/README.md)。修订前两份文件已原样复制至 `docs/archive/before_spec_cleanup_20260911_005919/`。

## 修订内容

- 第5、7节统一采用简化运动学、简单响应与车身几何约束。旧质量/惯量/轮胎刚度方程移出当前正文，以归档保留。位置、速度、航向和等效转向由控制与积分产生；贝塞尔仅作参考。
- 第6.3节沿用有限范围理想观测，所有开发、对照、消融和正式实验都采用该假设。前200 m、后100 m、侧向±50 m、0.1 s更新及零额外测量延迟不变，不设置噪声、遮挡、漏检或失联模块。
- 第13–15节更新验收、当前进度和后续启动提示，明确下一步为阶段4独立NOA；删除要求重新执行阶段0–1并补充质量、轮胎参数的旧提示。
- 保留C1而非C2、实际停车jerk待验收、无通信、局部信息隔离、禁止车型真值与隐藏调度、失败保留等限制。能耗后处理的额外假设与主运动模型分开登记。

未修改研究代码、配置或参数数值；未运行阶段4或正式收益实验。历史动力学文档、旧配置字段和原始运行快照保留用于溯源，不能作为恢复旧主模型要求的依据。

## 验证与证据

本次重新执行基础verify、现有86项测试及固定阶段3数值重放，均通过。重放运行ID为 `20260910T170435433186Z_6b9c489a`，来源为阶段3验收运行 `20260910T163533938451Z_2dcd59f7`；6,720次信息隔离比较通过，状态重放最大差为0，代码/配置变化及原始证据哈希差异均为空。重放审计原始SUMO读回，不重新启动SUMO。

- [基础核验日志](D:/yanjiu1/keyan1/results/phase3/spec_revision_20260911_005919/verify.log)
- [86项测试日志](D:/yanjiu1/keyan1/results/phase3/spec_revision_20260911_005919/tests.log)
- [固定运行重放日志](D:/yanjiu1/keyan1/results/phase3/spec_revision_20260911_005919/replay.log)
- [文档、代码与证据核验](D:/yanjiu1/keyan1/results/phase3/spec_revision_20260911_005919/revision_verification.json)
- [本次补充交付清单](D:/yanjiu1/keyan1/results/phase3/spec_revision_20260911_005919/revision_manifest.json)

原阶段3验收报告与交付清单作为当时版本记录保留；本次文档差异和复核证据由补充清单单独记录，不回写冻结运行。

在 `D:\yanjiu1\keyan1` 可用登记的Python解释器复核：

```powershell
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S results/phase3/spec_revision_20260911_005919/audit_revision.py
```

后续按[阶段4入口](D:/yanjiu1/keyan1/docs/phase4_entry.md)继续；完整NOA、停车舒适性及M1仍未验收，没有交通效率或节能改善结论。
