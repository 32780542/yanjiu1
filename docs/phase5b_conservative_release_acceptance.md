# 阶段5B：保守放行规则验收

状态：本单元实现、正式实验、固定来源比较、标准语义重放和补充数值验证均已完成。**未验证编队改善，阶段5科学门槛仍未通过，阶段6继续关闭。**

## 实际实现与前置条件

本单元承接前阶段失败边界，在独立[新副本](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/noa/r5.py:229)实现“私有退避已到期，但当前可见竞争仍无法区分先后时继续等待”。只增加3行生产规则，沿用YIELD及原让行守卫。期限、episode和私有随机状态继续保留，不重抽、不分配全局先后。

[前置核验](D:/yanjiu1/keyan1/results/phase5b/prerequisites_20260913T040953805450Z/verification.json)核对了旧交付39文件、父R5运行包332文件、106份实际源码和7项输入；全部与封存哈希一致。旧A/B开发与保留集结论保留：留出集全队成功均0/6，未验证简单规则优于成本法。没有根据这些失败重新选择方法或种子。

新副本从父run的code/input快照克隆。[源码冻结](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/phase5b_source_freeze.json)为107文件，差异严格限于规则文件、两份测试文件及runner的计划输入绑定。所有数值参数、B1形成规则、SUMO桥、动力学、原安全和舒适界均未改变；目标/最小换道速度仍为5 m/s，退避仍0.5–2 s，附加让行制动仍0.5 m/s²。完整设计与预登记见[计划](D:/yanjiu1/keyan1/docs/phase5b_conservative_release_plan.md)。

## 必要验证

- 新9项测试先在旧规则下出现18个预期子断言失败，然后在新规则下全部通过；旧R5相关51项通过。[TDD记录](D:/yanjiu1/keyan1/docs/phase5b_implementation_notes.md)
- 新副本完整受影响回归276项，0失败、0错误、0跳过，含原SUMO实测；测试前后源码一致，耗时224.469 s。[回归日志](D:/yanjiu1/keyan1/results/operations/20260913T042256145127Z_phase5b_integrated_regression_e8243aa0/result.json)
- 独立审查40项控制器测试及探针全部通过，覆盖低速/静止、无动机、准备期间重新出现歧义、原守卫拒绝和编队增量抑制；无未关闭P1/P2。[独立审查](D:/yanjiu1/keyan1/docs/phase5b_independent_review.md)
- 只读比较器的首次trace前失败边界、补充积分总体门槛各有独立负向验证。比较器能描述缺trace，不表示冻结标准重放已经覆盖缺trace；无法通过标准重放的包不能标为交付验收通过。[补充检查](D:/yanjiu1/keyan1/docs/phase5b_supplement_review.md)

## 固定实验事实

使用原8个场景及其完整物理/私有随机初态，不重抽。固定初态文件SHA256为`46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20`。17变体包括8个OFF/ON及首个清晰场景的半控制采样。父版本ON为已知诊断对照，本单元不是新的统计保留集。

新[正式run](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5_r5/runs/20260913T042930121115Z_deb427af/validation.json)用832.218 s完成17项尝试：14项完整执行，3项保存SUMO报告失败前缀，0未启动。recording=true，engineering/driving=false，complete_execution=false，scientific=null。源/输入变化列表为空。8个新ON均完整且通过原驾驶/舒适检查；三项OFF竞争失败及front_priority OFF完整窗口的驾驶/舒适失败仍在原包中。

两种ON规则比较如下。“提交/完成”按本车控制器记账；失败窗口包含已保存物理尾段，不延伸到计划时长。

|固定场景|父期限放行：窗口，提交/完成|新保守放行：窗口，提交/完成|观察|
|---|---|---|---|
|single_clear|20 s完整，1/1|20 s完整，1/1|无竞争行为保留|
|competing|4.7 s失败前缀，2/0|30 s完整，0/0|本例不再触发原生失败，但没有通行|
|speed_floor|30 s完整，0/0|30 s完整，0/0|仍不能换道，平均速度进一步降低|
|entered_priority|20 s完整，0/0|20 s完整，0/0|已进入优先路径保留|
|front_priority|20 s完整，1/1|20 s完整，1/1|可见位置优势仍可放行，无需随机抽样|
|reentry|40 s完整，1/1|40 s完整，0/0|出现退步；两版本都没有第二次竞争抽样|
|same_private_state|4.3 s失败前缀，2/0|20 s完整，0/0|相同私有状态仍对称等待|
|quantized_private_states|4.3 s失败前缀，2/0|20 s完整，0/0|不同期限同一行为格也继续等待|

[固定比较包](D:/yanjiu1/keyan1/results/phase5b/comparison_formal_20260913T0444/comparison.json)核实8个OFF的共同保存区间动作、输入/输出记忆和物理链全部exact相同；所有17变体参数、原8个场景及私有初態均相同。11对双方完整才有全窗口差值，6对含失败前缀的全窗口差值为null。3个父ON失败与新ON完整之间不能比较全窗口均速或断言统计安全改善。所有新变体保存子步的模型geometry collision_substeps仍为0；这不抵消三项SUMO报告失败。

