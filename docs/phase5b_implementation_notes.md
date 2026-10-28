# Phase 5b 有界实现与 TDD 证据

日期：2026-09-13。实现工作目录为 `D:/yanjiu1/keyan1/variants/phase5b_conservative_release`。

## 修改范围

- `noa/r5.py`：在原 deadline 分支新增 3 行。期限已到且当前 assessment reason 为 `ambiguous` 时，沿用 `YIELD`，阻断并报告 `expired_ambiguous_wait`。deadline、episode 关联流程、私有 RNG、draw_count 不变。
- `tests/test_phase5b_release.py`：9 项新测试；两个控制采样间隔均为 0.1/0.05 s。覆盖持续 ambiguous、相同私有状态、原 1/2 不同私有状态共享 0.5 s 行为格、精确到期与同时间重复调用、不提前放行、可见 ego-front 释放与重新 ambiguous 阻断、全部 HARD_YIELD reason、UNKNOWN、稳定 clear/再入、每 episode 一次 draw、无准备/无 plan 与原真实让行守卫调用。
- `tests/test_phase5_r5_controller.py`：仅更新 5 项冲突旧用例。持续 ambiguous 和到期 JSON 状态检查改为 YIELD；最低速度、到期 guard 拒绝、准备/行为时钟用例改用由 -1.99 m 到 -2.01 m 的真实可见 ego-front 输入。保留负向断言；到期 guard 用例仍要求 `expired_but_guard_blocked`、候选拒绝证据、期限不重启、draw_count=1、plan=None。

其余生产源码没有由本实现代理修改。INPUTS 计划绑定、完整回归、正式固定 17 变体与标准重放由主任务处理。

## 实际命令与日志

以下三条命令均在上述新副本目录执行，Python 为 3.12.9。每次 wrapper 都创建新目录；无覆盖旧尝试。

RED（生产代码尚未修改）：

```powershell
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -B scripts/run_logged.py --label phase5b_release_red --timeout 600 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -B -m unittest discover -s tests -p test_phase5b_release.py -v
```

日志：`variants/phase5b_conservative_release/results/operations/20260913T041816571054Z_phase5b_release_red_30eb41fb`。退出码 1；9 项测试、18 个子情形断言失败，无测试 error。代表性失败：到期返回 `('ELIGIBLE', 'private_backoff_expired', False)`，控制器在 1.35/1.4 s 开始准备，违反新增等待断言。RED 后仅移除新测试未使用的 import，断言未调整。

GREEN：

```powershell
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -B scripts/run_logged.py --label phase5b_release_green --timeout 600 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -B -m unittest discover -s tests -p test_phase5b_release.py -v
```

日志：`variants/phase5b_conservative_release/results/operations/20260913T041922272382Z_phase5b_release_green_b2dd1f3c`。退出码 0；9/9 通过，测试耗时 0.434 s，wrapper 0.875 s。

旧 R5 相关回归：

```powershell
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -B scripts/run_logged.py --label phase5b_r5_related_green --timeout 600 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -B -m unittest discover -s tests -p 'test_phase5*r5*.py' -v
```

日志：`variants/phase5b_conservative_release/results/operations/20260913T041934338104Z_phase5b_r5_related_green_93092d5f`。退出码 0；51/51 通过，测试耗时 91.189 s，wrapper 91.640 s。包含 controller、固定场景/私有状态、记录、失败前缀、标准重放/篡改拒绝。wrapper 已确认 private Windows Job 活跃进程为 0；三次完整 stderr 与元数据保存在各自目录。

## 本次实现文件 SHA256

| 文件 | SHA256 |
|---|---|
| `noa/r5.py` | `3425ab301eaab7aae785159efeb036dc18ff83c5a3c47db7fd65d8c504fe1201` |
| `tests/test_phase5_r5_controller.py` | `b99d7cf07a28beea8041d31f5a8725fd87e5529dfbd700ffce0c21bce7f49fb0` |
| `tests/test_phase5b_release.py` | `1525554d5927edb1694a42cf1265753f0acc09e2593062749e50c2fd21f9ad65` |

## 边界与待主任务完成项

这些证据证明所测离散规则及原 guard/clock 边界，没有证明竞争通行、编队改善或一般安全。HARD_YIELD 全枚举测试是 gate 输入契约；真实几何分类继续由原 R5 测试覆盖。相同/不同私有状态使用继承的 1/2，未搜索新状态；它们共享 0.5 s 行为格，但 0.05 s 控制格不保证相同。新旧控制采样的完整动力学、受影响全回归、独立审查、正式 17 变体与标准重放均须由主任务继续验收。本实现代理没有启动正式 17 变体 run。
