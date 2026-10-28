# R5 配对机制摘要工具单元

2026-09-13。范围是 root 外层 [tmp/phase5_r5_summary.py](D:/yanjiu1/keyan1/tmp/phase5_r5_summary.py) 与 [合成测试](D:/yanjiu1/keyan1/tmp/test_phase5_r5_summary.py)。没有改动任何 variant 生产源码、测试、配置、v1 或旧实验结果，没有执行车辆实验，也没有读取 heldout 或正式 R5 性能。

**17 项合成测试、两个已有短时记录管线夹具及跨工作目录快照重放通过；独立审查无剩余 P1/P2。本单元尚未汇总正式机制实验。** 工具不选方法、不筛种子、不调参，也不改变任何科学评分。

## 输入与证据合同

必须显式传入已结束的 `--run-dir` 和不存在的新 `--output-dir`；不读取 latest，不自动覆盖，输出不得位于源包内。输出包含自身 `script_snapshot.py`、固定版本 `motion_snapshot.py`、`summary.json`、`analysis_validation.json` 和 `evidence_hashes.json`；失败创建独立失败报告并保留目录，不回写源包。

摘要前后核对源 `evidence_hashes.json` 的完整文件集合与每个 SHA256，内层 code/input snapshot 也核对 exact file set、逐项 hash 和安全相对路径。最终 metadata/validation、frozen case file、每 case 元数据、case_index、各 case validation 和 top variants 均交叉绑定。started/finalized 必须是预期顺序的前缀，completed 必须对应实际 metadata，未启动项必须显式出现而不是被删除。

这验证的是封存来源；**不声明当前 workspace 等于封存代码，不重新执行控制器/模型/SUMO，不重新调用初态生成器，也不替代标准 R5 整包语义重放。** 初态发生器及物理状态的语义合法性仍由标准重放验收。summary 中 `formal_seventeen_variant_shape` 仅检查八案例、17 变体及 sampling 开关的数量形状，不证明它们已经通过正式规格；下述 0.2s 管线夹具也有这个形状。

普通 off/on 必须共享全部 case、物理初态、私有初态、模型与参数；唯一允许参数差异为 `r5_enabled`。两支 `formation_enabled` 都必须为 true。半控制周期分支与普通 on 初态/模型完全相同，仅 clock/policy 的 control/perception 两周期减半，其余参数不变。未启动分支列出的 formation=true 是声明计划，scope 明确没有执行证据。

## 机制观测口径

来源为最终 runner `mechanism_report` 的 `r5_events.json` 合同，以及每条 trace 的 input memory、decision memory、状态、steps 和 status。摘要从 trace 逐字段重建完整 events timeline 和累计字段并核对已保存 events；还核对 input 的私有/plan 记忆与最后一次成功 commit 的链。它不把记录内的随机数重新采样，也不把 failed tail 的 after memory 当作下一状态。

机制 actor 集合严格取 `case.controlled`；外生脚本车辆没有 R5 decision/私有记忆，不能伪造它们的零抽样结果。实际运动摘要仍覆盖全部初态物理 actor，原标准 metrics 未对外生 actor 登记时明确保留 null。

| 摘要字段 | 严格含义 |
|---|---|
| draws_requested / draws_committed | 前者为各 decision 相对其 input 的 draw 差，包含失败尾；后者只累计 status=completed 的提交，失败尾不推进最终 RNG。 |
| new_plan_requests / new_plans_committed | before.plan=None 且 after.plan 非空；后者额外要求完整 commit。它是新计划启动，不是换道完成，更不是实际避碰或通行。 |
| controller_maneuver_completions_committed | 本车已提交 completed_lane_changes 的增量；物理车道中心变化另外原样引用标准 metrics 的 lane_changes。两者不混同。 |
| phase_decision_counts | BACKOFF/YIELD/UNKNOWN/ELIGIBLE/IDLE 的决策观察数，包含有 decision 的失败尾。 |
| phase_committed_interval_s | 仅成功 commit 区间，以区间起点该决策 phase 左持有 dt 计算；失败尾没有提交时长。它不是原始连续时间状态占用真值。 |
| phase_speed_observations | 对应 phase 决策时刻的实际记录速度 min/max 及严格低于原 noa_min_lane_change_speed_mps 的观察数；没有私降门槛。 |
| eligible_below_minimum_lc_speed_decisions / first_eligible_s | 到期 phase 的观察事实，包括明确低速阻塞可能；到期不保证 prepare、原守卫接受或有限时间内启动。 |
| yield_guard / candidate_guard | guard 字段非 None 才是尝试分母；分别列接受/拒绝及已 commit 子集，零分母比例为 null，首拒绝保留对应原 assessment 和原守卫报告。 |
| episode_clears_committed / reentry_draws_committed | 前者为已提交物理 episode 从非空转为空，后者是之后观察到的新提交抽样；不离线推断真实对手身份或隐藏意图。 |
| blocking_exits_committed | 先前提交 blocking=true 到当前提交 false 的观察；它不等同已经换道。 |
| plans_started_after_observed_wait | 当前定义为该 actor 在历史上已经提交过 blocking 后的提交 plan 启动记录；不声称同一 episode，也不作等待导致启动的因果判断。 |
| private_stream_boundaries | 离线比较各自封存私有初态、首次抽样 deadline 和向上取整到原 behavior 网格的时刻。它不把各车释放时刻发回控制器。 |

