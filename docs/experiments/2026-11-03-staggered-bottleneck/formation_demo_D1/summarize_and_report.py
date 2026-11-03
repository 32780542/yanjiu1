"""Only aggregate the original CTH/raw-dx geometry; no success evaluator."""
import csv,gzip,hashlib,json,statistics
from pathlib import Path
OUT=Path(__file__).resolve().parent;BASE=OUT.parent
def read(path):
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
summary=read(OUT/'snapshot_summary.csv');states=read(OUT/'snapshot_states.csv');runs=json.loads((OUT/'demo_results.json').read_text());protocol=json.loads((OUT/'protocol.json').read_text())
metrics=[];orders=[];large=[];whole=[]
for r in summary:
    rr=[s for s in states if s['demo']==r['demo'] and s['time_s']==r['time_s']]
    current=next(x for x in runs if x['demo']==r['demo'])
    dx=[float(s[f'adj_lane{i}_signed_dx_m']) for s in rr for i in range(3) if s[f'adj_lane{i}_id']]
    front=[s for s in rr if s['front_id']];gaps=[float(s['front_gap_m']) for s in front]
    ordered=sorted(rr,key=lambda s:float(s['x_m']));deltas=[float(b['x_m'])-float(a['x_m']) for a,b in zip(ordered,ordered[1:])]
    for i,s in enumerate(ordered):
        orders.append(dict(demo=r['demo'],time_s=r['time_s'],frame_kind=r['frame_kind'],anchor_offset_s=r['anchor_offset_s'],measured_x_order_index=i,vehicle_id=s['vehicle_id'],actual_lane=s['lane'],x_m=s['x_m'],y_m=s['y_m'],speed_mps=s['speed_mps'],dx_from_previous_measured_x='' if not i else deltas[i-1]))
    m={**r,'raw_signed_dx_min':min(dx),'raw_signed_dx_max':max(dx),'raw_abs_dx_min':min(map(abs,dx)),'raw_abs_dx_max':max(map(abs,dx)),
       'actual_front_gap_min_m':min(gaps),'actual_front_gap_max_m':max(gaps),'measured_x_neighbor_delta_min_m':min(deltas),'measured_x_neighbor_delta_max_m':max(deltas),
       'consecutive_measured_x_same_lane_pairs':sum(a['lane']==b['lane'] for a,b in zip(ordered,ordered[1:])),
       'first_trip_exit_s':current['first_actual_exit_s'],'first_missing_initial_frame_s':current['first_missing_initial_frame_s'],
       'at_or_after_first_trip_exit':float(r['time_s'])>=current['first_actual_exit_s']}
    metrics.append(m)
for current in runs:
    rows=read(OUT/current['version']/(current['demo']+'_geometry.csv.gz'))
    valid=[s for s in rows if s['front_id']]
    maximum=max(valid,key=lambda s:float(s['front_gap_m']))
    for s in valid:
        if float(s['front_gap_m'])>=50:large.append(dict(demo=current['demo'],**s))
    whole.append(dict(demo=current['demo'],full_geometry_rows=len(rows),all_trace_largest_actual_front_gap=maximum,all_trace_front_gap_ge_existing_50m_range_rows=sum(float(s['front_gap_m'])>=50 for s in valid)))
def write(name,rr):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
write('all_fixed_frame_metrics.csv',metrics);write('measured_x_order_states.csv',orders)
if large:write('all_untruncated_front_gaps_outside_existing50m.csv',large)
report=dict(rules_sha256=protocol['runtimes']['D12400']['rules_sha256'],input_sha256=protocol['input_sha256'],geometry_method='Original E geometry() reused verbatim; actual body-corridor front and actual nearest adjacent lane, no modulo/no clipping',formation_success_classifier_added=False,flag_used_as_geometry_proof=False,measured_x_order_is_offline_readonly_not_controller_reordering=True,registered_offsets=[0,5,10,15,20,25],all_fixed_frame_metrics=metrics,all_trace_geometry=whole,full_raw_retained=True,source_protocol_sha256=sha(OUT/'protocol.json'),summaries_sha256={n:sha(OUT/n) for n in ['snapshot_summary.csv','snapshot_states.csv','cross_lane_pair_references.csv','all_fixed_frame_metrics.csv','measured_x_order_states.csv']})
(OUT/'metric_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# D1：相同24/45初态的真实形成与3→2几何诊断','',
'两例均safe、全部排空、碰撞/瞬移0。实际坐标支持D1在这两个固定输入中形成并在3→2后恢复有秩序交错；没有用flag1、参与率或TT代替几何。未形成24在+10仍有CTH正残差9.417487米，+25尚有0.144223米最大正残差；这些过程没有删除。原45在+20全45仍在场且严格早于首退出，实际横向两道呈连续交错，+25帧仍45在场但恰在trip首退出时间边界，必须区分。此诊断不证明所有流量/种子的普遍性，不并入交通效率表。','',
'## 冻结来源与物理合同','',
'候选D1 423行，SHA `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`；基准其他五源和support来自上一轮冻结S。只将原native_sumo的两个出口坐标1200→2400，prep640、瓶颈1000、3→2、上游1000米/下游1400米、原物理/安全/执行保持原样。生产S及候选源不修改，输入不吸附、不重新排列。[完整源/input hash](protocol.json)、[两行网络patch](D12400_network_only.patch)、sources_original与新tmp runtime均保留。','',
'原24为三道各8辆、安全稀疏随机间距，原45为outer lane0/2领先middle lane1十五米（outer35+30i、middle20+30i），不是相反相位的旧几何初态。两份输入与既有formation_demo原件字节相同。全depart0/speed28.8，原生插入；flow1750仅元数据，`--initial`完全覆盖arrival tape，duration1/max180，不是新增流量实验。','',
'CTH为实际物理前车车头间距减本车速度对应`D(v)=5.5+(30−5.5)/28.8×v`；真实front无50米截断，无front记空。跨道dx为实际相邻车道最近车辆peer.x−ego.x，保留符号、不取模，不把几何最近邻冒充controller互选reference。全程geometry及原positions/diagnostic/events保留，包括>=50米的实际gap，不裁掉大孔或并排样本。离线按实际x列示仅为读数，不进入SUMO或控制器。','',
'## 原固定时刻与全注册下游帧','',
'原0/5/10/15/20全部保留；t0显示真实首物理帧0.1，不伪造0秒状态。anchor为最后一辆初始车首次被实测已过1000的帧；下游固定+0/5/10/15/20/25，无按整齐程度择帧。','',
'| 输入 | offset/实际t(s) | 在场 | CTH残差min/median/max(m) | raw跨道dx min/max(m) | 速度min/max(m/s) |','|---|---|---:|---|---|---|']
for m in metrics:
    if m['frame_kind']!='registered_downstream':continue
    lines.append(f'| {m["demo"]} | +{float(m["anchor_offset_s"]):g}/{float(m["time_s"]):.1f} | {m["onroad_n"]}/{m["initial_n"]} | {float(m["cth_error_min"]):+.6f}/{float(m["cth_error_median"]):+.6f}/{float(m["cth_error_max"]):+.6f} | {m["raw_signed_dx_min"]:+.6f}/{m["raw_signed_dx_max"]:+.6f} | {float(m["v_min"]):.6f}/{float(m["v_max"]):.6f} |')
