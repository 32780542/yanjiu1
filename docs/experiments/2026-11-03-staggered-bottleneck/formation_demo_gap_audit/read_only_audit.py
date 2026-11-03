"""Audit actual intermediate-layer witnesses and short local geometry history.

Reads immutable traces only; the proposed witness predicate is not a controller
rule or a formation success classifier.
"""
import ast
import csv
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

OUT=Path(__file__).resolve().parent
BASE=OUT.parent
LONG=BASE/'formation_demo_long'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={
    'formation_demo':'b97209b2612c27a4d177ea1595c929ad7b468adf3ae49488cc44e60987433585',
    'formation_demo_H':'fc2162df5ca3d7ca38653ff9755f7aea8c4a9ab9bdb07a59c6a368f092ecf1c3',
    'formation_demo_J2':'0fbf28680ff8ea19ba855e145e1f96fc6c4aaa609ff8cc7f506be643b7a71ff9',
    'formation_demo_JT2':'da47465d6bdae379a1e66d99e68b295626a1f1f16b322f14f016eaa96a1b4a66',
    'formation_demo_long':'6fefa8466985a9bfdce30652f8c6bb163d6f3018882fe22d994000cfb453e766'}
for folder,h in expected.items():assert sha(BASE/folder/'evidence_reviewed.tar.gz')==h
protocol=json.loads((LONG/'protocol.json').read_text())
rules=Path(protocol['runtimes']['J22400']['frozen_runtime'])/'noa/native_rules.py'
assert sha(rules)=='895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689'
tree=ast.parse(rules.read_text(encoding='utf-8'))
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['_phase','_physical_phase']]
assert len(functions)==2
env=dict(GAP=30.,LANE_WIDTH=3.3)
exec(compile(ast.Module(body=functions,type_ignores=[]),str(rules),'exec'),env)
phase=lambda s:env['_physical_phase'](SimpleNamespace(**s),3)

