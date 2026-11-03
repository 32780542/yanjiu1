# LP0：同输入长下游几何诊断

LP0不是交错成功：24同道CTH虽接近零，+20所有raw跨道差却仅±.770… .929米，实际接近并排；45的raw多0或±5.63…5.95米，仍有65.623米同道孔。+25已43/45在场，不能用幸存车宣称全组完成。没有因TT较好把普通同道跟驰认作15米交错。

## 冻结合同

controller SHA `64a134fee75ae628779b81e497fca1de6b095a2f1828493c573ee2dacc455eb4`，同原24/45输入字节、depart0/speed28.8、seed1、transform、duration1/max180，原生插入、不重排/吸附。冻结runtime只改native_sumo两个exit坐标1200→2400，controller和其余五源不变；prep640、瓶颈1000、3→2、下游1400米，source/config/input hash见[协议](protocol.json)与[两行网络补丁](LP02400_network_only.patch)。两例均安全排空、碰撞瞬移0，保留完整positions/events/diagnostic，非正式1200m效率样本。
原0/5/10/15/20帧完全保留（t0用真实首帧.1），下表按原预登记tail首次过1000的anchor+0/5/10/15及统一新增+20/+25给出全部实际数据。各方法anchor不同，不混淆绝对时刻。新增帧一律实录人数/退出，未填补退出车辆。

## 固定帧实际状态

| 输入 | anchor+ / 实际t(s) | 在场 | CTH误差min/median/max(m) | 本车v范围(m/s) |
|---|---|---:|---|---|
| unformed24 | +0 / 36.8 | 24/24 | -0.822526/-0.096232/+0.676955 | 27.854455–29.251671 |
| unformed24 | +5 / 41.8 | 24/24 | -0.195960/-0.024624/+0.181409 | 28.433053–28.957279 |
| unformed24 | +10 / 46.8 | 24/24 | -0.077102/-0.004066/+0.050446 | 28.662554–28.871723 |
| unformed24 | +15 / 51.8 | 24/24 | -0.031959/-0.001001/+0.015820 | 28.749858–28.833606 |
| formed45 | +0 / 42.9 | 45/45 | -3.867715/-0.012254/+37.019785 | 27.086282–29.800065 |
| formed45 | +5 / 47.9 | 45/45 | -0.918338/-0.004445/+35.539554 | 28.071210–29.108751 |
| formed45 | +10 / 52.9 | 45/45 | -0.209642/-0.000485/+35.598043 | 28.492812–28.896050 |
| formed45 | +15 / 57.9 | 45/45 | -0.067947/-0.000122/+35.616806 | 28.672279–28.830194 |
| unformed24 | +20 / 56.8 | 24/24 | -0.012582/-0.000125/+0.006153 | 28.782080–28.814214 |
| unformed24 | +25 / 61.8 | 24/24 | -0.004775/-0.000041/+0.002831 | 28.793702–28.805638 |
| formed45 | +20 / 62.9 | 45/45 | -0.028046/-0.000023/+35.622739 | 28.747709–28.809604 |
| formed45 | +25 / 67.9 | 43/45 | -0.011581/-0.000011/+35.624593 | 28.778922–28.803091 |

CTH用每辆实际本车v的`D(v)=5.5+(30−5.5)/28.8×v`，真实物理走廊前车车头间距减D；无真实前车留空，不当误差0。raw相邻跨道dx保留符号、不取模；x最近邻只是离线几何对象，不混淆为控制器按q互选的phase reference。0/1关系记录未用于几何成功判定。

有限视野原LocalTracks重放共16条witness事件；原59米孔ego的事件数0。全部原事件记录保留[事件CSV](all_finite_view_bridge_witness_events.csv)、[审计](bridge_audit.json)，未用邻车私有Memory。局部几何排序不进入规则。

## 完整数据与图

- [原固定帧状态](snapshot_states.csv)、[原固定帧统计](snapshot_summary.csv)、[raw跨道差](cross_lane_pair_references.csv)。
- [新增+20/+25实际人数、误差与速度](fixed_extra_20_25_summary.csv)、[新增全部实存ID状态/raw dx](fixed_extra_20_25_states.csv)、[首退出前全部连续帧统计](all_pre_exit_frame_statistics.csv)。
- [提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[原件完整封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。所有PNG300dpi+SVG，复用同一个academic-figures Nature绘图程序，未移动车辆；xy轴0…2400，标640/1000，坐标比例与状态纵轴范围分别缩放，判断应读刻度/原数值。

- unformed24：[固定xy](LP02400/unformed24_fixed_snapshots.png)、[全部预登记下游xy](LP02400/unformed24_downstream_snapshots.png)、[全时序](LP02400/unformed24_time_series.png)、[所有实存v/CTH/raw dx](LP02400/unformed24_downstream_all_states.png)，同名SVG保留。
- formed45：[固定xy](LP02400/formed45_fixed_snapshots.png)、[全部预登记下游xy](LP02400/formed45_downstream_snapshots.png)、[全时序](LP02400/formed45_time_series.png)、[所有实存v/CTH/raw dx](LP02400/formed45_downstream_all_states.png)，同名SVG保留。

本轮未加形成评价器、全局满格条件或成功时限；未以参与率或TT替代真实交错。长2400m的TT只保留原result，不并入1200m正式流量表；生产、候选与旧档案保持不变，未Git操作。
