"""Write the measured L/J2 report and prepare independent verification/sealing."""
import ast
import csv
import json
from pathlib import Path
OUT=Path(__file__).resolve().parent;OLD=OUT.parent/'formation_demo_long'
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
q=[]
for r in rows(OUT/'snapshot_states.csv'):
    lateral=max(0.,min(2.,float(r['y_m'])/3.3-.5));lo=int(lateral);hi=min(lo+1,2)
    phi=(15. if lo%2 else 0.)+(lateral-lo)*((15. if hi%2 else 0.)-(15. if lo%2 else 0.))
    q.append(dict(**r,physical_phase_3_m=phi,q_m=float(r['x_m'])+phi))
with (OUT/'all_selected_physical_q.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(q[0]));w.writeheader();w.writerows(q)
ss=rows(OUT/'snapshot_summary.csv');comparison=rows(OUT/'J2_L_registered_comparison.csv')
lines=['# L：原输入、长下游的真实几何验收','',
    '**L修复了本24辆输入中有实际邻道witness的约59米孔；45辆变换后几何基本保留J2表现。** 这是两例真实SUMO局部几何诊断，不是正式效率样本；未设全局满格、全车合成一队或新增形成成功门槛。','',
    '## 固定合同','',
    '- L冻结自`20261103_L_screen180_8/sources/L`，controller SHA `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`。原冻结源另外保存在`sources_original/L2400/`；[协议及逐源hash](protocol.json)。',
    '- 仅复制后的`native_sumo.py`两行exit1200→2400，[补丁](L2400_network_only.patch)。controller及其余五源不变，配置/init原样。原3→2、prep640、瓶颈1000；网XML实测上游1000m/3道、下游1400m/2道。',
    '- 原24未成形与45预成形JSON逐字节复用，depart0/speed28.8，原生插入、不重排/吸附。duration1/max_time180、seed1、transform、full diagnostic，两个独立run_logged600均安全排空，碰撞/瞬移0。',
    '- 保留0/5/10/15/20秒（t0使用首个真实.1帧），另用最后初始车首次被实测过1000的anchor+0/5/10/15。24 anchor38.1、45 anchor41.8；所有8个下游帧均全24/45辆在场，无提前退出、实际lane2=0。J2对应24anchor37.8，45同41.8，按同一相对偏移比较，不混淆绝对时刻。','',
    '## 全部预登记下游结果','',
    '| 输入/方法 | anchor+秒 / 实际t | 在场 | 实际lane0/1 | 本车v范围(m/s) | 真实前距−D(v) min/median/max(m) |',
    '|---|---|---:|---|---|---|']
for r in comparison:
    for tag in ['J2','L']:
        lines.append(f'| {r["demo"]}/{tag} | +{float(r["anchor_offset_s"]):g} / {float(r[tag+"_time_s"]):.1f} | {r[tag+"_onroad_n"]}/{r[tag+"_initial_n"]} | {r[tag+"_n_lane0"]}/{r[tag+"_n_lane1"]} | {float(r[tag+"_v_min"]):.3f}–{float(r[tag+"_v_max"]):.3f} | {float(r[tag+"_cth_error_min"]):+.3f}/{float(r[tag+"_cth_error_median"]):+.3f}/{float(r[tag+"_cth_error_max"]):+.3f} |')
lines+=['','`D(v)=5.5+(30−5.5)/28.8×本车v`，车头前距不扣车长；每帧24例22/45例43个真实前车，无前车留空，不当误差0。实际前车与车体走廊定义沿用原E/J2离线工具；raw跨道差保留正负、不取模。完整表：[同输入对比](J2_L_registered_comparison.csv)、[全部ID状态](snapshot_states.csv)、[raw跨道差及15米/速度参考](cross_lane_pair_references.csv)、[真实物理相位q](all_selected_physical_q.csv)。0/1仍只是原局部关系记录，未用于几何判定。','',
    '## 原59米孔：有限观测、实际动作与后续间距','',
    '指定原对象`unformed_l2_r05`→`unformed_l2_r06`仍保持实际同道前后关系。L在t21.6首次出现该ego的真实witness事件：ego x793.061767、lane1、v24.027920；front x843.413326、v27.629142，gap50.351559；邻道witness `unformed_l0_r05` x829.125082、lane0，指定相位式残差+.711756m。默认50m CF没有前车，60m分支的真实front private track=9；原记录动作join_follow、reference=9、command26.612833。',
    '该ego在21.6…24.3共28帧满足分支条件且记录reference确实指向该front；最后24.3 gap50.039606、witness残差+.921322、command30.951175。不是只从最终图推测规则生效。[全40条有限视野witness事件](all_finite_view_bridge_witness_events.csv)包含24例38帧/3辆、45例2帧/1辆，所有40条记录reference均与extended真实front匹配；源`LocalTracks`类按每帧私有轨迹历史原样重放，范围后100/前200m，不把全场ID交给控制规则。事件复盘不启动运动仿真。',
    '同一指定绝对t52.8：J2原gap58.792395、CTH误差+28.908640；L该同一实际前车gap29.968305、CTH误差−.006366，ego v28.770226。front在两控制器此时x1733.166541670527、v28.771742537094685完全相同；L的ego位置由J2的1674.374146变成1703.198236，约28.824m差异来自实际运动，并非离线重排。L预登记+15=t53.1该pair gap29.968781、误差−.006600。见[原对象真实历史](original_59m_pair_actual_history.csv)、[事件摘要](bridge_audit.json)。','',
    '## 跨道几何与保留的限制','',
    '- L24在+15全体在场，同道误差−.158…+.116m；多数raw相邻差约±15m，但尾车`unformed_l2_r00`至lane0首个实车仍为+45.140591m。实际lane0/1=11/13，两道尾位置分别1486.359871/1441.219280，头位置1786.827537/1801.556027；该端部差不能被取模成15，也不以端部未配齐要求追赶合队。当前结论是指定witness孔恢复、局部交错更有秩序，并不要求每格全满。',
    '- L45在+15 raw绝对差13.385580…15.000001m，与J2非常接近；CTH误差−1.789985/中位+.002428/+1.017623，速度27.604…31.102m/s，尾端仍在调距。没有因为修复24孔而宣称45全部精确平衡，也没有证据支持此输入明显优于J2。',
    '- [L与原J2完整controller diff](L_vs_J2_rules.patch)除局部桥接也包含已有J2fast缓存/短路优化，本报告不把源码差异隐去；实际事件引用由有限视野重放逐条验证。这里不另证明那些优化的全空间行为等价，也不以这两例推断大流量正式效率或任意初态普遍成功。',
    '- 长2400m的TT只保留在原result中，不并入原1200m正式统计，不作跨道路效率比较；全时序含车辆退出后的轨迹，但几何对比限定预登记全体在场帧。','',
    '## 图、原件和封包','',
    '严格复用原长下游同一个绘图程序，academic-figures Nature风格，300dpi PNG+SVG，全部8组目检。xy轴0…2400，标640/1000；坐标比例独立，状态纵轴自动范围，比较请读数值/刻度。颜色=初始车道、marker=当前实际车道。','']
for demo in ['unformed24','formed45']:
    lines.append(f'- {demo}：[原固定xy](L2400/{demo}_fixed_snapshots.png)、[全部预登记下游xy](L2400/{demo}_downstream_snapshots.png)、[全时序](L2400/{demo}_time_series.png)、[所有实存v/CTH/raw dx](L2400/{demo}_downstream_all_states.png)，同名SVG完整保留。')
lines+=['','[提取核验](extraction_verification.json)、[独立全轨迹核验](final_verification.json)、[完整原件封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。封包保留两例全positions/events/diagnostic、input/source、网XML、命令、trip与图表，不prune，单包小于20,000,000 bytes。', '',
    '旧26.9MB combined原样保留。另在`../formation_demo_long_split/`按E2400/J22400无损分包，各13,484,625/13,624,107 bytes；每个profile保留完整原轨迹。mapping覆盖原所有成员、公共材料重复，SHA见该目录verification.json。生产、候选、旧报告与旧封包均未修改，未Git操作。','']
(OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')

# Adapt only expected case counts and remove a cross-road test unavailable for L.
text=(OLD/'verify_long_demo.py').read_text(encoding='utf-8')
tree=ast.parse(text);node=next(n for n in tree.body if isinstance(n,ast.For) and isinstance(n.iter,ast.Call) and 'original_road_prefix_comparison.csv' in ast.unparse(n.iter))
ll=text.splitlines(True);text=''.join(ll[:node.lineno-1]+ll[node.end_lineno:])
text=text.replace('assert len(summary)==36','assert len(summary)==18').replace('assert len(pngs)==16','assert len(pngs)==8').replace('physical_runs=4','physical_runs=2').replace('registered_frames=16','registered_frames=8').replace('all_16_figures_visually_reviewed','all_8_figures_visually_reviewed')
(OUT/'verify_long_demo.py').write_text(text,encoding='utf-8')
seal=(OLD/'seal_long_demo.py').read_text(encoding='utf-8').replace("d.name in p['failed_operations']","d.name in p.get('failed_operations',[])").replace("['E2400-demo-','J22400-demo-','long-demo-']","['L2400-demo-','L-long-']").replace('includes_all_four_full_positions_events_diagnostic','includes_both_full_positions_events_diagnostic').replace('includes_failed_pre_SUMO_attempts=True','includes_failed_pre_SUMO_attempts=False')
seal=seal.replace("with tarfile.open(archive) as t:","assert archive.stat().st_size<20_000_000\nwith tarfile.open(archive) as t:")
(OUT/'seal_long_demo.py').write_text(seal,encoding='utf-8')
print(json.dumps(dict(report=str(OUT/'README.md'),all_selected_q_rows=len(q),verification_physical_runs=2,PNG_SVG_pairs_visually_reviewed=8)))
