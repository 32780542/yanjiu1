# 追加完整批与 TM 未封口批封存

原 `evidence/` 七包和原 `tools/package_stage.py` 均未改写；旧工具 SHA256 仍为
`3b202af61ed2a8aab66415dce4afad4204d5077e500f16b6b7684bfde50d11e7`。
本目录不包含仍在运行的 E40、ENF/ENP10，也不提供替代主汇总的新性能均值。

## 正式包

所有包小于 20,000,000 字节，共 54,510,717 字节。

| 包 | 完整计划 / 封存范围 | 字节 |
|---|---|---:|
| `20261103_E_long600_8.tar.gz` | 完整8例，已封口证据 | 6,098,193 |
| `20261103_E_formation_ablation180_18.tar.gz` | 完整18例，已封口证据 | 5,074,875 |
| `20261103_F_factorial180_12.tar.gz` | 完整12例，已封口证据 | 3,612,096 |
| `20261103_ED_screen180_8.tar.gz` | 完整8例，已封口证据 | 2,148,771 |
| `20261103_heldout_NOA40_straight3_20.tar.gz` | 预定直路全部20例 | 11,334,401 |
| `20261103_heldout_NOA40_lane_drop_20.tar.gz` | 预定3→2全部20例 | 13,929,146 |
| `20261103_TM_long600_16_unfinished.tar.gz` | 原完整16计划，13例完整证据及3例未封口原件 | 12,313,235 |

前六包覆盖五个完整批的 86 次案例尝试；末包是另一个16计划，不能把其中3例未封口计算失败算作已完成物理实验。
不同需求时长/批次不在这里混成同一有效性能组。

## NOA40 的预定道路分区

NOA40 首次整批为25,153,798字节，触发旧工具20MB上限。
该第一次 attempt 只保留在本地 `tmp/staggered_bottleneck/publication_attempts/NOA40_oversize/`，不纳入正式索引和Git证据。

新 `tools/package_partition.py` 薄封装原冻结工具，按原任务的 scenario 完整分成两种道路各20，完全不读取表现来选择成员。
每个分包同时保存：

- `stage/full_protocol.json` / `full_manifest.json`：整个40计划的原字节。
- `stage/protocol.json` / `manifest.json`：明确生成的20例分区视图，不冒充原整批字节。
- `partition.json`：原全批 hash、预定道路及40/20对应关系。
- 所有选中案例的原 evidence、小日志、冻结源与必要 operation；原整批外层 operation 也保留。

独立临时目录中的包内 verifier 同时复核全计划成员映射和原字段。
`verification_NOA40_partition_union.json` 重新验证两个分包的40例与原协议，原仓库读取尝试为零；
两个完整道路分区的并集覆盖原40，不筛选结果。此规则也可用于后续完整 E40 的道路分包。

## TM16 的未封口计算超时

新 `tools/package_unfinished.py` 仅用于原 `20261103_TM_long600_16`，保留整个16例 protocol/manifest 原字节，不从矩阵删掉失败案例。
13例已封口案例保留全部 evidence 并复用现有 seal/protocol 核验。
3例保留所有原来存在的非 positions/events 文件，包括 input/result/source、已有小日志及 operation；不存在的 trips 仍不存在，没有补造。

| 未封口案例 | 记录 |
|---|---|
| TM / 2250 / seed4 / lane_drop / transform | returncode124，原result=starting |
| TM / 2500 / seed1 / lane_drop / transform | returncode124，原result=starting |
| TM / 2500 / seed4 / lane_drop / transform | returncode124，原result=starting |

三例均明确标记 `unverified_compute_timeout`、`eligible=false`、`physical_completion=undetermined`。
这是实际计算的 wall-clock 超时，不是物理 `time_limit`，也不能用来证明车辆不能排空。
包只证明所保存文件的原字节及计算超时记录，不能给三例补出旅行时间、完成数、安全或轨迹结论。

六个现存 partial positions/events 原文件共 **110,542,673字节**，仅保存原全文件 SHA、字节数和本地路径索引，**原文件继续留在本地，没有删除**。
没有分卷、重组、解压或解析这些可能未封口的 gzip，也不把它们加入 Git。
`RAW_LOCAL_RETENTION.json` 保存再次核对仍存在且原 SHA/字节不变的记录。
`verification_TM16_offline.json` 在禁止读取原仓库的临时目录中验证13个 sealed case 与3个未封口元数据状态；
它明确声明 `raw_contents_verified=false`，不声称可从云端包重建 partial raw。

## 复核与范围

各包 `.tar.manifest.json`、`.tar.verification.json` 以及 `PUBLIC_MANIFEST.json` 保存 SHA/字节与核验结果。
正常包、道路分包及未封口包都可从包内目录启动原 `package_stage.py verify`；索引会选择包内对应 verifier。
这不需要原 tmp case 或 SUMO。新增道路/未封口合同先失败再通过，当前工具24 tests通过。

- NOA40 联合纯离线复核：`results/operations/20261103T042934537750Z_additional-NOA40-union-offline_aeab1f7b`，退出0。
- TM16 纯离线复核：`results/operations/20261103T042934527083Z_additional-TM16-unfinished-offline_b592600e`，退出0。
- 本地 raw 保留复查：`results/operations/20261103T043051364307Z_unfinished-raw-local-retention-check_8f906add`，退出0。

正常 sealed evidence 的全 flags、越线括号及区域账本只能重算所选字段，不能代表完整全时空轨迹。
原完整 positions/events 不在云端；hash 在原文件缺席时不能证明选出字段来源，也不能重新做全时空碰撞/换道走廊或任意新轨迹指标审计。
