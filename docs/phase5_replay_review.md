# 阶段5重放与信息隔离独立审查（2026-09-13）

审查者未编写 `experiments/phase5_replay.py` 或 `experiments/phase5_audit.py`。本次只读审查这两份实现以及其直接依赖：实际阶段5runner、重放测试、原阶段4 SUMO读回复算、JSON递归比较、记录器、代码清单、理想传感器和几何/驾驶审计。审查依据为既有批准规格、阶段5计划、前置验收和 requesting-code-review / verification-before-completion 工作流。无有效Git HEAD，按源码SHA-256标定时点。

本报告区分数值证据重建与驾驶/科学成功；重放通过不能把碰撞、未形成或未恢复改为成功。审查只新建 `results/phase5/replay_review_20260912T174910Z/` 下的合成证据及独立命令日志，没有修改被审源码、原运行包或原日志。负责重放的代理收到发现后自行修复；其修复状态必须有后续复核证据才能关闭。

## 确认发现

1. **P1：可通过元数据放宽数值容差，接受伪造动作。** 在真实runner生成的0.2 s配对夹具中，仅将off变体 `metadata.model_parameters.replay_absolute_tolerance` 改为0.2，并将第一帧某车动作加速度加0.1 m/s²，然后重新生成证据哈希。整包重放实测仍`passed=true`，该trace报告`max_numeric_error=0.10000000000000002`。源码/配置快照不变，说明仅有源码哈希校验不足以将实际运行元数据约束到登记参数。应从匹配源码的冻结配置重建model、物理参数、策略参数并严格核对，只允许显式半采样差异；回放容差不得来自未验证的元数据。
2. **P2：事件及驾驶派生结论只保留哈希，未重算。** 第一版整包重放允许把0.2 s事件报告改成已形成、失效、恢复并保持；也允许伪造geometry/metrics及case/top驾驶结论为true。重新封存后两种探针均获接受，后者还返回`source_driving_gate_passed=true`。应从已复算轨迹重算事件演化、可见参考出入、车身、驾驶/舒适指标、SUMO告警解释及top科学条件。
3. **P2：冻结case到变体的覆盖校验只有一个方向。** 给 `frozen_cases.json` 额外加入一个从未执行的case，重新封存后仍通过；第一版只保证已有变体能找到冻结case。应验证每个冻结case均有off/on成对变体，且仅允许明确声明的首case半采样变体。

这三项已逐条发给主代理和重放负责人。另提出同一元数据绑定边界的静态检查要求：冻结duration与计划intervals一致、case/top的live标志一致、on/off后缀与双开关一致，以及complete_suite不能只信保存布尔。这些额外边界未另行声称已用探针攻破。

## 实际探针与来源

| 操作 | 实际结果 |
|---|---|
| `20260912T175012244082Z_phase5_replay_review_probe_19a4564f` | 退出0；旧版3种重新封存的事件/驾驶/覆盖不一致全部被接受，属于已确认审查失败 |
| `20260912T175421346617Z_phase5_replay_tolerance_probe_c0a9b708` | 探针退出1，`KeyError: ego`；期间测试夹具已被作者改为真实runner，车名不再是ego；这不是重放拒绝篡改的证据 |
| `20260912T175512034357Z_phase5_replay_tolerance_probe2_250b2a6d` | 退出0；使用当前夹具实际首actor重试，0.1 m/s²伪造动作通过，确认P1 |

首轮被审replay SHA-256为`39c25b71fb09a4b27ad25bec3b12b8fce67cc65fd2801c63b22aecfd1ce2eb66`，audit为`ea727da0a91f1d0ccea617f521efa6e4181ad491fc2e5fe6a3e202f3df57cdb6`。第一轮probe在17:50:12–17:50:14 UTC检查replay/audit/runner/tests四文件前后hash一致，见 `probe_results.json`。

容差第二次probe使用作者已增加部分派生复算的replay，前后hash均为`3efe39e12c85614c6437db7e0762271f693689b039304904da684cb9b32acaba`，详见 `probe_parameter_tolerance_result2.json`。此区分避免把初版发现错误归因给后续修复版，或将新版本已补事件复算误称为P1已关闭。

探针源码和新建夹具均位于审查目录，真实命令、解释器、UTC、退出码及stdout/stderr哈希在各 `results/operations/<上表ID>/`。旧探针目录只读；再次运行须复制脚本到新的同层审查目录以新建证据，不得覆盖现有包。一次探索性读取曾请求不存在的 `tests/test_phase5_audit.py`，实际测试位于 `test_phase5_replay.py`；已改读实际路径，没有把缺失文件当成测试通过。

## 已核实的实现行为与范围

在上述已确认缺口以外，静态核对确认逐帧重放重新创建KinematicModel/FormationClock，从冻结初态依次生成传感器输入、纯本车决定、记忆、动作和全部物理子步；`compare_tree`严格比较对象字段、离散值及数值。trace声明区间计数、额外尾行、截断和物理/完成区间计数均有核查。失败尾通过明确的阶段/actor边界重建可执行前缀，保留记录的原错误字符串，不声称重新制造了外部异常的原因。

