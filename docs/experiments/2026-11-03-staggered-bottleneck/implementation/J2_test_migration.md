# J2正式225项核心迁移审查

2026-11-03。只在进程内注入J2，SHA `895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689`；E、J2、生产、原14份tests及历史H/P资料均保持原字节。精确选择仍来自2026-10-30正式225项的started.json，见[E迁移说明](test_migration.md)。

**结论：固定E四项迁移后，J2为212通过、13失败、37子测试通过。13项中12项依赖旧相位/队首政策，1项依赖大坐标相减恰好舍入到整数15。没有观察到需要修改J2的真实前车reference/CTH目标、硬安全、NOA、局部输入或执行回归失败。** 独立的J2迁移补丁在内存验证后，原14文件仍收集225项，225项和37子测试全部通过。

这只完成测试语义迁移。是否采用J2，仍由父代理的交通与长路真实几何验收决定。

## 原失败与明确的新预期

下表名称省略`test_`前缀。每项保留原场景的有效意图，使用固定物理0/15/0相位、实际互选边及公开公式推导；不直接把观察输出作为新常数。

| 文件/旧测试 | 根因 | 新几何或公式预期 |
| --- | --- | --- |
| native_rules / `equal_distance_actual_heads_use_signed_geometry_not_track_order` | 两车相位误差绝对值均26m，旧有符号键选后车；新第二键abs(dx)选11m前车，而非41m后车 | 固定误差为+26m，三道归一化后仍clip到+2m/s，head速度为CRUISE+.4；重标/倒序仍完全相同，reference仍None |
| native_rules / `retained_lane_head_does_not_follow_an_ending_car_behind` | 准备区实际lane2仍存在，J2允许中道与它互选；旧政策把它排除 | dx=−30、相位差−15，实际三道边归一化后clip为−2，速度CRUISE−.4；reference必须None，不能把跨道车变成真实前车 |
| native_rules / `retained_lanes_restore_their_missing_cell_before_the_drop` | 旧有限队列的缺格按两道15/0构造 | 固定0/15下，outer为785/(缺755)/725，middle为770/740/710，本车755是middle多余车。补入755后两道q=x+φ均为785/755/725；准备区及整体平移300m后仍须lane0、fill_layer |
| native_rules / `a_retained_head_adopts_the_two_lane_phase` | 旧两道强制翻为15/0 | 两道与三道存续车道均为0/15；lane0与lane1同x时前者误差+15，应请求正向+.4，而非旧负向 |
| native_rules / `a_free_head_rejoins_cross_lane_alignment_after_lateral_completion` | 横移完成后的旧相位方向相反 | ego为lane1、peer为lane0同x，误差−15，应恢复到CRUISE−.4；仍必须清lane_target/gap，并保留joining语义 |
| head_group_rules / `real_lane_zero_head_c1_shares_phase_by_slowing` | 真实固定帧A1/C1沿旧两道方向要求交叉换序 | 固定相位误差A1.x−C1.x+15=+3.462970535m；C1目标为自身x加该误差，速度继续由原_request推导 |
| head_group_rules / `real_lane_one_head_a1_shares_phase_by_accelerating` | 同一对的反向旧政策 | C1.x−A1.x−15=−3.462970535m；A1目标按此反对称误差调整，不能沿旧方向加速 |
| head_group_rules / `internal_b1_follows_only_its_physical_front_c1` | 旧body只CF，新body也耦合 | C1仍是真实reference，target仍C1.x−D(v_B1)。互选body A2给出e=A2.x−B1.x+15=+.728852021m，速度为原CF+.2×.3×e，即增加.043731121m/s |
| head_group_rules / `internal_a2_follows_only_its_physical_front_a1` | 同一body对的反向旧政策 | A1 reference及CTH target保留；B1边误差−.728852021m，原CF速度减.043731121m/s。测试仍显式覆盖0/MAX夹紧公式 |
| common_pair / `straight_and_outside_phase_geometry_matches_H` | 当前规则被要求与历史H的两道翻相位兼容 | 当前raw error始终dx+15，pair_lanes仍原共同构型。历史H原源继续加载；三道差0、两道与当前差30m，明确保留两者区别 |
| common_pair / `mode_dispatch_uses_640_for_transform_and_1000_for_formation` | 原transform raw误差含翻相位，得到限幅29.2 | lane1x650、lane0x670的raw error为20−15=5；formation/transform按共同构型3/2分别除2/1，速度为28.95/29.1。原跨边界反对称断言保留 |
| ending_pair_scope / `actual_ending_lane_keeps_three_lane_pair_geometry` | `_physical_phase`对实际浮点y=4.949999999999999给14.999999999999996；旧大坐标相减曾舍入成整数15 | 不增容差、不round。保留pair_lanes双方恰为3、离散_phase恰为15/0，并严格等于实测y的连续physical_phase差，前后误差严格反对称 |
| formation_state / `other_lane_body_is_not_a_mutually_selected_head` | 旧状态1限定跨道head关系 | ego90与相邻道body100确实互选，即使body另有真实front145也应报1；同时断言body真实front仍是145，不能读取邻车flags |

