# D1持续1800秒：六种子均比S更快且省油

D1六例与S/NOA参考共18case全部安全排空，原件/需求/参数/非规则源/协议及完整[100,1800)18/18验证；主D1减S同mode六对有效。源2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a不变。完整命令与原窗口保留原则见[固定协议](protocol.md)。

| 每道流量 | D1−S系统(s) | 增量改善(%) | 更快种子 | 燃油差(g/km) | 瓶颈段差(s) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | -0.199230 | 0.473347 | 2/2 | -0.588304 | -0.161779 |
| 1750 | -0.302476 | 0.712100 | 2/2 | -0.912109 | -0.243148 |
| 2000 | -0.638604 | 1.460871 | 2/2 | -2.540575 | -0.482011 |

81/82种子等权，六种子系统与燃油均同向改善。保留1750低速车辆秒+4.9的反向指标。2000区均速+0.350863m/s、低速-275.1车辆秒，但只跑缩道，不报告未测1800秒直路DID。相对NOA整体系统改善1.091054/2.047163/4.365248%，仍有燃油+7.555857/+7.543082/+5.843891g/km代价，不把S基础贡献全归为D1增量。

主六对与均值见[paired_D1_minus_S.csv](window_100_1800/paired_D1_minus_S.csv)、[flow_means_D1_minus_S.json](window_100_1800/flow_means_D1_minus_S.json)。由相同NOA参考的S/D1正式target值直接相减，核共同参考一致及原同mode资格，来源SHA/代数核验在[incremental_derivation.json](window_100_1800/incremental_derivation.json)，没有改原评价器。原[100,600)另留不覆盖；完整需求系统/燃油与窗口区域/越线明确区分，越线不称容量。严格两种子allLC/post5与真实局部几何见[long1800_D1_mechanism_v1](../diagnosis/long1800_D1_mechanism_v1/README.md)，不以局部接收后车正亏损替代完整请求时间。

完整包[evidence_complete6.tar.gz](evidence_complete6.tar.gz)，11,289,277字节，SHA256 `7d0f159ca4ead665deba5f59122e4aa0836a5f03c07732b8bb2201b2895ac4e7`，逐字原件及隔离离线6case/6协议/137成员验核通过。比较还须保留[S长六例包](../long1800_S81_6/evidence_complete6.tar.gz)及[NOA长六例包](../long1800_NOA81_6/evidence_complete6.tar.gz)。包内默认TM配对不用于本批评价；全positions/events仅索引，不在紧凑包中，不能恢复全部原轨迹。

当前本批raw全部原位保留待机制审计/本轮收口，至少81三流量三例长期全raw保留，失败不删。原manifest/seal/旧工具不改；这是预先登记的development、机制消融或另行持续需求确认，不是91–95最终批。主D1源保持相同字节，最终结果不回调源。Git仅root执行。
