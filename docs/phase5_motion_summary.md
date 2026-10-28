# 阶段5封存开发包的独立运动汇总

本单元补齐预登记的逐车速度、停车时长和实际纵横向加速度/jerk呈现，不运行车辆实验、不改变参数、不参与方法选择。只读取已封存A/B1/B2开发包，未读取heldout性能。实现位于 [phase5_motion_summary.py](/D:/yanjiu1/keyan1/tmp/phase5_motion_summary.py)，只用标准库，不导入项目控制器、仿真器或积分器。[独立复审](/D:/yanjiu1/keyan1/docs/phase5_motion_analysis_review.md) 已闭环，无未解决P1/P2，另有独立合成积分与拒绝探针、产物完整文件集及哈希检查；随后相同稳定脚本完成B两包汇总。

每车速度来自主轨迹 `steps.samples` 的0.01秒物理状态，初态和最终样本均计入，控制记录边界不重复计点。速度时间均值采用相邻速度梯形积分除以实际观察时长；min/max包含初态和末帧。停车时长为左阶梯积分：若区间左端速度小于等于既有 `phase2.stopped_speed_tolerance_mps=1e-6`，计入该完整物理小步时长；末帧单独到达零速不增加虚构时长。这是已保存物理网格上的数值统计，不是连续时间解析积分。

逐车实际纵向加速度上下界、横向加速度绝对峰值及加速度相邻差分jerk，从保存的实际诊断逐小步复核，包含初始实际加速度和跨控制记录边界。受控车辆的标准 `validation.metrics.actors` 完整带出，并与0.01秒观察的6项极值核对；该标准指标另由正式整包重放从轨迹重算。事件外生车辆虽有物理轨迹，标准runner只为 `case.controlled` 生成指标，因此它们保留本单元直接统计，但标准指标明确为null，不能伪称标准校验通过。0.005秒固定命令细积分单独汇总实际jerk，沿用已有2m/s³舒适阈值，不改变边界；它不是重新闭环控制试验。

完整运行保留 `full_window`；失败或截断运行只报告实际公共完整物理前缀，所有整窗口量为null。失败尾有缺车step时，明确记录被排除行及可用车辆，不能把不同车辆不齐的时段拼成共同完整窗口。缺控制记录、缺物理小步、重复时间、末状态不等于末样本、非有限值或未换行的截断JSONL均拒绝。当前实际A开发包各案例均完整，此处的失败前缀行为由合成测试验证；细积分摘要当前要求其保存序列完整，不为缺尾细积分补值。

补充的原始局部覆盖来自 `detection.default.frames`：成员并集比例 `fleet_coverage_fraction` 和最大局部组比例 `largest_group_fraction`，按控制网格左阶梯计算时间均值并保留瞬时峰值。它们包含未经5秒持续确认的瞬时局部组，不能冒充预登记确认后覆盖C、整队形成或恢复成功；对确认区间的完整报告沿用已有正式比较脚本，不更改评分。

来源检查逐项验证包 `evidence_hashes.json` 所列文件、内层源码/输入清单及实际消费文件的SHA256，读取结束再次核对消费文件与外层清单未变。该检查只覆盖清单列出的成员，未在本脚本中比较目录全部实际文件集合，也不替代正式整包的源绑定、动作/记忆/检测/SUMO语义重放。输出拒绝覆盖旧目录，保存本脚本快照、调用、摘要、逐车CSV及自身产物哈希；摘要不包含新输出目录或运行时刻，因此同脚本快照可在不同cwd生成逐字节一致摘要。

必要测试先留下缺模块RED，再实现GREEN；首次真实A汇总暴露了把事件外生车误当标准受控指标范围的错误，失败目录保留为 [首次汇总失败](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T195953676534Z_e68164d6/failure.json)，它是分析器错误，不是车辆试验失败。为该错误及空失败覆盖补了针对性RED后修复。最终 [13项测试](/D:/yanjiu1/keyan1/tmp/test_phase5_motion_summary.py) 覆盖初末去重、梯形积分、停车阈值等号/左端边界、完整与失败前缀、受控指标范围、失败尾、缺记录/小步/末帧/换行拒绝、原始覆盖定义及0.005秒跨段jerk。最终GREEN日志为 [200242398932Z](/D:/yanjiu1/keyan1/results/operations/20260912T200242398932Z_phase5_motion_scope_green_42eb310c/result.json)，13项通过。

A固定开发包是 [20260912T180218593655Z_1e4080c3](/D:/yanjiu1/keyan1/results/phase5/runs/20260912T180218593655Z_1e4080c3/validation.json)。独立汇总21个变体、111个物理车辆条目，其中103个受控条目的标准指标一致，8个事件外生条目标准指标明确null。347个清单文件验证通过。主 [summary.json](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T200305018866Z_b3ea51c3/summary.json) 与 [actors.csv](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T200305018866Z_b3ea51c3/actors.csv) 保留逐车原值。下面仅显示每个45秒随机案例逐车时间均速的等权均值（m/s），不使用它重新排序方法：

