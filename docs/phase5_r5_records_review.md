# 阶段5 R5记录层独立审查

结论：**下表最终版本的记录层审查通过，无未关闭 P1/P2。** 可以冻结记录 overlay 并进入已批准的新版本整合与正式机制实验。本结论验证私有初态路由、记录/重放和失败保留合同；不代表新版本真实 SUMO 驾驶通过、R5必有赢家、编队改善或下一研究阶段已获准。

审查对象为 `variants/phase5_r5_common_development`。案例生成器已由[独立案例审查](/D:/yanjiu1/keyan1/docs/phase5_r5_cases_review.md)验收，本次没有重复生成正式熵、筛选种子或运行正式机制案例；控制层结论见[控制独审](/D:/yanjiu1/keyan1/docs/phase5_r5_controller_review.md)。旧 A/B、heldout、v1、生产控制与旧证据未被本审查修改。

## 最终源码与合同

| common相对路径 | SHA256 |
|---|---|
| simulation/r5_clock.py | 7f39f6b9afccdbe06e17d2a4bb4bf398906e24f7cbe8a66c5f2a75895853b90f |
| experiments/phase5_r5.py | 4dfb5c98b5a366e9e32ca476d211e09b874bc0e42c3a6a659809e78aba59db37 |
| experiments/phase5_r5_replay.py | 6c703856aa10b99470531db960468e7007b430ec1a46fe32063003e611386286 |
| experiments/phase5_r5_audit.py | c5712c07585af45a1c3c5030d4a7247bba7091cc02dfaad95ea18df2c7553308 |
| experiments/phase5.py | 1bc9d7b4958084cc24d2b88eb55f967fe53af2c28fa0fc5a9b99c1bb3cc2ce8d |
| experiments/phase5_replay.py | 824791dcace7e759a39d2e3affe6f57c351a2c412ed700fff0e8bf889c272765 |
| run.py | b9f31e3f958a65b0b6c2dd42fdfa5de0631c717140626fcfcb7ca0836f4e9ce8 |
| tests/test_phase5_r5_records.py | a0b4858ae779a6c0420d3ff724a6f0ab12204606520dfcb2a876029ebd450ac7 |

最终独立单元输出 `common/tmp/phase5_r5_records_independent_units_v1/result.json` 保存上述快照、完整 `code_manifest_before/after`，两者相同。common中的基础 `simulation/noa_clock.py` 保持原字节 `5d68509a8a04ebd39360da81be0c76f90c4847ae7df6837634f5f4c096f0504d`。记录接口变化没有修改控制增益、目标速度、R5阈值、执行器或原守卫邻车横向界。

已核实以下行为：

- `phase5_r5_v1` 是显式 schema；初始记忆必须逐受控实例提供完整 dataclass 字段，RNG为精确uint64整数且拒绝bool/float，计数与状态机经控制codec校验。允许两个实例的初始随机值相同，但逐实例恢复独立对象。第一次冻结观察只更新该车观察历史，不重置私有流。
- 沿用原同刻冻结、全部决策、各车积分、同步、最后统一提交协议。控制器没有得到外层case列表、别车memory、种子来源登记或外生脚本。新run_case hook只显式选择clock和审计入口；启用R5却缺schema必须拒绝，原整包重放入口明确拒绝R5整包。
- 独立重放从metadata绑定的初始记忆重建全链，重算动作、全部已保存物理子步及失败边界；离散随机状态/计数逐值逐类型比较，浮点随机输出、期限和本车计时用`float.hex()`精确比较。物理episode签名仍按物理重放容差处理，不能因此宣称物理身份已被证明。
- 反事实先通过完整私有链重放，再重建所有传感历史并按既定步长及最后物理帧采样，使用已验证的同一份本车memory。除原物理比较外，最终版本还逐位比较原trace与反事实的私有域，以及重建audit与保存audit的私有域。隐藏类型、未来计划、ID/顺序、范围外状态属于离线审计变换；可见邻车移除对gate、私有状态、动作的改变分别统计。
- 整包绑定已声明业务证据、完整code/input快照集合与hash、当前源码、六个必需输入及冻结case文件原始字节；从生成器重新构造完整case和17变体声明，逐字段核对case、初态、模型、控制/策略参数、schema与时长。六个当前输入还纳入执行结束及重放前后比较，覆盖实际仍从当前NET读取道路的边界；原外部case文件在复制后不再作为运行依赖。
- 索引保留执行顺序前缀、已完成与未启动变体。部分包以共同的`summarize_partial`复算，既有sampling仍须复算；部分包不能自报驾驶/科学/下一阶段成功。完整无竞争配对只在两侧完整窗口上比较实际命令，失败/缺失为null；整包工程门槛还要求非空洞R5 gate或私有抽样敏感性，不用普通动作变化替代。

