# M：同输入长下游几何诊断

M24有witness孔继续恢复但同+15慢于L；M45全组在场至+25仍约±5.5米CTH残余，不是仅慢收敛，也不能只凭峰速较低声称振荡改善。冻结局部函数复算显示真实CTH与饱和相位项相反并接近抵消，见下方跨方法动态与具体互选事件。

## 冻结合同

controller SHA `a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762`，同原24/45输入字节、depart0/speed28.8、seed1、transform、duration1/max180，原生插入、不重排/吸附。冻结runtime只改native_sumo两个exit坐标1200→2400，controller和其余五源不变；prep640、瓶颈1000、3→2、下游1400米，source/config/input hash见[协议](protocol.json)与[两行网络补丁](M2400_network_only.patch)。两例均安全排空、碰撞瞬移0，保留完整positions/events/diagnostic，非正式1200m效率样本。
原0/5/10/15/20帧完全保留（t0用真实首帧.1），下表按原预登记tail首次过1000的anchor+0/5/10/15及统一新增+20/+25给出全部实际数据。各方法anchor不同，不混淆绝对时刻。新增帧一律实录人数/退出，未填补退出车辆。

## 固定帧实际状态

| 输入 | anchor+ / 实际t(s) | 在场 | CTH误差min/median/max(m) | 本车v范围(m/s) |
|---|---|---:|---|---|
| unformed24 | +0 / 37.9 | 24/24 | -6.895413/-0.006939/+25.594916 | 26.893018–29.736175 |
| unformed24 | +5 / 42.9 | 24/24 | -6.372431/-0.040544/+16.955869 | 28.416751–31.842290 |
| unformed24 | +10 / 47.9 | 24/24 | -1.632164/+0.000710/+4.445178 | 28.645375–30.320025 |
| unformed24 | +15 / 52.9 | 24/24 | -0.320200/+0.021264/+1.137270 | 28.722471–29.292111 |
| formed45 | +0 / 41.6 | 45/45 | -6.030516/-0.062343/+7.443516 | 25.700108–30.179633 |
| formed45 | +5 / 46.6 | 45/45 | -5.234285/-0.021544/+5.147692 | 26.177357–30.137361 |
| formed45 | +10 / 51.6 | 45/45 | -5.337713/-0.005936/+5.258016 | 26.628075–30.282563 |
| formed45 | +15 / 56.6 | 45/45 | -5.428558/-0.002013/+5.356919 | 27.709365–30.029648 |
| unformed24 | +20 / 57.9 | 24/24 | -0.194924/+0.015581/+0.288932 | 28.753603–28.979948 |
| unformed24 | +25 / 62.9 | 24/24 | -0.118692/+0.011700/+0.071658 | 28.770029–28.850667 |
| formed45 | +20 / 61.6 | 45/45 | -5.513143/+0.000892/+5.448234 | 27.778203–29.973129 |
| formed45 | +25 / 66.6 | 45/45 | -5.592466/+0.000283/+5.533567 | 27.840035–29.916852 |

CTH用每辆实际本车v的`D(v)=5.5+(30−5.5)/28.8×v`，真实物理走廊前车车头间距减D；无真实前车留空，不当误差0。raw相邻跨道dx保留符号、不取模；x最近邻只是离线几何对象，不混淆为控制器按q互选的phase reference。0/1关系记录未用于几何成功判定。

有限视野原LocalTracks重放共71条witness事件；原59米孔ego的事件数2。全部原事件记录保留[事件CSV](all_finite_view_bridge_witness_events.csv)、[审计](bridge_audit.json)，未用邻车私有Memory。局部几何排序不进入规则。

## 完整数据与图

- [原固定帧状态](snapshot_states.csv)、[原固定帧统计](snapshot_summary.csv)、[raw跨道差](cross_lane_pair_references.csv)。
- [新增+20/+25实际人数、误差与速度](fixed_extra_20_25_summary.csv)、[新增全部实存ID状态/raw dx](fixed_extra_20_25_states.csv)、[首退出前全部连续帧统计](all_pre_exit_frame_statistics.csv)。
- [提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[原件完整封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。所有PNG300dpi+SVG，复用同一个academic-figures Nature绘图程序，未移动车辆；xy轴0…2400，标640/1000，坐标比例与状态纵轴范围分别缩放，判断应读刻度/原数值。

- unformed24：[固定xy](M2400/unformed24_fixed_snapshots.png)、[全部预登记下游xy](M2400/unformed24_downstream_snapshots.png)、[全时序](M2400/unformed24_time_series.png)、[所有实存v/CTH/raw dx](M2400/unformed24_downstream_all_states.png)，同名SVG保留。
- formed45：[固定xy](M2400/formed45_fixed_snapshots.png)、[全部预登记下游xy](M2400/formed45_downstream_snapshots.png)、[全时序](M2400/formed45_time_series.png)、[所有实存v/CTH/raw dx](M2400/formed45_downstream_all_states.png)，同名SVG保留。

## 取消形成时限后的连续说明

统一E/J2/L/M全原轨迹动态与固定+20/+25在[formation_dynamics_all](../formation_dynamics_all/README.md)。M45持续残余的[真实局部phase/CTH复算](../formation_dynamics_all/M45_actual_local_phase_CTH_replay.csv)及[精确命令核验](../formation_dynamics_all/M45_local_replay_verification.json)保留。t61.6互选l2_r06↔l1_r07 raw±24.70346、q±9.70346，dv/K±5.61155，phase指令增量±.4与CTH∓.37956/.38041抵消；t66.6另一稳定互选对l2_r05↔l0_r05 raw±25.03115、q±10.03115同样对抗。既有真实配对切换也完整列出，不能把这些稳定互选事件仅解释成瞬时错误配对，也没有据此宣称全局静态平衡证明。

本轮未加形成评价器、全局满格条件或成功时限；未以参与率或TT替代真实交错。长2400m的TT只保留原result，不并入1200m正式流量表；生产、候选与旧档案保持不变，未Git操作。
