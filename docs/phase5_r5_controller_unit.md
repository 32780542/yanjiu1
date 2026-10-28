# 阶段 5 R5 控制单元验收

2026-09-13。范围仅为 `variants/phase5_r5_common_development` 的控制补全；基底来自 A 已封存 94 个源码文件，不是 B3，也不是最终选定 B1 新版本的车辆验收。本单元没有运行车辆实验、没有读取 heldout 性能、没有改动旧 A/B 生产代码和结果。

**控制实现与必要单元回归通过，独立审查无剩余 P1/P2；车辆机制、记录重放和科学门槛仍分别待验收。** 冻结计划 SHA256 为 `db9e5e09533adbeb837967a41188f32a2d6294867d6d914386085ed3b973b5fc`；设计通过后才实施，后续状态机确定化记在 [实现澄清](D:/yanjiu1/keyan1/docs/phase5_r5_implementation_clarifications.md)。旧阶段 5 原实现缺少随机退避是实现缺项，不能用允许实验失败替代补全。

## 实际改动与接口

| common 相对冻结 A 的文件 | 实际内容 |
|---|---|
| [noa/contracts.py](D:/yanjiu1/keyan1/variants/phase5_r5_common_development/noa/contracts.py:11) | NoaMemory 新增七个自身 R5 字段，uint64 私有状态、抽样计数、phase、deadline、物理 episode、clear 起点及自身上次时间；codec 递归恢复 tuple 并拒绝非法组合。 |
| [noa/r5.py](D:/yanjiu1/keyan1/variants/phase5_r5_common_development/noa/r5.py:17) | 纯 SplitMix64、有限可见物理竞争判断、物理兼容唯一关联与自身退避状态机；无文件、墙钟、在线随机熵、ID 或他车计划入口。 |
| [noa/controller.py](D:/yanjiu1/keyan1/variants/phase5_r5_common_development/noa/controller.py:170) | 在新候选原守卫之前加入 gate；旧 active plan 优先、候选 preview 不抽样，最终选定等待分支才提交一次抽样；让行最终请求仍经原守卫。 |
| [noa/formation.py](D:/yanjiu1/keyan1/variants/phase5_r5_common_development/noa/formation.py:171) | 仅在 risk 表达式插入一行：R5 开启且存在未清 episode 时抑制编队增量。正式 B1 整合只能应用这一行，禁止整文件覆盖 B1 的选择算法。 |
| configs/phase5_r5.json | 七项单独版本的实验前参数；全部原物理、安全、PD、目标速度及响应值不改。 |
| tests/test_phase5_r5_controller.py | 25 项 R5 契约与控制边界测试。 |
| tests/test_phase4_controller.py | 仅新副本的 NoaMemory 精确字段集合测试接受七个新增自身字段；禁止 ID/非局部源等 AST 守卫未放宽。 |
| docs/parameter_registry.csv | 原 A 字节前缀完整保留，末尾新增七行；仅新增行来源元数据经一次修正，旧登记版本和日志保留。 |

`assess_candidate(control, road, candidate, memory, p)` 先处理近邻已经进入目标条带或可见向内横移，再处理普通 same-gap 的明确前者/近同时条件。信息来自本车重建道路、当前有限理想测量和本车自身记忆，不把旁车 PREPARE、意图、车型或真实 laneID 当可见量。0.05m/s 只是当前惯性横移线索，回中也可能触发；低于阈值的初启仍不可见。

`advance_backoff(assessment, memory, now, p, allow_draw=True)` 保留同 episode 已抽取的 deadline 与计数，YIELD/UNKNOWN/ego-front 不能提前取消承诺等待。到期重新检查当前条件，不绕过原 5m/s 门槛、prepare 或原守卫。不同候选的 preview 不继承别的目标的阻塞，也不私自清除其状态。丢失/多义物理关联进入保守 UNKNOWN，不把缓存当新的真实观测；持续可见 clear 一秒或明确新目标等规定事件才结束旧 episode。

新 plan 的原预测使用最终实际 `candidate_accel`。让行使用当前车道零横移 `QuadraticLaneChange` 与最终限幅请求核验；**新减速未获守卫接受时不称安全已证明**，记录 `yield_not_certified` 并保留原驾驶 fallback。既有机动不清 plan、不清转向；紧急制动优先。原预测时域、额外邻车横向加速度界 0、执行器 lag=0.2s、NOA planning response=0.3s 均未改。

## 参数与来源

| 新参数 | 值 | 单位 |
|---|---:|---|
| r5_enabled | true | bool |
| r5_front_margin_m | 2.0 | m |
| r5_visible_inward_speed_mps | 0.05 | m/s |
| r5_yield_deceleration_mps2 | 0.5 | m/s² |
| r5_backoff_min_s | 0.5 | s |
| r5_backoff_max_s | 2.0（不含上端点） | s |
| r5_clear_stable_s | 1.0 | s |

状态均为 `predeclared_r5_development_unvalidated`。配置含 rationale 与原规格来源；registry 的 source/page_or_url/source_line/source_sha256 则准确指向该配置实际 name 行 11/17/23/29/35/41/47。配置 SHA256 `c828ecd82e6a36b91d5526f42072b969ad772da708cc2fb83b162dd67a99ed95`；最终 registry SHA256 `5403de7ecc24f2c518e87ac1c019e4b9b90e89a1949caa72fd24648a834c900d`。登记来源修正日志为 common `results/operations/20260912T213601376046Z_phase5_r5_registry_provenance_correction_52bb8548`，未改变任何数值。

## 测试、失败与修复

