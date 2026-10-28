# 阶段5E验收：精确可行速度上端

状态：**端点实现、受影响回归、固定实验和标准重放已完成；阶段5科学验收未通过，阶段6不开放。** 本轮只修复 `_comfortable_speed` 在配置上端已满足原停止表达式时仍返回二分下界的问题。参数、5 m/s换道准入、5 s换道轨迹、R5/博弈、安全守卫和邻车可达包络均未改变。

## 前置条件与隔离来源

[只读前置核验](D:/yanjiu1/keyan1/results/phase5e/prerequisites_20260913T120339903006Z_27c44d80/verification.json)重新计算阶段5D两正式包的113份源码和11份输入，确认两个映射相同、快照逐文件匹配、阶段5D源码冻结一致、最终交付39文件集合/哈希完整，并保留 `scientific_accepted=false`、`phase6_allowed=false`。verification SHA256为 `90a9748b8e6e28971e812ce70f415fffa02540f2d563156346c1e7c48c6f0a27`。

第一次前置核验因新核验脚本错误地按文件名排除了交付包内嵌套的一个 `evidence_hashes.json` 而退出1；正式包本身没有哈希错误。失败日志保留在 `results/operations/20260913T120254804556Z_phase5e_parent_prerequisites_5955dd32`。修正为只排除交付根清单后，新目录核验退出0，wrapper为 `20260913T120339645205Z_phase5e_parent_prerequisites_retry_7444c465`。

仓库没有git HEAD，不能创建git worktree；按项目既有隔离约定，从5D两份相同正式快照创建[独立5E版本](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/clone_provenance.json)。克隆脚本拒绝覆盖，恢复原8案例 `parent_frozen_r5_cases.json`，并把5C扩展单独保存为 `phase5c_extension.json`。原8案例SHA256为 `46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20`，扩展SHA256为 `a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a`；5D目录保持只读。

## 根因、实现与参数

正式目标速度和最低换道速度均为5 m/s。原函数总从二分的`lower`返回，即便上端5 m/s的同一停止表达式只需17.707942307692306 m、可用28.05 m，仍返回4.999999925494194 m/s。严格 `vx >= 5` 随后会在下一控制拍清除prepare。该链路已在阶段5B诊断中定位，本轮又以真实函数复现。

新实现先用完全相同的停止距离与速度反馈距离表达式检查配置上端：可行则精确返回5.0；不可行仍走原二分并返回保守下界。距上端可行边界少 `1e-6 m` 时，新旧均返回4.999999776482582 m/s，说明没有添加容差或强放行。

控制语义只改[controller.py](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/noa/controller.py)这一分支；实验清单只增加本轮[预登记计划](D:/yanjiu1/keyan1/docs/phase5e_exact_endpoint_plan.md)，继承的5D兼容测试则改为验证新默认/fixed逐字一致，并把相对5C差异限制为4.9/5.0 m/s、仅纵向请求、幅度不超过原几何容差，记忆/诊断/转向相同。[源码冻结](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/phase5e_source_freeze.json)SHA256为 `48128cf035ebe95ebdee79986e2043eea706e934d2012ecc48d513a6828accee`。

参数变化：**无**。尤其没有降低5 m/s门槛、延长5 s轨迹、增大加速度、缩小邻车占据包络或改变局部博弈权重。

## 测试证据

TDD证据完整保留：

- 端点RED：2项中精确上端测试以 `4.999999925494194 != 5.0` 失败，wrapper `variants/phase5e_exact_endpoint/results/operations/20260913T120439300056Z_phase5e_endpoint_red_f5ac11c9`。
- 端点GREEN：2/2通过，wrapper `.../20260913T120514456003Z_phase5e_endpoint_green_12422283`。
- 输入绑定RED/GREEN：先因计划不在`INPUTS`失败，增加绑定后3/3通过，wrapper分别为 `.../20260913T120533040109Z_phase5e_input_binding_red_6050ebca` 与 `.../20260913T120600153039Z_phase5e_input_binding_green_8390e31f`。
- 首次受影响回归有效失败：191项中40个错误均为隔离副本缺少测试临时目录，5个失败均为旧“逐字等于5C”断言捕获预期端点差异；源码保持不变。日志为 `results/operations/20260913T120711258708Z_phase5e_affected_regression_0a3bf86b`。
- 修复夹具并收紧兼容性断言后，同一选择的**191项全部通过，0失败、0错误、0跳过，源码前后不变**；wrapper `results/operations/20260913T121118654980Z_phase5e_affected_regression_retry_72f5c23e`，耗时389.766 s。未受影响模块沿用5D已封存347项0skip证据，不重复旧车辆套件。

