# R：完成横移后的组织参考恢复候选

本候选独立基于 Git `8ed11d90ac457269b2175e20aec5ba1bbba8a318` 的 `variants/phase5g_pure_formation/noa/native_rules.py`。仅修改 `tmp/literature_trials/R/native_rules.py`，未修改生产规则、NOA、必要合流优先权、安全计算、固定30米组织目标、统计口径或其他候选。尚未运行交通仿真，不能据此判断通行效率或稳定性改善。

依据文献报告第5节，在本车实测已居中、横向速度已小于既有门槛且没有未执行横移请求时，重新求当前真实F/R间隙参考。若该间隙的F恰为 `_following` 当帧选择的真实近前车，则把合流参考相对于常规 `F.x−30m` 和 `F.speed` 的两个差值记入本车 `Memory.recovery`，并以当前合流请求完成交接。其余情况继续现有规则，尤其不为无真实近前车的队首创建虚拟前车。

令完成时刻为本车观测时间 `t0`，位置/参考速度偏差为 `dx,dv`，则仅组织参考使用：

`w=max(0,min(1,1−(t−t0)/0.5))`

`target=current_front.x−30+w*dx`

`reference_speed=current_front.speed+w*dv`

响应时间固定复用原有0.5秒跟驰响应，不做参数搜索。线性恢复保证同一完成帧的请求连续，并在0.5秒后完整恢复原规则；它是本候选的工程假设，不是文献给出的本场景最优值。速度响应系数仍等于0.2。记录只含当前局部前车跟踪标识、两个本车参考差值和本车时间；标识仅用于关联，不参与大小排序或优先权。

当前实际前车改变、离开真实占道走廊、超出50米组织链或不可见时，立即丢弃恢复记忆。切换NOA或开始新的横移请求同样清除记忆。`gap` 在完成后照常清除，既有 `joining` 在恢复期间继续阻止立即重启自由补位；恢复结束后照原有调距条件退出。没有普遍或长期增大车间距。通用 `_request`、`safe_speed`、真实占道几何及其硬安全裁剪完全沿用原代码；安全/必要合流/接收开隙介入时可覆盖组织平滑请求。

静态验证为8项真实几何/本车记忆行为测试，加46项既有规则回归，共54项。检查内容覆盖完成帧位置与速度请求连续、半程与有限恢复、压缩/扩大两类临时间距、实际完成反馈、前车更换/丢失/离道后的重置、当帧真实停止前车安全限制、跟踪标识置换、不可见远车、NOA样例及必要合流优先权。测试直接调用真实候选，未用控制器mock。输入时间使用已存在的 `Vehicle.time`；原 `LocalTracks.observe` 已提供 `ego.time`。

TDD先将基线原件复制为候选，写测试并观察到4个预期断言失败（8项测试、3个测试方法中含2个子例）；随后实现。证据目录：

- RED：`results/operations/20261030T003054422101Z_literature_R_recovery_red_2d5c67d7/`，exit 1，failures=4，errors=0。
- 首次GREEN：`results/operations/20261030T003127842895Z_literature_R_recovery_green_168d42b2/`，exit 0，54项通过。
- 最终静态验证见 `manifest.json`。每次均通过 `scripts/run_logged.py` 生成独立日志，没有重用旧目录。

可复核入口：`python -I -B -S docs/experiments/2026-10-30-rule-trials/R/test_recovery.py --regressions`。`rules.patch` 仅表达候选规则相对于指定基线的差异；`manifest.json` 保存源码哈希。下一步由主代理冻结该源码，运行真实配对试验后决定是否采用；本候选未进入生产。
