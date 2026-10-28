# 阶段 5 重放与信息隔离审计单元

2026-09-13。本文件只验收重放/审计实现，不替代阶段 5 实验与研究结论。

实现文件：`experiments/phase5_replay.py`、`experiments/phase5_audit.py`；测试文件：`tests/test_phase5_replay.py`。阶段 4 文件未修改。

## API 与已实现事实

- `replay_case(metadata, trace_path)`：用冻结参数、初值、局部道路及各车自身脚本重新构造 `FormationClock`，逐帧重新生成传感输入、自身记忆、决定、动作、物理子步和诊断；SUMO 原始回读报告重新核算位置、姿态、速度、时间与区间加速度。不会重新启动 SUMO，也不会以回读位置修正物理状态。
- 正常记录必须含全部计划区间；失败记录必须有显式失败边界和失败尾，或已保留的连接关闭错误。只复算已产生前缀；检查 completed/physical/isolation/partial-tail 计数。重放通过不会把失败驾驶改为成功。
- `isolation_audit(records, model, p, policy, road, controlled, path)`：每辆受控车的四个反事实分支均逐帧重建传感器历史。分别改变真实标识与容器次序、隐藏类型、不可见未来计划、观测范围以外状态。每 `phase5_isolation_stride` 个控制区间及末帧比较完整本地输入与决定，并记录移除可见邻车是否改变动作的正例。
- 反事实决策使用同一本车记忆，记忆的真实性由完整时钟重放另行核验。这是抽样的同记忆因果比较，不能声称已执行四条完整闭环反事实轨迹。编队关闭时维持原 `NoaMemory` JSON schema；开启时使用 `FormationMemory` 的正式恢复函数。
- `replay_run(run_dir, base=None)` 必须指定来源；不读 `latest.json`。验证完整相对路径 SHA256 清单、封存代码/输入的文件集合、冻结案例与每案例验证文件，拒绝当前代码与封存代码不一致。输出新重放目录并给出 `code_snapshot` 恢复入口，不覆盖工作区。
- 独立检测只用 `status == completed` 的已提交物理区间。重新运行固定 15/30 m 检测器，重新计算默认阈值及位置/速度阈值的 0.5、1.0、1.5 倍敏感性结果；不使用控制器自身编队标签判成功。
- 半控制周期对照重新核对参数、相同案例与策略，重算公共物理时刻差异。每车半积分步长轨迹核对初态、计数、时间步长及逐条动作与普通源记录相同，重算动力学、轨迹差异及保存的验收门槛。

## 测试与失败保留

使用登记的 CPython 3.12，经 `scripts/run_logged.py` 运行；命令与 stdout/stderr/退出状态均留在新目录。

| 证据目录（相对项目根） | 事实 |
|---|---|
| `results/operations/20260912T173533855832Z_phase5_replay_red_fad01e0d` | 首轮 5 项测试因重放模块缺失失败，保留 TDD 红灯。 |
| `results/operations/20260912T173752403055Z_phase5_replay_core_1172e7ff` | 关闭编队的反事实错误恢复成 FormationMemory，8 次比较不一致；修改为原 NoaMemory 恢复。 |
| `results/operations/20260912T173821986994Z_phase5_replay_core_green_bc35574d` | 核心 5 项测试通过。 |
| `results/operations/20260912T174029332020Z_phase5_replay_bundle_red_7bc2ed21` | 新增整包测试因 replay_run 尚未实现失败。 |
| `results/operations/20260912T174213022039Z_phase5_replay_bundle_green_383209f0` | 8 项通过，含代码/证据清单、独立检测、编队记忆和回读篡改。 |
| `results/operations/20260912T174326023243Z_phase5_refinement_red_ae9eddc5`、`results/operations/20260912T174359958753Z_phase5_refinement_red_verified_3470af07` | 逐车积分细化目录与初版整包重放假设不一致，失败保留；修正为逐车结构。 |
| `results/operations/20260912T174452865305Z_phase5_actual_bundle_red_80550f10` | 实际 runner 的 on/off/半控制周期短包亦复现积分目录失败。 |
| `results/operations/20260912T174551003316Z_phase5_actual_bundle_green_36a00a22` | 10 项全部通过，4.147 s；含实际 runner 生成 0.2 s 三车 on/off/半控制周期及三车积分细化包，整包重放通过。 |