12个政策冲突中，真实body的CTH目标/ref断言在原始J2运行中已经通过，失败的是“最终速度必须只等于CF”的旧限制。J2的body速度有明确上限±.4m/s，最终decide的硬safe_speed仍覆盖它；相关原安全测试未迁移。

原J2专项合同还独立覆盖并列三串的所有body/head应有±.4、30/15平衡、真实前车保留、50m边界、重标/远车等价及NOA完整Command/Memory精确等价，见[共同方法记录](../methods/J_JT_local_coupling.md)。本次没有用这些专项合同代替原225项。

## 补丁范围与历史冻结

[J2_test_migration.patch](J2_test_migration.patch)直接针对当前未迁移的原tests，**包含原E四项及上述J2十三项**，五个文件、17项行为迁移；不要先apply E补丁再叠加本补丁。没有skip、xfail、删除测试或扩大数值容差，仍225项。生成器为[make_J2_test_migration_patch.py](make_J2_test_migration_patch.py)，原/内存文本SHA见[J2_test_migration_sources.json](J2_test_migration_sources.json)。

以下历史比较函数的AST与原tests完全一致，仍加载各自原hash源，不改为J2比较：

- `test_all_actual_front_body_actions_remain_H_exact`
- `test_NOA_is_unchanged_even_with_compressed_rears`
- `test_control_and_memory_match_frozen_P_across_local_states`

`test_common_pair.py`中当前r与历史H的相位兼容测试可以随当前政策更新；其中历史H本身不能更新。上述新的两道30m差值断言明确防止把历史参考重绑为J2。`test_formation_state.py`仅改当前局部关系测试，文件内历史P比较原样保留。

旧E/H补丁、报告未覆盖。审查driver仅把元数据文件名由固定`test_migration_sources.json`推广为与patch同stem的`*_sources.json`，并支持返回经双SHA验证的内存文本，便于组合原E补丁；原E/H调用含义不变。原先必须恰好两文件改成按元数据精确匹配实际文件数，J2五文件实际载入的文本SHA全部与登记一致。

## 运行证据

| 步骤 | operation | 结果 |
| --- | --- | --- |
| J2 + 固定E四test patch | `20261103T050420987743Z_J2-core14-existing-E-migration_65e99752` | exit1，14.610s；212/13，37子测试通过 |
| 生成独立J2迁移patch | `20261103T050828274049Z_J2-test-migration-patch-build_2d04ff46` | exit0；原tests未写入 |
| J2 + 独立J2 patch内存验证 | `20261103T050839655099Z_J2-core14-migration-formula-check_3b74b31d` | exit0，14.234s；225项、37子测试通过 |
| git apply --check | `20261103T050839675572Z_J2-test-migration-git-apply-check_d324783b` | exit0；只检查，未apply |

原始逐项记录[J2_core14_E_patch.json](J2_core14_E_patch.json)与迁移后[J2_core14_migrated.json](J2_core14_migrated.json)均保留。原失败分布为native_rules 5、head_group_rules 4、common_pair 2、ending_pair_scope 1、formation_state 1；其余九文件原样通过。两次完整运行收集均为225，保护文件SHA字典完全相同；driver还逐次断言运行前后磁盘SHA一致。

```powershell
python -B scripts/run_logged.py --label J2-core14-review-NEW --timeout 300 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/implementation/run_core_with_rules.py --rules tmp/staggered_bottleneck/candidates/local_phase_coupling_physical/native_rules.py --expected-sha 895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689 --report docs/experiments/2026-11-03-staggered-bottleneck/implementation/NEW_REPORT.json --patch docs/experiments/2026-11-03-staggered-bottleneck/implementation/J2_test_migration.patch
```

动态注入的`source_snapshot`局限沿[E原说明](test_migration.md)：控制实际为driver记录的J2路径/SHA，但同进程unit-run仍可能按磁盘路径把TM复制为snapshot。不得用本次单元输出作正式J2交通来源证据。原路/长路demo及600秒交通批继续由父独立冻结源验收，本审查没有重跑它们。