## 独立发现与修复闭环

本次发现两个边界并交由记录作者修复，审查者未修改实现。

1. **单case版本类型缺口。** 原`validate_metadata`中`True == 1`使PRNG版本布尔值在单case重放中通过。整包案例加载器当时已有严格类型检查，因此问题范围是单case入口。原始有效0.2s记录只将metadata/case的同一provenance版本改为True即可复现；最终版要求`type(version) is int`，原坏JSON不改字节即拒绝。
2. **非干扰私有计时仍穿过物理容差。** 原版对保存audit的私有字段已精确校验，但原trace与反事实的`identical`仍继承物理容差。独立wrapper只把离线反事实decision中的`r5_last_time_s`增加`replay_absolute_tolerance/4 = 2.5e-11`，原trace先独立重放正常，八次反事实仍被报告identical/passed。最终在此基线比较也加入`compare_private_record`，同wrapper产生八个不一致且审计失败，未修改原trace或在线控制。早期协作消息把该delta误写为2.5e-8；脚本、保存JSON及本报告中的实际值从始至终为2.5e-11。

有效旧反例日志为 `results/operations/20260912T214230510377Z_phase5_r5_record_entry_independent_negative_v2_8e77744b`，退出0、0.516s表示成功收集旧缺口。旧代码/输入/结果位于 `common/tmp/phase5_r5_records_independent_entry_negative_v2`。初次尝试把输出置于root/tmp，因common输出域限制而失败，日志`214158937508Z_phase5_r5_record_entry_independent_negative_846f39fe`和原脚本保留；v2仅更正输出目录。

修复后对原坏JSON及同一wrapper的独立复验为 `results/operations/20260912T215312690599Z_phase5_r5_entry_fixed_independent_aa38cdc7`，退出0、0.532s；正常trace和八次正常反事实仍通过，两个旧反例拒绝。随后作者只补了runner/source的六输入绑定，clock、audit和单case私有比较未再改变；最终17项独立单元再次覆盖这两项合同。

Root此前发现的`u/delay/deadline`小于物理容差篡改，以及partial自报四类成功，本次也在最终单元/独立整包反例中复验；没有把旧RED或作者自报GREEN当作独立复验的替代。

## 独立验证证据

所有命令通过root的`scripts/run_logged.py`，使用登记Python `-I -B -S`；脚本在 `tmp/phase5_r5_records_review_20260913/`，产物均在common自身新tmp目录，正式run未被复制或改动。

| 检查 | 日志（root/results/operations下） | 结果 |
|---|---|---|
| 四个一tick失败提交边界及各自改1bit RNG反例 | 20260912T215312690599Z_phase5_r5_failed_commit_independent_77952fc7 | 退出0，1.485s |
| 排除两套整包管线后的最终17项单元 | 20260912T215934591867Z_phase5_r5_units_final_independent_5fbae0f7 | 退出0，3.406s，17通过 |
| 最终短失败包正重放与11个复制包反例 | 20260912T215934586867Z_phase5_r5_bundle_final_independent_7d1a7328 | 退出0，25.187s，11拒绝 |
| 异cwd的3个CLI负入口 | 20260912T220434015866Z_phase5_r5_cli_independent_a27e350a | 退出0，0.454s；各子命令按预期退出2 |

