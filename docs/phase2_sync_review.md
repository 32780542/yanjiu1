# 阶段 2 同步、运行记录与重放审查

审查及修复复核日期：2026-09-10。审查范围为 `simulation/external_bridge.py`、`experiments/records.py`、`experiments/phase2.py` 及桥接、记录、重放测试；复核另执行了 `tests/test_phase2_live.py`。先对照原研究规格 §7、阶段 2 入口和实施计划，再核查实现与故障注入。研究代码仅从 `keyan1` 读取；未导入父目录研究代码，未改动实现。同步连接按已明确的本阶段单车 bench 语义审查，多车调度、感知及另一代理负责的低速模型/换道跟踪不计入本次问题。

当前结论：R1、R2、R3 均已修复并复核关闭；本范围没有待处理问题。下文历史发现保留原始行号与失败现象，不能作为当前仍有缺陷的陈述。原始复现脚本为 `tmp/review_sync_records/reproduce.py`，输出为同目录 `evidence.json` 与 `targeted_tests.log`；三份文件均未覆盖。

## 当前修复状态

| 问题 | 当前实现位置 | 关闭依据 |
| --- | --- | --- |
| R1，旧成功残留 | `experiments/phase2.py:193`、`:274` | 两个公共入口先进入 RunRecord，再执行初始化或重放；已有成功记录后的配置/缺失输入异常现在建立新失败记录。 |
| R2，metadata 初始化异常漏记 | `experiments/records.py:26-34` | `__enter__` 捕获首次 running 写入后的 metadata 异常，持久化 failed 与 traceback 后重抛。 |
| R3，SUMO 依赖初始化异常漏记 | `experiments/phase2.py:117-129` | 外层包装在已建档之后捕获 `_execute_sumo` 的 BaseException，覆盖依赖初始化及连接关闭阶段的异常；依赖失败的回归测试通过。 |

复核期间另检查并关闭了完成结果的保留问题：`run_phase2` 和 `replay_run` 现在在退出 RunRecord 后才对 `passed=false` 抛出命令失败，完整的科学门槛结果和重放不一致详情不会被外层异常记录覆盖。当前位置为 `experiments/phase2.py:193-198`、`:274-279`。

## 规格核对

| 约束 | 本次核对结果 |
| --- | --- |
| 连续积分是唯一权威运动，moveToXY 仅同步 | `synchronize()` 只接收完整的 IntegratedStep，先按保存状态和命令纯函数重放校验，再提交末态；仅在回读通过后推进 `self.current`。校验重算不写入权威状态，不等于重复物理推进。 |
| CG/前保险杠和数学角/导航角转换 | 桥接统一调用 `to_sumo_pose`、`from_sumo_pose`，前向偏移为 length/2，角度为 `(90-degrees(psi)) % 360`；回读按圆周角误差检查。 |
| 同步时刻与速度一致 | 初始化单独保存时间偏移；每次同步前核对旧 SUMO 状态，提交积分末态后推进一次 SUMO 并核对新物理时刻、位置、航向和速度。 |
| SUMO 加速度与瞬时模型量分开 | 使用两端速率模长的区间差分核对 SUMO acceleration，另行记录模型 `a_long_mps2` 与 `a_lateral_mps2`；对应测试确实验证两种量不相等。 |
| 瞬移、重复积分、子步篡改被拒绝 | 现有纯函数测试覆盖端点篡改、内部子步篡改、命令篡改、陈旧初态与缺少子步。 |
| dt 减半与独立几何负例 | orchestration 分别生成相同命令的 .01/.005 积分对照和 .1/.05 控制对照，并汇总独立几何检查与故障注入；复核执行了 .1/.05 两种同步率的短程真实 SUMO 跨 edge 测试。全工况门槛仍由主任务单独验收。 |
| 可重放、失败不得残留旧成功 | 初态、参数、命令、全部子步和诊断均被保存并比较；历史发现的异常记录生命周期问题已经修复，完成但未通过的结果保留完整诊断。 |
| 不引入真值/调度救场 | 本次范围内未发现用邻车车型、他车计划、全局槽位或隐含通信修正单车状态的路径；道路真值仅用于离线几何评估。 |

