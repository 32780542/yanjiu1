"""Write a measured geometric report; no formation labels or selected pretty frames."""
import csv
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
p=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
results=json.loads((OUT/'demo_results.json').read_text())
with (OUT/'snapshot_summary.csv').open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
lines=['# 2400米下游诊断：全体在场的交错几何实测','',
    '2026-11-03。**预成形45辆的变换后，J2在长下游显示比E更接近15米交错的全组几何；24辆仍有明显同道缺口，不能宣布完整形成问题已解决。** 此轮只延长观测道路，不改控制器，不作为正式效率样本，也不与原1200米的TT跨道路直接比较。', '',
    '## 1. 冻结合同与预登记帧','',
    '- E2400控制器SHA `04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274`；J22400为J2+2400标签，控制器SHA `895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689`。没有使用旧J/JT，也没有引入JT2。',
    '- 每个runtime仅`build_network`两处exit坐标1200→2400；控制器及五份其余源逐字节不变。原配置和包init原样带入。两行补丁：[E2400](E2400_network_only.patch)、[J22400](J22400_network_only.patch)。原源存于`sources_original/`；完整前后SHA在[协议](protocol.json)。',
    '- 原24/45 JSON逐字节复用：所有depart0、speed28.8、原生插入，无重排/吸附。原3→2瓶颈1000、prep640不变；网XML实测upstream1000米/3道、downstream1400米/2道，exit2400。duration1/max_time180，mode transform，SUMO seed1，全positions/events/diagnostic保留。',
    '- [预登记](protocol_initial_attempt.json)保留原请求0/5/10/15/20秒（实际首帧.1，未伪造t0）。另以“最后一辆初始车首次被实际观测过1000米”的原帧为anchor，只用其+0/+5/+10/+15秒四帧。各case自己的anchor不同，不把不同绝对时间当成同一时刻。',
    '- 四例所有预定下游帧均24/45辆全体在场、无提前退出，实际lane2均0。[所有ID/车道/本车v/CTH/raw相邻Δx](snapshot_states.csv)、[逐帧人数与退出ID](snapshot_summary.csv)。0/1只是原局部关系记录，不用于形成成败。','',
    '原路200米不能同时容纳45辆转成两道23/22辆、同道30米的至少660米车头跨度；出口反复删头也会改变相位对象。本诊断通过更长物理下游解决完整观测限制，既不修改正式道路，也不由此推断原路效率提升。', '',
    '## 2. 全部预登记下游帧','',
    '| 方法/输入 | anchor+偏移(s) / 实际t(s) | 全体在场 | 实际0/1道数 | 本车v范围(m/s) | 实际前距−D(v)最小/中位/最大(m) |',
    '|---|---|---:|---|---|---|']
for r in rr:
    if r['frame_kind']!='registered_downstream':continue
    lines.append(f'| {r["version"]}/{r["demo"]} | +{float(r["anchor_offset_s"]):g} / {float(r["time_s"]):.1f} | {r["onroad_n"]}/{r["initial_n"]} | {r["n_lane0"]}/{r["n_lane1"]} | {float(r["v_min"]):.3f}–{float(r["v_max"]):.3f} | {float(r["cth_error_min"]):+.3f}/{float(r["cth_error_median"]):+.3f}/{float(r["cth_error_max"]):+.3f} |')