lines+=['',
'45首trip退出为67.4秒，首实际缺失帧67.5；+25=67.4秒的diagnostic/positions仍有全45，所以显示45/45，并在metric JSON标`at_or_after_first_trip_exit=true`。这个帧不是严格首退出前证据；+20=62.4秒则全组在场且严格早于首退出。没有用退出后的孤立车宣称全队完成。','',
'## 全体实存几何与限制','']
for demo in ['unformed24','formed45']:
    for offset in [20.,25.]:
        m=next(r for r in metrics if r['demo']==demo and r['anchor_offset_s']==str(offset))
        lines.append(f'{demo} +{offset:g}：真实同道front gap范围{m["actual_front_gap_min_m"]:.6f}…{m["actual_front_gap_max_m"]:.6f}米；跨道最近raw绝对差{m["raw_abs_dx_min"]:.6f}…{m["raw_abs_dx_max"]:.6f}米；全部实存车辆按实际x读数的相邻坐标差{m["measured_x_neighbor_delta_min_m"]:.6f}…{m["measured_x_neighbor_delta_max_m"]:.6f}米，连续同车道相邻项{m["consecutive_measured_x_same_lane_pairs"]}。这是描述实际位置，不是新增形成门槛。')
lines+=['','原45在严格退出前+20实际全组44个相邻x间隔均约15米、车道交替、各同道间距约30米，没有形成两个局部编队之间的大边界孔；因此本输入可陈述整体恢复有序交错。用户未要求全路车辆必须合成满格单队；若其他输入出现合理局部编队边界，不能套本例强制追赶。24和45均有调距过程，未称瞬时保持精确平衡。','',
'[全部固定帧actual x/y/v/CTH](snapshot_states.csv)、[全部原符号跨道pair](cross_lane_pair_references.csv)、[完整注册统计与退出标记](all_fixed_frame_metrics.csv)、[实测x次序/每辆坐标](measured_x_order_states.csv)、[指标JSON](metric_summary.json)、[全程无截断gap索引](all_untruncated_front_gaps_outside_existing50m.csv)。原flag仅保留在positions/diagnostic和demo_results中，不作为几何证明。','',
'## 图、可运行入口与核验','']
for demo in ['unformed24','formed45']:
    lines.append(f'- {demo}：[原固定xy](D12400/{demo}_fixed_snapshots.png)、[全部六帧下游xy](D12400/{demo}_downstream_snapshots.png)、[时序](D12400/{demo}_time_series.png)、[全部实存v/CTH/raw dx](D12400/{demo}_downstream_all_states.png)，各保留同名SVG。')
lines+=['','复用academic-figures Nature本地Matplotlib样式，PNG300dpi+SVG，x轴0…2400，标640/1000，所有8图已逐图目检；图轴比例分别缩放，不根据画面长度推断间距。两个例子所有实存ID原数值见CSV/原迹。','',
'可运行顺序：新目录运行[prepare_demo.py](prepare_demo.py)冻结→[run_demo.py](run_demo.py)`--demo unformed24`/`--demo formed45`各走run_logged600→extract_long_demo.py→原tools/summarize_extra_demo.py指定本目录→plot_long_demo.py→summarize_and_report.py→verify_long_demo.py→seal_long_demo.py。已存在运行目录拒绝覆盖，重现需用新命名目录；不复制整仓、不建新worktree。所有实际运行操作日志纳入封包。','',
'[提取核验](extraction_verification.json)、[独立全轨迹几何/源/input/网络核验](final_verification.json)、[完整原件与图封包](evidence_reviewed.tar.gz)、[封包SHA](archive_verification.json)。完整raw保留不删，既有S及旧目录只读。','',
'准备阶段有一次PowerShell内联元数据编辑因引号解析失败，未运行SUMO、未触碰旧目录，随后用apply_patch精确修改新D1元数据/校验脚本；两例物理运行各仅一次，没有重跑或选好结果。','']
(OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps([m for m in metrics if m['frame_kind']=='registered_downstream' and m['anchor_offset_s'] in ['20.0','25.0']],ensure_ascii=False))
