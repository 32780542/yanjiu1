# Phase 5C competing 完成案例的有界通行诊断

2026-09-13。**上方车完成了一次换道，下方车没有接续：下方车在目标带占据阻断结束前已降到原5 m/s换道门槛以下；清除后B1恢复的是对自身慢前导的跟随，余下窗口始终未重新达到门槛。** 本例没有原判据形成成功，也不提供有限时间通过结论。

状态：首段分析已 finalized/completed 的 `r5_competing_r5_on`，300个完整0.1 s控制区间、30 s物理记录。初次诊断时新整包仍运行；随后完成封存及原17项标准语义重放，本文案例文件与最终清单和重放来源一致。**原17项及三车扩展6项标准语义重放均已通过，并完成本文诊断来源绑定；失败前缀和形成失败保持原判定。** 末尾附预登记60 s三车等待/优先两完整窗口的独立核验。

## 固定来源和方法

- 新5C：`variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T061451357664Z_cd3da24b/cases/r5_competing_r5_on`。
- 固定5B：`variants/phase5b_conservative_release/results/phase5_r5/runs/20260913T042930121115Z_deb427af/cases/r5_competing_r5_on`。
- 完整case（含所有初始记忆）、initial、模型参数和原数值参数逐域exact相同；5C参数和policy只增加`r5_lane_priority_enabled=True`。
- 离线名称`right`对应初始y=8.25的上方受控车，`left`对应初始y=1.65的下方受控车；两者初始x=250、速度8。`lead_left/lead_right`为对应外侧车道上x=310、速度2的固定脚本前导。本文的名称关联仅以离线保存物理签名逐拍唯一匹配，不进入控制器。
- 使用系统化诊断流程追踪 assessment、gate、plan、物理状态、B1记忆、实际增量和检测结果。未改控制器或场景、未跑车、未派发代理。

原始提取保留在`results/phase5c/liveness_diagnosis_20260913T062150194121Z`；补充near几何和恢复峰值后的完整包为`results/phase5c/liveness_diagnosis_20260913T062435393209Z`，含`summary.json`与1200行`control_rows.csv`。对应`run_logged`日志：`results/operations/20260913T062435251183Z_phase5c_liveness_geometry_diagnosis_844bb1a0`，returncode=0、无stderr、读取前后五项案例文件哈希一致。

## 两版本的实际差别

| 量 | 5B等待基线 | 5C可见车道优先 |
|---|---|---|
| 上方车plan提交/本车完成记账 | 无/无 | 0.5 s / 5.6 s |
| 下方车plan提交/完成记账 | 无/无 | 无/无 |
| 下方车R5阻断 | [0,30) s | [0,18.1) s |
| 下方车物理采样首次低于5 | 3.99 s | 5.58 s |
| 下方车累计低于5 | 26.01 s | 24.42 s |
| 下方车30 s末速 | 0.00930874 m/s | 3.29532589 m/s |
| 上方车30 s末速 | 0.00930874 m/s | 5.00000000 m/s |
| 下方B1稳定参考/首次实际增量 | 无/无 | 19.1 s / 20.3 s |
| 原local / whole formation | false / false | false / false |

低速时间按原保存0.01 s物理样本的左端区间累计；5.58 s是首次保存的低于门槛样本，不声称精确连续穿越时间。5C控制拍首次低于5在5.6 s，之后直到30 s均低于5。两案例本地validation均为completed、recording/driving/comfort=true；5C本案例也已通过标准语义重放，整包其他失败前缀仍保留。

## 为什么第一辆完成后没有马上放行第二辆

上方车0 s进入PREPARE、0.5 s提交plan，5.6 s由自身控制器记账完成1次；它从未发生R5私有抽样。下方车始终没有plan，抽样次数也始终0，故此次下方等待没有私有deadline到期因素。

下方assessment先后为：`yield_visible_upper_lane`在[0,0.8)；`yield_visible_inward_motion`在[0.8,2.0)；`yield_entered`在[2.0,17.1)。部分时刻外层诊断改为`yield_not_certified`，只表示附加让行动作未通过原guard，gate仍阻断；没有把guard拒绝视为放行。

