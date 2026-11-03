# E正式核心回归迁移审查

2026-11-03。生产仍为TM，SHA256 `65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`；只在审查进程内把 `noa.native_rules` 绑定为444行E，SHA256 `04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274`。原测试、生产源与历史冻结资料均未编辑。

**结论：旧225项中4项依赖已删除的协作政策；其余221项及37子测试在E上直接通过。** 对这4项作限定的行为迁移后，原14文件仍收集225项，225项和37子测试全部通过。没有发现需要修改E实现的安全、局部信息、NOA、CTH或已有横移执行回归失败。该结论限于本次精确测试选择；不是全工况安全证明。

## 精确恢复原14文件

原入口来自 `variants/phase5g_pure_formation/results/operations/20261030T011348789879Z_literature-TM-final-core_219b48fd/started.json`；该JSON SHA256为 `b30de6fd42cc6de54b3f6a249250967e383b15f68c4dd4f3cdcd520f866d875c`。保留原 `-q -p no:cacheprovider`，增加JUnit记录；没有按失败结果删除文件或测试。

| 原选定文件 | 原项数 | E上未迁移的通过/失败 | 子测试通过 |
| --- | ---: | ---: | ---: |
| test_native_rules.py | 46 | 43 / 3 | 2 |
| test_native_sumo.py | 17 | 17 / 0 | 6 |
| test_native_comparison.py | 31 | 31 / 0 | 6 |
| test_native_recovery.py | 15 | 15 / 0 | 0 |
| test_global_reference.py | 15 | 15 / 0 | 6 |
| test_complete_layers.py | 24 | 24 / 0 | 3 |
| test_bottleneck_attribution.py | 14 | 14 / 0 | 2 |
| test_own_lane_execution.py | 10 | 10 / 0 | 4 |
| test_head_group_rules.py | 8 | 8 / 0 | 0 |
| test_common_pair.py | 9 | 9 / 0 | 0 |
| test_ending_pair_scope.py | 2 | 1 / 1 | 0 |
| test_formation_state.py | 15 | 15 / 0 | 0 |
| test_time_headway.py | 7 | 7 / 0 | 5 |
| test_braking_cost_fill.py | 12 | 12 / 0 | 3 |
| 合计 | 225 | 221 / 4 | 37 |

## 四个旧预期及人类可读的新预期

补丁只有两个文件、四个测试，见[test_migration.patch](test_migration.patch)。测试计数保持225；没有skip/xfail或删除测试。

| 原测试 | 为何旧断言不适用E | 新预期及保留的约束 |
| --- | --- | --- |
| `test_middle_front_car_makes_room_in_the_other_retained_lane` | 指定six场景中要求中道ego执行旧helper选举的1→0 | E不接收远处指派的helper角色；该场景保持原车道、不建立lane_target，不发布make_room/prepare_room/open_gap |
| `test_a_helper_tracks_the_gap_while_the_rear_opens_space` | 先靠旧helper分支生成Memory，随后人为给ego横向运动；删helper后第一步不再提交任务，后半段便缺少本车任务上下文 | 明确给本车已提交的 `Memory(lane_target=0,joining=True)`，保留原实测横移和后车650m/20m/s情景，仍要求真实目标gap中点675m；没有放宽执行断言 |
| `test_an_ending_lane_follower_does_not_get_a_virtual_merged_rank_at_640` | 旧整条命令在640前后依赖ending_follower保持源道跟驰，要求目标只平移2m；E在准备区开始接近本车真实F/R空隙，控制目标会切换 | 仍检验真实前车链在639→641时前车track不变、三道following目标平移2m；E进入准备区后必须用实际 `(front=4,rear=3)` gap，中点671.5m，走廊未clear不得横移，硬safe_speed继续成立 |
| `test_separate_ending_unit_waits_using_its_actual_three_lane_phase` | 直接断言旧reason=ending_follower | 相同实车场景改为approach_gap；保持不能横移、速度高于巡航的原断言，并新增真实单侧gap `(None,middle.track)` 与目标715m断言；同文件的实际三道pair几何测试原样保留 |

第三项的原失败为after.target=671.5m、旧预期652m。这不是串稳定或硬安全失效，而是进入准备区后从源道前车目标改为眼前真实空隙目标。补丁同时保留前车跟驰几何的原连续性意图，不能简单把旧断言改成当前数值了事。

