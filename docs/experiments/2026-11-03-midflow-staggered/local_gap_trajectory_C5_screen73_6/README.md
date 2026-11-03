# C5短筛：省油，但2000档两种子都变慢

独立局部gap轨迹C5六例全部安全排空，与冻结S73/74六例的原件/需求/参数/非规则源核对通过，`C5-minus-S_transform`六对全部有效。方法只在organized gap接近使用T=5秒控制，不叠V/W/F，基础CTH与安全/变道门禁仍沿S；源及完整命令见[固定协议](protocol.md)。

| 每道流量 | S系统时间(s) | C5系统时间(s) | C5−S(s) | 系统改善(%) | 更快种子 | 燃油差(g/km) | 变道完成数差 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | 42.188010 | 42.161726 | -0.026284 | 0.062303 | 1/2 | -2.015406 | -14.5 |
| 1750 | 42.686132 | 42.590216 | -0.095915 | 0.224699 | 2/2 | -1.246660 | +10.0 |
| 2000 | 43.240020 | 43.646880 | +0.406859 | -0.940933 | 0/2 | -1.655812 | -15.0 |

表为73/74种子等权，改善为负差值除以参考均值。2000两种子分别慢0.572542/0.241176秒；三档均省油不能替代交通成功判断，也不能以较小a或∫a²宣称提效。逐种子全部指标见[paired_C5_minus_S.csv](analysis/paired_C5_minus_S.csv)，均值见[flow_means_C5_minus_S.json](analysis/flow_means_C5_minus_S.json)。180秒原formal [100,600)区域窗不足保持空值，未补值或称容量。

全六例新增post2/post5、∫a²与分区制动提取见[raw_C5screen6_post5_v1](../diagnosis/raw_C5screen6_post5_v1)。严格新增共同S参考仅seed73三例，见[C5_post5_seed73_summary_v1](../diagnosis/C5_post5_seed73_summary_v1)及[同entrant/同接收后车匹配](../diagnosis/C5_post5_matched73_v1)。S74原raw此前按当时固定政策清理，没有新增post5严格参考，不能把三对诊断称六对；原交通六对仍完整有效。回CTH后制动与退出截断保留，事件暴露不能简单求和冒充网络总量。

C5六例紧凑证据[evidence_complete6.tar.gz](evidence_complete6.tar.gz)，1,508,814字节，SHA256 `7a69b5409f525ea362cd10d9df05ef84793dfd1a8d3025f7ad94110147faabda`。原package_stage逐字原件及隔离离线6case/6协议/137成员验核通过。完整C5-S比较还须同时保留[V1包](../projected_predecessor_v1_screen73_12/evidence_complete12.tar.gz)中的共同S六例。包内默认TM配对不用于评价；正式六对用固定协议的原summarize `--reference S`。完整positions/events不在紧凑包中，不能从选定字段恢复全轨迹。

机制全六提取并明确放行、原件SHA再核与完整包离线验核后，仅旧prune_raw清理seed74三成功case的六轨迹，释放11,728,299字节；seed73三例全raw原位长期保留并重查SHA。见[清理核验](raw_pruning/pruning_verification.json)及[raw索引](raw_pruning/raw_index_before_pruning.json)，逐例post5来源和分析源代码、完整run_logged命令/结果也保留。不改原manifest/seal、旧批或生产，无递归删除。失败0例。

外层305.36秒，执行返回0；墙钟不用于驾驶排名，Git由root统一处理。