def write(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

cases={};frame_maps={}
for r in json.loads((LONG/'demo_results.json').read_text()):
    if r['version']!='J22400':continue
    cases[r['demo']]=r
    with gzip.open(Path(r['case_dir'])/'diagnostic.jsonl.gz','rt') as f:frame_maps[r['demo']]={r['time_s']:r for r in map(json.loads,f)}
f=frame_maps['unformed24'][52.8];ss=f['states']
ego_id='unformed_l2_r05';front_id='unformed_l2_r06';ego=ss[ego_id];front=ss[front_id]
gap=front['x']-ego['x'];assert 50<gap<=60
assert ego['lane']==front['lane']==1
assert min((k for k,s in ss.items() if s['lane']==ego['lane'] and s['x']>ego['x']),key=lambda k:ss[k]['x'])==front_id
adj=[]
for k,s in sorted(ss.items(),key=lambda kv:kv[1]['x']):
    if abs(s['lane']-ego['lane'])!=1:continue
    residual=(s['x']+phase(s)-phase(ego))-(front['x']-30)
    between=ego['x']<s['x']<front['x']
    adj.append(dict(time_s=52.8,ego_id=ego_id,front_id=front_id,front_gap_m=gap,
        candidate_id=k,lane=s['lane'],x_m=s['x'],y_m=s['y'],speed_mps=s['speed'],physical_phase_3_m=phase(s),q_m=s['x']+phase(s),
        raw_signed_dx_from_ego_m=s['x']-ego['x'],within_50m_of_ego=abs(s['x']-ego['x'])<=50,
        strictly_between_ego_and_front=between,proposed_witness_residual_m=residual,
        abs_residual_le_2m=abs(residual)<=2,proposed_actual_witness=between and abs(residual)<=2))
write('J2_24_t52p8_all_adjacent_candidates.csv',adj)
witnesses=[r for r in adj if r['proposed_actual_witness']];assert len(witnesses)==1
assert witnesses[0]['candidate_id']=='unformed_l0_r05'

qrows=[]
for name,t in [('unformed24',52.8),('formed45',56.8)]:
    ff=frame_maps[name][t];states=ff['states']
    assert len(states)==cases[name]['initial_n']
    for k,s in sorted(states.items(),key=lambda kv:(kv[1]['x']+phase(kv[1]),kv[1]['lane'],kv[1]['x'])):
        ahead=min((oid for oid,other in states.items() if other['lane']==s['lane'] and other['x']>s['x']),key=lambda oid:states[oid]['x'],default=None)
        behind=max((oid for oid,other in states.items() if other['lane']==s['lane'] and other['x']<s['x']),key=lambda oid:states[oid]['x'],default=None)
        qrows.append(dict(demo=name,time_s=t,vehicle_id=k,lane=s['lane'],x_m=s['x'],y_m=s['y'],speed_mps=s['speed'],physical_phase_3_m=phase(s),q_m=s['x']+phase(s),
            command_speed_mps=ff['actions'][k]['speed'],reason=ff['actions'][k]['reason'],
            actual_same_lane_ahead_id=ahead,actual_same_lane_front_gap_m=states[ahead]['x']-s['x'] if ahead else None,
            actual_same_lane_behind_id=behind,is_actual_lane_head=ahead is None,is_actual_lane_tail=behind is None))
write('actual_q_sequences.csv',qrows)

pair_ids=[('formed_l1_r00','formed_l2_r01'),('formed_l2_r00','formed_l1_r02')]
history=[]
for t in [55.8,56.8,57.8]:
    ff=frame_maps['formed45'][t];states=ff['states']
    for a,b in pair_ids:
        s,c=states[a],states[b];qerr=c['x']+phase(c)-s['x']-phase(s)
        nearest_a=min((k for k,v in states.items() if v['lane']!=s['lane']),key=lambda k:abs(states[k]['x']-s['x']))
        nearest_b=min((k for k,v in states.items() if v['lane']!=c['lane']),key=lambda k:abs(states[k]['x']-c['x']))
        history.append(dict(time_s=t,ego_id=a,peer_id=b,ego_lane=s['lane'],peer_lane=c['lane'],ego_x_m=s['x'],peer_x_m=c['x'],ego_speed_mps=s['speed'],peer_speed_mps=c['speed'],
            ego_command_speed_mps=ff['actions'][a]['speed'],peer_command_speed_mps=ff['actions'][b]['speed'],
            ego_phase_3_m=phase(s),peer_phase_3_m=phase(c),ego_q_m=s['x']+phase(s),peer_q_m=c['x']+phase(c),
            raw_signed_dx_m=c['x']-s['x'],q_peer_minus_q_ego_m=qerr,peer_speed_minus_ego_speed_mps=c['speed']-s['speed'],
            are_mutual_actual_x_nearest_adjacent=nearest_a==b and nearest_b==a,
            ego_is_lane_tail=not any(v['lane']==s['lane'] and v['x']<s['x'] for v in states.values()),
            peer_is_lane_tail=not any(v['lane']==c['lane'] and v['x']<c['x'] for v in states.values()),
            all_initial_n=len(states),no_initial_exited_yet=t<cases['formed45']['first_actual_exit_s']))
write('J2_45_tail_pair_local_history.csv',history)

lines=['# J2长下游局部缺口：真实跨道层只读核查','','本轮未启动仿真、未实现规则、未改原报告或旧封包。这里仅核对父任务提出的几何witness，不新增形成评价器或“全24辆必须连成一队”的要求。两个局部编队之间两道共同空白，可以是合法边界；单凭大同道前距不能断言形成失败。','',
    '## 24辆：该58.792米缺口内确有中间交错层','',
    'J22400原诊断t52.8，24辆全在场，实际lane0/1=13/11；道路出口首退车t73.5之前（精确首退车见原demo_results.json）。按冻结J2原`_physical_phase(car,3)`逐字提取的函数计算q=x+phi，包含实际y的连续插值，不取模，不按ID分配相位。','',
    '| 角色/实车 | 实际道 | x(m) | phi(m) | q(m) | v(m/s) |',
    '|---|---:|---:|---:|---:|---:|']
localids=['unformed_l2_r05','unformed_l1_r06','unformed_l0_r05','unformed_l2_r06','unformed_l0_r06']
for k in localids:
    s=ss[k];lines.append(f'| {k} | {s["lane"]} | {s["x"]:.6f} | {phase(s):.6f} | {s["x"]+phase(s):.6f} | {s["speed"]:.6f} |')
w=witnesses[0]
lines+=['',f'ego→实际同道front为`{ego_id}`→`{front_id}`，真实车头前距{gap:.9f}m，满足此次待研究范围50<gap≤60。实际邻道中间车`{w["candidate_id"]}`位于ego.x与front.x之间，距ego{w["raw_signed_dx_from_ego_m"]:.9f}m；按给定式`(c.x+phi(c)-phi(ego))−(front.x−30)`，残差{w["proposed_witness_residual_m"]:+.9f}m，满足给定绝对值≤2m。**因此该具体缺口有实际witness，不是两道共同空白的局部编队边界。**', '',
    'q序列局部为1688.938954(邻道车l1_r06)、1689.374146(ego)、1718.228258(邻道中间层l0_r05)、1748.166542(front)、1748.190931(邻道车l0_r06)。只有q≈1718层缺少ego同道的对应车；原最近邻l1_r06与ego属于q≈1689的已配对层，不能将该最近邻误当中间witness。所有13辆实际邻道车均在[候选表](J2_24_t52p8_all_adjacent_candidates.csv)，未只输出命中者。','',
    '这里只证明现存几何占用与指定witness条件成立。该front距ego58.792m，在原CTH跟驰的50m范围外；不能由本离线表直接宣称原控制器已知它，也不能自动获得新感知/通信权限。此处没有要求跨局部编队追赶，没有实现跨道桥接。','',
    '## 45辆：13.38/13.99米是实车仍在调距','',
    '同一原轨迹t56.8，全45辆仍在场，首退出t67.6。两处都有互为实际x最近邻的真实邻道车辆。第一对处于两道各自尾端，但两端车辆均实际存在；第二对在尾端内侧。因此“端点缺对应车”不能解释这两处偏差。','',
    '| 实际车辆对（lane1→lane0） | t(s) | raw dx(m) | q_peer−q_ego(m) | peer.v−ego.v(m/s) |',
    '|---|---:|---:|---:|---:|']
for r in history:lines.append(f'| {r["ego_id"]} → {r["peer_id"]} | {r["time_s"]:.1f} | {r["raw_signed_dx_m"]:.6f} | {r["q_peer_minus_q_ego_m"]:+.6f} | {r["peer_speed_minus_ego_speed_mps"]:+.6f} |')
lines+=['','该表固定追踪t56.8这两对真实车辆，使用前后各1秒原帧核查局部运动，不另挑整齐帧替换原16张预登记下游图。第一对raw dx从8.316→13.383→15.160；第二对11.783→13.988→14.729，对应q偏差正在缩小并有轻微过冲。t56.8的速度分别27.603/31.104与28.951/30.291m/s，说明它们仍在相对调距；不能把当帧非15m直接解释为欠一个层车辆。57.8时第一对已非互为raw x最近邻（CSV如实为False），因为lane0车到另一辆lane1车约15.075m、到所跟踪尾车15.160m；这不表示原车退出或消失，也不应混淆raw最近邻与控制器基于q的配对。详见[两对真实历史、速度和命令](J2_45_tail_pair_local_history.csv)。','',
    '## 来源与限制','',
    '- [完整实际q序列/坐标/速度及真实同道前后车](actual_q_sequences.csv)：t52.8的24辆和t56.8的45辆全部列出，q排序只用于离线展示，不进入控制器。',
    '- 原数据：`../formation_demo_long/demo_results.json`中J22400两case的全量`diagnostic.jsonl.gz`，每行time/state/action原件；冻结controller SHA `895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689`。原控制定义`_physical_phase`与`_front_following`见冻结`noa/native_rules.py:71–114`。',
    '- 结论针对这些具体原帧；不把单处空格视为全局形成失败，不将几何排序或指定witness容差升级为形成门槛，不评价尚未运行的K。',
    '- 原E/H/J2/JT2与long五个封包SHA在分析前后均核对不变；核验见[verification.json](verification.json)。','']
# Read the recorded first exit rather than introducing another handwritten value.
lines=[s.replace('道路出口首退车t73.5之前',f'道路出口首退车t{cases["unformed24"]["first_actual_exit_s"]:.1f}之前') for s in lines]
(OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
for folder,h in expected.items():assert sha(BASE/folder/'evidence_reviewed.tar.gz')==h
verification=dict(no_new_simulations=True,no_controller_changes=True,old_archive_sha256_unchanged=expected,
    controller_sha256=sha(rules),raw_inputs={n:dict(case_dir=r['case_dir'],diagnostic_sha256=sha(Path(r['case_dir'])/'diagnostic.jsonl.gz')) for n,r in cases.items()},
    phase_function_extracted_verbatim_from_frozen_source=True,all_actual_adjacent_candidates=len(adj),actual_witnesses=witnesses,
    all_vehicle_q_rows=len(qrows),pair_history_rows=len(history),full_presence_at_all_analyzed_times=True,
    output_sha256={n:sha(OUT/n) for n in ['J2_24_t52p8_all_adjacent_candidates.csv','actual_q_sequences.csv','J2_45_tail_pair_local_history.csv','README.md']})
(OUT/'verification.json').write_text(json.dumps(verification,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(actual_witness_id=w['candidate_id'],witness_residual_m=w['proposed_witness_residual_m'],front_gap_m=gap,all_adjacent_candidates=len(adj),all_vehicle_q_rows=len(qrows),pair_history_rows=len(history),old_five_archives_unchanged=True)))