失败边界是`decision/right`、`integration/right`、`synchronization`、`commit`。保存了1或2次决策抽样，已提交draw均为0，clock真实memory/state仍等于初态，失败clock拒绝再次tick。部分积分保留3车/30子步；同步/提交前保留4车/40子步，仍不冒充提交。每个边界正回放通过，改一bit决策随机状态均拒绝。输出在`common/tmp/phase5_r5_records_independent_commit_v1/result.json`。这些是offline停止边界，未执行SUMO同步故障；实际桥读回仍由已有live协议和下一正式包验证。

独立整包来源是作者最终**单元夹具**：

`common/tmp/r5_failed_package_test_gcsk5wyy/runs/20260912T215614684669Z_7ed49d2d`，evidence manifest SHA256 `4017059173a3a927dee05c91be4f0ec41c0ff6b66a91aeeeea6afb7361494ef8`。

它只把8个固定case时长显式缩成0.2s，第三个变体后在竞争on的积分前中断；独立重放也使用相同、公开的测试生成器patch。正重放验证4个已尝试变体，保留13个未启动变体，不能计为原20–40s机制试验。原包manifest及其受绑定内容在前后检查中不变。输出在`common/tmp/phase5_r5_records_independent_bundle_v1/result.json`。

在各自新copy中修改并重封证据后，以下11项仍全部拒绝：增加未登记源码文件；源码清单漏原文件；改必需冻结输入且同步其hash；改metadata/case私有初态并同步局部digest；给case增加不影响物理的R5观察目标；漏一项expected变体；分别自报`driving_passed/scientific_passed/next_stage_allowed/complete_execution=True`；虚构integration sampling通过。前3项直接调用整包使用的`_source_state`，其余8项走完整`replay_run`。拒绝并非单纯依赖旧evidence hash不匹配。

CLI从`D:/yanjiu1`启动绝对路径run.py，核实未提供case-file、未提供显式run-dir、指定单case子集均拒绝。这里没有声称独立完成了正式长案例CLI正运行或完整快照异cwd正回放。作者另保存了只恢复包内code/input并显式适配短生成器夹具的17变体CLI重放：common `results/operations/20260912T220050544132Z_phase5_r5_snapshot_foreign_cwd_cli_419192d5`，19.718s通过、缺参退出2、原源hash不变；本审查只读核对了其日志。作者整套19项最终记录测试日志为common `results/operations/20260912T215510353905Z_phase5_r5_records_bound_inputs_final_59380bbc`，85.957s通过；此前40项新记录/原阶段5记录回归在`215022201695Z_phase5_r5_records_final_regression_fbc8ac39`通过。它们与上表独立运行明确区分。

## 未验证条件与下一入口

本次没有正式R5车辆结果，短夹具offline为真，因此不能据其补写live工程成功或科学改善。私有流可重放不等于独立流在有限样本中必然错开；相同状态或同一行为采样bin可以继续对称。same-own-memory审计是已声明的采样反事实，不是分别模拟隐藏信息不同的完整闭环世界，也不证明变拓扑/串行稳定或全局互斥。原邻车额外横向加速度界0和不可见准备意图的限制未被随机退避消除。

下一入口：按root已确认的旧方法选择结果，将已审控制与记录overlay整合进独立新版本，绑定父版本、最终源码、冻结计划及三份独审报告原字节hash，再一次性冻结正式完整case/private RNG初态。只在该新版本执行声明的完整机制矩阵、实际SUMO读回和数值对照，独立重放并报告实际触发/拒绝/等待/失败。旧A/B与heldout结论保持其原版本范围；无改善或失败不能靠重抽私有状态、调阈值、隐藏通信、车型真值或全局调度补救。
