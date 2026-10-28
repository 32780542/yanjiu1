# R5 控制实现独立审查

日期：2026-09-13。对象为 `variants/phase5_r5_common_development` 内的 `noa/r5.py`、`noa/controller.py` 接入、`noa/contracts.py` codec 与 `noa/formation.py` 抑制条件。依据已审计划 `db9e5e09533adbeb837967a41188f32a2d6294867d6d914386085ed3b973b5fc`、独立风险/测试设计及实现澄清中“同 episode 已承诺等待不因 ego-front 提前取消”的解释。

**结论：本次控制层审查通过，没有剩余 P1/P2。** 可按下列源码封存控制单元，进入独立记录/重放及预登记机制实跑入口。此结论不表示整包记录通过、车辆实际避碰/舒适性通过、R5 实验成功或阶段 5 科学门槛通过。未修改生产源码、旧 A/B、heldout 或 v1。

| 被审文件 | 最终 SHA256 |
|---|---|
| noa/r5.py | `c3e70c793da10783e4f499a3d5b35cfa6c99f8ca0e227650f12eaa4a08e32ddc` |
| noa/controller.py | `7deb810fcce825144d55aa2a8dfcb3e547df79daf2f2e3e38e92d796959e7ac2` |
| noa/contracts.py | `104eb68e4995ecd08b413a1c1a06b30cf3ade9d2e5fd7a9518782ec58df8e82e` |
| noa/formation.py | `ac0165d2cb5d5ddc80e8164994e390e07a589cd37ec92c1f8ae3f7d37fd8fae7` |

最终独立命令前后核验这些文件哈希未变；独立快照、合成输入及结果在 `tmp/phase5_r5_control_review_20260913`。原预测、模型、感知、几何、基础时钟和旧配置共 16 个相关文件与 root 冻结基线逐字节一致，完整列表在最终结果 JSON。

## 发现、反例与修复

**P2：旧目标让行阻止了另一无竞争目标。** 旧 `advance_backoff` 在检查目标变化前处理 `no_potential_competition`，把目标 A 的 YIELD/BACKOFF/ELIGIBLE 作为候选 B 的阻塞状态。独立局部反例中，自车在中道，上道 peer 导致 A=8.25 的 YIELD；第一 tick 下道候选不通过测试守卫。下一 tick 同样可见输入下，即使下道守卫已允许，保留 A episode 时只检查同车道 hold，B=1.65 根本没进入守卫；无 episode 的同输入却进入 B 的 PREPARE。这违反多候选的作用域及“有无需等待且安全候选则选它”的计划。

反例保存为 `candidate_scope_result.json` 和 `before_candidate_scope_fix` 快照；日志 `results/operations/20260912T212009170122Z_phase5_r5_candidate_scope_independent_negative_2785ca5f`，退出 0、0.437 秒，表示成功复现问题。测试明确 stub 守卫，只证明控制分支可达性，不构成安全证据。旧 r5 SHA 为 `eb42103fbe8f7b4319dc2da3d9cb1adaa78fb8c4d39424ac49a05f120c7d69f0`。

修复后，跨目标的无竞争 assessment 只产生独立不阻塞 preview；B 只有通过自己的原守卫并被选中才提交该 preview，未选 B 不清除 A 的等待。完全相同反例输入复验，保留 episode 与无 episode 两侧均进入 B 的 PREPARE，动作相同、随机计数仍为 0。最终日志 `results/operations/20260912T212924575882Z_phase5_r5_candidate_scope_fixed_independent_a833912b`，退出 0、0.484 秒。

**P2：存储 phase 与其存储时刻不一致仍被接受。** 独立 probe 从有效首次 BACKOFF 记忆构造三例：deadline=−1；last_time=0.1/deadline=0.05 仍为 BACKOFF；last_time=0/deadline=0.05 却已为 ELIGIBLE。旧校验只看当前 now 的部分关系，三例均被接受。记录在 `geometry_time/result.json`，日志 `results/operations/20260912T212312564044Z_phase5_r5_geometry_time_independent_probe_6fc6bb25`，退出 0、0.485 秒，表示坏状态接受事实被保存。旧 contracts SHA 为 `e923923c40ad525cfa782d9e99c39d0400130140414d0ec4c212dd8cc588e8ac`。

最终 codec 按上一已保存 `r5_last_time_s` 校验 BACKOFF/ELIGIBLE，活跃 episode 必须有该时间；clear 起点不得在存储时刻之后，且必须属于活跃 episode。YIELD/UNKNOWN 可以保留未来或已到期的锁存。旧 BACKOFF 合法跨越到当前 now 的期限仍允许自然变成 ELIGIBLE。保存的三例原样复验全部拒绝，普通局部输入仍保持合法 BACKOFF：`results/operations/20260912T212924573882Z_phase5_r5_state_time_fixed_independent_49c90d6b`，退出 0、0.469 秒。

**作者自审修复已核对。** UNKNOWN 保留旧签名时，不能在更新时间后把缓存伪装成上一帧来自动恢复；最终同目标 UNKNOWN 锁存至当前可见 clear 或明确新目标。前/后可见 anchor 的唯一兼容关联发生角色改变时，最终可建立新 gap episode。对应新增测试已在独立 25 项重跑中通过；角色交换测试明确是关联/状态契约夹具，不能冒充真实车辆已经完成过该事件。

