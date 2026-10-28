# 阶段5F验收：测得速度下的有限换道时长候选

状态：**实现、受影响回归、三组预登记正式实验和标准语义重放已完成；阶段5科学验收仍未通过，阶段6/7/8不开放。** 本单元只在R5开启且可见车道优先开启时枚举5.0、7.5、10.0 s候选，使用当前测得正速度，并让每个候选继续通过原R5竞争门和未修改的 `verify_candidate` 全时域守卫。

## 前置条件、隔离与登记

[只读前置核验](D:/yanjiu1/keyan1/results/phase5f/prerequisites_20260913T155330954265Z/verification.json)重新计算5E最终交付、正式run/replay/comparison、114份父源码及输入，确认5E科学状态仍为false、阶段6仍关闭。核验wrapper为 `results/operations/20260913T155330131336Z_phase5f_parent_prerequisites_8571e748`，verification SHA256为 `8a5d23dea58f7bfb93b8f51d90fe3bdc04f24a32c035e321c78a0266383d6ee4`，证据清单SHA256为 `da4fd63310b4424b1c7395d0ac7c94d0d288c8b8cb71dda8297021c1a8f30f6d`。

仓库没有Git HEAD，不能建立Git worktree或提交。按既有隔离约定，从5E正式 `code_snapshot` / `input_snapshot` 创建[独立5F版本](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/clone_provenance.json)，拒绝覆盖已有目标；克隆wrapper为 `results/operations/20260913T155340482705Z_phase5f_isolated_snapshot_f0fa4556`。原8案例SHA256为 `46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20`，5C扩展SHA256为 `a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a`，二者始终分开。

[预登记计划](D:/yanjiu1/keyan1/docs/phase5f_adaptive_duration_plan.md)在生产实现前冻结，SHA256为 `13ab0a72be49305cc842e7db1c3eef05d3683122ffd4b2861bd4eac6c9c2ea7a`。设计与实施计划SHA256分别为 `ca5eed45e82b6dcc16fabf57c2d739ea3c79b999d262c31fa4968163c7e0e6bc` 和 `d434a0a7a4cddb4aeca28ac770c217b72d5fd99f30a132738ba13d893e963b13`。

实现前只读扫掠保存在[父状态扫掠](D:/yanjiu1/keyan1/results/phase5f/parent_sweep_preregistered_20260913/sweep.json)，数据SHA256为 `85fe4ca6eb77def3453a01cf077c2adbadd3fbcae7e742d3fb61c5bdae65d8c5`，清单SHA256为 `44794846a3fcd4f7ff8e27d2e83c17bb72c1ec75840b1bcbc426d5b7ee00c0ea`。真实1.70116227和1.84939749 m/s父状态的三个时长均满足运动学必要条件，却全部被原R5邻车可达占据判断阻断；4.51122719 m/s父状态的5/7.5 s通过原守卫，10 s因更长邻车可达域被拒绝。扫掠只描述封存父状态，不算闭环车辆成功。第一次扫掠因脚本误取仿真参数而非策略参数失败，保留在 `results/operations/20260913T155657361313Z_phase5f_parent_low_speed_sweep_9a317f6d`；修正后的wrapper为 `.../20260913T155748544980Z_phase5f_parent_low_speed_sweep_retry_80315256`。

## 实现与边界

[low_speed.py](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/noa/low_speed.py)实现确定性的候选数学；[controller.py](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/noa/controller.py)只在 `phase5f_enabled && r5_enabled && r5_lane_priority_enabled` 时进入新路径；[r5.py](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/noa/r5.py)仅把相对速度搜索半径的固定5 s替换为候选自身时长。固定模式、R5-off和关闭车道优先的waiting基线保持原路径。

冻结车道宽3.3 m、轴距2.7 m、最大转角40度后，二段二次Bezier的峰值参考横向加速度及必要速度为：

|持续时长|峰值参考横向加速度|必要速度下界|
|---:|---:|---:|
|5.0 s|0.528 m/s²|1.3034431025565734 m/s|
|7.5 s|0.23466666666666666 m/s²|0.8689620683710490 m/s|
|10.0 s|0.132 m/s²|0.6517215512782867 m/s|