## 历史发现与原始复现

### R1 — P1，已关闭：运行/重放入口开始记录过晚，失败会保留旧 passed=true

历史位置：`experiments/phase2.py:187-194`，以及 `:249-264`；当前修复位置见上表。

`run_phase2()` 在进入 RunRecord 前调用 `VehicleModel.from_config()`、清单散列及输入文件散列。配置物理值非法、配置文件损坏或输入文件缺失均可在新运行建立前抛出异常。此时 `runs/latest.json` 仍指向上一次 `completed/passed=true`，没有本次 run_id、失败原因或 traceback。`replay_run()` 同样在读取源文件、清单与全部重放之后才创建 RunRecord；源 metadata 或 evidence 文件缺失时，`replays/latest.json` 也保留旧成功。

复现：在隔离目录先创建一次成功记录，然后分别让 `VehicleModel.from_config` 抛出 `ValueError('Invalid physical parameter mass_kg')`，以及调用 `replay_run` 读取不存在的源目录。两次调用都确实抛异常；前后 latest 的 run_id 完全相同且 `passed=true`。证据字段为 `model_initialization_failure.stale_passed_true=true` 和 `replay_missing_source_failure.stale_passed_true=true`。

建议：两个公共入口都先建立最小 running/passed=false 记录，再在其异常保护范围内读取/校验配置和源工件；完整 metadata 可以随后更新。回归测试应在已有成功记录的前提下故障注入，要求新 run_id、failed、passed=false 和 traceback，而不只验证 RunRecord 已进入后的异常。

### R2 — P2，已关闭：RunRecord 的 metadata 初始化失败不会被记录为 failed

历史位置：`experiments/records.py:26-29`；当前修复位置见上表。

`__enter__()` 写入 running 之后直接序列化 metadata。若该调用抛异常，Python 不会调用本次上下文的 `__exit__()`。因此运行永远停在 running/passed=false，没有异常原因或 traceback。此处不会保留旧成功，但不符合明确失败与可追溯诊断要求。

复现：`with RunRecord(base, {'invalid_metadata': float('nan')}): ...` 在 metadata 序列化时抛出 JSON ValueError；同一新运行的 validation 和 latest 均留在 running，且 validation 无 error/traceback。证据为 `metadata_serialization_failure`。

建议：在 `__enter__()` 内对首次状态建立后发生的初始化异常执行失败持久化再重抛；至少覆盖 metadata 非法值和写入异常。不能依赖 `__exit__()` 捕获 `__enter__()` 自身的失败。

### R3 — P2，已关闭：SUMO 依赖初始化在异常保护之外，子工况失败留在 running

历史位置：`experiments/phase2.py:129-133`；当前修复位置见上表。

`run_sumo()` 已写入 `validation.json` 的 running 状态，但 `lock_traci()` 在 try 之前执行。TraCI 导入失败或来源检查失败会直接逃逸，子工况的 validation 留在 running，缺少 error/traceback。外层 RunRecord 可能标记整轮失败，因此这不是 R1 的旧成功问题；但具体失败的 SUMO 工况记录不完整。

复现：注入 `lock_traci` 抛出 `RuntimeError('Injected TraCI dependency load failure')`，调用一次单步 bench。未启动真实 SUMO；异常确实抛出，SUMO 子目录 validation 仍为 `{'passed': false, 'status': 'running'}`。证据为 `sumo_dependency_failure`。

建议：将依赖载入与已开始记录之后的初始化纳入失败保护，确保子工况自身保存 failed 和 traceback；连接关闭异常和 KeyboardInterrupt 也应在设计上覆盖，但本次只对依赖初始化故障做了实测，不将未执行场景当作已验证现象。

## 原始执行证据

