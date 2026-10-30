# 阶段5恢复检查点

2026-09-13。工作目录固定 `D:\yanjiu1\keyan1`。本文件用于传输中断后恢复，不等于阶段5验收。

- 已完成：前置独立审查，固定164项测试、verify、阶段4普通/采样包重放、6车源码几何与环境复核均通过。审查报告 `docs/phase5_prerequisite_review_20260913.md`。
- 固定证据：`results/phase5/prerequisites_20260913_20260912T1617539387172Z/`；64项审计文件再次核对无差异。不要因为Codex断流重跑这一整套。
- 已有实现：`experiments/phase5_detection.py` 与23项独立检测测试。既有设计为 `docs/phase5_implementation_plan.md`。
- 2026-09-13续接核实：`results/phase5/resume_20260912T173201610967Z/prerequisites.json`，原79份源码/配置无变化，普通270与采样157份证据哈希全部匹配；没有重跑前置整套测试。
- 实现进行中：`noa/formation.py`、`simulation/formation_clock.py`、`experiments/phase5.py`、`phase5_cases.py`、`phase5_replay.py`、`phase5_audit.py`及两个新配置已存在，尚待本轮全部回归与独立验收。
- 实验记录单元：三个针对性测试于`results/operations/20260912T173940209624Z_phase5_records_green_769c4540/`通过。此前缺模块的红日志及依赖尚未完成的一次错误保留。随机连续初态3/6/12各两种子、速度扰动/可见性/不恢复事件已冻结为生成代码。
- 控制单元：物理签名连续关联/歧义拒绝已实现，原守卫不变；45项控制回归、16项原records回归及冻结源码重放通过。后续采样审查发现policy周期未同步，已修复为FormationClock拒绝不一致，runner半采样同步两个周期；新增21项控制/clock通过。报告`docs/phase5_controller_unit.md`。
- 已结束开发试运行：`results/operations/20260912T174013616059Z_phase5_offline_paired_smoke_9a0d286a/`，对应`results/phase5/runs/20260912T174013892192Z_6037864a/`。94.547s退出0，3车5101的on形成、off未形成；两组记录/驾驶通过。此包实现期间源码变化，且纯离线，不用于最终验收。
- 记录与事件：`results/operations/20260912T175320339672Z_phase5_events_interrupt_af90708d/`，8项通过；包含严格同一参考出域释放（无返回不得成功）、回放包启动/完成索引与KeyboardInterrupt失败前缀保留。
- 理论：6项测试与固定分析重放通过，`results/phase5/theory_20260912T174605182163Z_fdfda018/`；固定参考理想分支稳定，不代表实际混合系统串行稳定。`docs/phase5_theory.md`。
- 参数登记：281行，新增17项；原264行快照与新的登记表保存在`results/phase5/registry_20260912T174511425286Z/`。物理/安全界与原NOA配置未变。
- 独立重放审查发现事件/驾驶汇总未复算、冻结case漏执行、元数据可自行放宽重放容差；正在补配置绑定/覆盖/派生复算与partial整包验收。独立探针失败证据`results/phase5/replay_review_20260912T174910Z/`保留。
- 修复后冻结核验：重放14项测试通过；独立重新封存的4类篡改探针全部拒绝。完整回归`results/operations/20260912T180015894613Z_phase5_full_regression_a3452480/`，213项、104.236s、退出0。基础核验`results/operations/20260912T180057168739Z_phase5_foundation_verify_0c7aab16/`通过，94份代码/配置核验期间未变化。
- 正在运行真实SUMO：固定本次源目录`results/phase5/runs/20260912T180218593655Z_1e4080c3/`，命令日志`results/operations/20260912T180218304791Z_phase5_live_frozen_suite_0337da9d/`；外部7200s上限，实际21变体（10案例on/off+1半采样）。断流先查result.json、case_index.json与进程，不从latest推断已经失败或重跑。
- 下一入口：等待上述运行完成，读取逐案例真实结果；固定源整包重放、0.005积分细化检查；执行`tmp/phase5_summarize.py <明确运行目录>`生成自身封存的实际Δv配对分析和阈值敏感性汇总，然后验收。阶段5尚未验收，阶段6未放行。实验期间不得改源码/配置/测试与已冻结输入文档。
- 约束：无隐含通信、车型真值、ID优先权或全局调度；安全门槛与原失败证据保留。全部代码完成后另跑受影响回归，不能用前置报告替代最终回归。

执行时每次只读当前单元必要文件，工具输出默认限制在约1500 tokens，完整输出写入独立日志。单条长命令使用 `scripts/run_logged.py`，显式传入超时；先检查上次 `started.json` / `result.json` 与进程状态，再决定是否重试。没有 `result.json` 不能自动解释为失败或仍在运行；不要自动重复有副作用的命令。

传输诊断材料：`results/codex_transport/20260913_005335/`。网络问题与研究算法失败分别记录，不能把连接恢复当作研究验收。

- 用户追加研究方向（2026-09-13 02:31前后）：明确比较A现有局部cost与B本车车道/八邻域ifelse，可有限深入探索。A固定完整run继续，不修改原生产。B在`variants/phase5_rules_front_first/`隔离副本实现，复制来源为上述A固定run的94份code_snapshot+5份input_snapshot；工具`tmp/phase5_clone_workspace.py`，日志`results/operations/20260912T183102240558Z_phase5_front_clone_dd8bbe03/`。两个B开发分支预声明为正前优先、前角优先；安全界、数值增益、5m/s目标保持，侧后仅占位/安全，严格可见前向主参考。
- 旧6种子统一作为开发集；计划预先冻结独立验证种子3车6111/6112、6车6211/6212、12车6311/6312，A与由开发结果选择的B及OFF使用同初态配对。预登记写`docs/phase5_comparison_preregistration.md`；新任务扩展尚未完成，不能在仅原A跑完时结束。
- B1独立副本已冻结：`variants/phase5_rules_front_first/`，96源码；A原94source+5input仍匹配。B新增枚举、formation_rules.py、test_phase5_ifelse.py并修改formation.py，原PD/物理/安全/runner/detector/replay不变。68项回归通过`variants/phase5_rules_front_first/results/operations/20260912T184242292521Z_b1_final_regression_3b8710ca/`，暂存11也通过。原型中失败/RED均保留。说明`docs/phase5_ifelse_design.md`及副本`docs/phase5_rules_controller_unit.md`明确侧带候选收窄、占位否决、保持优先、switch_cost不再使用，不能称纯排序。
- B2已从B1固定副本克隆：`variants/phase5_rules_corner_first/`，仅config enum+registry值改corner_first（`tmp/phase5_set_corner_rule.py`），68项回归通过`variants/phase5_rules_corner_first/results/operations/20260912T184657916683Z_phase5_corner_regression_1555c53e/`。两副本module origins均通过。尚未启动B正式suite，等待独立审查。
- 比较预登记已封存：`docs/phase5_comparison_preregistration.md`、`tmp/phase5_comparison_design/case_matrix.json`、selection_rules.json，manifest `preregistration_hashes.json` SHA256 `424e8e27f0f4d4f4f8db1a6db16cdddaa314e2abf51d7951d9e3effe6fc5fe96`。B开发各21变体；选定B后heldout A/B各13变体（6随机on/off+半采样），重复OFF核对后18主比較单元。6h仅资源预计不是停止/验收豁免，每整包仍7200s。
- `variants/phase5_cost_holdout/`只准备了固定6新seeds、registry和plan说明，origins已通过，尚未运行车辆。将由生成器冻结明确初态hash再逐字段校验；不能先看heldout结果再挑B。
- 结构负例：45s三车三道完全并排A/OFF稳定并排未形成，初版包`results/phase5/symmetry_runs/20260912T184041752635Z_0d68ab1f/`；网络/覆盖绑定补齐的新包`results/phase5/symmetry_runs/20260912T184156146471Z_0bc4b20e/`均记录/结构检查通过，但独立review指出离线摘要未含末帧、snapshot绑定与顶层推导需再加强，尚不作为最终通过验收。工具`tmp/phase5_symmetry_fixture.py`会修正并新目录复跑，旧版本快照保留。
- 2026-09-13约03:05：B1/B2已开始固定完整开发suite，不得改各自生产/测试/configs/5input。B1固定run `variants/phase5_rules_front_first/results/phase5/runs/20260912T185217115718Z_0bbe422c/`，wrapper `.../results/operations/20260912T185216776734Z_phase5_front_live_suite_99cb3eee/`，exec session45608；B2 `variants/phase5_rules_corner_first/results/phase5/runs/20260912T185217113215Z_3a3b35df/`，wrapper`.../results/operations/20260912T185216779579Z_phase5_corner_live_suite_d52619bd/`，session83407。均7200s上限；B2 plan已在启动前修正副本身份为corner_first，数值/其他代码不变。A原run仍session80449，20/21完成、正跑半采样。
- A已知科学事实：6个随机on整体形成1/6（仅3车5101）；12车5301局部成功且最大瞬时组3/12，两个12车均无全队。disturbance事先形成、21.1s失效、80s内未恢复并保持；visibility严格出域释放重入重选通过；nonrecovery事先形成、21.1s失效且未恢复。科学条件暂已确定前二未过、后二通过，仍等采样/源封存/整包重放后正式验收。
- B独立审查35项通过、38共同核心文件相同、无P1/P2；新增实施澄清`docs/phase5_comparison_v2_implementation_clarification.md`及`tmp/phase5_comparison_design/implementation_clarification_v2_hashes.json`，原预登记未改。
- heldout完整初态`tmp/phase5_comparison_design/heldout_frozen_cases.json`已冻结，SHA256 `f0055edf2b68485c435b6c25ca2cc2efe2da0f393370d41faf2d7952578d7133`。对应freeze audit/hash/verification文件同目录，12项case/initial哈希通过且拒绝覆盖，未启动车辆。
- 完整整包重放优先用已冻结外层绑定入口`tmp/phase5_comparison_design/phase5_bind_v1.py`（SHA256 `622991c1e5a4aa66f1270120ffc5eceb87f7ebed590cc4a8ad4be1bab8f3cae2`）：外层`run_logged.py --timeout 7200`，命令`PY -I -B -S <固定脚本> --workspace D:/yanjiu1/keyan1 bind-replay --variant <正确副本或A根> --run-dir <明确sealedrun> --timeout-s 6600`。它运行原标准phase5-replay并绑定运行前后来源/hash/currentcode与replay报告，产生root results/phase5/comparison_<time>_binding目录。比较器`phase5_compare.py`尚在开发，不能拿其变化中的文件做长run；正式调用前另复制封存版本。
- 对称fixture三缺口已修复的新包`results/phase5/symmetry_runs/20260912T185027830000Z_f1216bee/`通过，正重放log`results/operations/20260912T185302049000Z_phase5_symmetry_fixed_replay_ecd4d2ae/`27.843s退出0；代码`tmp/phase5_symmetry_fixture.py`当前固定，含4500物理子步/末帧/实际匀速核对、snapshot绑定和case物理通过门槛。独立审查正在重做3负探针，等闭环后再跑B1/B2相同结构fixture。
- A正式完整包已完成：wrapper`20260912T180218304791Z_phase5_live_frozen_suite_0337da9d`退出0，3788.953s；21/21、engineering/driving/recording/complete_suite均true、scientific_passed=false（random/recovery失败）。源码期间零变化，nonvacuous_action_changes=3572。半控制maxposition0.012703160673481761m；半积分最大1.4856027519272175e-10m，均通过。A原session80449已结束。
- A整包绑定重放当前运行：session58002；wrapper`results/operations/20260912T191153035059Z_phase5_cost_bundle_replay_binding_d02e5b0b/`；绑定包`results/phase5/comparison_20260912T191153232875Z_binding_6aec92e0/`。使用冻结bind_v1（外7200/内6600秒）。binding.json初始passed=false且无最终status不是失败结论，先查wrapper result/进程。标准replay仍在执行，A生产继续保持可重放。
- 为并行整理数据，A只读汇总在完整封存后、整包重放同时进行（未把重放待完成说成已通过）：`results/phase5/analysis_20260912T191502457194Z/`，21变体、source_hash_mismatches=[]，wrapper`results/operations/20260912T191459253661Z_phase5_cost_frozen_analysis_59870083/`36.984s退出0。最终引用仍须绑定重放通过。实际paired Δv peak rear=.170526、middle=.340941、event=2.996559m/s，80s扰动案例21.1s失效未恢复保持。
- 三缺口独立symmetry复审已闭环：`docs/phase5_symmetry_review.md`及`tmp/phase5_symmetry_review_fixed_20260913/review_hashes.json`；正包通过，4坏包拒绝，真实source未改。B1 45s结构包`variants/phase5_rules_front_first/results/phase5/symmetry_runs/20260912T190618408568Z_c517849e/`；B2`variants/phase5_rules_corner_first/results/phase5/symmetry_runs/20260912T190618416428Z_c7384b6b/`均通过并已重放，wrapper分别`.../results/operations/20260912T191239949750Z_phase5_front_symmetry_replay_a159440f/`15.125s及`...191239950750Z_phase5_corner_symmetry_replay_df5b4c34/`14.906s。A/B/OFF结构性未形成完整保留，不计随机分母。
- 守卫诊断`docs/phase5_guard_diagnostics.md`，证据`results/phase5/guard_analysis_20260912T191212138298Z_de3c3f03/`（另新目录快照重放summary逐字节相同）。实际A5201 880/2200拒绝且非零1320；A5202 1320/2200且880；B1/B2 5201各440/1760且1320。全部记录neighbor_reachable_occupancy，无法辨拒绝邻车/包络重叠vs递归未排除，不能称“过保守”或效果改善。离线唯一物理匹配A5202有2次换参考，其余三case0，不把signature坐标逐帧变化当换车。
- 选择器已另冻结`tmp/phase5_comparison_design/phase5_select_v1.py` SHA`f2da6e517f3e6be61a0b0c08ac106c931360fa52b69896343282d37c09a7af1c`（绑定脚本v1不变）。8单元+完整pipeline通过，包含fresh重新生成A cases，source/config/initial/脚本/OFF一致，B2计划仅固定身份段落canonicalize，真实物理失败前缀失格/null而不要求跑到成功、损坏或缺case仍拒绝。正做独立审查，正式selection需等三个完成run的binding。heldout汇总模式另在phase5_compare.py开发，不改select_v1。
- 2026-09-13约03:37恢复：A整包绑定重放session58002仍运行；B1/B2固定开发包session45608/83407仍运行，均已完成第二个12车OFF，正在第二个12车on。没有重启任务，仍未运行任何heldout车辆。A结果说明`docs/phase5_cost_baseline_results.md`已保存，明确12车OFF本身也有局部组，不能把局部二值成功独自归因于A。
- 冻结select_v1独立审查已通过：`docs/phase5_selector_review.md`，17.547s独立日志`results/operations/20260912T191825198636Z_phase5_selector_independent_review_e1b53a0f/`及真实A初态重建`...191942665797Z_phase5_selector_real_A_initials_review_b1f07be1/`。仍需等待三个实际绑定包通过才能执行正式选择。
- 可变heldout分析实现的独立探针发现两项P2（不影响冻结bind_v1/select_v1和车辆控制）：重签selection可将run指向未绑定目录，嵌入矩阵可缩为一个随机case。旧源码和坏包保存在`tmp/phase5_heldout_review_20260913/`，独立日志`results/operations/20260912T193225865039Z_phase5_heldout_independent_integrity_review_ce7b8ff3/`。作者已修复并增加回归，正在独立复验；另要求失败前缀窗口量不得与完整45s对照求改善均值。正式heldout分析要等复验后另冻`phase5_heldout_v1.py`。不得将探针工具退出0误称旧实现通过。
- heldout最终分析器已冻结`tmp/phase5_comparison_design/phase5_heldout_v1.py`，SHA256 `f80314e9b0334ead62b2511bfe017c74696b95263a7e6724fbed883a44c4e4d0`。15项及独立最终复验通过，旧两P2关闭；完整/20s失败前缀/未开始seed均检验，失败前缀raw事实保留但完整45s窗口差值/均值为null并报告5/6。独立日志`results/operations/20260912T194132782130Z_phase5_heldout_final_independent_review_ed6b2a56/`7.078s，报告`docs/phase5_heldout_analysis_review.md`SHA `96797d31fa8ac7adca02bb9dfe03f79de7d98a2cff1abdbb4fb5276fbd59d30e`。bind/select旧SHA未变。
- heldout入口预检完成：`docs/phase5_heldout_execution_entry.md`、`tmp/phase5_comparison_design/heldout_entry_check_20260912T1946Z.json`。六次`--case`、不关live或sampling；每副本13变体，顶层complete_suite=false是只跑随机子集的预期，不是完整stage5放行。Aholdout94源码/5input、完整六初态与模块来源再次匹配，未启动车辆。实际必须正式选B之后才创建Bholdout并启动两边。
- 约2026-09-13 03:51：两B随机12变体均完成，全队各1/6、局部各3/6，与A的二值数量相同，尚未正式whole+C选择；后续事件进行中。B1由root持有原session45608；B2原session83407不关闭，其完整结束检查和唯一bind-replay已交replay_audit负责（不能root重复启动）；A绑定session58002仍由root检查。
- 主验收草稿`docs/phase5_completion_acceptance.md`已写，当前明确执行中而非最终验收；独立需求矩阵`docs/phase5_requirement_traceability.md`已核对实际源码。事实纠正：39m是CTH期望净距不是硬安全距；disturbance总长80s、扰动从20s开始，所以截至80s只有扰动后60s；B同道重叠也会让旧参考失去资格；A配对扰动OFF的rear/middle速度差均为0，不能以on内部传播比小于1称优于OFF。固定输入/预登记文本不覆盖。motion外层速度/停车/原始局部覆盖与逐车约束摘要正在tmp独立补齐，不修改冻结策略或分析v1。
- B1/B2完整开发已结束：B1 wrapper4022.422s退出0，B2 4012.0s退出0，均21/21、engineering/driving/recording=true、source_changed_during_run=[]、移除可见邻车动作改变3529。两包scientific四条件同A：全随机全队false、恢复false、参考出入true、不恢复反例true。B1/B2各6随机whole1/6、local3/6，仍须绑定后才能按whole+C选择。
- B1唯一正式绑定由root运行：session43738；root wrapper `results/operations/20260912T200031499713Z_phase5_front_bundle_replay_binding_d6d0f712/`；binding `results/phase5/comparison_20260912T200031670602Z_binding_15a2b3aa/`。B2唯一正式绑定由replay_audit接管：session85806；root wrapper`results/operations/20260912T200259785998Z_phase5_corner_bundle_replay_binding_0e666bd3/`；binding`results/phase5/comparison_20260912T200259973699Z_binding_4446e653/`。均固定bind_v1/inner6600/outer7200；A仍session58002。B1旧45608、B2旧83407已正常退出并关闭，不得重跑。
- B封存只读摘要已生成（最终使用仍待绑定）：B1 `results/phase5/analysis_20260912T200127726864Z/`，wrapper`...200125020724Z_phase5_front_frozen_analysis_e15ddee5/`31.36s；B2 `analysis_20260912T200212436867Z/`，wrapper`...200209674030Z_phase5_corner_frozen_analysis_6bc490bd/`31.812s。各21变体且来源hash无差异。summary临时sessions3391/59723均已完成关闭。
- motion独立单元闭环：脚本`tmp/phase5_motion_summary.py` SHA`1cbdab1433ec01f7547f58dfa873eab0355588249ad0df23a1f6d10576d8b6ca`，13项及独立审查通过；文档`docs/phase5_motion_analysis_review.md` SHA`b10689192cbab262dc013329eb355dfaf0206de4330a8f9ef102afdc885f3b44`。A主产物`results/phase5/motion_20260912T200305018866Z_b3ea51c3/`，跨cwd快照重放`motion_20260912T200425963695Z_408aae6d/`；summary均SHA`485340e0578293b5f831c062b90f27e1e93dc1eeacb82b25794e7bbc9b6b3b74`，CSV/脚本也相同。21变体111物理车条目，其中103被控标准metrics全部匹配，8外生标准metrics明确未记录；6随机on/off及半采样停车时长均0。第一次把外生车也要求标准metrics的分析错误保留，不是车辆失败。B两包motion摘要与快照重放由formation_control继续完成。
- **原规格R5明确缺实现，不能仅留待后续：** §9.5要求竞争同一空隙局部让行、近同时无法判定时保守减速+本地随机退避，§13阶段5要求R1–R5；保持车道的编队范围并不禁止基础NOA机动，因此该前提并非代码上不可达。root已告知用户在本次授权内补齐独立新版本。formation_control在motion闭环后先写`docs/phase5_r5_completion_plan.md`供root审查，再开发（此条写入时尚未批准具体实现；后续批准见下面新记录）；theory并行审查私有RNG/到期/prepare期间不可见横移/同时到期边界。A/B/v1/已冻结heldout选择不改；R5补全不是B3，不纳入已冻结优选，旧比较不能冒充补全新版的heldout验证。需要新的独立副本、初始私有记忆封存和针对性真实案例/重放。现有verify_candidate不支持plan=None，应按formation guard同车道零横移Bezier构造hold候选，原时域/边界不变；新减速守卫拒绝时保留未获证明的现有fallback及真实失败，不偷放行机动。下一步不能在仅A/B比较结束后遗漏R5工作。

## 2026-09-12 21:15 UTC继续检查点

- A绑定已完成：`comparison_20260912T191153232875Z_binding_6aec92e0` passed，原session58002关闭；正式verify `operations/20260912T202200826280Z_phase5_cost_binding_verify_f6d0bff9`。B1唯一绑定也完成：原session43738关闭，wrapper `operations/20260912T200031499713Z_phase5_front_bundle_replay_binding_d6d0f712` elapsed3801.578s退出0，binding `comparison_20260912T200031670602Z_binding_15a2b3aa`；正式verify `operations/20260912T210835518758Z_phase5_front_binding_final_verify_55e9c754`通过。B2原session85806正常关闭，binding `comparison_20260912T200259973699Z_binding_4446e653`，wrapper elapsed3764.813s退出0，standard replay `variants/phase5_rules_corner_first/results/phase5/replays/20260912T200303509017Z_e6e6d928`21/21通过、max_numeric_error=0，sources/inputs前后相同；agent最终verify `operations/20260912T210738849451Z_phase5_corner_binding_final_verification_b94e5756`通过。旧整包不要重跑。
- **正式B选择完成，不再改选：** frozen `phase5_select_v1.py`运行 `operations/20260912T210839105716Z_phase5_formal_development_selection_a0b12cb9`23.516s退出0；封存 `results/phase5/comparison_20260912T210839292741Z_selection_652993c7` passed。B1_same_front与B2_front_corner均安全/舒适/数值eligible、whole_count=1；mean_C分别0.19854938271604936、0.19407407407407404，所以按原规则选 **B1_same_front**。不是全队普遍成功，也不是科学验收通过。
- B1保留副本 `variants/phase5_rules_front_first_holdout`已从旧B1复制、只改固定6seed/rationale/registry/plan追加；clone日志211004275780Z...28595a79、prepare211005590323Z...02893578。模块来源无串用；fresh生成完整6case与封存初态相同；新外层入口审计 `results/phase5/comparison_20260912T211214770462Z_selected_holdout_entry_183043ff` passed，已调用frozen heldout helper核对唯一source seed文件变化与允许input追加，零车辆结果读取。
- **保留集真实运行中，由root负责：** 2026-09-12 21:12:54 UTC同时启动A/B1各13登记变体（6case off/on+首case半控制），所有命令repeat `--case`，没有事件补跑。A session **2100**，run `variants/phase5_cost_holdout/results/phase5/runs/20260912T211254802638Z_b9c31d10`，wrapper `.../results/operations/20260912T211254497816Z_phase5_cost_heldout_live_da6cba6b`；B1 session **96280**，run `variants/phase5_rules_front_first_holdout/results/phase5/runs/20260912T211254789627Z_3d1257fa`，wrapper `.../results/operations/20260912T211254497816Z_phase5_selected_front_heldout_live_1ab0a839`。两外层timeout7200；这两个source完全冻结。完成后各bind_v1+verify，再用frozen heldout_v1进行6seed/18主单位配对分析，不能把subset的complete_suite=false解读为崩溃。
- R5设计已获root和theory正式批准。最终冻结计划 `docs/phase5_r5_completion_plan.md` SHA db9e5e09533adbeb837967a41188f32a2d6294867d6d914386085ed3b973b5fc；独立设计通过 `docs/phase5_r5_plan_review.md` SHA ccfb9e08f48128c2a6aa94b0c1d72e966dc9ad19dc44d6052accee8c5593eb7d。共同底座 `variants/phase5_r5_common_development`从A94+5输入复制（root clone日志202703807546Z...7a72287b）；实现仅common。正式新版本待整合到从选定B1复制的 `variants/phase5_r5_completed`，不能整文件用common formation替掉B1候选函数；作者只在formation风险行加R5 episode抑制，后续应最小补丁。旧A/B/v1/heldout完全不改，新R5不是B3。
- R5控制作者负责noa/contracts/controller/r5/formation、config/schema测试、common registry新增7行；控制21tests+受影响67tests通过，common日志211026194408Z_phase5_r5_affected_controller_clock_a935ee00（20.547s）。独立theory实现审查待进行，尚无正式新版车辆。记录代理负责simulation/r5_clock、experiments/phase5_r5(_audit/_replay)、run.py、旧phase5.run_case显式schema/private kwargs及rebuild_clock最小分派；8条记录原语GREEN common日志211114772781Z...9b1124f9，整包/CLI完整性仍在开发。
- root负责cases：`experiments/phase5_r5_cases.py`及tests仅common。完整固定8例/时长/速度脚本说明 `docs/phase5_r5_case_matrix.md`，17变体R5 off/on（formation始终true）+首case半控制，私有初态同case两侧相同。6普通例共9次封存时系统uint64熵，duplicates允许；same_state=1/1及quantized=1/2明确对抗。独立算术：两delay1.3498423627584213/1.3867846012971192，初时同触发落1.5s行为格；v8/v5 lead净gap56/31分别≤原动机77.4/42，只是必要动机条件。已检查28初始物理状态均道路内无重叠，未实跑筛结果。
- 初态loader缺字段默认补全漏洞已用root及theory反例确认并修复，完整JSON先直接比expected再codec；provenance版本True误当1也有RED并改严格int。首个测试括号SyntaxError、后续缺模块RED、5项缺字段RED、version类型RED及旧坏文件全部保留，不冒充物理失败。最终7tests GREEN common日志211304702553Z_phase5_r5_cases_final_green_63858431，cases当前SHA5c9bb2aa52a3ce8e5f135c33358f5a9512c7cf674f802920ea9172ad679cb92b；theory正在最终负探针审查。正式case JSON尚未封存/未运行，完成控制与记录审查并整合最终B1新版后再一次生成封存。

## 2026-09-12 22:23 UTC：R5源码整合、独立审查闭环，正式机制实验待回归完成

