# F2短筛：系统时间表现混合

F2六例全部安全排空，与原冻结S73/74六例跨批原件/需求/参数/非规则源核对通过，正式`F-minus-S_transform`六对全部有效。候选是从S独立修改的未来资源指导选道，不是指定未来slot跟踪，不叠V/W；源与完整命令见[固定协议](protocol.md)。

| 每道流量 | S系统时间(s) | F系统时间(s) | F−S(s) | 系统改善(%) | 更快种子 | 燃油差(g/km) | 变道完成数差 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | 42.188010 | 42.163424 | -0.024587 | 0.058279 | 1/2 | -0.313183 | -6.0 |
| 1750 | 42.686132 | 42.735054 | +0.048922 | -0.114609 | 1/2 | +0.397497 | +10.0 |
| 2000 | 43.240020 | 43.083448 | -0.156573 | 0.362101 | 2/2 | +0.451402 | -2.0 |

表为73/74种子等权，改善为负差值除以参考均值。2000档73仅快0.002034秒，74快0.311111秒；1750档73快0.152713秒、74慢0.250558秒。保留异质结果，不只报告均值。逐种子全部指标见[paired_F_minus_S.csv](analysis/paired_F_minus_S.csv)，均值见[flow_means_F_minus_S.json](analysis/flow_means_F_minus_S.json)。180秒原formal [100,600)窗不足保持空值；不补值、不宣称容量。

F六例完整紧凑证据[evidence_complete6.tar.gz](evidence_complete6.tar.gz)，1,508,855字节，SHA256 `10c2084f7503d3665346dc4bcf441ab72c740311e80e19717acf78ef62fafe19`。原package_stage逐字原件及隔离离线6case/6协议/137成员验核通过。完整F-S比较仍须同时保留[V1完整包](../projected_predecessor_v1_screen73_12/evidence_complete12.tar.gz)中的共同S六例。包内默认TM配对不用于评价，正确六对使用固定协议的原summarize `--reference S`。

新增变道完成后2秒/5秒、回CTH制动和∫a²已对F全六例提取，见[raw_F2screen6_post5_v1](../diagnosis/raw_F2screen6_post5_v1)。共同S新增post5参考目前仅有原raw仍在的seed73三例；原S74已按当时固定政策清理，不能声称它也有新增post5六对证据。原交通六对评价不受影响。

机制全六提取并明确放行、原件SHA再核、完整包离线复核后，仅旧prune_raw清理seed74三个成功case的六轨迹，释放11,705,134字节；seed73三例全positions/events原位长期保留且重查SHA。见[清理核验](raw_pruning/pruning_verification.json)及[raw索引](raw_pruning/raw_index_before_pruning.json)。新增post5逐例来源/源代码与命令也保存在raw_pruning。没有改原manifest/seal、旧批或生产，无递归删除。机制分析与原交通评价分开，较小加速度不直接等于交通改善。

外层332.516秒、执行返回0；墙钟不用于驾驶排名。生产与旧工具未改，Git由root统一处理。
