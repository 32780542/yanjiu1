"""Measured fixed-frame report for small M/N/Q/LP0 long-road diagnostics."""
import argparse,csv,json
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--label',choices=['M','N','Q','LP0','LT','S'],required=True);a=parser.parse_args()
BASE=Path(__file__).resolve().parent.parent;OUT=BASE/('formation_demo_'+a.label+'_long');p=json.loads((OUT/'protocol.json').read_text());tag=a.label+'2400'
def rows(name):
    with (OUT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
ss=rows('snapshot_summary.csv');extra=rows('fixed_extra_20_25_summary.csv');audit=json.loads((OUT/'bridge_audit.json').read_text())
notes={
 'S':'S在本两输入均保留有序交错并恢复实际间距：24在+25全部跨道raw差约±14.9929…15米；45在+25约±14.9702…15米，同道CTH误差约−.010751…−.000039米，全组仍在场。未见M/Q相同窗口内持续约5米残余。此处仅陈述固定真实输入，未以全局满格、成功时限或参与率作新门槛。',
 'LT':'LT24逐步恢复，45多数raw跨道差已接近±15，但尾部仍调距，+25尾部真实gap45.538730米、CTH误差+12.894945米、ego速度31.907797。不能把尾部大孔直接当全局失败，也不能说首退出前全组已精确交错；所有大空隙与端点都如实保留。',
 'M':'M24有witness孔继续恢复但同+15慢于L；M45全组在场至+25仍约±5.5米CTH残余，不是仅慢收敛，也不能只凭峰速较低声称振荡改善。冻结局部函数复算显示真实CTH与饱和相位项相反并接近抵消，见下方跨方法动态与具体互选事件。',
 'N':'N24指定witness孔恢复，N45到+25的真实CTH误差约−.0124…+.1922米。结果支持本两输入在原有限观察与原控制下逐步恢复有序间距；仍只列实际误差与raw跨道位置，未设全局满格或形成时限。',
 'Q':'Q24恢复比L快且+25误差约−.000294…+.005864米；Q45在全45仍在场的+20/+25仍约±5米CTH波动，不能据24例或峰速改善宣称解决M45残余。',
 'LP0':'LP0不是交错成功：24同道CTH虽接近零，+20所有raw跨道差却仅±.770… .929米，实际接近并排；45的raw多0或±5.63…5.95米，仍有65.623米同道孔。+25已43/45在场，不能用幸存车宣称全组完成。没有因TT较好把普通同道跟驰认作15米交错。'}
lines=[f'# {a.label}：同输入长下游几何诊断','',notes[a.label],'',
 '## 冻结合同','',f'controller SHA `{p["runtimes"][tag]["rules_sha256"]}`，同原24/45输入字节、depart0/speed28.8、seed1、transform、duration1/max180，原生插入、不重排/吸附。冻结runtime只改native_sumo两个exit坐标1200→2400，controller和其余五源不变；prep640、瓶颈1000、3→2、下游1400米，source/config/input hash见[协议](protocol.json)与[两行网络补丁]({tag}_network_only.patch)。两例均安全排空、碰撞瞬移0，保留完整positions/events/diagnostic，非正式1200m效率样本。',
 '原0/5/10/15/20帧完全保留（t0用真实首帧.1），下表按原预登记tail首次过1000的anchor+0/5/10/15及统一新增+20/+25给出全部实际数据。各方法anchor不同，不混淆绝对时刻。新增帧一律实录人数/退出，未填补退出车辆。','',
 '## 固定帧实际状态','',
 '| 输入 | anchor+ / 实际t(s) | 在场 | CTH误差min/median/max(m) | 本车v范围(m/s) |',
 '|---|---|---:|---|---|']
for r in [*filter(lambda r:r['frame_kind']=='registered_downstream',ss),*extra]:
    lines.append(f'| {r["demo"]} | +{float(r["anchor_offset_s"]):g} / {float(r["time_s"]):.1f} | {r["onroad_n"]}/{r["initial_n"]} | {float(r["cth_error_min"]):+.6f}/{float(r["cth_error_median"]):+.6f}/{float(r["cth_error_max"]):+.6f} | {float(r["v_min"]):.6f}–{float(r["v_max"]):.6f} |')
lines+=['','CTH用每辆实际本车v的`D(v)=5.5+(30−5.5)/28.8×v`，真实物理走廊前车车头间距减D；无真实前车留空，不当误差0。raw相邻跨道dx保留符号、不取模；x最近邻只是离线几何对象，不混淆为控制器按q互选的phase reference。0/1关系记录未用于几何成功判定。','',
 f'有限视野原LocalTracks重放共{audit["qualified_local_witness_event_rows"]}条witness事件；原59米孔ego的事件数{audit["original_ego_bridge_event_rows"]}。全部原事件记录保留[事件CSV](all_finite_view_bridge_witness_events.csv)、[审计](bridge_audit.json)，未用邻车私有Memory。局部几何排序不进入规则。','',
 '## 完整数据与图','',
 '- [原固定帧状态](snapshot_states.csv)、[原固定帧统计](snapshot_summary.csv)、[raw跨道差](cross_lane_pair_references.csv)。',
 '- [新增+20/+25实际人数、误差与速度](fixed_extra_20_25_summary.csv)、[新增全部实存ID状态/raw dx](fixed_extra_20_25_states.csv)、[首退出前全部连续帧统计](all_pre_exit_frame_statistics.csv)。',
 '- [提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[原件完整封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。所有PNG300dpi+SVG，复用同一个academic-figures Nature绘图程序，未移动车辆；xy轴0…2400，标640/1000，坐标比例与状态纵轴范围分别缩放，判断应读刻度/原数值。','']
for demo in ['unformed24','formed45']:lines.append(f'- {demo}：[固定xy]({tag}/{demo}_fixed_snapshots.png)、[全部预登记下游xy]({tag}/{demo}_downstream_snapshots.png)、[全时序]({tag}/{demo}_time_series.png)、[所有实存v/CTH/raw dx]({tag}/{demo}_downstream_all_states.png)，同名SVG保留。')
if a.label=='M':lines+=['','## 取消形成时限后的连续说明','',
 '统一E/J2/L/M全原轨迹动态与固定+20/+25在[formation_dynamics_all](../formation_dynamics_all/README.md)。M45持续残余的[真实局部phase/CTH复算](../formation_dynamics_all/M45_actual_local_phase_CTH_replay.csv)及[精确命令核验](../formation_dynamics_all/M45_local_replay_verification.json)保留。t61.6互选l2_r06↔l1_r07 raw±24.70346、q±9.70346，dv/K±5.61155，phase指令增量±.4与CTH∓.37956/.38041抵消；t66.6另一稳定互选对l2_r05↔l0_r05 raw±25.03115、q±10.03115同样对抗。既有真实配对切换也完整列出，不能把这些稳定互选事件仅解释成瞬时错误配对，也没有据此宣称全局静态平衡证明。']
lines+=['','本轮未加形成评价器、全局满格条件或成功时限；未以参与率或TT替代真实交错。长2400m的TT只保留原result，不并入1200m正式流量表；生产、候选与旧档案保持不变，未Git操作。','']
(OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
print({'profile':a.label,'report':str(OUT/'README.md'),'uniform_extra_rows':len(extra)})
