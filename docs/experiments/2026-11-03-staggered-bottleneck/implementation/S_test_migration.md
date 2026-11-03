# S核心：两项真实CF冲突的最小迁移

固定S源 `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`。用原14文件及既有J2 patch审计为223通过/2失败/37子通过；两项都在head_group_rules的真实body状态，旧断言仍要求相位叠加，实际front target/ref已经通过。原报告[S_core14_J2_patch.json](S_core14_J2_patch.json)保持。

新[S_test_migration.patch](S_test_migration.patch)包含完整J2 patch，相对J2只改B1/A2这两个函数。每项仍从同一原实测fixture计算几何e、原phase_speed与真实front CTH请求CF，先明确断言

```text
phase_speed * (CF - ego.speed) < 0
```

再要求S的速度hex精确等于CF；不是把观察值换成新常数，也没有把所有body相位都删除。

- B1的P误差约+.728852m、phase速度约+.218656，而CF28.476133低于ego28.539033，正相位与CF减速冲突，故返回CF。
- A2的P误差约−.728852m、phase速度约−.218656，而CF28.483996高于ego28.443256，负相位与CF加速冲突，故返回CF。

表中小数只解释原fixture，patch未硬编码这些结果。真实front/ref及原CTH目标断言保持；heads原J2相位断言不变。独立[S七项合同](../tests/test_cth_priority_phase.py)还要求同方向、CF0和head完全保留L，防止用“全部关相位”通过本迁移。

[生成器](make_S_test_migration_patch.py)核固定J2 patch SHA，并硬断言相对J2只这两个function AST变化、其余四内存文件逐字不变。五份元数据见[S_test_migration_sources.json](S_test_migration_sources.json)。历史H/P冻结比较、原tests/源码/旧patch均保持。

## 运行证据

- 原审查：`20261103T072435358594Z_S-core14-existing-J2-migration_aefa8faa`，exit1，223/2/37，30.735秒。
- 生成：`20261103T072737477900Z_S-two-CTH-conflict-core-migration-build_dc45e10b`，exit0。
- 内存全14：`20261103T072902415483Z_S-core14-two-CTH-conflict-migration-verified_f4af69bf`，exit0，23.281秒，**225项/37子测试通过**；五份实际内存文本SHA与登记一致。见[S_core14_minimal_migrated.json](S_core14_minimal_migrated.json)。
- `git apply --check`：`20261103T072902447108Z_S-test-migration-git-apply-check_917bbe98`，exit0，未apply。

本完整patch用于当前原tests，不先叠E/J2。driver保护的原tests、S/E/生产及历史归档前后SHA相同；动态注入snapshot局限沿[E说明](test_migration.md)。本单元没有跑交通、改生产或Git，父统一实际几何/交通确认。
