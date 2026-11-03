# L核心迁移：直接复用J2补丁

2026-11-03。固定L源 `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`，用原14文件、仅内存应用既有[J2_test_migration.patch](J2_test_migration.patch)。**225项、37子测试全部通过，无新增旧断言冲突，不需要L专用迁移补丁。**

operation `20261103T060346605028Z_L-core14-existing-J2-migration_00c09975`，exit0，17.031秒。逐项结果、实际加载的五份内存测试文本SHA与保护文件SHA见[L_core14_J2_patch.json](L_core14_J2_patch.json)。patch SHA仍 `13aaefe37d8fd7705da74a00499a2b40601519c7df611072fce57ac9706a4640`，未覆盖J2/E/H旧报告。

L保留默认50m的NOA/CF，只为有相邻实车证明的单格空位在形成分支选真实60m前车。旧225项中的队首/两道相位政策迁移已经由J2补丁处理，L没有进一步修改它们。新的缺格行为必须继续运行[独立L十四合同](../tests/test_local_vacancy_bridge.py)，其先红后绿及原相位合同联合30项/106子测试的记录见[L方法](../candidates/local_vacancy_bridge/method.md)，不能用225项通过代替此新行为覆盖。

若最终采用L，最小迁移方案就是针对当前原tests应用已有J2完整补丁，额外保留L十四行为合同；不要先应用E再叠加J2，也不要为L另改数值或删除旧安全测试。历史H/P三个归档比较函数、原hash源及loader仍冻结，不重绑为L。

本次driver运行前后原14tests、E、生产、L、归档资料SHA完全相同。未apply任何补丁，未改生产或Git。临时source_snapshot仍有原[动态注入局限](test_migration.md)：实际控制身份由driver所记L路径/SHA证明，不能把单元运行复制的磁盘TM snapshot当正式L交通来源。