| seed / 车辆数 | A OFF | A ON | 每车停车时长 |
|---|---:|---:|---:|
| 5101 / 3 | 4.997956197555324 | 4.946035568098598 | 全部0秒 |
| 5102 / 3 | 5.004711853306261 | 5.007984361415066 | 全部0秒 |
| 5201 / 6 | 4.9970481966143225 | 5.062595426981445 | 全部0秒 |
| 5202 / 6 | 5.00581584448239 | 5.047708469669053 | 全部0秒 |
| 5301 / 12 | 4.9996196108314495 | 5.03387130352822 | 全部0秒 |
| 5302 / 12 | 4.997648476791478 | 5.072326851932321 | 全部0秒 |

5101的0.05秒控制版本均速为4.946044966100462m/s，逐车停车也全0。速度有增有减；零停车不是形成证据。源包 `engineering_passed=true`、科学 `passed=false` 原样保存，不因本单元通过而改变。

从 `D:/yanjiu1` 不同cwd执行主产物的脚本快照生成 [快照重放](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T200425963695Z_408aae6d/summary.json)，主/重放的summary、CSV和脚本逐字节一致，各自产物清单全通过。摘要SHA256为 `485340e0578293b5f831c062b90f27e1e93dc1eeacb82b25794e7bbc9b6b3b74`；[独立比较记录](/D:/yanjiu1/keyan1/results/phase5/motion_verification_A_20260912T2008/verification.json) 附每车均速、停车原值及快照哈希。正检、快照重放、比较操作日志分别为 [200304823659Z](/D:/yanjiu1/keyan1/results/operations/20260912T200304823659Z_phase5_motion_a_summary_final_4a8a5bcc/result.json)、[200425770698Z](/D:/yanjiu1/keyan1/results/operations/20260912T200425770698Z_phase5_motion_snapshot_replay_4eec0d59/result.json)、[201012955211Z](/D:/yanjiu1/keyan1/results/operations/20260912T201012955211Z_phase5_motion_a_verify_f48bf633/result.json)，均exit0。

可重放调用（PowerShell，新的输出目录自动生成）：

```powershell
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S 'D:/yanjiu1/keyan1/scripts/run_logged.py' --label phase5_motion_replay --timeout 180 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S 'D:/yanjiu1/keyan1/results/phase5/motion_20260912T200305018866Z_b3ea51c3/phase5_motion_summary.py' --workspace 'D:/yanjiu1/keyan1' --run-dir 'D:/yanjiu1/keyan1/results/phase5/runs/20260912T180218593655Z_1e4080c3'
```

B1与B2使用相同脚本，各汇总21个变体、111个物理车辆条目，103项受控标准指标一致、8个外生条目标准指标null；各349个清单文件核对通过。每包均由输出的脚本快照从不同cwd重放，再逐字节核对summary、CSV和脚本，全部一致。主包与快照重放分别为：

| 方法 | 主汇总 | 快照重放 | summary SHA256 |
|---|---|---|---|
| B1 front_first | [主产物](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T201601690336Z_079fd3f6/summary.json) | [重放](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T201723487443Z_f6779312/summary.json) | `e4b66601674c3378efb9e2c338c0dd604ed007933f4eee175c969b8bf185ffdd` |
| B2 corner_first | [主产物](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T201601731901Z_d5c31d76/summary.json) | [重放](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T201723501954Z_de811af0/summary.json) | `0c473bf452d75748a9239b83eee0467dabe8c91c8db80410dd9dfe8d5ad8dce3` |

B1 [比较与逐车原值](/D:/yanjiu1/keyan1/results/phase5/motion_verification_B1_20260912T2021/verification.json)、B2 [比较与逐车原值](/D:/yanjiu1/keyan1/results/phase5/motion_verification_B2_20260912T2021/verification.json) 各附脚本与记录哈希。两个正检、两个快照重放和两个比较日志均exit0，操作目录名分别以 `20260912T201601468807Z_phase5_motion_B1_summary_be06808b`、`20260912T201601520006Z_phase5_motion_B2_summary_bb8eab50`、`20260912T201723270389Z_phase5_motion_B1_snapshot_replay_9a1897e3`、`20260912T201723289893Z_phase5_motion_B2_snapshot_replay_b81f5727`、`20260912T201904305061Z_phase5_motion_B1_verify_607704a7`、`20260912T201904306065Z_phase5_motion_B2_verify_4f2ff397` 命名，位于 `results/operations`。

同一45秒随机窗口的B ON均速如下；其定义与上表A完全相同。两B各随机on/off及half-control中每辆车停车时长全0秒。A/B两B全部OFF逐车运动统计相同，保留在各CSV与JSON；该一致性不等于ON更好。

| seed / 车辆数 | B1 ON均速m/s | B2 ON均速m/s |
|---|---:|---:|
| 5101 / 3 | 4.946035568098598 | 4.946035568098598 |
| 5102 / 3 | 5.007984361415066 | 5.007984361415066 |
| 5201 / 6 | 5.060776469439308 | 5.062595426981445 |
| 5202 / 6 | 5.052411104490395 | 5.046640405865173 |
| 5301 / 12 | 5.042033273349802 | 5.029800444489442 |
| 5302 / 12 | 5.0760340067678404 | 5.066742141485721 |

三个方法的源包科学 `passed=false` 均原样保留。本单元不选择B、不读取heldout、不扩大试验，运动摘要不能替代整队形成和恢复指标。阶段5的实现与科学未通过条件仍见 [需求矩阵](/D:/yanjiu1/keyan1/docs/phase5_requirement_traceability.md)。
