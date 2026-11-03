# 后续探索与失败记录封存

本目录与正式31–35种子结果分开；不移动或改写旧归档、生产、候选。七包共21,311,606字节，单包均小于20MB。

| 包 | 原完整计划 | 定位 / 字节 |
|---|---:|---|
| `20261103_H_screen180_8.tar.gz` | 8 | H探索短批；2,155,094 |
| `20261103_J_JT_screen180_16.tar.gz` | 16 | 旧J0/JT0诊断，已知准备区单边邻接缺陷；4,205,209 |
| `20261103_J2_JT2_screen180_16.tar.gz` | 16 | 物理邻接修正版探索短批；4,203,809 |
| `20261103_E1250_screen180_2.tar.gz` | 2 | E的1250补充对照；435,268 |
| `20261103_K_screen180_8.tar.gz` | 8 | 不采用的负结果，全部保留；2,135,274 |
| `20261103_J2_long600_8_unfinalized.tar.gz` | 8 | 7例已封口＋1例未封口执行失败；7,134,102 |
| `20261103_J2fast_retry600_1.tar.gz` | 1 | 独立计算重试，不能覆盖原失败记录；1,042,850 |

共59条原计划尝试，58条有已封口证据、1条物理结果不明；不同探索版本、需求时长和重试不混成一个性能均值。
每包保留其原protocol/manifest、冻结驱动与源、完整已有evidence/小件、必要operation及包内核验依赖，逐成员SHA和原件字节比对。
每包都在临时目录用包内新Python `-I`独立核验，禁止读取原仓库；原仓库读取尝试为零。

旧J0/JT0的单边图诊断不能冒充已修复的J2/JT2：准备区接收车道使用未来lanes2时，旧界限会排除尚存在的终止lane2实车。
旧源与原结果不修补、不滤掉；修复关系见 `../review_J2_JT2.md` 和原方法记录。
K8作为不采用负结果保留，不因结论不利移出计划。

## J2长批的实际失败口径

核验原件后，此例**不是已记录的timeout**：

- J2 / flow2500 / seed4 / lane_drop / transform，原result仍`starting`，trips不存在。
- case记录returncode=`4294967295`；worker.log与operation记录status=`failed`、child/returncode=`3221225477`。
- 耗时350.531秒，设置的worker上限1200秒。不能改标为return124或物理time_limit。

新薄包装 `tools/package_failed_followup.py` 只封存该原8例批：7例正常复用seal/协议核验；失败例保全所有已有非positions/events文件及两层退出码，标记`unverified_execution_failure`、`physical_completion=undetermined`、`eligible=false`。
不伪造trips、旅行时间、完成数或安全统计，也不由未封口状态推断不能排空。
原worker operation为 `results/operations/20261103T045328528400Z_staggered-case-febc0e8ee5_9f6c50b6`。

两个partial positions/events共23,878,232字节只保存全文件SHA、字节和本地路径索引；**原件仍留原位置，没有解析、重组或删除**。
`RAW_LOCAL_RETENTION.json`记录再次逐文件核对仍存在且SHA/字节不变。云端包不能重建或解释这些partial raw。
J2fast retry是另一个完整原计划，不能把其成功当作原J2长批已8/8完成。

新分类合同先失败再修复，现工具27 tests通过。
失败批原件/归档字节与包内离线核验operation：`20261103T060859337050Z_followup-J2-long8-unfinalized_2fd30898`，退出0。
本地partial raw复查operation：`20261103T061100590238Z_followup-local-raw-retention_ef10937c`，退出0。

## 证据范围

正常sealed证据保留原JSON/六源、全0/1、越线和区域账本；这些字段不能代表完整全时空轨迹或完整交错几何。
原完整positions/events仅hash索引，hash在原件缺席时不能证明全部选字段来源，也不能重新检查所有碰撞/换道走廊。
所有SHA及正式包名单见`PUBLIC_MANIFEST.json`；本目录不包含正式validation31_J2fast80或仍在试的新方法数据。
