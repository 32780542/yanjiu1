# H在既有E测试迁移下的核心回归审查

2026-11-03，只报告，不改H、E、生产、原tests或既有E迁移补丁。H SHA256 `bfd3080c166f63d07e401a9f106a27ae82c1dbcb7df96d92eb4b922c39d51a4e`；仍使用旧225项精确14文件，并仅内存应用先前已通过的E四test迁移。

operation `20261103T041256850432Z_H-core14-existing-E-migration_fc2e48b3` 退出1，用时21.64秒：**218通过、7失败、37子测试通过**。不能把此结果写成H核心225项全通过。逐项与源码身份见[H_core14_E_patch.json](H_core14_E_patch.json)。实际载入的两份内存测试文本SHA与既有E补丁目标一致，收集仍为225项。

## 七个失败的性质

| 失败测试 | 原预期与H实际值 | 分类 |
| --- | --- | --- |
| native_rules：`test_a_retained_head_adopts_the_two_lane_phase` | lane0/1同x时旧两道方向要求ego0减速；H采用固定物理三道平局偏好，目标706.666667m而非低于700m | 已批准的平局朝向取舍；phase常数仍原样为15/0，但误差使用幅度与稳定几何破平局 |
| native_rules：`test_a_free_head_rejoins_cross_lane_alignment_after_lateral_completion` | 物理完成后ego1与ego0同x，旧预期加速>28.8；H为28.400000000000002 | 同一平局朝向政策改变；任务完成后的相位恢复仍发生，方向反过来 |
| head_group_rules：`test_real_lane_one_head_a1_shares_phase_by_accelerating` | 固定真实帧A1旧目标1089.295196；H为1079.165559 | 旧政策要求越过另一道队首，H保持实际先后并拉开到15m |
| head_group_rules：`test_real_lane_zero_head_c1_shares_phase_by_slowing` | 同帧C1旧目标1087.498892；H为1097.628529 | 上述同一队首对的对称变化，H误差反号 |
| common_pair：`test_mode_dispatch_uses_640_for_transform_and_1000_for_formation` | 旧transform速度29.2；H为29.1；formation首项28.95仍通过 | 构型分配仍相同，但H不把实际+20m当作反向35m误差，旧限幅数值不再适用 |
| common_pair：`test_straight_and_outside_phase_geometry_matches_H` | 当前规则必须等于2026-10-29历史H误差；某例旧27.0，H为−2.9999999999999964 | 新相位政策有意改变旧H兼容范围；历史H源仍原SHA加载，不能替换历史参考来消除失败 |
| ending_pair_scope：`test_actual_ending_lane_keeps_three_lane_pair_geometry` | 精确 `forward==15 and backward==-15`；H为±14.999999999999996，双方pair_lanes均3 | 浮点计算次序差异，非构型/方向回归；先只报告，没有改该断言或四舍五入H源 |

头车A1/C1真实帧的H调整，是把既有11.537029m先后间隔拉向15m，而不是强求两车互换前后。这说明旧断言与新政策确有矛盾，但不能替代完整24/45车几何demo的结果。

## 保留的安全与历史边界

本次没有观察到NOA、真实前车CTH、硬安全限速、局部观测、当前横移执行或恢复/评价器回归失败；相关原测试和37子测试原样通过。H专项9项（含600个随机NOA命令/Memory等价及横移边界反对称）此前也已通过，来源见[H方法记录](../candidates/order_preserving_phase/method.md)。这属于有限场景回归，不是全工况安全证明。

H/P的归档loader、真实历史源及state-only档案保持原hash，历史物理等价比较没有改为H。上表旧H几何兼容断言是当前r与历史H的政策兼容测试；它失败不授权修改历史H文件。若后续采用H，需要单独审阅新相位的测试语义，目前不提供H测试迁移补丁。

生产、E、H、14份原tests及保护的归档在此运行前后SHA均一致。临时动态注入的source_snapshot局限沿用[E迁移说明](test_migration.md)：控制身份由driver的H路径/SHA记录，不把同进程unit-run的磁盘TM源码快照作为正式H交通证据。

H尚待实际队形、持续交错层与性能验收；0/1关系或TT改善不构成完整形成成功。本审查只解释兼容性失败，不改既有E锁定结果。
