# E heldout追加封存

本目录只封存原已完成 E40 与 ENF/ENP10，共50次案例尝试，不修改旧114及additional包或冻结工具。
三个包总计39,253,073字节，单包均小于20,000,000字节。

| 包 | 计划 | 字节 |
|---|---:|---:|
| `20261103_heldout_E40_straight3_20.tar.gz` | 原E40直路全部20 | 14,501,905 |
| `20261103_heldout_E40_lane_drop_20.tar.gz` | 原E40的3→2全部20 | 15,375,436 |
| `20261103_heldout_formation_ablation10.tar.gz` | 原ENF/ENP全部10 | 9,375,732 |

E40按原预定道路完整分区，没有按表现选择；两个包均保留整个40计划的原protocol/manifest字节、分区视图和映射。
因此无须再按flow细分。三包都完成原件逐字节比对，并在临时目录新Python进程中用包内工具重新核验全部病例、协议、源/请求hash。
各包 `.tar.manifest.json`、`.tar.verification.json` 保存完整结果；没有重新仿真。

同协议NOA40已在 `../evidence_additional/` 的两种道路各20包中保存，不重复复制。
E_heldout90的90例、50个配对和五种子等权均值由 `../review_E_heldout.md`、`../review_E_heldout.json` 独立核验。
父表 `../E_heldout90/` 保持原字节，本目录不重写其统计口径或输出。

包内核验入口和选择字段范围沿用旧 `package_stage.py` / `package_partition.py`。
完整positions/events不在云端；hash不能还原完整轨迹或在原件缺席时证明所有选出字段来源。
交通指标通过不等于24辆、45辆demo已在200 m下游共同恢复完整30/15 m交错；几何边界见独立审查及原demo报告。

封存 operations：

- E直路：`20261103T044112988655Z_heldout-E40-straight3-publication_264f80cf`，退出0。
- E的3→2：`20261103T044112986459Z_heldout-E40-lane-drop-publication_a5f4f10a`，退出0。
- ENF/ENP：`20261103T044113002858Z_heldout-ENF-ENP10-publication_17c16787`，退出0。
