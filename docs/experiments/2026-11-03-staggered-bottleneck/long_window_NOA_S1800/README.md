# 延长窗口：复用封存账本

区域积分窗口[100,1800)；1000m首次越线沿原定义含两端。区域仍800≤x<1000、三道长度0.6车道公里，低速v<5m/s。TT/系统时间/燃油/分段时间/旗标沿用原全需求或全轨迹值，仅region和越线流量延长。缺样/不完整不补值；全部计划样本均列出，种子等权，target−NOA。

| 方法/流量 | eligible seeds | 系统时间NOA/候选(s) | 全窗区均速NOA/候选(m/s) | 全窗低速车辆秒NOA/候选 | 全窗越线流量NOA/候选(veh/h) |
|---|---:|---|---|---|---|
| S/2250.0 | 2 | 60.55226/48.39229 | 12.31890/22.13107 | 24124.95000/3813.05000 | 6549.88235/6672.70588 |
| S/2500.0 | 2 | 139.23420/115.22707 | 7.81536/8.01869 | 49868.50000/49610.15000 | 6760.58824/6908.82353 |

执行状态逐例保留case_analysis_status、原native status与worker operation路径。worker墙钟timeout/124与仿真max_time结束分开，native残留starting不表示仍在运行，也不推断物理已完成或算法未排空；未封存者不产生窗口指标。

全部案例、逐种子配对、均值与逐文件来源hash见同目录CSV/ledger_index.json/summary.json。原[100,600)数值另存original_100_600_metrics并逐项重建核对，不覆盖原工具或封包。

## 独立核验后的实际结论

本批为锁定S与NoA的同输入长时需求诊断，2250/2500每道流量、seed41/42、1800秒需求、max_time3000、原1200米道路；八例均安全排空、封存并完整覆盖时间窗，4对均可比。规则SHA为`8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，NoA为`65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`。这些41/42长批是候选对比后的延时诊断，与正式新种子61–65、600秒需求的结果分开报告，不包装成额外独立holdout。

| 每道流量 | 系统时间改善 | 入场等待NoA/S(s) | 燃油S−NoA(g/km) | 区域密度NoA/S(veh/km/lane) |
|---:|---:|---:|---:|---:|
| 2250 | 20.0818% | 0.2311/0.2358 | +2.9946 | 53.2033/28.0323 |
| 2500 | 17.2423% | 29.5571/14.7391 | +2.3692 | 80.3764/80.1203 |

2250档区均速与低速车辆秒改善明显；2500档依然强拥堵，速度仅从7.8154升至8.0187m/s、低速仅从49868.5降至49610.15车辆秒。系统收益同时包含入场等待减少，不能称为2500拥堵已消失，也不能由时间收益声称节油。种子数每档仅2，均值等权，不把全需求的TT/等待/燃油误称为1700秒窗口统计。

[独立积分/越线与原始帧审核](independent_audit/verification.json)不导入原评价器，对全部8例全region ledger逐区间按[100,1800)独立积分，对原bracket逐条线性复算首次越线，结果与报告一致；每例100/600/1000/1799.9秒实际positions共32帧的n、低速n与速度和也完全一致。[独立数值](independent_audit/independent_integrals.csv)、[逐帧证据](independent_audit/raw_spotchecks.csv)与[固定seed42时空图](../final_figures/long1800_2250_seed42_speed_raster.png)可交叉复核。操作`20261103T082147698234Z_long1800-NOA-S-independent-ledger-raw_cebd3ea5`通过。

## 审查包与精确raw处理

- [NoA四例完整封存证据](evidence_profiles/NoA_four_cases_evidence.tar.gz)：11,654,665字节，SHA`877c3be2be615e0545989c056d882bbe3540078303b07a3ce6ae0309f9e3bcad`。
- [S四例完整封存证据](evidence_profiles/S_four_cases_evidence.tar.gz)：12,513,619字节，SHA`2ffdefbb9b923575791f54a3f57bd185ab0091458ad1a0a583b8bbca5f376e1e`。

两包各114个member，均逐文件hash验证，含原compact（完整JSON/冻结六源/全部0或1帧）、完整region/gate/vehicle ledger、冻结runtime、原网络/执行上下文、指标和核验源码；包内MEMBER_MANIFEST列完整对应关系。[archive_verification](evidence_profiles/archive_verification.json)是包级SHA。完整positions/events只索引，未伪称已在包内：选中的2250seed42两源positions.gz本身66.1/56.5MB，完整raw继续留本地，由[raw索引](evidence_profiles/raw_index_before_pruning.json)给出绝对路径/字节/SHA。

父明确授权并通知技术步骤后，8例原件验证与两包逐member验证均通过，才调用既有`seal_case.prune_raw`：只对两个指定新批的六个非选中成功case删12个positions/events文件，释放574,580,621字节；选中两例raw仍在。删除前解析绝对路径、batch ownership marker和每个原始文件SHA，未递归删除。[最终清单](evidence_profiles/pruning_verification.json)保留逐例结果；旧L失败与全部其他批raw未动。操作`20261103T082445987127Z_long1800-NOA-S-reviewed-archive-exact-prune_6d56de71`通过。封包内README是归档时版本；所有数值CSV保持原SHA不变，以上为归档完成后的透明补记。
