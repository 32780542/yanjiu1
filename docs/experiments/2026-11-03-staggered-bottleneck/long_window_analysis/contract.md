# 延长窗口的复用合同

新工具`../tools/report_long_window.py`只读取已封存case的完整region_steps、gate_brackets和vehicles等既有证据，不调用SUMO、不调用evaluate_case、不重新从positions计算全程指标、不修改原report_paired/seal工具或旧封包。

区域仍为800≤x<1000，三道总0.6车道公里；低速仍v<5m/s。调用原`existing._region(steps,100,1800,complete)`，按每个实际[time_s,end_s)与[100,1800)交集积分；车辆秒、车辆速度积分、低速车辆秒和密度原公式不变。只有完整连续记录覆盖窗口才给出可用区域指标，不能把提前结束后的时间补成空路、填0或延长末帧。缺失、不安全、未排空与不满足归因条件的样本如实保留，配对不可用。

1000m首越线只从原observed gate brackets线性插值重建；不补censored越线，重复同车同gate拒绝。原工具约定start≤t≤end，故越线统计沿用闭端点[100,1800]，与区域积分右开端点不同。完整窗口越线率=次数×3600/1700。原[100,600)区域与[100,600]越线数逐项复算核对，原值另存，不覆盖旧数据。

TT/系统时间/入场等待/燃油/各空间分段时间/原0或1关系旗标/横移次数仍保留原全需求或全轨迹指标，只扩展region与越线时间窗口。种子等权，delta=候选−NOA；没有缺值填补。

手算合同`../tools/test_report_long_window.py`初版通过6项；增加worker状态分类后，在run_logged operation `20261103T072714254260Z_long-window-hand-contract-v2_7be2c6cf`通过7项：

- 窗口[100,100.5)，原区间[99.9,100.1)有n2/低速1/速度和6，[100.1,100.4)有n4/低速2/速度和20，[100.4,100.5)有n1/低速0/速度和10。边界后额外n100区间不计。预期observed.5s、vehicle1.5s、mean_n3、密度5、速度7.6/1.5、低速.7车辆秒、低速比例.7/1.5、峰值2。
- 显式complete=False时不补指标；缺中段时不补指标。
- gate时刻99.99/100/100.25/100.5/100.51按原端点定义计3次。
- gate1000在(t99.9,x999)与(t100.1,x1001)之间插值得t100；没有观测记录的其他车不补。
- 同一车同一gate重复记录拒绝。
- worker墙钟timeout且returncode124分类为物理完成情况未知，不能误作仍在运行、仿真达到max_time或算法已证实未排空。

旧L批计划为20261103_long1800_NOA4与20261103_long1800_L4，flow2250/2500、seed41/42。最终快照只有6例安全排空并封存；L2500两例worker墙钟timeout/124（3000.078/3000.063秒），原native残留starting，物理完成未知，不填指标，也不纳入两seed均值。对应operation为`20261103T061701176387Z_staggered-case-005ef2a6e1_7dac23f5`及`20261103T061941931858Z_staggered-case-0d16515191_571c0c49`。原失败尝试保留；[旧L快照报告与CSV字节副本](old_L_snapshot_report/README.md)保留全部8计划项，[独立核验](old_L_snapshot_independent_audit/verification.json)核验6可用例的全ledger、24原帧，与原结果一致，未触碰其raw。

锁定S另有完全独立的[NoA/S八例长窗报告](../long_window_NOA_S1800/README.md)：8例均安全排空、封存、完整覆盖窗口，4对可比；没有混入旧L失败或候选筛选数据。[独立审核](../long_window_NOA_S1800/independent_audit/verification.json)不导入原评价器，逐条独立积分与越线复算，并抽核每例100/600/1000/1799.9秒原始位置，共32帧，n/低速n/速度和全部精确相符。只按父明确授权，对这两个新成功批先归档验证、再按原prune_raw规则精确清理非选中raw；选中2250seed42两源完整positions/events保留本地并索引。其他批与旧raw不动，最终文件清单和释放量见新报告evidence_profiles/pruning_verification.json。
