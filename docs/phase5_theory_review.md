# 阶段 5 理论与控制采样一致性复审

2026-09-13。对生产源码只读复核；本轮仅新增本报告与追加式操作日志，原 `docs/phase5_theory.md`、理论计算包、旧失败/探针日志均未回写。

## 结论

此前发现的“实际控制保持为 0.05 s，基础 NOA policy 仍按 0.1 s 计算半步反馈”问题已在本次检查的源码中修复。现在半采样分支同时更新物理/观测参数与 policy 的 `control_sync_dt_s`、`perception_dt_s` 为 0.05 s；FormationClock 在初始化时拒绝物理控制周期与 policy 控制周期不一致；重放侧对半采样 policy 的期望值同步更新。原理论文档中 `h=0.05 s` 对应 `-k0*h*a/2=-0.015*a` 的公式与修复后的真实命令一致。

本轮控制器、时钟和理论共 **27/27 测试通过**。就固定参考理论、控制器和采样时钟接口这一复审范围，未发现尚未解决的阻塞项。本报告不代替正在收尾的完整实验/重放源码绑定审查，也不证明阶段 5 全部研究验收条件通过。

## 已核对的修复

- `simulation/formation_clock.py:13`：比较 `p.control_sync_dt_s` 与 `policy.control_sync_dt_s`，绝对容差 `1e-12`、相对容差 0；不一致立即抛出 `ValueError`。继承的 NoaClock 同时保持物理控制周期与传感周期一致检查。
- `experiments/phase5.py:218`：半采样物理参数的控制/观测周期均为 0.05 s；紧接着对 policy 的两个周期作同样更新。
- `experiments/phase5_replay.py:179`：半采样 policy 的期望值从普通 policy 派生，仅同步控制和观测周期；其他字段仍严格对照。
- `tests/test_phase5_clock.py`：新增测试同时覆盖编队开/关时拒绝周期不一致，以及统一 0.05 s 后一次物理提交包含 5 个 0.01 s 积分子步。

针对性正例还直接比较修改前后的 policy 字典：变化字段恰好为 `control_sync_dt_s`、`perception_dt_s`，均从 0.1 变为 0.05；所有反馈增益和响应时间参数保持不变。原理论文档的控制步长与积分步长区分保持有效。

## 真实命令复核和保留证据

旧问题的固定证据是 `results/operations/20260912T175124571788Z_phase5_theory_clock_period_probe_82ab2e2a`：当 `v_i=v_target=5 m/s`、实际加速度 `a=.2 m/s²` 时，物理保持 `.05 s`、policy `.1 s` 被错误接受，实际基础命令为 `-.006 m/s²`。

本轮从该旧目录 `started.json` 读取并原样重跑已保存的命令，创建新日志：

`results/operations/20260912T175738100903Z_phase5_theory_old_probe_rejected_4dd326a7`

其进程退出码为 **1**，错误为 `ValueError: Formation physical/control policy periods must agree`，发生在 FormationClock 初始化阶段。这里的非零退出码是对旧错误配置的预期拒绝，不能标为算法实验失败或删除。

将物理和 policy 周期均设为 `.05 s`，其余初态和参数保持一致，再调用实际 `FormationClock.tick()`；日志为：

`results/operations/20260912T175806059757Z_phase5_theory_half_command_confirmed_09eb7638`

结果：

| 项目 | 实际值 |
|---|---:|
| 物理控制保持时间 | .05 s |
| policy 控制周期 | .05 s |
| 基础 NOA 命令 | −.002999999999999936 m/s² |
| 解析预期 `-.6*.2*.05/2` | −.003 m/s² |
| 物理积分子步数 | 5 |
| 进程退出码 | 0 |

探针要求实际命令与解析值之差小于 `1e-12`，要求一次提交的最终物理时刻为 `.05 s`，并断言 policy 只变化上述两个周期字段。日志同时保存 7 个相关源码文件的 SHA-256，包括 FormationClock、NoaClock、基础 NOA、编队控制器、实验、重放和理论计算脚本。

## 回归和边界

回归日志：

`results/operations/20260912T175737988612Z_phase5_theory_sampling_review_tests_cc9c5795`

该命令独立执行 `test_phase5_controller.py`、`test_phase5_clock.py`、`test_phase5_theory.py`，实际结果为 `Ran 27 tests ... OK`、退出码 0，覆盖 21 项控制器/时钟测试和 6 项理论测试。测试继续检查 15/30 m 本地参考、编队关闭时完整记录与原 NoaClock 等价、风险退出与安全拒绝、连续观测迟滞、丢帧/歧义重置、JSON 嵌套记忆恢复及实际 RK4/解析 ZOH 的交叉核对。

固定参考、直路巡航、无饱和、权重恒定且安全层接受增量仍是理论前提。本次修复使半采样实验的控制命令语义与理论一致，没有消除参考切换、变权重、非线性限幅、基础跟驰和可见性变化的分析边界。后续应继续使用真实物理速度扰动与完整实验记录报告改善、无改善或失败；不把本次周期修复或局部谱半径小于 1 解释为全局收敛、串行稳定或全阶段研究验收通过。
