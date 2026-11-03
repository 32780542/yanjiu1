# LT：同输入长下游几何诊断

LT24逐步恢复，45多数raw跨道差已接近±15，但尾部仍调距，+25尾部真实gap45.538730米、CTH误差+12.894945米、ego速度31.907797。不能把尾部大孔直接当全局失败，也不能说首退出前全组已精确交错；所有大空隙与端点都如实保留。

## 冻结合同

controller SHA `8a773793ccba5eb5e0ecae7f1b02083a8571d7e77f5a1f5f5f78b13eb6596593`，同原24/45输入字节、depart0/speed28.8、seed1、transform、duration1/max180，原生插入、不重排/吸附。冻结runtime只改native_sumo两个exit坐标1200→2400，controller和其余五源不变；prep640、瓶颈1000、3→2、下游1400米，source/config/input hash见[协议](protocol.json)与[两行网络补丁](LT2400_network_only.patch)。两例均安全排空、碰撞瞬移0，保留完整positions/events/diagnostic，非正式1200m效率样本。
原0/5/10/15/20帧完全保留（t0用真实首帧.1），下表按原预登记tail首次过1000的anchor+0/5/10/15及统一新增+20/+25给出全部实际数据。各方法anchor不同，不混淆绝对时刻。新增帧一律实录人数/退出，未填补退出车辆。

## 固定帧实际状态

| 输入 | anchor+ / 实际t(s) | 在场 | CTH误差min/median/max(m) | 本车v范围(m/s) |
|---|---|---:|---|---|
| unformed24 | +0 / 37.4 | 24/24 | -4.248667/+0.098638/+3.762369 | 26.368563–31.435213 |
| unformed24 | +5 / 42.4 | 24/24 | -1.826837/+0.060881/+1.166177 | 26.974265–31.081124 |
| unformed24 | +10 / 47.4 | 24/24 | -0.647791/+0.008363/+0.374505 | 28.747961–29.056016 |
| unformed24 | +15 / 52.4 | 24/24 | -0.154215/-0.000106/+0.118315 | 28.763121–28.852145 |
| formed45 | +0 / 42.4 | 45/45 | -3.555053/+0.001895/+3.409011 | 25.257405–31.237708 |
| formed45 | +5 / 47.4 | 45/45 | -4.111072/+0.007256/+3.937845 | 26.328637–31.169395 |
| formed45 | +10 / 52.4 | 45/45 | -8.457289/+0.001623/+54.751532 | 24.916287–30.452540 |
| formed45 | +15 / 57.4 | 45/45 | -2.206682/+0.000340/+54.429540 | 28.219268–28.960094 |
| unformed24 | +20 / 57.4 | 24/24 | -0.086704/-0.002035/+0.035675 | 28.775109–28.800000 |
| unformed24 | +25 / 62.4 | 24/24 | -0.048747/-0.001612/+0.009558 | 28.783450–28.800000 |
| formed45 | +20 / 62.4 | 45/45 | -0.017280/-0.000562/+21.533775 | 28.789275–31.368222 |
| formed45 | +25 / 67.4 | 45/45 | -0.009715/-0.000572/+12.894945 | 28.792364–31.907797 |

CTH用每辆实际本车v的`D(v)=5.5+(30−5.5)/28.8×v`，真实物理走廊前车车头间距减D；无真实前车留空，不当误差0。raw相邻跨道dx保留符号、不取模；x最近邻只是离线几何对象，不混淆为控制器按q互选的phase reference。0/1关系记录未用于几何成功判定。

有限视野原LocalTracks重放共57条witness事件；原59米孔ego的事件数29。全部原事件记录保留[事件CSV](all_finite_view_bridge_witness_events.csv)、[审计](bridge_audit.json)，未用邻车私有Memory。局部几何排序不进入规则。

## 完整数据与图

- [原固定帧状态](snapshot_states.csv)、[原固定帧统计](snapshot_summary.csv)、[raw跨道差](cross_lane_pair_references.csv)。
- [新增+20/+25实际人数、误差与速度](fixed_extra_20_25_summary.csv)、[新增全部实存ID状态/raw dx](fixed_extra_20_25_states.csv)、[首退出前全部连续帧统计](all_pre_exit_frame_statistics.csv)。
- [提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[原件完整封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。所有PNG300dpi+SVG，复用同一个academic-figures Nature绘图程序，未移动车辆；xy轴0…2400，标640/1000，坐标比例与状态纵轴范围分别缩放，判断应读刻度/原数值。

- unformed24：[固定xy](LT2400/unformed24_fixed_snapshots.png)、[全部预登记下游xy](LT2400/unformed24_downstream_snapshots.png)、[全时序](LT2400/unformed24_time_series.png)、[所有实存v/CTH/raw dx](LT2400/unformed24_downstream_all_states.png)，同名SVG保留。
- formed45：[固定xy](LT2400/formed45_fixed_snapshots.png)、[全部预登记下游xy](LT2400/formed45_downstream_snapshots.png)、[全时序](LT2400/formed45_time_series.png)、[所有实存v/CTH/raw dx](LT2400/formed45_downstream_all_states.png)，同名SVG保留。

本轮未加形成评价器、全局满格条件或成功时限；未以参与率或TT替代真实交错。长2400m的TT只保留原result，不并入1200m正式流量表；生产、候选与旧档案保持不变，未Git操作。
