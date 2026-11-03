# C：有效腾位交接

基线固定177f7a3。仅在 `_make_room` 原options加三条局部物理判据：head当前不能直接进中道；候选helper当前可进左道；假设helper离开后head可以进中道。保留原counts、window、anchor、max(x)排序、实际执行与安全。3行新增，无新参数、Memory、CF门槛或隐含意图。

暂时排除helper仅是反事实选择计算；真实执行仍检查实测横向占用，head不能提前当作已腾空。若当前就可合流或没有有效helper，则不为了counts额外腾位。可能丢失需要先纵向整形才可腾出的机会，交通收益需另验。

`build.py` 从Git重建独立候选到 `tmp/staggered_bottleneck/candidates/effective_handoff/native_rules.py`，保存统一diff及source.json，不改生产。参考与数学定义见[reference_design.md](../../methods/reference_design.md)。

验证入口：`tests/test_effective_handoff.py`，不设RULES_PATH时检验冻结基线，设置为候选路径时检验候选。

- 基线8项中4项按预期断言失败，另4项通过；operation `20261103T031425633873Z_effective-handoff-red_62b88da5`，退出1，保留原失败。
- 候选构建operation `20261103T031509116775Z_effective-handoff-build_f8dbd6f3`，退出0。
- 候选8/8通过，operation `20261103T031517652430Z_effective-handoff-green_8dcd3a75`，退出0。包含300个随机局部场景的NOA命令与Memory对冻结TM完全一致、ID重标/邻车次序/范围外车辆不改变helper位置、实际腾空前head不得入中道。
- 生产规则仍为SHA256 `65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`，无生产diff；候选SHA256 `9b7f80dc6f7f4fb6352f2fb8356fbf57cb14aef1aa03bb3b6c8457bb0002bbe4`。

以上是局部机制验证；未运行C交通仿真，不将静态通过写成交通性能通过。