拒绝测试覆盖动作、输入记忆、决定记忆、物理子步、SUMO 原始回读、独立检测结果篡改；trace 截断/加行、隔离审计截断、缺失文件、清单漏列和路径越界；同时验证失败前缀重放仍保留失败属性。

## 参数与下一入口

本单元未调整控制律、安全阈值或检测阈值。新增显式审计采样键 `phase5_isolation_stride`，runner 设为 10，沿用阶段 4 的每十个控制区间抽样及末帧必审计口径；传感历史仍逐帧重建。

下一入口是对控制器、实际 runner 和本单元做独立规格/代码审查，随后使用当前稳定代码冻结并执行实际 SUMO 阶段 5 案例。以上短时测试不能证明编队形成、稳定性、交通收益或阶段 6 入口成立。

## 独立审查后的补强与最终冻结

本单元与控制器代理交叉审查了 runner、cases 和整包证据路径。发现与修复均保留记录；以下是实现缺口，不能当作算法实验失败。

- 旧 `visibility_exit_and_return` 仅按邻车数量下降后上升判定。探针 `results/operations/20260912T175030340006Z_phase5_runner_review_probe_ece8a189` 验证：从未选过参考也会返回 true。主代理将数量变化降为诊断，新增同一预设事件车实际被选为参考、出界、失去参考作用、再入界、再次选中的完整离线事件链；在线控制器仍不读取事件车真实标识。
- 旧 events、几何/舒适性指标与科学结论仅受哈希保护，未做语义重算。新增从轨迹重新计算 `event_report`、扫掠几何、实际加速度/jerk/舒适性及 `summarize_conditions`；核对每车/顶层的 driving、recording、engineering、scientific 与采样门槛。事件指标和形成检测均只将已提交区间解释为实际运动；失败尾仍留在物理前缀审计中。
- 旧 frozen_cases 只单向匹配已存在变体，缺少某个 on/off 变体可漏检。现对冻结案例、case_index 计划、启动/完成列表、目录、顶层 variants 与每案例名称双向校验。正常包必须完整覆盖冻结的 on/off 与已声明采样变体。
- 控制器代理实测元数据可以把 `replay_absolute_tolerance` 改成 0.2，再修改动作 0.1 后重新封存，旧重放会接受。现整包先用已通过代码/配置哈希核验的 `phase5.parameters(enabled)` 严格零容差核对完整 model、时钟和策略参数；半控制周期仅允许双方明确的 0.05 s 控制/观测周期。变体后缀、live、冻结 duration 与计划区间数也必须一致。
- 主代理修复外层中断丢失 variants 索引问题。重放现支持已正常捕获并封存的中断包，单列未启动变体，重新构造完成案例及失败案例前缀，强制原科学/工程结果为失败。硬杀导致未封存的目录仍不自动视为可重放。

新增红灯证据：`results/operations/20260912T175132437361Z_phase5_derived_audit_red_10e0813b`（派生结论/覆盖缺口 5 个失败），`results/operations/20260912T175538091445Z_phase5_partial_package_red_ecad5f7f`（中断包），`results/operations/20260912T175629847596Z_phase5_parameter_binding_red_1d102af4`（中断与参数绑定）。均未删除或覆盖。

最终检查为 14 项全部通过：`results/operations/20260912T175925922182Z_phase5_replay_final_review_3d11fbc9`，命令退出 0，外部记录耗时 12.968 s。包含实际 runner 的 0.2 s on/off/半控制/半积分测试，以及第二个变体物理积分处触发 KeyboardInterrupt 后，对已完成 off、失败 on 与未启动 half 的整包重放。短时管线测试通过 unittest 显式缩短案例，不作为正式案例集合或科学成功证据。

冻结的 `experiments/phase5_replay.py` SHA256 为 `23315525472b4c686de8819118606dfc2468d0661c7b9292ef7c7a2eae59ca34`。此后不再修改生产、测试或配置，主代理进入全回归与 21 个实际 SUMO 变体。成对扰动/无扰动轨迹的实际 Δv 分析由独立、带哈希的离线分析脚本执行；相对 5 m/s 的偏差比不能替代扰动差分，更不能单独证明串稳定。

单案例 `replay_case` 的参数来自调用方明确传入的 metadata；封存代码/配置/输入绑定属于 `replay_run` 的整包前置检查。需要研究证据的参数完整性时应使用整包入口。
