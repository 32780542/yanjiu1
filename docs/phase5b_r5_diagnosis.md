# 阶段5b：R5到期、同格启动与再入缺失的只读根因调查

2026-09-13。本报告固定读取 `variants/phase5_r5_completed` 及正式包 `results/phase5_r5/runs/20260912T222655136582Z_203b85c8`。未修改旧控制器、参数、初态、抽样、旧六种子或heldout；未调用控制器 `decide`、随机 `draw`、车辆积分或SUMO。旧R5正式结果仍为17个变体、11个完整执行、6个失败前缀；标准重放成功不抵消驾驶失败。

本次独立单元选择方案A：到期但当前仍为 `ambiguous` 时保持阻断，仅在可见优先成立或原稳定clear完成后重新检查候选。方案B的舒适速度数值端点问题留到另一个独立单元，不与A一起实现。本报告只有诊断、修正规则建议和待测反例，没有生产实现或新车辆效果证据。

## 证据与方法边界

独立产物在 [evidence_20260913_02](D:/yanjiu1/keyan1/tmp/phase5b_r5_diagnosis/evidence_20260913_02/summary.json)：10个旧变体、2722个actor决策行，包括失败项最后的未提交决策。完整标量行在 [scalar_rows.jsonl](D:/yanjiu1/keyan1/tmp/phase5b_r5_diagnosis/evidence_20260913_02/scalar_rows.jsonl)，保留 `status`、原trace行号、提交前后记忆、动作、phase、guard以及速度/动机门槛。该行数不是新的物理试验数量。失败末行不能计入已提交时长；例如competing-on每车47行中仅46行completed。

辅助脚本只从旧trace恢复本车输入，调用冻结的 `_longitudinal`、`_comfortable_speed`、`_stop_distance`、道路/可见车身重建；对reentry完成后的相邻候选，额外调用无副作用的 `assess_candidate`，字段明确命名为 `off_path_adjacent_assessments_not_executed`。这些额外assessment没有出现在原控制器执行路径中，不能计为原请求或通行。脚本未读取另车私有记忆来决定本车动作。

[来源记录](D:/yanjiu1/keyan1/tmp/phase5b_r5_diagnosis/evidence_20260913_02/provenance.json)保存全部已用来源文件前后SHA256，前后一致；导入的版本代码逐项匹配正式包代码清单。[独立核验](D:/yanjiu1/keyan1/tmp/phase5b_r5_diagnosis/verification_20260913_01/verification.json)不导入控制器，逐行对照原始trace的速度、动作、phase、deadline、draw数、plan和prepare时间，并断言下述关键事件，结果 `passed=true`、2722行。此核验没有重新执行全包标准语义重放，也没有声明连续时间安全。

所有长命令由根目录 `scripts/run_logged.py` 加120s外部超时执行，退出码均0。第一次提取保留在 `evidence_20260913_01`；第二次补充上端停止距离分解，并以1e-9时间匹配把原始7.099999999999991纳入“7.1s以后”，没有覆盖旧尝试目录。

|操作|根目录results/operations下日志|用时|
|---|---|---|
|初次只读提取|`20260913T040517085603Z_phase5b_r5_diagnosis_8904e811`|2.468s|
|补充上端表达式和边界时刻|`20260913T040711356412Z_phase5b_r5_diagnosis_endpoint_48ccf322`|2.110s|
|独立对照原trace核验|`20260913T041056802805Z_phase5b_r5_diagnosis_verify_9afc7c46`|1.734s|

两个脚本分别为 [diagnose.py](D:/yanjiu1/keyan1/tmp/phase5b_r5_diagnosis/diagnose.py) 和 [verify_evidence.py](D:/yanjiu1/keyan1/tmp/phase5b_r5_diagnosis/verify_evidence.py)；产物内各有脚本快照。重放必须使用全新输出目录。

## 一、speed_floor：三个不同原因不能合并

**已证数据流。** [controller.py:222](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:222)先推进已有R5 episode，即使本车低于5m/s、没有动机也允许旧计时和clear继续。随后 [248行](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:248)要求动机成立、无cooldown、无emergency，且精确 `vx_mps >= noa_min_lane_change_speed_mps`，才进入候选、R5 preview、原guard和prepare。正式参数的目标速度与最小换道速度均为原5m/s。R5到期只把旧phase改成ELIGIBLE，不能越过上述入口。