0速与低于全部下界的状态仍拒绝。所有可建候选按时长升序先过R5、再过原守卫；只取最短safe候选，无safe候选不准备、不提交。未改纵向请求、邻车硬加速度可达区间、横向假设、道路重建、车身余量、舒适/硬界、紧急制动、形成判据、随机链或局部博弈参数。

[源码冻结](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/phase5f_source_freeze.json)绑定10个允许变化文件，SHA256为 `4982d94ee84126df5e80dbe4f8c761185926fd1bbd89f4678ebd4999502acddf`。

## TDD与回归证据

新增16项数学、控制器和实验/重放绑定测试全部通过，wrapper为 `variants/phase5f_adaptive_duration/results/operations/20260913T160750166692Z_phase5f_new_tests_green_3e15c69f`。对应RED证据包括缺少数学模块、旧控制器无法低速构造候选、缺少CLI/输入绑定；均保留在该版本的 `results/operations` 下。控制器第一次GREEN的两项失败来自测试慢前车位于新10 s R5时域内，调整夹具而未缩小R5范围后通过。

首次受影响回归为240项、0失败、1错误：旧测试mock仍使用两参数 `expected_variants`，新runner/replay调用边界未保留旧签名，日志为 `results/operations/20260913T160912836916Z_phase5f_affected_regression_508551ec`。两处仅在双策略均fixed时调用旧签名后，聚焦继承测试通过，最终同一240项选择为**0失败、0错误、0跳过、源码前后不变**；wrapper为 `results/operations/20260913T161716818841Z_phase5f_affected_regression_retry_5ffc1314`，耗时305.703 s。

## 正式运行与重放

三包使用同一5F源码与公共协议输入，只有预登记的案例包或顶层模式不同：

|包|变体/完整/失败前缀|记录/工程|run manifest SHA256|标准重放 manifest SHA256|
|---|---:|---|---|---|
|[扩展fixed](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400640291Z_a5586029/validation.json)|6 / 5 / 1|true / false|`6859790f878a5c4143f554ebd8274c526c7a6f45b233cbbfcc914119f2a488a4`|`b369cd03f0fe387f079e8d35e64db5d62bc4ab566abb7202d33de944a0374250`|
|[扩展adaptive](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400652574Z_9f6cc9d8/validation.json)|6 / 5 / 1|true / false|`da5f87a7abb899fa8c92aaf32696d9f2b275452452703e4e6c3ed70208a23e03`|`46a787b9e14d5703f5f1d16395f2955374606413f9591ccb217dc51d7590152f`|
|[原8案例adaptive](D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400649059Z_207be322/validation.json)|17 / 13 / 4|true / false|`5be26694d9d123b0b5c37fa9598626fdfbe32c3dd9bbbcdd75daf54e25bc0683`|`aaa2d04790bc37f2ab62dc84e2f30579efd42c6043e2048533a2577c767ceb4b`|

三份通过的标准重放分别为 `.../replays/20260913T163527576957Z_4632477a`、`.../replays/20260913T163527576957Z_6c53edf8` 与 `.../replays/20260913T164250928637Z_74f0aa54`；errors/unstarted均为空，来源前后源码相同，失败前缀仍按失败重建。

第一次并行启动三重放时，原17包在创建replay目录时与另两进程争用共享 `replays/latest.json.writing`，以PermissionError退出；它未读取到语义比较阶段，操作日志 `variants/phase5f_adaptive_duration/results/operations/20260913T163527151469Z_phase5f_replay_original17_adaptive_8dfbec93` 和不完整replay目录原样保留。两扩展重放结束后，原17包顺序重试通过，wrapper为 `.../20260913T164250585641Z_phase5f_replay_original17_adaptive_retry_118bdf0c`。该事件是操作层共享指针竞争，不是车辆或证据语义失败。

## 配对结果

[最终配对比较](D:/yanjiu1/keyan1/results/phase5f/comparison_formal_20260913T1659_final_v2/comparison.json)在读取前后复核4个run、4个replay和源码冻结，要求5E到5F恰为10个源码、4个输入变化；扩展fixed/adaptive输入逐字相同，跨原始/扩展包只允许 `frozen_r5_cases.json` 不同。三个正式包源码完全相同。两个扩展非目标OFF及waiting轨迹逐字相同；原矩阵全部8个R5-off轨迹与5E逐字相同。比较清单SHA256为 `17d799e9082bdd2b5b3a0fef27ca7bd191ea3e9fb6a39aee20016deeb0712c45`。

