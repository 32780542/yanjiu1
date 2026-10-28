# 阶段4失败证据修复跟进审查

审查日期：2026-09-11。结论：**本次范围内无未解决的 P1/P2；原两项 P2 及跟进发现的重复诊断 P2 已修复并独立复核。M1 仍不放行。**

生产审查范围为 `experiments/phase4.py`、`experiments/phase4_replay.py`、`simulation/noa_clock.py`、`tests/test_phase4_records.py`；必要时只读核对 RunRecord、FleetBridge 和读回接口。审查代理没有修改生产代码、参数或测试，没有提交，没有重写任何旧冻结目录；只写本文及 `results/phase4/continuation/final_review/`。初始化专项结论见 `phase4_bootstrap_review.md`，本文不扩大其保证。

## 原问题及修复复核

1. **原 P2：部分末区间不能独立重放——已关闭。** 运行元数据现在分别保存 trace 总数、成功完成数、全车本地积分及诊断完整数、隔离审计消费数和部分尾标记，并保存失败阶段、actor、原始错误。重放从前缀状态重建，只执行到已登记的失败边界，比较确已保存的输入、决策、动作、积分和诊断，不补造未产生的结果；隔离审计先验证 trace，再使用同一完整本地记录范围。独立观测、决策、脚本动作、积分、诊断异常探针均通过。首区间后车决策失败保留一条部分记录，驾驶覆盖为零，隔离比较数为零且明确为不适用，未生成驾驶指标来冒充覆盖。

2. **原 P2：KeyboardInterrupt 缺索引及哈希——已关闭。** case 执行前即加入顶层索引；case 在重抛中断前完成失败状态、计数及已有证据审计；顶层最终路径在 RunRecord 保存失败后生成哈希。独立对第二 actor 第二区间积分注入 KeyboardInterrupt，原中断继续传播，case 保留完整前缀和部分尾，顶层索引包含该 case。独立中断 run `20260910T185221067068Z_23a5cdd0` 的 89 个证据哈希、76 个源码快照完整匹配，标准 `replay_run` 通过；`source_driving_gate_passed=false`、`fault_injection_performed=false`，没有把未执行故障注入记为已完成。回归另覆盖决策阶段中断与实际诊断阶段中断。

3. **跟进新增 P2：重复诊断被中断时边界与保留范围不一致——已关闭。** 修复前 `NoaClock.tick` 已逐车保存诊断，却在排序时再次调用 `model.observe`。独立在第二物理区间后车某个已返回积分子步的第二次诊断调用注入 KeyboardInterrupt，末条已包含两车完整诊断，却仍标记首次 `diagnostics/front` 边界；数值重放报 `interval2.diagnostics: fields differ`，隔离重放也失败。原复现保存在 `probe_review.py/.log/.json` 与 `diagnostics_duplicate_interrupt/`。

   最终 `simulation/noa_clock.py:118` 只按 key 排序已保存的诊断值，不再重算或覆盖。新增回归确认每车每个已返回子步仅诊断一次，排序后的诊断对象与原对象相同；真正首次诊断期间的 KeyboardInterrupt 仍保留两车积分及先前 actor 诊断并可重放。独立固定区间及子步对象身份的复核见 `after_diagnostics_fix_verified/`：重复调用触发条件不再达到，3 个区间正常完成且 trace/隔离重放通过；其他真实异常边界继续按失败保存和重放。最终 records 集由审查代理独立运行 **16/16 通过**。

## 契约核对

| 要求 | 独立证据及结论 |
| --- | --- |
| 已得到的 actor 输出保留，缺失输出不伪造 | 后车异常时保留先前 actor 的输入/决策/动作/积分；首次诊断失败仍保留已经返回的两车积分。13 项尾删除、已保存决策删除、虚构后车结果、初态及子步更改均同时被 trace 与隔离重放拒绝。 |
| 失败实例不可继续 | 移除注入后再次 tick 仍报 `NOA clock terminated after failure`；状态、记忆与最后失败记录均未被重试改动。 |
| 完成、积分与实际 SUMO 推进不混同 | `physical_intervals` 是全车本地积分及诊断完整数，`physical_sumo_advances` 才是实际 SUMO 推进数。独立 precommit 故障保留 2 个本地完整区间、1 次 SUMO 推进；postcommit 故障保留 2 个本地完整区间、2 次推进；二者仅 1 个成功完成区间。 |
| 真实部分读回保留状态与相位 | 两个真实 SUMO 短 case 分别在提交前/后读回后车时异常；ego 原读回保留、front 为 `readback_exception`、rear 为 `not_read`。重放只检查已捕获原值，不生成缺失车辆位置、速度或时间。数值与隔离重放均通过，驾驶仍失败。 |
| 失败与数值可重放分别报告 | 所有真实故障探针的 driving/passed 保持 false；重放成功只说明已记录的计算前缀可重建。未触发故障的短 fixture 通过不代表研究驾驶验收通过。 |
| 旧记录兼容且不补写历史证据 | 首次旧 run 的 15 个原可重放变体继续通过；原 `merge_no_gap/base` 初始化失败的零条物理 trace 仍按失败报告。旧审查 `partial_second_decision/` 缺新边界 schema，当前仍拒绝重放，未事后补造其元数据；这与新格式边界故障可重放是不同结论。 |