- A/B1 heldout真实运行均完成，13/13记录完整、工程/驾驶/采样通过、源码无变化；subset complete_suite=false不等于运行失败。A run `variants/phase5_cost_holdout/results/phase5/runs/20260912T211254802638Z_b9c31d10`，B1 run `variants/phase5_rules_front_first_holdout/results/phase5/runs/20260912T211254789627Z_3d1257fa`。A绑定replay由root负责session19452，wrapper `results/operations/20260912T221225252280Z_phase5_cost_heldout_replay_binding_934e88b7`；B1由replay_audit负责session80225，wrapper `results/operations/20260912T221045339197Z_phase5_selected_front_heldout_replay_binding_5b81e422`，binding `results/phase5/comparison_20260912T221045541952Z_binding_26b7acbc`。不得重复启动。两绑定通过后再运行已冻结heldout_v1摘要；选择B1不再更换。
- 新R5完整106源码已整合到 `variants/phase5_r5_completed`，17文件差异，B1参考规则保留，仅插入R5 episode风险抑制。integration provenance保存源输入/参数/复制设计/源码哈希；日志 `results/operations/20260912T220757224119Z_phase5_r5_integrate_selected_b1_19002d1b` passed，origins `...220906359003Z_phase5_r5_integrated_module_origins_e1028157` passed。此副本也完全冻结，不改source/config/tests/固定输入；ROOT仍是冻结A，不能把ROOT/run.py当作新版R5入口。
- 控制独审 `docs/phase5_r5_controller_review.md` SHA40df5eefa52f6df20fbdd4e808b704ff2ca2500c90a246ad7443a1e7382985bf；记录独审 `docs/phase5_r5_records_review.md` SHA56426035387cbf868b3b08791c314b4e6191f5ede86ce25e7978394098303aea；均无剩余P1/P2。控制25新+46相关、记录19专项、案例7项及独立10坏文件均通过；记录另有正常17短case、失败prefix、异cwd源码快照CLI和微小私有定时器/版本/摘要欺骗负例通过。短fixture不算正式机制科学结果。
- root新副本267项回归首跑 `results/operations/20260912T220856173294Z_phase5_r5_integrated_regression_76acecba`，174.515s，failures=0/errors=4，错误来自3旧测试读取未复制的历史验收文件（阶段4测试两subtests报错）；source_unchanged=true。原失败保留。依据实际reader闭包复制7个ROOT历史原件并比对哈希：phase0 source_hash_check、phase1 foundation、phase2/3固定validation、phase2/3 acceptance、phase4 plan；脚本 `tmp/phase5_restore_legacy_test_inputs.py`，日志 `...222135101522Z_phase5_r5_restore_legacy_test_inputs_92cce1fe`。这些只是旧失败记录回归的历史fixture输入，不重认证前置阶段。完整267回归新尝试session95323正在运行；5个test_artifacts历史阶段1检验仍使用已有固定通过证据，未伪装进267。
- 正式R5初态尚未抽取/未跑车辆。入口 `tmp/phase5_freeze_r5_casefile.py` 需 -I -B -S；已核对106source+integration+设计/registry/parent输入，拒绝已存在initials或正式runs；一次9系统私有uint64+4固定对抗状态，不筛选不重抽。输出固定final/results/phase5_r5/initials/frozen_cases.json，17完整变体。待回归和冻结入口审查通过后运行此脚本，再在finalcwd通过run_logged启动 `run.py phase5-r5 --case-file <明确初态JSON>`，默认LIVE+sampling；正式输出 `results/phase5_r5/runs`，后续专用 `phase5-r5-replay`（不能旧v1绑定器）。8固定机制case及20/30/40s窗口不改。
- R5外层摘要 `tmp/phase5_r5_summary.py` SHA09efc4ddafc8573dc7b0c053e164a0891b1d9c3494da6701a8c6958f7f097658，17测试通过，异cwd artifact重放字节一致；独立 `docs/phase5_r5_summary_review.md` SHAa3b186b5fe8d57475d99a905ea23aa0869ad3537eb78a315450fb61e8dd536b2，无P1/P2。说明 `docs/phase5_r5_summary_unit.md` SHA27e4c8af7edf66cf312f1753a78612fe7dd7cc9d5bbacfc9433f68e1a16948fa。只汇总.01实际运动与请求/提交时序，未算.005 jerk/raw/C，不代替标准语义重放。formation_control可在正式包及标准replay封存后处理摘要。
- 收尾仍必须完成：两个heldout绑定与冻结六seed配对摘要；R5正式17机制实验、必要采样、失败保留与标准重放；更新phase5_completion_acceptance、requirement_traceability、README和明确下一入口。旧A/B全队形成1/6、扰动恢复未过已确定；新R5机制case不是第三支B、旧heldout不能替新版本效果验证。实验失败可交付，但不能漏做已授权实现/测试/日志，也不能宣称阶段6入口已开。

## 2026-09-12 22:34 UTC：267回归通过，正式R5运行中并已保留科学失败

- 整合回归补历史原件后的新日志 `results/operations/20260912T222146217240Z_phase5_r5_integrated_regression_with_historical_inputs_46f566ec` exit0，195.484s（测试194.919s），267tests、0failure/0error/0skip，106source完全不变；session95323已结束。
- 冻结入口发现删provenance映射可漏掉必需输入的真实零熵RED，保留 `tmp/phase5_r5_freeze_review_20260913/negative_v1`。最终入口硬绑定integration SHA e5698997b4f81e241d389b380f2e2109414758bad8c8cd56c6be52fcb3286dd6，导入副本前独立枚举106source与全部固定inputs，再导入交叉复核。脚本 `tmp/phase5_freeze_r5_casefile.py` SHA ab899e3c9dcc58b1d0a5b5f94e612d6d5c951af9368b9c328e201393ea8c335d。10隔离负例全部导入前拒绝、真实熵0，独审无P1/P2，GREEN日志222553226795Z...efffc550。
- **正式初态一次冻结完成**：日志 `results/operations/20260912T222641906768Z_phase5_r5_formal_initial_freeze_03012bd7`，输出 `variants/phase5_r5_completed/results/phase5_r5/initials/frozen_cases.json` SHA46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20；8固定场景/28物理actor/13自身记忆/17变体，9普通系统熵+4固定对抗。禁止重抽或覆盖。
- **root负责正式R5 LIVE+sampling，session37484 ACTIVE**：run `variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8`；wrapper `.../results/operations/20260912T222654796674Z_phase5_r5_formal_mechanism_suite_595af2b3`，timeout7200。已出现competing off/on SUMO collision-report失败，均recording true，on保留47/300interval、draw2/commit2、newplan2、block37；on已存物理前缀geometry collision_substeps=0，SUMO报告与模型扫掠必须分开呈现，不宣称已证矩形碰撞/误报。front_priority off/on完整20s，off驾驶/舒适/跟踪失败，on驾驶通过；这只是局部机制差异，不外推形成或普遍安全。其余固定案例继续，不因失败调参或早停。
- R5完成后在同finalcwd以run_logged新目录运行专用 `run.py phase5-r5-replay --run-dir <上述明确run>`，必须保存失败前缀与完整/未完成列表。不要调用旧v1绑定。formation_control准备在标准replay完成后运行已审R5 summary及异cwd字节重放。
- A heldout绑定root session19452仍运行，binding目录已明确 `results/phase5/comparison_20260912T221225440029Z_binding_a5fd1653`。B1 binding session80225由replay_audit持有。两者待结束再verify-binding+冻结heldout-summary。
- formation_control正在执行两个已封存heldout的固定motion脚本摘要及快照重放，输出新 `docs/phase5_heldout_motion_summary.md`，不改源码/选择器、不作未绑定最终效果结论。theory正在更新需求矩阵并保留旧历史截面；主报告/root README初步更新完成，正式数据尚待填入。新 `docs/phase5_next_entry.md`给出正确新版本与专用重放命令，阶段6仍关闭。

## 2026-09-12 22:54 UTC：R5正式证据闭合；只剩两个heldout绑定与最终配对收尾

- R5正式LIVE session37484已结束，wrapper222654796674Z_phase5_r5_formal_mechanism_suite_595af2b3 exit0/429.625s。17attempt/11完整/6SUMO碰撞报告失败prefix/0未启动，recording/private accounting/nonvacuity121/no-competition完整actions相同皆通过，engineering/driving=false、scientific=null、source_changed=[]。包完整封存不等于每个case完整执行。
- R5专用标准replay session46427已结束，wrapper223427979958Z_phase5_r5_formal_semantic_replay_3e602177 exit0/303.781s，报告 `variants/phase5_r5_completed/results/phase5_r5/replays/20260912T223428312609Z_75c18330/validation.json` SHA5c1b748854c825b3bca8b268fb920148fdcd37a6cf7d6a87f111df6ae650a684，17 cases passed、errors[]、unstarted[]、partial_source_package=false，原工程/驾驶失败和scientific=null保留，source before/after一致。
- R5正式描述性报告 `docs/phase5_r5_formal_mechanism_summary.md` SHA8c6d3a27e23e8d199f52aadcc424a3e87fc61e5dba45a859f6f3287caeba95e5。主摘要 `results/phase5/r5_summary_formal_20260912T2235`、异cwd重放 `r5_summary_formal_replay_20260912T2237`，summary SHA34c08f617944d91b02b29e5c58189372f335a456ac8123c2282dd824b7b20ab6。独立.005附录 `r5_refinement_formal_20260912T2237`/`r5_refinement_formal_replay_20260912T2238`，summary SHAdd01c8653acbf88738179edae325e45dfc4b6e6775e471c3cef45365b7ee239b。所有输出文件集合/哈希/异cwd字节一致 `results/phase5/r5_formal_rows_20260912T2241/verification.json`，17case表/27受控actor表同目录。薄来源绑定 `results/phase5/r5_formal_binding_20260912T2250/binding.json` SHA04898ba7242abf30c7645039f8e8578c0a89b934b08b7418c9015a5a81070f0e，wrapper224751145379Z...4758cf83 exit0 .204s，未重跑模型。
- 六SUMO失败为competing/same_private_state/quantized_private_states的off/on；所有17模型扫掠collision_substeps=0，原因差异未定位，禁止称已证矩形相交或SUMO误报。front_priority off满20s但舒适/跟踪失败，左右停车16.55/16.32s，on驾驶通过且right完成1次/left让行。speedfloor on两个draw，低于5门槛ELIGIBLE286/285决策，newplan0。reentry on只1draw且1完成，clear后无第二draw，预声明再入目标未覆盖；UNKNOWN实际物理占用0，单位覆盖不能替代实际证据。首次无竞争half控制pos .006795317257802753m/heading .0014094107195192496rad通过，.005 jerk ego2.0000000000000444/lead0通过，只覆盖该case而非触发退避的时间步鲁棒性。
- heldout motion两包各13完整/87actor，87/87标准字段一致，停车均0，主/foreigncwd summary/CSV/script字节一致。报告 `docs/phase5_heldout_motion_summary.md` SHA644bbafd41303eb230360e0793a01820fa32c73817f1862c55f9f5e074bae6c0。A主 `motion_20260912T222756595440Z_0a9d4e9c`，重放 `motion_20260912T222907946622Z_b37d9c42`，summary SHA6517c475a6eddfd463cacf9158886b33a3be7d3e9de58035b4229e9ab4945085；B1主 `motion_20260912T222756612512Z_431a0b01`，重放 `motion_20260912T222907944622Z_31c971ee`，summary SHAbf4993a46bc0274c549e2a4304ff7f3e21665ec3703c4a06ade000c645403988。验证目录motion_verification_heldout_A_20260912T2231、...B1_20260912T2231；26行原值 `heldout_motion_rows_20260912T2233`。绑定仍待root与replay_audit各自已有session自然完成。
- theory已更新 `docs/phase5_requirement_traceability.md`并保存历史原稿 `results/phase5/traceability_history_20260912T222831176368Z/phase5_requirement_traceability.md` SHA9b0ae7c8c1f9bc7680d873a3557af5bf5cc861f728b5842b0e535c0dc250f522；最新独审70链接存在/106source+设计+原A5inputs未变化。正在回填R3/S1，H1/H2/H3待最终heldout；root负责主验收/README/next_entry/replay_index。主报告已填R5正式事实，不再称新R5未实现。
- 下一动作：root继续等待A绑定session19452（22:12:25起、内6600/外7200），B1由replay_audit等待session80225（22:10:45起）。两者正常计算stderr空，不重复启动。A结束调用frozen bind_v1 verify-binding；B1 agent自行verify。随后root用frozen heldout_v1 --workspace ROOT heldout-summary --selection-dir ...210839292741Z_selection_652993c7 --a-run ...Aheldout211254802638Z_b9c31d10 --a-binding ...221225440029Z_binding_a5fd1653 --b-run ...B1heldout211254789627Z_3d1257fa --b-binding ...221045541952Z_binding_26b7acbc，root run_logged新目录。完成6seed/18主单位配对与全部报告回填、最终证据索引后才能结束本轮。阶段5科学失败、阶段6不放行仍已确定。

## 2026-09-12 23:17 UTC：本轮执行与证据交付完成，科学验收未通过

- 两heldout绑定均完成，所有原session已结束，不存在待运行车辆或标准重放。A session19452，wrapper221225252280Z_phase5_cost_heldout_replay_binding_934e88b7 exit0/3154.515s，标准replay `variants/phase5_cost_holdout/results/phase5/replays/20260912T221228394230Z_8afb9b96` validation SHA83fb197650611b5806cc2c90e1d72835b2603c4d09309cd33212ec37c415a43f，bindingmanifest e4ac791697da6a19ca6521e74225bf9b07e5a69e9898fd2ec8881abc0d925579；最终verify wrapper230612530705Z...7411b2fa exit0/2.531s。B1 session80225已由replay_audit关闭，wrapper221045339197Z...5b81e422 exit0/3160.062s；标准replay `...phase5_rules_front_first_holdout/results/phase5/replays/20260912T221048306395Z_e4fc5f51` validation SHAea5b28b8889ff283cd160074142ff1ad9cc2689431508054b5fd87ed0df63bdd，bindingmanifest d2712125f8cb8456d2663175ad3d3b9ce5b0e5b8c958e51d10ae07489a3f8278；最终verify230424706781Z...4b3a6864 exit0/2.75s。两者13/13重放、source before=after、错误空，原科学失败保留。
- 正式冻结配对 `results/phase5/comparison_20260912T230631758620Z_heldout_47117b4d/heldout.json` passed true/errors[]/6seed/18主单位/fulltrue/incomplete[]，重复OFF完整轨迹一致。SHA c4a9d6b11429c69673d26b6bdea7b1f6d8cdaf76db19dd93d8cc00d627f3e326，manifest0b891a1ad0516b57640f7d155d7a18c6082e64fface7512719a34ea7b40d923a；wrapper230631571676Z_phase5_formal_heldout_paired_summary_6f25d9ef exit0/57.859s，session31458已结束。A/B1/OFF whole均0/6，local均2/6；mean C A .05259259259259263、B1 .05037037037037037、OFF .07407407407407407。B1−A mean C −.002222222222222255，B1−OFF −.0237037037037037，差异只在6312；B1−A末span均值 +.9304226744666645m。开发B1的小幅C优势未在保留集延续，没有改选B2/重抽种子/补第三方法或调安全界。
- 全部文档当前状态已回填：主验收、README、next_entry、replay_index、heldout运动报告末尾补充来源终态；需求矩阵最终 SHA05bbc600ce2fb728c848645f56bf0cd1aeed236a86bb767367bf02a75a8f8214，H/R/S占位全部清除。theory独审六seed各值/差值/OFF同一性、两摘要、88链接/106source/固定inputs通过，日志231144950801Z...3bf9e719、231451426109Z...ef071b5b。根代码仍冻结A94，完整R5只能从variants/phase5_r5_completed进入。
- 最终快照脚本 `tmp/phase5_save_delivery.py` 已独审关闭错包P2：显式绑定最终heldout SHA，核对其exact seal、固定selection+manifest、精确6case/seed/N、A/B run/binding/source/replay对应和五binding封存；这只是报告快照，不代替原标准重放。脚本SHA325ec7ef221685622ef0be4321ae7a19f680d2e668b8bb5b1c028807b4958b38。执行日志 `results/operations/20260912T231547857808Z_phase5_final_delivery_snapshot_20f5753d` exit0/.485s。
- **最终交付快照：`results/phase5/completion_20260912T231548093420Z/acceptance.json`**，37引用原件与报告快照、159个主文档绝对链接核对，完整39个清单文件最终逐hash/精确集合复核均无差异。evidence_hashes SHA dfb33bf771cccad632a2f5cb4a3fab7229404792ffe2684b4b0ac954f83b7ff7。artifact_integrity_checked=true / implementation_and_registered_experiment_delivery_complete=true；**phase5_scientific_accepted=false，phase6_allowed=false，next_stage_allowed=null**。这些字段明确区分执行交付完成与科学门槛未过。后续若继续，先读该冻结快照及docs/phase5_next_entry.md；不重复本轮已通过前置/整包重放，不篡改旧失败，另立阶段5机制单元。无交通收益、节能、全局收敛、互斥或一般安全证明。

## 2026-09-13 04:16 UTC：阶段5B新单元已登记，尚未运行正式实验

- 用户授权继续下一阶段5入口；本单元检验“私有退避到期且仍 ambiguous 时继续局部保守等待”。旧版本/旧实验只读，阶段6继续关闭。
- 前置核验 `results/phase5b/prerequisites_20260913T040953805450Z/verification.json`：旧交付39文件、旧R5包332文件、106当前源码和7输入一致；复用旧267测试和标准重放。
- 独立副本 `variants/phase5b_conservative_release` 已从旧R5正式run code/input_snapshot精确克隆。计划 `docs/phase5b_conservative_release_plan.md` 已冻结并复制进新副本，runner INPUTS添加计划以绑定来源。所有数值参数/SUMO桥不变，低速上端数值问题留待独立单元。
- phase5b_release_implementation 正做新测试RED及最小r5.py修改；root负责正式回归/17变体/标准重放。两个只读诊断代理正在完成旧R5与SUMO边界报告。尚无正式新机制结果，不得从本检查点宣称通过。

## 2026-09-13 04:32 UTC：阶段5B已通过回归，正式机制运行中

- 新9测试RED(18子断言失败)→GREEN9；旧R5相关51通过。root全回归276/0fail/0error/0skip，源码不变，wrapper `results/operations/20260913T042256145127Z_phase5b_integrated_regression_e8243aa0` exit0/224.469s。源码冻结 `variants/phase5b_conservative_release/phase5b_source_freeze.json`，107源码/4差异文件。
- 独立核心审查40测试(25旧+9新+6探针)通过、无P1/P2，源码前后不变；日志 `results/operations/20260913T042822575362Z_phase5b_independent_review_38159e46`。报告 `docs/phase5b_independent_review.md`正在补充只读比较helper审查。
- 正式LIVE+sampling由root session81119持有。run `variants/phase5b_conservative_release/results/phase5_r5/runs/20260913T042930121115Z_deb427af`，wrapper `.../results/operations/20260913T042929716765Z_phase5b_formal_mechanism_suite_05b34a2f`，timeout7200。已完成single_clear off/on，通过；competing off28/300保存区间，SUMO报告失败，recording=true。新ON结果待跑满，不能提前推断成败。
- 完成后先新副本标准 `phase5-r5-replay --run-dir <上述run>`，新日志；随后只读parent/new比较 + active competing ON保存动作.005细化/重放。旧source run/案例/参数均不改。比较helper正在补“新ON首trace前失败”保留空前缀的边界，属于记录器修复，不修改控制规则。最终收口脚本 `tmp/phase5b_save_acceptance.py`尚未使用，待独审。

## 2026-09-13 05:00 UTC：阶段5B单元完成、正式证据已闭合

- 无root在跑会话。新17机制run session81119已完成，wrapper042929716765Z_phase5b_formal_mechanism_suite_05b34a2f exit0/832.218s；17尝试/14完整/3 OFF SUMO报告失败prefix/0未启动。recording=true，engineering/driving=false，scientific=null；107源/8输入不变。run evidence SHA6f7ddd2a844f9b58a29bd7efd7b7774d9d3bad5e94809c5f99e72784b51ff192。
- 标准replay session10027已完成，固定 `variants/phase5b_conservative_release/results/phase5_r5/replays/20260913T044401892589Z_bd809c6b`，wrapper044401542067Z_phase5b_formal_semantic_replay_7d1c727d exit0/528.203s；17 cases passed/errors[]/unstarted[]，source before/after一致，3失败前缀仍失败。
- 只读parent/new比较session4706已完成，`results/phase5b/comparison_formal_20260913T0444`，wrapper044401551572Z_phase5b_formal_parent_comparison_56d6a6a4 exit0/25.14s，evidence SHA c1b4476848251b2c59abd8912bd22d4557ff75b649e8f6e45aa62b73c696b00f。8 OFF共同动作/记忆/物理链exact；17参数/初态一致；11完整配对有全窗delta，6含prefix的delta=null。描述34行 `results/phase5b/descriptive_rows_20260913T0446`。
- 活跃competing新ON4车同保存动作.005积分包 `variants/phase5b_conservative_release/results/phase5b/active_integration_20260913T0455`，manifest ee1900be432a7fa90a42d59c56bebc5d70d686dda72b1ceaf818fd27e09185ed；create045431259994Z...778e2fe6 exit0/5.922s，snapshot replay045527454997Z...1caae3a4 exit0/3.141s。最大位置差1.6958362550667516e-5m，heading0；只固定动作积分，不声称活跃控制采样或细化扫掠/舒适通过。
- 两次路径调用错误完整保留：045341401879Z...26e04f9a输出不在新副本，部分根results/phase5b/active_integration_20260913T0454未封存；045503890893Z...972b03e8 source-run参数错误在路径检查拒绝。重试只改调用路径，未改策略/模型/数据/脚本。
- 276全回归、40独立控制测试、比较helper P2修复后的9本地/12独立、补充总体门槛6分支、最终binder18夹具通过。核心与helper审查无P1/P2。helper最终948f3e5e...；binder最终8af823bf...；日志与早期失败均保留。
- 最终绑定 `results/phase5b/completion_20260913T045835330124Z/acceptance.json`，23文件；wrapper045834410797Z_phase5b_final_delivery_binding_5530e382 exit0/1.141s。artifact integrity/delivery complete/semantic bound=true，scientific=false，phase6=false；源、回归出处、两侧标准重放、比较、数值和文档链接已检查。
- 验收 `docs/phase5b_conservative_release_acceptance.md` SHA7380ce981443a74959e2d0339e7b57b010766ab99e8ff83c4fc5a9c28d8858be。重放索引 `docs/phase5b_replay_index.md`；当前下一入口 `docs/phase5_next_entry.md` SHA37e56d2aeb957e20fb9ff6bd0f8cfee9d024023ceaa442c71b58b5e62896b3fb。
- 科学负结果：8新ON均无执行失败，但competing/same/quantized持续不换道，短暂停车后蠕行；speed_floor均速下降；reentry完成换道1→0。1889到期模糊阻断不证明互斥/公平/编队。下一独立单元优先速度求解可行上端，参数/守卫不放宽；停车执行器可观测性、SUMO原生最小复现、形成/恢复/UNKNOWN等另列缺口。阶段6/7/8继续关闭。

## 2026-09-13 05:52 UTC：阶段5C车道优先单元已登记并开始实现

- 最新用户建议优先于旧速度端点入口；车道优先、同车道前车优先，保留entered/inward/occupied与全部守卫和数值参数。计划docs/phase5c_lane_priority_plan.md已写入独立副本INPUT候选；107源码父快照/8输入及5B封存证据核对通过。
- 新副本variants/phase5c_lane_priority，从5B正式包clone，无git HEAD，不改旧数据。core/harness代理分别实施r5核心及固定案例/runner/replay；均要求先RED后GREEN，根负责回归、独审、正式试验、重放及报告。
- 预登记原8案例17变体，以及新single_clear+60s三受控车/两慢前导扩展6变体（包含同物理等待基线）。阶段5科学门槛仍未通过，阶段6关闭；尚无5C正式车辆结果。

## 2026-09-13 06:12 UTC：阶段5C实现完成，正式车辆试验前验证中

- 110源码、7差异文件；新增核心24测试、案例13测试。新增规则依赖可信完整车身可见strip，车道优先再同lane2m，pure缺省False；所有数值和安全守卫不变。三个旧records随机链测试显式选等待False，原断言保留。
- 首完整313：root session36748已结束，wrapper060409792208Z_phase5c_integrated_regression_ade9712e，312pass/1旧draw前提fail/0errors，源码不变，未生成成功freeze。定向修复GREEN后第二完整313由root session45675持有，wrapper061008877499Z_phase5c_integrated_regression_bound_885174e7，timeout1200。不要重复启动；尚未冻结extension、未正式跑车。
- 独立core probe9通过，280组父assess/gate差分、30拍完整decide链、3375偏序三元组及22记忆字段篡改等通过，未发现P1/P2。对应wrapper060940960623Z_phase5c_independent_probe_693c8e03；审查报告由代理补写。
- 证据helper独审已复现并修复：gradual参数数值类型混同；回归删减stdout错源混绑（新日志绑定完整attempt freeze SHA）；物理完成但evaluation failed应按metadata.execution_status对应标准replay，评估失败保留。候选helper测试及早期fixture错误/RED全部保留。最终helper审查待最后GREEN报告。
- 下一动作：等待session45675及独审结束；成功后root tmp/phase5c_freeze_extension.py单次冻结预登记60s扩展；运行原17+新6两个正式包；各自phase5-r5-replay；父/新comparison与gradual lifecycle/detection摘要及快照重放；最后sourcebound验收和next_entry。科学门槛/阶段6仍未通过。

## 2026-09-13 06:16 UTC：阶段5C回归通过，原17项正式运行中

- root session45675完成，313/0fail/0error/0skip，source unchanged，wrapper061008877499Z_phase5c_integrated_regression_bound_885174e7 exit0/227.094s。成功freeze variants/phase5c_lane_priority/phase5c_source_freeze.json；完整attempt freeze SHA由stdout绑定。独立核心9及证据helper/binder14通过，无未关闭P1/P2。
- 单次扩展冻结wrapper061438776913Z_phase5c_freeze_registered_extension_710e1ae3 exit0/.281s；case SHA a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a，0entropy，两case20/60s。计划SHA23066a79d77aa57ea227c8ffa0898c70253e24df79d8532345ba416869be7296不再改。
- 原17项LIVE由root session33960持有，run variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T061451357664Z_cd3da24b，wrapper该副本results/operations/20260913T061451110885Z_phase5c_formal_original_mechanisms_1407fe0a，timeout7200。singleclear OFF/ON记录与驾驶通过；competing OFF保留原SUMO碰撞报告，ON尚未结束。
- 完成后同源码新跑extension6（phase5c_extension.json），不重抽/调参；两个各自标准phase5-r5-replay；root tmp/phase5c_compare_priority.py对固定5Bparent+新17，tmp/phase5c_gradual_summary.py对新6，均保存快照重放。最后tmp/phase5c_save_acceptance.py实际source/spec绑定。当前无其他agent运行任务；独立审查报告已经落盘。阶段6仍关闭。

## 2026-09-13 06:45 UTC：阶段5C所有正式运行/重放结束，最终报告绑定中

- 原17 LIVE session33960已结束，wrapper061451110885Z...1407fe0a exit0/620.969s；17attempt14完整3OFF失败prefix，新8ON全部完整驾驶/舒适通过，模型扫掠0，339manifest SHA3155cca5eaa634ead59353a6327a244ae70730f1fa4ee18f4f6bd9d75c37ff34。标准replay session96799完成，062619302264Z_135ea687，wrapper062619017260Z...d3192948 exit0/474.516s，17pass/source前后同/errors与unstarted空。
- 扩展6 LIVE session47743结束，run062619294263Z_4126e0fd，wrapper062619009264Z...4f341559 exit0/536.266s；6attempt5完整1三车OFF失败prefix，207manifest SHA08e1ab0f619dd404fd048d62c3718838224c55d4fbcbaf14d9939be76ae03f5c。其标准replay session49526结束，063537973705Z_c407c3ee，wrapper063537672656Z...8e5d2fca exit0/375.937s，6pass/source前后同/errors与unstarted空。
- 新比较results/phase5c/comparison_formal_20260913T0626，session54602结束exit0/31.25s；snapshot replay session38724结束exit0/30.219s，comparison_byte_verification_20260913T0632核整包集合/字节一致。14完整配对可差分，3prefix配对全窗delta=null，8OFF共同链精确。34行原值descriptive_rows_20260913T0628。
- 三车过程gradual_summary_20260913T0636，创建exit0/4.359s；异cwd保存脚本replay_20260913T0638 exit0/5.204s，gradual_byte_verification_20260913T0638整包字节一致。ON1完成/等待0；两者全5/受控3判据false、持续区间均空。ON upper有稳定ref但483拍增量guard拒绝；waiting43.0s前锚点越出200m后两车各170拍UNKNOWN保守保持。
- 无root车辆/重放会话在跑。root已写phase5c_lane_priority_acceptance.md、replay_index.md和新的phase5_next_entry.md；下一单元应诊断局部等待后的再启动可行性，不把真实低速归结为epsilon。两个代理仅做最终只读证据/报告补核。随后root执行tmp/phase5c_save_acceptance.py --spec tmp/phase5c_delivery_inputs.json，封存完成再登记最终路径。不要重复运行正式套件。

## 2026-09-13 06:53 UTC：阶段5C单元已完成并封存