上方完成换道时，其车身处于中间目标带，纵向尚几乎与下方并排。5.6 s两车dx为−0.26931 m，下方速度已经4.98699 m/s。R5保留的entered优先只看当前可见车身，不知道也不使用邻车的完成事件。因此上方完成一次换道并不自动清除下方episode。

原near半径还包含`|相对纵速| × 5 s`。下方越慢，上方虽渐渐向前拉开，仍能在较大的near范围内持续成为已进入目标带的参与者。这是当前定义直接产生的保守阻断，而非冻结后添加的新规则：

| 下方时刻 | 上方相对dx | 原near半径 | assessment |
|---|---:|---:|---|
| 17.0 s | 31.76477 m | 32.24818 m | yield_entered |
| 17.1 s | 32.26385 m | 32.25941 m | no_potential_competition |

17.1 s上方刚退出near集合，下方启动原1 s clear稳定期；18.1 s才清除episode并转IDLE。上方此时仍在本车前向可见范围内，退出的是局部竞争near集合，不是消失出传感器范围。18.1 s下方速度仅0.03236 m/s。

## 清除后为什么仍然没有新plan

`noa/controller.py:248`仍要求本车速度`>=5`才进入新候选循环。记录中下方在5.6 s之后的`candidate_rejections`均为空：原因是未进入候选循环，并非存在一个获得车道优先后又被新candidate guard否决的计划。R5清除并不能绕过该入口。

下方清除后确实恢复了加速，但物理速度最高只有4.51093456 m/s（22.96 s），随后下降至末速3.29532589 m/s。本次低速差距达到约0.489 m/s，不能归为原已知的5 m/s可行上端微小数值下偏；该旧数值问题未被本诊断修复，也不是解释本记录仍未达到5所必需的假设。

B1在18.1 s开始稳定参考候选，19.1 s持有稳定参考。该参考的物理签名唯一对应**同车道速度2 m/s的lead_left**，没有切换成已经换道的right：18.1 s `selection_rule=nearest_front`，20.3 s以后为`hold_visible_forward_reference`。18.1 s上方相对下方速度约4.968 m/s，也超过原B1候选相对速度上限3 m/s。

19.1–20.2 s虽然参考已经稳定，形成增量仍因`neighbor_reachable_occupancy`拒绝；20.3 s第一次实际加上0.0463868 m/s²。之后跟随较慢的同车道参考产生负增量。22.9 s的直接分解是：NOA基础请求+0.29318165、原B1实际增量−0.35032127，合计−0.05713962 m/s²，实际增量通过原guard；速度随后在22.96 s达到峰值。这证明B1恢复后可以参与制动，不能把“有参考、有增量”直接当作换道速度恢复。

29.4 s起形成增量再次被原guard拒绝，29.9 s仍保留稳定参考，但`formation_state=FALLBACK`、实际增量0、NOA基础请求−0.16004437 m/s²；对该慢前导的间距目标误差为−11.10389 m。这里列的是本次实际作用分解，不是移除B1后的反事实结果，更不能据此保证任何单点修改会使第二辆通过。

上方车自身在完成后受原5 s形成冷却等风险条件限制，直到10.7 s进入`no_reference/NOA_ONLY`；整个30 s没有B1候选、稳定参考或实际形成增量。

## 形成与结论边界

新旧原检测器均使用全部4个物理actor，5C的`local_success=false`、`whole_cohort_success=false`，candidate_intervals与intervals均为空；没有持久局部群组。这次可支持的机制事实是“上方车获得优先并完成一次换道、下方后续解除R5并恢复对慢前导的B1参考”，不支持“第二辆已接续”“逐车形成已实现”或“一般有限时间通行”。

此次无新P1/P2实现发现：长期entered阻断、clear稳定期、低速入口和原B1参考行为均是计划要求保留的边界。本文不建议全局赢家、通信、邻车意图或调度补救，也未改变旧守卫、数值阈值或场景。

## 原17项最终封存与标准语义重放绑定

新5C已完成案例五文件读取前后均一致；固定5B对应五文件已逐项匹配其整包evidence manifest。新5C封存后也已确认下表五文件与早期诊断及最终evidence manifest逐项一致：

