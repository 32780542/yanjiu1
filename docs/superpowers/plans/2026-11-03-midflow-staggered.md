# 中流量提前交错变换实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 仅在1500/1750/2000辆/h/车道，用清晰局部规则验证交错队列提前变换减少合流扰动，并持续迭代到2026-11-03 24:00。

**Architecture:** 生产S保持锁定，候选替换单个native_rules.py。旧runner冻结其余源码和物理，完整案例封存后评价。诊断、文献、实验各写独立新目录，root整合与发布。

**Tech Stack:** Python 3.12、原生SUMO/TraCI、unittest、既有紧凑证据工具、GitHub。

## 1. 固定问题与基线

- [x] 核对AGENTS、前阶段检查点、S461行SHA与云端HEAD；新建research/20261103-midflow-staggered分支，不复制工作区。
- [x] 写设计及本计划；用户已明确授权自主运行，本轮不追加审批停点。
- [ ] 完成baseline71_24：600s/1200s、三档、71/72、两道路、NOA/S；保存协议与全部案例，至少保留seed71/drop六例raw。
- [ ] 用diagnosis目录脚本核算上游/末端横移位置、区域耗时及实际速度变化，确定候选假设。

## 2. 单一候选及合同

- [ ] 在新阶段tests/test_premerge_topology.py先写公开decide场景：真实终止车前方投影、近实际前车优先、CTH/phase一致、边界、NOA不变；以生产S运行并确认预期行为失败。
- [ ] 以candidates/projected_predecessor/build.py从SHA锁定S仅修改_following/_decide，构建tmp/staggered_bottleneck/candidates/midflow_projected_predecessor/native_rules.py及差异/元信息。禁止改物理、安全或NOA。
- [ ] 对候选运行相同合同，检验一万组有效局部状态的NOA、安全上限及非变换模式逐字段相等。
- [ ] 候选若未形成可执行收益，回到轨迹与拓扑解释，最多再检验一个有明确机制的替代方向；不叠加补丁。

## 3. 公平筛查、确认与形成

- [ ] 先短筛查V对S三档（180s/500s，73/74）；安全、排空、方向通过后600s全段，失败照录。
- [ ] 独立冻结最终源后，用新种子91/92/93三档600s、两道路、NOA/候选确认。未冻结前不运行该最终输入。
- [ ] 三档1800s持续需求以独立种子81/82作确认，统一排空上限与原生入口，区分路内与入口时间。
- [ ] 复用24/45辆初态与2400m几何观察网络，验证实际交错形成/3→2变换，不增加形成期限。
- [ ] 仅在有效案例上报告配对差，保留所有失败；用机制消融和直路对照检查归因。

## 4. 期刊叙事与交付

- [ ] 按官方T-ITS/TRC指南和实际论文撰写literature中文原始研究主线；列明与Cai/虚拟合流/局部形成文献区别及可检验命题。
- [ ] 写现行完整规则集、参数/状态/所有函数、流程和代表性车辆例子；最终规则必须与实际安装SHA对应。
- [ ] 受影响回归、根GUI入口、自检及真实SUMO smoke；独立源码与结果复核。
- [ ] 24:00前持续研究、补足机制及验证；随后只做必要归档发布。紧凑证据分包，小文件先推GitHub，成功raw经过哈希/原件对照后清理，失败raw保留。
- [ ] 更新根README/检查点，记录最终真实结果、采用/未采用理由、完整线上commit与本地存储变化。
