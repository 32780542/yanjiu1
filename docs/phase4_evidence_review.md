# 阶段4证据与代码质量审查

审查状态：**需修复两项提前失败重放缺陷；正常完整记录的证据核对通过。** 本结论不放行M1。只读审查生产代码、配置与测试；独立复现及日志写入 `results/phase4/reviews/evidence/`。审查对象为首次真实SUMO冻结运行 `20260910T175330533300Z_84f34950` 及其对应实现。

## 需修复的问题

1. **P2：诚实保存的部分末区间不能独立重放。** `experiments/phase4.py:54–55,76` 只把含所有车辆完整积分/诊断的末条纳入 `recorded_intervals`，但 `trace.jsonl` 仍包含部分末条。`experiments/phase4_replay.py:29–33,53–62` 对每条都重算完整tick，并要求整个对象完全相同；只识别“所有积分和读回均已产生”的失败末区间。`phase4_replay.py:74–80` 又把部分末条计入隔离审计的预期范围，与原生成审计只消费完整记录的范围不同。

   独立复现：两台受控车运行0.3 s，在已完成0.1 s后，对后处理车辆的第二次决策注入RuntimeError。原trace保留2条，末条保留所有输入和已先处理的ego决策，`recorded_intervals=1`。移除注入后独立重放得到 `ValueError: interval2: fields differ`，隔离重放得到 `Truncated or extra isolation audit`。已有状态/决策保留修复有效，但不能据此宣称部分失败可重放。完整物理区间后发生SUMO碰撞的19步压力案例不受此缺陷影响。

   建议：明确记录已完成区间、完整物理区间、部分尾记录和失败阶段；对部分尾记录只复算确已产生的输入/决策/动作/子步并检查完整性，隔离审计使用同一明确范围。增加“第二actor决策/积分异常后的独立重放”及尾记录删改拒绝回归，不能通过删掉部分记录来修复。

2. **P2：中断退出绕过索引及哈希收尾，使已有完整前缀无法通过标准run重放。** `experiments/phase4.py:65–68` 在写完失败信息后立即重抛KeyboardInterrupt，跳过区间统计与审计；`phase4.py:180–182` 要到case返回后才把目录加入运行元数据；`phase4.py:219–221` 只在普通完成路径生成证据哈希。`phase4_replay.py:97` 无条件读取该哈希文件。

   独立复现：相同短case在第二区间注入KeyboardInterrupt。独立失败目录与源码快照、两条原始trace均保留，但顶层 `case_trace_directories=[]`，且无 `evidence_hashes.json`；标准 `replay_run` 直接FileNotFoundError。问题不仅是预期非零退出，而是连已完成前缀也不能审计。建议在执行前登记子目录，并在中断异常收尾路径生成失败状态、统计、可审计前缀和最终哈希；原中断继续按失败退出。

复现程序、原始日志及结果：`probe_failures.py`、`probe_failures.log`、`probe_failures.json`；部分case在 `partial_second_decision/`，中断run及独立重放失败目录分别在 `interrupt_runs/`、`interrupt_replays/`。全部使用登记Python3.12的 `-I -B -S`；注入仅由审查脚本mock完成，未改生产文件。

## 已核实的实跑失败解释

首次实跑 `merge_no_gap` 是**初始化失败，尚未测试驾驶**：29车均插入，但在安装预定初态的SUMO t=0.10发生remoteControl碰撞报告；t=0.20初始化读回因20个全局碰撞报告终止，物理推进为0/160。`merge_no_gap/base/bootstrap.json` 保留ego读回和其余车辆not_read状态；原日志包含本应为正2 m车身间隔对应的 `gap=-0.50`，也有跨车辆顺序的更大负gap。生产vType未显式设定minGap，安装次序也与最终位置次序不同，均需在运行平台层定位。现有证据不能称“无空隙时控制器停车失败”，也不能用它证明碰撞不可避免。原目录必须保留，修复平台初始化后另开尝试。

`stop_restart`、`observed_cut_in`、`merge_gap_after_queue` 的舒适性或驾驶要求失败，以及 `normal_lane_change` 的采样减半差异，是保持原阈值的真实门槛结果；本审查不建议调参掩盖。`urgent_braking_stress` 在第19个完整物理区间由SUMO碰撞终止，完整前缀可重放且驾驶失败保持失败；这是与上述“无物理轨迹”不同的失败类型。

## 通过的核验与边界

- 独立校验266个证据文件SHA256及清单覆盖范围、74个源码/配置快照的启动哈希，无缺失或差异；源码清单包含 `noa/`。首次运行记录了源代码中途变化为空。
- 冻结注册表中32项phase4及phase4_experiments参数与配置数值一致，单位、来源、位置、状态、理由完整。本文没有更改阈值或把试验策略宣称为论文标定。
- 16个case变体的全部已有轨迹逐子步检查：每车初态承接、子步数、物理时间增量、命令dt/seed、SUMO推进次数与时间偏移一致。无空隙初始化失败的0条轨迹按0条报告，没有计作驾驶覆盖。
- 独立按实际加速度有限差分复算所有受控车的actual jerk，并按执行器状态差分复算actuator jerk，与输出指标一致。例如停止再起步约50 m/s³、稀疏队列约100.47 m/s³的实际jerk没有被执行器约2 m/s³替代。舒适门槛使用actual jerk。
- 主门槛要求真实SUMO、完整case集、所有普通case通过、全变体记录通过、故障注入拒绝、至少一个可见信息正例及源代码稳定。普通case失败不会因预声明压力case排除规则而被掩盖；本次正例72次，普通case9/14通过，最终gate失败、无下一阶段放行。
- 当前 `tests/test_phase4_records.py` 独立重跑9/9通过，包含真实SUMO短case、逆序不变、漏车终止、后续actor异常保留已有决策，以及观测/记忆/动作/初态/子步/决策/时刻读回/截断和隔离记录篡改拒绝。该9项集尚未覆盖上述诚实部分尾记录与中断收尾重放。

数值与冻结校验脚本/结果：`audit_frozen_run.py`、`audit_frozen_run.log`、`frozen_run_audit.json`；局部测试为 `records_tests.log`。完整控制器领域规格结论见 `phase4_spec_review.md`，本审查不重复或扩大其保证。