| 文件 | SHA256 |
|---|---|
| metadata.json | `b89d431dc599b2337ce920cbe521db0043bfc6bccb2ade7ea72ad50722a19d8e` |
| trace.jsonl | `aae06c6b19aa97cb72d566194a32916f51304a48eebfb7a6f8ebb3199b75db52` |
| validation.json | `1c7b4958917acf44d9581c077368827e8e778f7092a72617f3e97eb9eb71ebec` |
| r5_events.json | `61da2f12bc4ea2a2d8ba94f3bf9616d33ac7f409061c5fdb26712879196fca23` |
| detection.json | `550400766745d82f302cf22a2b9444a2df133d32466071718d52739fab423dd6` |

全部父/新来源哈希与脚本哈希已保存在补充提取包summary.json；最终整包标准replay状态不从单案例validation推断。

封存核对记录：`results/phase5c/liveness_seal_20260913T062751569480Z/verification.json`；日志`results/operations/20260913T062751385449Z_phase5c_liveness_seal_verify_9315403e`，returncode=0。最终index及validation也匹配清单，run status=completed，17项已启动/已finalized、14项完整，evidence manifest有339项，SHA256为`3155cca5eaa634ead59353a6327a244ae70730f1fa4ee18f4f6bd9d75c37ff34`。本次仅核对所诊断案例和最终index/validation，未另跑车辆。

标准语义重放：`variants/phase5c_lane_priority/results/phase5_r5/replays/20260913T062619302264Z_135ea687`，status=completed、passed=true，17个唯一case全部passed，errors及unstarted均为空，source_before与source_after完全相同。独立核对其小型封存包、当前来源manifest/code/input/validation绑定，以及上述competing五文件均通过。对应competing重放为300区间、12000车辆子步、max_numeric_error=0，隔离及检测重建通过；local/whole formation仍false。

该replay的evidence manifest SHA256为`9b147af13451f13bcc9406df16e8e816ada7e339f05ed2e25cec6fa3ed796594`，validation SHA256为`3313bfe4f01baf8b86ebb50b25a2441a4f92453de93e7d729833ad994ec30e73`。独立核验只读取现成重放证据，没有再次执行车辆、控制器或模型。

## 60 s三车扩展的独立事实核验

固定来源：`variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T062619294263Z_4126e0fd`。已核原始摘要：`results/phase5c/gradual_summary_20260913T0636`。本追加核对其中`r5c_gradual_three_r5_on`与`r5c_gradual_three_r5_waiting`两个完整600区间窗口；各自600记录均committed。waiting与priority的完整case、物理及自身记忆初态、模型、原数值参数相同，唯一策略差异为lane-priority bool。

独立从保存trace重算每车plan提交/完成、首候选/参考/实际增量、UNKNOWN与blocking次数、平均速度及低于门槛时长，匹配摘要；再用封存原检测器分别重算all5与controlled3的601帧检测，均与摘要完全一致。检测器计算只消费离线保存位置/速度，没有执行控制器或模型。

| 事实 | priority ON | waiting基线 |
|---|---|---|
| upper提交/完成 | 0.5 s / 5.6 s | 无/无 |
| lower、middle_front提交/完成 | 均无 | 均无 |
| lower 60 s末速 | 2.10745725 m/s | 0.02418945 m/s |
| upper 60 s末速 | 4.99999992549 m/s | 0.02418945 m/s |
| lower累计低于5（0.1 s控制左端采样） | 54.4 s | 56.0 s |
| lower/upper累计blocking拍数 | 181 / 0 | 600 / 600 |
| lower/upper累计UNKNOWN拍数 | 0 / 0 | 170 / 170 |
| controlled3原local/whole成功 | false / false | false / false |
| all5原local/whole成功 | false / false | false / false |

两版本middle_front均无R5阻断、无UNKNOWN、无B1参考或实际增量，末速约5 m/s。两套检测均使用原30 s确认期限及确认后10 s保持，没有把晚发生区间改成成功；实际candidate_intervals与intervals均为空。表中控制左端低速口径与前段competing的0.01 s物理左端口径分开，不能互换。

