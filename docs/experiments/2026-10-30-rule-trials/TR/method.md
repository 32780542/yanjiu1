# TR：在T上检验R的增量作用

父源码为 `tmp/literature_trials/T/native_rules.py`，SHA256 `046f00aa397b7f4ff306f3fbb796c97565b743550a9dae608572e88f5a8cc02b`。复用R源码SHA256 `cba7c9a1fb74c25192fed4765c75626bb78117c0a5c6e3f1a6dfb9b9166f722d` 的既有恢复机制，没有增加新机制或调参，也没有组合T2。候选为 `tmp/literature_trials/TR/native_rules.py`；生产、Git及交通仿真均未改动或运行。

本车实测完成横移且没有待执行横移请求时，沿现有真实F/R间隙求当前可行的合流目标。只有其F仍是T选取的当前50米内实际前车时才交接。位置偏差从 **T当帧目标** `F.x−4−1.5−HEADWAY*ego.speed` 计算，速度偏差从 `F.speed` 计算；完成帧输出原合流请求。随后由 `_front_following(ego, rows, recovery=None)` 将两个偏差按既有R的线性权重 `w=max(0,min(1,1−(t−t0)/0.5))` 加在当帧T目标和真实F速度上。若本车速度发生变化，T目标仍按当前本车速度重算；偏差只代表完成时的组织参考交接。

`_following` 只在组织模式的调用路径上传入恢复记忆；NOA调用共享帮助函数时不传恢复、状态保持0，并清除残余恢复记忆。前车更换/丢失/离开走廊/超出50米组织链、开始新横移以及0.5秒到期的重置均沿用R。私有tuple、`gap` 清除及 `joining` 的短期保持也沿用R。`safe_speed` 和真实占道几何不做平滑；通用速度请求、必要合流及接收逻辑保持原有优先级。

9项真实规则静态测试覆盖完成帧位置/速度连续、相对于T的正确偏差、恢复期间本车速度变化、0.5秒有限恢复、实测完成反馈、失去/更换前车、NOA逐项匹配T及状态0、低速/巡航T平衡、真实停止前车安全、跟踪标识置换/远车，以及没有混入T2。

- RED：`results/operations/20261030T005415119764Z_literature_TR_recovery_red_5f302d01/`。在复制的父T上运行，9项测试、2个预期失败、0错误。
- GREEN：`results/operations/20261030T005445864100Z_literature_TR_recovery_green_7d86f934/`。9项测试通过，exit 0。

复核入口：`python -I -B -S docs/experiments/2026-10-30-rule-trials/TR/test_recovery_on_T.py`。补丁相对于父T，文件哈希保存在 `manifest.json`。静态通过只证明组合满足上述行为契约；增量交通价值须由主代理另做TR相对T的真实配对试验判定。
