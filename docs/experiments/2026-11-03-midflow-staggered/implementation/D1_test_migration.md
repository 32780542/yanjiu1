# 已安装 D1 的受影响测试迁移

本单元只迁移两份旧测试并新增便携合同，不改控制器。生产 D1 必须始终保持 SHA256 `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`。旧测试及实际磁盘红灯证据保留在版本历史与原 `installed_D1_legacy_contracts.xml/json`；本文件在修改测试前写入推导。

## 修改前的预期红灯：expected_red9

原磁盘 15 文件回归为 **224 passed、43 subtests passed、9 failed**。失败名严格为：

1. native `test_a_new_lane_head_uses_the_exact_lane_phase`
2. native `test_an_unstarted_fill_does_not_enter_the_ending_lane_after_640`
3. native `test_retained_head_couples_to_actual_ending_peer_without_a_fake_front`
4. native `test_selected_local_cell_survives_lateral_motion_and_completion`
5. native `test_upstream_extra_car_fills_the_nearby_missing_middle_slot`
6. native `test_visible_front_sequence_follows_the_nearest_physical_front`
7. braking `test_a_lower_braking_alternative_wins_equal_formation_benefit`
8. braking `test_cost_ranking_alternative_is_below_separate_severe_braking_bound`
9. braking `test_equal_speed_useful_fill_is_still_accepted`

修改前 SHA256：`test_native_rules.py=7040a00ac4a7104f14d714afeb98af4eed7ae5b01f2421d0c7fff528f32fa356`；`test_braking_cost_fill.py=10789e6a64c99476c835625481424961df024d2a9588fa094c8bfbc570879ac2`。不改其余测试，不 skip/xfail，不降低精度，不改安全、ID、NoA 不变量。

## 迁移推导

- **前车和相位三项（1/3/6）**：旧场景的道间数量明显不平衡，D1 新自由补位会合法覆盖纵向输出，因此整条 `decide` 的 gap target 不再等于相位/CTH target。新 lane-head 场景改用三道各两辆、没有下降机会的平衡实车布局，独立给出 15m 相位和 1m 扰动的解析期望。其余两个场景使用已 joining 的自身记忆隔离新自由补位，保留真实 reference、相位方向/幅度和最近前车断言。
- **真实空隙和执行两项（4/5）**：旧 useful-fill 让更前方 x300 的 source 车也成为 D1 候选，因此 x285 不再是 winner。改为 ego x285/lane0，source 后车 x255/x225，目标道 rear x255，另一外道 x270/x240；数量 `(3,1,2)→(2,2,2)`，Phi `14→12`，且 ego 是零成本中最前方 source 候选。跟踪原真实 rear 的同一 gap，检查新发起、横移中和到达后的 target/Memory，不再依赖格点 cell 编号。
- **接收范围一项（2）**：原 x639 场景已经看见进入准备段的 ending 车，D1 此时有意禁止新入 lane2。替换为 x625 的存续道车看见 ending x640/x670：明确验证尚未开始的 lane2 请求在本车到640前已取消并通过真实 gap 均衡到 lane0；moving 和本车 own pending 的已启动 lane2 动作继续执行。
- **成本三项（7/8/9）**：共用 useful-fill 使用上面的 `(3,1,2)` 场景；添加 lane2 x285/v25 后数量为 `(3,1,3)`，两侧向lane1均可使 Phi下降，均通过原8m clearance，且各自 gap目标在30m内。ego v28.8 的新后车无减速损失；lane2替代者 v25 对同一 rear 独立产生0.76m/s公开CF损失，仍低于每帧1m/s独立制动上限，因此应按成本选ego而不是靠排除替代资格通过。原严重制动与“旧道释放不得抵销新后车制动界”保持独立物理算式和正收益反例。
- **新增便携合同**：仅从安装包 `noa.native_rules` 导入，覆盖 future 配道资源与下降、实测y/vy目的资源计数、D1偏心自身排除后的同gap执行、合法NoA状态0与原硬安全，不依赖临时候选或Git。

## 执行记录

实际修改仅为获准的两份旧测试及新增 `test_local_formation_balance.py` 六项便携合同。前者六个 native 场景按上文迁移；成本文件更新共用实际机会 fixture，添加明确的真实gap/clear/严格负荷下降资格断言。原严重后车制动界、净释放正收益反例、mandatory merge、ID/排列、邻车私有字段、感知外车辆、公共CF及安全断言均保留。

fixture 推导期间另核对过另一外道 x300/x270：增加 lane2 x285 替代者后，前方 x300 也变为低成本合法候选，会盖过所需的两候选比较。因此正式 fixture 使用 x270/x240；这只是测试场景消除第三个更优候选，没有修改 D1 或按返回值放宽资格。两侧 x285 的机会均满足同一负荷收益、clear8、真实gap与制动界，故成本排序确实决定 winner。

原 `verify_installed_D1.py --tag migrated_core` 在实际 variant 目录、真实磁盘模块上运行，**239 passed、51 subtests passed、0 failed**，pytest 20.96秒。共16文件（原15+新portable）；没有模块注入、skip/xfail或放宽精度。新报告为 [installed_D1_migrated_core.json](installed_D1_migrated_core.json) 及同名 XML；原9红灯报告未覆盖。operation `20261103T141053480793Z_D1-installed-migrated-core-on-disk_597a4640`，exit0、23.125秒，stderr空。

验证后另按原红灯 metadata 对照全部磁盘 SHA：只有获准的两份旧测试改变，其余13份旧测试与D1源码保持原字节；新portable按其实际新SHA登记。审计见 [D1_test_migration_audit.json](D1_test_migration_audit.json)，完整三文件差异见 [D1_test_migration.patch](D1_test_migration.patch)，修改前文本另在 `D1_test_migration_before/` 只读保留。

新 SHA256：

- `test_native_rules.py`：`147f5168306cfe4e904a06dbecaa91805539c2069735e92dc7d5e83793d2d035`
- `test_braking_cost_fill.py`：`6377ea192c17b9f1dd0a24a5a828d5917f5cd6650533909aa2c774a32fe17308`
- 新 `test_local_formation_balance.py`：`5973ef9f9760d133c2f5fcf6c0b681285a83b58ab0d01d5b41dcd516f256e26e`

新旧映射见 [D1_test_migration_sources.json](D1_test_migration_sources.json)。源从开始、运行中到结束均为锁定 `2be889…f35a`，未执行Git操作或交通仿真。首次完整磁盘绿后已通知root，未扩大测试范围。