复现命令（在 keyan1 执行）：

```powershell
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S 'tmp\review_sync_records\reproduce.py'
```

首次针对性测试 9/9 通过，同时 R1、R2 故障注入复现。第二次执行时主任务已加入 R1 的两条回归测试，结果为 11 项中原有 9 项通过、两条新测试失败；失败断言均为 latest run_id 仍等于上一次成功 run_id。该次还复现了 R3。这属于发现缺陷后的红测试证据，不能写成当前全部测试已通过。

以上为修复前历史证据。原始失败输出中的 `stale_passed_true=true` 及 running 状态保持原样，不代表当前代码结果。

## 修复复核证据与边界

独立复核首次执行 15 项桥接、记录、重放和真实 SUMO 测试，15/15 通过；日志为 `tmp/review_sync_records/recheck_13f356f5/tests.log`。其中真实 SUMO 测试使用锁定的 1.27.1，在 .1/.05 s 两种同步率下跨越 edge，检查位置及区间加速度误差、道路转换和零传送。这里只证明短程接口测试，不代表完成所有阶段 2 工况。

主任务保存的红绿证据已逐项阅读：`results/phase2/preflight/initialization_failure_red.log` 与 `_green.log` 证明 R1 两条回归由失败转为通过；`early_diagnostics_red.log` 与 `_green.log` 证明 R2、R3 由失败转为通过，后一份同时包含 8 项记录/真实 SUMO 测试全部通过。`gate_preservation_green.log` 显示完成但门槛失败的结果保留及失败重放详情保留测试在内的 7 项全部通过。该项的历史红日志中，科学门槛测试当时被前置 foundation 状态提前阻止，故不能将那一条红输出当作已触达结果覆盖缺陷的证据。

补充隔离复现保存为 `tmp/review_sync_records/recheck_5b14be42/evidence.json`，脚本为 `tmp/review_sync_records/recheck.py`。它执行短程实际模型积分和完整 orchestration，mock 前置验证与 SUMO 子工况，以单独检查结果持久化与哈希，不把 mock 输出当作真实 SUMO 证据：

- 成功与科学门槛失败的两次运行各有 7 份 validation 文件，均纳入 evidence_hashes，缺失项与散列不匹配均为空。
- `run.finish` 完成后才生成哈希（当前 `experiments/phase2.py:267-269`），因此包括最终根 validation、工况、三种积分/控制变体以及两个 SUMO 子目录的 validation。
- 故意令科学门槛失败后，根 validation 保留 `cases`、`faults`、`passed=false`、`status=completed`，哈希仍一致。
- 篡改 trace 内一个子步的 x 后，失败重放保留具体文件 `constant_speed/base/trace.jsonl` 的哈希不匹配和 `State mismatch at t=0.01`；其他两份 trace 仍成功。
- `original_evidence_unchanged=true` 核实原始复现脚本及两份失败证据未被覆盖。

这次补充脚本中的 17 项测试日志曾因活动 foundation 记录的临时状态而出现一条前置条件失败；它不是隔离哈希检查的失败，也不能称作 17/17 通过。主任务随后已在独立进程恢复 foundation 验证并保存上述 7/7 绿日志，进一步将回归测试前置依赖改为隔离 fixture。最新 `results/phase2/preflight/tests_all_before_final.log` 已读取核验，52 项全部通过。复核脚本后续执行明确 mock 前置验证与相关读取，不再写活动 foundation 结果。

最后一轮配置整理把原硬编码验收常数按原值移入 phase2 参数清单；桥接时间与区间加速度容差改为查表，数值阈值未放宽。上述测试日志是冻结最终完整实跑之前的回归证据，最终五工况实跑仍应使用主任务随后生成的独立 run_id。

当前三项缺陷均关闭，指定范围内未发现未解决的实质缺陷。完整五工况、完整收敛结果和阶段验收结论由主任务报告，本审查不据短程回归外推交通安全、NOA 或交通收益结论。
