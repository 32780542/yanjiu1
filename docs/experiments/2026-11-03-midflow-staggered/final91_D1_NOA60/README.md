# 五个新种子主确认：D1相对NOA

D1源2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a在91–95输入运行前锁定，60预定案例全部安全排空、原件/需求/物理/五个非规则源/协议60/60核验通过，30主配对全部有效。主比较D1-transform减同冻结源的原NOA模式，NOA路径与原S逐位一致；没有据最终数据调源。三流量×五种子×两道路=30共同输入组，两方法共60例。完整事前方案见[protocol.md](protocol.md)。

| 每道流量 | 道路 | NOA系统(s) | D1系统(s) | D1−NOA(s) | 逐种子百分比均值(%) | 更快种子 | 燃油差(g/km) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | lane_drop | 42.443881 | 41.930337 | -0.513544 | 1.209386 | 5/5 | +7.608524 |
| 1500 | straight3 | 41.850732 | 41.433428 | -0.417304 | 0.997078 | 5/5 | +4.222785 |
| 1750 | lane_drop | 43.252977 | 42.344911 | -0.908067 | 2.094288 | 5/5 | +7.793151 |
| 1750 | straight3 | 41.903635 | 41.399849 | -0.503787 | 1.202166 | 5/5 | +4.714468 |
| 2000 | lane_drop | 44.715362 | 43.233811 | -1.481551 | 3.304213 | 5/5 | +6.514407 |
| 2000 | straight3 | 41.959839 | 41.392937 | -0.566902 | 1.351002 | 5/5 | +5.204806 |

| 每道流量 | 绝对道路DID(s) | 额外缩道更好种子 |
| ---: | ---: | ---: |
| 1500 | -0.096240 | 4/5 |
| 1750 | -0.404280 | 4/5 |
| 2000 | -0.914650 | 5/5 |

系统时间30对全部更快，15个道路DID有2个非改善案例，未删除或换种子。燃油代价与所有反向指标保留。DID=同种子缩道绝对差值减直路绝对差值，不相减百分比。绝对均值按五种子等权；本表百分比是五个配对百分比的等权均值。原system_improvement_percent保留ratio_of_means，并另列显式ratio及mean_of_paired_percent字段，不能混称相同。

正式全部逐种子见[paired_D1_minus_NOA.csv](analysis_primary/paired_D1_minus_NOA.csv)，均值见[primary_flow_road_means.json](analysis_primary/primary_flow_road_means.json)，15个DID见[primary_DID_paired_seeds.csv](analysis_primary/primary_DID_paired_seeds.csv)，反例见[primary_nonimprovements.json](analysis_primary/primary_nonimprovements.json)，百分比口径见[percentage_aggregation.json](analysis_primary/percentage_aggregation.json)。独立原trips/raw端点与区域核对见[official_primary_concordance.json](../diagnosis/final91_independent_v1/official_primary_concordance.json)，不以局部receiver指标替代完整请求系统时间。

按预先道路完整组分两包，分组不依据结果，whole原protocol/manifest及subset视图均保存：
- [evidence_lane_drop30.tar.gz](evidence_lane_drop30.tar.gz)：19,465,309字节，SHA256 `d6526fdf4888718d7011dcf037f360b4b2d053ce85d94824f4ba2f7544cf6bd0`，30例逐字原件及隔离离线验核通过。
- [evidence_straight3_30.tar.gz](evidence_straight3_30.tar.gz)：17,018,055字节，SHA256 `1f2d54b8ee06b7595c81f2c01d3a10df6daa608e03eaa3150c00320114970134`，30例逐字原件及隔离离线验核通过。

包仅原JSON/源码、直接0/1选定字段及完整traffic ledger；全positions/events只索引，不能恢复全轨迹。所有90最终raw当前原位保留，独立allLC/post5及root清理plan审查前不删除，失败与反例不剔除。原manifest/seal/旧工具不改。窗口越线不称饱和容量，直接0/1不等于完整队形或单支编队。
