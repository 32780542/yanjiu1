# S：同输入长下游几何诊断

分析重试记录：首次witness审计已经正确得到两例均0条合格事件，但写空CSV时假定有首行而失败（不是仿真或控制器失败）。[首次脚本与输出原件](audit_attempt1/failure.json)保留；新建`analyze_S_long_retry2.py`复用原L表头写零行CSV，未重跑SUMO、未填入虚构事件。重试独立完成，后续核验使用零事件结果。首次最终核验还发现此段失败元数据链接拼写错误，纠正后另建核验操作重试，旧操作日志保留。

S在本两输入均保留有序交错并恢复实际间距：24在+25全部跨道raw差约±14.9929…15米；45在+25约±14.9702…15米，同道CTH误差约−.010751…−.000039米，全组仍在场。未见M/Q相同窗口内持续约5米残余。此处仅陈述固定真实输入，未以全局满格、成功时限或参与率作新门槛。

## 冻结合同

controller SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，同原24/45输入字节、depart0/speed28.8、seed1、transform、duration1/max180，原生插入、不重排/吸附。冻结runtime只改native_sumo两个exit坐标1200→2400，controller和其余五源不变；prep640、瓶颈1000、3→2、下游1400米，source/config/input hash见[协议](protocol.json)与[两行网络补丁](S2400_network_only.patch)。两例均安全排空、碰撞瞬移0，保留完整positions/events/diagnostic，非正式1200m效率样本。
原0/5/10/15/20帧完全保留（t0用真实首帧.1），下表按原预登记tail首次过1000的anchor+0/5/10/15及统一新增+20/+25给出全部实际数据。各方法anchor不同，不混淆绝对时刻。新增帧一律实录人数/退出，未填补退出车辆。

## 固定帧实际状态

| 输入 | anchor+ / 实际t(s) | 在场 | CTH误差min/median/max(m) | 本车v范围(m/s) |
|---|---|---:|---|---|
| unformed24 | +0 / 36.9 | 24/24 | -0.690155/-0.103659/+1.159538 | 28.254641–28.874129 |
| unformed24 | +5 / 41.9 | 24/24 | -0.233666/-0.041619/+0.225260 | 28.583302–28.820268 |
| unformed24 | +10 / 46.9 | 24/24 | -0.082986/-0.011368/+0.027321 | 28.716036–28.805403 |
| unformed24 | +15 / 51.9 | 24/24 | -0.028773/-0.003321/+0.004835 | 28.767930–28.801531 |
| formed45 | +0 / 41.7 | 45/45 | -0.850647/-0.055935/+0.044525 | 27.403222–28.800000 |
| formed45 | +5 / 46.7 | 45/45 | -0.298683/-0.020453/+0.006635 | 28.139304–28.800000 |
| formed45 | +10 / 51.7 | 45/45 | -0.122866/-0.010803/-0.000689 | 28.508049–28.800000 |
| formed45 | +15 / 56.7 | 45/45 | -0.055483/-0.004569/-0.000270 | 28.674612–28.800000 |
| unformed24 | +20 / 56.9 | 24/24 | -0.009948/-0.001106/+0.001192 | 28.787820–28.800451 |
| unformed24 | +25 / 61.9 | 24/24 | -0.003431/-0.000319/+0.000297 | 28.795590–28.800133 |
| formed45 | +20 / 61.7 | 45/45 | -0.024707/-0.001909/-0.000103 | 28.746890–28.800000 |
| formed45 | +25 / 66.7 | 45/45 | -0.010751/-0.000805/-0.000039 | 28.777565–28.800000 |

CTH用每辆实际本车v的`D(v)=5.5+(30−5.5)/28.8×v`，真实物理走廊前车车头间距减D；无真实前车留空，不当误差0。raw相邻跨道dx保留符号、不取模；x最近邻只是离线几何对象，不混淆为控制器按q互选的phase reference。0/1关系记录未用于几何成功判定。

有限视野原LocalTracks重放共0条witness事件；原59米孔ego的事件数0。全部原事件记录保留[事件CSV](all_finite_view_bridge_witness_events.csv)、[审计](bridge_audit.json)，未用邻车私有Memory。局部几何排序不进入规则。

## 完整数据与图

- [原固定帧状态](snapshot_states.csv)、[原固定帧统计](snapshot_summary.csv)、[raw跨道差](cross_lane_pair_references.csv)。
- [新增+20/+25实际人数、误差与速度](fixed_extra_20_25_summary.csv)、[新增全部实存ID状态/raw dx](fixed_extra_20_25_states.csv)、[首退出前全部连续帧统计](all_pre_exit_frame_statistics.csv)。
- [提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[原件完整封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。所有PNG300dpi+SVG，复用同一个academic-figures Nature绘图程序，未移动车辆；xy轴0…2400，标640/1000，坐标比例与状态纵轴范围分别缩放，判断应读刻度/原数值。

- unformed24：[固定xy](S2400/unformed24_fixed_snapshots.png)、[全部预登记下游xy](S2400/unformed24_downstream_snapshots.png)、[全时序](S2400/unformed24_time_series.png)、[所有实存v/CTH/raw dx](S2400/unformed24_downstream_all_states.png)，同名SVG保留。
- formed45：[固定xy](S2400/formed45_fixed_snapshots.png)、[全部预登记下游xy](S2400/formed45_downstream_snapshots.png)、[全时序](S2400/formed45_time_series.png)、[所有实存v/CTH/raw dx](S2400/formed45_downstream_all_states.png)，同名SVG保留。

本轮未加形成评价器、全局满格条件或成功时限；未以参与率或TT替代真实交错。长2400m的TT只保留原result，不并入1200m正式流量表；生产、候选与旧档案保持不变，未Git操作。
