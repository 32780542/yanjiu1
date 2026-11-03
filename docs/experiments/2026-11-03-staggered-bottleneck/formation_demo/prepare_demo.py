"""Freeze two predeclared native-request initial configurations, without running SUMO."""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
RUNTIME=ROOT/'tmp/staggered_bottleneck/20261103_heldout_E40/sources/E'
EXPECTED='04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274'
assert hashlib.sha256((RUNTIME/'noa/native_rules.py').read_bytes()).hexdigest()==EXPECTED
seed=20261103
rng=random.Random(seed)
rows=[]
for lane in range(3):
    x=rng.uniform(0,8)
    for rank in range(8):
        if rank:x+=rng.uniform(35,45)
        rows.append(dict(id=f'unformed_l{lane}_r{rank:02d}',depart=0,lane=lane,x=x,speed=28.8))
assert len(rows)==24 and max(r['x'] for r in rows)<=330
formed=[dict(id=f'formed_l{lane}_r{rank:02d}',depart=0,lane=lane,
             x=35+30*rank-(15 if lane==1 else 0),speed=28.8)
        for lane in range(3) for rank in range(15)]
assert len(formed)==45 and min(r['x'] for r in formed)==20 and max(r['x'] for r in formed)<640
configs={'unformed24':rows,'formed45':formed}
for name,initial in configs.items():
    path=OUT/(name+'_initial.json')
    assert not path.exists()
    path.write_text(json.dumps(initial,indent=2)+'\n',encoding='utf-8')
protocol=dict(frozen_runtime=str(RUNTIME),rules_sha256=EXPECTED,initial_random_seed=seed,
    mode='transform',scenario='lane_drop',sumo_seed=1,duration_s=1,max_time_s=120,diagnostic=True,
    original_positions_events_diagnostic_retained=True,
    fixed_snapshot_requested_times_s=[0,5,10,15,20],
    final_snapshot='First stored frame after every requested vehicle has observed x>=1100m, if before drainage',
    actual_t0_policy='No t=0 physical frame is fabricated; first stored physical frame is shown with actual time; request t0 is separately labelled.',
    selected_geometry_ids={name:[f'{"unformed" if name=="unformed24" else "formed"}_l{lane}_r{4 if name=="unformed24" else 7:02d}' for lane in range(3)] for name in configs},
    initial_sha256={name:hashlib.sha256((OUT/(name+'_initial.json')).read_bytes()).hexdigest() for name in configs},
    initial_limits={name:dict(n=len(rs),min_x=min(r['x'] for r in rs),max_x=max(r['x'] for r in rs)) for name,rs in configs.items()},
    source_sha256={str(p.relative_to(RUNTIME)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [RUNTIME/'run_native_flow.py',RUNTIME/'experiments/native_sumo.py',RUNTIME/'noa/native_rules.py',RUNTIME/'research/common.py']})
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(protocol,ensure_ascii=False))