**UNKNOWN的实际触发已经明确。** waiting的lower和upper均在43.0 s首次转UNKNOWN，随后到59.9 s连续170拍；42.9 s的前锚点物理签名唯一对应middle_front。其相对纵距从199.53830223 m增到200.03740854 m，越过原200 m前向可见边界；观测邻车数4→3，当前episode的front anchor从该签名变为None。参与的并排peer仍存在，assessment仍是ambiguous，旧`_same_episode`因锚点缺失返回unknown，记录`episode_association_unknown`。

该170拍内，旧episode签名、deadline、RNG和draw_count均逐拍保持，原gate持续blocking。这是可见锚点丢失后的保守未知关联，不能表述为物理身份关联成功、重新抽样或期限强制放行。它为先前原8案例未出现的UNKNOWN补充了一个真实保存工况；仅属于此预登记waiting基线，不保证其他工况覆盖。priority三受控车均无UNKNOWN。

**upper的稳定参考仍未转成实际形成增量。** priority upper在10.7 s开始稳定候选，11.7 s取得物理上对应middle_front的同车道参考；第一拍目标间距误差0.28477544 m、原始增量+0.02278212 m/s²，但被`neighbor_reachable_occupancy`拒绝。自11.7到59.9 s共483拍均相同guard拒绝，实际形成增量全为0；因此不能写成“上方先形成后下方跟随”。upper严格低于5的34.3 s计数对应最终约7.45e-8 m/s的上端下偏，不能当作lower真实低速等待的同等量级损失。

priority lower在18.1 s出现候选、19.1 s持有自身慢前导lead_lower参考、20.3 s首次实际增量，仍没有后续换道。以上只支持一次上方完成及局部参考恢复；受控三车和全部五actor的原形成判据均失败，没有形成改善或有限通行证明。

本次核验未发现摘要数值或归因的P1/P2问题。原始扩展摘要保留生成时的`semantic_replay_bound=false`，未覆盖旧证据；本报告随后完成标准语义重放的独立封存来源绑定，见下节。

原17项replay绑定及三车独立数值/UNKNOWN核验的最终证据：`results/phase5c/independent_final_liveness_20260913T064110595839Z/verification.json`；`run_logged`目录`results/operations/20260913T064107730378Z_phase5c_final_liveness_unknown_binding_48d90d37`，returncode=0、无stderr、耗时2.938 s。首次不含逐拍UNKNOWN私有状态恒定检查的结果另保留于`results/phase5c/independent_final_liveness_20260913T063937129744Z`，未覆盖旧尝试。

## 三车扩展6项最终语义重放绑定

标准重放包：`variants/phase5c_lane_priority/results/phase5_r5/replays/20260913T063537973705Z_c407c3ee`。已独立读取并核对其封存小包及来源：status=completed、passed=true，6个唯一case全部passed，errors及unstarted为空，source_before与source_after完全相同；当前source的evidence/code/input/validation哈希与重放记录一致。

已诊断的priority和waiting案例各4个来源文件（metadata、trace、detection、validation）同时匹配先前独立摘要核验、原封存manifest及当前文件。两个案例的标准重放均为600区间、30000车辆子步、max_numeric_error=0，隔离及检测重建通过；原local/whole formation仍false。扩展OFF三车case仍标记source_execution_status=failed，未因重放通过改成完整车辆成功。

最终独立绑定证据：`results/phase5c/liveness_final_gradual_replay_20260913T064654086823Z/verification.json`；日志`results/operations/20260913T064653848797Z_phase5c_liveness_final_gradual_replay_4d2c210d`，returncode=0、无stderr、0.25 s。仅读取封存/重放及已诊断案例，没有重跑检测器、控制器、车辆或模型。

| 封存文件 | SHA256 |
|---|---|
| 扩展run evidence_hashes.json | `08e1ab0f619dd404fd048d62c3718838224c55d4fbcbaf14d9939be76ae03f5c` |
| 扩展replay evidence_hashes.json | `3af4afc22c1ecec5392e9813ab04b8e4e5718395106403662750239d487fd67a` |
| 扩展replay validation.json | `e047d8a8f95a2cbf42e8fa6f7991cc6591ec3b01f2fbac9b426ec263339de3f7` |

本报告的标准重放绑定已闭合，诊断结果保持不变：上方一次完成、下方未接续、UNKNOWN仅在指定waiting工况实际出现、稳定参考不等于实际形成增量，原形成判据仍未通过。