同私有状态及不同延迟落入同一 behavior 网格均只是边界事实。最早网格仅由 deadline 算出，不包括 prepare、当前几何、速度门槛和原守卫，因此不能作为实际启动时间。每个 draw/plan 关键事件保留 committed 标志；失败区间即使已有 steps.final 及横向位移，也不能据此说逻辑状态已提交。

guard 的 `committed_rejections` 表示“该次拒绝所在的决策区间后来成功 commit”，不表示被原守卫拒绝的请求被执行。实际返回的 fallback 与新请求要按原 decision/trace 区分。

完整运行、失败前缀、已开始但早期缺 trace、未启动分别记录。只有已失败且 trace/completed 均声明为零时才允许缺 trace；此时机制观察为空、motion=null。标准 replay 可能拒绝缺 trace，本工具不会据此声称源包已重放。存在失败记录后再出现其他记录、缺决策的 completed 区间、时序断帧、无尾换行、私有记忆链错误和 events 篡改均拒绝。

## 驾驶、舒适性和运动

每 case 原样保留标准 geometry 的碰撞/越界/模型包络事件，记录错误、评价错误、SUMO warnings、驾驶和舒适 gate；不根据 R5 观察目标未触发推断碰撞。几何事件仍属于原保守扫掠检查口径。标准 actual actor metrics、tracking/requirements 和物理 lane_changes 分开列出。

速度/停车及实际加速度、jerk 复用已独立验收的 [phase5_motion_summary.py](D:/yanjiu1/keyan1/tmp/phase5_motion_summary.py)，固定 SHA256 `1cbdab1433ec01f7547f58dfa873eab0355588249ad0df23a1f6d10576d8b6ca`；工具不重新定义这些指标。保存的 0.01s initial/末帧去重，速度梯形积分，停车阈值取原 phase2 的 `1e-6 m/s` 并按左阶梯积分，实际纵横加速度/jerk 按原标准 metrics 对照。失败物理前缀保留 observed_window，full_window=null；即使关闭失败时物理已走满计划时长，也不提升为完整运行。缺 trace 时没有虚构的物理运动均值。

此入口目前只调用稳定 helper 的 `summarize_trace`，没有调用 `refinement_summary` 或 raw coverage 分支，因此不产出 0.005s 积分细化 jerk、未确认 raw coverage 或确认后 C。它们不被填零或计作已验证；若后续需要细化运动补充，应独立复用原 helper，数值验收仍由标准 replay 的 sampling 证据承担。

普通 off/on 仅在两支完整且初态/参数绑定通过后计算全窗口 draw/start 数量差；失败或未启动对照的全窗口差为 null。没有汇总成选择评分，也不将拒绝率下降解释成编队改善。新 runner 的 `paired_actions.json` 作为封存来源引用，明确由 producer/标准 replay 负责动作复算，本摘要不重复宣称已复算它。

## 测试与可重放日志

全部日志在 root `results/operations/`。执行环境为登记 Python312 的 `-I -B -S`，外层 `scripts/run_logged.py` 设超时并保存完整 stdout/stderr/命令。