正式自适应轨迹中的候选事实：

- 扩展包评估5/7.5/10 s候选113/80/80次；80组各时长均由R5阻断。5 s通过守卫33次并被选33次；被选速度范围4.24054327--8.0 m/s，提交计划速度范围4.58247558--7.75 m/s。
- 原始包评估5/7.5/10 s候选507/420/420次；420组各时长均由R5阻断。5 s通过守卫87次并被选87次；被选速度范围3.79066940--8.0 m/s，提交计划速度范围4.15332082--7.75 m/s。
- 正式轨迹中没有运动学候选拒绝，也没有到达守卫后的拒绝；7.5/10 s均未被选择或提交。它们不是“失败的轨迹”，而是在这些观测下未越过更长R5时域。计数按决策拍，不是独立试验数。

相对fixed/5E的实际车辆变化：

|配对场景/车辆|新提交|新完成|完成时刻|均速变化（m/s）|
|---|---:|---:|---:|---:|
|扩展 `r5c_gradual_three_r5_on` lower|22.5 s，5 s，4.58247558 m/s|1|26.98 s|2.79008690 → 4.39655501|
|原始 `r5_competing_r5_on` left|22.5 s，5 s，4.58287316 m/s|1|26.98 s|3.38231133 → 3.56218911|
|原始 `r5_entered_priority_r5_on` ego|15.5 s，5 s，4.30577954 m/s|1|19.96 s|3.99820094 → 4.06582000|
|原始 `r5_reentry_r5_on` ego|15.0 s，5 s，4.15332082 m/s|1|19.47 s|3.11837023 → 4.59611260|
|原始 `r5_speed_floor_r5_on` left|17.5 s，5 s，4.40686349 m/s|1|21.97 s|2.69914549 → 3.27457681|
|原始 `r5_front_priority_r5_on` left|19.0 s，5 s，4.80444499 m/s|0|观察窗20 s结束时计划仍在执行|3.09021238 → 3.09150451|

扩展总完成换道4→5；原始矩阵9→13。以上是变体—车辆变化，不是独立随机样本，也不能合并成成功率。所有新增提交车辆的comfort/tracking均通过；但未受新策略影响的 `r5_front_priority_r5_off` 两车仍保留既有comfort/tracking失败。

扩展的 `r5c_gradual_three_r5_off` 27拍碰撞前缀，以及原始矩阵 `r5_competing`、`r5_quantized_private_states`、`r5_same_private_state` 各28拍和 `r5_speed_floor` 27拍的R5-off原生SUMO碰撞/teleport报告，与对照轨迹逐字相同。两侧任一不完整时全窗差值在比较文件中强制为null，没有把前缀均值与完整窗比较。

## 验收结论与限制

- **实现与测试交付：通过。** 有限候选、模式隔离、实际时域R5、原守卫、输入/元数据/重放绑定均已实现并由240项受影响回归验证。
- **候选可行性：有限通过。** 正式闭环证明测得速度低于旧5 m/s时，5 s候选可通过原R5与守卫并提交；没有证据表明7.5/10 s在本批观测中可用。1.70--1.85 m/s父状态仍由R5阻断。
- **车辆完成：有限增加。** 扩展配对新增1次、原始配对新增4次完成；另有1项在观察窗末仍执行。它们只对应冻结初态和确定性轨迹。
- **形成与恢复：未通过。** 四包比较中的全队形成与局部形成成功均为0；没有新增扰动恢复、并排无参考或UNKNOWN恢复证据。
- **科学验收：不通过。** 旧碰撞前缀、front-priority OFF舒适/跟踪失败、无形成和缺少独立重复均保留。
- **阶段6授权：false。** 阶段6/7/8继续关闭。

没有通信、车型真值、真实ID优先、邻车私有意图、全局槽位或中心调度。R5输出仍只是本车基于有限局部观测的保守判断，不是邻车承诺；重放通过也不把失败前缀改成安全驾驶。
