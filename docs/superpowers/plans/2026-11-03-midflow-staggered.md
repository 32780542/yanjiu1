# 中流量提前交错变换实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 仅在1500/1750/2000辆/h/车道，用清晰局部规则验证交错队列提前变换减少合流扰动，并持续迭代到2026-11-03 24:00。

**Architecture:** 生产S保持锁定，候选替换单个native_rules.py。旧runner冻结其余源码和物理，完整案例封存后评价。诊断、文献、实验各写独立新目录，root整合与发布。

**Tech Stack:** Python 3.12、原生SUMO/TraCI、unittest、既有紧凑证据工具、GitHub。

**22:48进度订正：** 第一候选V未采用后，依用户持续迭代授权，实际分别检验F2/C5、GP/GP2、B/BC和D1，而非叠加候选。原“最多再一个”是初始资源计划，现以各独立冻结协议及完整结果为准。D1在21:01锁源，正式确认增加原S次参考，实际为90例；所有正式输入均在21:34登记后运行。下列保留最初任务顺序，任务2描述历史V，现行实现以D1报告和实际源码为准。

## 1. 固定问题与基线

- [x] 核对AGENTS、前阶段检查点、S461行SHA与云端HEAD；新建research/20261103-midflow-staggered分支，不复制工作区。
- [x] 写设计及本计划；用户已明确授权自主运行，本轮不追加审批停点。
- [x] 完成baseline71_24：600s/1200s、三档、71/72、两道路、NOA/S；保存协议与全部案例，至少保留seed71/drop六例raw。
- [x] 用diagnosis目录脚本核算上游/末端横移位置、区域耗时及实际速度变化，确定候选假设。

## 2. 单一候选及合同

- [x] 在新阶段tests/test_premerge_topology.py先写公开decide场景：真实终止车前方投影、近实际前车优先、CTH/phase一致、边界、NOA不变；以生产S运行并确认预期行为失败。
- [x] 以candidates/projected_predecessor/build.py从SHA锁定S仅修改_following/_decide，构建tmp/staggered_bottleneck/candidates/midflow_projected_predecessor/native_rules.py及差异/元信息。禁止改物理、安全或NOA。
- [x] 对候选运行相同合同，检验一万组有效局部状态的NOA、安全上限及非变换模式逐字段相等。
- [x] 候选若未形成可执行收益，回到轨迹与拓扑解释，分别检验有明确机制的替代方向；不叠加失败补丁，变化及负结果均在报告登记。

## 3. 公平筛查、确认与形成

- [x] 先短筛查V对S三档（180s/500s，73/74）；安全、排空、方向通过后600s全段，失败照录。
- [x] 独立冻结最终源后，用新种子91–95三档600s、两道路、NOA/D1共60例主确认，增加原S30例次参考，总计90。源码、种子与比较在任何最终结果产生前固定。
- [x] 三档1800s持续需求以独立种子81/82作确认，统一排空上限与原生入口，区分路内与入口时间。
- [x] 复用24/45辆初态与2400m几何观察网络，验证实际交错形成/3→2变换，不增加形成期限。
- [x] 仅在有效案例上报告配对差，保留所有失败；用DR/DP机制消融和直路对照检查归因。

## 4. 期刊叙事与交付

- [x] 按官方T-ITS/TRC指南和实际论文撰写中文研究主线，列明与Cai/虚拟合流/局部形成文献区别及可检验命题。
- [x] 写现行完整规则集、参数/状态/所有函数、流程和代表性车辆例子；最终规则与实际安装SHA对应。
- [x] 受影响回归239测试+51子测试、根GUI9、自检及真实SUMO30/30 smoke；独立源码与90例结果复核。
- [ ] 24:00前持续研究、补足机制及验证；随后只做必要归档发布。紧凑证据分包，小文件先推GitHub，成功raw经过哈希/原件对照后清理，失败raw保留。
- [ ] 更新根README/检查点，记录最终真实结果、采用/未采用理由、完整线上commit与本地存储变化。