| 日志 | 事实 |
|---|---|
| 20260912T214938733386Z_phase5_r5_summary_red_d247de1d | 11 项先因缺实现失败。 |
| 20260912T215220949220Z_phase5_r5_summary_core_green_a4eaeb62 | 11 项核心 accounting/状态/来源测试通过。 |
| 20260912T215436586827Z_phase5_r5_summary_package_red_21b96dc7 | 新整包接口缺失 RED。 |
| 20260912T215647778969Z_phase5_r5_summary_package_green_931ab733 | 14 项包括完整/前缀/未启动和快照重放通过。 |
| 20260912T215906667056Z_phase5_r5_summary_boundaries_red_49258415 | 缺 trace、半周期绑定、禁用私有状态不变和 guard 提交分母新增失败。 |
| 20260912T220036414046Z_phase5_r5_summary_boundaries_green_ad0b4688 | 保留的一次夹具失败：内存中 p/policy 共享对象导致测试连续减半两次；改为与落盘 JSON 一致的两个独立对象，未放宽实现检查。 |
| 20260912T220336126981Z_phase5_r5_summary_boundaries_green_v2_8908267c | 最终 17 项通过，1.181s 测试时间。 |
| 20260912T220746303026Z_phase5_r5_summary_unit_snapshot_tests_c26ecb96 | 单元快照从 D:/yanjiu1 工作目录独立运行相同 17 项通过。 |

随后只读记录作者已经保存的 **0.2s 管线测试夹具**，没有再运行物理控制。这些夹具曾在测试中替换 duration/发生器函数，不是冻结正式机制矩阵的实际效果证据：

- 完整 source：common `tmp/r5_complete_package_test_m2ru0jxc/runs/20260912T215511488774Z_3e90ef9a`。摘要为 root `results/phase5/r5_summary_fixture_complete_20260912T2206`；显式保留 17 完整，源 engineering=false。
- 失败 source：common `tmp/r5_failed_package_test_gcsk5wyy/runs/20260912T215614684669Z_7ed49d2d`。摘要为 root `results/phase5/r5_summary_fixture_failed_20260912T2206`；显式保留 3 完整、1 失败、13 未启动，源 engineering=false。

原摘要日志 `20260912T220601677179Z_phase5_r5_summary_complete_fixture_0e1c1580` 与 `20260912T220601675203Z_phase5_r5_summary_failed_fixture_f7657c12` 均退出 0。两个输出内保存的 script_snapshot 分别从 D:/yanjiu1 重放到 `r5_summary_fixture_complete_replay_20260912T2207` / `r5_summary_fixture_failed_replay_20260912T2207`，日志 `20260912T220638008242Z_phase5_r5_summary_complete_fixture_replay_48fe6ba1` / `20260912T220638009242Z_phase5_r5_summary_failed_fixture_replay_7841081e` 均退出 0。

两侧 summary/script/motion/analysis_validation 全部字节相同，exact file set 与每个输出 hash 均通过；[单元验证](D:/yanjiu1/keyan1/results/phase5/r5_summary_unit_20260912T2208/verification.json) 还保存验证脚本、工具、测试与 motion 原字节。完整摘要 SHA256 `6ec2123e939c2778cc9db8979fa858442f0655745eceefb9ef23ba4adc89a9cf`；失败摘要 SHA256 `3cce6bd773354aff9289de8c637dc4093e03254dac42f2251877eeb3a9943be8`。

最终工具 SHA256 `09efc4ddafc8573dc7b0c053e164a0891b1d9c3494da6701a8c6958f7f097658`，测试 SHA256 `aabb0692db981936f0915295cfc883921e398521490d38c498f1bc5d99301f76`。

[独立审查](D:/yanjiu1/keyan1/docs/phase5_r5_summary_review.md) SHA256 `a3b186b5fe8d57475d99a905ea23aa0869ad3537eb78a315450fb61e8dd536b2`：无剩余 P1/P2。审查者独立重跑 17 项；另对物理已积分完但未 commit 的失败尾、微小配对参数差、half 额外参数、坏末帧和重封的内部源文件做了新探针，结果符合合同。短失败包的全部摘要 artifact 异 cwd 重放同字节，日志 `results/operations/20260912T221225439029Z_phase5_r5_summary_independent_941d97e5`，4.078s。控制、正式记录、实际车辆效果均不在此独审结论内。

## 正式运行结束后的入口

主代理提供明确已封存 R5 run 路径后，使用 `python -I -B -S tmp/phase5_r5_summary.py --run-dir <明确源包> --output-dir <新目录>`，仍由 run_logged 包裹；重放使用输出中的 script_snapshot.py，源包参数不变，输出指向另一个新目录。独立审查和正式整包语义重放结论另行绑定。下一阶段仍是阶段 5 的机制/实际驾驶验收；本工具通过不开放阶段 6。