## 固定实验结果

新正式包为[20260913T121814146616Z_12a1dc15](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/results/phase5_r5/runs/20260913T121814146616Z_12a1dc15/validation.json)。17/17预登记变体均启动并封存，13项完整、4项OFF为原生SUMO失败前缀；记录通过，整体驾驶/工程不通过，科学状态未放行。运行中源码变化列表为空。run evidence manifest SHA256为 `8e6c6ffe4a94a0bb06c1f52ce50ae263dd4a84a017908667072cc63255e6ab3c`。

[固定父包与5E配对比较](D:/yanjiu1/keyan1/results/phase5e/comparison_20260913T1244_exact_endpoint_final/comparison.json)绑定同一原8案例、物理初态、私有状态、参数、道路、时钟和17变体矩阵；两侧标准重放已绑定。比较包5文件清单精确，manifest SHA256为 `01a6904fb556226a399d770359028d13dd17e2d116f6bb2ce68d468a4542ce79`。

端点变化在 `r5_speed_floor` 场景产生了真实分叉：

|分支|父版本|阶段5E|解释|
|---|---|---|---|
|OFF|30 s完整；两车都只在0 s短暂prepare，0次提交、0次完成|两车0 s prepare、0.5 s同时提交；2.8 s在中间车道原生碰撞，保存2.6 s完整前缀；0次完成|修复消除了数值阻塞，也暴露无局部竞争处理时的真实同时换道风险；性能量不能用2.6 s前缀与30 s全窗比较|
|R5 ON 左车|0次提交/完成；30 s均速2.58813216 m/s|0次提交/完成；30 s均速2.69914549 m/s|仍由可见车道优先/R5让行，未形成|
|R5 ON 右车|0次提交/完成；30 s均速2.65231532 m/s|0.5 s提交，4.98 s完成1次；30 s均速4.95231510 m/s|端点修复与既有局部优先共同允许单车通过，但只是一固定初态的局部结果|

新ON完整运行的右车最终速度4.999999994 m/s，最低4.45065337 m/s；左车最终2.55122899 m/s。该分支全队形成和局部形成仍均为false。除`r5_speed_floor`外，其余15个变体的运行状态、完成换道数和形成布尔量均未改变；多处约1e-8 m/s量级轨迹差保留，未解释为收益。

父包14项完整、3项OFF失败；5E为13项完整、4项OFF失败。新增失败不是测试基础设施错误，而是明确的 `SynchronizationError: SUMO collision or teleport reported`，原始警告为两车在 `upstream_1`、2.80 s发生碰撞。修复一个数值缺陷因此既带来ON局部通行，也让OFF安全结果恶化；二者都必须保留。

## 重放、结论与未通过条件

[5E标准重放](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/results/phase5_r5/replays/20260913T122921286694Z_13a9cac5/validation.json)17/17通过，errors/unstarted均为空，来源前后相同，manifest SHA256为 `d1dee65f5b53363c79f4fe949e8d8fbf0e92bd9248f167699904fe6e6f05b2e8`。4个失败前缀仍按失败重现，重放通过不把它们改成完整驾驶。

已验证事实：精确可行上端缺陷被修复；原不可行分支仍保守；固定速度地板场景的R5 ON右车由0次变为1次换道。未验证事实：全队形成、保持、扰动恢复、并排无参考、UNKNOWN恢复、公平、互斥证明、交通/能耗收益和一般安全。阶段5D在真实clear时的1.70--1.85 m/s低速仍远低于5 m/s，本轮没有改变最低速度或慢前导约束，也没有把5D扩展重跑后择优解释。

因此**阶段5科学验收仍不通过，阶段6/7/8保持关闭**。下一入口仍在阶段5：单独预登记并研究通过原模型、可见性、碰撞与舒适守卫的低速/更长时长换道候选；不能用本轮单车通过替代形成证据。