等待的代价有直接数量证据。competing新ON两车各30 s平均速度1.6821 m/s，末速0.00931 m/s，按原1e-6 m/s停车阈值和0.01 s左端积分，各累计停车0.43 s；其余低速阶段是蠕行，不能表述成持续静止。speed_floor两车均速由约2.7457降到0.8811 m/s，各累计停车0.57 s。reentry受控车均速由5.2432降到3.1109 m/s，完成换道由1减为0。[全部34描述行](D:/yanjiu1/keyan1/results/phase5b/descriptive_rows_20260913T0446/rows.json)

competing新ON每车有7次原让行守卫拒绝，原因均为`own_actuator_unobservable_at_stop`；最后一帧29.9 s，本车观测速度/加速度为0，附加减速被拒绝，原回退动作请求+2 m/s²，产生再次低速移动。规则仍阻断换道，未把守卫拒绝改成接受，也未读取不可用的执行器真值。新规则的1889次“到期且仍ambiguous阻断”记录不构成互斥或通行证明。所有新机制物理记录中UNKNOWN仍为0，相关边界只得到测试覆盖。

数值方面，原single_clear半控制采样最大位置差0.00679532 m、航向差0.00140941 rad，通过原门槛；同保存动作的0.005 s积分位置差最大1.05365e-5 m，也通过。该清晰场景没有活跃R5竞争。补充的活跃competing新ON用全部4车的原保存动作细化至0.005 s，最大位置差1.69584e-5 m、航向差0，4车轨迹重建均通过；[补充包](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5b/active_integration_20260913T0455/validation.json)与[独立快照重放日志](D:/yanjiu1/keyan1/results/operations/20260913T045527454997Z_phase5b_active_refinement_snapshot_replay_correct_source_1caae3a4/result.json)已保存。这只检验固定动作下的动力学细化，不覆盖活跃竞争的控制采样变化、细化后的多车扫掠或舒适重新验收。

新[标准语义重放](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5_r5/replays/20260913T044401892589Z_bd809c6b/validation.json)用528.203 s完成：17个唯一变体全部通过，errors为空，unstarted为空，源前后相同。3个失败前缀仍为失败，source_engineering/source_driving=false、source_scientific=null。重放成功只表明这些实际成功/失败记录可重建，不改变驾驶或科学判定。

## 保留的执行错误

补充流程首次输出目录设在新副本之外，被原`output_path`边界拒绝；[失败日志](D:/yanjiu1/keyan1/results/operations/20260913T045341401879Z_phase5b_active_integration_refinement_26e04f9a/result.json)及未封存的部分输出 `results/phase5b/active_integration_20260913T0454` 保留。只将输出位置改到新副本的results后完成，未改脚本或原模型。随后一次快照重放把source-run路径填错，在路径检查阶段失败；[该日志](D:/yanjiu1/keyan1/results/operations/20260913T045503890893Z_phase5b_active_refinement_snapshot_replay_972b03e8/result.json)也保留，正确固定来源的后续独立尝试才通过。这两次是调用错误，不能计为车辆算法失败，也不能从记录中删除。

## 已验证的旧失败根因

1. 原不同私有期限可以被0.5 s行为格和准备时间合并，不能提供互斥保证。旧competing两车开始换道前的纵向动作完全相同，原基础制动已强于附加0.5制动，私有期限差异没有产生相对位置优势。[R5诊断](D:/yanjiu1/keyan1/docs/phase5b_r5_diagnosis.md)
2. 低速失败包含两种原因：真实制动使速度低于5；原舒适速度二分在上端可行时仍返回下偏值。旧OFF第一帧的数值下偏已使下一帧严格`>=5`门槛退出。本单元未修该求解问题，也未降低门槛。
3. 旧六个SUMO失败末端，保存车身横向间隙仍为1.0413–1.3000 m；13020次保存子步车对扫掠重核为0。前保险杠映射为同一原生车道，默认非sublane路径按纵向间距报告碰撞，其语义与带航向二维模型不同。六项原生失败照旧保留；首次映射后一拍报警的内部车道激活解释仍是官方版本源码支持的推断，尚未做原生最小夹具复现。[SUMO诊断及官方源码链接](D:/yanjiu1/keyan1/docs/phase5b_sumo_diagnosis.md)

## 科学条件与下一入口

本单元不提供互斥、公平、有限时间通行或一般安全证明。保守等待可以导致对称双方都停车；较少的换道请求/碰撞报告不能替代形成和恢复。原并排无前参考、多车局部片段、扰动后恢复、物理再入第二次抽样和UNKNOWN覆盖仍须分别验证。阶段6及交通、能耗收益结论继续关闭。

下一独立单元优先核实并修复舒适速度求解的可行上端返回，不改变目标5、最小门槛5或停止空间表达式；同时保留可能恢复双车同时启动的负结果。停车后执行器不可观测与蠕行另作隔离诊断，不能读取隐藏执行器状态或把守卫拒绝改成通过。具体入口见[当前下一入口](D:/yanjiu1/keyan1/docs/phase5_next_entry.md)，完整固定日志见[重放索引](D:/yanjiu1/keyan1/docs/phase5b_replay_index.md)。