live轨迹复用原阶段4 `replay_readbacks`，检查捕获阶段、每车覆盖、not_read/readback_exception状态，以及位置/朝向/速度/加速度/时间误差和碰撞/teleport报告。它复核保存的SUMO读回，不重新启动SUMO，也不能认证一份任意合成的原始报告确实来自外部进程。本次探针均offline；真实SUMO与全套回归由主任务另行执行。

`phase5_audit` 为每个车/反事实分支维护独立传感器并在每一帧推进历史，改变真实键拼写/顺序、隐藏车型、未来计划及范围外状态；采样时比较完整局部输入和决定。所用控制器自身记忆来自先经过完整trace复算的同一实际运行，因此这是“相同自身记忆下的采样因果反事实”，不是四条独立反事实闭环。代码和输出scope明确该范围。它还移除当前可见邻车检查动作响应计数，主runner要求全组非空洞计数>0；不能要求每车每帧都必须响应移除。

整包要求明确源目录，禁止回放输出落入已封存源目录；核查证据文件集合、代码快照集合、输入快照集合及当前源码全清单，拒绝缺项/额外项/路径逃逸/当前源码变化，且不会自行恢复或执行不匹配的旧快照。哈希提供封存后的完整性检查，不是第三方签名；本审查故意重新封存派生错误，用来验证是否存在独立语义复算，而不是要求抵御任意全包造假。

## 初轮结论（保留历史）

截至容差探针时，P1尚未关闭，不能将整包重放作为参数与数值证据的最终验收。事件/驾驶/覆盖的修复由重放负责人进行中；必须对修复版在新目录重做真实runner正例与上述负例，并检查源文件前后hash后，才能追加关闭结论。全套测试通过本身仍不等于阶段5科学目标通过。

## 修复后的独立复核与最终结论（18:02 UTC）

重放负责人完成修复后，审查者重新读取实际实现，并在**新的** `results/phase5/replay_review_recheck_20260912T180130Z/` 创建当前真实runner产生的短时offline配对夹具：干净包通过；4种重新封存的负例全部被明确拒绝。结果为 `probe_results.json`，其中记录18:01:41–18:01:50 UTC前后四份被审源码SHA-256一致。最终replay hash为`23315525472b4c686de8819118606dfc2468d0661c7b9292ef7c7a2eae59ca34`。

| 独立复验 | 实际结果和拒绝原因 |
|---|---|
| 当前干净0.2 s配对证据 | 接受；科学形成仍为false，未把短时运行解释为科学成功 |
| events恢复/可见性结论伪造 | 拒绝：`events.neighbor_count_exit_and_return: value differs` |
| 增加从未执行的冻结case | 拒绝：`Case index does not cover the frozen on/off and optional sampling plan` |
| geometry/metrics派生数据伪造 | 拒绝：`geometry: fields differ` |
| metadata容差改0.2且动作加0.1 m/s² | 在数值重放前拒绝：`fixture_off.frozen_model_parameters.replay_absolute_tolerance: numeric value differs` |

这次命令日志为 `results/operations/20260912T180141598249Z_phase5_replay_independent_recheck2_dd15cfd3/`，8.781 s，退出0。第一次复验脚本曾使用旧事件字段名`visibility_exit_and_return`，新版已改为明确的`neighbor_count_exit_and_return`，导致探针自身`KeyError`；日志 `20260912T180056948998Z_phase5_replay_independent_recheck_358a4858`及该次目录保留。随后根据实际schema在新目录修正探针，未修改被审生产代码。

修复版现在从已通过源码哈希一致性检查的登记配置重建model、物理参数和策略参数，以**零比较容差**绑定运行元数据；半采样只允许显式周期差异。另核对on/off后缀、live标志、冻结duration/intervals、case_index和冻结case/实际变体的双向覆盖；明确未启动变体的中断包只能按保留的partial范围处理。派生层重新计算事件演化、可见性、车身、驾驶与舒适指标、SUMO告警解释和top条件，并核对独立几何检测及采样对照结果。

此外，审查者独立实跑当前 `tests/test_phase5_replay.py` **14项全部通过**，测试器13.313 s，命令包装13.656 s，退出0，日志 `results/operations/20260912T180214380670Z_phase5_replay_independent_tests_b3b4a667/`。覆盖完整/off/on/JSON记忆、动作/输入/子步/记忆篡改、trace与isolation截断、已保存SUMO读回篡改、显式源路径、源/证据清单、检测/事件/参数篡改、积分与半控制周期复算和中断partial包。测试后再核四份源码hash，均与独立负例复验时一致。

**本次确认的1项P1及2项P2已由实际复验关闭；在所审范围内，未发现仍阻止阶段5开发证据重放的严重或重要问题。** 这只放行主任务继续完整回归、实SUMO及科学条件验收。本审查没有运行3/6/12车完整矩阵，也没有证明形成、恢复、串行稳定、连续时间安全、交通收益或阶段6通过。短时fixture为执行/重放管线测试，其case factory按测试需求缩短，不是正式冻结种子实验；已有失败和无改善记录继续保留。