- 最终交付：`results/phase5c/completion_20260913T065251926120Z/acceptance.json`。wrapper `results/operations/20260913T065250805931Z_phase5c_final_delivery_binding_b85dba21` exit0/1.313s，24清单文件；封存后再次核对完整文件集合及每个SHA一致。manifest SHA `8a6122c44cafca6150d66c71c3e6b15b76c666742213d4a88b30a9a1560e74ad`。
- implementation_and_registered_experiment_delivery_complete=true；semantic_replays_bound=true；313测试通过且source不变；scientific_accepted=false、phase6_allowed=false。绑定包括5B父run/replay、5C原17与扩展6run/replay、313完整attempt freeze、当前110源码/各10输入、对比/三车过程、审查及最终报告快照。数值参数与5B一致，仅新增优先布尔开关。
- 最终真实包独审无P1/P2，wrapper065005580677Z_phase5c_real_final_evidence_review_precision_d454a8c2 exit0/3.344s；两摘要7/5文件snapshot重放字节一致，51绝对链接存在。审查报告最终SHA c5fb0b7c517bed29f7ae5f2a92f43c4f9aaaaa2ed2b88897c81fbebddba2f6c7；liveness最终SHA2bb2f83b958b821981f9018f65d5527d0f75a378fd6e425c7c3cf6fcdd3c63ce。
- 事实：原并排/重复私有态/同时间格3用例完成0→1（同类物理场景，不是3独立场景泛化）；60s三车priority1次/等待0次，原全5与受控3持续形成区间均空。下方未接续，真正低速与慢前导/B1守卫约束保留。4个OFF失败prefix及front_priority OFF驾驶失败保留。
- 无root运行会话、无待车辆/标准重放。所有代理已停写，报告已提交Codex打开队列。若继续，先读docs/phase5c_lane_priority_acceptance.md、phase5c_replay_index.md及新的phase5_next_entry.md，从5C冻结源码进入“局部等待后的再启动可行性”独立单元；不要重复这轮正式实验或篡改旧失败，阶段6/7/8仍关闭。

## 2026-09-13 10:53 UTC：阶段5D无通信局部博弈单元实施中

- 用户最新要求查主从博弈/分布式换道论文并继续完成。已用primary文献检索；docs/phase5d_game_theory_literature_review.md、phase5d_independent_literature_notes.md已写，独立原PDF/26页审读日志在results/phase5d/literature_20260913。root额外arXiv归档尝试依赖/TLS错误保留，web已读方法段，不能称本地归档成功。
- 前置只读核验results/phase5d/prerequisites_20260913T104302456188Z/verification.json；wrapper104302289057Z...402e999b exit0，24/339/207文件及110当前源码、原/扩展各10输入一致。313与23replay仅复用；science=false/6关闭。
- 预登记docs/phase5d_local_game_plan.md已复制新variant输入。新variants/phase5d_local_game从5C原17run code/input_snapshot clone110，单独拷贝5C原extension固定SHA a21f8a...e682a；clone wrapper104421672817Z...ae418e41 exit0。
- 唯一变化：R5阻断等待时，fixed vs有限minimax vs对方leader/本车follower的悲观Stackelberg；模型5s、peer动作±.5/0、gap/speed/effort权重1/1/.05；原5m/s门槛、priority/gate/guard/formation/模型不变。只执行ego请求，矩阵及guard回退分别记录，不能说真实邻车遵守均衡。
- 正式计划：沿用5C扩展同一两物理case/6变体，minimax和stackelberg各一包；fixed用既有5C，全部12日志重放。本轮唯一活跃新策略物理场景是60s三车，不是统计/留出验证。
- agent phase5d_waiting_core 正在新variant独占noa/waiting_game.py、controller.py、tests/test_phase5d_waiting_game.py（先RED）；root修改run.py、experiment runner/replay和新harness测试，已6断言有效RED日志variant/results/operations/20260913T104703368097Z_phase5d_harness_red_8d1040ec，尚未GREEN。root tmp/phase5d_regression.py已适配但尚未执行。无正式车辆/重放进程在跑。
- 后续先完成核心/harness GREEN、独立spec/quality审查、回归冻结；再两正式run、标准replay、读后数据摘要/快照重放/交付绑定。不要重新clone或重跑旧5C。

## 2026-09-13 11:12 UTC：5D完整回归通过，正式比较运行中

- 347 tests/0 fail/0 error/0 skip，完整回归wrapper results/operations/20260913T110036350132Z_phase5d_integrated_regression_bound_e04df533 exit0/279.921s，session58762已关闭。成功冻结variant/phase5d_source_freeze.json，113源码、7登记delta；原helper SHA e74ac541a6ca8a041248f9f60dfe192c46e98f9a6724b7512d119f888054fa58保持只读。
- 核心独审11/11通过，root wrapper111020045837Z_phase5d_independent_core_probes_f2a6c540，source前后不变；报告agent正在收尾。证据review确认旧fixed参数/矩阵差分、game类型/存在性重放、父6包，缺陷仅原回归helper遇skip会exit0但无freeze；本轮无skip不受影响。已保留原文件新建tmp/phase5d_regression_v2.py并8独立probe GREEN（110900327210Z...346424b3），不重复347；最终binder仍严格绑定原0skip成功证据。
- LIVE minimax session37783，variant run results/phase5_r5/runs/20260913T111001467229Z_2d9c8d5f，wrapper111001072685Z_phase5d_formal_minimax_f83f8262。
- 首次Stackelberg wrapper111001081269Z...6b5d70a2 exit1/.406s：RunRecord构造前output_path收到扩展前缀\\?\D路径导致root containment拒绝，未产生实验包/未启动case。复查当前Path.resolve与root均正常；原源码不变，同参数新尝试LIVE session68578，run20260913T111103953169Z_c63ac16e，wrapper111103549825Z_phase5d_formal_stackelberg_retry_initialized_path_3b935a62。不要删除首启动失败或称作车辆算法失败。
- 两个LIVE尚未结束，尚无新正式效果结论。结束后分别标准replay（同V源码），根tmp/phase5d_compare_games.py做三策略18变体读后比较（fixed parent原5C6），helper已写未实包执行；snapshot跨cwd重放/字节核验；tmp/phase5d_save_acceptance.py初稿未调用、证据review在审。
- 论文追加归档成功results/phase5d/primary_archive_20260913T111008400597Z/manifest.json（Hang+Yoo两篇，11/14/12页；仅归档不升级阅读范围）；wrapper111006853716Z...21e71a8d exit0/6.203s，6文件hash核对。根文献总述已链接；原3论文26页独立全文审读报告保持原hash。

## 2026-09-13 11:42 UTC：阶段5D局部博弈单元完成并封存

- 最终交付 `results/phase5d/completion_20260913T114142485584Z/acceptance.json`，39文件；wrapper `results/operations/20260913T114141113576Z_phase5d_final_delivery_binding_02e701d1` exit0/1.735s。manifest SHA `2a0b91f7b159a411cff71dd14fce172b0fb4a49f64b4796b613dd23ef8409785`。implementation_and_registered_experiment_delivery_complete / semantic_replays_bound / tested_source_unchanged=true；scientific_accepted=false、phase6_allowed=false。报告与入口9文档快照已封存，不再修改。
- 当前113源码仅7登记delta，11输入，继承数值不变；新增mode、5s预测、peer假想动作±0.5/0及权重1/1/0.05。缺省fixed。最小换道5m/s、原guard/priority/UNKNOWN/随机/形成均不改；未实现低速换道或浮点端点修复。
- minimax正式run `variants/phase5d_local_game/results/phase5_r5/runs/20260913T111001467229Z_2d9c8d5f`，wrapper111001072685Z...f83f8262 exit0/607.047s；stack正式run111103953169Z_c63ac16e，wrapper111103549825Z...3b935a62 exit0/607.687s。各6尝试、5完整、1 OFF原生失败前缀，211文件，recording=true，总体engineering/driving=false。首Stack路径构造失败保留，不能算车辆算法失败。
- 新标准replay分别 `results/phase5_r5/replays/20260913T112041226929Z_ba12ddc8`（wrapper112040750835Z...9dd95de8 exit0/433.437s）和112236784168Z_4ee72d26（wrapper112236370045Z...0e7d22d2 exit0/437.812s），共12case全部passed/source前后同/errors及unstarted空；2 OFF仍failed且failed_execution_prefix=true。其manifest SHA分别0155e9159d725a57c3eda90f2762a634d3452873ec2761152d67300cf150d27d、b9bc09466e54d88fae47b11e9b12c18f55f04822bd7fe8c6cbbd8cf29ee10621。
- 比较 `results/phase5d/comparison_formal_20260913T1122`，wrapper112236382062Z...3ddc686b exit0/20.578s。旧snapshot1124虽字节同，实际child cwd仍root，独审有效RED；原数据/日志不改。新透明launcher实际os.chdir(D:/yanjiu1)，输出comparison_actual_crosscwd_20260913T1132、回执crosscwd_receipt_20260913T1132，wrapper113552974106Z...886c702c exit0/20.734s；comparison_actual_crosscwd_bytes_20260913T1137核整包集合及字节同，wrapper113716843183Z...35bdf005 exit0/0.234s。两摘要manifest c01f65db0b230250464fb880345ae9dcdd23aa7035acb3d29f5ea0a1ee4ad481。最终binder绑定实际回执、脚本、完整命令、wrapper和日志。
- 347全回归0fail/error/skip、核心独审11通过、证据前置9及实际矩阵独立重算通过。实包不同请求106/127，guard拒绝27/47，真正改变79/80拍；收益模型对方动作不等于对方承诺。两个证据P2已闭合，旧skip helper保留、v2仅合成验证，没有第二遍347。独立最终replay/cwd核验wrapper113752097479Z...f6e75893 exit0/3.015s，结果independent_final_replays_20260913T113755079142Z。最后封存只读复核正在收尾，不重复原测试/车辆/重放。
- 科学负结果：同一60s三受控车场景，fixed/minimax/Stack全为上方换道1、下方0，全5/受控3形成与候选区间均空。下方clear18.1/19.8/20.2s，clear速度0.03236/1.84940/1.70116m/s；均速2.79008690/2.79005449/2.79005559m/s，无改善。仅1活跃新策略物理场景，无统计/泛化主张。所有早期失败、OFF前缀及此前阶段5科学失败保留。
- 文献7篇主线/补充与额外线索已整理，3篇26页独立全文阅读+另外3篇原PDF归档/选段阅读有准确范围；不把共同定位/已知收益/真实类型假设搬入在线策略。文档 `docs/phase5d_game_theory_literature_review.md`。
- 所有root车辆/标准重放/摘要进程已完成。验收 `docs/phase5d_local_game_acceptance.md` 已提交Codex打开队列；重放索引 `docs/phase5d_replay_index.md`；下一入口 `docs/phase5_next_entry.md` 为阶段5内低速换道可行候选/联合排序，先核5D封存后新副本，参数变更需先登记。不要重跑这轮或修改已封存5D，阶段6/7/8仍关闭。

### 2026-09-13 11:44 UTC：5D封存后独立核验完成

- `results/phase5d/independent_delivery_20260913T114351830186Z/verification.json`，wrapper `results/operations/20260913T114350461302Z_phase5d_independent_final_delivery_b0f313c6` exit0/1.390s：39清单成员、38引用快照、9当前文档、97绝对本地链接均通过；关键来源/3份各6case标准重放绑定、实际跨cwd回执/整包字节、binder及wrapper日志hash一致。
- 最终manifest仍为2a0b91f7b159a411cff71dd14fce172b0fb4a49f64b4796b613dd23ef8409785；science=false/phase6=false。独立probe SHA cacf1536cbd6d44999461dd12f67f2f46181292b3ac99eaf763e9e4e22acfd12。已封存9文档未改；本轮无运行进程、无待完成核验。

## 2026-09-13 12:48 UTC：阶段5E精确可行速度上端单元完成并封存

- 前置核验 `results/phase5e/prerequisites_20260913T120339903006Z_27c44d80/verification.json` 重新计算5D两正式包的113份源码和11份输入，确认快照一致、5D最终交付完整，并保留 `scientific_accepted=false`、`phase6_allowed=false`。首次核验因脚本错误排除嵌套清单而失败，日志 `results/operations/20260913T120254804556Z_phase5e_parent_prerequisites_5955dd32` 原样保留；修正后的wrapper为 `20260913T120339645205Z_phase5e_parent_prerequisites_retry_7444c465`。
- 新只读版本 `variants/phase5e_exact_endpoint` 从5D正式快照克隆。唯一控制变化是：原停止表达式确认配置上端5 m/s可行时，`_comfortable_speed` 精确返回5.0；不可行时仍返回原二分保守下界。未改变5 m/s换道门槛、5 s轨迹、加速度、安全包络、局部博弈或任何数值参数。源码冻结 `variants/phase5e_exact_endpoint/phase5e_source_freeze.json`，SHA `48128cf035ebe95ebdee79986e2043eea706e934d2012ecc48d513a6828accee`。
- TDD RED捕获旧值4.999999925494194；GREEN确认可行端点为5.0、边界少1e-6 m时仍为4.999999776482582。受影响回归191/191通过、0失败/0错误/0跳过、源码前后不变，wrapper `results/operations/20260913T121118654980Z_phase5e_affected_regression_retry_72f5c23e`。未受影响模块复用5D已封存347项证据，不重复旧车辆套件。
- 正式原8案例run `variants/phase5e_exact_endpoint/results/phase5_r5/runs/20260913T121814146616Z_12a1dc15`：17/17启动，13完整、4个OFF原生SUMO失败前缀；run manifest SHA `8e6c6ffe4a94a0bb06c1f52ce50ae263dd4a84a017908667072cc63255e6ab3c`。标准replay `.../replays/20260913T122921286694Z_13a9cac5` 17/17通过、errors/unstarted为空、source前后一致，4个失败前缀仍按失败重现；manifest SHA `d1dee65f5b53363c79f4fe949e8d8fbf0e92bd9248f167699904fe6e6f05b2e8`。
- 固定父包/5E比较 `results/phase5e/comparison_20260913T1244_exact_endpoint_final` 绑定相同案例、初态、私有状态、参数、道路、时钟与两侧标准重放；5文件精确清单SHA `01a6904fb556226a399d770359028d13dd17e2d116f6bb2ce68d468a4542ce79`。speed-floor ON右车由0次换道变为1次并在4.98 s完成；全队与局部形成仍false。OFF两车在0.5 s同时提交后于2.8 s原生碰撞，旧父包30 s完整；该新增安全失败明确保留，不能用ON局部通行掩盖。
- 最终交付 `results/phase5e/completion_20260913T124834184236Z/acceptance.json`，75文件；wrapper `results/operations/20260913T124833444297Z_phase5e_final_delivery_binding_78ac53ff` exit0/1.328s，manifest SHA `e02e6b73db8b73504b1be98ce1daa926111cfdce741d59ae5d08f169d813df85`。验收 `docs/phase5e_exact_endpoint_acceptance.md`、重放索引 `docs/phase5e_replay_index.md` 和下一入口 `docs/phase5_next_entry.md` 已写明复现命令与限制。
- 结论：精确可行上端缺陷已修复，但阶段5科学验收仍未通过，阶段6/7/8继续关闭。下一独立单元研究真实1.70--1.85 m/s低速下、仍通过原 `verify_candidate` 全时域守卫的速度自适应/更长时长候选；建议预登记保留5 s并增加7.5 s、10 s，若都不可行则报告无可行解，不强放行、不缩小安全包络。
- 收尾时新运行只读验证 `results/operations/20260913T125326894641Z_phase5e_fresh_final_verification_6a11ea73`，重新核对75文件交付、345文件正式run、3文件标准replay、5文件比较、114当前源码和17项重放，退出0。第一次聚焦测试调用因`run_logged.py`固定根cwd而发现0项、第二次直接相对路径因此找不到文件，两个失败目录均保留；显式隔离launcher重试 `results/operations/20260913T125423611553Z_phase5e_fresh_focused_tests_launcher_503fed24` 为3/3通过。

## 2026-09-13 17:00 UTC：阶段5F速度自适应时长单元完成正式运行与报告

- 前置只读核验 `results/phase5f/prerequisites_20260913T155330954265Z/verification.json` 和隔离克隆均通过；新版本为 `variants/phase5f_adaptive_duration`。原8案例SHA `46cff8d...af20`、5C扩展SHA `a21f8a...e682a` 分开保存，旧5E/5D结果未改。
- 预登记候选5/7.5/10 s；必要速度下界1.30344310/0.86896207/0.65172155 m/s。只在R5-on且车道优先on启用，采用测得正速度；每个候选仍通过候选自身R5时域及原 `verify_candidate`，无safe不提交。0速、UNKNOWN、安全包络、纵向请求、随机/博弈/形成均未放宽。
- 新增16项测试通过；最终受影响回归240/240、0失败/0错误/0跳过、源码前后不变，wrapper `results/operations/20260913T161716818841Z_phase5f_affected_regression_retry_5ffc1314`。源码冻结SHA `4982d94ee84126df5e80dbe4f8c761185926fd1bbd89f4678ebd4999502acddf`。
- 正式run：扩展fixed `20260913T162400640291Z_a5586029`、扩展adaptive `20260913T162400652574Z_9f6cc9d8`、原17 adaptive `20260913T162400649059Z_207be322`。分别5/6、5/6、13/17完整；其余均为继承的R5-off原生碰撞前缀，记录通过、整体工程不通过。
- 三个标准replay全部通过：`20260913T163527576957Z_4632477a`、`20260913T163527576957Z_6c53edf8`、`20260913T164250928637Z_74f0aa54`。首次并行重放原17包因共享 `latest.json.writing` PermissionError失败，操作层负证据保留，顺序重试通过。
- 最终比较 `results/phase5f/comparison_formal_20260913T1659_final_v2`，manifest SHA `17d799e9082bdd2b5b3a0fef27ca7bd191ea3e9fb6a39aee20016deeb0712c45`。扩展/原始分别新增1/4次完成，另有front-priority一项在20 s窗末仍执行；正式提交均是测得4.1533--4.8044 m/s的5 s计划。7.5/10 s无提交；1.70--1.85 m/s父状态仍由R5阻断。
- 11个非目标变体轨迹逐字兼容：扩展2个OFF加waiting，以及原矩阵8个OFF。所有比较形成/局部形成成功均0；front-priority OFF舒适/跟踪失败、碰撞前缀和旧研究失败均保留。科学验收=false，phase6_allowed=false。
- 验收报告 `docs/phase5f_adaptive_duration_acceptance.md`，重放索引 `docs/phase5f_replay_index.md`，当前入口 `docs/phase5_next_entry.md`。下一单元先只读分解新增换道完成后仍无形成的原因，不直接添加控制自由度、不重跑5F正式包。

## 2026-09-15 07:24 +08:00：Phase5G简单局部if/else编队实现与最终验证完成

### 设计、实现与变更范围

- 本单元按已批准设计执行：设计提交 `462108bfdda71f090d1051d8d4b68634f091393a`，实施计划提交 `5d652527e4a011a1a0d8c9ea2b87eccc52fa9a93`。规则坚持无通信、有限局部观测、本车私有记忆、禁止全局车辆列表/全局槽位/中心调度；没有障碍车、背景车或脚本慢车。纵向只采用最近前车15/30 m和±2 m容差的三分支规则，增量限幅±0.5 m/s²；仅局部后排车可向唯一更少车辆的相邻车道申请换道，仍须通过既有安全守卫，每车最多一次编队换道。
- 实现/修复/测试提交依次为：`43f552bd43f82eb7f4dce54896ce8810b9a7f9b8`、`dc031c79364be9896bc0b0ef74ca59e1c323c983`、`72dc72d0fb8a783515d3c33f671f2261fc2bbb5c`、`69a0e08a8e9baa6b646219d0fef24fa391c2c771`、`008adb60135eece67f058bf68048116844e3f60f`、`11d7f2dc07dd03a70a81f8bf9fd4a981f6263229`、`f6dea94a748e0a9f25bb5012a1769b1d0ae71db1`、`2dc54342ea875e2e0a8c04482612a1f5b9235128`、`b534bed76c1be2bcd5e7df8c75664ffb82d258bb`、`dc97a88c7e652579368d7ba8edb210058ce63ca5`、`87b8b7c59affcc36eb52cfda2c547b7c03d51cf6`、`84aa1de55a242de6668ecd365a2e8b1df42a6f08`、`dac23710fa64f492b4287b5ed3f05413614bcd63`、`8e033deb94cc6ad4b9c03bb6cb2479b07d68d741`、`b46d53764eda851736f5ad907ef77d066a9f37a0`、`80b87748a4a69bbf105e2175caff01283ca3f32b`、`a346b22cc9bf14bd7722ef8fb16396e3a2fddf40`。
- 确切变更文件为：`variants/phase5g_pure_formation/docs/superpowers/specs/2026-09-14-phase5g-simple-local-ifelse-formation-design.md`、`variants/phase5g_pure_formation/docs/superpowers/plans/2026-09-14-phase5g-simple-local-ifelse-formation.md`、`variants/phase5g_pure_formation/noa/simple_formation.py`、`variants/phase5g_pure_formation/noa/controller.py`、`variants/phase5g_pure_formation/simulation/phase5g_clock.py`、`variants/phase5g_pure_formation/configs/phase5g.json`、`variants/phase5g_pure_formation/experiments/phase5g.py`、`variants/phase5g_pure_formation/experiments/phase5g_replay.py`、`variants/phase5g_pure_formation/run.py`、`variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py`、`variants/phase5g_pure_formation/tests/test_simple_formation_rules.py`、`variants/phase5g_pure_formation/tests/test_simple_formation_controller.py`、`variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`、`variants/phase5g_pure_formation/tests/test_phase5g_lane.py`、`demo/sumo_gui.py`、`runrun.py`、`tests/test_runrun_demo.py`、`README.md` 和本检查点。没有修改阶段5F封存结果或旧失败证据。

### 最终测试与运行日志