另对小幅自身位置/航向扰动做了观察重建探针，所测输入没有触发假目标失踪，结果原样保留；未将未复现的数值疑虑报告为缺陷。

## 已核实实现边界

- `assess_candidate` 只用当前允许的物理测量和可见道路。entered/inward 在普通 same-gap 条件前处理；局部近邻半径、投影占位、0.05m/s 速度阈值及 2m 前方优势有明确参数。既有 `measured_bodies` 按物理签名排序；没有读取 track_id、车型、旁车计划或共享优先状态。
- 私有 SplitMix64 是显式输入状态的整数纯函数，只有提交所选不可判定候选才抽样。新状态、累计计数、期限和物理 episode 进入自身记忆；普通 preview 不消耗随机。测试包括固定向量、重复/交错调用、JSON 恢复、标签/顺序变化、期限跨 YIELD 保留、同 episode 到期不重抽、clear 后重新抽样。
- 原 active plan 分支先行，不因退避清 plan 或瞬时回中；机动完成清除本 episode，但保留 RNG 状态和累计计数。原前车/车道终止/紧急纵向控制继续优先，紧急制动不被裁回舒适界。
- 已有 episode 在速度不足和无当前换道动机时仍更新。ELIGIBLE 不绕过原 5m/s 门槛和 prepare；同目标未知/清除未确认可以继续保守阻塞。编队层以基础 R5 状态和未清除 episode 抑制增量，不能把让行减速加回。
- 新 plan 启动时，实际返回的纵向请求就是本次原候选预测使用的 `candidate_accel`；没有在通过后再附加 R5 减速。未启动让行使用最终裁剪请求与同道零横移 hold plan 调用原预测器，拒绝时明确保留 `yield_not_certified` 和原 fallback。

AST 检查及代码阅读确认 controller/r5 未增加在线 random、secrets、墙钟、文件、TraCI 或 ID 属性入口。它们不能单独替代记录层的全轨迹反事实；私有初态路由、冻结观察、抽样后未提交失败及 canonical memory 链仍由下一记录单元验收。

## 冻结基线与真实守卫的独立检查

最终独立运行：`results/operations/20260912T213132437009Z_phase5_r5_frozen_baseline_real_guard_review_35b9683e`，退出 0、0.625 秒。结构化输出为 `tmp/phase5_r5_control_review_20260913/final_contracts_guard/result.json`。

1. **关闭等价。** 实读 root 旧 NOA controller，并核实它与 A 正式源包中的文件同字节（SHA `fd947943a861020c236b03636552b7080917516bddec7731121686c154c17ad1`）。在相同新版 dataclass 输入、相同参数及同样测试守卫返回下，巡航、候选、紧急、执行中、机动完成五类各配 safe/reject，共 10 组完整 decision 一致。这验证所测旧控制语义；新增 schema 不等于旧记录格式全字节兼容。
2. **实际原预测器接受。** 5m/s 自车、前方净距 31m 的 2m/s 慢车、对侧外道 5m/s 潜在竞争者，调用原真实预测器而非 stub。hold 请求为 −0.5m/s²，5.5 秒条件扫掠检查通过，控制器实际发出的请求恰为 −0.5，R5 抽样一次且未启动 plan。
3. **实际原预测器拒绝。** 在同局部输入加入后方 10m 的 30m/s 车，原预测器在约 0.24 秒因邻车可达占位拒绝同一 −0.5 请求。控制器报告 `yield_not_certified`，发出约 `−4.470348358154297e−8 m/s²` 的原基础 fallback，没有把被拒绝的让行请求强行执行。
4. **回归范围。** 本次独立重跑最终 25 项 R5 测试全部通过；这些包含计时、几何、恢复、候选与紧急/active 分支。作者更广的受影响回归是另一证据，不在这里冒称全部由本次重复执行。16 个共享模型/守卫/感知/基础时钟和旧配置文件经字节比较保持不变。

真实守卫调用在内部使用原预测积分器，但本次没有执行车辆控制区间或 SUMO，也没有观测到实际避碰/舒适性结果。接受分支仍以原本车未来请求及邻车运动假设为条件；拒绝后的 fallback 未获得一般安全证明。

## 保留限制与下一入口

同种子、不同延迟量化到同一行为事件、prepare 未出现可见横移、低于 0.05m/s 的初启、回中假阳性、持续 UNKNOWN、5m/s 渐近门槛及非配合车辆均仍可能造成等待、并发尝试或失败。原邻车额外横向加速度界保持 0，随机退避不保证互斥、公平、通行、无碰撞或整队恢复。新增参数仍为计划所列初始规则值，本次审查没有调参或筛种子。

下一入口：封存当前控制源码，完成独立 R5 clock/metadata/record/replay 审查；随后依据已冻结方法来源整合新副本，在完整物理与私有初态原字节绑定后运行固定机制矩阵，保留所有未触发、未完成和实际失败。旧 A/B 结果只属于旧实现，不能据此补写为新版已经验收，也不放行阶段 6。
