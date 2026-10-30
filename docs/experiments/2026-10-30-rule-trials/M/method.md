# M：自主形成补位的局部制动成本排序

本候选按已批准的[文献建议 §4](../../../research/2026-10-30-literature-review/文献结论与方法建议.md)实现，仅供配对真实 SUMO 筛查，尚无交通改善结论。

基线 Git：`8ed11d90ac457269b2175e20aec5ba1bbba8a318`。规则源：`variants/phase5g_pure_formation/noa/native_rules.py`，基线 SHA256：`ac1c5aba082130718c81a23eb2c7bc9708caa8dae6b138baea951d07e735ee7d`。

候选完整规则位于 `tmp/literature_trials/M/native_rules.py`，SHA256：`a23321ebae6f291994275e6239f47c585eeabd36b844d6b2879e81955340839c`。公开差异为 [rules.patch](rules.patch)。未改生产文件，未建分支、暂存、提交或推送。

## 规则

1. 原 `_fill` 的局部车群、缺位、负荷改善、相邻道、30/15 米相位、已完整层保护与 8 米走廊条件全部保留。
2. 新增公开统一估计器 `cf_speed(car, rows)`：50 米内最近实际前车使用原 `_request` 的 30 米跟驰；没有该前车则以原巡航速度为参考；再取现有 `safe_speed` 的较小值。不读邻车的记忆、意图、加速度、0/1 或提交状态。
3. 对同一观察者当帧有限邻车表，比较保持与候选车已处于目标道的两张物理快照；只变候选车横向位置和车道，不推进时间，不改变任何车纵向位置或速度。比较候选车、新道直接后车、原道直接后车；后车跨占两道时按局部 track 关联去重。
4. 成本为 `C = Σ max(0, v̂_keep − v̂_change)`；即三个受影响者的非负纵向响应损失，等价于共同 0.1 秒步长下的响应加速度损失排序。改善项不抵消损失项。在已有形成收益的候选中先取较小 C，再沿用原几何排序。没有要求自车获得正加速度收益，因此有用的等速补位仍可执行。
5. 目标道直接后车单独满足 `v̂_change >= v_rear − BRAKING × 0.1`。这里 0.1 秒来自现有原生 SUMO 控制步，`BRAKING=10 m/s²` 来自现有物理参数，等价于其请求减速不超过 10 m/s²；未引入可调礼让系数、舒适阈值或成本权重。其他车辆释放收益不能绕过该条件。

只修改 `_fill` 并新增 `cf_speed`；`_request`、`_following`、必要合流、进入与执行、安全、入口、0/1 和所有全局常数均保持原 AST。缓存只在当前 `_fill` 调用内按局部 track/目标道索引，不保留跨帧状态，也不以 track 大小排优先权。

## 验证与限制

[test_braking_cost_fill.py](test_braking_cost_fill.py) 的首轮 7 项测试在冻结基线上出现 2 个预期行为失败：严重后车制动仍准入，以及几何平局未选较低代价者。补充 CF 合同后的 9 项基线测试有 4 个预期失败（另 2 个为公开估计器不存在），候选 9 项通过；再补充净收益不得抵消严重制动、较温和扰动的排序、邻车私有字段不变性和有限感知边界，最终 **13 项通过**。证据索引见 [evidence.json](evidence.json)。

现有 `test_native_rules.NativeRulesTests` **46 项在基线与候选均通过**。额外自定义静态兼容性探查共 72 项，两边均 69 通过、3 个完全相同的历史断言失败、0 errors；这不是官方测试入口失败的声明。三项均来自 `test_physical_following.PhysicalFollowingTests`：

- `test_a_join_is_finished_longitudinally_before_another_free_fill`：原 `_decide` 在当前目标与速度已对齐时清除 joining，断言仍要求 True。
- `test_heads_align_the_first_row_instead_of_accepting_a_one_row_offset`：现有相位速度限幅及渐进响应给出目标 706.6667，断言要求旧目标 730。
- `test_real_negative_reference_cycle_has_no_cross_lane_speed_feedback`：从零速按现有 0.2 速度响应请求 5.36，断言要求至少 26.8。

[diagnose_legacy_assertions.py](diagnose_legacy_assertions.py) 用两个独立命名模块证明这三项的命令、记忆、`_following`、`_fill` 输出逐项相同；三例 `_fill` 都返回 None。没有为历史断言修改无关规则。静态回归加载器的中间改写曾漏设模块 `__spec__`，导致 46 个 `find_spec` 加载错误；已改回 `module_from_spec`，最终结果以 `valid-spec` 日志为准，原错误日志保留。

范围偏差：最初回归加载整个 `StateOnlyChangeTests` 时误执行其单个 3 秒真实 SUMO 记录测试（通过，临时输出由原测试删除），还包含了本来要求动作与旧 P 完全一致的断言。该运行不作为 M 交通验证；随后明确只加载静态类，没有再运行仿真，也未运行仿真批次。该偏差及完整日志保留供复核。

物理估计假设与可行性限制：这是统一公开跟驰模型的当帧反事实，不能声称知道 HDV 的实际控制器；没有看到的后车不进入成本，有限视野外的交通不能补造；横移过程和纵向入列参考没有在成本中展开。原源道后车释放改善被保守忽略；除目标后车独立上限外，没有附加总成本门槛，因此仅有一个可行形成候选时仍可能付出有限扰动。10 m/s² 是沿用已有物理制动上限，不能称为舒适制动。本候选与时距/参考平滑候选保持独立，若组合必须重新核对统一 CF 估计器。采用与否留给后续同输入真实 SUMO 对照。

复现（仓库根目录；均经 `python -B scripts/run_logged.py --label <唯一名> --timeout 60 --` 包裹）：

```text
python -B docs/experiments/2026-10-30-rule-trials/M/test_braking_cost_fill.py --source baseline
python -B docs/experiments/2026-10-30-rule-trials/M/test_braking_cost_fill.py --source candidate
python -B docs/experiments/2026-10-30-rule-trials/M/run_affected_regression.py --source candidate --suite native
python -B docs/experiments/2026-10-30-rule-trials/M/diagnose_legacy_assertions.py
```