所有命令使用登记 Python312 的 `-I -B -S`，通过 `scripts/run_logged.py` 设置外部超时。以下日志均在 common `results/operations/`；失败退出码原样保留，未删去旧快照。

| 证据 | 结果与含义 |
|---|---|
| 20260912T204544419044Z_phase5_r5_controller_red_1c7d904b | 初始缺模块 RED，先有失败才实现。 |
| 20260912T205154632047Z_phase5_r5_schema_red_7ac37096 | 旧字段精确集合拒绝新增状态；仅更新隔离副本 schema 测试。 |
| 20260912T210740967755Z_phase5_r5_lifecycle_red_e5eda6a1 | clear 期间到期状态未推进的真实失败；另含不完整 active-plan 夹具，分别修复实现/夹具。 |
| 20260912T211722382701Z_phase5_r5_unknown_gap_red_48caa67b → 20260912T211803784980Z_phase5_r5_unknown_gap_green_af0f4081 | 旧缓存 UNKNOWN 恢复和新 gap 角色关联的两个失败关闭。 |
| 20260912T211951653957Z_phase5_r5_candidate_scope_red_63ae13fe → 20260912T212012005846Z_phase5_r5_candidate_scope_green_b1282616 | 旧目标 A 等待错误阻止另一目标 B；修为独立 preview。 |
| 20260912T212607393184Z_phase5_r5_memory_time_red_afe06cd8 → 20260912T212648543125Z_phase5_r5_memory_time_green_afd49174 | 六种非法 stored phase/time 组合由接受变为拒绝；合法旧 BACKOFF 跨当前期限仍接受。 |
| 20260912T212753517084Z_phase5_r5_affected_final_v3_596df9dc | 最终控制代码 71 项通过，22.026s 测试时间；25 项 R5 加 46 项受影响旧 controller/clock。 |
| 20260912T213657031223Z_phase5_r5_controller_snapshot_replay_v4_95f6780e | 修正登记后的最终快照，从 D:/yanjiu1 外部 cwd 重跑同 71 项通过，22.179s；没有导入 common 当前 runner。 |

测试覆盖固定 PRNG 向量、纯调用/独立私有流、JSON 恢复、ID 改名与列表重排、平移、前界/后界/重叠 entered、inward 阈值与消退、未抽样 YIELD、deadline 跨 YIELD 和 ego-front、同 seed/同离散事件、clear/失联/多义/新 gap、低速不能启动、紧急、active plan 连续性、新候选与被拒让行。stub 守卫的测试仅证明分支和状态契约；不作为实际碰撞/舒适性证据。

[独立审查](D:/yanjiu1/keyan1/docs/phase5_r5_controller_review.md) SHA256 `40df5eefa52f6df20fbdd4e808b704ff2ca2500c90a246ad7443a1e7382985bf`，明确没有剩余 P1/P2。审查者保存的候选作用域和非法时刻原反例均已复验，独立重跑 25 项通过；十组关闭分支与已封存 A 完整 decision 相同，16 个共享模型/预测/感知/旧配置等字节未变。审查者另用真实原守卫验证：清空后方时 −0.5 请求在原 5.5s 检查通过；加入快后车后同请求约 0.24s 被拒，实际返回原 fallback。后者不证明 fallback 一般安全，也没有执行 SUMO 车辆控制区间。

## 最终可重放证据

最终快照 [r5_controller_unit_20260912T213615273452Z_08f22109](D:/yanjiu1/keyan1/variants/phase5_r5_common_development/results/phase5/r5_controller_unit_20260912T213615273452Z_08f22109/source_provenance.json) 包含冻结 A 94 源码及五输入、仅八个本单元 overlay、计划/澄清、生成脚本和完整 hashes.json。旧 v1/v2/v3 是保留的开发证据，不以它们代替最终来源。

`hashes.json` SHA256 `26ee5c26d1ea7867c75a96bc48f52c112b745155ea8b68b51fb1df063a5dd52e`；provenance SHA256 `c37242d0751321def86a11ed780302451bd0327541f41af6de8e2f66cccdb244`。独立外层脚本核实 106 个成员的 exact file set、全部哈希及八个当前受控文件均与快照一致：[verification.json](D:/yanjiu1/keyan1/variants/phase5_r5_common_development/results/phase5/r5_controller_verify_20260912T2139/verification.json)。验证脚本快照也已保存；该校验仅指单元快照，不冒称车辆整包语义重放。

复跑命令记录在 v4 replay 日志的 started.json；核心为将 Python sys.path 插入绝对快照根，依次 discover `test_phase4_controller.py`、`test_phase4_clock.py`、`test_phase5_controller.py`、`test_phase5_clock.py`、`test_phase5_r5_controller.py`。工作目录明确为 `D:/yanjiu1`，防止当前同名模块替代快照。

## 未通过或未完成条件与下一入口

随机退避不保证互斥、公平、通行、整队恢复或无碰撞；同 seed、不同延迟落在同一行为 tick、初启横移不可见、回中假阳性、持续 UNKNOWN 均保留为反例。物理兼容关联不是身份真值，硬域上界较宽可能增加 UNKNOWN。目标 5m/s 下减速跌破 5 后可能有限时间内再也达不到原启动门槛；ELIGIBLE 仅表示计时到期。

下一入口仍是阶段 5：独立完成 R5Clock 初态/记录/重放审查，按正式已选 B1 生成新副本，封存私有 RNG 初态和固定机制 case 后才运行真实竞争/无竞争/再入与预登记负例。旧 A/B 与旧 heldout 只能支持旧实现。控制单元通过不补写为新版已经车辆通过，也不开放阶段 6。
