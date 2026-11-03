# 三档1800秒公共NOA参考：六例全部安全排空

每道1500/1750/2000辆/h、81/82种子、3→2道路、1800秒连续需求/3000秒物理上限的六例全部安全排空，原件/冻结源/协议验核6/6通过。mode为noa，候选标签S仅固定共同规则源，不代表运行transform。完整命令与公平合同见[固定协议](protocol.md)。S长时参考另批运行，不能重复本批NOA。

原[100,600)指标原样保留；另用原report_long_window从完整封存region_steps/gate brackets重算[100,1800)，六例完整性与窗口验核全部通过，见[窗口报告](window_100_1800/README.md)、[逐例指标](window_100_1800/per_case.csv)和[来源账本](window_100_1800/ledger_index.json)。本批只有公共NOA，没有transform配对，因此pairs=0是预期状态。

| 每道流量 | 系统时间(s) | 路内行程(s) | 入口等待(s) | 燃油(g/km) | 全窗区均速(m/s) | 全窗低速车辆秒 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1500 | 42.352493 | 42.285210 | 0.067282 | 66.751072 | 28.050397 | 118.55 |
| 1750 | 43.055531 | 42.949829 | 0.105702 | 69.769676 | 26.870803 | 431.95 |
| 2000 | 45.041465 | 44.883408 | 0.158057 | 74.068193 | 23.781422 | 1682.45 |

表为81/82种子等权；系统/行程/入口/燃油是原完整需求指标，区域均速与低速车辆秒才使用[100,1800)共同需求窗，不混淆两者。完整等权表见[reference_flow_means.json](window_100_1800/reference_flow_means.json)。窗口越线流量不称道路容量。

机制全六例同窗独立提取见[raw_long1800_NOA81_6_v1](../diagnosis/raw_long1800_NOA81_6_v1)与[longNOA1800_6_summary_v1](../diagnosis/longNOA1800_6_summary_v1)。六例raw SHA与完整窗核对通过，region ledger最大差8.85e-8，64,566条事件积分守恒检查最大差1.42e-13。

完整紧凑包[evidence_complete6.tar.gz](evidence_complete6.tar.gz)，9,782,351字节，SHA256 `046f747fdceef6fa2e6401658dd83ded0ed1d6626d8413674ee4400874e2bd8e`。原package_stage已逐字原件和隔离离线重验6case/6协议/137成员通过，不读原仓库、不运行SUMO。包内默认TM配对不用于本批评价，参考-only无配对；后续S/候选另批按相同81/82完整需求配对。包保存原JSON/源码、0/1选定字段和完整交通ledger，全positions/events仅索引，不能恢复全原轨迹。

清理前固定第一种子81的三档共三例为完整raw展示范围，不据性能选删。机制全六提取并明确放行82、原件SHA再核、扩展窗口与完整包隔离离线验核后，只用旧prune_raw清理seed82三个成功case的六轨迹，释放92,299,805字节；seed81三例全raw原位长期保留并重查SHA。见[清理核验](raw_pruning/pruning_verification.json)、[完整raw索引](raw_pruning/raw_index_before_pruning.json)与完整run_logged命令/结果。失败0例，不改原manifest/seal、旧批或生产，无递归删除。

外层953.594秒、执行返回0，墙钟不用于驾驶排名。Git由root统一处理。
