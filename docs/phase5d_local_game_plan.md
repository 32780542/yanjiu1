# 阶段5D：局部主从博弈等待策略实施计划

> 使用 subagent-driven-development 执行有界子任务，并进行规格与代码独立审查。用户已授权继续实施和实验。

目标：在5C之后比较固定减速、局部最坏情况选择、局部主从博弈预测，检查等待阶段是否减少无必要的降速并促进后续换道；允许无改善和失败。技术栈沿用Python标准库、现有模型/守卫/SUMO1.27.1。

## 前置条件与范围

- 读5C验收、通行诊断、实际controller/r5/prediction/formation；重新校验5C交付及两正式包、110实际源码和10输入，不重跑固定313测试与23重放。
- 无git HEAD，源自5C封存code_snapshot新建 `D:/yanjiu1/keyan1/variants/phase5d_local_game`；原算法及5C证据只读。
- 本轮只改变R5阻断期间非紧急的本车纵向等待请求。不改变谁可开始换道、UNKNOWN、随机链、低速5m/s门槛、速度端点、换道时间、形成规则、原守卫/感知/模型/舒适性。
- 博弈主从角色是本车对可见物理优先关系的建模：对方是模型leader，本车是模型follower。没有车辆间角色协议、邻车效用真值、消息、转向灯或试探动作信号；不声称实际达到两车均衡。

## 预登记算法（正式结果产生前冻结）

仅在R5仍阻断、非UNKNOWN、当前assessment存在且reason为 `yield_visible_upper_lane/yield_visible_front/yield_entered/yield_visible_inward_motion/yield_occupied_corridor`、参与者恰好一辆且两车前向世界vx非负时启用。其他情形沿用fixed。全部参与者来自当前有限观测物理签名，不按真实ID排序；多参与者不简化成全局选出的赢家。

设原NOA请求为b，原R5经过stop-tail/舒适/硬界裁剪的等待请求为f。本车候选是去重排序后的 `{b, min(b,0), f}`，逐项使用相同stop-tail与加速度界裁剪；不得提出高于原NOA b的请求。对方模型动作固定 `{-0.5,0,+0.5}` m/s²，原硬速限内的常加速度运动，用既有 `distance_at` 计算5s后位置；此简化预测只用于排序，不用于安全放行。

令D=两车当前投影半长之和+2×原body margin+原standstill gap，g=x_peer(5)-x_ego(5)，q=max(0,(D-g)/D)^2。两方代价均为 `q + ((v_i(5)-5)/5)^2 + 0.05*(a_i/0.5)^2`。目标5是我方指定的邻车模型假设，不是邻车真实目标；D仅表示希望对方在前的纵向分离，不能称作安全证书。参数固定、无结果后调优。

- fixed：沿用f及原守卫。
- minimax：在同一矩阵上选 `argmin_a max_b J_ego(a,b)`；并列选较小本车加速度。这里只对三个模型动作做最坏情况排序，不宣称覆盖真实邻车全部动作。
- stackelberg：对每个对方动作b求完整 `BR_ego(b)=argmin_a J_ego(a,b)`；对方选 `argmin_b max_{a in BR_ego(b)} J_peer(a,b)`。多最优响应按leader最坏代价、再较小ego加速度；leader并列取较小peer加速度。精确有限比较，不以人为唯一私有状态/身份破局。
- 最终仅执行本车动作；记录全部矩阵、BR集合、选中模型对方动作与本车动作。模型对方动作不传给任何车。
- 若模型选中不同于f的请求，必须先通过原 `verify_candidate` 全5.5s保持车道守卫；失败记录并回到原f/原guard路径。不缩减邻车硬加速度可达包络；f不通过时与5C一样保留原NOA请求。紧急与已提交plan均绕过新层。

新增参数：`r5_waiting_policy` 为fixed/minimax/stackelberg；非fixed显式记录预测时域5s、预测对方动作尺度0.5m/s²、分离/速度权重1、努力权重0.05。fixed默认无新增策略参数，保持5C数值/动作兼容。原数值全部不变。

## 实施与测试文件

- [ ] 创建 `noa/waiting_game.py`：模式校验、物理矩阵、有限minimax/悲观Stackelberg求解、诊断；不读文件/随机/全局状态。
- [ ] 修改 `noa/controller.py` 仅原R5阻断的proposed/guard路径，先验证新模式，保留fixed的原动作/记忆/诊断；接入新层不修改R5决策。
- [ ] 新增 `tests/test_phase5d_waiting_game.py`，先RED再实现GREEN：手算非平凡双层矩阵与minimax不同；多BR悲观处理；动作排序不变；参数非有限/类型拒绝；单车/多车/未知/低速角色回退；完整控制输入次序与身份变换；R5关/紧急/active plan不改；新动作守卫失败与fixed守卫失败分层回退；最低换道速度仍有效、私有状态无新抽样。
- [ ] 修改 `experiments/phase5_r5.py`、`experiments/phase5_r5_replay.py`、`run.py`：显式 `--waiting-policy` 参数，run metadata及expected_variants绑定模式。仅R5 ON且lane_priority不为False的变体采用新模式；OFF和旧waiting基线固定。默认fixed保留原矩阵格式与parameters。
- [ ] 新增 `tests/test_phase5d_harness.py`：严格枚举、参数/源码/输入绑定，完整短测试包重放，重哈希篡改模式/诊断后拒绝。测试短窗仅测试工具，不作正式效果证据。
- [ ] 回归源冻结、受影响整套测试（沿用原排除已验收stage1产物5项的边界），独立规格/质量审查，再正式运行；所有失败尝试独立日志只读保留。

## 固定实验，不重抽或改物理初态

正式使用5C已封存扩展包，SHA256 `a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a`：single_clear20s与gradual_three60s，原6变体完整矩阵（OFF/ON各2、single半控制步1、三车旧waiting1）。分别执行minimax和stackelberg，两包12变体；fixed比较使用5C已完成的同一扩展6包，不重跑旧失败来选择结果。

60s三车是本轮唯一活跃新策略物理场景，不可称作留出集/多种交通条件/统计验证。原8场景及此前留出失败继续保留，不把本轮局部结果推广为阶段5科学通过。半步核验仍仅single_clear，不冒充活跃博弈采样验证。

逐车指标：阻断拍数、新层启用/回退、选中/实际应用请求、首个候选/提交/完成、episode清除时刻与速度、末速度/位置、原检测器全5 actor与3受控车子集形成区间、原驾驶/舒适、几何与SUMO报告分列。完整窗才算均速差，失败前缀不可补零/外推。

命令在新variant：`PY -I -B -S scripts/run_logged.py --label phase5d_formal_MODE --timeout 1800 -- PY -I -B -S run.py phase5-r5 --case-file phase5c_extension.json --waiting-policy MODE`；每包结束用相同封存源码 `run.py phase5-r5-replay --run-dir ABS_RUN` 进行标准语义重放，失败不改写为成功。

## 验收与下一入口

- [ ] 保存文献来源/阅读范围与局限、参数变化、前置核验、RED/GREEN/回归/独立审查、正式两包、标准重放以及数据摘要的快照重放与哈希封存。
- [ ] 只有全部通过的工程条件才能标通过；未形成继续scientific=false、phase6=false。即使少刹车改善，也不能说速度门槛/普遍公平性/停止端/全局形成已解决。
- [ ] 根据真实结果更新 `docs/phase5_next_entry.md` 与检查点：下一阶段仍在5内，分别判断等待动作、物理重新启动、最小速度/端点和形成守卫的约束；不自动另改参数补救。
