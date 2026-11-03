# H：保留实际队首先后次序的交错配对

2026-11-03。父源固定444行E，SHA256 `04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274`。H为独立445行候选，SHA256 `bfd3080c166f63d07e401a9f106a27ae82c1dbcb7df96d92eb4b922c39d51a4e`。只改 `_pair_error`，新增 `math.copysign` 导入；E、生产、核心原tests及E已跑批次均未改变，未在本子任务跑交通仿真。

## 具体假设与公式

同一对相邻道实际队首已经相差+15m或−15m时，都具有交错关系。原E只接受其中一种方向；构型3→2相位符号翻转后，另一种有效交错会被当作30m误差继续调距。H让实际纵向先后决定交错朝向。

沿用E原有共同 `pair_lanes` 判定，设

```text
dx = peer.x - car.x
d  = abs(physical_phase(peer,pair_lanes) - physical_phase(car,pair_lanes))
sign_source = dx
              or (physical_phase(car,3) - physical_phase(peer,3))
              or (car.y - peer.y)
error = dx - copysign(d, sign_source)
```

`or`只在前项恰为0时使用下一项，是确定的几何字典序破平局；无驾驶阈值、Memory、邻车flags或ID优先权。实际非零dx优先，因此±15m均为零误差。±45m仍分别为±30m误差，没有30m取模。

两车交换时dx、固定物理三道相位差及y差均反号，而d不变，所以误差反对称。若三项均0，双方y相同使d也0，error自然为0，不增加其它fallback。

## 两次必要的设计取舍

1. 恰同x时不能继续随当前pair_lanes选择旧相位偏好。lane0/1同x从639平移到641、boundary640时，旧三/两道Δphase翻号，会使误差从+15跳成−15。H的平局方向固定读取物理三道phase，因而跨640/1000不翻转。这里固定的是已知道路几何，不是全局交通状态。
2. 固定三道phase仍可能有第二重平局。例如同x、car(lane0,y=3.3)、peer(lane1,y=6.6)：三道phase双方都是7.5，但两道phase为7.5/0，故d=7.5。仅以前两项给copysign会使两车误差同号；最后的物理y差解决这一退化平局。该反例已收入测试。

非零dx时的距离幅度继续使用实际横向位置插值，跨车道中心连续。dx穿过0时仍有选择交错朝向的分支，不声称整个动态邻居系统具有全局光滑性或稳定性证明。

## 保留的范围与几何验收边界

- 真实同道前车CTH仍先返回；跨道调相仍只来自50m内实际相邻队首的当拍互选。没有改变前车链、gap目标、安全裁剪、fill或执行器。
- NOA仍不用此队首相位法。H不叠加D的静态相位改写、A的gap投影或F疏解。
- 三头相邻图的两侧可各自选取实际交错朝向，外侧队首可以相差0或30m，前端可能缺层。接受一对±15m不等于整组已形成完整层。
- E的24/45车真实demo尚未恢复完整15m交错；H必须用实际轨迹检查是否改善同道30m巡航间隔、相邻道交错、完整层及持续时间。0/1关系人数和TT改善均不能替代该几何验收。沿用既有几何评价，不为H另改完整层标准。

## 红绿证据

`tests/test_order_preserving_phase.py` 共9项，覆盖两种±15m交错方向不调距/不调速、交换反对称、同x并列跨640/1000、横移边界反例、无30m取模、横向phase幅度连续、真实前车优先、ID重标/远车及600个随机NOA完整Command+Memory对E精确相同。

- 初始E红：operation `20261103T040848269962Z_order-preserving-phase-red_1fc29cd0`，9项内16个预期断言/子断言失败。
- 构建：`20261103T040946828025Z_order-preserving-phase-build_60919302`，退出0；AST逐项确认只有指定函数和导入改变。
- 首次候选验证 `20261103T040948032846Z_order-preserving-phase-green_1cefd919` 保留为失败：测试误用精确浮点相等，将 `30.000000000000004` 与30.0判不同。只把该几何浮点断言改为标准assertAlmostEqual，候选算法字节未变。
- 更正测试后E重新红：`20261103T041018837664Z_order-preserving-phase-red-precision-corrected_5913f4ab`，仍16个预期失败。
- H最终绿：`20261103T041020142176Z_order-preserving-phase-green-precision-corrected_07e19ae6`，9/9通过，退出0。

以上证明指定局部几何合同成立，不提供尚未运行的交通收益或实际完整编队结论。
