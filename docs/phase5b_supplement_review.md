# 阶段5B：回归与活跃细积分辅助脚本独立审查

2026-09-13。有界范围为根目录`tmp/phase5b_active_refinement.py`、`tmp/phase5b_regression.py`及其直接调用的冻结记录/细积分函数，对照[预登记计划](D:/yanjiu1/keyan1/docs/phase5b_conservative_release_plan.md)。本次不改src、不运行新车辆，也不代替新副本R5实现的独立源码审查。旧SUMO诊断及固定证据未改。

**发现并闭合1项P2：原活跃细积分辅助脚本的总体passed与进程退出码只取数值重建成功，未包含原误差比较门槛。** 原始写法允许`recording=true / integration_comparison=false`仍保存总体passed=true并exit0。已向主任务报告，由主任务修改create/replay两支为两条件合取，增加独立`recording_passed`，末尾依据总体passed返回0/1。本审查未自行修改该脚本。

修复后脚本SHA256为`75c13399b78647f8142acde06165ab4b11d36a6b3867e04a1c08f897927d4c2b`。独立夹具对**实际脚本**两种模式各执行三个门槛组合，均满足预期：

|重建结果|原细积分误差比较|create总体/exit|replay总体/exit|
|---|---|---|---|
|true|false|false / 1|false / 1|
|true|true|true / 0|true / 0|
|false|true|false / 1|false / 1|

夹具使用极小临时JSON来源，mock数值细化与数值重放返回值；create仍实际写入新packet、脚本快照、provenance和evidence manifest，replay仍核对manifest、来源、复制输入与脚本哈希。还检查每个场景只调用一次integration_refinement，而create/replay各调用一次replay_sampling。它验证失败门槛及封存分支，**不验证实际0.005s轨迹、数值收敛、动作正确或SUMO结果**。

证据为[夹具脚本](D:/yanjiu1/keyan1/tmp/phase5b_supplement_gate_probe.py)、[六分支结果](D:/yanjiu1/keyan1/tmp/phase5b_supplement_gate_probe_20260913T0430/validation.json)、[受审脚本快照](D:/yanjiu1/keyan1/tmp/phase5b_supplement_gate_probe_20260913T0430/reviewed_script_snapshot.py)。`run_logged`日志目录为`results/operations/20260913T041946404867Z_phase5b_supplement_gate_probe_33f881d1`，exit=0，elapsed=0.422s。三个夹具源和packet均在该新tmp目录内，没有读取或修改正式run。

其余审查结论如下：

- active helper的`_source_state`检查正式源evidence/code/input的完整文件集合、逐文件哈希和当前工作副本一致性；create/replay前后再次比较来源状态。packet必须在所选source之外且create拒绝已有目录。replay要求外部给定expected manifest SHA，核对整个packet、复制metadata/trace及脚本快照，未发现静默覆写旧成功的路径。
- 只选`r5_competing_r5_on`，要求execution_status=completed且left有已提交draw，要求复制记录均completed。原`integration_refinement`从保存首态出发，仅重用各记录actions，将原dynamics_dt/2；本计划原0.01s对应0.005s，控制dt保持0.1s。原`replay_sampling`检查每车覆盖、元数据、区间数、逐动作完全相等、数值重建和原位置/航向门槛。没有half_control记录、策略调用或SUMO入口。
- `_source_state`是完整性检查，不代替整包标准语义重放。正式使用仍应在新run封存并通过其专用标准重放后调用，完整窗口含义由该正式来源验证。本夹具不能证明将来数据已完整。本脚本也没有计算实际jerk/舒适或多车细积分扫掠；不得扩大为这些条件通过。
- regression脚本只允许计划声明的四文件源码差异，并要求规则文件及新测试存在；在固定新副本运行，旧fixture按固定source_hashes核对后复制，不由导入旧测试生成来源。代码清单在回归前后比较；失败或代码变化返回1；已存在且内容不同的source freeze拒绝覆盖。
- regression排除整个`test_artifacts`模块并记录排除ID和原因，符合复用已有阶段1证据的范围。它**包含真实SUMO**的`test_phase2_live.test_real_sumo_cross_edge_and_both_sync_rates`，因此未来正式回归不能描述成纯离线。本审查没有运行回归suite。
- 当前冻结八案例文件SHA256仍为计划中的`46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20`；克隆来源登记的七项输入当前全部相等。回归脚本对计划/案例输入记录SHA而不是自行重做整包语义核验，正式run和标准重放仍须执行计划中的源/输入绑定，不应只以其`source_unchanged`字段代替全部输入验收。

本轮未发现在上述声明调用前提下仍未闭合的P1/P2。审查通过只允许继续正式验证，不表示回归、17机制、活跃细积分或阶段5科学门槛已通过。回归脚本SHA256为`6211b220da5e27c5a13e20de6ae6e23414fe41d56f733246b7bfca59cfaa60f7`，预登记计划SHA256为`cdeb037b71ee07487e6dcbe9d8ac335a85c68130f0db3aba31353d902ac78e35`；直接依赖及输入SHA保存在[审查输入清单](D:/yanjiu1/keyan1/tmp/phase5b_supplement_gate_probe_20260913T0430/review_input_hashes.json)。后续如脚本再改，以上夹具结果仅归属于这里记录的修复版本。