- 变体语法：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T225615039518Z_simple-formation-final-compile_d976ad38`，exit 0。
- simple focused 70/70、0 fail/error/skip：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T225623144016Z_simple-formation-final-focused_e5cea79e`，exit 0。
- Phase5G inherited 101/101、0 fail/error/skip：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T225658522921Z_simple-formation-final-phase5g-regression_e84c729e`，exit 0。
- 根目录 `runrun` 专项 68/68、0 fail/error/skip：`D:\yanjiu1\keyan1\results\operations\20260914T225803706053Z_simple-formation-final-root-demo-tests_f5019c86`，exit 0。
- 根目录完整受影响回归 281/281、0 fail/error/skip：`D:\yanjiu1\keyan1\results\operations\20260914T225822346163Z_simple-formation-final-root-regression_af84ad46`，exit 0。
- 三个规模都只运行一次：3车 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T230034152310Z_simple-formation-final-3car_959b982b`，6车 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T230133218295Z_simple-formation-final-6car_2b491ee0`，12车 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T230359600516Z_simple-formation-final-12car_fc4675ae`；三者均exit 0，没有按科学结果重试或改用`latest.json`。
- 精确6车重放：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T231107255411Z_simple-formation-final-6car-replay_b672831c`，exit 0。三包锚点/输入绑定审计：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T231531052968Z_simple-formation-final-anchor-audit_09a0d6f5`，exit 0。独立指标读取：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\operations\20260914T232013298322Z_simple-formation-final-metrics-audit_6371d46a`，exit 0。
- `runrun.py --check`原环境输出：`D:\yanjiu1\keyan1\results\operations\20260914T231637417064Z_simple-formation-final-runrun-check_ad6173b5`，exit 0。新增同一子进程内的原子零副作用审计：`D:\yanjiu1\keyan1\results\operations\20260914T233912624164Z_simple-formation-final-runrun-zero-side-effect-audit_629ec313`，exit 0、`passed=true`；它先记录根`results/demo_runs`与变体`simple_gui_sources`的精确目录名集合及`tasklist`中的SUMO进程，再实际调用`python runrun.py --check`，最后重新记录。子命令returncode 0、stderr空，两个目录集合前后逐项相同，前后`sumo.exe`/`sumo-gui.exe`集合均为空。
- 编辑器运行/调试等价入口（仅在内存中设置`SHOW_GUI=False`）：`D:\yanjiu1\keyan1\results\operations\20260914T231712652752Z_simple-formation-final-debug-equivalent_7b648bdc`，exit 0。新轨迹与配置/帧核验：`D:\yanjiu1\keyan1\results\operations\20260914T232041458037Z_simple-formation-final-debug-trace-audit_f254e030`，exit 0；没有编辑默认配置。后续原子零副作用审计记录的当前最终post-state无SUMO进程；不把该后续状态表述为debug执行自身的原子前后集合证据。

### 固定证据、重放与独立科学事实

- 3车字面路径：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final\20260914T230034382845Z_91f43ba4`。
- 6车字面路径：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final\20260914T230133460292Z_000af52a`。
- 12车字面路径：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final\20260914T230359835380Z_d22fc580`。
- 6车精确重放路径：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\replays\20260914T231107520227Z_df6b4c94`。`passed=true`、semantic/source/engineering replay均通过，450/450区间、27000车辆子步、最大数值误差0、`errors=[]`；科学门槛仍为false，且因源结果科学失败，`variant_acceptance_passed=false`。信任模型如实为`sibling_anchor_only_not_whole-package-tamper-resistant`，不是签名来源证明。
- 三包均通过`phase5g_external_trust_anchor_v2`源锚、完成锚、源码/输入快照、外层/子包manifest及物理/案例/参数/初始记忆摘要重算。共同源码根为`105161e0fbf92e329d5fb33efeb02a5871feb67c63ab5acad609f3a6ccd87205`；3/6/12车输入根分别为`8663fd9174755fd07d696db277b5ad4fd1f710cd429760afb44b0e45e58340a2`、`cf121b2a0c52b4bc171b6e4f49dd15c0bf9557da96fc4b85d87bc918f56fd106`、`b5cafbd682a402ad8dc3557009cdb1e1438d76f749e618c83d68d24806c48340`。
- 3车独立输出：全队形成false，形成/保持时间均null，完成/编队换道0/0，最终车道计数`[1,1,1]`，最低速度8.375438347096939 m/s，恢复false，碰撞0，几何与舒适均true；工程记录通过，科学门槛不适用、结果null，持久区间0、候选区间0。
- 6车独立输出：全队形成false，形成/保持时间均null，完成/编队换道0/0，最终车道计数`[3,2,1]`，最低速度9.496692509585099 m/s，恢复false，碰撞0，几何与舒适均true；工程记录通过，科学门槛适用但false，持久区间0、候选区间0。失败原因保持为`no_persistent_local_group`和`whole_cohort_milestone_not_met`。
- 12车独立输出：全队形成false，形成/保持时间均null，完成/编队换道0/0，最终车道计数`[4,4,4]`，最低速度8.085958821063635 m/s，恢复false，碰撞0，几何与舒适均true；工程记录通过，科学门槛不适用、结果null，持久区间0、短暂候选区间1，不能把短暂局部候选改写成形成成功。
- debug-equivalent轨迹：`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_gui_sources\20260914T231713066746Z_be5f7def`，6车、451帧，轨迹SHA-256为`8a2655bf7004558d1d39ec52b9ce559ebf18eb5dc559a48f730b178b0ad2e5e4`。已保存并核对顶部解析配置：车辆6、目标10 m/s、seed 1、时长45 s、GUI delay 40、auto zoom true、wait before close true、六项规则90/15/30/2/0.5/1；唯一临时差异是`SHOW_GUI=False`。

### 工程结论、科学结论与下一入口

- 工程实现完成：规则、控制器接入、轨迹生成、外层证据绑定、精确重放、根直接入口和环境自检均通过；三组运行碰撞均为0且几何/舒适均通过。`runrun.py`现在无菜单，直接编辑顶部配置后可点击运行/调试或执行`python runrun.py`；`python runrun.py --check`不运行仿真、不创建演示目录、不打开GUI。
- 科学结论未通过：固定六车案例没有在30 s内形成全队编队，更不存在随后10 s保持；3/12车也未形成，三组均没有发生编队换道且速度恢复为false。不得据此声称交通效率、通行能力或能耗收益；研究阶段6/7/8继续关闭。本实施计划中的Task 6完成不等于研究阶段6开放。
- 下一研究入口仍在阶段5：只读分析固定包中`unique_less_populated_adjacent`请求、局部后排判断与既有安全守卫的逐车逐拍分布，解释为什么最终0次换道；若需要改变if/else顺序、局部范围或安全可行性处理，必须另行预登记并保留本次3/6/12负结果，不得引入通信、真实ID优先权、全局车辆数、全局槽位、候选评分器或障碍车。

## 2026-09-15 17:00 +08:00：Phase5G 最终复审整改与一次性证据复核

### 前置、范围与五项整改

- 本单元先重读本检查点、最终复审整改计划、README、实际代码和Git状态；旧 `simple_final`、锚定包、重放和所有失败日志均只读。本轮没有改变无通信局部if/else动作、规则次序、数值参数或既有扫掠安全接受条件；没有通信、真实ID优先权、全局车辆列表/数量、全局槽位、中心分配、候选评分器、障碍车、背景车或脚本慢车。
- 文档验收RED的计划原命令使用单个OR正则，因旧文档已有 `SHOW_GUI=False` 而意外exit 0：`D:\yanjiu1\keyan1\results\operations\20260915T062932166796Z_review-e-doc-marker-red_9857ddb8`。没有把它伪称为RED；改用“每个文件逐个要求每个marker”的断言后确实exit 1：`D:\yanjiu1\keyan1\results\operations\20260915T063001635483Z_review-e-doc-marker-red-corrected_0ce0db7f`，README缺7项，本检查点除 `SHOW_GUI=False` 外缺6项。
- Task A（无损守卫诊断）：提交 `29051ef` 修改 `variants/phase5g_pure_formation/noa/controller.py`、`tests/test_simple_formation_controller.py`、`tests/test_simple_formation_harness.py`，分离 `longitudinal_guard` 与 `lane_guard`，兼容公开 `guard` 指向当前动作守卫，动作和记忆不变。RED `D:\yanjiu1\keyan1\results\operations\20260915T004115356849Z_review-a-guard-red_46f2a591` exit 1；最终simple与Phase5G日志 `D:\yanjiu1\keyan1\results\operations\20260915T004242961572Z_review-a-current-tests_f88175d9`、`D:\yanjiu1\keyan1\results\operations\20260915T004334525468Z_review-a-phase5g-regression_f05ebb33` 均exit 0。旧重放相对路径尝试 `D:\yanjiu1\keyan1\results\operations\20260915T004428570129Z_review-a-old-snapshot-replay_8de8b658` exit 1原样保留；字面绝对路径重试 `D:\yanjiu1\keyan1\results\operations\20260915T004502317486Z_review-a-old-snapshot-replay-absolute_f112c884` exit 0。
- Task B（直接入口与安全建档）：提交 `993998e`、`d562f12`、`3f1653a`、`b5934cc`、`193536a`、`37f4d37`，修改范围限于 `demo/sumo_gui.py`、`tests/test_runrun_demo.py`、`variants/phase5g_pure_formation/experiments/phase5g.py` 和 `tests/test_simple_formation_harness.py`。45 s输入的预算公式在3/6/12车分别给出198/306/`522 s`；检查模式只读，正常生成只在已验证的variant results或系统Temp范围内排他创建暂存/结果。硬链接RED `D:\yanjiu1\keyan1\results\operations\20260915T021225533135Z_taskb_staging_hardlink_red_3387d75e` exit 1，GREEN `D:\yanjiu1\keyan1\results\operations\20260915T021417712496Z_taskb_staging_hardlink_green_c904501b` exit 0；最终simple/Phase5G为 `D:\yanjiu1\keyan1\results\operations\20260915T021548830660Z_taskb_staging_simple_all_f842b4aa` 与 `D:\yanjiu1\keyan1\results\operations\20260915T021548998154Z_taskb_staging_phase5g_all_b3f117a9`，均exit 0；检查日志 `D:\yanjiu1\keyan1\results\operations\20260915T015920860372Z_taskb_harden_runrun_check_06016a68` exit 0。
- Task C（流式求值与身份绑定）：提交 `9e6a65e`、`2f0a75c`、`a3ab69a`，修改 `experiments/phase5g.py`、`phase5g_replay.py`、`phase5.py`、`phase4_audit.py` 与 `tests/test_simple_formation_harness.py`。生成后处理和重放按行扫描，保存失败物理前缀；每次重新扫描前后都验证轨迹身份，重放固定第一次验证的设备/文件身份与摘要。冻结身份RED `D:\yanjiu1\keyan1\results\operations\20260915T040108232785Z_review-c-freeze-identity-red2_daa496c5` exit 1，GREEN `D:\yanjiu1\keyan1\results\operations\20260915T040242637484Z_review-c-freeze-identity-green_680fb3fa` exit 0；最终simple、Phase5G、根专项日志 `D:\yanjiu1\keyan1\results\operations\20260915T040502594619Z_review-c-freeze-simple-all_7cb0bbde`、`D:\yanjiu1\keyan1\results\operations\20260915T040629678798Z_review-c-freeze-phase5g-all_1ec73dac`、`D:\yanjiu1\keyan1\results\operations\20260915T040743857216Z_review-c-freeze-root_d36d9f37` 均exit 0。
- Task D（可运行Git闭包）：提交 `6af693a`、`4171067`、`ddb3d1c`、`ce66252`、`6ad5681`。`6af693a` 首次按审计新增76个精确运行/测试闭包文件，首次闭包日志为 `D:\yanjiu1\keyan1\results\operations\20260915T045501380221Z_review-d-closure-audit-final2_fd340055`，baseline为 `D:\yanjiu1\keyan1\results\operations\20260915T045527404332Z_review-d-baseline-green-commit_93912d25`，均exit 0。后续只修复空工具模板便携发现、系统Temp长路径与fixture scratch；整改后的最终闭包为96个文件，精确列表在 `D:\yanjiu1\keyan1\results\operations\20260915T061117194742Z_review-d2-final3-closure-audit_75fb2807`，exit 0，不含results、tmp、PDF、旧variant或无关历史。最终提交态archive check/simple/Phase5G为 `D:\yanjiu1\keyan1\results\operations\20260915T061549659958Z_review-d-spec-6ad5681-archive-check_e3287ac3`、`D:\yanjiu1\keyan1\results\operations\20260915T061615733387Z_review-d-spec-6ad5681-archive-simple-all_11a6ac71`、`D:\yanjiu1\keyan1\results\operations\20260915T061758838899Z_review-d-spec-6ad5681-archive-phase5g-all_87eb1278`；纯archive baseline/check/simple/Phase5G为 `D:\yanjiu1\keyan1\results\operations\20260915T062043209546Z_review-d-spec-6ad5681-pure-archive-baseline_3bc1f2ce`、`D:\yanjiu1\keyan1\results\operations\20260915T062100313759Z_review-d-spec-6ad5681-pure-archive-check_4f444d1a`、`D:\yanjiu1\keyan1\results\operations\20260915T062157699793Z_review-d-spec-6ad5681-pure-archive-simple-all_4cef3bbf`、`D:\yanjiu1\keyan1\results\operations\20260915T062322119333Z_review-d-spec-6ad5681-pure-archive-phase5g-all_205ae67d`，全部exit 0。
- Task E回归发现根 `configs/tools.json` 已在 `4171067` 改为空便携模板，而根 `research/common.py` 仍直接读取空值，TraCI落到site-packages；这是changed-path缺陷，不归类为继承失败。TDD RED `D:\yanjiu1\keyan1\results\operations\20260915T063919068362Z_review-e-root-sumo-discovery-red_a734d489` exit 1后，提交 `9dbb3af` 只新增/跟踪 `research/common.py` 与 `tests/test_root_tool_discovery.py`，实现严格实际origin下的 `SUMO_HOME`→配置→PATH发现。临时加入原用户未跟踪测试文件的3段已迁入新文件并删除，原文件其余字节未纳入提交；提交前staging精确只有这两个文件。隔离GREEN `D:\yanjiu1\keyan1\results\operations\20260915T064319829444Z_review-e-root-sumo-discovery-isolated-green_dbfb6dd4` 为3/3、exit 0。
- 整改计划文字命令修正提交为 `6b23bf0`。截至文档提交前，本轮整改代码提交完整序列为：`29051ef`；`993998e d562f12 3f1653a b5934cc`；`9e6a65e 2f0a75c a3ab69a`；`193536a 37f4d37`；`6af693a 4171067 ddb3d1c ce66252 6ad5681`；`9dbb3af`。上述改动均为本地提交，未push到GitHub远端。

### 最终工程验证

- fresh完整回归：编译 `D:\yanjiu1\keyan1\results\operations\20260915T063038691791Z_review-e-compile_c6968997` exit 0；simple 90/90、0 skip `D:\yanjiu1\keyan1\results\operations\20260915T063047928512Z_review-e-simple-all_d1ab6c64` exit 0；Phase5G 101/101、0 skip `D:\yanjiu1\keyan1\results\operations\20260915T063245634168Z_review-e-phase5g-all_6985ebf9` exit 0；根demo 75/75、0 skip `D:\yanjiu1\keyan1\results\operations\20260915T063358991331Z_review-e-root-demo_cd6293b2` exit 0。
- 根全回归第一次 `D:\yanjiu1\keyan1\results\operations\20260915T063445038019Z_review-e-root-regression_db729b97` 跑296项，因错误TraCI来源为6 failure/6 error、exit 1。实现环境修复后的第一次299项 `D:\yanjiu1\keyan1\results\operations\20260915T064032062518Z_review-e-root-regression-after-sumo-fix_5f788ce9` 又因新测试泄漏临时 `SUMO_HOME` 为3 failure/3 error、exit 1；修复测试隔离后，`D:\yanjiu1\keyan1\results\operations\20260915T064347194380Z_review-e-root-regression-sumo-green_09bfdbb5` 为299/299、0 skip、exit 0。两个失败均保留，且在开始一次性科学证据前已闭合。
- 开始证据前核对不存在 `review-e-final-*` 操作目录、不存在 `simple_final_review` 新结果且无相关Python/SUMO进程。随后在同一PowerShell会话严格按3→6→12→精确六车重放顺序执行，任一步失败即停止；四步全部exit 0，没有按科学结果重试/挑选。独立审计 `D:\yanjiu1\keyan1\results\operations\20260915T090022969141Z_review-e-final-summary-audit_6fd94680` exit 0，确认基址中除 `.phase5g-trust` 外恰好3个运行目录，四个操作标签各恰好1个。
- `python runrun.py --check` 直接日志 `D:\yanjiu1\keyan1\results\operations\20260915T070343175313Z_review-e-runrun-check_30f050a0` exit 0；原子目录名/大小/mtime前后比较 `D:\yanjiu1\keyan1\results\operations\20260915T070358941330Z_review-e-runrun-zero-write_115db1c6` exit 0，确认根demo、variant `simple_gui_sources` 和 `simple_final_review` 全部 `zero-write`。
- 编辑器直接运行/调试契约用内存补丁设 `SHOW_GUI=False`、12车、seed 1、10 m/s、45 s，没有编辑默认值。日志 `D:\yanjiu1\keyan1\results\operations\20260915T070439280777Z_review-e-runrun-debug-fixture_f2f56ede` exit 0，断言subprocess timeout为 `522 s`，真实加载器接受本轮新建的12 actor、451 frame可信轨迹（SHA-256 `c7850bdc99ca590a435b91c520e5ec643a5f9c4fdf15e7c36cb761a3de2878ee`）。该检查明确使用mock subprocess与系统Temp夹具，只验证入口/返回校验，不属于 `simple_final_review` 科学证据，也没有第四个12车科学运行。

### 一次性科学证据与精确重放

- 3车操作 `D:\yanjiu1\keyan1\results\operations\20260915T064713640738Z_review-e-final-3_ae7b68ff` exit 0/37.532 s；字面运行路径 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final_review\20260915T064713884072Z_ee92fc0e`。
- 6车操作 `D:\yanjiu1\keyan1\results\operations\20260915T064751407078Z_review-e-final-6_9ec891c3` exit 0/138.000 s；字面运行路径 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final_review\20260915T064751667560Z_e3a1b27f`。
- 12车操作 `D:\yanjiu1\keyan1\results\operations\20260915T065009559786Z_review-e-final-12_6b5b15ec` exit 0/426.391 s；字面运行路径 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final_review\20260915T065009813717Z_832d9ca2`。
- 精确六车操作 `D:\yanjiu1\keyan1\results\operations\20260915T065716122076Z_review-e-final-6-replay_df32dcd1` exit 0/136.797 s；字面重放路径 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\replays\20260915T065716450367Z_8a58643e`。其source就是上述字面六车路径，`passed=true`、`semantic_replay_passed=true`、`source_validation_passed=true`、`errors=[]`、450区间/27000车辆子步/最大数值误差0；因源科学失败，`variant_acceptance_passed=false`。
- 三组固定输入均为seed 1、10 m/s、45 s，完整执行、工程外层通过、碰撞0、几何true、舒适true。3/6/12车分别：全队形成false/false/false，形成时间与保持时间全部null，完成换道0/0/0，编队换道0/0/0，最终车道计数 `[1,1,1]`/`[3,2,1]`/`[4,4,4]`，最低速度8.375438347096939/9.496692509585099/8.085958821063635 m/s，速度恢复false/false/false。3车与12车为探索规模，科学门槛不适用；登记六车的30 s形成加10 s保持门槛适用且false。
- 因此科学验收仍为false：没有良好编队、没有形成保持、没有换道、没有速度恢复。工程完成和重放一致不能改写成形成成功，也不能声称交通效率、通行能力或能耗收益；阶段6/7/8继续关闭。旧 `simple_final` 三组同样的负结果、旧重放和所有早期失败证据均未删除、重封或回写。

### 守卫审计、真实内存与限制

- 六车真实trace的逐行流式审计为 `D:\yanjiu1\keyan1\results\operations\20260915T070109830747Z_review-e-final-guard-audit_717c1287`，exit 0。450物理行/2700 actor decisions；公开 `guard` 非空2250、空450：`lane_change/false/neighbor_reachable_occupancy` 451，`longitudinal/false/neighbor_reachable_occupancy` 1342，`longitudinal/true/conditional_swept_prediction_clear` 457。`lane_guard` 非空451、空2249，全部为换道拒绝；`longitudinal_guard` 非空2250、空450，其中拒绝1792、安全458。
- 每个非空 `guard`、`lane_guard`、`longitudinal_guard` 都完整包含 `safe`、`reason`、`at_s`、`checked_s` 键，没有缺字段；`checked_s` 对应2250/451/2250项均非null。`at_s` 键对应2250/451/2250项均存在，非null分别1793/451/1792；安全结果允许值为null。全部451个lane `safety_rejected` 行的公开 `guard` 都等于被拒 `lane_guard`，不再错误暴露较早的安全纵向守卫，不匹配为0。
- 真实 `tracemalloc` 生成后处理测量直接调用真实12车、343.890316 MiB trace的 `evaluate_trace`；`D:\yanjiu1\keyan1\results\operations\20260915T073116628550Z_review-e-memory-real12-generation-field-fix_8324950c` exit 0/141.062 s，峰值11,868,398 bytes = 11.318586 MiB，低于 `64 MiB`。真实重放测量直接调用真实六车、110.655587 MiB trace的 `replay_variant(require_manifest=True)`，不写重放包；`D:\yanjiu1\keyan1\results\operations\20260915T083538368435Z_review-e-memory-real6-replay_dc5b6161` exit 0/1243.297 s，峰值5,631,568 bytes = 5.370682 MiB，低于 `64 MiB`，450区间/27000子步/误差0。两者都是真实trace、真实调用的观测峰值，没有把小夹具或缩放推断冒充测量。
- 内存负证据保留：组合12车测量 `D:\yanjiu1\keyan1\results\operations\20260915T070624180450Z_review-e-memory-real12_e2fe2b95` 在1200 s timeout、exit 124；首个12车generation-only helper因读取错误字段名 `whole_cohort_formed` 而在完成真实计算后exit 1：`D:\yanjiu1\keyan1\results\operations\20260915T072806185134Z_review-e-memory-real12-generation_ce5cf1a2`；修正为 `whole_cohort_formation_success` 后才得到上述有效峰值。真实12车整包重放 `D:\yanjiu1\keyan1\results\operations\20260915T073423780774Z_review-e-memory-real12-replay_a357da16` 在3600 s timeout、exit 124且无测量输出，所以**没有12车重放峰值结论**；有效重放峰值只适用于字面六车源，不能据此外推12车。
- 当前行为限制完全保留：有限局部观测、本车私有记忆、每车最多一次编队换道、唯一较少相邻车道与既有安全守卫；守卫拒绝统计是解释性证据，不授权放宽安全或按结果调参。下一步若继续阶段5，应预登记最简单的局部if/else规则分析，并保留本次一次性负结果。

## 2026-09-23 D 盘工作区的分层编队与窗口仿真

- 按用户指定，在 `D:\yanjiu1\keyan1` 集成 Phase5G 分层跟驰、换道及三车道直接观测实现。工作区的 `phase01` 先快进至 `phase5g-local-tail` 提交，再应用该分支未提交的分层规则补丁。原有未跟踪的 `test_phase5_detection.py` 与分支文件重名，原件保存在 `tmp\phase5g_premerge_untracked_test_phase5_detection.py`。没有清理其他历史未跟踪资料。
- `runrun.py --check` 在 D 盘解析出本目录的 Phase5G 入口与 SUMO GUI。Phase5G 专项 143 项测试通过，日志为 `results\operations\20260923T091013607270Z_d-drive-layered-phase5g-suite_59adec27`。根目录窗口入口 84 项测试通过，日志为 `results\operations\20260923T092243615718Z_d-drive-runrun-after-roundoff_2f45404c`。
- 首次真实窗口运行在加载第 4 帧时因浮点时间 `0.30000000000000004` 与 `0.3` 的字典精确比较失败，失败源与日志保留。`demo/sumo_gui.py` 仅将前帧时间归一为已通过 `1e-9` 容差检查的当前初始时间，其他车辆状态字段仍精确比较；新增回归测试先失败后通过。先前失败的 901 帧源现可加载。
- 修复后从 `D:\yanjiu1\keyan1` 直接运行 `python -B runrun.py`，SUMO 1.27.1 窗口打开，12 车、seed 1、90 s 轨迹播放至结束提示；为用户查看保留窗口。新生成源在 `variants\phase5g_pure_formation\results\phase5g\simple_gui_sources\20260923T092319151715Z_1cdf6a95`。
- 本次新源的 `validation.json` 显示 `engineering_passed=true`，12 车演示的科学门槛不适用；记录了 2 次编队换道、0 次碰撞，但 `whole_cohort_formation_success=false`、形成/保持时间为 null、`speed_recovered=false`。因此窗口中能观察到规则产生的局部跟驰与换道，不能称整队交错编队已经形成。
- D 盘宽泛 `run.py test` 发现了 348 个额外历史未跟踪测试，619 项中有 2 个失败、34 个错误；失败日志为 `results\operations\20260923T090224436649Z_d-drive-layered-variant-regression_7a01f431`。本次不能据此称全量测试通过。窗口播放证明入口可用，不改变此前阶段五科学验收未通过、阶段六至八尚未开放的判断。
- 用户再次运行 `runrun.py` 后没有立即看到窗口。现场核查发现入口先同步生成并校验 12 车、90 s 的约 399 MiB 轨迹，成功的这次从 Python 启动到 SUMO 窗口出现约 69 s；重复点击产生了并发生成，其中一次以 `KeyboardInterrupt` 结束，原失败证据保留。已在生成前增加明确提示，说明 SUMO 窗口会在生成校验后打开；相应测试先 RED 后 GREEN，根目录入口 85 项测试通过，日志为 `results\operations\20260923T093946982388Z_d-drive-runrun-status-message_7687319b`。现场 SUMO 进程 PID 114324 在同一桌面会话中，窗口可见且未最小化。

## 2026-09-23 19:40 +08:00：按用户要求恢复到“运行 runrun 未见 SUMO 窗口”时的代码

- 用户明确要求先恢复到该消息时的代码，故停止继续修改分层和换道算法。已核对 `simple_gui_sources/20260923T092319151715Z_1cdf6a95` 与 `20260923T093711449166Z_fca8d545` 两份当时源码快照：9 个需回退的 Phase5G 文件 SHA-256 逐项相同。已从后一快照恢复 `experiments/phase5g.py`、`noa/controller.py`、`noa/road.py`、`noa/simple_formation.py`、`perception/road.py`、`run.py`、`test_layered_formation.py`、`test_simple_formation_controller.py`、`test_simple_formation_harness.py`；恢复后 9 项哈希再次逐项一致。
- 根入口恢复当时默认配置：12 车、seed 1、90 s、GUI true；移除后来增加的生成等待提示及其测试，保留此前修复的轨迹帧时间浮点舍入兼容。`runrun.py` 当前与 Git HEAD 相同；不删除任何历史运行目录或失败证据。
- 回退前的诊断证据保留：12 车/seed 1/90 s 的后续试验 `simple_gui_sources/20260923T111947228100Z_9cffc112` 只出现 1 次编队换道；30 车/seed 6/180 s 的 `simple_gui_sources/20260923T111944383314Z_9648b97e` 虽写满 1800 条轨迹，但最终验收停在 `running`、没有完成锚，不能视作完整通过。后者轨迹中没有换道发起。两者均不是当前恢复版的验收结果。
- 恢复版的本轮核验：Phase5G 规则 16/16、控制器 48/48、根入口测试 84/84、`python -B runrun.py --check` 通过，`git diff --check` exit 0。未重复运行 12 车真实 GUI；此前当时源码生成的 `20260923T092319151715Z_1cdf6a95` 已有窗口播放及 2 次编队换道的固定证据。
- 下一入口：用户若要求继续修复长时运行，需从恢复版重新诊断 20 车/200 s 的三车道到两车道路段切换及隐藏的完成锚错误；不要把回退后的代码说成已修复该故障。

## 2026-09-23 20:13 +08:00：恢复版保存至 GitHub

- 用户指定新仓库 `https://github.com/32780542/yanjiu1`。该仓库推送前无分支；本地原 `origin` 仍指向 `32780542/biyesheji1`，另加 `yanjiu1` 远端并将恢复版提交 `0a87512d0e778bf5a6491ac4cc2dffe37e51c051` 推送到新仓库 `main`，远端 SHA 已核对一致。仅提交已有 Git 闭包中 13 个变更文件，未提交未跟踪的实验结果、PDF 或历史资料。
- 提交前重新运行：根 `test_runrun_demo.py` 84/84、Git 闭包测试 8/8、Phase5G simple 专项 143/143、`runrun.py --check` 与 `git diff --cached --check` 均通过。专项完整日志为 `results/operations/20260923T120013849416Z_github-save-restored-phase5g-tests_bd8e0bf0`。
- Git CLI 直连 GitHub 曾超时；通过 Windows 系统代理 `127.0.0.1:10997` 重试后正常推送。下一入口为 GitHub `main` 的上述恢复版；未重新宣称长时 20 车案例或科学形成门槛通过。

## 2026-09-28：当前恢复版研究接续 README

- 应用户要求，将根 `README.md` 改写成新聊天窗口的自包含入口。它按当前被 Git 跟踪的代码、2026-09-23 分层规格、本检查点及当日真实 12 车 `simple_gui_sources/20260923T092319151715Z_1cdf6a95` 证据区分研究目标、实际方法、模块、运行、测试、失败和下一步；没有修改控制算法，也没有重跑科学案例或 GUI。
- README 明确当前 12 车案例为 2 次完成的编队换道、0 次碰撞、`whole_cohort_formation_success=false`、`speed_recovered=false`，并说明动态 GUI 演示的外层生成成功不等于科学门槛通过。大量本地历史资料仍未跟踪、未上传；阶段五科学验收未通过，阶段 6–8 继续关闭。
- 本次新鲜验证：`python -B runrun.py --check` exit 0；根入口测试 84/84、Git 闭包测试 8/8，均 exit 0；Phase5G simple 专项 143/143、0 failure/error，日志 `results/operations/20260928T124921411356Z_readme-phase5g-special_7d955346` 中 `result.json` 为 exit 0。README 的 29 个 Markdown 链接逐一核对，仓库内相对目标缺失数为 0；`git diff --check` exit 0。
- 下一入口仍是 README 末尾的“新聊天窗口如何接续”：从此恢复版诊断形成失败及长时完成锚问题，保留所有旧证据；不要把文档整理或专项测试解释成科学成功。

## 2026-09-28：新阶段五工作，局部补位规则单元

- 用户新要求：取消最后发车后 30 s 形成与 10 s 保持门槛；GUI 与模型逐步同步；检查规则；按 2/3/4 车道、交错 15 m 扩展评价。本次计划见 `docs/superpowers/plans/2026-09-28-phase5g-live-formation-evaluation.md`。工作区为 `D:\yanjiu1\keyan1`，未改旧结果包。
- 局部规则 RED：`python -m unittest tests.test_layered_formation -v` 共 9 项，2 项失败：偏好目标被占用时停等；独立车群距离 60 m 时被错误纳入局部层窗。
- 实现：目标车道已占用时从本车可见的前层空位顺序选择；层窗仅纳入以 50 m 连续纵向间距连接的本车车群。GREEN：同命令 9/9 通过。此单元尚未做全套回归，不能据此宣称整队形成成功。
- 下一入口：检查换道执行期的纵向减速优先级；再移除时限验收、做 GUI 流式化及车道数实验。
- 纵向规则 RED：活动编队换道、无即时危险时，普通 NOA 的 `-1.0 m/s²` 盖过编队请求 `2.0 m/s²`。改为应用编队请求；即时危险与路端停车分支未移除。相应控制器测试先失败后通过，分层与控制器合跑 58/58 通过。旧“相隔 60 m 的独立车辆重置稳定计时”测试按物理车群边界更新。
- 下一入口：移除动态演示验收中的 30 s/10 s 时限和生成等待；上述 58 项尚不足以证明长时仿真可形成全队编队。
- 动态演示不再追加 30 s/10 s 成功门槛；终点需比最后计划发车多一个 0.1 s 控制步，保证末车至少进入一次计算。检测器在动态模式只需连续 1 s 有序几何，另列 `formation_success`、`safety_passed`、`recording_valid`；历史检测器缺省参数仍保留以支持旧证据解释。根配置聚焦测试与检测器 22/22 通过。
- GUI 流式化：根进程先打开 SUMO-GUI，隔离子进程写完一条物理记录后输出该帧并等待父进程 ACK，父进程每帧仅调用一次 `simulationStep`。根入口 86/86 测试通过；旧生成优先的加载器测试改为直接调用冻结源加载器。
- 真实短时窗口验证：`results/operations/20260928T134119644919Z_phase5g-live-gui-smoke_ded783b0` exit 0，3 车/15 s/seed 1，GUI记录 `results/demo_runs/20260928T134119891400Z_simple_formation_4c0ca1fe` 为 completed、151 帧、最终 15.0 s、0 GUI 碰撞与传送；封存源 `variants/phase5g_pure_formation/results/phase5g/simple_gui_sources/20260928T134123747143Z_55916217` 被严格加载。测试使用不等待关闭的临时内存配置，不改变 `runrun.py` 默认值。
- Phase5G harness 第一次完整运行 79 项/283.875 s 有 1 failure、1 error，日志 `results/operations/20260928T133118005580Z_phase5g-duration-harness_00bda0fa`，原因是 `duration_s=0.2` 等于末车发车时刻却被本轮最初的宽松边界接受，mock 跑进序列化。已将最短时长修为末车发车后一个控制步；两个受影响聚焦测试随后通过，尚待完整 harness 重跑。
- 下一入口：统一参数化车道数和恒定车道路网，实施 2/3/4 车道与车流量矩阵；完善动态指标与 README，保留全部失败包。

## 2026-09-28：2/3/4 车道、参数实验与评价指标

