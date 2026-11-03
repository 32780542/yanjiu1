# E / NC / F 独立审查

本审查只读实际候选和冻结 TM，不改生产、不改候选，也不重复 SUMO 筛查。
驱动为 `tools/review_direct_relief.py`，机器结果为 `review_direct_relief_verification.json`。
原 ABC/D 审查驱动与原 verification JSON 保持原 SHA 不变。

| 源 | SHA256 |
|---|---|
| 原 NC，且等于 ablation24 protocol 冻结值 | `fe6c9d6e0629358eee86dce7a46ad0068375939d5faaca0d21acebc2d64b218f` |
| E direct_gap，444 行 | `04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274` |
| F local_oneway_relief，454 行 | `f3a7acba6a812196d357cdccefb707ffec88df1e744d6f4dfc77ce26d916464d` |

## E 清理与 NC 对应

E 只删除 NC 的 `_make_room`、`_receiving`、`_receiving_distance` 三个函数和 `_decide` 中带恒 False 的 cooperation 分支。
从 NC AST 中删除该分支后，`_decide` 与 E 的 AST 完全相同；其余存续函数和类逐项相同。
因此这是对 NC 未运行代码的清理，不应另起一份同物理行为的筛查。

随机种子 `202611030931` 的 2000 组完整场景/记忆，三模式共 6000 次 Command+Memory 与 NC 精确相同。
E 对 TM 的 NOA、formation 各 2000 次也精确相同。比较包含已有 gap/lane_target/joining、pending 和横移状态，没有放宽浮点容差。
NC 的已有实验可以在明确控制等价关系和原 NC SHA 的条件下用于 E；原 NC 源码和失败结果仍应保留。

## F 增量

F 相对 E 的 AST 仅 `_decide` 改变，增加 10 行。
模块常量、导入、Vehicle/Command/Memory、跟驰、安全限速、间隙目标及横移执行逻辑均未改变。
未新增排序 track、通信、车型真值、邻车意图/私有阶段或全局槽位。

新分支只在准备区的 transform 存续车道执行。压力计数来自本车收到的 `[x−60,x+30]` m 窗口，
把当前中道及终止道车辆计为未来中道负荷、左道车辆作抵消；道路结构是共同已知条件，不读取其他车的动作意图。
只有中道本车且压力≥2、原 `_clear(ego,rows,0)` 成立时，才为本车请求 1→0，并沿用原 `_join_speed`。
新分支没有向其他车发命令，也不假定其他车会让行。

准备区中尚未进入既有执行分支的存续车道车辆会提前返回跟驰，停止新增自由补位请求。
在进入新分支前，原先已提交的 lane_target/pending/横移执行逻辑仍可能继续；因此不能把该政策描述成取消所有已开始的补位。

独立精确影子比较结果：

- F 对 E：NOA/formation 共 4000 次相同；准备区外共 6000 次相同；straight3 三模式共 6000 次相同。
- F 改 track 并倒序邻车 6000 次、加入远车 6000 次均相同，排序 key 无 `.track`。
- 2000 个 transform 场景中有 19 次与 E 不同，说明测试触及增量；其中 18 次实际 local_relief 输出均逐项验证本车中道、准备区、局部压力和原 clear0 条件。

以上是有限场景与 AST 合同，不是 SUMO 效率/拥挤/全工况安全结论，也不证明自主疏解必能解决给定死锁。
生产审查前后始终为 TM SHA `65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`。

## 独立记录

- 影子审查通过：`results/operations/20261103T033202861642Z_staggered-independent-E-NC-F-shadow-review-correct_385c288e`，退出 0，7.594 s。
- E 专项 5 tests：`results/operations/20261103T033245061723Z_staggered-independent-E-contracts_a0f4a494`，退出 0。
- F 专项 12 tests：`results/operations/20261103T033245073880Z_staggered-independent-F-contracts_e61cc6ed`，退出 0。
- 首次影子驱动因审查脚本先使用未绑定局部变量 ego 而退出，未产出通过 JSON；该失败为 `20261103T033134380525Z_staggered-independent-E-NC-F-shadow-review_8519140a`，记录保留。修复审查脚本后另起上述通过 operation，未改候选。
