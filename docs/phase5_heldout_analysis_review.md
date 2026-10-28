# 阶段 5 heldout 汇总独立审查

2026-09-13（Asia/Shanghai）。最终结论：两个 P2 已关闭，共同完整窗口统计修复也通过独立复验；未发现仍阻断冻结的 P1/P2。建议以最终 SHA-256 `f80314e9b0334ead62b2511bfe017c74696b95263a7e6724fbed883a44c4e4d0` 的精确字节冻结 `phase5_heldout_v1.py`。

初审对象为 `tmp/phase5_comparison_design/phase5_compare.py` 的 heldout 汇总与选择来源验证，初审 SHA-256 为 `b9495cd398afc5f6d4b96dc5fc035830ccc5103b7cb567294ed9f8bd88d9bcd6`。本轮不修改生产代码、已冻结绑定/选择 v1 或预登记，不读取实际 heldout 结果。文中合成输出不能视作物理实验通过。

## 初审发现与保留证据

初审发现两个 P2，因此当时未建议冻结该版本为正式 heldout 分析器。均由只修改合成选择包并重新封存的负探针复现，不需要更改原绑定、实际开发输入或冻结选择器脚本。

1. **旧数据路径未与绑定来源强制相等。** `verify_selection` 验证了旧 binding 的 `source_before`，随后却从独立的 `selection.input_bindings[method].run` 路径重新计算分数。探针只将 B2 的该路径指向一个未绑定的复制目录，改复制目录的检测结果，并同步保存的 case summary、score 与选择字段；旧 binding 完全不变。验证仍接受，且赢家从 B1 变成 B2。需要强制解析后的 `item.run == binding.source_run`，并只从此绑定来源读取分数事实。
2. **重新计算仍信任可改的内嵌案例矩阵。** 重算使用 `selection.preregistration.matrix`，未重新验证其与固定 SHA 的预登记快照相等。探针将内嵌开发随机案例从六个缩为一个，保持原预登记快照不变并重封，仍被接受。需要复验固定预登记清单和其文件，并要求内嵌 matrix/rules/files/hash 与已验证快照相等，使用该固定矩阵重算。

独立证据保存于 `tmp/phase5_heldout_review_20260913/`：原脚本副本 `review_snapshot.py`、探针 `probe.py`、`probe_result.json`、`redirected_selection`、`changed_matrix_selection` 及完整合成输入。总日志 `results/operations/20260912T193225865039Z_phase5_heldout_independent_integrity_review_ce7b8ff3` 退出 0、9.937 s，表示上述漏洞断言确实成立；不能误读为两种坏包正确拒绝。原始合成选择包所有文件摘要前后一致。

## 已核对的汇总规则

完整 heldout case 必须等于封存的六个完整对象，种子顺序为 6111、6112、6211、6212、6311、6312；包括初态、生成尝试数、scripts 和其他字段，不能只核对种子名称。A 和选定 B 分别从各自开发来源派生，只允许 `configs/phase5_experiments.json` 的既定种子和 rationale 变化；输入登记行只允许既定 seed/rationale/status，计划只允许精确追加文字。共同模型、控制、安全和检测器参数与逐 case 初态继续比较。

完整 OFF 轨迹必须字节或逐记录 JSON 语义相等才允许合并；部分 OFF 只报告已完成公共前缀相等，不作为完整 OFF。六个已登记 seed 始终保留。未开始的 case 输出 null 和明确状态；C 在执行不完整或缺完整窗口时为 null。按 seed 的差值保留六项，任一项缺失时整体 mean/median 为 null，available_pairs 可小于 6，registered_pairs 固定为 6，不删除缺失案例后重估。统计没有按车辆或时间帧扩充样本，也不提供显著性检验。

独立探针验证：五个有效 C 配对加一个缺失项，mean 与 median 均为 null、available_pairs=5、registered_pairs=6。另构造三次参考决策：同一前车位置更新一次，随后真正更换为另一辆车，离线计数得到 acquisition=1、change=1；没有把位置更新算成换参考。两个实际记录的 prediction 中一个被拒绝，拒绝率为 1/2，未调用 prediction 的帧不进入分母。

离线参考匹配使用记录的物理 signature 与同帧真实状态进行唯一匹配；这些全局标签只用于事后统计，未送入控制器。无法唯一匹配时换参考总数为 null。直接非空参考变化、参考丢失与重新获得是分别记录的事件，不能把三个计数混用。

## 解释边界与复验入口

`passed` 表示来源验证和汇总过程成功；`full_matrix_observed` 表示计划的普通案例及数值对照是否全部完整执行，二者都不能替代形成、安全或舒适的科学判定。即使程序汇总通过，研究结果仍可能全部失败或没有改善。`merged_primary_units` 是具完整 OFF 合并证明的三方法单元数，不应单独用来声称所有 on 的完整驾驶窗口均已观测；同时检查 incomplete_variants 和 full_matrix_observed。

