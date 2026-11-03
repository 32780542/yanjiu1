# V2短筛：1750和2000四个种子均变慢

新增W/V2六例全部安全排空，与原冻结S73/74六例同输入跨批核对有效。原summarize重验18个case（包括V1历史六例），原件/协议均通过；本批正式只引用`W-minus-S_transform`六对。源与完整命令见[固定协议](protocol.md)。

| 每道流量 | S系统时间(s) | W系统时间(s) | W−S(s) | 系统改善(%) | 更快种子 | 燃油差(g/km) | 变道完成数差 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | 42.188010 | 42.119262 | -0.068748 | 0.162957 | 2/2 | +0.332839 | -1.0 |
| 1750 | 42.686132 | 42.788761 | +0.102630 | -0.240428 | 0/2 | +0.844725 | +14.5 |
| 2000 | 43.240020 | 43.286673 | +0.046652 | -0.107891 | 0/2 | +1.731462 | +11.5 |

表为73/74种子等权，差值W减S，改善为负差值除以参考均值。1750/2000四个种子全部变慢、变道明显增加，燃油三档均增加；此短筛不支持采用V2。逐种子全部指标见[paired_W_minus_S.csv](analysis/paired_W_minus_S.csv)，均值见[flow_means_W_minus_S.json](analysis/flow_means_W_minus_S.json)。原180秒formal [100,600)区域窗不足保持空值，未补值或声称容量。

机制全六例已提取，并与S/V在共同[30,180)窗比较，见[raw_V2screen6_v1](../diagnosis/raw_V2screen6_v1)和[V1V2screen18_summary_v1](../diagnosis/V1V2screen18_summary_v1)。该诊断单列，不替换原评价。

W六例完整紧凑证据[evidence_complete6.tar.gz](evidence_complete6.tar.gz)，1,510,629字节，SHA256 `d70958a7568ca87f98b093cfa76e3889779b897d9a1a37cbccdd394c0c234448`。原package_stage逐字原件及隔离离线6case/6协议/137成员验核通过。完整W-S比较还须同时保留[V1完整包](../projected_predecessor_v1_screen73_12/evidence_complete12.tar.gz)中的共同S六例。封包默认TM配对不用于评价，正确参考由固定协议的原summarize `--reference S`指定。

seed73三例全positions/events原位保留并重查SHA。机制全六提取、明确放行、原件SHA及完整包离线复核后，只用旧prune_raw清理seed74三个成功case的六轨迹，释放11,748,747字节。见[清理核验](raw_pruning/pruning_verification.json)与[完整raw索引](raw_pruning/raw_index_before_pruning.json)。失败0例，不改原manifest/seal、旧批或生产，无递归删除。紧凑证据只保存选定字段与ledger，完整轨迹仅SHA索引，不能恢复全部原始轨迹。

外层331.484秒、执行返回0；墙钟不用于驾驶排名。
