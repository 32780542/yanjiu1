# V1短筛：无稳定系统时间改善

12个预定case全部安全排空，原件/冻结源/协议/ledger验核12/12通过；6个V-transform减S-transform同输入配对有效。规则与输入见[固定协议](protocol.md)，V1源锁定SHA `517d169ff012950e288c20a9fca9225db20bae6ffcc1a6f3aca43c05c8790c7d`。不是V减NOA。

| 每道流量 | S系统时间(s) | V系统时间(s) | V−S(s) | 系统改善(%) | 更快种子 | 燃油差(g/km) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | 42.188010 | 42.157157 | -0.030853 | 0.073133 | 2/2 | +0.512627 |
| 1750 | 42.686132 | 42.746904 | +0.060772 | -0.142369 | 0/2 | +0.165863 |
| 2000 | 43.240020 | 43.206467 | -0.033553 | 0.077598 | 1/2 | +1.138990 |

表为73/74种子等权均值，改善为负差值除以参考均值。1750两种子均变慢，三流量燃油均增加；不据短筛微小差值宣称提效。逐种子全部指标见[正确六对](analysis/paired_V_minus_S.csv)，原完整输出见[paired.csv](analysis/paired.csv)和[summary.json](analysis/summary.json)。`flow_means_V_minus_S.json/csv`仅从原工具有效六对按本协议做种子等权汇总。

180秒需求不覆盖原[100,600)完整窗口，因此原formal区域指标空值照留，不能冒称容量或完整窗口均速。机制分析另在[诊断](../diagnosis/V1screen12_summary_v1)固定[30,180)共同需求期核对region_steps，不改原评价器。几何及制动负结果按原诊断保留。

完整紧凑证据[evidence_complete12.tar.gz](evidence_complete12.tar.gz)，2,961,276字节，SHA256 `752886dc747c5e11102288c51fb681fc524c129fad7a4c9f8b273ab462713cf7`。原package_stage隔离离线核验12例/12协议/250成员通过，不读原仓库、不运行SUMO，并逐字对照原件。它附带的默认TM参考配对不用于本批比较；本批有效比较必须使用原summarize的`--reference S`，再取`V-minus-S_transform`六对。封包包含原JSON/源、0/1和交通ledger；全positions/events只索引，不包含在紧凑包中。

所有73种子三流量S/V共6例完整positions/events原位保留且重查SHA。机制agent完成全部12例提取后，已在原件SHA、离线封包核验及旧prune_raw路径门禁下，仅清理seed74六个成功case的12个轨迹文件，释放23,437,356字节。见[清理核验](raw_pruning/pruning_verification.json)与[完整raw索引](raw_pruning/raw_index_before_pruning.json)；失败0例，不改原manifest/seal，不碰旧批，无递归删除。清理命令和run_logged结果保存在raw_pruning/operation_*。

可从包内README给出的原工具重新隔离验包；本批正确分析入口在固定协议中。外层运行718.218秒，执行返回0；墙钟仅作计算记录，不用于驾驶排名。
