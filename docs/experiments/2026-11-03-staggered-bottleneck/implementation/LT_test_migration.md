# LT核心：四个固定15m期望改为对称半时距

固定LT SHA `8a773793ccba5eb5e0ecae7f1b02083a8571d7e77f5a1f5f5f78b13eb6596593`。父原225+J2 patch为221项及37子通过、四个head_group_rules固定相位公式失败，原[LT_core14_J2_migration.json](LT_core14_J2_migration.json)保持。

[LT_test_migration.patch](LT_test_migration.patch)合并原J2文本，相对它**只改四个原head/body函数**：从fixture当前ego/peer速度计算

```text
half_headway = (5.5 + HEADWAY*(ego.speed+peer.speed)/2)/2
error = peer.x-ego.x ± half_headway
```

C1/B1为正、A1/A2为负，仍按原P相位限幅/响应；head target=ego.x+error，body保留实际front target/reference及原CF速度，只叠新几何误差。本补丁不加入M的相对速度项，不改fill/witness或任何安全/NoA测试，也不替换成当前观察数字。

[生成器](make_LT_test_migration_patch.py)硬断言相对J2仅这四function AST变化，其余四份内存文件逐字保持。完整patch SHA `9251ed43197480774aab90a36c39343efaca5f0e60d1687f2ff2eefebb1ba22c`，元数据见[LT_test_migration_sources.json](LT_test_migration_sources.json)。历史H/P归档比较及源hash不动。

- 构建：`20261103T072445605366Z_LT-four-headway-core-migration-patch-build_d006fc31`，exit0。
- 内存全225：`20261103T072530355064Z_LT-core14-symmetric-headway-migration-verified_705fada8`，exit0，26.047秒，**225项/37子测试通过**；五份内存文本实际SHA与登记一致，原源码/tests/保护归档前后不变。见[LT_core14_minimal_migrated.json](LT_core14_minimal_migrated.json)。
- `git apply --check`：`20261103T072530327247Z_LT-test-migration-git-apply-check_db377e28`，exit0，未apply。

该完整patch针对当前原tests，不先叠E/J2。动态注入source_snapshot局限沿原[E说明](test_migration.md)，不作为正式交通source身份。没有生产修改、Git或新增交通仿真。
