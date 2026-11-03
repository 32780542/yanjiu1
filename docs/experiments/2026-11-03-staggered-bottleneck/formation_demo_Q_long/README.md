# Q：同输入长下游几何诊断

Q24恢复比L快且+25误差约−.000294…+.005864米；Q45在全45仍在场的+20/+25仍约±5米CTH波动，不能据24例或峰速改善宣称解决M45残余。

## 冻结合同

controller SHA `9837a67be24635102672a87b65f99a85e1ab902a1e86ac743056af6aa4ffaf41`，同原24/45输入字节、depart0/speed28.8、seed1、transform、duration1/max180，原生插入、不重排/吸附。冻结runtime只改native_sumo两个exit坐标1200→2400，controller和其余五源不变；prep640、瓶颈1000、3→2、下游1400米，source/config/input hash见[协议](protocol.json)与[两行网络补丁](Q2400_network_only.patch)。两例均安全排空、碰撞瞬移0，保留完整positions/events/diagnostic，非正式1200m效率样本。
原0/5/10/15/20帧完全保留（t0用真实首帧.1），下表按原预登记tail首次过1000的anchor+0/5/10/15及统一新增+20/+25给出全部实际数据。各方法anchor不同，不混淆绝对时刻。新增帧一律实录人数/退出，未填补退出车辆。

## 固定帧实际状态

| 输入 | anchor+ / 实际t(s) | 在场 | CTH误差min/median/max(m) | 本车v范围(m/s) |
|---|---|---:|---|---|
| unformed24 | +0 / 37.2 | 24/24 | -2.289198/-0.031292/+8.620190 | 25.284863–31.153051 |
| unformed24 | +5 / 42.2 | 24/24 | -0.529119/-0.005525/+1.137347 | 28.775581–29.354500 |
| unformed24 | +10 / 47.2 | 24/24 | -0.060326/-0.001810/+0.240774 | 28.792153–28.951580 |
| unformed24 | +15 / 52.2 | 24/24 | -0.005336/-0.000036/+0.066382 | 28.797487–28.850428 |
| formed45 | +0 / 42.4 | 45/45 | -5.936879/+0.044419/+4.290679 | 25.676192–31.013052 |
| formed45 | +5 / 47.4 | 45/45 | -5.091086/+0.012999/+5.213311 | 25.957094–30.710754 |
| formed45 | +10 / 52.4 | 45/45 | -4.792473/+0.010270/+5.058331 | 26.881685–31.024209 |
| formed45 | +15 / 57.4 | 45/45 | -4.566251/+0.006853/+4.439764 | 26.073663–31.123583 |
| unformed24 | +20 / 57.2 | 24/24 | -0.000908/-0.000010/+0.019608 | 28.799096–28.816561 |
| unformed24 | +25 / 62.2 | 24/24 | -0.000294/-0.000003/+0.005864 | 28.799687–28.805289 |
| formed45 | +20 / 62.4 | 45/45 | -5.121088/+0.001196/+5.178863 | 27.760483–30.317202 |
| formed45 | +25 / 67.4 | 45/45 | -4.341876/+0.000770/+4.528081 | 26.928593–31.078839 |

CTH用每辆实际本车v的`D(v)=5.5+(30−5.5)/28.8×v`，真实物理走廊前车车头间距减D；无真实前车留空，不当误差0。raw相邻跨道dx保留符号、不取模；x最近邻只是离线几何对象，不混淆为控制器按q互选的phase reference。0/1关系记录未用于几何成功判定。

有限视野原LocalTracks重放共40条witness事件；原59米孔ego的事件数0。全部原事件记录保留[事件CSV](all_finite_view_bridge_witness_events.csv)、[审计](bridge_audit.json)，未用邻车私有Memory。局部几何排序不进入规则。

## 完整数据与图

- [原固定帧状态](snapshot_states.csv)、[原固定帧统计](snapshot_summary.csv)、[raw跨道差](cross_lane_pair_references.csv)。
- [新增+20/+25实际人数、误差与速度](fixed_extra_20_25_summary.csv)、[新增全部实存ID状态/raw dx](fixed_extra_20_25_states.csv)、[首退出前全部连续帧统计](all_pre_exit_frame_statistics.csv)。
- [提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[原件完整封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。所有PNG300dpi+SVG，复用同一个academic-figures Nature绘图程序，未移动车辆；xy轴0…2400，标640/1000，坐标比例与状态纵轴范围分别缩放，判断应读刻度/原数值。

- unformed24：[固定xy](Q2400/unformed24_fixed_snapshots.png)、[全部预登记下游xy](Q2400/unformed24_downstream_snapshots.png)、[全时序](Q2400/unformed24_time_series.png)、[所有实存v/CTH/raw dx](Q2400/unformed24_downstream_all_states.png)，同名SVG保留。
- formed45：[固定xy](Q2400/formed45_fixed_snapshots.png)、[全部预登记下游xy](Q2400/formed45_downstream_snapshots.png)、[全时序](Q2400/formed45_time_series.png)、[所有实存v/CTH/raw dx](Q2400/formed45_downstream_all_states.png)，同名SVG保留。

本轮未加形成评价器、全局满格条件或成功时限；未以参与率或TT替代真实交错。长2400m的TT只保留原result，不并入1200m正式流量表；生产、候选与旧档案保持不变，未Git操作。