|原trace事件|left|right|含义|
|---|---:|---:|---|
|on私有deadline|1.3503197593202356s|1.4302393706704328s|每车仅一次draw|
|首次提交到期决策|1.4s|1.5s|观察离散化后的时刻|
|到期输入速度|4.402406329596007m/s|4.352443186026530m/s|物理上已明显低于5|
|到期基础纵向请求|+0.37354210697831236m/s²|+0.40352552158457705m/s²|已解除R5额外制动；正加速度不等于已达5|
|ELIGIBLE且速度低于5的completed行|286|285|均无plan；不是guard拒绝计数|

1. **on的实际额外制动。** 初始本车5m/s，R5按 [302行](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:302)取 `min(base,-0.5)`，经原hold候选guard接受后执行；left/right有14/15次额外制动，相应BACKOFF区间均从5以下开始或走向5以下。到期时原慢前车动机仍成立，emergency=false，但speed gate=false，`candidate_rejections=[]`、`candidate_guard=null`。不能把未尝试的候选说成被guard拒绝，也不能把ELIGIBLE说成已准备启动。
2. **off的独立数值下偏。** off在t=0确实进入PREPARE_LC，但初次基础动作已是 `-4.470348358154297e-8m/s²`；t=0.1速度为 `4.999999999047541m/s`，精确速度比较失败，prepare被 [317行](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:317)清掉。来源是 [_comfortable_speed:87–97](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:87)总从二分的lower返回：当5m/s上端可行时，实际返回 `4.999999925494194`。初态同一个原停止表达式在上端5的需求仅17.707942307692306m，可用距离28.05m；并非初态安全界必须把速度压到5以下。该微小量足以触发无容差的基础门槛。off没有R5 draw，不能把此首个失败归因于R5退避。
3. **后续物理跟车约束。** on-left到期后虽暂时加速，t=3s仍仅4.507148860495597m/s；基础跟车分量已变成−0.19740529426741116m/s²，慢前车始终2m/s。到29.9s，本车2.0008969981983076m/s、舒适安全速度约2.00239867m/s、上端5的停止表达式需17.71136107m而可用仅5.82912132m。长期未启动不能只解释成第一帧数值误差；随意直接返回5或强行补偿加速会改变原安全决策。on的活跃episode还使formation层持续FALLBACK，见 [formation.py:164](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/formation.py:164)，没有编队增量把速度补回。

**推断与限制。** 比例速度恢复律本身没有“从下方在有限时刻跨过同值基础门槛”的保证；本例还受到不断缩小的慢车间距约束。修复二分端点只修复可行上端的数值下偏，不自动消除on的实际减速，更不保证30s内安全启动。不能降低5m/s门槛、加入速度容差或提高目标速度来把这些负结果变为成功。

## 二、不同delay如何被合并成同时plan

**已证链路。** R5在 [r5.py:229](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/r5.py:229)只以deadline比较判断是否blocking；当前assessment即使仍为ambiguous，到期也返回ELIGIBLE。controller随后原guard接受，才在 [283行](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:283)开始prepare。prepare必须满0.5s，且 [288–290行](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:288)恰逢0.5s行为时刻才生成plan。

|on案例|两车delay(s)|首次prepare(s)|prepare最早满时刻(s)|实际plan时刻(s)|启动时assessment|
|---|---|---|---|---|---|
|competing|1.7772472488870688 / 1.8718904715041507|1.8 / 1.9|2.3 / 2.4|两者2.5|两者ambiguous|
|same_private_state|1.3498423627584213 / 同值|两者1.4|两者1.9|两者2.0|两者ambiguous|
|quantized_private_states|1.3498423627584213 / 1.3867846012971192|两者1.4|两者1.9|两者2.0|两者ambiguous|

competing不仅是时间网格问题：两车从t=0到plan启动的速度和纵向动作逐行完全相等。等待阶段基础减速一直比−0.5m/s²更强，故 `min(base,-0.5)`没有添加实际纵向差异。1.8–1.9s只有一方开始私有prepare，双方还没有可见横移；私有状态差异不会成为另一方可用观测。2.5s两车速度同为5.749629477032546m/s，原candidate guard均接受，随后同时产生相反的横向转向请求。不能把不同随机数视为已产生不同可见行为。

**守卫含义。** 正式参数 `noa_prediction_lateral_accel_bound_mps2=0`；[prediction.py开头](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/prediction.py:1)声明邻车横向预测沿已测惯性横向速度及配置界。两车启动前均无横移观测，同步发起的未来横移不由“尚未见到横移”排除。原guard的conditional接受不构成邻车不会同时发起的保证。本单元不调整这个界。