- 用户确认 2、3、4 车道以及相邻车道交错 15 m。实际控制器按最高车道向下 `0,15,0,15 m` 两相位交错；同车道默认 30 m。将局部层窗、补位、同车道跟驰与局部头车参考推广到 2/3/4 车道；2/4 车道真实短时 `run_variant` 和 4 车道封存演示测试通过。恒定车道网络由 `variants/phase5g_pure_formation/scenarios/formation/build_networks.py` 生成，3/4 车道真实 GUI 短时逐帧运行并封存，日志分别为 `results/operations/20260928T135740585221Z_phase5g-straight3-gui-smoke_bec8487e`、`results/operations/20260928T135759856672Z_phase5g-straight4-gui-smoke_9f183ea9`。
- 当前运行前固定 39 例矩阵：`L=2/3/4` × `q=300/600/900 veh/h/lane` × seeds `1/2/3` 共 27 例；3 车道、`q=600` 下目标速度 `8/12 m/s` 和同车道层距 `24/36 m` 各 3 seeds 共 12 例。每条车道 4 车，末车计划发车后观察 90 s；90 s 不是控制器期限。协议与指标解释写入 `docs/phase5g_evaluation_2026-09-28.md`，每例独立封存、失败不覆盖。
- 初次启动矩阵因模块路径错误留下两份立即失败的操作日志 `results/operations/20260928T140030541932Z_phase5g-formation-matrix_ab368a43` 和 `results/operations/20260928T140048828264Z_phase5g-formation-matrix_a01b7fe5`。修正命令路径后，完整矩阵操作为 `results/operations/20260928T140117595076Z_phase5g-formation-matrix_322367b4`，批次根为 `variants/phase5g_pure_formation/results/phase5g/formation_matrix/20260928T140117912348Z_f67527d1`；本段记录时仍在运行。前几例显示低需求率有未形成案例，也有较高需求率案例形成，不能在全矩阵结束前下适用性结论。
- 文档将旧设计规格中的 30 s/10 s 和三车道限定标记为被用户修订覆盖，README 改为 GUI 先开、逐拍计算/显示、新的成功定义与 2/3/4 车道配置。2026-09-28 22:12 +08:00 新鲜受影响测试：variant 87/87，根 GUI 入口 88/88，均 exit 0；`runrun.py --check` 解析默认恒定三车道路网并通过。这里是专项验证，不替代待重跑的完整 harness 和矩阵结论。

## 2026-09-28：收敛诊断、两条纵向规则及观察窗修订

- 首个 39 例矩阵先用末车后 90 s 观察；已完成 14 例，其中 2 车道 `q=300` 的 3 个种子均未形成，`q=900` 的 3 个种子均形成，3 车道低/中流量部分未形成，案例均完整封存。逐帧分析确认，50 m 外的可见独立车群被局部头车忽略，且同一 50 m 链式连通车群内、距自车约 96 m 的同车道前车也被错误的 90 m 换道层窗截断。因评估窗口过短且代码缺规则，主动终止原矩阵；14 个完整结果和第 15 例未完成前缀原样保留。操作 `results/operations/20260928T140117595076Z_phase5g-formation-matrix_322367b4` 返回失败；绝不能当成 39 例全矩阵。
- 新增纵向规则一：局部头车在本车群内无前方参考、却可直接看到另一独立车群时，按最近可见前车做纵向接近；两群未进入 50 m 连通关系之前，不把前群纳入分层占位。新规则测试先 RED（`upper_leader` 而非接近）后 GREEN。
- 新增纵向规则二：同一可见连通车群内的同车道前车即使距本车 95 m，也参与纵向跟驰；90 m 仍只截断换道层窗。新规则测试先 RED（错误当头车）后 GREEN。规则 suite 19/19 通过。旧规则 suite 另发现一项三车道私有记忆测试仍把 4 号车道当合法性边界，按本轮 2/3/4 车道输入合同修为 4 号非法。
- 两规则之后，末车后 90 s 的 2/3/4 车道探针安全但未整队形成；延长观察后，真实封存结果为：2 车道 `q=300` seed1 于 165.3 s 形成、末车后 123.3 s、换道 1 次、最终 `[4,4]`；3 车道 `q=600` seed1 于 164.1 s 形成、末车后 142.1 s、换道 4 次、最终 `[4,4,4]`；4 车道 `q=300` seed1 于 189.0 s 形成、末车后 144.0 s、换道 4 次、最终 `[4,4,4,4]`；4 车道 `q=600` seed1 于 170.1 s 形成、末车后 147.6 s、换道 4 次、最终 `[4,4,4,4]`。四例碰撞 0、安全检测通过，均为单 seed 探针，不代替全矩阵。源在 `variants/phase5g_pure_formation/results/phase5g/approach_probes/extended-*`，操作在 `results/operations/20260928T143935*` 和 `20260928T144333*`。
- 原 `runrun.py` 默认 12 车、seed1、三车道、2.5–4.0 s 随机间隔，延长到 230 s 后于 158.6 s 首次形成，末车 35.5 s 发车、4 次换道、最终 `[4,4,4]`、无碰撞；操作 `results/operations/20260928T144612612798Z_extended-default-l3_e1124360`。因此入口默认显示时长改为 200 s，而科学成功不设期限。正式矩阵的统一观察窗改为末车后 200 s，39 例保持不变；三工作进程短案例测试 2/2 完成、均封存。评价协议见 `docs/phase5g_evaluation_2026-09-28.md`。
- 完整 harness 重跑第一次 81 项仅 1 failure，是 CLI 新参数令旧 mock 精确调用预期不一致；已修测试并单项通过。第二次在运行中编辑了被封存的规则/测试源码，导致两项源哈希或语义重放失败；日志分别为 `results/operations/20260928T141427521989Z_phase5g-final-harness_d66a55ec`、`results/operations/20260928T142318165946Z_phase5g-harness-after-cli-test_ad3234a4`。它们是执行过程污染留下的失败证据；最终版必须在源码冻结后重新跑完整 harness，不得宣称已经通过。


## 2026-10-26：纯规则代码可读性与存储整理

- 本轮以 D:\yanjiu1\keyan1 的实际工作版本为基准。先核查旧进程、GitHub main、操作日志和磁盘占用；没有仍运行的矩阵进程。当前旧 Phase5G 原始结果目录已不在。第一轮完整矩阵的历史文档记录为 38/39 形成；修复后第二轮日志仅记录到 12 例，缺少结束汇总，按这个状态接续。
- 固定重构前行为：600 个局部场景；2/3/4 车道分别 200/450/600 拍的闭环记录。原始摘要采集操作为 results/operations/20261026T123934958210Z_readability-baseline_64287be1；重构后等价验证为 results/operations/20261026T124727613299Z_readability-equivalence_11d9b90f，两项测试通过，完整动作、记忆、诊断和轨迹摘要全部相同。
- 从 noa/controller.py 提取基础纵向计算到 noa/driving.py，提取当前编队执行到 noa/simple_controller.py；公共入口保留原调用和诊断。simple_formation.py 将同车道最近前车改为早返回，合并重复分支，统一代码格式。SOURCE_FILES 增加新模块，Git 运行闭包检查 8/8 通过。
- 独立复审确认迁移函数与原代码的运算 AST 一致。复审发现历史 test_phase5e_exact_endpoint.py 仍导入 _comfortable_speed，已恢复该兼容重导出；对应 3 项测试通过。
- 两处新轨迹 JSON 写入采用紧凑分隔符，字段和精度完整保留。历史 results 与 tmp 共约 6.8 GiB，经 NTFS 无损压缩后约占 2.2 GiB，节省约 4.6 GiB。最大 8 份历史轨迹及隔离记录全部符合原证据清单 SHA-256。当前 variant 的 results/tmp 设置压缩属性；.gitignore 明确排除生成物。临时工具与缓存删除被自动审批拦截，原目录保留。
- 验证：完整编队测试 150 项通过，操作 results/operations/20261026T125057632259Z_readability-formation-suite_adababef；GUI 与审计 91 项通过，操作 results/operations/20261026T125057628253Z_readability-gui-suite_f84155fa；多车道与检测专项 41 项通过。600 场景五次交错计时中位数为重构前 0.2205 s、重构后 0.2195 s。
- 实际 GUI 检查：三车、15 s、151 帧、碰撞与传送 0，操作 results/operations/20261026T130350482590Z_readability-live-gui_56a023b9；显示记录 results/demo_runs/20261026T130350776510Z_simple_formation_b596cf25；新封存源 variants/phase5g_pure_formation/results/phase5g/simple_gui_sources/20261026T130355497351Z_588469a3。
- 文档入口改为 docs/纯规则编队系统说明.md；配套 docs/纯规则系统方法索引.md 列出 419 个函数、类和显式类方法，docs/存储整理报告.md 记录空间和 GitHub 安排。README 已改为简明入口。
- 下一研究入口：沿新说明核对当前规则，在新批次中补齐修复版 39 例矩阵；代码整理本身以重构前后行为一致为验收。
- GitHub 同步完成：实现提交 `e9594f5` 已推送到 `https://github.com/32780542/yanjiu1` 的 `main`。同步包含之前保留在工作区的实时 GUI、多车道与实验协议修改，以及本轮重构、测试和说明；大轨迹与临时数据继续由实验目录管理。

## 2026-10-28：MATLAB 随机车流与编队评价实验

- 用户要求直接完成不同流量、2/3/4 车道和参数变化实验，并参考本机文献确立编队评价。计划为 `docs/superpowers/plans/2026-10-28-formation-validation.md`。MATLAB 实际生成段每 0.1 s 在三条车道分别独立判断 `rand<VGR`；有效 `Tflow=0.042` 对应每车道 1512 辆/h。
- 本轮固定 65 例：车道 2/3/4 × 每车道需求 252/756/1512 × seed1–5 共45例；三车道、756 辆/h 下目标速度8/12 m/s、同车道层距24/36 m，各5 seed，共20例。总车数4L，全部实际入场后继续观察200 s，实验直路10 km。
- 新增 `formation_study.py`：逐车道 Bernoulli 请求和 FIFO 入口等待，保存首事件原始时刻与完整请求/实际入场表。采用既有时距与静止间距入场，控制器规则不变。紧凑推进省去原记录器重复诊断树，保留完整0.1 s状态和0.01 s子步接触检查。
- 新增 `formation_metrics.py` 与 `docs/编队效果评价标准.md`。依据本机 Cai2019、ADEPT2024 等文献核对几何、速度、形成过程指标。复审发现缺车道时空配对被记为0误差，增加反例并修正为缺测；正式批次物理轨迹不受影响，最终离线复算采用修正指标并保留原结果。
- 新测试9项通过，包含请求确定性与期望流量、入口等待、推进完整状态/动作/记忆等价、精确队形、缺车道及实际入场时间戳。连同规则、控制、多车道和检测回归共106项通过，日志 `results/operations/20261027T170626369908Z_formation-study-regression_bc0f0272`。
- 65例运行根为 `variants/phase5g_pure_formation/results/formation_study/20261027T170127795643Z`。运行前协议已保存；83个实际源文件和配置摘要及一份共享源码zip已保存。此检查点时批次仍在运行，最终结论待完整汇总与逐例复算后补充。

### 本轮完整结果与验收

- 65/65例全部完成，57例形成、8例未形成，全部记录有效、检测安全通过、车体接触车辆对0。完整运行616.453s，操作日志 `results/operations/20261027T170127441019Z_formation-study-65_ac604571`。每车道252/756/1512辆/h的45个基准案例分别形成11/15、13/15、15/15；参数20例形成18/20。
- 从压缩物理轨迹独立复算65例，260个文件摘要全部通过。复算71.687s，操作 `results/operations/20261027T171158216856Z_formation-study-recompute_cb48a170`。4个终态占位不完整的几何总误差修正为缺测，旧运行结果及83文件源存档保留；所有形成、时间、记录、安全、车道数及目标速度偏差与原输出一致。
- 4个低流量未形成案例终态车群分离，最大空隙305.3–430.9m；3例连通车群占位不均；1例层距36m、seed5仍在位置和速度调整。57个已形成案例最差终态几何误差0.273542m、速差0.072817m/s、目标速度最大偏差0.072817m/s。
- 新增真实换道进行时的完整动作、记忆与物理状态等价测试。最初固定六车40s测试未产生换道，故主动断言失败；改用固定随机请求真实推进至开始换道，再冻结状态并比较原时钟/紧凑时钟60拍，测试通过。这是测试场景修正，未改车辆控制器。最终相关回归108/108通过：`results/operations/20261027T171128052927Z_formation-study-final-regression_b9c9c9d5`。
- 形成率、参数配对延迟和终态队形三张图均输出300DPI PNG与SVG并目视检查。独立复审确认结果数字、汇总、缺测处理、图轴和结论相符，无重要遗留问题。
- 报告为 `docs/编队多工况验证报告.md`，指标为 `docs/编队效果评价标准.md`；65例逐例表、13组汇总、协议、复算与未形成数据在 `docs/experiments/2026-10-28-formation`。整个原始批次54.17MiB。README与系统说明已接续至本轮完成状态。
- 发布前移除开发初期仅判断模块存在的重复测试，保留10项有实际行为断言的新测试；最终回归107/107通过，操作 `results/operations/20261027T172017896498Z_formation-study-publication-tests_45961e76`。核对运行前83项源摘要，只有离线几何缺测处理文件与执行存档不同，车辆控制、感知、积分和实验推进代码全部一致。便携结果与三张图合计约0.67MiB。
- 本轮实现、报告与便携数据已以 `995e543` 推送到 `https://github.com/32780542/yanjiu1` 的 `main`。直连第一次重置，改用本机系统代理 `127.0.0.1:10997` 后推送成功。本轮用户要求的两项任务全部完成；后续从多工况报告与评价标准接续。

## 2026-10-28：持续大交通流、交通效率与燃油

- 用户纠正上一轮研究单元，要求Cai2024式长时大交通流和效率、油耗。用户通过异步问题明确选择 MATLAB 当前恒定三车道直路作为主场景；论文为3→2瓶颈，两者已区分。计划 `docs/superpowers/plans/2026-10-28-continuous-traffic.md`，评价方法 `docs/持续交通流评价方法.md`。
- 固定54例：三车道每车道1250/1500/1750/2000辆/h、3seed、编队开/关共24例；2/4车道1500辆/h配对12例；目标速度24/32m/s配对12例；层距24/36m编队6例、复用对应基准。入口初速度28.8m/s，基准目标28.8m/s；1200m开放测量段，600s持续来车，之后继续队列和排空，终点上限2400s。
- 新增 `OpenTraffic` 支持空场、逐车道FIFO、出口插值与清理。采用原传感器/决策/运动模型，先校验世界快照，再用x±207m保守裁剪候选，精确可见性仍由原传感器判断。两组统一关闭额外旧主动超车，对照为常规跟驰和车道保持；编队跟驰与补位代码不变。
- 初次短测中旧off主动超车路径出现Python3.12.9原生访问冲突0xc0000005，Windows Event1000/1001与目录时间一致，未归因为内存或算法失败；旧目录 `variants/phase5g_pure_formation/results/continuous_traffic/20261028T025336934551Z` 保留。随后按预定比较目的明确跟驰/车道保持基线。
- 仅时距入场的高速短测出现接触，确认会把28.8m/s新车插到减速队列后方；入口补为同时满足原时距及含执行响应的制动距离，条件两组相同。修正短测 `20261028T030718880944Z` 每组81请求全部完成、0碰撞，逐拍与逐车燃油/里程累计相符。操作日志 `results/operations/20261028T030718441765Z_continuous-safe-entry-probe_8b4e28ef`。所有早期原始结果保留。
- 独立复审发现并修复出口后仍审计车体的伪碰撞，以及未排空却输出排空耗时0；均有RED→GREEN反例。新增 `models/fuel.py` 按SUMO1.27.1的HBEFA3/PC_G_EU4瞬时质量流率积分，47个平路官方工具参考点最大差0.005mg/s；证据 `tmp/emissions_audit_20261028T024248Z` 与已保存测试fixture。
- 正式54例操作：`results/operations/20261028T031206019800Z_continuous-54_3fbc863d`，原始根 `variants/phase5g_pure_formation/results/continuous_traffic/20261028T031206451914Z`，12workers、外部超时7200s。此段记录时仍运行；恢复时先检查该进程和results.jsonl，不能盲目重启。每例保存600s请求表、行程台账、0.1s全网统计、1s位置与接触事实，批次共享源码zip。
- 冻结前118项相关回归通过，操作 `results/operations/20261028T031037666570Z_continuous-freeze-tests_d2aeefa7`。后续仅补后处理工具与测试，不改已冻结仿真源码。汇总器 `summarize_traffic_flow.py` 独立核验台账、逐拍累计与30个配对请求表；图工具 `plot_traffic_flow.py` 输出效率、燃油和8张时空速度子图。最终结果和GitHub同步待整批结束后完成。

### 安全失效保留与剩余条件接续

- 实验框架与方法提交 `7a77e88` 已推送用户GitHub。新后处理与既有相关回归121项通过，操作 `results/operations/20261028T032548553028Z_continuous-postprocess-tests_cf968a0e`。
- 原批次两车道seed3编队例出现1次车体接触，首次36.2s；该例虽继续至排空，按安全失效保留且不计有效效率。两车道seed2在跑样本37s已出现重叠，继续积分后的稠密无效车群使计算开销持续上升。
- 增加“首次安全事件控制拍保存后停止”的记录规则；未来计划请求与真正入口队列分开。性能统计仍要求完整排空且0碰撞/驶出道路；失败、缺测和负改善均保留。未改变跟驰、换道、入口条件、车辆参数和积分运算。
- 在 `models/records.py` 用缓存attrgetter读取数值冻结dataclass，替代 `models/kinematic.py`、`perception/ideal.py` 中的astuple递归复制。1000随机完整积分摘要优化前后均为 `4aa4173e6fc44a7fece87b88c2c6bf8cafc2cfc179413182388189458b473103`。既有600局部场景、1250闭环完整记录摘要及相关114项测试通过，日志 `results/operations/20261028T040253517582Z_continuous-numeric-equivalence_dc1afc97`。
- 经命令行核对后仅停止本任务拥有的run_logged PID76528，Windows Job关闭清理其全部子进程。原目录和全部前缀只读保留。独立验证已封存的30例文件摘要（包括父结果流尚未来得及登记的1例），不按科学好坏挑选；其余24例在新目录同种子同参数重算。
- 接续操作 `results/operations/20261028T041744016334Z_continuous-remaining_17127841`，原始根 `variants/phase5g_pure_formation/results/continuous_traffic/20261028T041744709217Z`，16workers；集合索引 `variants/phase5g_pure_formation/results/continuous_collections/20261028T041744706859Z/collection.json`。接续首例L2 seed2在36.7s安全停止，计划502请求、实际释放/入场22、出场0、未来480，碰撞车辆对1。当前剩余条件仍运行。
- 汇总脚本支持 `--additional-root` 读取两批已封存证据，每个原定条件只出现一次，并核验参数和配对请求一致；旧结果只在导出时补齐兼容字段，原文件不改。源快照分别保留。最终公开结果、图表、README和发布待所有条件封存后完成。

### 持续交通流完整结果与验收

- 接续24/24条件全部结束，操作`results/operations/20261028T041744016334Z_continuous-remaining_17127841`退出0，3071.281s，Windows Job确认剩余进程0。集合目录已写`completed.json`。与原批次30封存条件合为54个唯一预定条件；53例排空，其中1例带接触；52例完整且安全，另2例两车道编队失效。无驶出道路，28/30性能配对有效。
- 三车道主实验24例全部排空且0接触。每车道1250/1500/1750/2000辆/h四组的系统时间配对减少分别84.28%/86.68%/83.96%/79.18%，g/km油耗减少15.27%/15.26%/13.58%/13.93%。统计以逐种子改善率的均值报告。四车道与参数变化的编队组各3/3安全排空；两车道seed2/3分别36.7/36.2s首次接触，未纳入有效改善率。
- 独立复算操作`results/operations/20261028T051140597862Z_continuous-final-recompute_c6a566f2`退出0，核验54例、41282条计划台账、324文件摘要、54例逐拍累计、30个同种子请求表。`verification.json`保留每例实际来源及两批源码zip摘要，旧目录没有覆盖修改。
- 封存到导出的合成端到端测试暴露后处理循环变量覆盖工况名的问题，已用`filename`分离并通过反例。先前两次日志命令因run_logged固定根目录而未找到variant模块，保留其失败日志；改为显式加入variant路径后16项持续流测试全部通过。最终相关回归124/124通过，操作`results/operations/20261028T045914787613Z_continuous-publication-regression_bcb4be47`，10.570s测试时间。
- 完整编队harness150/150通过，操作`results/operations/20261028T042759794464Z_continuous-formation-harness_99d965b5`。等价优化后的完整短测两模式与旧探针的滚动轨迹/动作摘要及全部逐车台账完全一致，操作`results/operations/20261028T043746460369Z_continuous-representative-equivalence_1c855e73`。
- 三组图（交通效率、燃油、8张时空速度子图）均输出300DPI PNG与SVG并目视核对，绘图操作`results/operations/20261028T051153159424Z_continuous-final-figures_de8ccdbf`。便携数据17文件约1MiB，含54例、18组、30配对、10配对组；原始gzip留在本机。
- 独立复审核对表格/CSV/JSON、配对有效性、早停未来请求与图表定义。唯一文字修正为明确速度统计粒度：四个需求组跨3seed均值32.76–33.02m/s；12个逐例32.73–33.06m/s。报告说明后车位置追赶允许高于28.8m/s巡航设定，效率图不等同几何形成判定。未把之前65有限车群形成结果混作持续流结论。
- 成果入口`docs/持续大交通流验证报告.md`、方法`docs/持续交通流评价方法.md`、数据`docs/experiments/2026-10-28-continuous-traffic`。README、系统说明、28项新增方法索引和计划已更新。任务所需运行、统计、图表与文档完成；下一研究入口为两车道高速持续流的接触原因与规则调整。
- 本轮成果提交`642949e`已推送到`https://github.com/32780542/yanjiu1`的`main`。独立最终复审确认CSV/JSON逐字段一致、配对和分组复算一致，图表与正文统计口径一致，无剩余需修改问题。此次要求的持续大交通流实验与效率、燃油评价全部完成。

### 常规组耗时的进一步审计

- 用户追问常规系统时间长的原因。核对原台账：1500辆/h/车道下平均入口等待246.014s、在网116.883s、系统362.897s，平均车速10.267m/s；2000下分别440.456/121.021/561.477s。系统时间的主要增量来自入口排队，路内跟驰本身也偏慢。
- 使用原off参数代入同速28.8m/s、零加速度、净距54.84m（3+1.8v）：`comfortable_speed`仅16.27176m/s，最坏制动所需净距73.272m，会继续要求制动。实际输入SHA与数值保存在便携数据的`baseline_diagnosis.json`。时距目标与额外停车约束在该速度下不一致，是慢行的具体代码原因。
- 确认两组纵向安全规则不相同：`controller.py`第131–133行在普通编队、无活动计划时将最坏制动距离紧急状态替换为当前净距/TTC判据；`simple_controller.py`再以位置跟踪请求替换常规纵向加速度。加上实际速度32.73–33.06m/s，79%–87%改善包含了控制规则与速度差异，不能作为编队排列本身的独立改善率。
- 本次补充报告、评价方法、README和系统说明的解释，保留所有原始结果与统计。未修改控制器、实验参数或重新运行。下一步若评价编队独立收益，先统一两组纵向安全与速度条件，再开展配对比较。

## 2026-10-28：基础NOA修正与直接编队评价（已完成）

- 用户明确要求基础NOA实际合理，不把常规车虚假制动和入口等待造成的差异当作编队优势；直接评价编队大小、稳定度等。新计划为`docs/superpowers/plans/2026-10-28-realistic-noa-and-platoon-metrics.md`。
- 已保留原CTH线性ACC（3m+1.8s、kp0.15、kv0.8），去掉运动前车的瞬间硬刹停车差及舒适停车罩。两模式共用`driving._lead_gaps/immediate_emergency/response_emergency`：统一前向车身、当前/投影切入候选，按当前净距、TTC、闭合速度含响应/jerk停车距离保护。静止前车舒适停车及物理终点停车保留。编队期望速度封顶共同巡航值，不再跟随前车速度逐层抬升。
- 入口为-300m物理上游段，本车道200m内最近前车匹配速度；两组在上游均用普通NOA。台账增加`inserted_s`，0m跨越时记`entered_s`，1200m记出口；燃油、里程和车辆时间只积分0至1200m。`mean_entry_wait_s`在v3为请求至源端放行等待，`mean_upstream_travel_s`为放行至0m运动时间，`mean_entry_delay_s`为两者合计，队列/上游运动车辆分别记录。
- 反例先失败：同速时距、速度封顶及共享闭合保护（`20261028T092402247455Z_realistic-noa-red-guard_e55b74b7`）；上游入场三项（`20261028T092808975731Z_upstream-entry-red_537d76b0`）；源端等待分解（`20261028T092950350760Z_upstream-time-split-red_a3bcb911`）。均已GREEN。
- 独立复审发现常规仅最近车与编队逐车保护的候选分叉，补同中心重叠反例RED（`20261028T093954045164Z_common-body-candidates-red_b259f9b7`），现已统一全部候选。一次整套回归发生原生0xc0000005，日志`20261028T094045043625Z_realistic-noa-common-guards_be6c7896`保留；带faulthandler独立复跑对应阻塞并道例通过（`20261028T094239205812Z_noa-blocked-merge-diagnosis_c5de8f07`），整套125项随后通过（`20261028T094327976892Z_realistic-noa-frozen-regression_7bac9b30`）。未归因为算法碰撞或内存。
- 四例60s q1250/2000、seed1、on/off探针全部完成、0接触，根`variants/phase5g_pure_formation/results/realistic_noa_probes/20261028T093040310873Z`，操作`results/operations/20261028T093039794876Z_realistic-noa-flow-probe_cfbff5c8`。常规在网41.673s、均速28.795m/s；编队41.765/41.686s。源端等待两组相同。直路不再有原先的数量级优势。
- 新离线`experiments/platoon_metrics.py`在variant内，只读1s物理位置；6类主指标为平均/最大规模、参与率、几何RMS、队内速度RMS、5s关系稳定参与率、内部断裂率。18项合成测试通过，实际运行路径并入上述125项验收。图组件不重叠，D24/36与offset15独立；边界退出/记录结束删失，不作内部断裂。定义和Su2017/Cai2019/ADEPT2024等原文依据见`docs/编队规模与稳定度评价.md`。
- 新54例正式批次已启动并冻结仿真源码：操作`results/operations/20261028T094516935685Z_realistic-noa-platoon-54_2c48d5d9`，进程由run_logged私有Job管理，16workers，7200s。原始根`variants/phase5g_pure_formation/results/continuous_traffic_v3/20261028T094517387582Z`。旧54例及其源码、统计保持原样。不得盲目重启；先检查该操作日志和封存案例。
- 完整simple formation harness也在运行，标签`realistic-formation-harness`。此检查点尚未完成新54例、复算、结果报告与GitHub发布，继续至全部完成。

### 边界低速插入与物理图反例修正后的最终冻结

