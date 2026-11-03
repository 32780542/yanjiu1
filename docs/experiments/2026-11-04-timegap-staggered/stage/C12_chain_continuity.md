# C12/P12：已建立纵向链允许真实前驱替换

这是独立短筛候选，不覆盖已冻结fallback final或生产。C12/P12各含200/300 m版本，四份各316行；沿用final的同一可读性清理。

相对清理后的C11/P11，仅把普通远孔条件中的`physical[2] == memory.front`改为`memory.front is not None`。仍要求50 m内没有普通前车、200 m内存在当前最近真实前车。

本车已建立纵向链时，插入或离开引起前驱身份变化，继续跟当前真实前车，不追旧ID。普通分支当前没有真实前车时释放关联；下一次fresh80 m仍不自动建链。保持C11的anchor优先、否则保存本帧reference，真实接入/虚拟CTH、严格前向引用及其他规则不变。

`stage/test_C12_chain_continuity.py`先在C11复现三个前驱替换失败子例；新四源各5组通过，包括替换保持、失见释放及下一次fresh不入队、原50 m建立、slot/pending和80 m虚拟接入。

| 候选目录（位于tmp/staggered_bottleneck/candidates，文件native_rules.py） | SHA256 |
|---|---|
| 20261104_C12_200 | d24524bb74aa3ac1e1e45afbf4fc577de56bfce440153d237357f7f988ac487b |
| 20261104_C12_300 | e9dda2f6d0ae8b77b56908019a6dd9f3c3c8ef218175f003a6dcade0a9191e1c |
| 20261104_P12_200 | 3f0c0e88642c9528c3b0cb23b34c4417f3aa326e918d9d42ccfb2c13051fc11c |
| 20261104_P12_300 | afff29c1db94a7116997deeea0122be5289381fc628a16f753e220ea204570e6 |

04:27冻结后不再修改；控制单元未跑仿真，由root与runner短筛后决定，正式采用前不把它写入生产规则说明。
