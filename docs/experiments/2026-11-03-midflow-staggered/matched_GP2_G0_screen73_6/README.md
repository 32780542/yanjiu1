# G0匹配控制：1750档支持GP2更快，其他档种子混合

G0六例全部安全排空，主分析原件/需求/参数/非规则源核对通过，G0减GP2同mode六对有效；六例实测flag peak、参与率及均参与人数全0。运行mode为transform，是匹配非编队控制，**不是原纯NOA**。关闭phase与freefill两项，不能解释为仅关闭单一phase。完整定义与命令见[固定协议](protocol.md)。

| 每道流量 | 参考系统(s) | 控制系统(s) | 控制−参考(s) | 控制更快种子 | 燃油差(g/km) | 变道数差 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | 42.269612 | 42.281735 | +0.012123 | 1/2 | -8.812433 | -116 |
| 1750 | 42.654042 | 43.036052 | +0.382010 | 0/2 | -7.427606 | -100.5 |
| 2000 | 43.105513 | 43.190800 | +0.085287 | 1/2 | -9.330468 | -83.5 |

种子等权，主差值G0减GP2。逐种子全部主指标见[六对](analysis_primary/paired_G0_minus_GP2.csv)，另对S的次比较单列[analysis_vs_S](analysis_vs_S)。不把三档均值同号说成全部种子同向。

G0保留GP2真实gap规划、CTH兼容带、实际执行和普通慢前车超车，关闭主动phase/freefill，因而检验整个主动交错子系统相对规划控制的作用。1750两种子GP2都更快，低/高档各有反向种子，GP2燃油代价约7–9g/km。实际触发及同entrant/receiver/post5证据另审计，不能仅凭函数保留就声称触发等价。

180秒原[100,600)formal窗不足照留空值，共同[30,180)和post5机制单列，不补值、不称容量。

完整紧凑包[evidence_complete6.tar.gz](evidence_complete6.tar.gz)，1,367,532字节，SHA256 `9854157fc871a732155b8c8f32c6dcc8edbb92d819330422e8ac54f0c09ebfe0`；逐字原件及隔离离线6case/6协议/137成员验核通过。主参考为[GP2短筛六例包](../bound_real_gap_GP2_screen73_6/evidence_complete6.tar.gz)，次S参考在[V1包](../projected_predecessor_v1_screen73_12/evidence_complete12.tar.gz)。

包内默认TM配对不用于本批评价，正式比较使用固定协议的reference。包含原JSON/源码、0/1选定字段和完整交通ledger，完整positions/events仅索引，不能从紧凑包恢复全轨迹。

当前六例raw全部原位保留待审计/本轮收口，至少seed73三流量三例永久完整保留。无本批raw清理，旧manifest/seal/工具与生产未改，失败不删。控制只用本车/有限局部观测/自身记忆。最终91–95未在本批运行，墙钟不用于驾驶排名，Git由root统一处理。