- 长时检查发现源端还会按短空隙/时距反算很低插入速度：前车−290m、28.8m/s时，新车竟以1.5m/s插在−300m。已新增RED（`results/operations/20261028T095419489882Z_source-short-gap-red_2af270ab`），删除该反算，只匹配实际前车速度，空隙不足则请求留源端，路内车辆照常前进。
- 因该边界规则影响实际流量，已按命令行核对并停止本任务run_logged supervisor PID77136，私有Job清理全部子进程。先尝试PID65424时识别到它是受管子进程，身份检查拒绝，未操作；原目录`20261028T094517387582Z`无封存案例，保留所有中间前缀，不与最终批次混合。
- 再次四例60s探针根`variants/phase5g_pure_formation/results/realistic_noa_probes/20261028T095510918986Z`，操作`results/operations/20261028T095510460089Z_moving-source-flow-probe_45467f89`，85s完成，全部0接触、排空。NOA在网41.6667s；编队41.8122/41.6974s。源端等待两组相同，q1250/2000分别1.8746/7.8189s。
- 评价器出现“缺少同道中间层却被跨道对角边串成大队”的反例。三道各3车、同道距60m而D30，原图误记9车。RED为`results/operations/20261028T095903361055Z_platoon-diagonal-false-positive-red_e4d0b921`。已改为跨道只连同层相位，跨层必须真实同道D邻接支撑；反例为3个双车局部队，D24/30/36的完整三层队仍连通。阈值未改，两组一致使用。独立复审确认定义合理，协议明确同层局部小队不等于完整多层大队。
- 最终冻结138项通过，操作`results/operations/20261028T095941356480Z_noa-platoon-publication-freeze_ae290a56`。完整150项首次为149通过、1项仍断言旧超巡航追赶+2；已改为新封顶0预期。旧操作`20261028T094527404302Z_realistic-formation-harness_f269a65e`保留，完整套件正在新源码下重跑。
- **当前唯一正式批次**：`results/operations/20261028T100104659374Z_noa-platoon-final-54_ea4eff30`，原始根`variants/phase5g_pure_formation/results/continuous_traffic_v3/20261028T100105100032Z`，16workers、7200s。当前exec会话20978。完整harness操作`results/operations/20261028T100115306188Z_noa-platoon-final-harness_7a595fd8`，exec会话58958。源代码已冻结；最终结果、报告与GitHub发布尚待完成。
- 新绘图入口`variants/phase5g_pure_formation/plot_noa_platoon.py`位于冻结运行文件夹之外，输出直路对照、规模/稳定参与、几何/速度/内部断裂三组PNG/SVG。README与系统说明已将旧大幅改善率标为历史实现，当前规则见`docs/基础NOA与入口修正规则.md`。
- 修正与指标单元已提交`5025592`并推送用户GitHub main。完整150项最终套件通过，操作`results/operations/20261028T100115306188Z_noa-platoon-final-harness_7a595fd8`，测试592.109s，外部操作退出0。当前仍需完成54条件与正式结果发布；不能把本段测试通过当作矩阵已经结束。
- 主三车道24例已全部封存、完整排空且0接触/越界。仅NOA四组在网行程均41.6667s；编队四组均值41.845/41.759/41.733/41.708s。平均局部规模2.30/2.21/2.287/2.471，参与率22.23%/19.77%/32.44%/10.60%。仅NOA参与率7.95%/7.72%/20.48%/0.53%。六个两车道工况也全部完成、0接触，包括旧失败seed2/3。全54例仍未结束。
- 在保留原稳定参与率的同时，离线汇总派生`platoon_stability_rate=stable_vehicle_seconds/platoon_vehicle_seconds`，作为“已编队成员稳定时间占比”，与内部断裂并列。无编队暴露为空，单例恒等式Pstable=P×H。2项手算测试RED/GREEN分别`20261028T103933595793Z_conditional-stability-red_6013b9ab`、`20261028T104004449115Z_conditional-stability-green_245578a8`；不改冻结识别、轨迹或控制。主四组H为82.79%/85.26%/86.60%/85.10%，仅NOA约87.9%，说明规模/参与增加不等同关系更稳定。
- 三张主场景图的真实预览在`tmp/noa_platoon_preview_20261028T104425`，已目视检查。占比图给均值和3个种子实际点（0–100%坐标），其他面板给均值±样本SD，避免将超出物理域的对称SD误差条读成负参与率。正式导出将重新从全部54例生成。
- 已准备`tmp/write_noa_platoon_report.py`和`tmp/noa_platoon_data_readme.md`。54例结束后先运行`summarize_traffic_flow.py 原始根 docs/experiments/2026-10-28-noa-platoon`（输出目录必须尚不存在），再运行`plot_noa_platoon.py`，最后执行该报告生成脚本并复制数据README。生成后必须补写基于实际数字的结论、独立复审和GitHub同步；此时不要结束任务。

### 最终54例结果、直接指标与验收

- 正式54/54全部完成、全部请求排空、接触车辆对0、驶出道路0；源端队列、上游及测量段终点余车均0。操作`results/operations/20261028T100104659374Z_noa-platoon-final-54_ea4eff30`退出0、4161.719s，Job确认active_processes0。原始根`variants/phase5g_pure_formation/results/continuous_traffic_v3/20261028T100105100032Z`，97个运行前源码/配置摘要与当前实际文件逐项相同。
- 独立复算`results/operations/20261028T111159547289Z_noa-platoon-final-recompute_30a46ba4`退出0，11.875s；54例、378文件摘要、41282条计划台账、54例逐拍累计、30个配对请求表均通过；直接编队指标从物理样本重算。导出`docs/experiments/2026-10-28-noa-platoon`，含54例、18组、30配对、10配对组。
- 每道1250/1500/1750/2000主场景：仅NOA在网均41.6667s；编队41.845/41.759/41.733/41.708s。平均局部规模2.30/2.21/2.29/2.47，观察最大7/7/8/4辆；参与率22.23%/19.77%/32.44%/10.60%。组织规模和参与增加，直路通行略慢，稳定性未全面改善。
- 两车道全部6例、四车道全部6例及所有参数变化均安全排空。当前平均队伍仍主要是2辆左右的局部车组；D24/36和速度24/32各3个种子结果完整列在新报告。旧两车道失败seed2/3重跑已安全完成，旧失败原始证据继续保留。
- 统计审计发现2000需求的仅NOA有两个安全种子没有车组；参与率0保留在3例平均中，条件规模/几何/H只含1个有组样本。已新增每指标`_n`、图中n=1，缺测不填0，避免将1例条件均值写成3例。新增样本数反例RED/GREEN为`20261028T105804245161Z_undefined-platoon-count-red_f8ac1f06`、`20261028T105805828737Z_undefined-platoon-count-green_3cea3829`。
- 最终相关141项通过：`results/operations/20261028T110109799593Z_noa-platoon-final-statistics-tests_98e37d7a`，29.801s测试；完整链路150项已在`20261028T100115306188Z_noa-platoon-final-harness_7a595fd8`通过。四份CSV/JSON与各组/配对/条件稳定H由独立复审核对一致。
- 三组300DPI PNG/SVG已目视核对，操作`results/operations/20261028T111256403661Z_noa-platoon-final-figures_23836c37`。复审修正了图说明中的H名称和误差条样本口径；图按各模式非空安全观测分别统计，未强称统一配对3样本。18个便携成果文件共1166526字节，原始gzip只存本机结果目录，源码版本交Git管理。
- 报告`docs/直路NOA与编队规模稳定度报告.md`，规则`docs/基础NOA与入口修正规则.md`，指标与文献`docs/编队规模与稳定度评价.md`。README、系统说明、方法索引和计划均更新。基础NOA修正与直接编队评价任务已完成，下一研究重点为持续流中的大队增长和关系保持，以及独立的车道减少/合流实验。
- GitHub发布：控制器与边界修正提交`5025592`，完整54例成果、指标统计、图表与研究说明提交`df6e576`，均已推送`https://github.com/32780542/yanjiu1`的`main`。发布前再次核对54例排空、CSV/JSON行数、后处理源码摘要及源端等待+上游运动+在网时间分解，全部一致；原始压缩数据留本机，便携成果随仓库保存。

### 仅NOA误计与持续大流量形成失效：口径纠正与规则诊断

- 用户指出仅NOA被记为编队且大流量规模异常小。核对原始开关：12例仅NOA的formation/simple/lane-change均关闭，实际换道0。问题在局部评价器只要求至少两车几何连通，未检查完整车道占位及多层结构；上下并排、中道缺位也被算作二车组。原“平均规模2.21–2.47、最大8”撤回其作为完整编队规模成果的表述，改称局部几何匹配，原数字保留。
- 从三车道主实验24例positions逐帧复算：仅NOA共17892个匹配分量观测（17851个二车、41个三车），全部单层，同车道30m边为0；11105个仅上下双车。数量是分量×帧，包含重复实体。既有完整队形函数检查50m物理车群，仅NOA2帧、编队规则171帧合格，全部3车单层，多层合格样本0；单帧结果不作为持续形成次数。
- 原始trips实际补位换道：编队组q1250的3个seed为0/1/2，其余q1500/1750/2000均0。因此高流量1750/2000的6例没有一次补位，不能将局部匹配增加解释为形成规则已适应大流量。
- 具体失效链：源端1.8s时距和0.1s放行形成最小/各例中位同道距60.48m；目标D30。上一轮把期望速度封顶共同巡航28.8，使同速后车即使有30.48m位置误差，加速度也为0，无法追近；层窗又要求窗口所有同道距与相位已稳定，才允许补位，形成僵局。600s是车流生成长度，单车只有约41.7s在网时间。
- 数值例子直接调用真实choose_formation_target/formation_acceleration/layered_window/choose_layered_fill：独立前群能选到但加速度0；加跨道桥接车后层窗不一致、layer_not_stable、加速度仍0。例子保存在docs/experiments/2026-10-28-platoon-diagnosis/rule_examples.json。
- 离线复查初次在写结果时因重复name参数失败，操作`20261028T115919849327Z_noa-group-structure-audit_fc2cf64e`保留；修正后`20261028T115937940891Z_noa-group-structure-audit_5511003a`完成。含数值复现的最终操作`20261028T120414211349Z_noa-group-structure-audit-final_90419dd0`退出0、9.735s；公开脚本复算`20261028T120924578198Z_geometry-audit-public-reproduction_878a150b`退出0、9.625s，与两份公开JSON逐字节一致。图标签重生成`20261028T121126699366Z_geometry-figure-final-layout_47197563`退出0、2.125s，并目视核对。
- 新报告`docs/仅NOA误计与大流量小车组诊断.md`，24例结构、规则例子、摘要与复现脚本在`docs/experiments/2026-10-28-platoon-diagnosis`。README、系统说明、原结果报告、指标与基础规则说明均标注当前真实进展，图表改称几何匹配。控制器、入口、阈值、原始轨迹和数值均未改。本轮验证为24例离线结构复算及规则函数复现。
- 当前接续：完整持续流形成尚未实现。下一规则单元须先解决可实现的纵向接近方式与过严的补位前置条件，再按完整物理车群的车道占位、层距、相位和连续保持验证。不要根据局部匹配分量宣称形成成功，也不要按是否启用控制强制改写几何测量结果。

## 2026-10-29：1250流量形成修复与3→2变换设计，等待用户审核

- 用户要求按MATLAB机制取消额外入口等限制，先解决1250流量下形成，再设计分布式3→2变换，并明确要求先交方案、审核后才实施。后续补充已确认巡航28.8m/s、最高33.3m/s；其他方案内容尚未批准。本轮没有修改仿真、入口或控制器代码，也没有启动新性能实验。
- 已重新读取MATLAB实际主链：mainmain逐车道Bernoulli请求并直接TraCI添加；最终VGR0.042实际为1512，1250应取0.0347222；车型CAV_ICV的tau0.2/minGap1.5/长4/加速5/减速10/紧急30。8m目标车道净空是MATLAB自身条件，保留；额外1.8s入口门并非MATLAB机制。
- 核实MATLAB由SUMO真实推进，当前Python自行车模型+SUMO显示与它不同。方案推荐SUMO负责发车和运动、Python逐车决策，将这一工程选择明确交用户审核，不悄悄切换。SUMO原生插入有空间检查和实际发车延迟，不另叠加Python入口队列；时长、道路、物理与最高速度在各组一致。
- 已提取并目视核对Cai2024 PDF第3/4页：纸面巡航28.8、最高33.3、结构周期5s、1000m处3→2、总长1200m；1250为其开始考察收益的流量。其统一目标与0-1分配不直接移植到分布式控制。MATLAB切换触发1000−2.5×28.8×5=640m作为首版准备起点，动态车辆视野仍前200/后100，道路预告两组共用。
- 方案`docs/superpowers/specs/2026-10-29-flow1250-distributed-lane-drop-design.md`：恢复巡航以上追赶，取消整个层窗先稳定与全标签不变的门；局部中道向较空保留车道让位，终止车道选择当前物理F/R间隙，R依据同一物理候选独立开隙，依次相邻换道，恢复两车道30m/15m。90m局部计数用于分担负荷，不使用全局编号、目标表、其他车记忆或通信预约。
- 六车示意为三道各2辆→两道各3辆，2辆A并入中道、1辆B向另一个保留车道让位，其余只纵向调整。手算脚本验证：期望600s请求625辆、触发640m、车辆守恒、3次相邻换道、同道30m/跨道15m；此为设计几何核对，不是轨迹仿真通过。
- 审核后先做真实入口与三车道形成，再做少车变换，最后1250/600s/seeds1–5三组比较：纯NOA、编队+普通合流、编队+本变换。正常NOA保留提前必要合流与择道；效率收益从同种子结果检验。完整连续层的规模/参与、变换完成和上下游稳定分开评价。
- 当前下一入口是用户审核上述设计，尤其SUMO真实推进和中道让位方案。未批准前不进入实施计划或代码修改；已确认的28.8/33.3无需再次询问。

## 2026-10-29：用户批准实施，真实SUMO与局部方法迭代中

- 用户要求先云端保存，随后实施、检验、改进，最后比较纯NOA/分布式编队/Cai全局；未成功时持续至北京时间10月29日08:00。开始时本地为00:47，有约7小时。不要因中间失败提前结束，也不能把测试通过当成研究成功。
- 已将304个原有未跟踪源码/配置/研究文档（约3.4MB）完整备份提交`26a3de5`并推main，云端标签`backup/pre-lane-drop-20261029`。未跟踪PDF与MagicMock测试残留未上传。仍在D:\yanjiu1\keyan1、phase01就地修改；没有另建worktree。
- 实施计划`docs/superpowers/plans/2026-10-29-native-lane-drop-implementation.md`。新主规则`noa/native_rules.py`，真实运行器`experiments/native_sumo.py`与`run_native_flow.py`，完整层`experiments/complete_layers.py`，集中式适配参考`experiments/global_reference.py`，均在variant目录。现有runrun尚未切换，等方法验证后集成。
- 独立任务完成真实SUMO入口/3→2几何、每车私有track、全局策略隔离、油耗/车辆账本；完整层识别与24项手算测试；Cai原图与MATLAB依赖核对；全局匈牙利参考15项测试。Python312新增scipy1.18.1；安装日志`results/operations/20261028T171412469766Z_global-reference-scipy-install_22a03487`。
- Cai原文PDF5/6页仅热图Fig.5和截图Fig.6，1250/100%CAV瓶颈采样约29±2m/s；没有可直接三方案排名的平均行程或油耗数字，0%CAV是HDV。MATLAB R2024a可启动，但SNOPT合法查询报Invalid SNOPT Mex File，不能声称原样复现。报告`docs/Cai2024全局方案对照依据.md`与6点/依赖/摘要在`docs/experiments/2026-10-29-cai-reference`。
- 首版六车`native_flow/20261028T170554015549Z_lane_drop_transform_s1_1fbe10`全排空且0接触，出现2:4而非3:3。方法更新详见`docs/2026-10-29-编队变换方法更新.md`，包括目标道纵向跟踪、每车负荷一次、物理锚点延续、已有安全空间不等待他车计划、恢复上游补位与平衡约束、相位参考保持、增益0.6/0.5。
- 独立复审发现speedFactor1未关闭默认speedDev，实际有.88；现已统一speedDev0并核对实际全1。发现1s轨迹混叠连续保持，现记录0.1s；索引翻转是横移中点，另加真实完成事件。首次unsafe停机；status改drained/time_limit/unsafe/error；未排空时整体均值为空、子集另列。复审记录`docs/2026-10-29-native-integration-review.md`。运行器17项GREEN操作`20261028T173144463683Z_native-physical-evidence-green_ea0355d7`。
- 旧v1四探针操作`20261028T172109321812Z_native-method-v1-four-probes_c768bfef`，变换流出现接触，纯NOA92/93；全部保留。v2六探针`20261028T173343741373Z_native-method-v2-six-probes_9c270cbc`：六车3:3但下游未恢复，100s直路未完整多层；NOA和编队普通合流92/93、time_limit，transform93/93且0接触，global93/93且0接触。不能据未完成NOA比较收益。
- NOA残车v2_00319停x1000，preparing的x<drop误清合流义务。独立诊断`native_noa_stall_diagnostic/20261028T174115416269Z_lane_drop_noa_s1_ab735e`及零速能力探针确认有空间时native可换，是规则错误。已改实际lane2未退出则继续必要合流；几何门15m目标/8m必要条件与更快位置收敛改善实际可执行性。
- v3六探针操作`20261028T175402646999Z_native-method-v3-six-probes_1af57a19`部分完成后因2道恢复仍观察到后方lane2导致_fill数组越界而失败，保留所有前缀。其六车已真实恢复6车两道3层（下游参与约58.85%），100s直路首次完整6车（上游参与约1.87%），NOA93/93、0接触、41.7688s。后续transform案例错误不是安全/性能失败统计，已新增反例并修恢复成员/物理障碍分离。
- 最新规则反例22项左右全部GREEN，联合运行器/完整层/全局参考套件已通过；最新边界RED/GREEN为`20261028T175834922772Z_native-boundary-observation-red_23e01385`/`20261028T175848512106Z_native-boundary-observation-green_1bfd14f5`。原13项功能RED、闭合/实际运动、相位/进度等日志均独立保留。
- v4至v8六探针均已结束，汇总在tmp/native_probe_v4至v8_summary.json。v4下游连续流无完整编队；v5移动参考改善到6.75%但长期追远群；v6引入50m连通的局部单元但高道参考让前方低道车减速，行程57.44s。v7改实际投影前沿后93/93安全排空，行程41.286s对NOA41.917s，上游参与3.96%、下游27.20%，峰值9/10。v8允许保留道在准备区实际补位，下游29.30%、行程41.815s，仍需多种子检验。小六车各版已能两道3层恢复，不等同连续流成功。
- 新增规则反例30项、集中式15项GREEN；最近RED/GREEN为native-frontier-phase、native-early-restoration系列。当前形成参考不再存memory.reference，以实车前沿为共同相位；跟随实测参考速度+.6位置误差。50m仅分形成单元，不缩小安全视野。方法更新文档已同步当前规则。
- **当前运行**：v8三种子300s探针`tmp/native_explore_v8.py`，run_logged标签native-v8-three-seed-300s，timeout1200；输出根native_explore_v8，逐case汇总tmp/native_explore_v8_summary.json。另有独立只读方法诊断、GUI入口实现和配对汇总工具三个子任务，不改主规则。
- **下一步**：依据多种子探针和真实轨迹诊断更新方法；冻结源码后做1250/600s/seeds1–5矩阵、独立复算、图表/人类说明与runrun GUI集成，测试/独立审查后推GitHub。尚未进行正式600s矩阵，不能终止为完成。用户只在成功或08:00截止后才接收最终结果。

### 03:38继续点（覆盖上面的运行状态）

- v8三种子300s已结束。种子1在168.9s追尾v2_01470→v2_01435，118/260完成，不能参与性能均值；种子2/3虽安全仍不合格。精确原生重现`native_v8_collision_diagnostic/20261028T190251461371Z_lane_drop_transform_s1_341f5a`。安全公式原来只用相对闭合速度，现已改同10m/s²前后车停止位置与0.2s响应；真实40步反例RED/GREEN，v9与v10种子1/300均260安全排空。
- 独立诊断给出149.59→302.27m补位目标丢失、640m虚拟合并名次导致727.81→600.08m急刹、45次刚完成就反向换道。证据tmp/local_method_diagnosis_report.json、local_method_replay_report.json和tests/fixtures/native_slot_jump.json（原生两帧）。
- 当前规则Memory保存lane_target、gap(F/R)、phase(近处实车track,相对整层差k)；无邻车意图。跟随实际对应层而非永久原始偏移。v11原始偏移法失败（49.40s/down0.13%），v12精确相位改善（41.50s/down13.46%），当前v13继续验证。相位按当前2/3道及实测横向位置连续变化；自由领航自身参考0偏移；物理间隙边界与安全1s预测占用分开。
- 规格复审确认并修复自由领航正offset自追、已换道边界不失效、过640仍执行未开始的lane2补位、两侧争同空位各自窗口不同而同时发令。改为空位中心固定窗口。规则43项左右+global15项GREEN；最近日志native-relative-layer-phase、native-local-corridor-priority、native-current-gap-boundary。
- GUI子单元已完成：根runrun.py默认q1250/600s/transform/3→2实时SUMO；--check、--headless、--no-wait、--gui-delay-ms。Python显式仅GUI逐帧延时，600m视角跟前车最终固定600–1200m，交互结束Enter后封存。109项受影响GREEN；真实45sGUI450帧、0接触/teleport（刻意time_limit，非性能通过）。证据tmp/native_gui_evidence_20261029.json。runner已冻结；含complete_layers快照及Python/SciPy版本。
- 新配对汇总模块experiments/native_comparison.py及15测试已完成；支持manifest路径数组/{cases:paths}，输出runs/pairs/run_means/pair_means/summary；重核源快照与随机需求，失败组不平均，g/km油耗真实账本重算，真实完成事件合流率。39项含完整层GREEN，旧v6真实解析通过。使用python -B -S -m experiments.native_comparison manifest --output新目录（variant cwd）。
- **当前运行**：v13六探针重试（首次straight案例因current/predicted边界不一致TypeError中断已修），run_logged native-method-v13-six-probes-retry，exec39284，timeout900。先查，不重复。成功后tmp/native_probe_v13_summary.json，随后已准备tmp/native_explore_v13.py（三种子300s）尚未启动。距离08:00约4h20；正式600s矩阵仍未跑。

### 04:33继续点（覆盖前面的运行状态）

- v13三种子300均safe/drained但transform TT42.16/68.16/80.41s（NOA约41.8），未成功。独立原生重放证实283.7s负层差循环：A持久phase要求A=B+15，B普通frontier要求B=A−45，两车均0速但A实际同道前车60m外在行驶，A safe cap33.3。51引用环、35有负有效差；2992动作精确重放0差异。报告tmp/native_v13_reference_audit_report.json、native_v13_reference_memory_report.json。
- 因此删除了失败的Memory.phase/_remember_cell/_cell_following与frontier计数跟驰，改成现行实际同道最近前车D30；头车固定巡航28.8±2加其他车道实际头车raw相位误差均值（不取模、不复制跨道速度），实际y连续相位。仍用50m连通单元，短单元可接近组件外可见前车（30.8上限），完整单元巡航。速度引用前车链按实际x单向，不再有跨道低速反馈环。
- v14取模/最近邻头车会让首行错一层，六车仅4车闭合；v15改真正各道头车、未取模相位后六车恢复6车，但300s TT40.97/53.50/58.26，仍未成功。
- v15诊断证明未横移就追目标道F−30会追到R位置：63.4s实际F/R31.897m，本车在中点前1.463m、v11.587，原request0而cap22.29；中点目标request11.580。180596动作重放0差异。因此v16加入_join_speed，Memory.gap保存真实F/R，横移前/中保持中点，居中后入列D30，joining物理收敛后才自由补位。无时间冷却。v16 seed3/300 improved49.89仍不足。
- v17允许ending后排已有独立_clear间隙时并入，不必等head；v18/_mandatory_priority针对同走廊的0→1非必要补位给准备区lane2必要合流让行，解决六车19.9s C2(x638)与A2(x640.3)争同gap额外两次LC；v18六车下游peak6、参与54.07%、TT39.383，100s流TT41.108 vsNOA41.820。v19连未开始的pending自由变道也让行，三种子300 TT41.02/42.00/47.31，仍未成功。
- 控制对照：v19 straight seed3/300 TT39.936（262实际LC，无<1速度或>=2s停车），drop47.31（513LC、39段长停）；不能把所有问题归因于自由补位或pending时长。真正几何bug：held gap仅检查F/R可见，未检查E仍在区间；88.5s E684.284已越过F660.209/R643.585，却带651.897目标零速横移（cap33.3），当前位置实际间隙目标676.579可请求7.875。drop961越界拍/30次越界横移接受；straight仅102拍approach且无这种停车。报告tmp/native_v19_gap_audit_report.json、native_v19_first_delay_report.json。
- **现行v20**：_merge_target local held有效条件增加R.x<=E.x<=F.x，越界重新绑定当前间隙；NOA normal_overtake也使用同一必要合流优先过滤，与pending取消一致。最近RED/GREEN native-current-gap-reselection、native-common-overtake-priority等，规则43+physical_following11+global15左右GREEN。原始失败快照都保留，不用测试通过替代性能。
- **当前运行**：v20三种子300s，tmp/native_explore_v20.py，run_logged native-v20-three-seed-300s；exec26849；日志results/operations/20261028T202911635602Z_native-v20-three-seed-300s_065c9059；输出根native_explore_v20、逐case汇总tmp/native_explore_v20_summary.json。源代码在此批次内冻结，不在多case Python进程运行时编辑被快照文件，以免缓存与磁盘快照不一致。
- 正式600s矩阵仍未跑，截止08:00还有约3.5h。若本批次好：精简/格式整理（临时black已装在tmp/native_formatter，工作后可仅清此临时工具目录）、完整相关回归、少车最终验收、冻结30case配对矩阵（4×5 lane_drop + NOA/transform×5 straight3）、native_comparison独立复算、图表/报告、复审、push Github。若不好继续查原生证据，不加任意时间门或恶化NOA。
- docs/原生SUMO编队变换系统说明.md 已独立写成6345汉字，覆盖现行v20全规则/方法/运行/指标，无虚假效果数；只待最终结果链接。README仍描述旧12车/10m/s/200s及旧模型，需要最终重写入口/结构/进展。Cai报告与GUI已完成。black安装操作20261028T202938650511Z_native-python-formatter-install_47a2b152。

### 05:55继续点（覆盖前面的运行状态）

- 正式A40已完成：1250/600s、5种子、4模式×直路/3→2，24,464车次全部安全排空、碰撞/teleport均0。原始根native_validation_20261029T0452；运行日志20261028T205326163579Z_native-final-600s-forty-cases_00845490，1352.547s。当前源码native_rules κ=.3，实际前车与头车raw相位，不再持久phase。
- 成果包docs/experiments/2026-10-29-native-lane-drop：protocol/manifest、comparison_verified、recovery、functional_six和figures。40例独立审计、60配对全有效。A3→2 TT均值NOA41.8786、formation40.9714、transform40.8392、global适配41.2986s；transform较NOA快2.48%，但fuel88.5104对61.9175g/km（+42.95%），不能称节油。
- A下游transform完整多层参与22.52%、平均5.35辆、各种子峰值均10.8辆；原上游已形成243辆中210辆在调整后恢复两道多层（86.42%），普通合流47/243。所有车辆1308/3058观察到两道恢复。六车最终真实3次横移、6/6恢复，平均恢复13.78s。NOA未测到确认完整多层。
- 比较器P2已补轨迹覆盖审计（空/截断/丢帧不可入均值），恢复时间独立模块15反例，完整variant150项GREEN，root8项GREEN；最终规格/质量复审无未处理控制阻碍。图已生成，最新样式在tmp/native_plot_style_refine_20261029_equal_v2，正式旧A图保留。
- 由于A油耗代价大，继续简洁方法检验。只限正加速度1m/s²导致3个transform种子未排空，2m/s²seed3行程73.52s，拒绝。记录tmp/native_acceleration_probe_summary.json，原始native_acceleration_probe保留。
- 当前引擎native_sumo为候选B：常规速度请求对称±2m/s²，安全速度下限直接优先，不延迟制动；四模式共同执行，物理SUMO仍5/10/30。不是A源码。单seed3/300已310/310安全排空，TT40.9635、fuel76.0119；对应A同seed TT40.8294、fuel89.717。需结构复核及其他种子。
- 当前运行B五探针tmp/native_symmetric_probe.py，exec78340，标签native-symmetric-speed-five-controls，输出根native_symmetric_speed_probe、摘要tmp/native_symmetric_probe_summary.json。禁止运行中改六个被快照源码，先查日志再继续。
- A引擎恢复来源：A40 manifest第一case/source/experiments/native_sumo.py，sha27e2de0941e019d4fb548c6e2b5f2427a0b4e1ee415d16ccd832d53902438e31。当前B增加test_native_actuation4项，若拒绝需同步恢复或适配。controller Asha bdbd68bc5191bf9c50a61c27b863c21f973fd666e25f2abbc6a28831cfa2a0e8。
- 现行说明docs/原生SUMO编队变换系统说明.md和README已写好A接口，最终报告由独立任务按A起草，可能B正式结果后替换。所有本轮新源码/文档/结果尚未提交（仅修改前备份26a3de5已云端）。最终须冻结选定版本、重跑必要正式40（若选B）、独立复算、最终图目检、补全报告/说明/计划、完整测试及push yanjiu1 HEAD:main。
- 北京时间05:55，距用户08:00限时约2小时。不得停止在未完成交付；不得把Cai适配参考写成原论文重现或原文精确TT/油耗。

### 06:12继续点：C40冻结运行，代码已再次云端保存