plan一旦存在，controller的 [active分支](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:193)继续原机动；[219行](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:219)只记录 `active_plan_bypass`，不再用R5给既有plan排优先。competing-on从2.6s起进入此分支，3.0s起出现原active预测不接受后的EMERGENCY动作。此时不能用“重抽随机数”“清掉plan”或把转向归零来假装修复已开始机动。三个竞争案例的on/off失败前缀及SUMO报告继续保留；本报告不把后来SUMO与模型几何的差异归因为一个未经核验的数值因素。

**推断。** 在镜像局部几何和相同私有状态下，确定的本地计算可产生完全相同的释放决定；即使独立状态不同，0.1s观察格与0.5s行为格也可合并差异。因此随机等待既没有互斥保证，也没有有限等待保证。仅换种子、延长退避上界、改随机流或细分时间格都不能关闭该反例。

## 三、reentry没有第二draw：没有第二个可启动的竞争episode

**已证事实。** 本例ego在t=0抽样一次、t=1.1开始prepare、t=2.0生成plan。原记录t=7.099999999999991（报告显示7.1s）满足机动完成；`completed_lane_changes`由0变1，同时old_plan=true、new_plan=false、old_episode=true、new_episode=false。清理路径是 [controller.py:198–202](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:198)的**机动完成清理**，不能解释为已经观察到“竞争清空并稳定1s”的独立物理事件。旧摘要所称clear仍成立于自身episode结束定义；原因需要区分。

从该行到39.9s共有329个completed输入：ego已经在中间车道，选中的基础lead为null、可见本车道lane end为null、慢前车动机=false、episode=false、draw=0。外生peer始终走另一外侧车道，其速度脚本变化不会自行创造本车换道动机。完成plan以后 [controller.py:235–248](D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py:235)走 `no_active_episode`，且不进入候选；不存在到达 `ambiguous && deadline is None && allow_draw` 的执行路径。

作为额外排除检查，对这329行的两个相邻候选只做离线路径外assessment：484次no_potential_competition、174次yield_entered、0次ambiguous。这不是新增原控制器请求。peer在12s以后可见纵向相对距离最小仍约62.38579531733552m，时刻27.1s；它的速度下降并未让原案例出现第二次近距离并排模糊竞争。即使观察到的邻车仍在传感范围内，“可见”“进入候选目标条带”“本车有换道动机”“同一空隙模糊竞争”也是不同条件。

**推断与应测反例。** 现有物理矩阵没有测试到clear后新的ambiguous episode，不能据此判断重抽机制失效。已有 `test_clear_then_reentry_draws_once_more` 可检验局部记忆转移，却不能补成真实物理再入覆盖。新的独立场景必须事先登记：旧episode确实结束，随后本车再次有原换道动机及合法相邻候选，当前可见近距离关系又为ambiguous；其二次draw必须来自新的本车episode。无动机、仅外生车加减速、只进入传感范围或只有HARD_YIELD的负例仍应维持不抽样，不得为凑第二draw改变原场景脚本再冒称旧例通过。

## 两种最小局部修正及代价

### 方案A：仍模糊竞争时，到期继续阻断（本单元选择）

**改动位置应在 `r5.advance_backoff` 的既有deadline分支，不能只在controller候选循环补一个if。** 该函数同时服务于controller的已有episode推进（230行）、候选preview（262行）和唯一允许draw的最终选择（300行）。只改候选层会让低速或无动机时的旧episode推进仍报告不阻断，并使preview与最终提交语义不一致。

最小语义为：保留已抽deadline及episode；到期且当前reason仍为ambiguous，返回blocking=true、既有phase YIELD及一个明确诊断原因（例如 `expired_ambiguous_wait`），不重抽、不提前进入prepare。可见关系转成 `ego_visible_front` 且原deadline已到，才允许进入原ELIGIBLE后续检查；新出现的ego_visible_front而无旧等待仍沿原规则。无竞争的稳定clear仍沿原clear时钟，不能在第一帧“无竞争”时直接解除旧episode。

以下分支必须保留：