已开始但失败的前缀仍有合法的观测事实，如最后位置、前缀最大 jerk 和前缀守卫比例。初审版本也会对这些仍为数值的字段生成配对均值，因此不能把它们解释为同样 45 s 窗口的改善。若报告需要固定完整窗口比较，应保留单 case 前缀事实，并将不完整案例对应的窗口比较字段置 null；成功/安全失败二值可保留为已发生的研究失败。

修复代理已收到两个可直接重放的坏包。关闭条件为：原合成选择正检通过；上述路径重定向和矩阵篡改两种包都拒绝；既有缺 seed/null/固定分母与完整 OFF 配对行为保持；全套汇总验证通过后，再冻结新的 heldout 分析器并保留旧版本及本轮失败证据。

## 修复后独立复验与最终入口

中间版本 `0a433ce397a7c8ebd27731ea597d90f82436031fdeb7c4d9f5604d6d8478e557` 对选择消费增加了完整来源重查。它从固定 SHA 清单重新验证预登记、v2 澄清和 heldout 初态快照，要求内嵌 matrix/rules/files 与快照相等；按固定矩阵调用 `load_bundle`，强制显式 run 与绑定 source 相等；再核验三方法源码、输入、case 与 OFF 可比性，并从绑定案例重算摘要与分数，也重查原新进程 A 初态输出及其源码摘要。原正例通过，两个保留的坏包原样分别以 `Explicit run does not match its replay binding`、`Embedded preregistration differs from the fixed verified snapshots` 拒绝。

中间独立日志为 `results/operations/20260912T193925150200Z_phase5_heldout_fixed_independent_review_bb140dca`，退出 0、10.766 s；脚本副本、探针和结果为 `fixed_review_snapshot.py`、`recheck.py`、`recheck_result.json`。该轮还重现了完整合成 18 单元、失败前缀以及未开始最后一个 seed 三种汇总，并保留了共同窗口问题的反例：20 s 前缀 jerk=.2 与完整对照 jerk=.4，被旧统计写成第六个 seed 差值 −.2 和六 seed 均值 −.03333333333333333。这一数值只属于合成分析程序的旧行为，不是驾驶改善证据。

最终版本增加共同完整窗口约束：连续指标只在两侧 `full_execution is True` 时生成配对差值；否则明确为 null 并给出 `incomplete_observation_window`。raw case 中的前缀事实保留。已发生的整体/局部成功、安全、舒适等二值事实仍按其记录保留；未开始的二值仍为 null。六 seed 的总分母不变，mean/median 继续要求全部六项可用。

最终独立日志为 `results/operations/20260912T194132782130Z_phase5_heldout_final_independent_review_ed6b2a56`，退出 0、7.078 s；保存于同一审查目录的 `final_review_snapshot.py`、`final_recheck.py`、`final_recheck_result.json` 绑定最终 hash。实际验证如下：

| 验证对象 | 最终结果 |
| --- | --- |
| 原固定选择与两种旧坏包 | 正例继续通过；重定向、内嵌矩阵篡改继续拒绝 |
| 六 seed 完整、所有形成结果为 false 的合成包 | analysis passed=true、full_matrix_observed=true、18 合并单元；没有因此把形成记为成功 |
| 第六 seed 在 20 s 失败 | raw jerk=.2、observed_end_time=20 s 保留；jerk 的该项差值、mean、median 均为 null，available_pairs=5、registered_pairs=6；安全失败差值仍按已发生事实保留 |
| 第六 seed 未开始 | 六行仍存在，OFF 无完整合并证明而为 null；合并单元 15，full_matrix_observed=false；C、jerk、整体成功与安全的配对 mean/median 为 null |
| 历史材料 | 原选择、旧坏包及前次分析包所有文件摘要前后一致，未以通过版本覆盖历史失败 |

绑定 v1 仍为 `622991c1e5a4aa66f1270120ffc5eceb87f7ebed590cc4a8ad4be1bab8f3cae2`，开发选择 v1 仍为 `f2da6e517f3e6be61a0b0c08ac106c931360fa52b69896343282d37c09a7af1c`，本轮检查确认未变。新增修复只影响离线来源核验和统计资格，未改变控制器、安全阈值、种子、实际生成初态或方法选择准则。

下一入口是冻结最终分析器，等待真实开发三包全部封存及各自标准回放绑定，执行并封存开发选择，再按既定六初态运行 A/选定 B 的 heldout，最后调用冻结分析器。此次审查没有产生真实 heldout 的形成率、舒适性收益或显著性结论。