lines+=['','`D(v)=5.5+(30−5.5)/28.8×v`，按每辆本车实际速度计算。实际前车按原离线物理走廊定义，包括当帧跨线车体；无真实前车保留空值。每帧24例22、45例43个真实前车，其余是仍在场的两道队首，未将空值当误差0。[每对raw signed Δx和15米/速度参考](cross_lane_pair_references.csv)完整保留，不取模或增设成功阈值；该表是几何x最近邻，不宣称等于控制器相位互选对象。', '',
    '## 3. 明确的改善与未解决项','',
    '**45辆预成形后的变换：**在anchor+15，J2全45辆仍在场，跨道最近signed Δx大多在±14.94…15.00米，剩余局部约±13.38/13.99米；E此时仍有约±9.15…10.19米相位段。J2全部真实前车误差为−1.788/中位+.002/+1.018米；E有+23.993米大空隙。故在本固定输入与1400米下游，J2对全组几何的改善有实测支持。J2速度仍27.603–31.104m/s，并非所有车辆已同速或精确平衡；不能据这一有限时窗宣布任意初态完整成功。', '',
    '**24辆未成形：**两方法在anchor+15多数跨道差都接近15米。E仍为11/13车道分配、尾部有+44.504米的最近跨道差，但同道CTH误差已约−.036…+.025米。J2为13/11分配，raw跨道差约±13.995…14.939米；同道仍有58.792米缺口、相对D(v)超出+28.909米。跨道近15与同道缺层可以并存，因此不能只看相邻跨道差或0/1就说24辆形成完成，也不能说J2在此输入全面优于E。', '',
    '两个残留空隙有具体原帧证据（[全16帧极值事件](registered_cth_extreme_events.csv)）：', '',
    '- E45，t57.3，`formed_l1_r05`，x1649.523、lane0、v28.8，真实前车`formed_l1_r06`前距53.993，D≈30、误差+23.993；动作formation_follow，reference空，仍在原50米CTH范围外。',
    '- J2 24，t52.8，`unformed_l2_r05`，x1674.374、lane1、v28.663，前车`unformed_l2_r06`前距58.792，D29.884、误差+28.909；跨道最近`unformed_l1_r06`raw dx+14.565，动作formation_follow，CF reference空。没有隐去这个与“看起来交错”同时存在的缺层。', '',
    '全轨迹时序还保留了所有车辆后续运动及退出后的扰动，没有为了整齐而增选另一张下游帧。这里没有新增形成评价器、成功阈值或控制规则；改善结论仅指表列真实间距/速度与图示几何。','',
    '## 4. 相同控制、原路前缀与安全','',
    '四例均全部安全排空、碰撞/瞬移0。平均TT仅在原result与[本轮原结果](demo_results.json)中保留，不并入原1200米统计，也不以2400/1200的TT作直接效率比较。网XML、source/input、SUMO命令、trips、events、positions、diagnostic完整保存。', '',
    '[跨道路前缀核对](original_road_prefix_comparison.csv)：同控制器、同初态在原路首个车辆不再出现在物理记录前，E24/E45/J2 24/J2 45分别318/257/322/259帧所有x/y/v及其余物理状态完全一致，最大差0。表同时分别列trip exited_s与下一帧首次缺车时刻，避免0.1秒记录定义混淆。因此图中准备区没有因长道路提前改变原运动；后续差异应在出口保留车辆的不同边界条件下解释。', '',
    '首次打包漏带原configs/tools.json，四个attempt在SUMO启动前0.4秒左右失败；[首版协议](protocol_initial_attempt.json)及四份失败operation保留。重试新建runtime与output retry2，仅逐字节补齐原配置/init，没有改源或覆盖失败目录；四例通过run_logged timeout600完成。完整失败/成功操作路径随封包保留。','',
    '## 5. 全图与可复核原件','',
    '每例四组图：原固定帧xy、四预登记下游xy（全部实存ID）、原3×3时序、四预登记帧全部实存v/CTH/raw Δx。均使用同一个[绘图程序](plot_long_demo.py)，academic-figures Nature风格、300dpi PNG+SVG、无车辆重排。xy轴0…2400米，标640/1000；x/y比例分别缩放；时序/状态纵轴按实际范围自动缩放，应读刻度或CSV数值，不比较不同面板点云的视觉幅度。状态图标记圆形=当前lane0、三角=其他实际道，颜色只代表初始道。','']
for tag in ['E2400','J22400']:
    for demo in ['unformed24','formed45']:
        lines.append(f'- {tag}/{demo}：[原固定xy]({tag}/{demo}_fixed_snapshots.png)、[预登记下游xy]({tag}/{demo}_downstream_snapshots.png)、[时序]({tag}/{demo}_time_series.png)、[全部下游状态]({tag}/{demo}_downstream_all_states.png)，均有同名SVG。')
lines+=['','全部16组图已目检；[提取核验](extraction_verification.json)、[独立全轨迹与源核验](final_verification.json)。[原轨迹及输入/source封包](evidence_reviewed.tar.gz)含逐文件SHA manifest，封包的最终SHA见[封存信息](archive_verification.json)。E/H/J2/JT2原路证据保持不变。','']
(OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
print({'report':str(OUT/'README.md'),'registered_rows':16,'fixed_snapshot_times_unchanged':True})
