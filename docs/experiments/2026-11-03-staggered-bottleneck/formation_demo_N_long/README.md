# N：同输入长下游几何诊断

N24指定witness孔恢复，N45到+25的真实CTH误差约−.0124…+.1922米。结果支持本两输入在原有限观察与原控制下逐步恢复有序间距；仍只列实际误差与raw跨道位置，未设全局满格或形成时限。

## 冻结合同

controller SHA `5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6`，同原24/45输入字节、depart0/speed28.8、seed1、transform、duration1/max180，原生插入、不重排/吸附。冻结runtime只改native_sumo两个exit坐标1200→2400，controller和其余五源不变；prep640、瓶颈1000、3→2、下游1400米，source/config/input hash见[协议](protocol.json)与[两行网络补丁](N2400_network_only.patch)。两例均安全排空、碰撞瞬移0，保留完整positions/events/diagnostic，非正式1200m效率样本。
原0/5/10/15/20帧完全保留（t0用真实首帧.1），下表按原预登记tail首次过1000的anchor+0/5/10/15及统一新增+20/+25给出全部实际数据。各方法anchor不同，不混淆绝对时刻。新增帧一律实录人数/退出，未填补退出车辆。

## 固定帧实际状态

| 输入 | anchor+ / 实际t(s) | 在场 | CTH误差min/median/max(m) | 本车v范围(m/s) |
|---|---|---:|---|---|
| unformed24 | +0 / 37.2 | 24/24 | -4.143082/+0.166964/+3.781841 | 26.363426–30.792275 |
| unformed24 | +5 / 42.2 | 24/24 | -2.950654/+0.143521/+3.011308 | 25.567513–31.181995 |
| unformed24 | +10 / 47.2 | 24/24 | -1.144199/+0.054961/+0.393395 | 28.740753–29.157231 |
| unformed24 | +15 / 52.2 | 24/24 | -0.265762/+0.014667/+0.131288 | 28.763409–28.883288 |
| formed45 | +0 / 41.6 | 45/45 | -3.431795/-0.004993/+3.922243 | 24.854371–30.686270 |
| formed45 | +5 / 46.6 | 45/45 | -3.766288/-0.005026/+3.358510 | 25.499360–31.238948 |
| formed45 | +10 / 51.6 | 45/45 | -2.028393/-0.003418/+1.061989 | 25.985039–31.174258 |
| formed45 | +15 / 56.6 | 45/45 | -0.037948/-0.001966/+2.509624 | 28.770222–30.687017 |
| unformed24 | +20 / 57.2 | 24/24 | -0.100078/+0.002251/+0.042109 | 28.776072–28.806975 |
| unformed24 | +25 / 62.2 | 24/24 | -0.057155/-0.000869/+0.012258 | 28.783278–28.800000 |
| formed45 | +20 / 61.6 | 45/45 | -0.021672/-0.001323/+0.686930 | 28.780624–29.098193 |
| formed45 | +25 / 66.6 | 45/45 | -0.012377/-0.000906/+0.192151 | 28.787306–28.873764 |

CTH用每辆实际本车v的`D(v)=5.5+(30−5.5)/28.8×v`，真实物理走廊前车车头间距减D；无真实前车留空，不当误差0。raw相邻跨道dx保留符号、不取模；x最近邻只是离线几何对象，不混淆为控制器按q互选的phase reference。0/1关系记录未用于几何成功判定。

有限视野原LocalTracks重放共37条witness事件；原59米孔ego的事件数28。全部原事件记录保留[事件CSV](all_finite_view_bridge_witness_events.csv)、[审计](bridge_audit.json)，未用邻车私有Memory。局部几何排序不进入规则。

## 完整数据与图

- [原固定帧状态](snapshot_states.csv)、[原固定帧统计](snapshot_summary.csv)、[raw跨道差](cross_lane_pair_references.csv)。
- [新增+20/+25实际人数、误差与速度](fixed_extra_20_25_summary.csv)、[新增全部实存ID状态/raw dx](fixed_extra_20_25_states.csv)、[首退出前全部连续帧统计](all_pre_exit_frame_statistics.csv)。
- [提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[原件完整封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。所有PNG300dpi+SVG，复用同一个academic-figures Nature绘图程序，未移动车辆；xy轴0…2400，标640/1000，坐标比例与状态纵轴范围分别缩放，判断应读刻度/原数值。

- unformed24：[固定xy](N2400/unformed24_fixed_snapshots.png)、[全部预登记下游xy](N2400/unformed24_downstream_snapshots.png)、[全时序](N2400/unformed24_time_series.png)、[所有实存v/CTH/raw dx](N2400/unformed24_downstream_all_states.png)，同名SVG保留。
- formed45：[固定xy](N2400/formed45_fixed_snapshots.png)、[全部预登记下游xy](N2400/formed45_downstream_snapshots.png)、[全时序](N2400/formed45_time_series.png)、[所有实存v/CTH/raw dx](N2400/formed45_downstream_all_states.png)，同名SVG保留。

本轮未加形成评价器、全局满格条件或成功时限；未以参与率或TT替代真实交错。长2400m的TT只保留原result，不并入1200m正式流量表；生产、候选与旧档案保持不变，未Git操作。
