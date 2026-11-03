# M核心回归：四项明确PD期望

固定M源 `a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762`。父已用既有J2迁移运行原14文件，221项及37子测试通过、四个head_group_rules测试失败，原报告[M_core14_J2_migration.json](M_core14_J2_migration.json)保持。四项均是假定只有P项的旧期望，没有真实front/ref、CTH目标或安全失败。

新[M_test_migration.patch](M_test_migration.patch)直接针对当前原tests，包含完整J2迁移，**相对J2内存文本只改上述四函数的相位公式**。内存验证原225项和37子测试全部通过；不改原tests、M源或J2/E/H旧patch/report，不skip、不增加容差、不替换为观察数值。

## 从当前实测状态推导

两道固定φ0=0、φ1=15。此fixture每车只有一侧实际互选边，pair_lanes=2，即n=1。令 `e=peer.x−ego.x+φ_peer−φ_ego`，明确计算

```text
u = clip(POSITION_GAIN*e + (peer.speed−ego.speed), −2,+2)
head target = ego.x + u/POSITION_GAIN
head speed = 原_request(ego,target,CRUISE)
body target/reference = 原实际front CTH，完全保留
body speed = clip(原CTH speed + SPEED_RELAXATION*u, 0,MAX_SPEED)
```

M实现按等价形式 `.3*(e+dv/.3)` 累加；测试用独立PD形式 `.3*e+dv` 从fixture的当前速度/位置推导，沿用原assertAlmostEqual精度，不复制新的观察结果。

| 当前测试（保留J2测试名） | 几何e及相对速度dv | 新断言 |
| --- | --- | --- |
| C1 head uses_fixed_phase_of_actual_a1 | e=+3.462971m，dv=−.422255m/s | u≈+.616636m/s，目标自身x+u/.3；保持无实际front、未饱和与原_request速度断言 |
| A1 head uses_fixed_phase_of_actual_c1 | e=−3.462971m，dv=+.422255m/s | u≈−.616636m/s，对称目标；保持无实际front及原_request，速度仍按实际自身状态计算 |
| B1 body keeps_front_c1_and_couples_to_actual_body_a2 | e=+.728852m，dv=−.095777m/s | u≈+.122878m/s，原真实C1 target/ref不变；原CF速度加.2u≈.024576m/s |
| A2 body keeps_front_a1_and_couples_to_actual_body_b1 | e=−.728852m，dv=+.095777m/s | u≈−.122878m/s，原真实A1 target/ref不变；原CF速度减约.024576m/s |

表中小数只解释推导，patch没有硬编码它们。四项仍读取原34.7秒实际fixture，目标/速度通过当前实测x/v和公式计算。旧P body修正±.043731m/s与PD的±.024576不同，不能简单要求M继续旧速度。

## 最小范围及历史保护

[生成器](make_M_test_migration_patch.py)先验证J2 patch SHA `13aaefe37d8fd7705da74a00499a2b40601519c7df611072fce57ac9706a4640`，从经原/内存SHA核过的五份J2文本生成M patch。AST硬断言相对J2恰是这四个原函数变化，其余四文件逐字不变，原14文件仍225项。元数据见[M_test_migration_sources.json](M_test_migration_sources.json)。

H/P三个归档比较、冻结源及loader继续原含义，不重绑到M；原安全、NOA、CTH、局部信息、横移执行、统计和恢复测试均原样。M在新实验L30合同中的两项已知政策冲突仍按[M方法](../candidates/local_phase_velocity_damping/method.md)原样留存，不因本225通过而宣称所有历史增量精确等价。

采用时应只把完整M patch用于当前原tests，不能先叠E/J2再重复应用M。尚未apply任何补丁。

## 验证证据

- 父原225+J2 patch：221通过、4失败、37子通过，四项失败报告保持。
- 生成：`20261103T062816201279Z_M-four-PD-core-migration-patch-build_b9194274`，exit0。
- 内存全14：`20261103T062835037426Z_M-core14-four-PD-migration-verified_923c8ffb`，exit0，27.734秒；**225项及37子测试全过**，五份内存文本实际加载SHA与登记相同。见[M_core14_minimal_migrated.json](M_core14_minimal_migrated.json)。
- `git apply --check`：`20261103T062835037426Z_M-test-migration-git-apply-check_38403d79`，exit0，未apply。

driver在运行前后核对M、E、生产、原14tests及保护的历史资料SHA一致。动态注入的磁盘snapshot局限仍沿[E说明](test_migration.md)，控制身份由driver记录M路径/SHA证明；本单元没有跑交通或Git提交，正式交通由父冻结源统一执行。
