# 局部交错编队瓶颈迭代实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在北京时间2026-11-03 17:00前，量化现有拥堵边界，并取得经过配对与消融检验的局部交错编队更新；所有正负结果用GitHub保存。

**Architecture:** 沿用原SUMO执行与逐车规则。独立工作分别处理旧结果诊断、文献/MATLAB和紧凑试验工具；父代理按诊断顺序实现单一控制假设并整合验收。生产规则在验证前保持TM。

**Tech Stack:** Python标准库、pytest、SUMO/TraCI、Git/GitHub。

## 1. 恢复与诊断

- [x] 阅读AGENTS、检查点、TM规则和上轮结果；确认Git起点177f7a3及现有未跟踪用户文件。
- [ ] 从已有公开结果生成NOA自由流及瓶颈对照表；核查每道Bernoulli来车与MATLAB口径。
- [ ] 阅读Cai活跃源和关键原文，写入 `docs/experiments/2026-11-03-staggered-bottleneck/methods/reference_design.md`。
- [ ] 新工具在单例归档、失败保留及限定路径清理测试通过后，跑32例高需求诊断：TM、双模式、1750/2000/2250/2500、种子1/4、两种道路、180/500秒。

## 2. 单项假设与小批验证

- [ ] 每个候选先在本轮 `tests/` 写出违反当前行为的具体合同，用动态加载固定TM及候选运行；记录预期失败。
- [ ] 只替换候选 `native_rules.py` 的对应函数；不改engine/CLI/物理、输入或NOA。
- [ ] 合同通过后运行冻结候选与TM同输入筛查；每次只增加一个方法。
- [ ] 在 `candidates/<名称>/method.md` 写明信息、公式、源差异和结果；未改善者退回前一有效方法。

## 3. 归因与独立验证

- [ ] 选用确实拥堵的负荷，进行600秒需求和足够排空上限；与1250原工况同时报告。
- [ ] 同跟驰NOA、TM、新交错策略、关闭交错关系的变换消融进行配对，检查瓶颈分段而非仅全程差。
- [ ] 用未用于选参的新种子核验。重算原trip、原0/1和已有瓶颈账本；检查碰撞/瞬移/未完成与一致输入/源码。
- [ ] 对最终源运行受影响的真实规则/安全/局部信息/GUI入口测试；代码与结果独立审查。

## 4. 交付与云端管理

- [ ] 分单元提交并推送 `yanjiu1/research/20261103-staggered-bottleneck`，不建立本地整库版本副本。
- [ ] 只在新源通过正式验证时装入默认入口，更新当前规则说明、结果报告和检查点，推送main。
- [ ] 到17:00或达到设计中明显提升的全部条件时，交付实际最优版本、完整差异及下一入口。未达目标按实际结果交付，不能把筛查最好种子当最终结论。

所有长命令：`python -X utf8 -B scripts/run_logged.py --label <唯一名称> --timeout <不超过7200> -- <command>`。旧尝试不覆盖，断流先查操作日志和进程。