- 新common对称±2候选B的transform三种子300均安全排空，TT40.304/40.533/40.964s、fuel71.819/74.162/76.012g/km；NOA42.078、global41.300正常。但普通formation seed3为61.70s，不能忽略。
- 真实物理帧和冻结规则重放指出普通_merge_target会排除不足30m的当前间隙，并跨多个gap跳目标。RED反例E718/F730/R706同速、_clear真，旧target745而非中点718；实际重放见tmp/native_symB_formation_findings.json，重构非全动作精确重现，原日志无actions，不能把重放推算称原生指令。
- 当前C删除普通跨gap搜索分支：NOA/formation/transform必要合流统一实际当前位置F/R、有效区间保持和中点；_merge_target不再有local参数。93相关检查GREEN，C六车6/6安全、3次实际LC、TT39.317、下游参与60.1%。formationseed3/300改善41.165，但seed2仍56.276，真实保留。NOAseed3/300为42.153。
- C正式40已启动：exec18263，操作results/operations/20261028T220241899295Z_native-current-gap-final-forty-cases_f58e6ba7，timeout3600；root variants/phase5g_pure_formation/results/native_current_gap_validation_20261029T0604。4模式×5种子×lane_drop/straight3，600s需求/max900。请查已有进程日志，不重复启动。当前刚完成前5例，ordinary seed2运行中，队列使其比主模式更慢。
- C协议及六车在docs/experiments/2026-10-29-native-current-gap。六源码运行期间冻结：native_rules f8dea7b717b0d3292d29e888285951810b90140cf0932ede29616a1fe7a3c5b5；native_sumo d6aff77f818f87fbc212e2f3104c80f8447fcccd2d755996b06138149a9a2132。不得在多case Python进程内改这些被快照文件。
- 新执行参数已补入comparison的case/result一致性和配对哈希（4反例RED/GREEN）；比较器现sha b39dd54cadbefa28116ea46f7135f56863b1b0356f5702bfdb07832df897804c。C全variant159项GREEN（20261028T220555135158Z_native-current-gap-final-all-tests_c07b644a），root窗口9项GREEN（d8339dcd）。增量独立规格9项+150属性通过（20261028T220744935319Z_native-c-spec-incremental_ec124144），无新阻碍。
- 当前代码21个文件已提交1112697并push yanjiu1 HEAD:main成功，云端main从26a3de5前进。README/说明/报告/成果尚未提交，待C结果独立复算。
- A40报告已另存docs/experiments/2026-10-29-native-lane-drop/A40方法对照.md（4423字），主报告docs/2026-10-29-原生编队变换验证报告.md已改成C骨架（2850字）。不得把A数值对应C源码。现行系统说明已更新统一gap、common±2与恢复定义。A40完整源/原始/旧图仍保留。
- 接续：等待C40→验证全部源码快照/状态并导出manifest/run_status→新版comparison独立复算+recovery→生成新版图（使用C sixcase）/目检→按实测填主报告，A敏感性和Cai原图分栏→文档计划/README/检查点同步→小成果与文档push。可为Git生成compact recovery summary（不含重复per_vehicle数组）和CSV，原大文件只读保留。已有A旧完整复算后可用最新版comparison另新输出一次，但不要覆盖旧尝试。

### 06:33继续点：D速度差阻尼候选已安装，D40运行中

- C40已全部结束，40/40 safe/drained，外层退出0。transform seed2/600为50.110s，对应NOA42.195s，拒绝C为最终方法；即使全部排空也不能声称通行成功。C完整证据由complete_layer_metrics独立复算comparison/recovery/compact，原始不删。
- 恢复MATLAB原物理执行5/10/30后测试κ=.15/.2（tmp/native_physical_gain_calibration_summary.json）：均安全，但.15参与仅约4.9–5.6%，.2约14.8–19.4%，以小幅节油交换明显组织损失。位置修正饱和±2也做3seed600（tmp/native_bounded_feedback_probe_summary.json），TT40.88–41.15、fuel83.28–87.44、参与20–22%，未作为首选。其首次测试因临时包缺init导致导入失败，属于探针基础设施错误，重试严格确认RED是AssertionError。
- 最终D候选采用速度差阻尼：_request为desired=reference_speed+.3*(target−ego.x)，request=clip(ego.speed+SPEED_RELAXATION*(desired−ego.speed))，SPEED_RELAXATION=.2。0.1s步长相当于a=.6位置误差+2参考速度差、名义响应.5s。头车有界相位仍原规则；global也共享_request。删除失败的共同±2执行层，原生车型边界保持；安全cap仍直接min。
- D3seed600全部安全：seeds1/2/3 TT40.617/40.796/40.879s，fuel77.794/81.510/80.747g/km，下游参与30.1/24.6/24.7%，峰值均12。不是最终5seed结论。
- D正式40正在执行：exec46391，操作results/operations/20261028T222456580783Z_native-pd-final-forty-cases_a8ef7a48，timeout3600；root variants/phase5g_pure_formation/results/native_pd_final_validation_20261029T0624。代码先在仅80KB的六模块冻结包tmp/native_final_pd_package_20261029运行，避免污染并行C源码。协议docs/experiments/2026-10-29-native-pd-final/protocol.json。禁止改这六源码，当前完成约10例，种子1/2各主模式均安全，transform40.617/40.796。
- C40结束后已将D六源码逐字复制到main variant并逐SHA核对。安装证据integration_evidence.json。旧test_native_actuation.py仅测被删除限制的4测试已删除；新增PD反例RED确认23!=20.6（20261028T222342092602Z_native-relative-speed-response-red_f5635519）。D冻结包156测试GREEN（20261028T222414778117Z_native-pd-final-package-green_c05fa1d1）。Main安装后156完整核心复测exec4822/label native-pd-installed-final-core-tests待查，root9项GREEN（20261028T223128265508Z_native-pd-installed-final-gui-tests_a8527570）。
- D六车6/6安全恢复、真实3LC、TT39.3667、down参与59.81%、峰值6、平均恢复12.333s，functional_six_verified/independent.json两份逐项一致。Main同六车另跑后解压轨迹与逐车账本和D冻结包逐字节/字段相等，证据native_pd_installed_verification/20261028T223103...，已加入integration_evidence.json，用户指定目录安装已实际核实。
- cloud main当前仍1112697(C候选源码)。D main变更尚未提交；156+9验证后可代码先commit/push，再待D40全部结束复算、图/文档发布。最终报告已改为D骨架，A40另方法对照，C长时失败在方法更新末尾。系统说明/README已更新PD定义但正式数值尚待。
- 下一步：检查核心测试→D代码云端；D40等待全40（失败全部保留）→complete_layer_metrics负责D comparison_verified/recovery+compact→native_result_figures生成D4图与元数据并目检→主报告按正式数值填表+同seedTT/直路/恢复/A代价/C失败/Cai原图分离→所有文档计划检查点同步→精确stage小成果（recovery compact，不Git重复6MB原JSON）→push最终文档与结果。北京时间06:33，08:00前任务不提前结束为未完成。

## 2026-10-29 07:08：D40实现、正式验证与说明文档完成

- 用户指定目录D:\yanjiu1\keyan1中的D方法已实现。当前控制规则e1704882...、运行器27e2de09...与协议及冻结运行包逐字节一致，方法代码931a005已在云端main；窗口与首次计算逐步同步，已无轨迹预生成/完成锚点链路。`python -B runrun.py --check`再次退出0，路径为该目录的native_sumo及SUMO1.27.1。
- 最终方法只保留真实前车链、头车有界相位、局部补位、当前F/R间隙、局部让位/接收开隙与位置/速度差阻尼。_request两行，κ=.3、SPEED_RELAXATION=.2（dt.1、名义响应.5s）。物理5/10/30，无失败的±2执行限幅。没有全局意图或通信；global仅是独立对照。
- D40 operation `20261028T222456580783Z_native-pd-final-forty-cases_a8ef7a48` completed/0，1395.343s。40/40全部safe/drained/all_completed，24,464车次全部请求/发车/离场，0碰撞/teleport，最终源端/在网0。独立60/60配对、240/240源码快照、0.1秒轨迹覆盖均通过。5个直路formation/transform账本及解压轨迹完全一致。
- 主数据docs/experiments/2026-10-29-native-pd-final；原始native_pd_final_validation_20261029T0624只读保留。独立比较日志`20261028T224853076772Z...d8bd71f6`、恢复`20261028T224853075270Z...d2ae3101`、最终包验证`20261028T225341980054Z_cd40-final-package-verification_aacca377`在variant/results/operations。
- 3→2五seed均值：NOA TT42.023507/fuel61.635803；formation40.955616/83.429821；transform40.971247/81.313859；Cai式适配global41.294427/69.655501。D较NOA时间少2.50398%、燃油多31.92634%；5seed TT差[-1.564685,-1.185150,-1.034370,-.990590,-.486500]s。对普通形成均值慢.015631s，不能写额外交通收益。出口流量3428.4对3418.8，只是有限600s窗口，非容量。
- D下游完整多层参与25.2537%、条件平均5.4088辆、每seed峰值12、5秒稳定参与1.3894%。上游曾形成279辆中243恢复、36出口删失，条件平均12.4864s；普通形成29/288，两个实际形成集合不同。全3058辆里1410观察到两道结构。5秒指标需结合200m下游观察窗与边界删失解释。
- D六车3次实际LC均在675m前，6/6恢复、mean12.333s；安装目录再次实跑的账本与解压轨迹和冻结包完全相同，integration_evidence.json可查。直路D平均TT39.9441、fuel71.6800、参与12.4169%、最大15辆，NOA41.7167。
- 156核心+9当前GUI+83历史GUI=248项通过；独立质量60项与核心重叠不另加。根控最终证据`20261028T230122030231Z_native-final-release-evidence_7129a700`退出0，另核main/Git HEAD六源码、4图300DPI有效PNG/SVG及3批无损gzip账本和compact一致性。便携证据在D/verification。
- A40是无阻尼历史对照；D燃油比A下降8.13073%，仍高于NOA。C40完整保留且明确否决：seed2 TT50.110对NOA42.195，整体42.668对42.323，失败未剔除。37条校准中34排空、3未排空，均有真实source hash与路径。
- 四组D图已生成并逐张目检，plot62992122...、summary411c7b17...。新主报告4398字与现行系统说明（含全部规则/方法和正式进展）、README、方法更新、计划/规格已同步。Cai原Fig5的29±2m/s读数与本机适配中央参考分开；原SNOPT查询Invalid Mex记录保留，不冒充原论文完整重现。
- 小成果A/C/D与Cai数据图约5.8MB随Git提交；恢复逐车CSV无损gzip压到约185KB/批，compact约90KB。旧展开JSON/CSV及大轨迹留本机并ignore，不复制整个项目存版本。临时格式化工具目录清理被自动审批以blocked by policy拒绝，目录保留；其代码无运行依赖。
- 当前研究实现与验证工作已完成，正将报告/数据推云端；推送后补最终发布记录。后续新窗口先读README、docs/原生SUMO编队变换系统说明.md第9节及本节，再读实际规则；不要回退到被拒绝C或旧Python运动链路。后续研究可在此配对证据基础上降低燃油代价，并扩展原生工况。


### 最终云端发布记录

方法代码`931a005`、完整报告/规则说明/图形/A-C-D数据包`87303b8`均已成功推送`https://github.com/32780542/yanjiu1`的main。实施计划全部验收项已完成。本轮1250/3→2实现、检验、改进、独立比较及可读交接文档任务完成；当前版本为D，未启动后续实验。最后封存提交只补本发布记录与计划勾选，不改变已验证运行代码和数据。

## 2026-10-29 08:28：用户要求四流量瓶颈归因，当前任务重新开始

- 用户指出自建global不应充当Cai集中式性能数据，并要求500/750/1000/1500每道流量比较NOA/编队，只有瓶颈拥挤降低带来的收益才成立；若无关必须改方法。补充允许读取D:/matlab_huipu_2000完整思路和车辆控制。已明确更正主README/旧D报告/Cai依据，不再把自建global列作Cai或最优集中基线。
- 旧D1250整体数据实际反例：drop−straight瓶颈附加TT，NOA0.306771s、transform1.027158s，NOA−transform减少量−0.720387s。不能用D全程2.5%优势宣称瓶颈疏解；源控制允许形成追赶30.8/33.3而NOA通常28.8，需因果核验。
- 新计划docs/superpowers/plans/2026-10-29-flow-bottleneck-attribution.md，用户已授权直接试验与归因失败后改方法，不等额外确认。当前六D源码冻结不改；新增run_flow_study.py仅批次编排。
- 100例D诊断正在运行：exec40841，operation results/operations/20261029T002525304552Z_flow-attribution-D-baseline-100_73a5fdcb，timeout7200；study根variants/phase5g_pure_formation/results/flow_attribution_D_20261029/20261029T002525811260Z。每flow×5seed有straight noa/transform及drop noa/formation/transform；先seed再flow，便于早期四流量诊断。每例600s需求/max900，_source_snapshot六源不变，wrapper也逐SHA复制到study目录。旧数据不覆盖。
- 独立MATLAB审计agent matlab_control_audit_4flows：已证mainmain vF28.8但轨迹优化max33.33，每5s执行首5s，ICV setSpeed(goalSpeed)未按vF截断；mainmain→formationControl→formationControlNormal→singleVehicleCalculate为实际链。applySmoothSpeedControl/constrainSpeed仅定义无调用，其他CAV_control/Car_following等属备用入口，不能混称。文档待该agent完成。
- 独立评价agent bottleneck_attribution_metrics仅创建experiments/bottleneck_attribution.py及对应test，TDD分段过门/密度/低速积聚和多flow配对；先旧D1250只读复算。不会改控制器。
- 独立local_causality_method_review只读研究最小局部更新、避免自由流超速伪造收益，不改源码/不跑仿真。root待真实分段/密度证据和MATLAB审计后决定替换方案。若原方法失败，必须保留并进行新冻结四流量验证，不能只交诊断结束。
- 本轮尚未完成，禁止沿用上一轮“任务完成”记录。下一入口：先检查40841与study/run_status，读取agent成果；运行中的六源码不能改，只可在小型隔离包做候选校准。最终要清晰报告低流量是否根本无拥挤，不能制造慢NOA、入口门或改阈值凑收益。

### 09:32继续点：旧D四流量归因失败，执行生命周期已修，候选仍在验证

- D100 operation completed0，2759.375s，100/100 allsafe/completed，45,790请求全部排空，6源码快照600份与原D协议一致。正式独立包docs/experiments/2026-10-29-four-flow-attribution/D_baseline，analysis_overview/postverification/artifact_hashes齐；每flow25case独立native+recovery。全体主要640–1100归因减少均负：500−.161833、750−.298630、1000−.409117、1500−.337082s；20配对19负。全程DID500−.168441/750−.332441/1000−.486049/1500−2.873420s。低速vehicle-s NOA .54/1.38/3.20/120.32，transform0；1500断面flow反而−18.72/h。不能把消除少量低速与整体瓶颈提效混同，D不满足用户归因要求。
- MATLAB调用链与55哈希证据已完成，docs/2026-10-29-MATLAB车辆控制调用链核查.md及同名源码证据.json。真正mainmain→formationControl→formationControlNormal→singleVehicleCalculate；普通ICV可33.33追赶、vF28.8为巡航末速；smooth/constrain/旧CAVControl并未走主链。道路源码两段实体都3道、仅连接2→1，不等于当前实际3→2。只读未执行MATLAB，无集中式实测效率，旧自建global已退出主结论。
- 新离线评价器experiments/bottleneck_attribution.py及14测试完成，sha deea86...，+27comparison+15recovery冻结56项GREEN。逐请求过门、首尾/连续0.1s覆盖、分段删失、低速/密度/flow及差分，按flow分组。D100正式分析另有冻结源副本/70个artifact hash校验。旧1250真实定位640–800额外成本+.795175s，800–1100局部改善+.358439s，净主要段失败−.436736s。
- 根因迭代：E1双向前后位置/速度反馈接近速度中性，但头车独自相位传递慢，六车peak0；加gain或安全接收距离仍未成6，保留tmp/balanced* summaries。E3将相位按可见车道头车共同分担，局部按车数去公共修正，六车peak6；20case seed1pilot却flow500残一车，750/1000整体慢，1500较NOA快但需全种子。E4将所有相位按30m折叠解决截断头行静态反例，却六车只成4，拒绝。
- E3残车实际不是流量堵塞：v2_03506请求1→2于372.2(x637.598)，372.3未开始横移已进640，规则把target2重绑0；372.4原native开始向2，373.4已居中2而memory0，2→0被执行guard拒绝，终点残留900s。4100帧精确重现、空路端点独立probe证明能正常2→1。报告tmp/E3_stall_diagnosis_report.json与golden_frames。
- 主variant已TDD修这一共用执行bug（不改D跟驰/相位/接收策略）：Vehicle.pending_lane仅本车，runner.active_lane_request从自身lane_attempts在decide前同步；严格0.05居中完成后先释放，尚在真实横移超1.2也保持；pending不能被preparing reset或宽容差arrived取消；静止旧非相邻目标重估。neighbor pending始终None，无邻车意图。rules e50ba5...、engine6a5300...，10新测/104native/39global-layers/rootGUI9共162不同测通过，主D500/seed1 238/238、六车6/6三LC安全。证据tmp/own_lane_execution_main_evidence.json。尚未git；agent e3_stall_diagnosis正把大REAL_FRAMES literal移tests/fixtures/own_lane_request_race.json，只碰test+fixture，10项再验。
- 隔离E5=E3平衡相位+ownpending初版+普通路30m周期相位、prepare内unwrapped。六车peak6/P48.6%；500straight42.074/drop42.115，1500straight42.452/drop42.498（seed1，安全）。大流量成组参与仅~.8%，不足以定版。其ownpending实现早于主严格完成细修，勿覆盖主main。root在tmp/E5_execution_regression_summary.json记录；已全部结束。
- 新E6基于已修复主D六源码，双向距离、跟前后实速均值（避免每车Cruise锚点拖慢队首传导），仅真实队首在45m范围成对对齐，安全接收距离用停止距离反解（同速11.26，快后车需额外停车差）。六车peak6但P14.4%。E7改一致的速度差耦合（body ref=ego.speed+ΣneighborΔv，head ref=Cruise+ΣneighborΔv），六车peak6/P26.9%，未加新状态或硬速度限幅；需真实流量因果检验。
- 当前唯一候选长运行：E7 pilot，exec95054，label E7-two-flow-full-pilot，使用tmp/E7_symmetric_velocity/run_flow_study.py --flows5001500 --seeds1，10cases 600s，base variants/phase5g_pure_formation/results/flow_attribution_E7_pilot。源包冻结勿改。主main当前仍“D+执行bugfix”，不是E7。之前exec40841 D100、32809 E3pilot、59858 E5regression都已结束。
- 下一入口：检查E7 pilot，按NOA/transform直路与drop差分，检查编队规模/真实低速积聚，再决定最小修法/新正式100case。不要用低流量本来无拥堵硬制造收益，也不能只交诊断就停（用户要求归因失败后改）。待正式选择后将唯一简洁规则装main、受影响测试+独立审查、全四flow5seed冻结验证、图表/报告和Git发布。当前README/旧报告更正、MATLAB核查、新metric/wrapper/bugfix均尚未提交；可以先提交已验证的更正与bugfix，但不要把任何E候选当成功发布。

### 09:49：执行修复验收与候选否决

- 主目录执行修复与新评价器联合回归：operation `20261029T014353516479Z_flow-attribution-current-180-tests_78108322` 实际 **167 tests + 29 subtests passed**，退出0；label中的180是运行前估计，计数以pytest输出为准。此前从根目录直接收集整个variant tests因同名根包优先及历史模块而22项collection error，未执行测试；重试显式将variant加入sys.path首位并选当前8个测试文件，未改测试回避实际失败。
- E7 pilot 10/10完成，但1500 transform TT59.182841对NOA42.791421，主要段归因−4.779877s，上下游完整参与均0，正式否决。E5在1500下游参与仅.80%，没有同版NOA，不视为成功。独立候选质量包tmp/E_candidate_quality_review覆盖35持续流+3六车、166文件hash。
- 原six_vehicle_initial本就完整两层三道，不能证明自组织；之后同时检验打乱位置的六车形成和原六车变换，最终以连续随机来车为准。E8/E9只在tmp独立包试验，未装主代码；不在D上叠加失败规则。主目录仍为D+执行生命周期修复。

### 10:18：H版冻结正式复测，先验证后定结论

- D100便携证据约19.2MB在docs/experiments/2026-10-29-four-flow-attribution/portable_D_baseline；原展开分析只读并ignore。root独立verify operation `20261029T015636999909Z...b50e847c`退出0。四面板图figures/D_baseline.png/.svg已生成并目检；新报告docs/2026-10-29-四流量瓶颈归因报告.md列完整否定性结果，仍需补H正式数据。
- E8“所有可见front都追”造成整串接近最高速度，连续流上游P0，拒绝；E9相邻道body互选虽打乱六车成6，持续流仍P0，拒绝；E10限50m形成连接把速度恢复约28.8，但已有6车变换只成4。实际34.7s坐标证明：两道各3车、q各差约一整层，头尾悬空，body互选错误平衡，不是安全或车道数问题。
- H继承E11：50m内真实同道front30m跟驰；无该front才是局部队首，以physical phase在相邻道互选实际队首；头互选同50m，所需候选/前车信息完整落ego[-100,+150]，在现有视野内。只头跨道分担，跟车沿实际前链，不再body错层；接收gap用共同停止距离反解，不提前全30m。未增rear双向控制、全局分配或邻车intent。
- E11原6变换峰6/P59.95%，打乱6首次11.3s形成6/P60.84%，均safe；q500straight/drop41.7063/41.7366，q150041.8428/42.2557，均safe。1500up1.67%/down14.23%仍需改善，不能靠小组或单种子宣告成功。
- 发布冻结包tmp/head_group_H_release：从E11仅Black25.1格式化，AST完全一致；rules **77c0111530560db30e97dc466bcdaf276a78cb7dd7192767e9a2d51b97eab2d2**，engine **6a530098146e85a637b4f29d580d61877c7a54b3a7e15858724651d80e8956b0**；wrapper **cf7a371677a08dd312ae904f410d26070452d464314b12b0a2b5943f0b2d1385**。8静态门rootfresh通过，operation021105...b04c0681。
- 新wrapper支持独立进程jobs，源与wrapper完整封存。串行10case vs jobs2 10case实际请求/trips/解压positions全等，16.86→10.14s，无残留；异常5result亦保留且外层失败，tmp/parallel_study_equivalence.json。H格式化与验证wrapper AST同。没有改SUMO控制性能。
- **当前正式H100运行 exec82453**，operation `20261029T021127070794Z_H-four-flow-five-seed-100_7fba570b`，study `variants/phase5g_pure_formation/results/flow_attribution_H_final/20261029T021127615583Z`，600/900、5seed、4flow、相同5模式/场景矩阵（100例），jobs4。冻结目录勿改。bottleneck_attribution_metrics agent等外层0+100齐后独立分析至H_analysis，复用原冻结评价器，所有失败保留。
- e3_stall_diagnosis agent负责主目录字节安装H rules/wrapper、新增head静态8测试、按新规则重写旧7个合同（原失败38pass/7fail证据020715...ae1a7be8），不改其他production；root负责README/系统说明/主报告。local_causality_method_review只读独立审查H信息边界与因果解释。
- root已告诉用户将补“仅协作合流”消融：保留同样helper/接收/必要并入、关闭成组调距和自由补位，20例drop配对，用来检验收益是否无需编队也能出现。主常用代码不增模式，只在明确源码封存的独立实验包实现；尚未启动，不可把其当已验证结果。
- Git已推e9de622（执行bug修复/新metrics/MATLAB核查/撤回假Cai对比）；D便携、图、新报告、H代码与wrapper/新tests尚未提交。本轮仍进行中，下一入口先检查82453与agent，勿沿用旧“阶段成功”。

### 11:10继续点：H100正式失败结论已明确，C0/C1因果消融与几何更新仍进行

- Git **ba78c6a** 已成功推yanjiu1/main（前序345edab是D100便携+图/阴性报告；ba78加入H规则/并行wrapper/测试/逐条系统说明/实现证据，并修复图SVG入库CRLF哈希）。一次verify与commit错误地写在同一shell继续执行，SVG校验失败后仍产生345edab；已在未发布期间用renormalize保留精确bytes，ba78中fresh核验D48payload+两图hash全通过后才推送。所有portable文件以-text保字节，CRLF按cr-at-eol检查；测试黄金fixture同样保字节。主production6源+wrapper Git索引与H冻结字节一致。
- H主安装回归 **176核心+9根GUI**通过，旧7合同在D上仍7红、H上绿；其余38旧测试AST不变、ownpending10未动。600局部状态NOA action/memory与旧版一致。30份实际日志/测试/fixture与freeze封存于implementation_evidence/H_implementation_evidence.tar.gz（46KB），manifest绑定。root已fresh检查核心与GUI result0、源码索引字节与冻结一致。
- H100 exec82453已completed0，957.484s；所有100safe/drained/all_completed，45790请求/离场，0collision/teleport。独立guard exec53059和postverify均completed0；H_analysis全77artifact hash、实际目录100与manifest100、source6/wrapper/protocol/jobs4、native/recovery/归因inputs/trips/positions一致。原H_analysis只读并ignore。
- H正式均值flow500/750/1000/1500：NOA TT41.753715/41.819128/41.880390/42.641211；TF41.778779/41.832421/41.934979/42.939205。**全四flow TF仍比NOA慢**。主640–1100 DID−.006107/+.042117/+.029315/+.429807；全程DID−.005099/+.043953/+.021525/−.187205。1500上游100–600 DID−.445722；seed4 TF44.249668 vsNOA42.982603。不能宣称交通提效成功。
- H upstream PP仅.28856/.36357/.72177/.87288%，down7.77057/15.02303/20.41428/13.57215%；down stable .44112/.98984/1.30671/.77455%。原upstream subjects恢复4/6、24/24、29/63、65/129，删失2/0/34/64。fuelTF64.3717/66.9433/69.9428/80.5142，NOA60.4024/60.8320/61.3152/63.2775。低速NOA1.20/2.58/5.30/201.86veh-s，TF0；1500断面flow4432.32对NOA4443.84，无容量提升。
- portable_H50文件19.319MB已完成，bundle rootbaf2341b...，root独立verify operation024939...6126fda1退出0；H四面板图已目检。D/H格式相同四张表。**portable_H/H图/H阴性数据更新report/README/系统说明、.gitignore H_analysis尚未提交**（main仍H已推；不要把H数据遗漏）。
- C0为“NOA+相同协作合流、关闭_following/_fill、允许ordinary overtake”，仅独立包tmp/H_cooperative_ablation，main不增mode。20drop9158请求全safe；短直路500/1500各HNOA/C0共4case账本/解压轨迹完全同。先严格hash分析因flow500(int)/500.0(float)表示停机；v2保留原两SHA并逐物理字段数值完全相同审计，不改raw。C0-H TT差−.007369/−.054820/+.072597/+1.347332；主段差+.006067/−.020141/+.140307/+2.049166；低速4.64/3.72/45.96/724.52对H0。不能把C0高q劣势全归编队：**C0实际834次normal_overtake**而H无，存在政策混杂。
- portable_C0新完成133payload约4.262MB，20case60原JSON+4短直路16成员、freeze6/eval/20gate/region、H_method_independent_review、v1错误/v2显式flow数值表示审计全留，manifest e3313915...。root还需fresh verify、stage及Git。local_causality_method_review agent已完成该包，未Git。
- **C1严格消融**由bottleneck_attribution_metrics agent在tmp/H_strict_formation_ablation独立做：仅从C0关掉cooperative的ordinary overtake（NOA仍保留），保持H同helper/接收/执行/合流，只关闭形成跟驰/补位；20drop同4flow5seed600/max900 jobs4，随后配对H与portable_C1。目的排除C0超车混杂。当前需检查其进度，主metrics/C0/H包不改。
- H已证准备区构型反例：两个头x635/645各按自己区域3/2解释对方，原始相位误差+25/+5，实际都加速。J隔离改为每car实测x的共用相位场：α=clip((x−640)/360,0,1)，φ=(1−α)φ3+αφ2，真实y插值；pair分母使用双方实际road-lanes max−1。9静态GREEN/两六车成6，sourcec08f8149...。但1500 seeds1/4 drop J−H TT+.027145/−.597875，downPP14.23→5.69%、13.08→5.24%，stable均0。原sixdown25.9%/stable0/break3。**J不装main、不作整体成功**，report在tmp/J_spatial_phase/report.json，source只读。
- **K当前短测**由e3_stall_diagnosis agent做tmp/K_spatial_velocity，从J只改_following：有实际互选head pair时，沿路相位φ的导数slope=(φ2−φ3)/360（仅640<x<1000），desired物理v=(28.8+phase_speed)/(1+slope)，仍原ρ/κ/cap/MAX/safe；孤车/无pair必须slope0，front<=50仍原真实前车。0新参数/记忆。物理反例x820两头同q，J的期望qdot30/27.6而K均28.8；8静态GREEN。打乱6P66.81%/stable56.49%，原6drop峰6/P35.49%但stable0/break3/TT39.333，已保留。规则 **83de119879ea940cd2455a3626b1a576ab9d4ff170895cd70b1a0606b64d5412**；正跑1500 seeds1&4×straight/drop600s四例。没有改main/J/H。若通过必须再冻结完整四flow100，不能单种子宣布成功；若失败不堆参数。
- 用户最新工作仍是四流量因果检验与失败后方法更新，允许借鉴完整MATLAB而必须局部/分布式。**当前整体目标未通过，继续工作，不以H小车功能通过代替交通结论**。下一入口：检查K短轮、C1及数据包，H数据/图/README已更新但还要Git；未触碰的PDF、run.ps1、MagicMock不要stage。最后需要主报告最新正式数据/所有规则文档、可读结果图、完整压缩证据和云端发布。