- `HARD_YIELD`（entered、inward、visible_front、occupied_corridor）始终优先；到期不撤销它们。
- `UNKNOWN`及观测缺失仍阻断；不能复用新鲜时间间隔去复活旧位置签名。
- `no_potential_competition`原1s稳定clear、断帧重计时及不同目标的clear preview规则不变。clear确认期间phase即使ELIGIBLE，其blocking也仍为true，不能只据phase判断可启动。
- `allow_draw=False`的preview不能消耗私有状态；同episode的有效deadline不因新增YIELD相位丢失。重新落回ambiguous时应立即阻断并清除未完成prepare；已存在plan继续原active策略，不在本单元回滚。
- gate解除后仍重新经过原5m/s门槛、原guard、0.5s prepare和0.5s行为时刻。守卫拒绝不刷新deadline，不能用新随机数逃避拒绝。

**明确代价。** 相同物理状态和同私有状态可永久YIELD，普通不同随机状态也可能一直无可见几何差异；所选规则放弃“仅随机到期即可启动”。持续让行可能使车速低于5甚至停车，排队或未通行须保留。它针对尚未开始的模糊竞争启动，不能解决已有机动、SUMO/几何通道差异、形成、恢复、UNKNOWN物理覆盖或速度恢复。本规则只支持更保守的启动权限结论，不支持整体安全或交通收益结论。

**最小待测负向集合。** 新版本先用固定的旧局部输入序列验证下列边界；不改写旧版本测试或旧结果：

1. 当前一直ambiguous、guard被测试桩明确设为接受：在deadline前后连续推进，同deadline、同rng和draw_count=1，到期仍blocking且无prepare/plan。低于5m/s的同序列也必须继续推进到新YIELD而不重抽。
2. 用既有私有状态1/1与1/2、原0.1s观察和0.5s行为格，长期保持镜像竞争：两车均不能因同格到期生成plan。应记录未通行，不将测试结论命名为“双车成功”。
3. 同episode先在原等待内转成ego_visible_front再转回ambiguous：不能缩短原等待；到期成为ego_visible_front时可解除gate；随后prepare期间重新ambiguous应阻断并清prepare。可见前后优先阈值的±2m边界保留。
4. 到期后进入原stable-clear：第一个clear观测仍阻断，满原1s连续clear才结束episode；断帧与UNKNOWN不能提前释放。另一个clear且原guard接受的合法目标仍可沿原preview选择，不继承错误目标的等待。
5. HARD_YIELD到期不释放、hold guard拒绝时保留原回退动作和原因、原emergency不被舒适裁剪、已active的plan不被清掉。guard阻断测试应在**真正已解除R5 gate**的可见几何下执行，不能以始终ambiguous输入声称已走到candidate guard。

原 [test_phase5_r5_controller.py](D:/yanjiu1/keyan1/variants/phase5_r5_completed/tests/test_phase5_r5_controller.py)的长期ambiguous最终ELIGIBLE、两delay同格启动、低速到期ELIGIBLE等断言是旧规则的有效证据；新版本须明确改成所声明的新语义。原clear确认期间ELIGIBLE且blocking的测试应保留，不可机械替换全部ELIGIBLE。原“expired guard blockage”用例需设置可见ego-front或完成clear，以免只验证了新的R5阻断却冒充guard覆盖。

### 方案B：精确核验可行速度上端后返回原上端（本单元不实施）

仅在 `_comfortable_speed` 中先用**同一个原停止表达式、同一个可用距离、同一个原加速度保守量**检验上端 `min(5,max_speed)`；已通过则直接返回该上端，否则仍使用原可行lower二分。目标5、精确基础门槛5、响应/jerk/制动假设和空间界均不变，不加容差、不把5以下速度四舍五入为5。它可以删除“可行5却因数值下偏被基础精确门槛阻挡”的局部缺陷。

**明确代价及反例。** 此修正不保证R5等待后的物理速度恢复；有慢前车/较短停止空间时上端校验必须失败；加速度非零时不能遗漏原响应距离。对于本来因数值下偏没有plan的双车off例，恢复候选启动甚至可能暴露同时换道和新的驾驶失败，不能称作成功。必须另行对端点刚可行/刚不可行、非零执行器加速度、速度恰等于5及实质低于5建立独立测试和车辆边界证据。与方案A同时改会混淆“保守阻断”与“释放数值误阻断”的作用，因此留待下一入口。

## 尚未证明的事项

本报告未证明任一方案可使speed_floor通行，未证明随机互斥、有限时间恢复或全队编队，未运行新的6seed/heldout选择。方案A必须容许无改善与等待失败；方案B也必须保留可能新增的双车启动失败。reentry和UNKNOWN仍需先登记与规则匹配的新物理覆盖，不能通过重选旧seed、改写旧案例脚本或移除失败前缀关闭缺口。阶段6入口继续关闭。
