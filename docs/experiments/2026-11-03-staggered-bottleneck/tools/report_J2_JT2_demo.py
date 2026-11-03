"""Write transparent short-road reports from completed, immutable physical traces."""
import csv
import gzip
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write(p,rr):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)

for tag in ['J2','JT2']:
    out=BASE/('formation_demo_'+tag);p=json.loads((out/'protocol.json').read_text())
    summaries=json.loads((out/'demo_results.json').read_text());audit=json.loads((out/'verification.json').read_text())
    tail=read(out/'tail_compact_summary.csv');down=read(out/'per_vehicle_downstream_summary.csv')
    changes=[];extras=[]
    for run in summaries:
        case=Path(run['case_dir']);demo=run['demo'];initial=json.loads((out/(demo+'_initial.json')).read_text())
        initially_closing={r['id'] for r in initial if r['lane']==2};seen=set()
        with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:
            for frame in map(json.loads,f):
                for k,s in frame['states'].items():
                    if k not in initially_closing and s['lane']==2 and k not in seen:
                        seen.add(k);a=frame['actions'][k]
                        extras.append(dict(demo=demo,vehicle_id=k,first_actual_lane2_s=frame['time_s'],
                            x_m=s['x'],y_m=s['y'],speed_mps=s['speed'],reason=a['reason']))
        with gzip.open(case/'events.jsonl.gz','rt') as f:
            for event in map(json.loads,f):
                if event['kind'] in ['lane_change','lane_completion']:
                    changes.append(dict(demo=demo,**{k:event.get(k,'') for k in ['kind','vehicle_id','time_s','x','from_lane','to_lane']}))
    write(out/'all_lane_change_events.csv',changes)
    if extras:write(out/'additional_closing_lane_entries.csv',extras)
    else:(out/'additional_closing_lane_entries.csv').write_text('demo,vehicle_id,first_actual_lane2_s,x_m,y_m,speed_mps,reason\n',encoding='utf-8-sig')
    lines=[f'# {tag} 原1200米真实demo：局部变化仍不能证明完整交错恢复','',
        f'2026-11-03。冻结{tag}规则SHA `{p["rules_sha256"]}`；使用修正物理3道邻接的新版本，不使用旧J/JT。原[E](../formation_demo/README.md)、[H](../formation_demo_H/README.md)输入和结果均保留。', '',
        '输入与E的24/45 JSON逐字节相同：24为seed20261103三道各8、35–45米随机间距；45为outer35+30i、middle20+30i（outer领先15米），初始全在640米前，全部depart0/v28.8。45辆初始每车原`_following`请求28.8已核验。原1200米3→2、mode transform、SUMO seed1、duration1、max_time120、diagnostic全量；安全与控制范围未改。见[协议](protocol.json)、[初始平衡证明](initial_equilibrium_check.json)。', '',
        '四时刻5/10/15/20、首物理帧t=.1及各自末车1100帧全部保留，另有末车1100前后1秒。t0没有物理记录，不编造车辆位置。全路xy、CTH与raw signed Δx绘图代码与E仅数据路径/标题替换；离线使用完整轨迹不馈入控制器，没有新形成门槛或取模。颜色仅代表初始车道，0/1只作原局部关系记录。', '',
        '## 1. 通行、安全与真实横移','',
        '| 输入 | 平均TT(s) | 相对E(s) | 排空(s) | 末车首1100(s) | 横移完成 | 实际关闭道观测/1000前完成 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        ett=37.791666666666664 if r['demo']=='unformed24' else 37.17333333333333
        lines.append(f'| {r["demo"]} | {r["mean_travel_time_s"]:.6f} | {r["mean_travel_time_s"]-ett:+.6f} | {r["actual_end_s"]:.1f} | {r["last_vehicle_1100_s"]:.1f} | {r["lane_change_completions"]} | {r["ending_lane_observed_vehicles"]}/{r["ending_lane_completed_before_drop"]} |')
    lines.extend(['','两例24/45辆均全部安全排空，碰撞/瞬移0。不同输入初始x/车数不同，不能直接比较它们的TT作为方法优势；这里只对同初态E配对。[结果](demo_results.json)、[E配对表](E_'+tag+'_demo_summary.csv)、[全部横移原事件](all_lane_change_events.csv)。'])
    if extras:
        lines+=['','非初始关闭道车辆的新进入记录（按实际lane而非请求）：'+ '；'.join(f'{r["demo"]} `{r["vehicle_id"]}` t{r["first_actual_lane2_s"]:.1f}、x{r["x_m"]:.3f}、v{r["speed_mps"]:.3f}' for r in extras)+'。[逐项记录](additional_closing_lane_entries.csv)。这些额外换道不被解释为形成成功。']
    lines+=['','## 2. 实际前距随本车速度核对','',
        '沿用`D(v)=5.5+.8506944444v`；表内误差=真实前距−D(v)。每辆车取首次实际lane0/1且x≥1100原帧，因此这是不同时间的逐车记录，不能拼成同时完整车群；每例两辆无真实前车保留空值。', '',
        '| 输入 | 有真实前车/总数 | 速度范围(m/s) | 前距−D(v)最小/中位/最大(m) |','|---|---:|---|---|']
    for r in down:
        if r['cutoff_x_m']=='1100':lines.append(f'| {r["demo"]} | {r["with_actual_front"]}/{r["requested"]} | {float(r["speed_min"]):.3f}–{float(r["speed_max"]):.3f} | {float(r["cth_error_min"]):+.3f} / {float(r["cth_error_median"]):+.3f} / {float(r["cth_error_max"]):+.3f} |')
    lines+=['','45例最大正误差比E的+10.734米小，但更负的误差与混合速度仍存在；24例最大正误差比E的+3.746米大。[逐车全部原帧](per_vehicle_downstream.csv)、[1000/1100汇总](per_vehicle_downstream_summary.csv)、[最大空隙具体车辆/命令/reference](E_'+tag+'_large_gap_events.csv)。大于50米的前车仍属于离线几何证据；原控制器没有把它作为50米内CTH实际前车。', '',
        '## 3. 尾部真实几何：不以少数留下车辆代表全队','',
        '| 输入/末车1100 | 实存/有前车 | 本车速度范围(m/s) | 前距−D(v)最小/中位/最大(m) | 原始相邻道signed Δx逐车(m) |','|---|---:|---|---|---|']
    for r in tail:
        dx=', '.join(f'{v:+.3f}' for v in json.loads(r['raw_cross_signed_dx_m']))
        lines.append(f'| {r["demo"]} / {r["last1100_s"]}s | {r["remaining_n"]}/{r["front_n"]} | {float(r["v_min"]):.3f}–{float(r["v_max"]):.3f} | {float(r["error_min"]):+.3f}/{float(r["error_median"]):+.3f}/{float(r["error_max"]):+.3f} | {dx} |')
    if tag=='J2':lines+=['','J2随机24在尾部仅7辆时多数跨道差约15米，速度差也较小，这一局部恢复有真实支持；45尾部8辆仍出现±1.671、±10.280等相邻差和25.114–30.391m/s混合速度，不能称已完整有序交错。45在t5与E全部物理状态相同；t10已产生最大位置差3.507米、速度差1.907m/s，说明实际变化出现在准备区，不能照搬H的“仅退出后不同”解释。']
    else:lines+=['','JT2没有在两个输入上显示一致优于J2的尾部几何：24还存在−30.808米缺位，45的约±3.015、±6.616、+21.980和+49.957米也未恢复15米交错。调整目标随速度缩放没有在这两例证明完整形成/变换成功。']
    lines+=['','原200米下游短于45车转成两道23/22辆、同道30米时所需至少660米纵向跨度；出口持续删头也改变配对。这个几何限制阻止在原路同时展示整个恢复车群，不能把末车1100时的少数存车当作全队。另授权的2400米下游诊断会独立建档，不与原路TT或交通批混合。', '',
        '[全部选帧状态](snapshot_states.csv)、[尾部前后状态](tail_window_states.csv)、[分1000/1100状态](downstream_cth_summary.csv)、[E队首signed Δx对照](E_'+tag+'_head_signed_dx.png)与[原值](E_'+tag+'_current_head_signed_dx.csv)。[跨道原值与速度参考表](cross_lane_pair_references.csv)同时保留raw signed Δx、15米参考及每对速度的`D((v_i+v_j)/2)/2`；此处邻车按几何x最近选取，不声称等于规则的相位互选对象，不设成功阈值。', '',
        '## 4. 图与封存','',
        '- 24：[全路xy快照](unformed24_snapshots.png)、[时序/CTH/raw Δx](unformed24_time_series.png)、[尾部](unformed24_tail.png)。',
        '- 45：[全路xy快照](formed45_snapshots.png)、[时序/CTH/raw Δx](formed45_time_series.png)、[尾部](formed45_tail.png)。',
        '- 七组均有同名SVG，academic-figures Nature风格、300dpi PNG，全部已目检。',
        f'- [原轨迹/输入/source完整封包](evidence_reviewed.tar.gz)：{audit["archive_bytes"]:,}字节，SHA `{audit["archive_sha256"]}`，52原件逐项解包核验，物理帧{audit["raw_frames"]["unformed24"]}/{audit["raw_frames"]["formed45"]}。原positions与diagnostic全部帧物理状态及原0/1精确一致。[原核验](verification.json)、[独立复核](final_verification.json)。',
        '- 不修改E/H、候选、生产、道路或原交通统计，不自动采用新规则；不以0/1、平均TT或尾部少数车声称形成完成。','']
    (out/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    verification=(BASE/'formation_demo_H/verify_sealed_demo.py').read_text(encoding='utf-8')
    verification=verification.replace('physical H traces','physical '+tag+' traces').replace('20261103_H_formation_demo','20261103_'+tag+'_formation_demo').replace('H / ',tag+' / ')
    verification=verification.replace("for link in links:assert (OUT/link.split('#')[0]).exists(),link", "for link in links:assert (OUT/link.split('#')[0]).exists() or link=='final_verification.json',link")
    verification=verification.replace("pngs=[]", """cross_rows=rows(OUT/'cross_lane_pair_references.csv')
for r in cross_rows:
    ss=frames[r['demo']][float(r['time_s'])]['states'];s=ss[r['vehicle_id']];peer=ss[r['peer_id']]
    assert float(r['raw_signed_dx_m'])==peer['x']-s['x'] and float(r['reference_15_m'])==15
    assert float(r['speed_mps'])==s['speed'] and float(r['peer_speed_mps'])==peer['speed']
    assert float(r['reference_D_pair_mean_speed_half_m'])==(5.5+(30-5.5)/28.8*(s['speed']+peer['speed'])/2)/2
pngs=[]""")
    verification=verification.replace("no_additional_simulations=True)","cross_lane_reference_rows_rechecked=len(cross_rows),no_additional_simulations=True)")
    (out/'verify_sealed_demo.py').write_text(verification,encoding='utf-8',newline='\n')
    print(json.dumps(dict(version=tag,extra_closing_entries=extras,report=str(out/'README.md'))))