### 2026-10-29 13:25：P独立四流量验收、严格消融与失败方法交接

**当前状态：工程链路可运行，整体研究目标未通过；本轮没有正在运行的仿真或候选。** 主目录仍是用户指定的 `D:/yanjiu1/keyan1`，直接运行 `runrun.py` 为P方法的实时SUMO窗口。不能沿用旧D40“瓶颈提效成功”的解释，也不能把后续R/S的较短行程当作编队成功。

- 前序H100、C0消融和H图表已推用户仓库 `yanjiu1/main`，提交 `e1d6254`。本检查点随P源码、独立报告、便携数据和诊断档案一同入库，最终云端提交以该远端main指针为准；`origin`仍是另一历史仓库。没有纳入未跟踪的PDF、run.ps1或MagicMock。
- 现行P仅保留必要的共同构型修正：每对队首在最近候选、反向互选和误差归一化时使用同一车道构型。两辆车的车道索引都小于2且均达到边界才改为两道；transform边界640米，formation边界1000米；有一辆仍在终止道则保留三道解释。这里依据实测车道索引，不能写成全车身已离开终止道。实际横移完成另查0.05米居中和0.05m/s横向速度。
- 主规则SHA256 **8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864**；引擎 **6a530098146e85a637b4f29d580d61877c7a54b3a7e15858724651d80e8956b0**；wrapper **cf7a371677a08dd312ae904f410d26070452d464314b12b0a2b5943f0b2d1385**。六核心源码与正式冻结包一致，没有将J/K/N/R/S装入主代码。此前9个H测试文件字节不变，P新增11项；总 **187 tests +29 subtests、9根GUI tests**通过。集成证据在 `implementation_evidence/P_implementation_evidence.tar.gz` 和 `P_manifest.json`，含原失败/通过日志及两次实际六车轨迹。
- P预登记协议为 `docs/experiments/2026-10-29-four-flow-attribution/P_protocol.md`。最终批次使用未用于D/H选择的种子 **6–10**，每道流量500/750/1000/1500、600秒请求、900秒上限、jobs4。完整100例（直路NOA/P、缩减NOA/F/P）已全部完成，48,060次车辆运行全安全排空、0碰撞/瞬移。原始目录 `variants/phase5g_pure_formation/results/flow_attribution_P_heldout/20261029T033726974665Z`；operation `20261029T033726646224Z_P-heldout-four-flow-five-seed-100_3a34680d` completed0，1076.312秒。冻结评价器没有改变。
- P在四流量的缩减道路全程均值依次 **41.769688/41.853895/41.970283/43.596960秒**，同输入NOA **41.731506/41.787264/41.894584/42.660825秒**，全部更慢。主要640–1100米差分改善 **−.005184/−.004519/−.009587/+.161616秒**；全程差分 **−.003788/−.007602/−.018194/−.815962秒**。1500上游100–600米差分−.693194秒，不能只截主要段得出总体提效。
- 1500的五个P−NOA全程差按种子6/7/8/9/10为 **+2.109180/+2.503927/−.175907/−.014516/+.257992秒**，三次变慢、两次变快。燃油P **64.821/67.519/70.652/83.462 g/km**，均高于NOA **60.401/60.802/61.236/63.336**。1500低速积聚由NOA213.10降为P13.68车辆秒，但全程慢0.936135秒；1000米有限时窗通过量4658.40→4641.12辆/h，没有通行能力优势结论。
- 严格C1_P只关闭形成跟驰和自由补位，保留P同样的协作合流、普通超车政策与执行器，20例种子6–10、9,612请求全部安全完成。原参数SHA与配对P严格相等，非数值表示豁免。C1_P均值 **41.767300/41.925911/42.047930/43.494615秒**。形成规则相对C1_P使主要段缩短 **.021191/.125468/.135442/.987646秒**，但1500全程P仍比C1_P慢.102345秒。这支持局部组织作用，不能据此声称有效编队已带来整体收益。旧C1种子1–5不与此合并，C0含834次普通超车的混杂也继续保留。
- 正式公开成果：`portable_P` 约20.08MB、100例300份原JSON及无损数据；bundle SHA **5622ced9d322ca8df061adf2a6a49d7b0625f4ca5686ce832d4d1b3b4949b15b**。`portable_C1_P` 约4.74MB、131payload；bundle SHA **2eb98e062b7806fc2794777747d1f90e2fcec014c6241d3314373e07404394ed**。旧 `portable_C1` 约4.89MB也完成。root已独立verify三包，并核验其Git索引字节；原展开P_analysis和大轨迹只读、ignore，不再复制进Git。D/H/C0原包不改。
- 新主报告 **`docs/2026-10-29-P独立验收报告.md`**含14张表，涵盖逐种子、交通/燃油/低速、上游下游完整层参与、规模、保持、内部断裂、边界删失与恢复有效数量。35个公开链接已独立核验，表格没有修改；报告SHA **8f4956327f6b62ef5ef3c95724ea6ac1be34ebcf564d9f615171237ee73b8af8**。数值来源审计归档于implementation_evidence。300dpi PNG和SVG四面板图已生成并目检，图与冻结表绑定。
- 分区横移诊断用现有P100+C1_P20原事件，不增评价阈值。34,723条严格完成事件与计数、车头位置分区及原source/input/result SHA一致；root独立核验operation `20261029T052027534159Z_P-existing-event-diagnosis-root-verification_5edc7f32`退出0。P缩减道路横移/请求 **.714168/.888760/1.025008/1.390660**，NOA **.329665/.345039/.350204/.379481**。额外横移与上游成本共同出现，但事件没有逐条绑定规则，不能把全部代价都归给_fill。
- 下游窗口仅200米，七层十四辆期望跨度195米，在28.8m/s下整组完全位于窗内的时间约.17秒，不能通过1秒确认。因此下游峰值12不是控制器固定上限；稳定参与也需同时读边界删失。上游640米窗没有该12辆限制，上游参与四流量均低于1%仍是实际持续形成问题。
- J/K空间相位与速度导数、N后车辅助均未安装。早先E/J/K/N等18个独立源码身份及原失败证据去重保存在 `method_diagnostics`，源档案134成员、342原input记录不变，root独立verify通过。最后R领航者保持、S分层实车参照均只用局部实车和原参数，各通过8静态反例、两个六车并完成1500种子1/4直路/缩减四例；行程改善没有形成持续的大编队，S缩减上游参与为0%/.02746%，**均否决**。R/S另存 `R_S_diagnostics`，不修改早先只读档案、不再开新候选。
- 已阅读用户补充的完整 `D:/matlab_huipu_2000` 活跃调用链：mainmain→formationControl→formationControlNormal→singleVehicleCalculate，5秒规划并执行5秒，28.8巡航、33.33追赶；55文件SHA和44份完整.m/11个旧main证据索引在MATLAB核查文档。全组目标分配和联合避碰需要全局信息，未直接装入局部控制。MATLAB当前两段均三道，不等于本轮物理3→2；未运行原MATLAB优化器，没有原Cai同工况交通数值，不编造集中式排名。
- `README.md`、`原生SUMO编队变换系统说明.md`、方法更新和实施计划已按上述结论重写。系统说明第3节逐条解释现行全部规则，第4节列方法和执行顺序，第7节说明指标，第9节区分工程完成和研究未通过。root最后 `python -B runrun.py --check`通过，实时配置仍为1250/600秒/seed1/GUI。
- 最后根端复核：R/S归档1.093MiB，4档案67成员、12case、141原文件逐项通过（operation `20261029T052917842288Z_R-S-final-independent-root-verification_450ca673`）；最终P主六源、wrapper、35个报告链接、14张表、PNG/SVG及各诊断文件的Git索引字节全部通过（`20261029T052948551044Z_P-final-publication-archive-index-verification_56578727`）。原操作和校验脚本封存在 `implementation_evidence/P_final_publication_check.tar.gz`，6成员、3514字节，档案SHA **183f1ddc0f90bb62f0d451d9f791b86b7b1a9f539b28b87a38a4365e49117bd0**。旧运动学系统说明和419方法索引已增加历史标注，现行方法以原生SUMO说明为准。

**下一入口：**先读P独立验收报告、系统说明与当前源码，勿重跑已通过的整套工程检查。未解决的是持续随机车流中的完整多层形成，以及形成/补位动作的上游时间和燃油成本。后续新方法须独立冻结源码，保留与真实NOA的同输入直路/缩减对照、严格消融及新种子验证；提高自由追赶速度或仅减少瓶颈低速不能代替持续成队和整体提效验收。本轮数据是完整的负结果，不能写成方法成功。

### 2026-10-29：固定间距与固定时距的理论核查，尚未改控制代码

用户提出当前低稳定性是否来自固定间距ACC，以及固定时距会怎样。本单元仅核对源码、文献和线性分析，不实施新控制器、不运行新仿真，P主规则仍为8d112d79…，正式数据及评价口径不变。

- 当前 `_following` 用真实前车后30米作为目标，`_request` 的0.2速度反馈作用于0.1秒步长。若请求被完整执行、忽略延迟/限幅/安全裁剪，等价加速度为 `a_i=0.6(d_i−30)+2(v_front−v_i)`，d为车头间距；对应位置增益Kp=.6/s²、相对速度增益Kv=2/s。
- 在上述连续时间、同质单道模型中，前后车速度扰动传递函数为 `H(s)=(2s+.6)/(s²+2s+.6)`。其幅值在0<ω<sqrt(1.2)时大于1，数值峰值约1.100719，ω约.500734rad/s（周期12.54795秒）。这是现有纵向规则缺乏串稳定性的理论依据，**不是SUMO实测放大率**；单车能收敛不等于长串波动不放大。
- 固定时距可将期望车头距设为 `d*=L+s0+h*v_i`，保留相同位置/相对速度反馈。无延迟二阶模型的传递函数变为 `(Kv*s+Kp)/(s²+(Kv+Kp*h)*s+Kp)`，幅值不放大的条件为 `Kv*h+.5*Kp*h²>=1`。代入上述增益，理想模型h下界约.467251秒；真实采样、安全覆盖、SUMO响应和横移会改变结论，不能据此宣布整套多车道系统稳定。代码中0.5秒名义速度响应已体现在控制增益中，不能再直接当作额外执行器迟滞套文献下界。
- 建议先用现有车长L=4米、静止净距s0=1.5米，并取h=(30−4−1.5)/28.8=.850694秒。这样在巡航28.8m/s时仍为30米车头距，便于比较控制结构；20m/s时约22.514米、10m/s时约14.007米。h≈.85是待验证起点，不是已仿真最优值。不能把“30米”再作为静止常数并叠加h*v，否则巡航间距将约54.5米，改变稳态密度。
- 原完整层参与率还受到跨道头车配对、自由补位、区域边界和1/5秒确认的影响，不能用参与率低直接代替串不稳定实测。时距实验应先在无换道、固定真实前车链上检查扰动沿队列是否放大，再进入原四流量同输入直路/缩减对照。巡航几何仍为30/15；减速时正常的时距伸缩与真正散队须分别记录，不能只把跟驰换成时距而仍用刚性30/15解释所有瞬态。
- 一手资料：[Soundararajan 2021，第2章传递函数和第4章串稳定区域](https://oaktrust.library.tamu.edu/bitstreams/dcd773fb-fb4f-4966-adc6-fb871d5432c2/download)；[Darbha等2018，含执行器迟滞的时距条件及车载前车观测方案](https://arxiv.org/abs/1803.02900)。上述本项目数值由现行代码参数自行推导，不是文献或仿真报告中的实验结果。

当前没有新时距仿真或候选进程。下一步若实施，以此为方法讨论起点；先验证纵向波动传播，再判断其能否改善持续编队和全程交通结果。

### 2026-10-29：用户确认的本车0/1状态已实现

用户确认状态1定义为“已有本车编队跟驰或队首配对关系，允许仍在调距”，孤立车和NOA为0。本轮在原目录直接实施输出与统计，没有实施固定时距，没有改驾驶参数或入口。当前没有运行中的试验。

- `Command.formation_state`新增0/1；现有50米前车链、可见同道后车或互选相邻道队首使其为1。后车使链首也能自报参与。状态只进入记录，`Vehicle`及邻车观测没有该字段。没有跨车读取状态或隐含通信。
- `_following`第四返回值为状态，前三项速度/目标/引用保留；各动作分支携带相同当帧局部状态。无误差阈值、完整层或额外确认计时。纯NOA固定0。自建global未实现本车状态，记为不可用而非0。
- `native_sumo.FormationStateStats`直接统计车辆秒加权参与率、平均/峰值同时参与人数、连续1段数及平均/最长已观测时长。逐帧`formation_states[id]`独立于原四项运动数组；result/diagnostic及根runrun终端均可查看。参与人数是全路总数，不等于单支编队大小。
- 新`native_comparison`直接从原状态帧重算，不调用完整层检测；测试用拦截器证明了该路径。它仍核对请求、共同参数、安全完成和记录完整性。旧轨迹无状态输出时保留原历史口径；既有P100及报告没有改写或补造状态。
- 初始13项新合同因字段/累计器缺失预期失败，随后通过；比较入口4项先失败后通过，其中一个测试误写车辆ID已修正并另留有效失败。全回归最初203通过、1项旧三元组断言失败；改为第四项状态后最终 **206 tests +29 subtests通过**，operation `20261029T093250428557Z_local-state-final-core_4a2b879b`，17.03秒。根GUI **9 tests通过**，operation `20261029T093432043403Z_local-state-root-gui-entry_74755a33`。`runrun.py --check`也通过。
- 900个随机局部状态逐项对比冻结P，除新增状态外，全部动作与私有记忆一致。真实SUMO五对（straight NOA/transform、drop NOA/formation/transform），1500/seed6/60秒请求/max180，每例80辆全安全排空；全部物理帧相同、trips原字节相同。operation `20261029T092956163630Z_local-formation-state-physical-equivalence_5e796f81` completed0，116.157秒；原目录 `tmp/formation_state_validation_20261029T092956361074Z`只读。
- 该短回归中，缩减道路编队变换的自报参与率95.651%、平均同时32.175人、峰61、平均连续1为28.671秒；NOA为0。它与旧完整层口径不同，不构成新的交通提效结果。原运动逐帧不变。
- 当前规则SHA **ac1c5aba082130718c81a23eb2c7bc9708caa8dae6b138baea951d07e735ee7d**；引擎 **bc22273fa224206e03dd896fb7b386a5d28ce3526fddebfa6bf7d7c93caaa1d1**；CLI **986431e85af09e2e4610d5be5570ea0860606717e94ca64a1167f07f3f9c3e24**。不是旧P的8d源码字节，但已验证控制行为相同。六源摘要随新运行封存。
- 公开交接目录 `docs/experiments/2026-10-29-local-formation-state`含可读说明、完整summary、约2.33MB的83成员证据及独立verify。档案SHA **09388ef1dd8539e2468a5634b59e45d1e8a81d120c1d623fe70ed037188c41f7**；保留一对完整新旧轨迹，其他8份仅索引大轨迹。根独立verify operation `20261029T094136843053Z_local-state-public-evidence-verification_91f257ed`退出0，83成员、999物理帧及直接状态重算均通过。README/系统说明3.13及7.1已同步。
- 最后核验源码、证据、Git索引与交接链接均通过，operation `20261029T094702078168Z_local-state-final-index-and-handoff_615e33fc`退出0。真实根入口短测 `20261029T094536422432Z_local-state-entry-output-smoke_e9fbaab2`也退出0：4/4安全完成，终端打印参与率86.49%、峰4人、连续1均值18.09秒。此例只验输出链路，不作交通结论。源码、说明和证据随本检查点提交至用户远端`yanjiu1/main`。

**接续入口：**当前默认统计为本车局部关系的0/1直接统计，历史完整层模块只作旧报告复算。固定时距仍未实施；此前约0.85秒的分析保留为下一项方法讨论。不要因新的状态参与率高而改写旧交通结果，也不要将全路总参与人数当作单支编队大小。

### 2026-10-30：150篇文献检索与形成/变换方法建议

用户要求先检索100–200篇网上相关文献，判断对当前编队形成及变换的帮助。本单元完成文献库、关键原文分析和实施建议；控制基线仍为`5fffdd3`，没有修改控制代码、参数或历史实验，没有运行新仿真。

- 交接入口为`docs/research/2026-10-30-literature-review/README.md`及`文献结论与方法建议.md`。A跟驰53条、B多车道形成50条、C合流50条，153条按DOI/题名去重为**150篇**。31篇读到相关重点正文章节、116篇读到摘要/预览、3篇仅题录；没有把全部150篇写成通读全文。Cai2024正文来自用户本地原PDF，另在线核对题录。
- 文献库含逐篇中文概要、信息条件、可借鉴机制、适用范围和原文定位，提供CSV/JSON/BibTeX。141条DOI中140条经独立Crossref确认，1条中文研究由原期刊确认；另9条保留可靠来源链接。主库订正Scarinci/Heydecker综述为2014、34(6)，保留初筛及订正依据。原全文缓存不入Git。
- 建议第一步只在真实前车`_following`建立单前车固定时距基线；保持原巡航30米平衡点的候选h为0.850694秒，并协调`_phase/_fill`暂态伸缩。通用`_request`同时服务开隙/合流，不作整体替换。Donà2022的第二实际前车感知作为独立后续扩展，不读取邻车加速度通信或私有状态。
- 建议第二步为`_fill`保留形成收益，借MOBIL比较同帧自车与新旧后车的制动代价；不能只用加速度获益挡住等速形成换道，也不能让其他收益抵消目标后车严重制动。必要合流不受自由补位收益门槛阻塞。第三步复用实际F/R、`gap`、`joining`和本车执行反馈，平滑恢复组织参考；真实前车与安全几何仍用当帧状态。
- 队首重选滞回与相位死区为低优先候选，需要先有切换扰动证据。Meere2023原文使用V2V/预设图，不能继承其证明为本系统结论；Rupp2018无通信车道减少主题很近，本轮只取得摘要，尚不移植公式。Cai全组分配不直接加入局部规则，仍没有同工况原集中式效率数值。
- 验证顺序写入报告：先固定前车链的速度扰动试验，再比较同一新跟驰下的NOA与编队，分别消融补位成本/参考恢复，最后同输入直路与3→2、五流量500/750/1000/1250/1500。原NOA继续留作基线。0/1参与人数、参与率与连续1时长保持用户口径，不恢复完整层评价门槛。
- 文献离线核验operation`20261029T175521159104Z_literature-final-catalog-verification_be14dba2`退出0：150条CSV/BibTeX、17处主报告引用、44条本地链接、原始输入SHA与生产代码未变通过。此前一次因合法的TU/e全文备用链接未列入检查表而失败，已补充该来源并另留成功记录。五份主目录文件离线重建逐字节一致，见`reproducibility.json`。最终出版核验以文献目录中的`verification.json`及Git提交为准。

**接续入口：**先读本轮方法建议与A/B/C重点笔记，再读当前`native_rules.py`。下一项候选是单前车固定时距；目前仍未实施、未宣称其提高交通效率。本轮文献目录及研究进度随检查点保存至用户远端`yanjiu1/main`，现有P正式负结果保持原样。

### 2026-10-30：文献建议的独立规则试验已启动

用户授权分别试验，采用有用项并用GitHub管理。协议为`docs/experiments/2026-10-30-rule-trials/protocol.md`，计划为`docs/superpowers/plans/2026-10-30-literature-rule-trials.md`。在原主目录工作，生产规则仍为8ed11d9对应版本，候选不先装入主入口。研究分支`research/20261030-rule-trials`随单元提交至远端`yanjiu1`。

- T为共用实际前车固定时距，巡航仍30米，h=.8506944444；NOA状态0，原NOA另留。候选规则SHA046f00aa…，7项合同先有6个预期断言失败再全部通过；T方法及补丁放在本轮目录。M/R由隔离候选分别实现，均未修改生产文件。
- `run_trials.py`冻结必要源及配置，每工况独立进程/目录；初筛base/T 32例正在运行，operation`20261030T003244549091Z_literature-screen-base-T_8f4b7c0a`，batch`tmp/literature_trials/batches/20261030T003244862597Z_screen`。1250/1500，种子1/4，直路/3→2，NOA/transform，600秒需求/900秒上限，jobs4。每个已完成例均保留原source/input/result/trips/positions，不改旧记录。
- 独立检查发现worker早期超时的临时result缺少最终字段时会抛KeyError。针对性测试先失败，改为读取可缺失的最终字段后通过，operation`20261030T003839724166Z_literature-runner-timeout-green_89d0573b`。新批使用修正；当前运行批次已加载原驱动、已完成数据不受影响。外层run_logged私有Windows Job管理全树；未观察到孤儿进程。

**断流后下一入口：**检查上述operation/manifest和进程再继续，不重启相同批次。完成T车串、M/R独立筛查后再选择组合；尚无最终采用结论，不用单种子燃油改善代替五流量验证。Git认证管理器在本机报运行时错误，使用现有Windows GitHub凭据的内存授权完成推送，不在文件或日志保存令牌。

### 2026-10-30：独立筛查48例完成，正在检验增量价值

- base/T批32例退出0、547.703秒；M/R批16例退出0、360.86秒。合并`tmp/literature_trials/screen48_manifest.json`，48例全部安全排空，分析`screen48_analysis`核对全部原源SHA、请求、物理、0/1及所有车辆的两段实际越线。T/M/R相对base的8例transform等权平均TT差为−.282/−.261/−.155秒，燃油差−3.924/−2.049/−.894g/km；R时间只4/8改善，M为8/8，不能把R列为一致改善。
- 实际12车单道纵向试验使用相同原生SUMO车型与安全执行，只激励领车、调用真实`_following`，隔离横移。base/T在周期输入的队尾速度半幅为2.380583/.247925m/s，制动恢复输入为11.600182/2.819649m/s，四例全部安全。目录`tmp/literature_trials/strings/20261030T004327072012Z`，operation`20261030T004326591783Z_literature-T-real-string-longitudinal_41b92b72`退出0。首次单道试验误调用完整三道决策，因产生换道请求而显式中止，失败日志保留；没有据该失败改生产规则。
- T2仅在T上加入第二实际前车、归一化0.5权重，维持动态平衡点；10项合同通过。独立16例已全部安全排空，batch`20261030T005014639722Z_screen`。增量车串目录`strings/20261030T005509239176Z`，T2周期/制动尾部半幅.199091/2.510745m/s；比T更平滑，但持续流时间/燃油/连续1增益较小且有代价，尚未采用。
- TM规则复用T公开跟驰做反事实预测，仅自由补位增加制动成本，11项合同通过。TR在T的速度相关目标上复用0.5秒恢复，9项通过；都没有改变生产规则。TM8正在batch`20261030T005519408674Z_screen`运行，随后TR8及新种子五流量验收。当前研究分支在线保存协议、候选补丁及测试，原生产仍为8ed基线。

**下一入口：**检查TM8和后续TR的operation，不重启已完成64例。候选是否采用，要看相对T的增量和新种子验证；保留原NOA、新NOA与编队三者区别。精简数据包保存原input/result/trips/source及0/1、越线原始字段，完整轨迹不重复加入Git。

### 2026-10-30：TM已写回主目录，250例独立验证运行中

**当前程序：**`D:/yanjiu1/keyan1/variants/phase5g_pure_formation/noa/native_rules.py`为冻结TM，SHA256`65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`，461行改为511行；仍是本车纯规则、有限局部感知，私有记忆三个字段。仅保留共用单前车时距和自由补位制动成本，R/TR与T2未启用。生产源现在有意改变驾驶行为，不再是上轮仅加0/1的状态输出提交。

- 初筛共80例，全部安全排空，清单`tmp/literature_trials/screen80_manifest.json`及分析`screen80_analysis`。在T上增加M，8例等权平均TT−.018819秒、燃油−.407684g/km，参与率+.32676个百分点、连续1均值+.702147秒。TR相对T四个道路/流量组平均TT全部增加，燃油均值约不变，不采用。T2车串更平顺但持续流增益很小且混合，暂留研究记录。所有候选补丁已核对能逐字节重建试算源码；T2/TR补丁的路径相对variant，其余相对仓库根，应用时使用对应目录。
- 最终协议`docs/experiments/2026-10-30-rule-trials/heldout_protocol.md`在新批前登记。**250例正在运行**，operation`results/operations/20261030T010841852291Z_literature-heldout-five-flow-250_63ec1217`，session38533；batch`tmp/literature_trials/batches/20261030T010842083890Z_heldout`。流量500/750/1000/1250/1500，种子11–15，600/900秒、jobs4。base NOA/transform各50，T transform50，TM NOA/transform各50；T的NOA与TM同规则，不重复运行。源包已冻结，勿在运行中修改或重跑已完成工况。外层timeout7200秒；首次10800参数被runner启动前拒绝，没有产生案例。
- 新增正式T7/M12合同先在基线出现预期失败，安装精确TM后19项及8个子测试通过。四个旧平衡/真实前车断言改为D*(v)，保持原容差；三项历史H/P全控制等价断言改为从原已公开`evidence.tar.gz`读取hash-pinned状态基线，保留原1220个随机案例、H/P SHA和全部断言。现行安全、局部信息、执行与直接状态合同继续检查当前源码。
- 正式14文件核心回归 **225 tests、37 subtests全部通过**，operation`variants/phase5g_pure_formation/results/operations/20261030T011348789879Z_literature-TM-final-core_219b48fd`，23.156秒。当前原生GUI入口9项通过，根operation`20261030T012137610390Z_literature-TM-live-root-entry_b0a103bd`；额外旧demo83项/230子测试也通过，勿把它代替当前9项。根`runrun.py --check`通过；实际根headless10秒请求/80上限短测operation`20261030T012137608852Z_literature-TM-live-root-smoke_201454ba`退出0。
- 代码审查未发现生产正确性缺陷，指出旧分析警示句对同候选NOA/编队的归因措辞不清，已修正生成器及说明。同候选共用跟驰，剩余差别为形成/协作/超车政策；TM−T用于补位增量。旧已封存分析数据不改数值，最终报告用正确解释。
- screen48紧凑包8,802,762字节，SHA`347fb732be6cc0d8c28056ddf4a0400ff209f039d83512d4ffc80e1027c97d02`，300去重块、307843帧、31956次车辆运行。root独立离线核验退出0（operation`20261030T011514175873Z_literature-screen48-root-independent-verify_b95dcf26`）；原件及选出字段重提取也由独立构建者核验。extensions32另建，旧包不重写。后续heldout建议按五策略各50例分包。脚本和数据入口见本轮`evidence/README.md`。
- 四面板真实车串图已生成并目检，PNG300dpi及SVG在本轮`figures/string_response.*`，原数值和源摘要同目录。T重复试验逐字节物理轨迹相同；图含base、T、T2，生产TM使用与T相同纵向规则。图由实测轨迹得到，不是示意图或理论传递函数曲线。

**断流恢复：**先读本条及heldout operation的result/manifest和活跃进程，不重启250例；完成后分析全部案例、逐种子和TM−T增量，再更新README/系统说明/最终报告，核对所有公开数据包及代码索引，推送`yanjiu1/main`。当前研究分支为`research/20261030-rule-trials`，远端main仍为上一轮8ed11d9；本轮先随单元推研究分支，最终才更新main。未解决的整体效率问题以本批实际结果为准，不把初筛当正式结论。
