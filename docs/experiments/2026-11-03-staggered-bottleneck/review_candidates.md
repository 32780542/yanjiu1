# A / C / D 独立源码与影子状态审查

本审查读取实际 `tmp/staggered_bottleneck/candidates/*/native_rules.py`，与 Git
`177f7a32088fb69efcc94d9acb72863e7e00e787` 的 TM 比较。没有修改候选、生产规则或原核心测试，未执行新的 SUMO 仿真。
可重跑驱动为 `tools/review_candidates.py`；原始机器结果为
`review_candidates_verification.json`。这是源码及代数合同验收，不是效率采用结论或全工况安全证明。

## 结论

A、D、C 的实际 AST 改动均限于声明范围，常量、导入、Vehicle/Command/Memory 定义均未变化。
未发现新增通信、真实车辆 ID 优先级、车型真值、全局槽位或中心调度。
新增运算只使用本车、收到的有限邻车状态和现有私有记忆。
适配器 `LocalTracks.observe` 仍仅给每车前 200 m、后 100 m 的私有轨迹，候选未改适配器。

| 候选 | 实际 SHA256 | AST 变化 |
|---|---|---|
| A gap_projection | `afa7ff9c85fdd9efae9c66805415e095d560eab750c7ce9722357098bcf552f5` | `_merge_target`, `_join_speed`, `_decide` |
| D continuous_phase | `ba78a9a19e1a876444afec9ef383a111243c4c504a0d9e511a29db9c2130e22e` | `_phase`, `_fill` |
| C effective_handoff | `9b7f80dc6f7f4fb6352f2fb8356fbf57cb14aef1aa03bb3b6c8457bb0002bbe4` | `_make_room` |

生产规则审查前后均为
`65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`，与冻结 TM 逐字节相同。

## 独立验收

随机种子 `202611030931`，共 2000 组有限数值场景，包含 640/1000 m 边界、横移中、pending 请求、已有 lane_target/gap/joining 记忆和部分失效 gap track。
比较完整 Command 和 Memory，使用精确数值相等，没有放宽容差。

| 检查 | A | D | C |
|---|---:|---:|---:|
| NOA 完整命令及记忆与 TM 精确相同 | 2000 | 2000 | 2000 |
| 三模式 straight3 与 TM 精确相同 | 未要求 | 6000 | 6000 |
| 任意重标 track 并反转邻车顺序后相同 | 6000 | 6000 | 6000 |
| 加入远处车辆后相同 | 6000 | 6000 | 6000 |
| transform 与 TM 实际发生差异的影子场景 | 745 | 38 | 2 |

AST 所有排序 key（包括命名 key 函数）均无 `.track` 优先排序。track 仍用于同一物理对象/私有记忆对应。
本随机样本未生成物理状态完全相同的重叠车辆，因此重标检验不是对所有退化平局的穷举证明。

D 的三道偏移 `[0,15,0]`、两道偏移 `[0,15]` 独立验证通过；三道 `_phase` 数值不变，
`_fill` 将原嵌套相位表达式统一为同一函数，未加入新锚点或外部槽位。
这避免了存续物理车道因道路道数变化而重新翻转相位，但不证明全交通系统必然改善。

A 只在组织驾驶的真实前后车间隙中投影目标位置，NOA 的 project 分支为 false；间隙不可行时仍回退旧目标。
其参考速度仍为前后车均速，故目标投影并不意味着绝不减速。1 s 相对速度走廊也不是对完整换道过程的安全证明；
共同 `safe_speed` 和 SUMO 执行防护未改变。

C 只对原 `_make_room` 候选增加三项当前观测筛选：头车确实受阻、helper 左侧走廊当前可用、移除 helper 后头车走廊可用。
随机场景中实际选出的 58 次 helper 均逐项通过；不读取其他车私有阶段，也没有假定 helper 已经完成横移。
原执行分支仍等待实际观察到空隙后才给头车横移请求。这是本车所见状态下的反事实几何筛选，不是全局可行性承诺。

## 保存的执行记录

- AST / 2000 影子场景：`results/operations/20261103T031926104253Z_staggered-independent-A-C-D-shadow-review_6d94b1ff`，退出 0，9.485 s。
- A 专项 5 tests：`results/operations/20261103T032000040985Z_staggered-independent-A-contracts_bb7289c5`，退出 0。
- D 专项 5 tests：`results/operations/20261103T032000051874Z_staggered-independent-D-contracts_4e4a8253`，退出 0。
- C 专项 8 tests：`results/operations/20261103T032000077268Z_staggered-independent-C-contracts_d737c6ca`，退出 0。

这些记录不取代 SUMO 筛查结果。A 的无改善结果、D/C 后续可能的失败及未完成案例都应照原数据保留。

## runner / seal / summary 复核与待修项

封存先执行原件 hash/选出字段核验、traffic ledger 复算和离线核验，再解析限定目录中的两个精确文件名。
所有目标 hash 在任何 unlink 前检查；不执行递归删除；worker/seal 失败保留原件和错误日志。
runner 最终成功条件同时要求 returncode、drained、safe、all_completed 与 verified，没有用进程退出码代替物理结果。
当前限定路径删除合同及失败保留合同已通过，未发现当前批次越界删除旧成果的迹象。

发现两项工具边界，父代理已要求先反例测试后修复，不需要重仿真：

1. **协议完整对应核验不足。** 原 summarize 只比较任务数，尚未逐案确认 protocol task、manifest、原 input/request/source 的一致性。
   现有配对参数/source hash 检查能拒绝一些混配，但不能代替计划矩阵验收。需要在出版前补齐，失败案例留在表中且不得进入有效配对。
2. **小数流量路径碰撞。** `flow:g` 的默认有效位数使 `1750.0001` 与 `1750.0002` 产生相同目录名。
   当前整数流量未受影响；应在启动创建目录前明确拒绝所有预定 case output 名称碰撞。

修复及所有已完批次的重新分析记录将另存，不改已经冻结的旧 driver 或重新运行仿真。

## 紧凑证据能证明与不能证明的内容

归档保存原 input/result/trips/六源字节、所有 active-id/0/1 原帧、选出的越线相邻观测括号，
以及既有 800–1000 m 区域的逐步人数/低速人数/速度和账本。
可据此离线重算对应 trip 统计、直接 flag 积分、记录的越线时刻/区段时间及既有区域指标。
短试验的正式 `[100,600)` 完整窗不足时保持 null，已观测交集暴露不能作为完整窗口比较或容量测量。

被清理的完整 positions/events 只保留全文件 hash 与字节数。**hash 本身不能在原文件缺席时证明选出字段来自它，也不能还原完整轨迹。**
这些包无法重新检查全部时刻的车辆几何、连续运动/换道走廊、区域外速度、完整事件顺序或任意新轨迹指标。
碰撞/瞬移数是保存的原 SUMO 结果，当前紧凑字段无法独立重做全时空碰撞审计。
可重跑源码与 SUMO 版本记录帮助复现实验，但不是对缺失原轨迹的逐字节替代。

traffic 离线核验仍依赖 hash 匹配的旧仓库方法源码；出版需同时保留这些依赖及工具，不能只交单个 traffic ledger。
每个 compact tar 中自带其 standalone verifier；这不意味着 companion traffic 部分已独立成包。