## 历史H/P资料保持原冻结含义

`test_common_pair.py` 的H对照仍直接加载 `portable_H/source/noa/native_rules.py`，SHA `77c0111530560db30e97dc466bcdaf276a78cb7dd7192767e9a2d51b97eab2d2`。该文件中历史body/NOA比较仍通过 `archived_rules_source.load_state_enabled_base` 读取原封存源。

`test_formation_state.py::StateOnlyChangeTests::test_control_and_memory_match_frozen_P_across_local_states` 继续比较历史state-only版本与历史P；没有把历史物理等价要求改为“E等价P”。state-only源由原 `evidence.tar.gz` 的 `current_source/noa/native_rules.py` 读取，并核SHA `ac1c5aba082130718c81a23eb2c7bc9708caa8dae6b138baea951d07e735ee7d`。这两个文件均不在迁移补丁中。

迁移驱动另锁住上述H/P源、state-only档案及archive loader的磁盘SHA，运行前后逐项一致。`test_head_group_rules.py` 虽保留旧E11命名，其当前真实前车CTH与队首几何约束仍有效，8项原样在E上通过。

## 实际运行和失败留存

- 原14文件动态E注入：operation `20261103T035209222502Z_E-core14-raw-injection_0e954c95`，退出1，221通过/4失败/37子测试通过；原失败及逐项报告保存在[core14_raw.json](core14_raw.json)。
- 补丁生成：`20261103T035621743905Z_E-test-migration-patch-build_22586478`，退出0。原始与内存修改文本SHA见[test_migration_sources.json](test_migration_sources.json)。
- 第一次内存补丁验证 `20261103T035706357137Z_E-core14-migration-in-memory_37e16efe` 退出1：pytest断言重写loader先于审查loader，实际加载的仍是原测试，因此重复相同4个旧失败。[core14_migrated.json](core14_migrated.json)保留该驱动失败，未更改补丁或E来掩盖它。
- 修正审查驱动后，先只收集：`20261103T035911722877Z_E-core14-migration-collect-check_b9c8a6ae`，退出0；仍225项，并核对两份内存文本SHA确实载入。[core14_collect_v2.json](core14_collect_v2.json)。
- 全14文件迁移验证：`20261103T035924499388Z_E-core14-migration-verified-loader_940e15f1`，退出0，20.937秒；**225项与37子测试全过**，执行时原源码/14tests/冻结资料SHA均未改变。[core14_migrated_v2.json](core14_migrated_v2.json)。
- 原新增E五项当前行为合同文件保持原样，另fresh通过 `20261103T035738754651Z_E-contract5-migration-review_ee9b5790`，5/5，明确从E路径加载。
- `git apply --check` 对原测试工作树通过，operation `20261103T040226936481Z_E-test-migration-git-apply-check_1a23e7c8` 退出0；只是检查补丁可应用，没有应用或修改测试。

## 复核方式与边界

[run_core_with_rules.py](run_core_with_rules.py) 从旧started.json恢复精确文件列表，在内存注入E。带 `--patch` 时只把补丁hunk应用到字符串，通过原SHA与修改文本SHA双检验；保留原 `__file__`，使fixtures、H/P资料和archive相对路径仍指向原处。pytest配置后才插入内存loader，最终报告核对实际载入两份文本SHA，避免再次发生“记录有补丁、运行的仍是旧文本”。

```powershell
python -B scripts/run_logged.py --label E-core14-review-new --timeout 300 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/implementation/run_core_with_rules.py --report docs/experiments/2026-11-03-staggered-bottleneck/implementation/NEW_REPORT.json --patch docs/experiments/2026-11-03-staggered-bottleneck/implementation/test_migration.patch
```

本审查的SUMO单元用例由同进程 `native.run_case` 调用，控制模块是已注入E；原 `_source_snapshot` 则按磁盘路径复制六源，仍可能记录磁盘TM。E执行身份由本驱动独立记录的E路径/SHA证明，这些临时unit-run输出不用于正式E交通性能/源码封存归因。正式批次继续使用冻结独立目录与原runner，不能以本审查替代其证据。

本补丁已经内存验证，尚未应用到原测试或提交。后续实际安装E时可审阅后应用这份最小迁移；当前主规则及原tests仍保持原字节。