新增字段在重放中与实际行数/完整范围交叉检查；历史已冻结完整记录通过兼容默认路径。没有通过丢掉部分尾、降低驾驶门槛或修改旧证据来关闭问题。

## 最终固定运行核验

最终运行：`results/phase4/runs/20260910T185443571873Z_3776ab63`。审查代理仅在其顶层状态完成且哈希已生成后开始核验。

- **269 个证据文件 SHA256 与清单范围完全匹配，76 个启动源码/配置快照匹配，无丢失、额外未登记文件或差异。** 运行报告的源代码运行期变化为空；独立审查时当前源码也与该运行清单一致。
- 16 个变体共 **2,222 个全车本地完整区间、2,222 次实际 SUMO 推进、90,060 个车辆子步**。独立遍历全部 trace，初态承接、每车子步数、子步 dt、终点、同步时间及 SUMO offset 均一致。这里两种区间总数相等是该完整实跑的结果，不能推广到提交前故障。
- 独立按保存状态的实际加速度有限差分复算所有受控车 actual jerk，并分别按执行器状态差分复算 actuator jerk，与保存指标一致，没有将两者替换使用。
- 最终 16 个变体的 trace 与 isolation 文件均与前一完整运行 `20260910T184756056570Z_eddf61a3` 逐文件 SHA256 相同。前一运行的全部 16 个变体已由本审查独立 trace/隔离重放通过；最终运行另独立重放无空隙并道、压力碰撞和采样减半三类关键变体，均通过。
- `merge_no_gap/base` 是实际驾驶 16 s：160 个本地完整区间、160 次 SUMO 推进、46,400 个车辆子步，碰撞/越界子步均为零，结束速度约 1.4769 m/s，仍未满足 0.1 m/s 门槛。它已区别于首次冻结运行的初始化失败，但仍不能称停车要求通过。
- `urgent_braking_stress/base` 保留 22 个本地完整区间及 22 次 SUMO 推进，仅 21 个区间状态为 completed；失败尾为同步后的全车读回。物理尾时刻约 2.2 s，SUMO 读回时刻 2.4 s、offset 0.2 s；离线几何审计有 11 个碰撞子步。数值重放通过不消除这次驾驶失败，也不把 SUMO 日志 warning 时间直接当成物理时间。
- 最终运行保持完整小案例集、所有变体 recording 通过、普通案例总体 **9/14 通过**；总门槛 false、`next_stage_allowed=null`。**M1 未通过，不放行阶段5或正式实验。** 舒适性、停车/驾驶要求、采样差异和真实压力碰撞等保留研究失败，本身不是证据代码审查缺陷。

首次旧冻结运行另独立校验 266 个证据哈希、74 个源码快照；中间完整运行校验 269 个证据哈希、76 个源码快照；均完整匹配。长审查进程跨越获授权的诊断修复和绘图脚本更新，因此其起止源码比较如实列出变化，不能误读为最终固定运行期间源代码不稳定；最终固定运行已单独证明零源差异。

## 可复跑证据与范围限制

所有命令使用登记解释器 `C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe -I -B -S`，工作目录与输出均在项目内。主要证据位于 `results/phase4/continuation/final_review/`：

- `records_tests.log` 为修复初期 14/14；`records_tests_after_diagnostics.log` 为最终 16/16。
- `probe_review.py/.log/.json` 为独立边界探针及新增 P2 原复现；`after_diagnostics_fix_verified/` 为最终正确范围的复核。两个中间探针目录 `after_diagnostics_fix/`、`after_diagnostics_fix_v2/` 保留审查脚本调试记录：前者把数值相同的评估重放状态也算入触发，后者跨区间累计次数；二者不用于最终缺陷判断，最终版本固定区间与子步对象身份。
- `probe_coverage.py`、`coverage_review.json` 为 13 项篡改拒绝、失败实例终止和两个真实部分读回 case；保留原始 trace、metadata、SUMO 日志及 validation。
- `probe_interrupt_and_frozen.py`、`interrupt_and_frozen_review.json` 为独立中断标准重放、旧及中间冻结完整性/兼容性检查；`historical_partial_status.json` 明确保留旧无 schema 部分尾仍不可重放的状态。
- `audit_final_fixed.py/.log`、`final_fixed_run_review.json` 为最终固定运行全部哈希、全部子步与 jerk 检查、字节一致性及关键变体独立重放。

本报告评价上述阶段边界、证据格式和已保留的数据范围；旧缺失 schema 没有被补写恢复。NOA 领域规格、连续时间安全和完整数值收敛不在本次证据修复审查结论内。
